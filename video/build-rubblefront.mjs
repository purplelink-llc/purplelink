#!/usr/bin/env node
// RubbleFront trailer builder. Reads a storyboard (storyboards/rubblefront-*.json), turns real gameplay clips captured with Godot's
// movie writer (see the RubbleFront repo, game/tools/trailer_runner.gd) into a finished video with Remotion.
//
//   node build-rubblefront.mjs storyboards/rubblefront-trailer.json [--format 16x9|9x16] [--skip-narrate] [--stills 3,10,40] [--no-poster]
//
// Reads  $RF_RUBBLEFRONT/build/trailer/clips/<clip>.mp4 (+ <clip>.wav, the game's own effects recorded with the clip)
// Writes $RF_RUBBLEFRONT/build/trailer/<outputs[format]> (never into this repository).
// Narration: narrate.py (edge-tts), normalised to -16 LUFS by audio.mjs, then mixed with the game's music by mixrf.py.
// Nothing is uploaded or posted.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { stageNarration } from "./audio.mjs";
import { buildPlan, toSrt } from "./src/rubblefront/plan.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const FL = process.env.RF_RUBBLEFRONT || process.env.RF_FRONTLINK || "/Volumes/Extreme SSD/RubbleFront";
const OUT = path.join(FL, "build", "trailer");
const CLIPS = path.join(OUT, "clips");
const ART = path.join(FL, "art", "store", "rubblefront");
const MUSIC = path.join(FL, "game", "audio", "music");
const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const sbArg = args.find((a) => a.endsWith(".json"));
if (!sbArg) { console.error("usage: node build-rubblefront.mjs storyboards/<id>.json [--format 16x9|9x16]"); process.exit(1); }
const sbPath = path.resolve(ROOT, sbArg);
const sb = JSON.parse(fs.readFileSync(sbPath, "utf8"));
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand-rubblefront.json"), "utf8"));
const formats = opt("format") ? [opt("format")] : sb.formats || ["16x9"];
const say = (m) => console.log(m);
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(2);
fs.mkdirSync(OUT, { recursive: true });

// 1. narration
const hasVoice = sb.scenes.some((s) => s.narration);
// edge-tts fails now and then ("No audio was received") and sometimes returns a clip cut short. narrate.py caches finished scenes, so a retry
// only redoes the missing ones; a clip shorter than 0.25 s per word is thrown away and made again.
const timingFile = path.join(ROOT, ".cache", sb.id, "timing.json");
function badScenes() {
  if (!fs.existsSync(timingFile)) return [];
  const t = JSON.parse(fs.readFileSync(timingFile, "utf8"));
  const bad = [];
  t.scenes.forEach((tm, i) => { if (sb.scenes[i]?.narration && tm.words && tm.duration < 0.25 * tm.words.length) bad.push(i); });
  if (bad.length) { bad.forEach((i) => { t.scenes[i].hash = ""; }); fs.writeFileSync(timingFile, JSON.stringify(t, null, 1)); }
  return bad;
}
if (hasVoice && !flag("skip-narrate")) {
  for (let attempt = 1; ; attempt++) {
    let ok = true;
    try { execFileSync("python3", [path.join(ROOT, "narrate.py"), sbPath], { stdio: "inherit" }); } catch (e) { ok = false; if (attempt >= 20) throw e; }
    const bad = ok ? badScenes() : [];
    if (ok && !bad.length) break;
    say(`narrate attempt ${attempt}: ${ok ? "short clips in scenes " + bad.join(",") : "service error"}, retrying`);
    execFileSync("sleep", ["3"]);
  }
}
const timing = hasVoice ? JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", sb.id, "timing.json"), "utf8")) : { scenes: [] };

// 2. stage assets
const pub = path.join(ROOT, ".cache", `public-${sb.id}`);
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand", "media"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
fs.copyFileSync(path.join(ART, "library-logo.png"), path.join(pub, "brand", "logo.png"));
fs.copyFileSync(path.join(ART, "page-background-1438x810.png"), path.join(pub, "media", "endbg.png"));
const used = new Set();
for (const sc of sb.scenes) {
  if (sc.clip) {
    const src = path.join(CLIPS, `${sc.clip}.mp4`);
    if (!fs.existsSync(src)) throw new Error(`missing clip ${src}`);
    if (!used.has(sc.clip)) fs.copyFileSync(src, path.join(pub, "media", `${sc.clip}.mp4`));
    used.add(sc.clip);
  } else if (sc.still) {
    const name = path.basename(sc.still).replace(/\.[^.]+$/, "");
    sc.stillName = name;
    fs.copyFileSync(path.resolve(sc.still.startsWith("/") ? sc.still : path.join(ROOT, sc.still)), path.join(pub, "media", `${name}.png`));
  }
}
// plan reads `clip` or `still` as the media name
const planSb = { ...sb, scenes: sb.scenes.map((s) => (s.still ? { ...s, still: s.stillName } : s)) };

