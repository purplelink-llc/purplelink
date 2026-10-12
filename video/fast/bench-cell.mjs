#!/usr/bin/env node
// One benchmark cell in its own process (fresh Chrome, fresh memory). Usage: node bench-cell.mjs '<json cell>'
// Prints one JSON line with the timings. Run by bench-grid.mjs; can also be run by hand.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { cachePath, loadavg1, sha, dirKey } from "./cache.mjs";
import { proxyFor } from "./proxy.mjs";

const cell = JSON.parse(process.argv[2]);
const adapter = await import(`./adapters/${cell.adapter}.mjs`);
const t00 = performance.now();
const prep = adapter.prepare({ sbPath: cell.sb, format: cell.format });
const [f0, f1] = cell.frames ? cell.frames.split("-").map(Number) : [0, prep.totalFrames - 1];

// stage the public folder: assets copied, clips linked to the chosen proxy (so no clip is ever copied)
const pub = cachePath("bench", `public-${sha(JSON.stringify([cell.adapter, cell.sb, cell.format, cell.clips]))}`, "x");
const pubDir = path.dirname(pub);
fs.rmSync(pubDir, { recursive: true, force: true });
for (const a of prep.assets) { const d = path.join(pubDir, a.dest); fs.mkdirSync(path.dirname(d), { recursive: true }); fs.copyFileSync(a.src, d); }
const tProxy0 = performance.now();
for (const c of prep.clips) {
  const p = proxyFor(c.src, cell.clips || "orig");
  const d = path.join(pubDir, c.dest); // the composition asks for media/<name>.mp4; a ProRes proxy keeps that name (ffmpeg sniffs the content)
  fs.mkdirSync(path.dirname(d), { recursive: true });
  // Remotion's file server returns 404 for symlinks, so link with a hard link (same volume, no copy) when possible.
  if ((cell.clips || "orig") === "orig") fs.copyFileSync(p, d); // baseline behaviour: the clip is copied into the public folder
  else fs.linkSync(p, d);
  c.staged = d;
}
const proxy_s = (performance.now() - tProxy0) / 1000;

const load0 = loadavg1();
const tB0 = performance.now();
const serveUrl = await bundle({ entryPoint: prep.entryPoint, publicDir: pubDir, symlinkPublicDir: cell.bundleSymlink === true });
const bundle_s = (performance.now() - tB0) / 1000;

const comp = await selectComposition({ serveUrl, id: prep.compositionId, inputProps: prep.inputProps });
const out = cachePath("bench", "out", `${cell.name}-${process.pid}.mp4`);
const opts = {
  composition: comp, serveUrl, inputProps: prep.inputProps, outputLocation: out, muted: true, overwrite: true,
  codec: "h264", pixelFormat: "yuv420p", frameRange: [f0, f1],
  concurrency: cell.concurrency ?? 5,
  imageFormat: cell.imageFormat ?? "jpeg",
  scale: cell.scale ?? 1,
  hardwareAcceleration: cell.hw ?? "disable",
  timeoutInMilliseconds: 180000, logLevel: "error",
};
if (cell.jpegQuality != null) opts.jpegQuality = cell.jpegQuality;
if (cell.hw === "if-possible" || cell.hw === "required") { opts.videoBitrate = cell.videoBitrate ?? "16M"; }
else { opts.crf = cell.crf ?? 16; if (cell.x264Preset) opts.x264Preset = cell.x264Preset; }
if (cell.gl) opts.chromiumOptions = { gl: cell.gl };
if (cell.cacheMB != null) { opts.offthreadVideoCacheSizeInBytes = cell.cacheMB * 1048576; }
if (cell.threads != null) opts.offthreadVideoThreads = cell.threads;
if (cell.mediaCacheMB != null) opts.mediaCacheSizeInBytes = cell.mediaCacheMB * 1048576;
if (cell.noParallelEncode) opts.disallowParallelEncoding = true;
if (cell.chromeMode) opts.chromeMode = cell.chromeMode;

const tR0 = performance.now();
await renderMedia(opts);
const render_s = (performance.now() - tR0) / 1000;
const frames = f1 - f0 + 1;
fs.rmSync(pubDir, { recursive: true, force: true }); // staged copy is rebuilt per run; do not leave GBs behind
console.log("RESULT " + JSON.stringify({
  name: cell.name, frames, render_s: +render_s.toFixed(2), fps: +(frames / render_s).toFixed(2), bundle_s: +bundle_s.toFixed(2), proxy_s: +proxy_s.toFixed(2),
  total_s: +((performance.now() - t00) / 1000).toFixed(2), out, out_mb: +(fs.statSync(out).size / 1e6).toFixed(2),
  load_before: +load0.toFixed(2), load_after: +loadavg1().toFixed(2), freemem_gb: +(os.freemem() / 1073741824).toFixed(2),
}));
