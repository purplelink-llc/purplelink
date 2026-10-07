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
  for (const f of ["sting-intro.wav", "sting-outro.wav", "purplelink-logo.png"]) fs.copyFileSync(path.join(assetsDir, f), path.join(brandDir, f));
}
