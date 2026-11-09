// node build-three-pilot.mjs [--stills 1,3.5,6,9,11] [--concurrency 4] [--no-flat]
// Keyfeel 3D pilot (three.js via @remotion/three). Renders KeyfeelPilot3D, times it, renders the flat StillHero
// for comparison, and writes video/out/keyfeel-3d/: keyfeel-3d.mp4, keyfeel-flat.mp4, side-by-side.mp4,
// contact-sheet.jpg and run-log.txt (frames per second for each render).
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { PRODUCTS } from "./src/products/index.js";
import { stageBrandAudio } from "./audio.mjs";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes(`--${n}`);
const OUT = path.join(ROOT, "out", "keyfeel-3d");
fs.mkdirSync(OUT, { recursive: true });
const log = [];
const say = (m) => { console.log(m); log.push(m); };
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const secs = (t) => (Date.now() - t) / 1000;
const GL = { gl: "angle" }; // macOS: ANGLE (Metal) gives Chromium a real GPU context; the default swiftshader is CPU-only

const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const pub = path.join(ROOT, ".cache", "public-keyfeel-3d");
fs.rmSync(path.join(ROOT, ".cache", "public-keyfeel-3d"), { recursive: true, force: true });
for (const d of ["fonts", "brand", "media", "audio/tactile"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
fs.copyFileSync(path.join(ROOT, "assets/keyfeel/sounds.webp"), path.join(pub, "media/sounds.webp"));
fs.copyFileSync(path.join(ROOT, "assets/keyfeel/icon.png"), path.join(pub, "media/icon.png"));
const samp = path.join(ROOT, "assets/keyfeel/samples/tactile");
for (const f of fs.readdirSync(samp)) if (f.endsWith(".wav")) fs.copyFileSync(path.join(samp, f), path.join(pub, "audio/tactile", f));
// flat comparison needs the product's own media
const kf = PRODUCTS["keyfeel-promo"];
if (kf) for (const [name, src] of Object.entries(kf.media)) fs.copyFileSync(path.resolve(ROOT, src), path.join(pub, "media", name));
stageBrandAudio(path.join(ROOT, "assets"), path.join(pub, "brand"));

let t = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
say(`bundle: ${secs(t).toFixed(1)}s`);

const props = JSON.parse(opt("props", "{}"));
const comp = await selectComposition({ serveUrl, id: "KeyfeelPilot3D", inputProps: props, chromiumOptions: GL });
const stills = opt("stills", "");
if (stills) {
  const sd = path.join(OUT, "stills");
  fs.mkdirSync(sd, { recursive: true });
  for (const s of stills.split(",")) {
    t = Date.now();
    await renderStill({ composition: comp, serveUrl, output: path.join(sd, `3d-${Number(s).toFixed(1).padStart(4, "0")}.png`), inputProps: props, frame: Math.round(Number(s) * comp.fps), chromiumOptions: GL, timeoutInMilliseconds: 120000 });
    say(`still ${s}s: ${secs(t).toFixed(1)}s`);
  }
  fs.writeFileSync(path.join(OUT, "run-log.txt"), log.join("\n") + "\n");
  process.exit(0);
}

const conc = Number(opt("concurrency", 4));
t = Date.now();
const raw = path.join(ROOT, ".cache", "keyfeel-3d-raw.mp4");
await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 16, outputLocation: raw, audioCodec: "aac", concurrency: conc, chromiumOptions: GL, timeoutInMilliseconds: 120000 });
const s3 = secs(t);
const file3 = path.join(OUT, "keyfeel-3d.mp4");
ff(["-i", raw, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", file3]);
say(`3D render: ${comp.durationInFrames} frames in ${s3.toFixed(1)}s = ${(comp.durationInFrames / s3).toFixed(2)} fps (${(s3 / (comp.durationInFrames / comp.fps)).toFixed(1)}x real time, concurrency ${conc})`);

if (!flag("no-flat") && kf) {
  const timing = { scenes: Array.from({ length: 6 }, () => ({ duration: 3, words: [] })) };
  const flat = await selectComposition({ serveUrl, id: "StillHero", inputProps: { id: "keyfeel-promo", timing } });
  t = Date.now();
  const fileF = path.join(OUT, "keyfeel-flat.mp4");
  await renderMedia({ composition: flat, serveUrl, codec: "h264", crf: 16, muted: true, outputLocation: fileF, inputProps: { id: "keyfeel-promo", timing }, concurrency: 6 });
  const sF = secs(t);
  say(`flat render: ${flat.durationInFrames} frames in ${sF.toFixed(1)}s = ${(flat.durationInFrames / sF).toFixed(2)} fps`);
  // side by side, 12 s each, half size, flat left
  ff(["-i", fileF, "-i", file3, "-filter_complex",
    "[0:v]scale=960:540,tpad=stop_mode=clone:stop_duration=12,trim=0:12,setpts=PTS-STARTPTS[a];[1:v]scale=960:540,trim=0:12,setpts=PTS-STARTPTS[b];[a][b]hstack[v]",
    "-map", "[v]", "-map", "1:a?", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", path.join(OUT, "side-by-side.mp4")]);
}
ff(["-i", file3, "-vf", "fps=1/1.5,scale=640:360,tile=4x2", "-frames:v", "1", "-q:v", "3", path.join(OUT, "contact-sheet.jpg")]);
say(`out: ${path.relative(ROOT, OUT)}`);
fs.writeFileSync(path.join(OUT, "run-log.txt"), log.join("\n") + "\n");
