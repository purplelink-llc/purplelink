// Renders the GlobePin App Store preview and the 16:9 film from clips already cut by globepin/cut.py.
//   node globepin/build.mjs [--preview-only] [--stills 30,120,...]
// Output: out/globepin-preview/ (gitignored): globepin-appstore-preview.mp4 (886x1920, 30 fps, H.264, AAC),
// globepin-film-16x9.mp4, and with --stills one PNG per frame number for review.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { stageBrandAudio } from "../audio.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PUB = path.join(ROOT, ".cache", "globepin-preview", "public");
const OUT = path.join(ROOT, "out", "globepin-preview");
const ICON = "/Volumes/Extreme SSD/MapPin App/GlobePin/Assets.xcassets/AppIcon.appiconset/AppIcon.png";
const argv = process.argv.slice(2);
const flag = (f) => argv.includes(`--${f}`);
const opt = (f) => { const i = argv.indexOf(`--${f}`); return i >= 0 ? argv[i + 1] : null; };

if (!fs.existsSync(path.join(PUB, "shots.json"))) throw new Error("run globepin/cut.py first");
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
for (const d of ["fonts", "brand"]) fs.mkdirSync(path.join(PUB, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(PUB, "fonts", path.basename(f.file)));
stageBrandAudio(path.join(ROOT, "assets"), path.join(PUB, "brand"));
fs.copyFileSync(ICON, path.join(PUB, "icon.png"));
fs.mkdirSync(OUT, { recursive: true });
// bundle() copies the public dir when it runs, so screenshots are staged before it
const shotsDir = opt("shots");
const spec = shotsDir ? JSON.parse(fs.readFileSync(path.join(ROOT, "globepin", "shots.json"), "utf8")) : null;
if (spec) {
  fs.mkdirSync(path.join(PUB, "shots"), { recursive: true });
  for (const list of Object.values(spec)) for (const s of list) fs.copyFileSync(path.join(shotsDir, s.raw), path.join(PUB, "shots", s.raw));
}

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: PUB });

// --shots <dir of raw simulator screenshots>: App Store screenshots from globepin/shots.json
if (spec) {
  for (const [device, list] of Object.entries(spec)) {
    const dir = path.join(OUT, `screenshots-${device}`);
    fs.mkdirSync(dir, { recursive: true });
    for (const [i, s] of list.entries()) {
      const props = { device, img: `shots/${s.raw}`, text: s.text, sub: s.sub, hot: s.hot };
      const comp = await selectComposition({ serveUrl, id: "GlobePinShot", inputProps: props });
      const file = path.join(dir, `${device}-${String(i + 1).padStart(2, "0")}.png`);
      await renderStill({ composition: comp, serveUrl, frame: 0, output: file, inputProps: props });
      console.log(file);
    }
  }
  process.exit(0);
}

const stills = opt("stills");
if (stills) {
  for (const id of ["GlobePinPreview", ...(flag("preview-only") ? [] : ["GlobePinFilm"])]) {
    const comp = await selectComposition({ serveUrl, id });
    for (const f of stills.split(",").map(Number)) {
      const file = path.join(OUT, "stills", `${id}-${String(f).padStart(4, "0")}.png`);
      fs.mkdirSync(path.dirname(file), { recursive: true });
      await renderStill({ composition: comp, serveUrl, frame: Math.min(f, comp.durationInFrames - 1), output: file });
    }
  }
  console.log(`stills -> ${path.join(OUT, "stills")}`);
  process.exit(0);
}

async function render(id, name) {
  const comp = await selectComposition({ serveUrl, id });
  const raw = path.join(OUT, `${name}.raw.mp4`), dst = path.join(OUT, `${name}.mp4`);
  await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 16, outputLocation: raw, audioCodec: "aac", concurrency: 6 });
  // App Store Connect wants constant 30 fps H.264 High, yuv420p, stereo AAC 256 kb/s at 48 kHz.
  execFileSync("ffmpeg", ["-v", "error", "-y", "-i", raw, "-c:v", "libx264", "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p",
    "-r", "30", "-crf", "16", "-preset", "slow", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", dst]);
  fs.rmSync(raw);
  console.log(`${id}: ${(comp.durationInFrames / 30).toFixed(2)} s -> ${dst}`);
}

await render("GlobePinPreview", "globepin-appstore-preview");
if (!flag("preview-only")) await render("GlobePinFilm", "globepin-film-16x9");
