// Objective quality guard for the benchmark: SSIM and PSNR of a candidate render against a reference render of the same frames.
import { spawnSync } from "node:child_process";

export function compare(candidate, reference) {
  const run = (filter) => spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", candidate, "-i", reference, "-lavfi", filter, "-f", "null", "-"], { encoding: "utf8" }).stderr || ""; // ffmpeg prints the scores on stderr
  const s = run("[0:v][1:v]ssim").match(/All:([0-9.]+)/);
  const p = run("[0:v][1:v]psnr").match(/average:([0-9.]+|inf)/);
  return { ssim: s ? +s[1] : null, psnr: p ? (p[1] === "inf" ? 99 : +p[1]) : null };
}
