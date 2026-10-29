#!/usr/bin/env node
// Circled Hoops Reddit ads: storyboard + narration + captures -> 9:16, 4:5 and 1:1 MP4s with burned-in captions.
//
//   node build-circledhoops.mjs storyboards/circledhoops-a.json [--format 9x16|4x5|1x1] [--stills 1,4,9] [--no-video]
//
// Inputs (env, with defaults):
//   CH_CAPTURES  headless captures of the app's sample league (clip-*.mp4 at 1170x2532, still-*.png)
//   CH_VO        Kokoro narration: <id>.mp3 + <id>.words.json per line (shared_media/kokoro_local.py)
//   CH_LOCKIN    a lockin checkout, for the brand sounds (packages/brand/sounds) and the app icon
//   CH_OUT       where the finished cuts go
// Renders are heavy: run this under ~/.purplelink/nightq/heavy. Nothing is uploaded anywhere.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { FPS } from "./src/circledhoops/layout.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const env = (k, d) => process.env[k] || d;
const CAP = env("CH_CAPTURES", "");
const VO = env("CH_VO", "");
const LOCKIN = env("CH_LOCKIN", "");
const OUT = env("CH_OUT", "/Volumes/Extreme SSD/PurplelinkVideos/circledhoops-reddit-ads");
const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const sb = JSON.parse(fs.readFileSync(path.resolve(ROOT, args.find((a) => a.endsWith(".json"))), "utf8"));
const formats = opt("format") ? [opt("format")] : ["9x16", "4x5", "1x1"];
for (const [k, v] of Object.entries({ CH_CAPTURES: CAP, CH_VO: VO, CH_LOCKIN: LOCKIN })) if (!v || !fs.existsSync(v)) throw new Error(`${k} not set or missing`);
const SOUNDS = path.join(LOCKIN, "packages", "brand", "sounds");

// ---- plan: scene lengths come from the narration ----
function words(id) {
  return JSON.parse(fs.readFileSync(path.join(VO, `${id}.words.json`), "utf8"));
}
function buildPlan() {
  let t = 0;
  const shots = [], caps = [], vo = [], sfx = [], flashes = [];
  for (const sc of sb.scenes) {
    const lead = sc.lead ?? 0.08;
    let dur = sc.min || 1;
    if (sc.vo) {
      const w = words(sc.vo);
      const first = w[0].start, last = w[w.length - 1].end;
      dur = Math.max(dur, lead + (last - first) + (sc.tail ?? 0.3));
      const off = t + lead - first; // place the mp3 so the first word lands at t + lead
      vo.push({ file: path.join(VO, `${sc.vo}.mp3`), t: off });
      if (sc.cap !== false) {
        caps.push({ t0: t, t1: t + dur, center: sc.cap === "center", hl: sc.hl || [], circle: sc.circle || [], words: w.map((x) => ({ w: x.word, s: x.start + off, e: x.end + off })) });
      }
    }
    for (const s of sc.shots || []) {
      const t0 = t + (s.at || 0);
      const t1 = s.dur ? t0 + s.dur : t + dur + (s.extend || 0);
      shots.push({ ...s, t0, t1 });
    }
    for (const s of sc.sfx || []) sfx.push({ file: path.join(SOUNDS, `${s.name}.wav`), t: t + s.at, gain_db: s.gain_db ?? -3 });
    if (sc.flash) flashes.push(t);
    sc._t = t;
    t += dur;
  }
  const drop = sb.bed.dropScene != null ? sb.scenes[sb.bed.dropScene]._t : 0;
  return { total: t, shots, caps, flashes, note: sb.note || "", vo, sfx, drop };
}

const plan = buildPlan();
console.log(`${sb.id}: ${plan.total.toFixed(2)} s, ${plan.shots.length} shots, ${plan.caps.length} caption lines`);
for (const c of plan.caps) console.log(`  ${c.t0.toFixed(2)}-${c.t1.toFixed(2)}  ${c.words.map((w) => w.w).join(" ")}`);

// ---- stage public files ----
const pub = path.join(ROOT, ".cache", `public-${sb.id}`);
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand", "media"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
const fontDir = path.join(ROOT, "assets", "fonts-circledhoops");
for (const f of fs.readdirSync(fontDir).filter((f) => f.endsWith(".ttf"))) fs.copyFileSync(path.join(fontDir, f), path.join(pub, "fonts", f));
fs.copyFileSync(path.join(LOCKIN, "packages", "brand", "logo", "circled-hoops-icon-1024.png"), path.join(pub, "brand", "icon.png"));
// Purplelink signs its products with the wordmark alone (light ink, for the dark ground): docs/brand/logo-usage.md.
fs.copyFileSync(path.join(ROOT, "..", "site", "assets", "purplelink-wordmark-dark.png"), path.join(pub, "brand", "wordmark.png"));
for (const s of plan.shots) if (s.src) fs.copyFileSync(path.join(CAP, s.src), path.join(pub, "media", s.src));

fs.mkdirSync(OUT, { recursive: true });
const work = path.join(ROOT, ".cache", sb.id);
fs.mkdirSync(work, { recursive: true });

// ---- audio, once for all formats ----
const wav = path.join(work, "mix.wav");
if (!flag("no-video")) {
  const spec = { dur: plan.total, vo: plan.vo, sfx: plan.sfx, bed: { ...sb.bed, drop: plan.drop, out_at: plan.total - 1.4 } };
  fs.writeFileSync(path.join(work, "mix.json"), JSON.stringify(spec, null, 1));
  console.log(execFileSync("python3", [path.join(ROOT, "mix-circledhoops.py"), path.join(work, "mix.json"), wav], { encoding: "utf8" }).trim());
}

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "circledhoops", "index.jsx"), publicDir: pub });
const rplan = { total: plan.total, shots: plan.shots, caps: plan.caps, flashes: plan.flashes, note: plan.note };
const stills = opt("stills", "");
for (const format of formats) {
  const inputProps = { format, plan: rplan };
  const comp = await selectComposition({ serveUrl, id: "CircledHoopsAd", inputProps });
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
  await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: Number(env("CH_CRF", "12")), outputLocation: silent, inputProps, muted: true, pixelFormat: "yuv420p", colorSpace: "bt709", concurrency: Number(env("CH_CONCURRENCY", "4")) });
  const out = path.join(OUT, `${sb.id}-${format}.mp4`);
  // AAC can overshoot sharp UI-sound transients by 2 dB or more: measure the encoded file and pull it under -1 dBTP.
  let gain = 0, tp = 0;
  for (let pass = 0; pass < 3; pass++) {
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", `volume=${gain}dB`, "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out]);
    const m = [...execFileSync("sh", ["-c", `ffmpeg -hide_banner -i "${out}" -map 0:a -af ebur128=peak=true -f null - 2>&1 | grep -A1 'True peak' | tail -1`], { encoding: "utf8" }).matchAll(/(-?[\d.]+) dBFS/g)];
    tp = m.length ? Number(m[0][1]) : 0;
    if (tp <= -1.0) break;
    gain -= tp + 1.2;
  }
  console.log(`wrote ${out} (true peak ${tp} dBTP, gain ${gain.toFixed(2)} dB)`);
}