// 3. audio
function makeAudio(plan, wavOut) {
  const normDir = path.join(ROOT, ".cache", sb.id, "norm");
  fs.rmSync(normDir, { recursive: true, force: true });
  if (hasVoice) stageNarration(path.join(ROOT, ".cache", sb.id, "audio"), normDir).forEach((n) => say(`  narration ${n}`));
  const spec = {
    dur: plan.total,
    narration: plan.narration.map((n) => ({ file: path.join(normDir, path.basename(n.file)), t: n.t, gain_db: 0 })),
    sfx: [],
    music: sb.music ? { ...sb.music, file: path.join(MUSIC, sb.music.file) } : null,
    sfx_duck_db: sb.sfxDuckDb ?? -3,
    peak_db: -2.0,
  };
  for (const s of plan.shots) {
    if (s.kind !== "clip") continue;
    const wav = path.join(CLIPS, `${s.name}.wav`);
    if (!fs.existsSync(wav) || sb.sfx === false || planSb.scenes[s.i].sfx === false) continue;
    spec.sfx.push({ file: wav, in: s.in, dur: s.dur, t: s.start, gain_db: (planSb.scenes[s.i].sfxDb ?? sb.sfxDb ?? -4) });
  }
  const specFile = path.join(ROOT, ".cache", sb.id, `mix-${plan.format}.json`);
  fs.writeFileSync(specFile, JSON.stringify(spec, null, 1));
  say(execFileSync("python3", [path.join(ROOT, "mixrf.py"), specFile, wavOut], { encoding: "utf8" }).trim());
}

// 4. render
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "rubblefront", "index.jsx"), publicDir: pub });
const stills = opt("stills", "");
for (const format of formats) {
  const plan = buildPlan(planSb, timing, format);
  plan.warnings.forEach((w) => say(`WARNING: ${w}`));
  if (sb.noCaptions) plan.captions = [];
  if (format === "9x16" && sb.vertical?.showLogo === false) plan.showLogo = false;
  say(`${sb.id} ${format}: ${plan.total.toFixed(2)} s, ${plan.shots.length} shots, ${plan.narration.length} narration lines`);
  const inputProps = { format, plan };
  const comp = await selectComposition({ serveUrl, id: "Trailer", inputProps });
  if (stills) {
    const sd = path.join(ROOT, ".cache", "stills", sb.id);
    fs.mkdirSync(sd, { recursive: true });
    for (const s of stills.split(",")) await renderStill({ composition: comp, serveUrl, output: path.join(sd, `${format}-${s}.png`), inputProps, frame: Math.round(Number(s) * 30) });
    say(`stills -> ${sd}`);
    continue;
  }
  const raw = path.join(ROOT, ".cache", `${sb.id}-${format}-raw.mp4`);
  await renderMedia({
    composition: comp, serveUrl, codec: "h264", crf: sb.crf ?? 17, pixelFormat: "yuv420p", muted: true, outputLocation: raw, inputProps,
    onProgress: ({ progress }) => { const p = Math.floor(progress * 10) * 10; if (p !== globalThis.__lp) { globalThis.__lp = p; process.stdout.write(`${format} ${p}% `); } },
  });
  process.stdout.write("\n");
  const outName = (sb.outputs || {})[format] || `${sb.id}-${format}.mp4`;
  const outFile = path.join(OUT, outName);
  if (sb.silent) {
    ff(["-i", raw, "-c:v", "copy", "-an", "-movflags", "+faststart", outFile]);
  } else {
    const wav = path.join(ROOT, ".cache", sb.id, `mix-${format}.wav`);
    makeAudio(plan, wav);
    ff(["-i", raw, "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", outFile]);
  }
  say(`wrote ${outFile} (${mb(outFile)} MB)`);
  if (sb.srt && format === formats[0]) {
    const srtPlan = buildPlan(planSb, timing, "16x9");
    fs.writeFileSync(path.join(OUT, sb.srt), toSrt(srtPlan.captions));
    say(`wrote ${sb.srt}`);
  }
  if (sb.poster && format === "16x9" && !flag("no-poster")) {
    const out = path.join(OUT, sb.poster.file);
    await renderStill({ composition: comp, serveUrl, output: out, inputProps, frame: Math.round(((plan.end?.start ?? 0) + sb.poster.at) * 30) });
    say(`wrote ${out}`);
  }
}
