#!/usr/bin/env node
// Builds the review bundle that critics (agents or people) judge a trailer from.
//   node fast/critic-bundle.mjs <video.mp4> --sb <storyboard.json> --format 16x9|9x16 --kind main|30s|vertical --adapter rubblefront5 --out <dir>
// Critics cannot watch video, so the bundle turns it into things they can read and look at:
//   contact.jpg (1 fps), micro6.jpg (first 6 s at 4 frames per second: the Steam microtrailer loop), scenes.jpg (one frame per scene),
//   phone-NN.jpg (480 px grabs), waveform.png (audio shape), scenes.json (shot table with cards), audio-events.json (sfx times, music cues,
//   loudness per second), gates.json (objective pass/fail checks, written by code, not by a model), report.txt (summary).
import fs from "node:fs";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const video = path.resolve(args.find((a) => /\.(mp4|mov)$/.test(a)));
const out = path.resolve(opt("out", path.join(path.dirname(video), `critic-${path.basename(video, path.extname(video))}`)));
const kind = opt("kind", "main");
const format = opt("format", "16x9");
fs.mkdirSync(out, { recursive: true });
const ff = (a) => spawnSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", ...a], { encoding: "utf8" });

// 1. the existing QA kit (contact sheet, phone grabs, loudness, black and freeze)
const sbArg = opt("sb");
const checkArgs = [path.join(HERE, "check.mjs"), video, "--out", out, "--format", format];
if (sbArg) checkArgs.push("--sb", sbArg, "--adapter", opt("adapter", "rubblefront4"));
execFileSync("node", checkArgs, { stdio: "ignore" });
const qa = JSON.parse(fs.readFileSync(path.join(out, "report.json"), "utf8"));

const probe = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", video], { encoding: "utf8" }));
const v = probe.streams.find((s) => s.codec_type === "video"), a = probe.streams.find((s) => s.codec_type === "audio");
const dur = Number(probe.format.duration);

// 2. the first six seconds as the muted Steam microtrailer loop: 24 frames, 4 per second
ff(["-i", video, "-t", "6", "-vf", `fps=4,scale=${format === "9x16" ? 180 : 320}:-1,tile=6x4:padding=4:color=black`, "-frames:v", "1", "-q:v", "3", path.join(out, "micro6.jpg")]);

// 3. audio you can look at: waveform picture and loudness per second
ff(["-i", video, "-filter_complex", "showwavespic=s=1600x240:colors=0x2fd0e0", "-frames:v", "1", path.join(out, "waveform.png")]);
const eb = spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", video, "-af", "ebur128=framelog=info", "-vn", "-f", "null", "-"], { encoding: "utf8" }).stderr || "";
const mBySec = {};
for (const m of eb.matchAll(/t:\s*([\d.]+)\s+TARGET:[^\n]*?M:\s*(-?[\d.]+|-inf)/g)) { const s = Math.floor(Number(m[1])); const val = m[2] === "-inf" ? -70 : Number(m[2]); mBySec[s] = Math.max(mBySec[s] ?? -70, val); }
const loudnessBySecond = Object.keys(mBySec).map(Number).sort((x, y) => x - y).map((s) => [s, mBySec[s]]);

// 4. shot table and cards, from the storyboard plan (when given)
let scenes = [], sfx = [], music = [], logoSeconds = 0, plan = null;
if (sbArg) {
  const adapter = await import(`./adapters/${opt("adapter", "rubblefront4")}.mjs`);
  const prep = adapter.prepare({ sbPath: sbArg, format });
  plan = prep.plan;
  scenes = plan.shots.map((s) => ({
    i: s.i, type: s.type, start: +s.start.toFixed(2), dur: +s.dur.toFixed(2), clip: s.clip || s.vclip || null,
    cards: plan.cards.filter((c) => c.scene === s.i).map((c) => c.text),
    flash: (s.flash || []).length, shake: (s.shake || []).length, slow: (s.spans || []).some((x) => x.rate && x.rate < 1),
    logo: !!s.logo,
  }));
  sfx = plan.sfx.map((x) => ({ t: +x.t.toFixed(2), kind: x.kind, gain_db: x.gain_db }));
  music = (prep.sb.music || []).map((m) => ({ file: m.file, at: m.at ?? m.t ?? 0 }));
  logoSeconds = plan.shots.filter((s) => s.logo).reduce((acc, s) => acc + (s.logo.dur ?? 0), 0);
  // one frame per scene (mid-scene), tiled: the whole story in one image
  const cols = Math.min(6, scenes.length);
  const sel = scenes.map((s) => `lt(abs(t-${(s.start + s.dur / 2).toFixed(3)}),0.034)`).join("+");
  ff(["-i", video, "-vf", `select='${sel}',scale=${format === "9x16" ? 180 : 320}:-1,tile=${cols}x${Math.ceil(scenes.length / cols)}:padding=4:color=black`, "-fps_mode", "vfr", "-frames:v", "1", "-q:v", "3", path.join(out, "scenes.jpg")]);
}
fs.writeFileSync(path.join(out, "scenes.json"), JSON.stringify(scenes, null, 1));
fs.writeFileSync(path.join(out, "audio-events.json"), JSON.stringify({ sfx, music, loudnessBySecond }, null, 1));

