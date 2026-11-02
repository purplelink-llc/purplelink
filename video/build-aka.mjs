// node build-aka.mjs
// Renders the silent AKA demo (src/aka/AKADemo.jsx): out/aka/aka-demo.mp4 (H.264) and
// out/aka/aka-poster.png. Copy them into site/assets/video/ (mp4, and the poster as WebP) when the page changes.
// No narration and no audio. Uses the same bundle approach as panely-shots.mjs.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const pub = path.join(ROOT, ".cache", "public-aka");
fs.rmSync(pub, { recursive: true, force: true });
fs.mkdirSync(path.join(pub, "fonts"), { recursive: true });
fs.mkdirSync(path.join(pub, "aka"), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
const assets = path.join(ROOT, "assets", "aka");
for (const n of fs.readdirSync(assets)) fs.copyFileSync(path.join(assets, n), path.join(pub, "aka", n));

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
const comp = await selectComposition({ serveUrl, id: "AKADemo" });
const out = path.join(ROOT, "out", "aka");
fs.mkdirSync(out, { recursive: true });
await renderMedia({
  composition: comp, serveUrl, codec: "h264", crf: 24, pixelFormat: "yuv420p", muted: true,
  outputLocation: path.join(out, "aka-raw.mp4"),
});
// Remotion's file reports full-range yuvj420p. Re-encode as ordinary limited-range yuv420p with the index up front,
// so every browser plays it and it can start before it has all downloaded.
execFileSync("ffmpeg", ["-v", "error", "-y", "-i", path.join(out, "aka-raw.mp4"), "-vf", "scale=out_range=tv", "-c:v", "libx264", "-pix_fmt", "yuv420p",
  "-crf", "23", "-preset", "slow", "-movflags", "+faststart", "-an", path.join(out, "aka-demo.mp4")]);
fs.rmSync(path.join(out, "aka-raw.mp4"));
await renderStill({ composition: comp, serveUrl, frame: Math.round(5.8 * brand.fps), output: path.join(out, "aka-poster.png"), imageFormat: "png" });
console.log("wrote", path.relative(ROOT, out));
