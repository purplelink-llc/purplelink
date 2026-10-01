// node build-latexfix.mjs <slug> [--format 16x9|9x16|both] [--stills t1,t2,...] [--skip-narrate]
// "Fix this LaTeX error" shorts (src/LatexFix.jsx, content in src/latexfix/data.js, narration and captions in
// storyboards/latex-errors/<slug>.json). Renders one format after the other, never in parallel.
// Outputs video/out/latex-errors/<slug>/: <slug>-16x9.mp4, <slug>-9x16.mp4, <slug>-poster.jpg, frames/*.jpg, run-log.txt.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { ERRORS } from "./src/latexfix/data.js";
import { build } from "./src/latexfix/plan.js";
import { stageNarration, stageBrandAudio } from "./audio.mjs";
import { bumperTotal, BUMPER } from "./src/bumper.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PY = fs.existsSync("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3") ? "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" : "python3";
const args = process.argv.slice(2);
const ID = args[0];
if (!ERRORS[ID]) {
  console.error(`usage: node build-latexfix.mjs <${Object.keys(ERRORS).join("|")}> [--format ...] [--stills ...] [--skip-narrate]`);
  process.exit(1);
}
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes(`--${n}`);
const OUT = path.join(ROOT, "out", "latex-errors", ID);
fs.mkdirSync(OUT, { recursive: true });
const log = [];
const say = (m) => { console.log(m); log.push(m); };
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(2);
const t0 = Date.now();
const secs = (t) => ((Date.now() - t) / 1000).toFixed(1);
say(`# ${ID} render, ${new Date().toISOString()}`);

const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const sbPath = path.join(ROOT, "storyboards", "latex-errors", `${ID}.json`);
if (!flag("skip-narrate")) execFileSync(PY, [path.join(ROOT, "narrate.py"), sbPath], { stdio: "inherit" });
const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", ID, "timing.json"), "utf8"));
const storyboard = JSON.parse(fs.readFileSync(sbPath, "utf8"));
const b = { ...BUMPER, ...(storyboard.bumper || {}) };
const bumper = { open: b.open, close: b.close, xf: b.xf };
const plan = build(ID, timing, storyboard);
const P0 = bumper.open - bumper.xf;
const TOTAL = bumperTotal(plan.total, bumper);
const firstWord = P0 + plan.audio[0].at + timing.scenes[0].words[0].start;
const lastWord = P0 + plan.audio[4].at + timing.scenes[4].words.at(-1).end;
const closeAt = P0 + plan.total - bumper.xf;
say(`beats (cut-local): ${plan.audio.map((a) => `${a.i}@${a.at.toFixed(2)}`).join(" ")}  ENDs ${plan.ENDs.toFixed(2)}  cut ${plan.total.toFixed(2)}s  with bumpers ${TOTAL.toFixed(2)}s`);
say(`narration ${firstWord.toFixed(2)}s to ${lastWord.toFixed(2)}s; opening bumper ends ${bumper.open.toFixed(2)}s, closing bumper starts ${closeAt.toFixed(2)}s`);
if (firstWord < bumper.open || lastWord > closeAt) throw new Error("narration overlaps a bumper");
if (TOTAL < 20 || TOTAL > 25) say(`WARNING: total ${TOTAL.toFixed(2)}s is outside 20 to 25 s`);

const pub = path.join(ROOT, ".cache", `public-${ID}`);
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand", "audio"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
stageBrandAudio(path.join(ROOT, "assets"), path.join(pub, "brand"));
say(`narration -16 LUFS: ${stageNarration(path.join(ROOT, ".cache", ID, "audio"), path.join(pub, "audio", ID)).join(", ")}`);

let t = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
say(`bundle: ${secs(t)}s`);

const fmts = opt("format", "both") === "both" ? ["16x9", "9x16"] : [opt("format")];
const stills = opt("stills", "");
for (const format of fmts) {
  t = Date.now();
  const inputProps = { id: ID, format, timing, storyboard, bumper };
  const comp = await selectComposition({ serveUrl, id: "LatexFix", inputProps });
  if (stills) {
    const sd = path.join(ROOT, ".cache/stills", ID);
    fs.mkdirSync(sd, { recursive: true });
    for (const s of stills.split(",")) await renderStill({ composition: comp, serveUrl, output: path.join(sd, `${format}-${Number(s).toFixed(1).padStart(5, "0")}.jpg`), imageFormat: "jpeg", jpegQuality: 85, inputProps, frame: Math.min(comp.durationInFrames - 1, Math.round(Number(s) * brand.fps)) });
    say(`stills -> ${path.relative(ROOT, sd)}`);
    continue;
  }
  const raw = path.join(ROOT, ".cache", `${ID}-${format}-raw.mp4`);
  await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, outputLocation: raw, inputProps, audioCodec: "aac", concurrency: 4 });
  const file = path.join(OUT, `${ID}-${format}.mp4`);
  ff(["-i", raw, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", file]);
  fs.rmSync(raw, { force: true });
  say(`render ${format} (${comp.width}x${comp.height}, ${(comp.durationInFrames / brand.fps).toFixed(2)}s): ${secs(t)}s, ${mb(file)} MB -> ${path.relative(ROOT, file)}`);
  const fdir = path.join(OUT, "frames");
  fs.mkdirSync(fdir, { recursive: true });
  const marks = [1.2, P0 + plan.B[0].e - 0.2, P0 + plan.B[1].e - 0.3, P0 + plan.stages.at(-1).t - 0.15, P0 + plan.B[2].e - 0.3, P0 + plan.B[3].e - 0.3, P0 + plan.ENDs + 2.2, TOTAL - 1.2];
  for (const m of marks) ff(["-ss", m.toFixed(2), "-i", file, "-frames:v", "1", "-q:v", "3", path.join(fdir, `${format}-${m.toFixed(1).padStart(5, "0")}.jpg`)]);
  if (format === "16x9") {
    const poster = path.join(OUT, `${ID}-poster.jpg`);
    await renderStill({ composition: comp, serveUrl, output: poster, imageFormat: "jpeg", jpegQuality: 92, inputProps, frame: Math.round((P0 + plan.poster) * brand.fps) });
    say(`poster: ${mb(poster)} MB -> ${path.relative(ROOT, poster)}`);
  }
}
say(`total: ${secs(t0)}s`);
if (!stills) fs.writeFileSync(path.join(OUT, "run-log.txt"), log.join("\n") + "\n");
