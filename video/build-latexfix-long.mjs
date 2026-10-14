// node build-latexfix-long.mjs [--stills t1,t2,...] [--skip-narrate] [--concurrency N]
// The long "LaTeX Error: File not found" tutorial (src/LatexLong.jsx): a title card, the five causes on
// /latex-errors/file-not-found/ (storyboards/latex-errors/file-not-found-*.json, content in src/latexfix/data.js),
// and a ModernTex card with the product's own editor screenshot. One render, one pair of Purplelink bumpers.
// Outputs video/out/latex-errors/file-not-found-long/: file-not-found-long-16x9.mp4, -poster.jpg, frames/*.jpg, run-log.txt.
// Narration is synthesised per storyboard (narrate.py) and cached; run `node check-latexfix.mjs` and
// `node verify-latexfix.mjs` first: every on-screen code line is checked against the page and the real pdflatex log.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { buildLong } from "./src/latexfix/longplan.js";
import { stageNarration, stageBrandAudio } from "./audio.mjs";
import { BUMPER, bumperTotal } from "./src/bumper.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PY = fs.existsSync("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3") ? "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" : "python3";
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes(`--${n}`);
const NAME = "file-not-found-long";
const OUT = path.join(ROOT, "out", "latex-errors", NAME);
fs.mkdirSync(OUT, { recursive: true });
const log = [];
const say = (m) => { console.log(m); log.push(m); };
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(2);
const secs = (t) => ((Date.now() - t) / 1000).toFixed(1);
const t0 = Date.now();
say(`# ${NAME} render, ${new Date().toISOString()}`);

const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
// part order = video order
const PLAN = [
  { kind: "title", id: "fnf-long-title", sb: "storyboards/latex-errors-long/title.json" },
  { kind: "cut", id: "file-not-found-package", sb: "storyboards/latex-errors/file-not-found-package.json" },
  { kind: "cut", id: "file-not-found-name", sb: "storyboards/latex-errors/file-not-found-name.json" },
  { kind: "cut", id: "file-not-found-template", sb: "storyboards/latex-errors/file-not-found-template.json" },
  { kind: "cut", id: "file-not-found-class", sb: "storyboards/latex-errors/file-not-found-class.json" },
  { kind: "cut", id: "file-not-found-input", sb: "storyboards/latex-errors/file-not-found-input.json" },
  { kind: "moderntex", id: "fnf-long-moderntex", sb: "storyboards/latex-errors-long/moderntex.json" },
];
const parts = [];
for (const p of PLAN) {
  const sbPath = path.join(ROOT, p.sb);
  if (!flag("skip-narrate")) execFileSync(PY, [path.join(ROOT, "narrate.py"), sbPath], { stdio: "inherit" });
  const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", p.id, "timing.json"), "utf8"));
  const storyboard = JSON.parse(fs.readFileSync(sbPath, "utf8"));
  parts.push({ kind: p.kind, id: p.id, timing, storyboard });
}
const { segs, total } = buildLong(parts);
const TOTAL = bumperTotal(total, BUMPER);
for (const s of segs) say(`${s.kind.padEnd(9)} ${s.id.padEnd(26)} starts ${s.t0.toFixed(2)}s, ${s.dur.toFixed(2)}s`);
say(`content ${total.toFixed(2)}s, with bumpers ${TOTAL.toFixed(2)}s`);
if (TOTAL < 120 || TOTAL > 360) say(`WARNING: total ${TOTAL.toFixed(2)}s is outside 2 to 6 minutes`);
for (const s of segs) {
  if (s.kind !== "cut") continue;
  const lastWord = Math.max(...[0, 1, 2, 3].map((i) => s.plan.B[i].n + (s.timing.scenes[i].words.at(-1)?.end ?? 0)));
  if (lastWord > s.plan.ENDs + 0.05) throw new Error(`${s.id}: narration runs past the end of the cut`);
}

const pub = path.join(ROOT, ".cache", `public-${NAME}`);
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand", "audio", "img"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
stageBrandAudio(path.join(ROOT, "assets"), path.join(pub, "brand"));
for (const p of PLAN) say(`narration -16 LUFS ${p.id}: ${stageNarration(path.join(ROOT, ".cache", p.id, "audio"), path.join(pub, "audio", p.id)).join(", ")}`);
fs.copyFileSync(path.join(ROOT, "..", "site", "assets", "moderntex-screens", "01-editor-clean-1440.webp"), path.join(pub, "img", "moderntex-editor.webp"));

let t = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
say(`bundle: ${secs(t)}s`);
const inputProps = { parts, bumper: BUMPER };
const comp = await selectComposition({ serveUrl, id: "LatexLong", inputProps });
const stills = opt("stills", "");
if (stills) {
  const sd = path.join(ROOT, ".cache/stills", NAME);
  fs.mkdirSync(sd, { recursive: true });
  for (const s of stills.split(",")) await renderStill({ composition: comp, serveUrl, output: path.join(sd, `${Number(s).toFixed(1).padStart(6, "0")}.jpg`), imageFormat: "jpeg", jpegQuality: 88, inputProps, frame: Math.round(Number(s) * brand.fps) });
  say(`stills -> ${path.relative(ROOT, sd)}`);
  process.exit(0);
}
t = Date.now();
const raw = path.join(ROOT, ".cache", `${NAME}-raw.mp4`);
await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, outputLocation: raw, inputProps, audioCodec: "aac", concurrency: Number(opt("concurrency", "2")) });
const file = path.join(OUT, `${NAME}-16x9.mp4`);
ff(["-i", raw, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", file]);
fs.rmSync(raw, { force: true });
say(`render 16x9 (${comp.width}x${comp.height}, ${(comp.durationInFrames / brand.fps).toFixed(2)}s): ${secs(t)}s, ${mb(file)} MB -> ${path.relative(ROOT, file)}`);
const fdir = path.join(OUT, "frames");
fs.mkdirSync(fdir, { recursive: true });
const P0 = BUMPER.open - BUMPER.xf;
const marks = [1.2, ...segs.flatMap((s) => [P0 + s.t0 + Math.min(s.dur - 0.3, s.kind === "cut" ? s.plan.B[1].e - 0.3 : 6)]), TOTAL - 1.2];
for (const m of marks) ff(["-ss", m.toFixed(2), "-i", file, "-frames:v", "1", "-q:v", "3", path.join(fdir, `${m.toFixed(1).padStart(6, "0")}.jpg`)]);
const poster = path.join(OUT, `${NAME}-poster.jpg`);
await renderStill({ composition: comp, serveUrl, output: poster, imageFormat: "jpeg", jpegQuality: 92, inputProps, frame: Math.round((P0 + segs[0].t0 + 8) * brand.fps) });
say(`poster: ${mb(poster)} MB -> ${path.relative(ROOT, poster)}`);
say(`total: ${secs(t0)}s`);
fs.writeFileSync(path.join(OUT, "run-log.txt"), log.join("\n") + "\n");
