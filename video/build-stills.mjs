// node build-stills.mjs <id> [--format 16x9|9x16|both] [--no-hero] [--stills t1,t2,...] [--skip-narrate]
// Still-driven promos (Vitae, GlobePin, Haea, Scholar Utility Belt, Paper Review, brand sizzle).
// Prereqs: python3 capture.py (browser captures) for the browser-framed products.
// Outputs video/out/<id>/: <id>-16x9.mp4, <id>-9x16.mp4, <id>-poster.jpg, <id>-hero.mp4/.webm (1280x720, silent,
// 8 s, under 1.5 MB), frames/*.png (review stills) and run-log.txt.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { PRODUCTS } from "./src/products/index.js";
import { stageNarration, stageBrandAudio } from "./audio.mjs";
import { bumperTotal, BUMPER } from "./src/bumper.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const ID = args.find((a) => !a.startsWith("--") && !args[args.indexOf(a) - 1]?.startsWith("--"));
if (!ID || !PRODUCTS[ID]) {
  console.error(`usage: node build-stills.mjs <${Object.keys(PRODUCTS).join("|")}> [--format ...]`);
  process.exit(1);
}
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes(`--${n}`);
const OUT = path.join(ROOT, "out", ID);
fs.mkdirSync(OUT, { recursive: true });
const log = [];
const say = (m) => { console.log(m); log.push(m); };
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(2);
const t0 = Date.now();
const secs = (t) => ((Date.now() - t) / 1000).toFixed(1);
say(`# ${ID} render, ${new Date().toISOString()}`);

const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
if (!flag("skip-narrate")) execFileSync("python3", [path.join(ROOT, "narrate.py"), path.join(ROOT, "storyboards", `${ID}.json`)], { stdio: "inherit" });
const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", ID, "timing.json"), "utf8"));
const storyboard = JSON.parse(fs.readFileSync(path.join(ROOT, "storyboards", `${ID}.json`), "utf8"));
const bumper = { ...BUMPER, ...(storyboard.bumper || {}) };
const product = PRODUCTS[ID];
const plan = product.build(timing);
const P0 = bumper.open - bumper.xf; // product cut starts here in the final timeline
const TOTAL = bumperTotal(plan.total, bumper);
say(`beats (product-local): ${plan.audio.map((a) => `${a.i}@${a.at.toFixed(2)}`).join(" ")}  ENDs ${plan.ENDs.toFixed(2)}  cut ${plan.total.toFixed(2)}s  with bumpers ${TOTAL.toFixed(2)}s`);
if (TOTAL > 45) say(`WARNING: total ${TOTAL.toFixed(1)}s exceeds 45 s`);

// stage assets
const pub = path.join(ROOT, ".cache", `public-${ID}`);
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "brand", "media", "audio"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
for (const n of ["vitae", "globepin", "haea", "moderntex", "outbound-veil"]) fs.copyFileSync(path.resolve(ROOT, `../site/assets/${n}-icon.png`), path.join(pub, "brand", `${n}-icon.png`));
for (const n of ["sub-icon.png", "purplelink-tile.png"]) fs.copyFileSync(path.join(ROOT, ".cache/captures", n), path.join(pub, "brand", n));
for (const [name, src] of Object.entries(product.media)) {
  const abs = path.resolve(ROOT, src);
  if (!fs.existsSync(abs)) throw new Error(`missing media ${src}`);
  fs.copyFileSync(abs, path.join(pub, "media", name));
}
stageBrandAudio(path.join(ROOT, "assets"), path.join(pub, "brand"));
say(`narration -16 LUFS: ${stageNarration(path.join(ROOT, ".cache", ID, "audio"), path.join(pub, "audio", ID)).join(", ")}`);

let t = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
say(`bundle: ${secs(t)}s`);

