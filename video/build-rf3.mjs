#!/usr/bin/env node
// RubbleFront trailer v3 builder (v1 and v2 builders are untouched). --wishlist renders the end card with a "Wishlist on Steam" line (storyboard end.wishlist text).
//   node build-rf2.mjs storyboards/rubblefront-v2.json [--format 16x9|9x16] [--stills 3,10] [--no-audio] [--poster-only]
// Reads  $RF_RUBBLEFRONT/build/trailer/v2/clips/<clip>.mp4 (+ .wav), falls back to build/trailer/clips/
// Writes $RF_RUBBLEFRONT/build/trailer/v2/<outputs[format]>. Nothing is uploaded.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { buildPlan } from "./src/rubblefront3/plan3.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const FL = process.env.RF_RUBBLEFRONT || process.env.RF_FRONTLINK || "/Volumes/Extreme SSD/RubbleFront";
const OUT = path.join(FL, "build", "trailer", "v3");
const CLIPS = [path.join(OUT, "clips"), path.join(FL, "build", "trailer", "v2", "clips")];
const ART = path.join(FL, "art", "store", "rubblefront");
const MUSIC = path.join(FL, "game", "audio", "music");
const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const sbArg = args.find((a) => a.endsWith(".json"));
const sb = JSON.parse(fs.readFileSync(path.resolve(ROOT, sbArg), "utf8"));
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand-rubblefront.json"), "utf8"));
const formats = opt("format") ? [opt("format")] : sb.formats || ["16x9"];
const say = (m) => console.log(m);
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const find = (name, ext) => CLIPS.map((d) => path.join(d, `${name}.${ext}`)).find((f) => fs.existsSync(f));
fs.mkdirSync(OUT, { recursive: true });

// stage assets
const pub = path.join(ROOT, ".cache", `public-${sb.id}`);
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand", "media"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
fs.copyFileSync(path.join(ART, "library-logo.png"), path.join(pub, "brand", "logo.png"));
fs.copyFileSync(path.join(ART, "library-hero-3840x1240.png"), path.join(pub, "media", "herobg.png"));
const used = new Set();
for (const sc of sb.scenes) {
  if (!sc.clip || used.has(sc.clip)) continue;
  const src = find(sc.clip, "mp4");
  if (!src) throw new Error(`missing clip ${sc.clip}`);
  fs.copyFileSync(src, path.join(pub, "media", `${sc.clip}.mp4`));
  used.add(sc.clip);
}

function makeAudio(plan, wavOut) {
  const spec = {
    dur: plan.total,
    music: (sb.music || []).map((m) => ({ ...m, file: path.join(MUSIC, m.file) })),
    music_env: sb.musicEnv || [],
    game: [],
    synth: [...(sb.synth || []), ...plan.sfx.filter((s) => !(sb.noAutoSfx))],
    synth_db: sb.synthDb ?? -3,
    peak_db: -1.5,
  };
  for (const g of plan.gameAudio) {
    const wav = find(g.clip, "wav");
    if (wav) spec.game.push({ file: wav, in: g.in, dur: g.dur, t: g.t, gain_db: g.gain_db });
  }
  const specFile = path.join(ROOT, ".cache", sb.id, `mix-${plan.format}.json`);
  fs.mkdirSync(path.dirname(specFile), { recursive: true });
  fs.writeFileSync(specFile, JSON.stringify(spec, null, 1));
  say(execFileSync("python3", [path.join(ROOT, "mixrf2.py"), specFile, wavOut], { encoding: "utf8" }).trim());
}

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "rubblefront3", "index.jsx"), publicDir: pub });
const stills = opt("stills", "");
for (const format of formats) {
  const sbf = sb.verticalScenes && format === "9x16" ? { ...sb, scenes: sb.verticalScenes } : sb;
  const sbw = JSON.parse(JSON.stringify(sbf));
  if (flag("wishlist")) sbw.scenes.forEach((s) => { if (s.type === "end") s.wishlist = sb.wishlistText || "Wishlist on Steam"; });
  const plan = buildPlan(sbw, format);
  say(`${sb.id} ${format}: ${plan.total.toFixed(2)} s, ${plan.shots.length} scenes, ${plan.cards.length} cards`);
  const inputProps = { format, plan };
  const comp = await selectComposition({ serveUrl, id: "Trailer3", inputProps });
  if (stills) {
    const sd = path.join(ROOT, ".cache", "stills", sb.id);
    fs.mkdirSync(sd, { recursive: true });
    for (const s of stills.split(",")) await renderStill({ composition: comp, serveUrl, output: path.join(sd, `${format}-${s}.png`), inputProps, frame: Math.round(Number(s) * 30) });
    say(`stills -> ${sd}`);
    continue;
  }
  const outName0 = (sb.outputs || {})[format] || `${sb.id}-${format}.mp4`;
  const outName = flag("wishlist") ? outName0.replace(".mp4", "-wishlist.mp4") : outName0;
  const outFile = flag("draft") ? path.join(ROOT, ".cache", `draft-${sb.id}-${format}.mp4`) : path.join(OUT, outName);
  const raw = path.join(ROOT, ".cache", `${sb.id}-${format}-raw.mp4`);
  if (!flag("poster-only")) {
    await renderMedia({
      composition: comp, serveUrl, codec: "h264", crf: sb.crf ?? 16, pixelFormat: "yuv420p", muted: true, outputLocation: raw, inputProps, concurrency: flag("draft") ? 8 : 5, timeoutInMilliseconds: 180000, scale: flag("draft") ? 0.5 : 1,
      onProgress: ({ progress }) => { const p = Math.floor(progress * 10) * 10; if (p !== globalThis.__lp) { globalThis.__lp = p; process.stdout.write(`${format} ${p}% `); } },
    });
    process.stdout.write("\n");
    const wav = path.join(ROOT, ".cache", sb.id, `mix-${format}.wav`);
    makeAudio(plan, wav);
    // loudness: -14 LUFS integrated, true peak -1.5 dB (two passes)
    const norm = path.join(ROOT, ".cache", sb.id, `norm-${format}.wav`);
    const meas = execFileSync("ffmpeg", ["-hide_banner", "-nostats", "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).toString();
    ff(["-i", wav, "-af", "loudnorm=I=-14:TP=-2.2:LRA=11", "-ar", "48000", norm]);
    ff(["-i", raw, "-i", norm, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", outFile]);
    say(`wrote ${outFile}`);
  }
  if (sb.poster && format === "16x9" && !flag("draft") && !flag("wishlist")) {
    const out = path.join(OUT, sb.poster.file);
    await renderStill({ composition: comp, serveUrl, output: out, inputProps, frame: Math.round(sb.poster.at * 30) });
    say(`wrote ${out}`);
  }
}
