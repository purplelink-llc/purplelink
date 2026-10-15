// node build-photoquiz.mjs <spec.json> --out FILE.mp4 [--stills t1,t2] [--skip-narrate]
// The weekly "Where in the world?" Short (src/PhotoQuiz.jsx). The spec comes from TikTokPipeline/PhotoPipeline/quiz.py:
//   { "id": "photoquiz-2026-W42", "week": "2026-W42", "url": "purplelink.llc/photography",
//     "items": [{ "place", "country", "fact", "img": "/abs/path/prepared.jpg", "hub": "https://..." }] }
// Narration (narrate.py: ElevenLabs when its key exists, edge-tts otherwise) follows quizLines(spec).
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { quizLines } from "./src/photoquiz/plan.js";
import { stageNarration, addTrendBed } from "./audio.mjs";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PY = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3";
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const specPath = args.find((a) => a.endsWith(".json"));
if (!specPath) { console.error("usage: node build-photoquiz.mjs <spec.json> --out FILE.mp4"); process.exit(2); }
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const out = path.resolve(opt("out", path.join(ROOT, "out", "photoquiz", `${spec.id}.mp4`)));
fs.mkdirSync(path.dirname(out), { recursive: true });

const sb = { id: spec.id, voice: spec.voice || "en-GB-SoniaNeural", rate: spec.rate || "-2%",
  scenes: quizLines(spec).map((narration) => ({ narration })) };
const sbPath = path.join(ROOT, ".cache", `${spec.id}.storyboard.json`);
fs.mkdirSync(path.dirname(sbPath), { recursive: true });
fs.writeFileSync(sbPath, JSON.stringify(sb, null, 1));
if (!args.includes("--skip-narrate")) execFileSync(PY, [path.join(ROOT, "narrate.py"), sbPath], { stdio: "inherit" });
const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", spec.id, "timing.json"), "utf8"));

const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const pub = path.join(ROOT, ".cache", `public-${spec.id}`);
fs.rmSync(path.join(ROOT, ".cache", `public-${spec.id}`), { recursive: true, force: true });
for (const d of ["fonts", "audio", "img"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
console.log(`narration: ${stageNarration(path.join(ROOT, ".cache", spec.id, "audio"), path.join(pub, "audio", spec.id)).join(", ")}`);
const items = spec.items.map((it) => {
  const name = `${crypto.createHash("sha1").update(it.img).digest("hex").slice(0, 10)}${path.extname(it.img)}`;
  fs.copyFileSync(it.img, path.join(pub, "img", name));
  return { ...it, img: `img/${name}` };
});
const inputProps = { spec: { ...spec, items }, timing };
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
const comp = await selectComposition({ serveUrl, id: "PhotoQuiz", inputProps });
console.log(`${spec.id}: ${(comp.durationInFrames / brand.fps).toFixed(1)}s`);
const stills = opt("stills", "");
if (stills) {
  for (const s of stills.split(",")) await renderStill({ composition: comp, serveUrl, output: out.replace(/\.mp4$/, `-still-${s}.jpg`), imageFormat: "jpeg", jpegQuality: 88, inputProps, frame: Math.min(comp.durationInFrames - 1, Math.round(Number(s) * brand.fps)) });
  process.exit(0);
}
const raw = path.join(ROOT, ".cache", `${spec.id}-raw.mp4`);
await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, outputLocation: raw, inputProps, audioCodec: "aac", concurrency: Number(opt("concurrency", "3")) });
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", raw, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]);
fs.rmSync(raw, { force: true });
console.log(addTrendBed(out, spec.id));
console.log(`wrote ${out} (${(fs.statSync(out).size / 1e6).toFixed(2)} MB)`);
