#!/usr/bin/env node
// node video/render.mjs storyboards/<id>.json [--format 16x9|9x16|both] [--skip-narrate] [--no-hero] [--frames]
//
// 1. narrate.py -> per-scene mp3 + word timings (cached)
// 2. stage fonts, logo, media and audio into .cache/public
// 3. bundle the Remotion project, render 16:9 and/or 9:16, a poster PNG and a silent hero loop
// Outputs go to video/out/<id>/ (gitignored). A run log with durations and sizes is written beside them.

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { buildTimeline, totalFrames } from "./src/timeline.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n, d) => {
  const i = args.indexOf(`--${n}`);
  return i >= 0 ? args[i + 1] : d;
};
const sbArg = args.find((a, i) => !a.startsWith("--") && !(i > 0 && args[i - 1] === "--format"));
if (!sbArg) {
  console.error("usage: node render.mjs storyboards/<id>.json [--format 16x9|9x16|both] [--skip-narrate] [--no-hero] [--frames]");
  process.exit(1);
}
const sbPath = fs.existsSync(path.resolve(sbArg)) ? path.resolve(sbArg) : path.resolve(ROOT, sbArg);
const storyboard = JSON.parse(fs.readFileSync(sbPath, "utf8"));
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const formats = opt("format", "both") === "both" ? ["16x9", "9x16"] : [opt("format")];
const outDir = path.join(ROOT, "out", storyboard.id);
fs.mkdirSync(outDir, { recursive: true });

const log = [];
const warnings = [];
const say = (m) => {
  console.log(m);
  log.push(m);
};
const warn = (m) => {
  warnings.push(m);
  say(`WARNING: ${m}`);
};
const t0 = Date.now();
const secs = (t) => ((Date.now() - t) / 1000).toFixed(1);
const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(2);
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);

say(`# ${storyboard.id} render, ${new Date().toISOString()}`);

// 1. narration
let t = Date.now();
if (!flag("skip-narrate")) {
  execFileSync("python3", [path.join(ROOT, "narrate.py"), sbPath], { stdio: "inherit" });
  say(`narrate: ${secs(t)}s`);
}
const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", storyboard.id, "timing.json"), "utf8"));

// 2. stage assets
const pub = path.join(ROOT, ".cache", "public");
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand", "media", "audio"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
fs.copyFileSync(path.resolve(ROOT, brand.logo), path.join(pub, "brand", "logo.png"));
fs.cpSync(path.join(ROOT, ".cache", storyboard.id, "audio"), path.join(pub, "audio", storyboard.id), { recursive: true });

const probe = (f) => {
  const out = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", f], { encoding: "utf8" });
  const [w, h] = out.trim().split(",").map(Number);
  return { w, h };
};
storyboard.scenes.forEach((sc, i) => {
  if (!sc.src) return;
  const src = path.resolve(ROOT, sc.src);
  if (!fs.existsSync(src)) throw new Error(`scene ${i}: missing media ${sc.src}`);
  const name = `${i}-${path.basename(src)}`;
  fs.copyFileSync(src, path.join(pub, "media", name));
  const { w, h } = probe(src);
  sc.media = { path: `media/${name}`, w, h, kind: /\.(mp4|mov|webm|m4v)$/i.test(src) ? "video" : "image" };
  if (sc.zoom && sc.zoom.to > 1.6 && sc.media.w < 1400) warn(`scene ${i}: zoom ${sc.zoom.to} on a ${sc.media.w}px source will look soft; use a larger capture`);
  if (sc.narration && !timing.scenes[i]?.duration) warn(`scene ${i}: narration has no timing`);
});
say(`stage assets: ${secs(t)}s`);

// 3. bundle
t = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
say(`bundle: ${secs(t)}s`);

const tl = buildTimeline(storyboard, timing, brand.fps);
const total = totalFrames(tl);
say(`timeline: ${tl.map((r) => `${(r.frames / brand.fps).toFixed(1)}s`).join(" + ")} = ${(total / brand.fps).toFixed(1)}s`);
if (total / brand.fps > 45) warn(`total ${(total / brand.fps).toFixed(1)}s exceeds the 45 s ceiling`);

