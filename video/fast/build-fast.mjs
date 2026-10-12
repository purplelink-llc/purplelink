#!/usr/bin/env node
// Fast trailer builder: draft/final profiles, per-scene segment cache, proxy clips, cached bundle, one shared Chrome,
// load-aware concurrency, one loudness pass. Same composition and mixer as build-rf4.mjs.
//   node fast/build-fast.mjs storyboards/rubblefront-v4.json --format 16x9 [--draft|--final] [--wishlist] [--no-audio] [--force] [--adapter rubblefront4]
// Draft: half size, jpeg, fast preset, written to the cache (never over a deliverable).
// Final: full size, writes the adapter's output path. Unchanged scenes are reused from the segment cache in both.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition, openBrowser } from "@remotion/renderer";
import { cachePath, sha, fileKey, dirKey, loadavg1, pruneCache } from "./cache.mjs";
import { proxyFor } from "./proxy.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VIDEO = path.resolve(HERE, "..");
const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const say = (m) => console.log(m);
const t0 = performance.now();
const lap = (label) => say(`  [${((performance.now() - t0) / 1000).toFixed(1)}s] ${label}`);

const settings = JSON.parse(fs.readFileSync(path.join(HERE, "settings.json"), "utf8"));
const draft = !flag("final");
const prof = { ...settings.common, ...(draft ? settings.draft : settings.final) };
const adapter = await import(`./adapters/${opt("adapter", "rubblefront4")}.mjs`);
const sbPath = args.find((a) => a.endsWith(".json"));
const format = opt("format", "16x9");
const wishlist = flag("wishlist");
const prep = adapter.prepare({ sbPath, format, wishlist });
const { plan, fps } = prep;
const total = prep.totalFrames;
say(`${prep.sb.id} ${format} ${draft ? "DRAFT" : "FINAL"}: ${plan.total.toFixed(2)} s, ${total} frames, ${plan.shots.length} scenes`);

// 1. public folder (assets copied once, clips hard-linked to the chosen proxy), cached by content key
const clipKind = prof.clips || "orig";
const pubKey = sha(JSON.stringify([prep.assets.map((a) => [a.dest, fileKey(a.src)]), prep.clips.map((c) => [c.dest, fileKey(c.src)]), clipKind]));
const pubDir = cachePath("fast", `public-${pubKey}`, "x").replace(/\/x$/, "");
if (!fs.existsSync(path.join(pubDir, ".done"))) {
  fs.rmSync(pubDir, { recursive: true, force: true });
  for (const a of prep.assets) { const d = path.join(pubDir, a.dest); fs.mkdirSync(path.dirname(d), { recursive: true }); fs.copyFileSync(a.src, d); }
  for (const c of prep.clips) {
    const p = proxyFor(c.src, clipKind);
    const d = path.join(pubDir, c.dest); fs.mkdirSync(path.dirname(d), { recursive: true });
    if (clipKind === "orig") fs.copyFileSync(p, d); else fs.linkSync(p, d);
  }
  fs.writeFileSync(path.join(pubDir, ".done"), "");
}
lap(`public folder ${path.basename(pubDir)}`);

// 2. bundle, cached by source + public content
const srcKey = sha(JSON.stringify([prep.sourceDirs.map((d) => dirKey(d)), (prep.sourceFiles || []).map(fileKey), pubKey]));
const bundleDir = cachePath("fast", `bundle-${srcKey}`, "x").replace(/\/x$/, "");
let serveUrl;
if (fs.existsSync(path.join(bundleDir, "index.html")) && !flag("force")) serveUrl = bundleDir;
else {
  fs.rmSync(bundleDir, { recursive: true, force: true });
  serveUrl = await bundle({ entryPoint: prep.entryPoint, publicDir: pubDir, outDir: bundleDir });
}
lap(`bundle ${path.basename(bundleDir)}`);

// 3. scene segments. Segment i runs from its scene's start frame to the next scene's start frame - 1.
const starts = plan.shots.map((s) => Math.round(s.start * fps));
const segs = plan.shots.map((s, i) => ({ i, shot: s, f0: starts[i], f1: (i + 1 < starts.length ? starts[i + 1] : total) - 1 })).filter((s) => s.f1 >= s.f0);
if (segs[0].f0 > 0) segs[0].f0 = 0;
const clipKeys = new Map(prep.clips.map((c) => [c.name, fileKey(c.src)]));
const scale = prof.scale ?? 1;
const renderKey = sha(JSON.stringify([format, scale, prof.crf ?? prep.crf, prof.x264Preset, prof.hw, prof.videoBitrate, prof.imageFormat, prof.jpegQuality, clipKind]));
const segHash = (s) => {
  const cards = plan.cards.filter((c) => c.end * fps >= s.f0 && c.start * fps <= s.f1);
  const clips = [s.shot.clip, ...(s.shot.insets || []).map((x) => x.clip)].filter(Boolean).map((n) => clipKeys.get(n));
  return sha(JSON.stringify([srcKey, renderKey, fps, s.f0, s.f1, s.shot, cards, clips, plan.format, plan.end]));
};
const segDir = cachePath("fast", "segments", prep.sb.id, `${format}-${draft ? "draft" : "final"}`, "x").replace(/\/x$/, "");
fs.mkdirSync(segDir, { recursive: true });
const todo = segs.filter((s) => { s.file = path.join(segDir, `${String(s.i).padStart(2, "0")}-${segHash(s)}.mp4`); return flag("force") || !fs.existsSync(s.file); });
say(`  ${segs.length - todo.length} of ${segs.length} scenes cached, ${todo.length} to render (${todo.reduce((a, s) => a + s.f1 - s.f0 + 1, 0)} frames)`);

