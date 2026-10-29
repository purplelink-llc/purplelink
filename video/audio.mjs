// Stage narration with loudness normalised to a target (default -16 LUFS integrated), measured per clip with
// ffmpeg loudnorm and corrected with a plain gain so the voice keeps its dynamics. Also copies the brand stings.
import fs from "node:fs";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";

export function measureLufs(file) {
  const r = spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", file, "-af", "loudnorm=print_format=json", "-f", "null", "-"], { encoding: "utf8" });
  const m = (r.stderr + r.stdout).match(/\{[\s\S]*\}/);
  if (!m) throw new Error(`loudnorm measurement failed for ${file}: ${r.stderr.slice(-400)}`);
  const j = JSON.parse(m[0]);
  return { i: parseFloat(j.input_i), tp: parseFloat(j.input_tp) };
}

export function stageNarration(srcDir, dstDir, { target = -16, ceiling = -1.5 } = {}) {
  fs.mkdirSync(dstDir, { recursive: true });
  const notes = [];
  for (const f of fs.readdirSync(srcDir)) {
    if (!/\.mp3$/.test(f)) continue;
    const src = path.join(srcDir, f);
    const dst = path.join(dstDir, f);
    const { i, tp } = measureLufs(src);
    let gain = target - i;
    if (tp + gain > ceiling) gain = ceiling - tp;
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-af", `volume=${gain.toFixed(2)}dB`, "-c:a", "libmp3lame", "-q:a", "2", dst]);
    notes.push(`${f} ${i.toFixed(1)} LUFS ${gain >= 0 ? "+" : ""}${gain.toFixed(1)} dB`);
  }
  return notes;
}

export function stageBrandAudio(assetsDir, brandDir) {
  for (const f of ["sting-intro.wav", "sting-outro.wav", "purplelink-logo.png", "purplelink-lockup-light.png", "purplelink-wordmark-light.png", "purplelink-wordmark-dark.png"]) fs.copyFileSync(path.join(assetsDir, f), path.join(brandDir, f));
}

// Trend-style music bed under a rendered video's audio (video stays stream-copied).
// The bed is synthesised by the TikTokPipeline checkout's shared_media.trends package (numpy only, no samples):
//   python3 -m shared_media.trends.cli bed --seconds N --out bed.wav --video-id ID   (style rotates per ID)
//   python3 -m shared_media.trends.cli mix --in video.mp4 --bed bed.wav --out out.mp4 (sidechain duck, -16 LUFS)
// Both cuts of one video pass the same id, so they share one bed. Never fatal: on any failure, or when the
// checkout is missing or TRENDS_BED=0, the original file is kept and a note is returned.
const TRENDS_ROOT = process.env.TRENDS_ROOT || "/Volumes/Extreme SSD/TikTokPipeline";
const TRENDS_PY = fs.existsSync("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3") ? "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" : "python3";

export function addTrendBed(file, id, { bedDb = -16 } = {}) {
  if (process.env.TRENDS_BED === "0") return "trend bed disabled (TRENDS_BED=0)";
  if (!fs.existsSync(path.join(TRENDS_ROOT, "shared_media", "trends", "cli.py"))) return `trend bed skipped: no ${TRENDS_ROOT}/shared_media/trends`;
  const tmpBed = `${file}.bed.wav`;
  const tmpOut = `${file}.bed.tmp.mp4`;
  try {
    const dur = parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { encoding: "utf8" }));
    const run = (a) => execFileSync(TRENDS_PY, ["-m", "shared_media.trends.cli", ...a], { cwd: TRENDS_ROOT, encoding: "utf8", timeout: 600000 });
    const info = JSON.parse(run(["bed", "--seconds", String(Math.ceil(dur) + 1), "--out", tmpBed, "--video-id", id]).trim().split("\n").at(-1));
    run(["mix", "--in", file, "--bed", tmpBed, "--out", tmpOut, "--bed-db", String(bedDb)]);
    fs.renameSync(tmpOut, file);
    return `trend bed ${info.style.name || info.style.genre} (${info.style.genre} ${info.style.bpm} bpm ${info.style.key} ${info.style.mood})`;
  } catch (e) {
    return `trend bed skipped: ${String(e.message).split("\n")[0]}`;
  } finally {
    fs.rmSync(tmpBed, { force: true });
    fs.rmSync(tmpOut, { force: true });
  }
}
