#!/usr/bin/env node
// ModernTex Reddit video ads: storyboard + real app captures -> 1:1 (1200x1200) and 4:5 (1200x1500) MP4s, 30 fps,
// burned-in headline captions, a synthesised bed and key clicks. No voice-over: the ad reads with the sound off.
//
//   node build-moderntex-ad.mjs storyboards/moderntex-reddit-30.json [--format 1x1|4x5] [--stills 1,4,9] [--no-video]
//
// Inputs (env, with defaults):
//   MT_CAPTURES  background captures of ModernTex on a synthetic sample project: <scene>/NNNN.jpg + frames.json
//                (seconds since the scene's capture began) per scene, and icon.png (the app icon, 1024 px)
//   MT_OUT       where the finished cuts go
// Renders are heavy: run this under ~/.purplelink/nightq/heavy. Nothing is uploaded anywhere.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { FPS } from "./src/moderntexad/layout.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const env = (k, d) => process.env[k] || d;
const CAP = env("MT_CAPTURES", "/Volumes/Extreme SSD/PurplelinkVideos/moderntex-reddit-ads/captures");
const OUT = env("MT_OUT", "/Volumes/Extreme SSD/PurplelinkVideos/moderntex-reddit-ads");
const KEYS = path.join(ROOT, "assets", "keyfeel", "samples", "tactile");
const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const sb = JSON.parse(fs.readFileSync(path.resolve(ROOT, args.find((a) => a.endsWith(".json"))), "utf8"));
const formats = opt("format") ? [opt("format")] : ["1x1", "4x5"];
if (!fs.existsSync(path.join(CAP, "icon.png"))) throw new Error(`MT_CAPTURES (${CAP}) has no icon.png`);

const frames = (seq) => JSON.parse(fs.readFileSync(path.join(CAP, seq, "frames.json"), "utf8"))
  .map((x) => ({ ...x, src: `media/${seq}/${x.f.replace(/\.png$/, ".jpg")}` }));

// ---- plan: scene times from the storyboard durations; clicks from the capture's own typing frames ----
function buildPlan() {
  let t = 0;
  const scenes = [], sfx = [];
  let key = 0;
  for (const sc of sb.scenes) {
    const s = { ...sc, t0: t, t1: t + sc.dur };
    if (sc.kind === "seq") {
      s.frames = frames(sc.seq);
      const from = sc.from || 0, rate = sc.rate || 1;
      if (sc.clicks) {
        let n = 0;
        for (const fr of s.frames) {
          if (fr.note !== "type") continue;
          const at = (fr.t - from) / rate;
          if (at < 0 || at > sc.dur) continue;
          if (n++ % sc.clicks) continue;
          sfx.push({ file: path.join(KEYS, `press-${String((key++ % 15) + 1).padStart(2, "0")}.wav`), t: t + at, gain_db: -15 });
        }
      }
      if (sc.press != null) sfx.push({ file: path.join(KEYS, "enter-press-01.wav"), t: t + sc.press, gain_db: -9 });
    }
    scenes.push(s);
    t += sc.dur;
  }
  const drop = sb.bed.dropScene != null ? scenes[sb.bed.dropScene].t0 : 0;
  return { total: t, scenes, sfx, drop };
}

const plan = buildPlan();
console.log(`${sb.id}: ${plan.total.toFixed(2)} s, ${plan.scenes.length} scenes, ${plan.sfx.length} sounds`);
for (const s of plan.scenes) console.log(`  ${s.t0.toFixed(2)}-${s.t1.toFixed(2)}  ${s.kind === "end" ? "end card" : s.seq}  ${s.cap ? s.cap.lines.join(" / ") : ""}`);
if (plan.total > 30.01) throw new Error("longer than Reddit's recommended 5-30 s");

