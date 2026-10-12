// node panely-shots/make-vtt.mjs <id> <out.vtt>   WebVTT captions from the narration text and the plan's start times.
// Cue times are final-timeline seconds: product-local time plus the bumper lead-in (open - xf).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PRODUCTS } from "../src/products/index.js";
import { BUMPER } from "../src/bumper.js";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const [id, out] = process.argv.slice(2);
const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", id, "timing.json"), "utf8"));
const sb = JSON.parse(fs.readFileSync(path.join(ROOT, "storyboards", `${id}.json`), "utf8"));
const b = { ...BUMPER, ...(sb.bumper || {}) };
const P0 = b.open - b.xf;
const plan = PRODUCTS[id].build(timing);
const ts = (t) => { const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t - h * 3600 - m * 60; return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${s.toFixed(3).padStart(6, "0")}`; };
let vtt = "WEBVTT\n\n";
plan.audio.forEach((a, n) => {
  const start = P0 + a.at, end = start + timing.scenes[a.i].duration;
  vtt += `${n + 1}\n${ts(start)} --> ${ts(end)}\n${sb.scenes[a.i].narration}\n\n`;
});
fs.writeFileSync(out, vtt);
console.log(vtt);
