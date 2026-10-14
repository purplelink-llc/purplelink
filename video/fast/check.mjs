#!/usr/bin/env node
// QA kit: one command replaces hand-pulling frames for review rounds.
//   node fast/check.mjs <video.mp4> [--out dir] [--sb storyboard.json --format 16x9] [--adapter rubblefront4]
// Writes: contact.jpg (1 fps sheet), phone-NN.jpg (480 px wide grabs, one per scene when a storyboard is given),
//         micro.jpg (one frame per scene, mid-scene: the "does every scene read without sound" test),
//         report.json + report.txt (duration, size, codecs, integrated loudness, true peak, black/frozen frame warnings).
import fs from "node:fs";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const video = path.resolve(args.find((a) => /\.(mp4|mov)$/.test(a)));
const out = path.resolve(opt("out", path.join(path.dirname(video), `qa-${path.basename(video, path.extname(video))}`)));
fs.mkdirSync(out, { recursive: true });
const ff = (a) => spawnSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", ...a], { encoding: "utf8" });

const probe = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", video], { encoding: "utf8" }));
const v = probe.streams.find((s) => s.codec_type === "video"), a = probe.streams.find((s) => s.codec_type === "audio");
const dur = Number(probe.format.duration);

// 1 fps contact sheet (10 columns)
const rows = Math.ceil(Math.ceil(dur) / 10);
ff(["-i", video, "-vf", `fps=1,scale=192:-1,tile=10x${rows}:padding=4:color=black`, "-frames:v", "1", "-q:v", "3", path.join(out, "contact.jpg")]);

// scene grabs
let scenes = [];
const sbArg = opt("sb");
if (sbArg) {
  const adapter = await import(`./adapters/${opt("adapter", "rubblefront4")}.mjs`);
  const prep = adapter.prepare({ sbPath: sbArg, format: opt("format", "16x9") });
  scenes = prep.plan.shots.map((s) => ({ i: s.i, type: s.type, start: s.start, dur: s.dur }));
}
if (!scenes.length) for (let t = 0; t < dur; t += 3) scenes.push({ i: scenes.length, type: "?", start: t, dur: 3 });
for (const s of scenes) ff(["-ss", String(Math.min(dur - 0.1, s.start + s.dur / 2)), "-i", video, "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "3", path.join(out, `phone-${String(s.i).padStart(2, "0")}.jpg`)]);
// microtrailer: one mid-scene frame per scene tiled, so a reviewer sees the whole story in one image
const cols = Math.min(6, scenes.length);
ff(["-i", video, "-vf", `select='${scenes.map((s) => `lt(abs(t-${(s.start + s.dur / 2).toFixed(3)}),0.034)`).join("+")}',scale=320:-1,tile=${cols}x${Math.ceil(scenes.length / cols)}:padding=4:color=black`, "-fps_mode", "vfr", "-frames:v", "1", "-q:v", "3", path.join(out, "micro.jpg")]);

// loudness, black and freeze detection
const ln = spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", video, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-vn", "-f", "null", "-"], { encoding: "utf8" }).stderr;
const m = ln.match(/\{[\s\S]*?\}/);
const loud = m ? JSON.parse(m[0]) : null;
const vd = spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", video, "-vf", "blackdetect=d=0.2:pix_th=0.05,freezedetect=n=0.003:d=1.0", "-an", "-f", "null", "-"], { encoding: "utf8" }).stderr;
const black = [...vd.matchAll(/black_start:([\d.]+) black_end:([\d.]+)/g)].map((x) => [Number(x[1]), Number(x[2])]);
const freeze = [...vd.matchAll(/freeze_start: ([\d.]+)/g)].map((x) => Number(x[1]));

const report = {
  file: video, seconds: +dur.toFixed(2), mb: +(Number(probe.format.size) / 1e6).toFixed(2), size: `${v.width}x${v.height}`, fps: v.avg_frame_rate, vcodec: v.codec_name, vbitrate_mbps: +(Number(v.bit_rate || 0) / 1e6).toFixed(2),
  acodec: a && a.codec_name, lufs: loud && Number(loud.input_i), true_peak_db: loud && Number(loud.input_tp),
  black_spans: black, frozen_from: freeze, scenes: scenes.length,
  warnings: [],
};
if (report.lufs != null && Math.abs(report.lufs + 14) > 1.5) report.warnings.push(`loudness ${report.lufs} LUFS (target -14)`);
if (report.true_peak_db != null && report.true_peak_db > -1) report.warnings.push(`true peak ${report.true_peak_db} dB`);
if (black.some(([s, e]) => s > 0.3 && e < dur - 0.3)) report.warnings.push("black frames in the middle of the video");
if (freeze.length > 3) report.warnings.push(`${freeze.length} frozen stretches (check slow-motion and holds are intended)`);
fs.writeFileSync(path.join(out, "report.json"), JSON.stringify(report, null, 1));
const txt = [`${path.basename(video)}  ${report.seconds}s  ${report.size}@${report.fps}  ${report.vcodec} ${report.vbitrate_mbps} Mbps  ${report.mb} MB`, `audio ${report.acodec}  ${report.lufs} LUFS  peak ${report.true_peak_db} dB`, `black spans ${JSON.stringify(black)}  freeze starts ${JSON.stringify(freeze)}`, report.warnings.length ? `WARN: ${report.warnings.join("; ")}` : "no warnings", `images in ${out}`].join("\n");
fs.writeFileSync(path.join(out, "report.txt"), txt + "\n");
console.log(txt);
