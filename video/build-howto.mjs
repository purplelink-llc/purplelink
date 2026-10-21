// node build-howto.mjs <slug> [--stills t1,t2] [--skip-narrate] [--skip-gate] [--concurrency N]
// A daily problem-and-fix video (src/HowTo.jsx) from storyboards/howto/<slug>.json: the publish gate
// (scripts/howto_gate.py), narration (narrate.py: ElevenLabs, edge-tts fallback), the 16:9 tutorial, the 9:16 Short
// (scenes marked "short"), and thumbnails A/B/C for Test & Compare (build-thumbs.mjs).
// Outputs out/howto/<slug>/: <slug>-16x9.mp4, <slug>-9x16.mp4, <slug>-thumb-{A,B,C}.jpg, run-log.txt.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { buildHowTo } from "./src/howto/plan.js";
import { stageNarration, stageBrandAudio, addTrendBed } from "./audio.mjs";
import { buildSrt } from "./src/howto/srt.js";
import { BUMPER, bumperTotal } from "./src/bumper.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(ROOT, "..");
const PY = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3";
const args = process.argv.slice(2);
const SLUG = args.find((a) => !a.startsWith("--") && !/^\d/.test(a));
if (!SLUG) { console.error("usage: node build-howto.mjs <slug>"); process.exit(2); }
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes(`--${n}`);
const SB = path.join(ROOT, "storyboards", "howto", `${SLUG}.json`);
const OUT = path.join(ROOT, "out", "howto", SLUG);
fs.mkdirSync(OUT, { recursive: true });
const log = [];
const say = (m) => { console.log(m); log.push(m); };
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(2);
const t0 = Date.now();
say(`# ${SLUG} ${new Date().toISOString()}`);

if (!flag("skip-gate")) {
  try { execFileSync(PY, [path.join(REPO, "scripts", "howto_gate.py"), SB, "--rebuild"], { stdio: "inherit" }); }
  catch { console.error("gate failed: not rendering"); process.exit(1); }
}
const storyboard = JSON.parse(fs.readFileSync(SB, "utf8"));
if (!flag("skip-narrate")) execFileSync(PY, [path.join(ROOT, "narrate.py"), SB], { stdio: "inherit" });
const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", storyboard.id, "timing.json"), "utf8"));
say(`narration engines: ${[...new Set(timing.scenes.map((s) => s.engine || "edge"))].join(", ")}`);

const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const pub = path.join(ROOT, ".cache", `public-howto-${SLUG}`);
fs.rmSync(path.join(ROOT, ".cache", `public-howto-${SLUG}`), { recursive: true, force: true });
for (const d of ["fonts", "brand", "audio", "img"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
stageBrandAudio(path.join(ROOT, "assets"), path.join(pub, "brand"));
say(`narration -16 LUFS: ${stageNarration(path.join(ROOT, ".cache", storyboard.id, "audio"), path.join(pub, "audio", storyboard.id)).join(", ")}`);
// repo-relative images -> staticFile paths
const stage = (src) => {
  if (!src) return src;
  const name = `${crypto.createHash("sha1").update(src).digest("hex").slice(0, 10)}${path.extname(src)}`;
  fs.copyFileSync(path.join(REPO, src), path.join(pub, "img", name));
  return `img/${name}`;
};
const sbProps = { ...storyboard, scenes: storyboard.scenes.map((s) => ({ ...s, img: stage(s.img), icon: stage(s.icon) })) };

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
const stills = opt("stills", "");
for (const format of ["16x9", "9x16"]) {
  const inputProps = { storyboard: sbProps, timing, format, bumper: BUMPER };
  const comp = await selectComposition({ serveUrl, id: "HowTo", inputProps });
  const { segs, total } = buildHowTo(storyboard, timing, format);
  say(`${format}: ${segs.length} scenes, content ${total.toFixed(2)}s, with bumpers ${bumperTotal(total, BUMPER).toFixed(2)}s`);
  // caption track for YouTube, on the same timeline as this cut (scripts/howto-publish.py uploads it)
  const srt = buildSrt(storyboard, timing, format, BUMPER);
  fs.writeFileSync(path.join(OUT, `${SLUG}-${format}.srt`), srt);
  say(`captions ${format}: ${srt ? srt.trim().split(/\n\n/).length : 0} cues`);
  if (stills) {
    for (const s of stills.split(",")) await renderStill({ composition: comp, serveUrl, output: path.join(OUT, `still-${format}-${s}.jpg`), imageFormat: "jpeg", jpegQuality: 88, inputProps, frame: Math.min(comp.durationInFrames - 1, Math.round(Number(s) * brand.fps)) });
    continue;
  }
  const t = Date.now();
  const raw = path.join(ROOT, ".cache", `howto-${SLUG}-${format}-raw.mp4`);
  const qa = [];
  const onBrowserLog = (l) => { const m = /^QA_RECT (.*)$/.exec(l.text || ""); if (m) { try { const r = JSON.parse(m[1]); qa.push({ name: `scene ${r.scene} ${r.name}`, t: Math.round(r.t * 1000) / 1000, rect: r.rect }); } catch {} } };
  await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, outputLocation: raw, inputProps, audioCodec: "aac", concurrency: Number(opt("concurrency", "3")), onBrowserLog });
  const file = path.join(OUT, `${SLUG}-${format}.mp4`);
  ff(["-i", raw, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", file]);
  fs.rmSync(raw, { force: true });
  say(addTrendBed(file, SLUG));
  // text boxes measured by HowTo.jsx, for the rendered-video check (scripts/howto_gate.py --video)
  qa.sort((x, y) => x.t - y.t || x.name.localeCompare(y.name));
  fs.writeFileSync(path.join(OUT, `${SLUG}-${format}.qa.json`), JSON.stringify({ format, fps: brand.fps, final_hold: BUMPER.close, regions: qa }, null, 1));
  say(`qa regions ${format}: ${qa.length}`);
  say(`render ${format} (${comp.width}x${comp.height}, ${(comp.durationInFrames / brand.fps).toFixed(2)}s): ${((Date.now() - t) / 1000).toFixed(1)}s, ${mb(file)} MB`);
}
if (!stills) {
  const spec = Object.entries(storyboard.thumbs).map(([k, v]) => ({ id: `${SLUG}-thumb-${k}`, variant: k, ...v }));
  const specPath = path.join(".cache", `howto-thumbs-${SLUG}.json`);
  fs.writeFileSync(path.join(ROOT, specPath), JSON.stringify(spec, null, 1));
  execFileSync(process.execPath, [path.join(ROOT, "build-thumbs.mjs"), "--spec", specPath, "--out", OUT, "--no-sheet"], { stdio: "inherit" });
  say(`thumbnails A/B/C -> ${path.relative(ROOT, OUT)}`);
}
say(`total ${((Date.now() - t0) / 1000).toFixed(1)}s`);
fs.writeFileSync(path.join(OUT, "run-log.txt"), log.join("\n") + "\n");
