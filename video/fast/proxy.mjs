// Proxy clips: re-encode a screen-capture clip into a form that is cheap to seek in, once, then reuse it.
// A long-GOP H.264 clip (one keyframe every ~250 frames) makes every random frame lookup decode from far back.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { cachePath, fileKey } from "./cache.mjs";

export const PROXY_KINDS = {
  orig: { ext: null, args: null, note: "the clip as captured (no proxy)" },
  gop15: { ext: "mp4", args: ["-c:v", "libx264", "-preset", "fast", "-crf", "14", "-g", "15", "-keyint_min", "15", "-sc_threshold", "0", "-pix_fmt", "yuv420p"], note: "H.264 with a keyframe every half second" },
  intra: { ext: "mp4", args: ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-g", "1", "-pix_fmt", "yuv420p"], note: "H.264, every frame a keyframe" },
  vt_intra: { ext: "mp4", args: ["-c:v", "h264_videotoolbox", "-b:v", "60M", "-g", "1", "-allow_sw", "0", "-pix_fmt", "yuv420p"], note: "hardware H.264, every frame a keyframe" },
  prores: { ext: "mov", args: ["-c:v", "prores_videotoolbox", "-profile:v", "proxy", "-pix_fmt", "yuv422p10le"], note: "hardware ProRes Proxy" },
};

/** Returns the path of the proxy for `src` of the given kind, creating it when missing. `orig` returns `src`. */
export function proxyFor(src, kind = "orig", { log = () => {} } = {}) {
  const k = PROXY_KINDS[kind];
  if (!k) throw new Error(`unknown proxy kind ${kind}`);
  if (!k.args) return src;
  const out = cachePath("proxy", kind, `${path.basename(src, path.extname(src))}-${fileKey(src)}.${k.ext}`);
  if (fs.existsSync(out)) return out;
  const tmp = `${out}.part.${process.pid}.${k.ext}`;
  const t0 = Date.now();
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-an", ...k.args, tmp], { stdio: ["ignore", "ignore", "inherit"] });
  fs.renameSync(tmp, out);
  log(`proxy ${kind} ${path.basename(src)} ${((Date.now() - t0) / 1000).toFixed(1)}s ${(fs.statSync(out).size / 1e6).toFixed(0)} MB`);
  return out;
}
