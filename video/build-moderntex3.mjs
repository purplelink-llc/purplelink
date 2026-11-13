#!/usr/bin/env node
// ModernTex 3.0 launch video: storyboard + screen captures -> 16:9 demo or 9:16 Short.
//
//   node build-moderntex3.mjs moderntex-3-demo  [--stills 5,20] [--skip-narrate] [--no-bed] [--check]
//   node build-moderntex3.mjs moderntex-3-short [...]
//
// Captures: MT3_CLIPS (default /Volumes/Extreme SSD/PurplelinkVideos/moderntex-3/clips) holds <clip>.mp4 files named in
// the storyboard (c01-zen-open.mp4 ...). Missing clips render as labelled placeholder cards, so --check and --stills work
// before any capture exists. A real render refuses to run with placeholders unless --allow-placeholders is passed.
// Output: out/moderntex3/<id>.mp4 (private, nothing is uploaded here). Heavy: run under ~/.purplelink/nightq/heavy.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { buildPlan, planTotal, overruns } from "./src/moderntex3/plan.js";
import { stageNarration, stageBrandAudio, addTrendBed } from "./audio.mjs";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PY = fs.existsSync("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3") ? "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" : "python3";
const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const ID = args.find((a) => !a.startsWith("--") && !/^[\d,]+$/.test(a));
if (!ID) { console.error("usage: node build-moderntex3.mjs <moderntex-3-demo|moderntex-3-short> [--stills t,t] [--check]"); process.exit(2); }
const SBF = path.join(ROOT, "storyboards", `${ID}.json`);
const sb = JSON.parse(fs.readFileSync(SBF, "utf8"));
const format = sb.format;
const CLIPS = process.env.MT3_CLIPS || "/Volumes/Extreme SSD/PurplelinkVideos/moderntex-3/clips";
const OUT = path.join(ROOT, "out", "moderntex3");
fs.mkdirSync(OUT, { recursive: true });

const clipNames = [...new Set(sb.scenes.filter((s) => s.clip).map((s) => s.clip))];
const have = clipNames.filter((c) => fs.existsSync(path.join(CLIPS, `${c}.mp4`)));
const missing = clipNames.filter((c) => !have.includes(c));
console.log(`${ID}: ${sb.scenes.length} scenes, clips ${have.length}/${clipNames.length}${missing.length ? ` (placeholders: ${missing.join(", ")})` : ""}`);

if (!flag("skip-narrate") && !flag("check")) execFileSync(PY, [path.join(ROOT, "narrate.py"), SBF], { stdio: "inherit" });
const tpath = path.join(ROOT, ".cache", sb.id, "timing.json");
const timing = fs.existsSync(tpath) ? JSON.parse(fs.readFileSync(tpath, "utf8")) : null;
let plan = buildPlan(sb, timing);
const bad = overruns(plan);
if (bad.length) { console.error(`narration overruns:\n  ${bad.join("\n  ")}`); process.exit(1); }
console.log(`cut ${plan.total.toFixed(1)} s, with bumpers ${planTotal(plan).toFixed(1)} s`);
if (flag("check")) process.exit(0);
if (missing.length && !flag("allow-placeholders") && !flag("stills")) { console.error("clips missing: capture them first, or pass --allow-placeholders"); process.exit(1); }

const pub = path.join(ROOT, ".cache", `public-${ID}`);
fs.rmSync(path.join(ROOT, ".cache", `public-${ID}`), { recursive: true, force: true });
for (const d of ["fonts", "brand", "audio", "clips"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
stageBrandAudio(path.join(ROOT, "assets"), path.join(pub, "brand"));
for (const c of have) fs.copyFileSync(path.join(CLIPS, `${c}.mp4`), path.join(pub, "clips", `${c}.mp4`));
if (timing) {
  const dst = path.join(pub, "audio", sb.id);
  stageNarration(path.join(ROOT, ".cache", sb.id, "audio"), dst);
  plan = { ...plan, scenes: plan.scenes.map((s) => ({ ...s, audio: s.audio ? `audio/${sb.id}/${path.basename(s.audio)}` : null })) };
}

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "moderntex3", "index.jsx"), publicDir: pub });
const inputProps = { plan, format, clips: have };
const comp = await selectComposition({ serveUrl, id: "ModernTex3", inputProps });

if (flag("stills")) {
  for (const t of opt("stills").split(",")) {
    const out = path.join(OUT, `${ID}-still-${t}s.png`);
    await renderStill({ composition: comp, serveUrl, output: out, inputProps, frame: Math.round(Number(t) * comp.fps) });
    console.log(out);
  }
  process.exit(0);
}

const raw = path.join(OUT, `${ID}.raw.mp4`);
const final = path.join(OUT, `${ID}.mp4`);
await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, outputLocation: raw, inputProps, audioCodec: "aac", concurrency: 3, timeoutInMilliseconds: 180000 });
fs.copyFileSync(raw, final);
if (!flag("no-bed")) console.log("bed:", addTrendBed(final, "moderntex-3"));
console.log(`done ${final}`);