if (todo.length) {
  const cores = os.cpus().length;
  const free = Math.max(1, cores - Math.round(loadavg1() / 2)); // load-aware: back off when other work is running
  const concurrency = Math.max(prof.concurrencyMin ?? 2, Math.min(prof.concurrency ?? 5, free));
  say(`  concurrency ${concurrency} (load ${loadavg1().toFixed(1)}, ${cores} cores)`);
  const inputProps = prep.inputProps;
  const comp = await selectComposition({ serveUrl, id: prep.compositionId, inputProps });
  const browser = await openBrowser("chrome", { chromiumOptions: prof.gl ? { gl: prof.gl } : {} });
  try {
    for (const s of todo) {
      const o = {
        composition: comp, serveUrl, inputProps, outputLocation: s.file + ".part.mp4", muted: true, overwrite: true, codec: "h264", pixelFormat: "yuv420p",
        frameRange: [s.f0, s.f1], concurrency, imageFormat: prof.imageFormat ?? "jpeg", scale, puppeteerInstance: browser, timeoutInMilliseconds: 180000, logLevel: "error",
        hardwareAcceleration: prof.hw ?? "disable",
      };
      if (prof.jpegQuality != null) o.jpegQuality = prof.jpegQuality;
      if (prof.hw === "if-possible" || prof.hw === "required") o.videoBitrate = prof.videoBitrate ?? "16M";
      else { o.crf = prof.crf ?? prep.crf; if (prof.x264Preset) o.x264Preset = prof.x264Preset; }
      if (prof.threads != null) o.offthreadVideoThreads = prof.threads;
      if (prof.cacheMB != null) o.offthreadVideoCacheSizeInBytes = prof.cacheMB * 1048576;
      await renderMedia(o);
      fs.renameSync(s.file + ".part.mp4", s.file);
      lap(`scene ${s.i} frames ${s.f0}-${s.f1}`);
    }
  } finally { await browser.close({ silent: true }).catch(() => {}); }
}
// drop stale segments of this storyboard/format/profile
const keep = new Set(segs.map((s) => path.basename(s.file)));
for (const f of fs.readdirSync(segDir)) if (f.endsWith(".mp4") && !keep.has(f)) fs.rmSync(path.join(segDir, f), { force: true });

// 4. join segments (stream copy)
const work = cachePath("fast", "work", prep.sb.id, "x").replace(/\/x$/, "");
fs.mkdirSync(work, { recursive: true });
const list = path.join(work, `${format}-${draft ? "d" : "f"}.txt`);
fs.writeFileSync(list, segs.map((s) => `file '${s.file}'`).join("\n"));
const raw = path.join(work, `${format}-${draft ? "d" : "f"}-raw.mp4`);
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", raw]);
lap("joined");

// 5. audio (cached) and mux
const outFile = opt("out") ? path.resolve(opt("out")) : draft ? cachePath("fast", "drafts", `${prep.sb.id}-${format}${wishlist ? "-wishlist" : ""}.mp4`) : path.join(prep.outDir, prep.outName(wishlist));
fs.mkdirSync(path.dirname(outFile), { recursive: true });
if (flag("no-audio")) { fs.copyFileSync(raw, outFile); }
else {
  const spec = prep.mixSpec();
  spec.game = [];
  for (const g of plan.gameAudio) {
    const c = prep.clips.find((x) => x.name === g.clip);
    const wav = c && c.src.replace(/\.mp4$/, ".wav");
    if (wav && fs.existsSync(wav)) spec.game.push({ file: wav, in: g.in, dur: g.dur, t: g.t, gain_db: g.gain_db });
  }
  const audKey = sha(JSON.stringify([spec, fileKey(path.join(VIDEO, "mixrf2.py")), spec.game.map((g) => fileKey(g.file)), spec.music.map((m) => fileKey(m.file))]));
  const norm = path.join(work, `norm-${format}-${audKey}.wav`);
  if (!fs.existsSync(norm)) {
    const specFile = path.join(work, `mix-${format}.json`);
    fs.writeFileSync(specFile, JSON.stringify(spec, null, 1));
    const wav = path.join(work, `mix-${format}-${audKey}.wav`);
    execFileSync("python3", [path.join(VIDEO, "mixrf2.py"), specFile, wav], { stdio: "ignore" });
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", wav, "-af", "loudnorm=I=-14:TP=-2.2:LRA=11", "-ar", "48000", norm]);
    fs.rmSync(wav, { force: true });
    for (const f of fs.readdirSync(work)) if (f.startsWith(`norm-${format}-`) && f !== path.basename(norm)) fs.rmSync(path.join(work, f), { force: true });
  }
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", raw, "-i", norm, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", outFile]);
}
lap(`wrote ${outFile}`);
say(`cache ${pruneCache(settings.cacheMaxGB ?? 8).toFixed(1)} GB after pruning (limit ${settings.cacheMaxGB ?? 8})`);
say(`total ${((performance.now() - t0) / 1000).toFixed(1)} s`);