const results = [];
for (const format of formats) {
  t = Date.now();
  const inputProps = { format, storyboard, timing };
  const comp = await selectComposition({ serveUrl, id: "Promo", inputProps });
  const file = path.join(outDir, `${storyboard.id}-${format}.mp4`);
  let lastPct = -1;
  await renderMedia({
    composition: comp,
    serveUrl,
    codec: "h264",
    crf: 20,
    outputLocation: file,
    inputProps,
    onProgress: ({ progress }) => {
      const pct = Math.floor(progress * 10) * 10;
      if (pct !== lastPct) {
        lastPct = pct;
        process.stdout.write(`\r${format} ${pct}%`);
      }
    },
  });
  process.stdout.write("\n");
  const dur = (comp.durationInFrames / comp.fps).toFixed(1);
  say(`render ${format} (${comp.width}x${comp.height}, ${dur}s): ${secs(t)}s, ${mb(file)} MB -> ${path.relative(ROOT, file)}`);
  results.push({ format, file });
  if (flag("frames")) {
    const fdir = path.join(ROOT, ".cache", "frames", `${storyboard.id}-${format}`);
    fs.mkdirSync(fdir, { recursive: true });
    tl.forEach((r, i) => {
      const at = (r.frames / brand.fps) * 0.85;
      ff(["-ss", (r.start / brand.fps + at).toFixed(2), "-i", file, "-frames:v", "1", path.join(fdir, `scene${i}.png`)]);
    });
    say(`frames: ${path.relative(ROOT, fdir)}`);
  }
}

// poster + hero loop (16:9 only)
if (!flag("no-hero")) {
  t = Date.now();
  const heroCfg = storyboard.hero || { scene: 1, seconds: 6 };
  const row = tl[heroCfg.scene];
  const inputProps = { format: "16x9", storyboard, timing };
  const comp = await selectComposition({ serveUrl, id: "Promo", inputProps });
  const poster = path.join(outDir, `${storyboard.id}-poster.png`);
  await renderStill({ composition: comp, serveUrl, output: poster, inputProps, frame: row.start + Math.round(row.frames * 0.8) });
  say(`poster: ${mb(poster)} MB -> ${path.relative(ROOT, poster)}`);

  const heroProps = { storyboard };
  const heroComp = await selectComposition({ serveUrl, id: "Hero", inputProps: heroProps });
  const master = path.join(ROOT, ".cache", `${storyboard.id}-hero-master.mp4`);
  await renderMedia({ composition: heroComp, serveUrl, codec: "h264", crf: 16, muted: true, scale: 2 / 3, outputLocation: master, inputProps: heroProps });
  const LIMIT = 1.5e6;
  const enc = (ext, mk) => {
    const out = path.join(outDir, `${storyboard.id}-hero.${ext}`);
    for (let crf = mk.start; crf <= mk.max; crf += 2) {
      ff(["-i", master, "-an", ...mk.args(crf), out]);
      if (fs.statSync(out).size < LIMIT) return { out, crf };
    }
    warn(`hero.${ext} still over 1.5 MB at crf ${mk.max}`);
    return { out, crf: mk.max };
  };
  const mp4 = enc("mp4", { start: 24, max: 40, args: (c) => ["-c:v", "libx264", "-crf", String(c), "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart"] });
  const webm = enc("webm", { start: 32, max: 46, args: (c) => ["-c:v", "libvpx-vp9", "-crf", String(c), "-b:v", "0", "-row-mt", "1", "-pix_fmt", "yuv420p"] });
  say(`hero loop (${heroCfg.seconds}s, 1280x720, silent): ${secs(t)}s, mp4 ${mb(mp4.out)} MB (crf ${mp4.crf}), webm ${mb(webm.out)} MB (crf ${webm.crf})`);
}

say(`total: ${secs(t0)}s, warnings: ${warnings.length}`);
fs.writeFileSync(path.join(outDir, "run-log.txt"), log.join("\n") + "\n");
