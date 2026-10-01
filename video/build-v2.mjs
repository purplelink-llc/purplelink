// node build-v2.mjs [--format 16x9|9x16|both] [--stills t1,t2,...] [--no-hero]
// Prereqs: python3 narrate.py storyboards/moderntex-promo-v2.json ; node build-edit.mjs
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { buildPlan } from "./src/v2plan.js";
import { buildLong } from "./src/v2long.js";
import { stageNarration, stageBrandAudio } from "./audio.mjs";
import { bumperTotal, BUMPER } from "./src/bumper.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const LONG = args.includes("--long");
const ID = LONG ? "moderntex-promo-v2-long" : "moderntex-promo-v2";
const V3 = args.includes("--v3"); // brand bumpers + normalised narration, written beside v2 as <id>-v3
const OUTID = V3 ? `${ID}-v3` : ID;
const OUT = path.join(ROOT, "out", OUTID);
fs.mkdirSync(OUT, { recursive: true });
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", ID, "timing.json"), "utf8"));
const plan = LONG ? buildLong(timing) : buildPlan(timing);
const storyboard = JSON.parse(fs.readFileSync(path.join(ROOT, "storyboards", `${ID}.json`), "utf8"));
const bumper = V3 ? { ...BUMPER, ...(storyboard.bumper || {}) } : null;
const TOTAL = V3 ? bumperTotal(plan.total, bumper) : plan.total;
const pub = path.join(ROOT, ".cache", "public-v2");
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand", "media", "audio"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
fs.copyFileSync(path.resolve(ROOT, "../site/assets/moderntex-icon.png"), path.join(pub, "brand/moderntex-icon.png"));
for (const f of LONG ? ["long-edit.mp4"] : ["edit.mp4", "hero-edit.mp4"]) fs.copyFileSync(path.join(ROOT, ".cache/v2", f), path.join(pub, "media", f));
if (V3) {
  stageBrandAudio(path.join(ROOT, "assets"), path.join(pub, "brand"));
  console.log("narration -16 LUFS:", stageNarration(path.join(ROOT, ".cache", ID, "audio"), path.join(pub, "audio", ID)).join(", "));
} else fs.cpSync(path.join(ROOT, ".cache", ID, "audio"), path.join(pub, "audio", ID), { recursive: true });
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(2);
const fmts = args.includes("--hero-only") ? [] : opt("format", "both") === "both" ? ["16x9", "9x16"] : [opt("format")];
const stills = opt("stills", "");
console.log("total", TOTAL.toFixed(2), V3 ? "(with bumpers)" : "");

for (const format of fmts) {
  const inputProps = { format, timing, total: plan.total, bumper };
  const comp = await selectComposition({ serveUrl, id: LONG ? "PromoLong" : "PromoV2", inputProps });
  if (stills) {
    fs.mkdirSync(path.join(ROOT, ".cache/stills"), { recursive: true });
    for (const s of stills.split(",")) {
      const out = path.join(ROOT, ".cache/stills", `${format}-${s}.png`);
      await renderStill({ composition: comp, serveUrl, output: out, inputProps, frame: Math.round(Number(s) * 30) });
    }
    continue;
  }
  const raw = path.join(ROOT, ".cache", `${OUTID}-${format}-raw.mp4`);
  await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, outputLocation: raw, inputProps, audioCodec: "aac", concurrency: 6 });
  const file = path.join(OUT, `${OUTID}-${format}.mp4`);
  ff(["-i", raw, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", file]);
  console.log(format, comp.durationInFrames / 30, "s", mb(file), "MB");
  if (V3) {
    const fdir = path.join(OUT, "frames");
    fs.mkdirSync(fdir, { recursive: true });
    for (const m of [1.2, 2.05, 2.7, TOTAL / 2, TOTAL - 1.6, TOTAL - 0.3]) ff(["-ss", m.toFixed(2), "-i", file, "-frames:v", "1", "-q:v", "3", path.join(fdir, `${format}-${m.toFixed(1).padStart(5, "0")}.jpg`)]);
  }
  if (format === "16x9" && !LONG && !V3) {
    const poster = path.join(OUT, `${ID}-poster.jpg`);
    await renderStill({ composition: comp, serveUrl, output: poster, imageFormat: "jpeg", jpegQuality: 92, inputProps, frame: Math.round((plan.B4s + 2.6) * 30) });
    console.log("poster", mb(poster));
  }
}

if (!stills && !LONG && !V3 && !args.includes("--no-hero")) {
  const heroComp = await selectComposition({ serveUrl, id: "HeroV2", inputProps: { timing } });
  const h = plan.hero;
  const c = { ...heroComp, durationInFrames: Math.round(h.T * 30) };
  const master = path.join(ROOT, ".cache", `${ID}-hero-master.mp4`);
  await renderMedia({ composition: c, serveUrl, codec: "h264", crf: 14, muted: true, scale: 2 / 3, outputLocation: master, inputProps: { timing } });
  const LIM = 1.5e6;
  const enc = (ext, start, max, a) => {
    const out = path.join(OUT, `${ID}-hero.${ext}`);
    for (let crf = start; crf <= max; crf += 2) { ff(["-i", master, "-an", ...a(crf), out]); if (fs.statSync(out).size < LIM) return `${ext} crf ${crf} ${mb(out)} MB`; }
    return `${ext} over limit`;
  };
  console.log(enc("mp4", 22, 40, (q) => ["-c:v", "libx264", "-crf", String(q), "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]));
  console.log(enc("webm", 30, 46, (q) => ["-c:v", "libvpx-vp9", "-crf", String(q), "-b:v", "0", "-row-mt", "1", "-pix_fmt", "yuv420p"]));
}