const fmts = flag("hero-only") ? [] : opt("format", "both") === "both" ? ["16x9", "9x16"] : [opt("format")];
const stills = opt("stills", "");
for (const format of fmts) {
  t = Date.now();
  const inputProps = { id: ID, format, timing, bumper };
  const comp = await selectComposition({ serveUrl, id: "StillPromo", inputProps });
  if (stills) {
    const sd = path.join(ROOT, ".cache/stills", ID);
    fs.mkdirSync(sd, { recursive: true });
    for (const s of stills.split(",")) await renderStill({ composition: comp, serveUrl, output: path.join(sd, `${format}-${s}.png`), inputProps, frame: Math.round(Number(s) * brand.fps) });
    say(`stills -> ${path.relative(ROOT, sd)}`);
    continue;
  }
  const raw = path.join(ROOT, ".cache", `${ID}-${format}-raw.mp4`);
  await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, outputLocation: raw, inputProps, audioCodec: "aac", concurrency: 6 });
  const file = path.join(OUT, `${ID}-${format}.mp4`);
  ff(["-i", raw, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", file]);
  say(`render ${format} (${comp.width}x${comp.height}, ${(comp.durationInFrames / brand.fps).toFixed(1)}s): ${secs(t)}s, ${mb(file)} MB -> ${path.relative(ROOT, file)}`);
  // review frames: title, each beat mid, end card, plus evenly spaced
  const fdir = path.join(OUT, "frames");
  fs.mkdirSync(fdir, { recursive: true });
  const marks = new Set([1.2, 2.05, P0 + 0.9, ...plan.audio.map((a) => +(P0 + a.at + 1.6).toFixed(2)), +(P0 + plan.ENDs + 1.6).toFixed(2), +(TOTAL - 1.4).toFixed(2), +(TOTAL - 0.3).toFixed(2)]);
  for (let k = 1; k <= 8; k++) marks.add(+((TOTAL * k) / 9).toFixed(2));
  for (const m of [...marks].sort((a, b) => a - b)) ff(["-ss", m.toFixed(2), "-i", file, "-frames:v", "1", "-q:v", "3", path.join(fdir, `${format}-${m.toFixed(1).padStart(5, "0")}.jpg`)]);
  if (format === "16x9") {
    const poster = path.join(OUT, `${ID}-poster.jpg`);
    await renderStill({ composition: comp, serveUrl, output: poster, imageFormat: "jpeg", jpegQuality: 92, inputProps, frame: Math.round((P0 + plan.poster) * brand.fps) });
    say(`poster: ${mb(poster)} MB -> ${path.relative(ROOT, poster)}`);
  }
}

if (!stills && !flag("no-hero")) {
  t = Date.now();
  const heroComp = await selectComposition({ serveUrl, id: "StillHero", inputProps: { id: ID, timing } });
  const master = path.join(ROOT, ".cache", `${ID}-hero-master.mp4`);
  await renderMedia({ composition: heroComp, serveUrl, codec: "h264", crf: 14, muted: true, scale: 2 / 3, outputLocation: master, inputProps: { id: ID, timing } });
  const LIM = 1.5e6;
  const enc = (ext, start, max, a) => {
    const out = path.join(OUT, `${ID}-hero.${ext}`);
    for (let crf = start; crf <= max; crf += 2) { ff(["-i", master, "-an", ...a(crf), out]); if (fs.statSync(out).size < LIM) return `${ext} crf ${crf} ${mb(out)} MB`; }
    return `WARNING ${ext} over 1.5 MB`;
  };
  const m = enc("mp4", 22, 40, (q) => ["-c:v", "libx264", "-crf", String(q), "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]);
  const w = enc("webm", 30, 46, (q) => ["-c:v", "libvpx-vp9", "-crf", String(q), "-b:v", "0", "-row-mt", "1", "-pix_fmt", "yuv420p"]);
  say(`hero loop (${plan.hero.T}s, 1280x720, silent): ${secs(t)}s, ${m}, ${w}`);
  ff(["-ss", "2.0", "-i", path.join(OUT, `${ID}-hero.mp4`), "-frames:v", "1", "-q:v", "3", path.join(OUT, "frames", "hero-02.0.jpg")]);
  ff(["-ss", "7.8", "-i", path.join(OUT, `${ID}-hero.mp4`), "-frames:v", "1", "-q:v", "3", path.join(OUT, "frames", "hero-07.8.jpg")]);
}
say(`total: ${secs(t0)}s`);
fs.writeFileSync(path.join(OUT, "run-log.txt"), log.join("\n") + "\n");
