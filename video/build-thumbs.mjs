// node build-thumbs.mjs [--only ID,ID] [--spec thumbs/youtube.json] [--out DIR] [--no-sheet]
// Renders YouTube thumbnails (src/Thumb.jsx, 1280x720 JPEG) for every entry in the spec into out/thumbs/<id>.jpg,
// plus out/thumbs/sheet.jpg (all of them at 320 px, the size viewers actually judge them at).
// Spec entries: { id, kind: "error"|"long"|"product", ... }. A product `img` is a repo-relative path, or
// { video, t } to use a frame of the app's own promo. Upload with scripts/yt-thumbnail.py or yt-upload.py --thumbnail.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(ROOT, "..");
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
let specs = JSON.parse(fs.readFileSync(path.join(ROOT, opt("spec", "thumbs/youtube.json")), "utf8"));
const only = opt("only", "");
if (only) specs = specs.filter((s) => only.split(",").includes(s.id));
if (!specs.length) throw new Error("no thumbnail specs selected");

const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const pub = path.join(ROOT, ".cache", "public-thumbs");
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "img"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));

// stage an image (or a promo frame) into the public dir and return its staticFile path
function stage(src) {
  if (!src) return undefined;
  if (typeof src === "object") {
    const name = `frame-${crypto.createHash("sha1").update(JSON.stringify(src)).digest("hex").slice(0, 10)}.png`;
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-ss", String(src.t), "-i", path.join(REPO, src.video), "-frames:v", "1", path.join(pub, "img", name)]);
    return `img/${name}`;
  }
  const abs = path.join(REPO, src);
  if (!fs.existsSync(abs)) throw new Error(`missing image ${src}`);
  const name = `${crypto.createHash("sha1").update(src).digest("hex").slice(0, 10)}${path.extname(src)}`;
  fs.copyFileSync(abs, path.join(pub, "img", name));
  return `img/${name}`;
}
const props = specs.map((s) => ({ ...s, img: stage(s.img), icon: stage(s.icon), icons: s.icons?.map(stage) }));

const OUT = path.resolve(ROOT, opt("out", path.join("out", "thumbs")));
fs.mkdirSync(OUT, { recursive: true });
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
const files = [];
for (const p of props) {
  const comp = await selectComposition({ serveUrl, id: "Thumb", inputProps: p });
  const file = path.join(OUT, `${p.id}.jpg`);
  await renderStill({ composition: comp, serveUrl, output: file, imageFormat: "jpeg", jpegQuality: 90, inputProps: p });
  const mb = fs.statSync(file).size / 1e6;
  if (mb >= 2) throw new Error(`${p.id}: ${mb.toFixed(2)} MB, YouTube's limit is 2 MB`);
  console.log(`${p.id}  ${p.kind.padEnd(7)} ${mb.toFixed(2)} MB  ${p.msg || p.line}`);
  files.push(file);
}
if (args.includes("--no-sheet")) process.exit(0);
const cols = Math.min(4, files.length);
const rows = Math.ceil(files.length / cols);
const layout = files.map((_, i) => `${(i % cols) * 320}_${Math.floor(i / cols) * 180}`).join("|");
execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...files.flatMap((f) => ["-i", f]), "-filter_complex",
  files.length > 1
    ? `${files.map((_, i) => `[${i}]scale=320:180[s${i}]`).join(";")};${files.map((_, i) => `[s${i}]`).join("")}xstack=inputs=${files.length}:layout=${layout}:fill=white`
    : "[0]scale=320:180", path.join(OUT, "sheet.jpg")]);
console.log(`${files.length} thumbnails -> ${path.relative(ROOT, OUT)} (sheet.jpg ${cols}x${rows})`);
