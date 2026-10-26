// node write-stills-srt.mjs <id> <format> <out.srt>
// SubRip captions for a still-driven product cut (build-stills.mjs), from the same timeline the video renders with:
// narration scene i starts at plan.audio[i].at (product-local), and the product cut starts at bumper.open - bumper.xf.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PRODUCTS } from "./src/products/index.js";
import { BUMPER } from "./src/bumper.js";
import { toSrt } from "./src/rubblefront/plan.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const [id, , out] = process.argv.slice(2);
const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", id, "timing.json"), "utf8"));
const storyboard = JSON.parse(fs.readFileSync(path.join(ROOT, "storyboards", `${id}.json`), "utf8"));
const bumper = { ...BUMPER, ...(storyboard.bumper || {}) };
const plan = PRODUCTS[id].build(timing);
const base = bumper.open - bumper.xf;
const MAX_WORDS = 7, MAX_CUE_S = 3.5, GAP_S = 0.6, END_RX = /[.!?:;]$/;
const cues = [];
for (const a of plan.audio) {
  const words = (timing.scenes[a.i] || {}).words || [];
  let cur = [];
  const flush = () => { if (cur.length) { cues.push({ start: cur[0].t0, end: cur[cur.length - 1].t1, words: cur.map((w) => ({ display: w.text })) }); cur = []; } };
  for (const w of words) {
    const text = (w.display || w.word || "").trim();
    if (!text) continue;
    const t0 = base + a.at + w.start, t1 = base + a.at + Math.max(w.end, w.start);
    if (cur.length && (t0 - cur[cur.length - 1].t1 > GAP_S || cur.length >= MAX_WORDS || t1 - cur[0].t0 > MAX_CUE_S)) flush();
    cur.push({ t0, t1, text });
    if (END_RX.test(text)) flush();
  }
  flush();
}
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, toSrt(cues));
console.log(`${out}: ${cues.length} cues`);
