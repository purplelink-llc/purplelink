// node build-nee-spot.mjs [--stills-only]
// Renders the Née spot (src/nee/NeeSpot.jsx) to out/nee/nee-spot.mp4 and nee-spot-tall.mp4 (9:16) (silent H.264), and one still per file type
// (the picker with the pointer on the chosen slice) to out/nee/stills/. If out/nee/nee-spot-bed.wav exists, also
// writes out/nee/nee-spot-music.mp4 with it. Ring frames come from the app: `Née --render-spot DIR`, backgrounds cut
// out, copied to assets/nee/spot/.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const pub = path.join(ROOT, ".cache", "public-nee-spot");
fs.rmSync(pub, { recursive: true, force: true });
fs.mkdirSync(path.join(pub, "fonts"), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
fs.cpSync(path.join(ROOT, "assets", "nee"), path.join(pub, "nee"), { recursive: true });
fs.mkdirSync(path.join(pub, "brand"), { recursive: true });
fs.copyFileSync(path.join(ROOT, "..", "site", "assets", "purplelink-wordmark-dark.png"), path.join(pub, "brand", "purplelink-wordmark-dark.png")); // wordmark B on the end card (the site copy; video/assets still has the old mark)

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
const comp = await selectComposition({ serveUrl, id: "NeeSpot" });
const out = path.join(ROOT, "out", "nee");
fs.mkdirSync(path.join(out, "stills"), { recursive: true });

const { SPOT_STILLS } = await import("./src/nee/spot-stills.mjs");
for (const s of SPOT_STILLS) {
  await renderStill({ composition: comp, serveUrl, frame: s.frame, output: path.join(out, "stills", `nee-${s.name}.png`), imageFormat: "png" });
}
if (process.argv.includes("--stills-only")) process.exit(0);

await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, pixelFormat: "yuv420p", muted: true, outputLocation: path.join(out, "nee-spot-raw.mp4") });
execFileSync("ffmpeg", ["-v", "error", "-y", "-i", path.join(out, "nee-spot-raw.mp4"), "-vf", "scale=out_range=tv", "-c:v", "libx264", "-pix_fmt", "yuv420p",
  "-crf", "20", "-preset", "slow", "-movflags", "+faststart", "-an", path.join(out, "nee-spot.mp4")]);
fs.rmSync(path.join(out, "nee-spot-raw.mp4"));
// The tall cut (1080 x 1920) for Shorts, Reels and TikTok.
const tall = await selectComposition({ serveUrl, id: "NeeSpotTall" });
await renderMedia({ composition: tall, serveUrl, codec: "h264", crf: 18, pixelFormat: "yuv420p", muted: true, outputLocation: path.join(out, "nee-spot-tall-raw.mp4") });
execFileSync("ffmpeg", ["-v", "error", "-y", "-i", path.join(out, "nee-spot-tall-raw.mp4"), "-vf", "scale=out_range=tv", "-c:v", "libx264", "-pix_fmt", "yuv420p",
  "-crf", "20", "-preset", "slow", "-movflags", "+faststart", "-an", path.join(out, "nee-spot-tall.mp4")]);
fs.rmSync(path.join(out, "nee-spot-tall-raw.mp4"));
const bed = path.join(out, "nee-spot-bed.wav");
if (fs.existsSync(bed)) {
  for (const [silent, music] of [["nee-spot.mp4", "nee-spot-music.mp4"], ["nee-spot-tall.mp4", "nee-spot-tall-music.mp4"]]) {
    execFileSync("ffmpeg", ["-v", "error", "-y", "-i", path.join(out, silent), "-i", bed, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
      "-shortest", "-movflags", "+faststart", path.join(out, music)]);
  }
}
console.log("wrote", path.relative(ROOT, out));