// 5. objective gates, decided by code
const range = { main: [60, 90], "30s": [25, 35], vertical: [10, 40] }[kind] || [10, 90];
const lens = scenes.filter((s) => s.type === "clip").map((s) => s.dur);
const q = Math.max(1, Math.floor(lens.length / 4));
const mean = (xs) => (xs.length ? xs.reduce((x, y) => x + y, 0) / xs.length : null);
const firstQ = mean(lens.slice(0, q)), lastQ = mean(lens.slice(-q));
const hitTimes = sfx.filter((x) => /hit|boom|slam/.test(x.kind)).map((x) => x.t);
const firstSfx = hitTimes.length ? Math.min(...hitTimes) : null;
const bitrateKbps = Math.round(Number(probe.format.bit_rate || 0) / 1000);
const gates = [];
const gate = (id, pass, detail, blocking = true) => gates.push({ id, pass: !!pass, blocking, detail });
gate("duration", dur >= range[0] && dur <= range[1], `${dur.toFixed(1)} s, allowed ${range[0]} to ${range[1]} s for ${kind}`);
if (format === "16x9") {
  gate("valve_resolution", v.width <= 1920 && v.height <= 1080 && v.width / v.height > 1.7, `${v.width}x${v.height}`);
  gate("valve_fps", ["30/1", "60/1", "30000/1001", "60000/1001"].includes(v.avg_frame_rate), v.avg_frame_rate);
  gate("valve_bitrate", bitrateKbps >= 5000, `${bitrateKbps} kbps, Valve asks for 5000+`);
  gate("valve_codecs", v.codec_name === "h264" && a && a.codec_name === "aac", `${v.codec_name}/${a && a.codec_name}`);
  gate("valve_audio_rate", a && ["44100", "48000"].includes(String(a.sample_rate)), a && a.sample_rate);
} else {
  gate("vertical_size", v.width === 1080 && v.height === 1920, `${v.width}x${v.height}`);
}
gate("loudness", qa.lufs != null && Math.abs(qa.lufs + 14) <= 1.5, `${qa.lufs} LUFS, target -14 +/- 1.5`, false);
gate("true_peak", qa.true_peak_db != null && qa.true_peak_db <= -1, `${qa.true_peak_db} dB, must be at or below -1`, false);
gate("no_black_in_body", !(qa.black_spans || []).some(([s, e]) => s > 0.3 && e < dur - 0.3), JSON.stringify(qa.black_spans));
if (scenes.length) {
  gate("hook_sound_early", firstSfx != null && firstSfx <= 5, `first hit, boom or slam sound at ${firstSfx} s, must be by 5 s`);
  gate("shots_accelerate", firstQ != null && lastQ != null && lastQ <= 0.75 * firstQ, `mean clip length first quarter ${firstQ && firstQ.toFixed(2)} s, last quarter ${lastQ && lastQ.toFixed(2)} s`, false);
  gate("logo_time", logoSeconds <= 3, `${logoSeconds.toFixed(1)} s of logo slam, at most 3`, false);
  gate("starts_on_gameplay", scenes[0].type === "clip", `first scene type ${scenes[0].type}`);
}
fs.writeFileSync(path.join(out, "gates.json"), JSON.stringify({ video, kind, format, gates, blockingFailures: gates.filter((g) => !g.pass && g.blocking).map((g) => g.id) }, null, 1));

const failed = gates.filter((g) => !g.pass);
const txt = [`${path.basename(video)}  ${kind}  ${dur.toFixed(1)}s  ${v.width}x${v.height}@${v.avg_frame_rate}  ${bitrateKbps} kbps`, `objective gates: ${gates.length - failed.length}/${gates.length} pass`, ...failed.map((g) => `  FAIL${g.blocking ? " (blocking)" : ""} ${g.id}: ${g.detail}`), `bundle: ${out}`].join("\n");
fs.writeFileSync(path.join(out, "bundle-report.txt"), txt + "\n");
console.log(txt);
