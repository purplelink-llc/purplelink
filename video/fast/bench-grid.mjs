#!/usr/bin/env node
// Grid search over render options. One-factor-at-a-time sweeps around a baseline, then optional combined cells.
//   node fast/bench-grid.mjs --grid fast/grids/stage1.json --sb storyboards/rubblefront-v4-30s.json --format 16x9 --frames 300-449 --reps 2
// Each cell runs in a fresh process, waits for a quiet machine, and is compared with the baseline output (SSIM, PSNR).
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { waitQuiet, loadavg1 } from "./cache.mjs";
import { compare } from "./quality.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const grid = JSON.parse(fs.readFileSync(path.resolve(opt("grid")), "utf8"));
const base = { adapter: opt("adapter", grid.adapter || "rubblefront4"), sb: opt("sb"), format: opt("format", "16x9"), frames: opt("frames"), ...grid.baseline };
const reps = Number(opt("reps", grid.reps || 2));
const quietMax = Number(opt("quiet", 3.5));
const only = opt("only");

const cells = [{ name: "baseline", ...base }];
for (const [factor, values] of Object.entries(grid.sweeps || {})) for (const v of values) {
  const label = `${factor}=${typeof v === "object" ? JSON.stringify(v) : v}`;
  cells.push(typeof v === "object" && v !== null && !Array.isArray(v) ? { name: label, ...base, ...v } : { name: label, ...base, [factor]: v });
}
for (const c of grid.combined || []) cells.push({ ...base, ...c });
const run = only ? cells.filter((c) => c.name === "baseline" || only.split(",").includes(c.name)) : cells;

const waitS = Number(opt("wait", 240));
// Round-robin: every cell gets one rep per round, so slow drift in machine load hits all cells alike.
const samples = new Map(run.map((c) => [c.name, []]));
for (let r = 0; r < reps; r++) {
  for (const cell of run) {
    const load = await waitQuiet(quietMax, waitS);
    const t0 = Date.now();
    const p = spawnSync("node", [path.join(HERE, "bench-cell.mjs"), JSON.stringify(cell)], { encoding: "utf8", env: { ...process.env, ...(cell.env || {}) }, maxBuffer: 1 << 26, cwd: path.resolve(HERE, "..") });
    const line = (p.stdout || "").split("\n").find((l) => l.startsWith("RESULT "));
    if (!line) { console.log(`  ${cell.name} rep${r + 1}: FAILED ${(p.stderr || p.stdout || "").slice(-300).replace(/\n/g, " ")}`); samples.get(cell.name).push({ failed: true }); continue; }
    const res = JSON.parse(line.slice(7));
    res.quiet_load = +load.toFixed(2);
    samples.get(cell.name).push(res);
    console.log(`  ${cell.name} rep${r + 1}: render ${res.render_s}s (${res.fps} fps) bundle ${res.bundle_s}s load ${res.load_before}->${res.load_after} ${((Date.now() - t0) / 1000).toFixed(0)}s wall`);
  }
}
const results = [];
let ref = null;
for (const cell of run) {
  const ok = samples.get(cell.name).filter((x) => !x.failed);
  if (!ok.length) { results.push({ cell, failed: true }); continue; }
  ok.sort((a, b) => a.render_s - b.render_s);
  const med = ok[Math.floor((ok.length - 1) / 2)];
  const q = (cell.scale ?? 1) === (base.scale ?? 1) ? (ref ? compare(med.out, ref) : { ssim: 1, psnr: 99 }) : { ssim: null, psnr: null };
  if (cell.name === "baseline") ref = med.out;
  results.push({ cell, reps: ok.map((x) => x.render_s), median_render_s: med.render_s, fps: med.fps, bundle_s: med.bundle_s, proxy_s: med.proxy_s, out_mb: med.out_mb, ssim: q.ssim, psnr: q.psnr, load_max: Math.max(...ok.map((x) => x.load_after)), out: med.out });
}
// every cell output except the baseline reference is only needed for the SSIM compare above
for (const r of results) if (r.out && r.cell.name !== "baseline") fs.rmSync(r.out, { force: true });
const b = results.find((r) => r.cell.name === "baseline");
const rows = results.filter((r) => !r.failed).map((r) => ({ ...r, speedup: b ? +(b.median_render_s / r.median_render_s).toFixed(2) : null }));
rows.sort((a, c) => a.median_render_s - c.median_render_s);
console.log("\nname | render_s (reps) | fps | speedup | bundle_s | out_MB | SSIM | PSNR | load_max");
for (const r of rows) console.log(`${r.cell.name} | ${r.median_render_s} (${r.reps.join(", ")}) | ${r.fps} | x${r.speedup} | ${r.bundle_s} | ${r.out_mb} | ${r.ssim ?? "-"} | ${r.psnr ?? "-"} | ${r.load_max}`);
const outDir = path.join(HERE, "results"); fs.mkdirSync(outDir, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const outFile = path.join(outDir, `${stamp}-${base.format}-${path.basename(opt("grid"), ".json")}.json`);
fs.writeFileSync(outFile, JSON.stringify({ when: new Date().toISOString(), host: os.hostname(), cpu: os.cpus()[0].model, cores: os.cpus().length, ramGB: Math.round(os.totalmem() / 1073741824), base, reps, results: results.map(({ out, ...r }) => r) }, null, 1));
if (ref) fs.rmSync(ref, { force: true });
console.log(`\nresults -> ${outFile}`);