// ---- stage public files: fonts, the lockup and icon, and only the frames the plan uses ----
const pub = path.join(ROOT, ".cache", `public-${sb.id}`);
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of ["fraunces-latin.woff2", "plus-jakarta-sans-latin.woff2"]) fs.copyFileSync(path.join(ROOT, "..", "site", "assets", "fonts", f), path.join(pub, "fonts", f));
// Wordmark B with the mark, light ink for the dark ground (docs/brand/logo-usage.md).
fs.copyFileSync(path.join(ROOT, "..", "site", "assets", "purplelink-lockup-horizontal-dark.png"), path.join(pub, "brand", "lockup.png"));
fs.copyFileSync(path.join(CAP, "icon.png"), path.join(pub, "brand", "icon.png"));
for (const s of plan.scenes) for (const fr of s.frames || []) {
  const dst = path.join(pub, fr.src);
  if (fs.existsSync(dst)) continue;
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(path.join(CAP, fr.src.replace(/^media\//, "")), dst);
}

fs.mkdirSync(OUT, { recursive: true });
const work = path.join(ROOT, ".cache", sb.id);
fs.mkdirSync(work, { recursive: true });

// ---- audio, once for all formats (the Circled Hoops mixer: bed, ducking off with no voice, loudnorm, limiter) ----
const wav = path.join(work, "mix.wav");
if (!flag("no-video")) {
  const spec = { dur: plan.total, vo: [], sfx: plan.sfx, bed: { ...sb.bed, drop: plan.drop, out_at: plan.total - 1.4 } };
  fs.writeFileSync(path.join(work, "mix.json"), JSON.stringify(spec, null, 1));
  console.log(execFileSync("python3", [path.join(ROOT, "mix-circledhoops.py"), path.join(work, "mix.json"), wav], { encoding: "utf8" }).trim());
}

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "moderntexad", "index.jsx"), publicDir: pub });
const rplan = { total: plan.total, scenes: plan.scenes };
const stills = opt("stills", "");
for (const format of formats) {
  const inputProps = { format, plan: rplan };
  const comp = await selectComposition({ serveUrl, id: "ModernTexAd", inputProps });
  if (stills) {
    const sd = path.join(work, "stills");
    if (format === formats[0]) fs.rmSync(sd, { recursive: true, force: true });
    fs.mkdirSync(sd, { recursive: true });
    for (const s of stills.split(",").map(Number)) {
      const frame = Math.min(comp.durationInFrames - 1, Math.round(s * FPS));
      await renderStill({ composition: comp, serveUrl, inputProps, frame, output: path.join(sd, `${format}-${String(frame).padStart(5, "0")}.png`) });
    }
    console.log(`stills ${format} -> ${sd}`);
  }
  if (flag("no-video")) continue;
  const silent = path.join(work, `${format}-silent.mp4`);
  await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: Number(env("MT_CRF", "16")), outputLocation: silent, inputProps, muted: true, pixelFormat: "yuv420p", colorSpace: "bt709", concurrency: Number(env("MT_CONCURRENCY", "4")) });
  const out = path.join(OUT, `${sb.id}-${format}.mp4`);
  // AAC can overshoot sharp transients (the key clicks): measure the encoded file and pull it under -1 dBTP.
  let gain = 0, tp = 0;
  for (let pass = 0; pass < 3; pass++) {
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", `volume=${gain}dB`, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out]);
    const m = [...execFileSync("sh", ["-c", `ffmpeg -hide_banner -i "${out}" -map 0:a -af ebur128=peak=true -f null - 2>&1 | grep -A1 'True peak' | tail -1`], { encoding: "utf8" }).matchAll(/(-?[\d.]+) dBFS/g)];
    tp = m.length ? Number(m[0][1]) : 0;
    if (tp <= -1.0) break;
    gain -= tp + 1.2;
  }
  console.log(`wrote ${out} (${(fs.statSync(out).size / 1e6).toFixed(1)} MB, true peak ${tp} dBTP)`);
}
