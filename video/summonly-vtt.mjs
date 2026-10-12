// node summonly-vtt.mjs summonly-promo  ->  out/<id>/<id>.vtt (captions from the narration timing and the plan)
import fs from "node:fs";
import { PRODUCTS } from "./src/products/index.js";
import { BUMPER } from "./src/bumper.js";
const id = process.argv[2] || "summonly-promo";
const timing = JSON.parse(fs.readFileSync(`.cache/${id}/timing.json`, "utf8"));
const sb = JSON.parse(fs.readFileSync(`storyboards/${id}.json`, "utf8"));
const b = { ...BUMPER, ...(sb.bumper || {}) };
const P0 = b.open - b.xf;
const plan = PRODUCTS[id].build(timing);
const ts = (t) => { const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60; return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${s.toFixed(3).padStart(6, "0")}`; };
let out = "WEBVTT\n\n";
for (const a of plan.audio) {
  const sc = timing.scenes[a.i];
  const words = sc.words;
  const chunks = [];
  let cur = [];
  words.forEach((w, i) => { cur.push(w); if (/[.!?,]$/.test(w.display) || i === words.length - 1) { chunks.push(cur); cur = []; } });
  for (const c of chunks) {
    const t0 = P0 + a.at + c[0].start, t1 = P0 + a.at + c[c.length - 1].end;
    out += `${ts(t0)} --> ${ts(t1)}\n${c.map((w) => w.display).join(" ")}\n\n`;
  }
}
fs.writeFileSync(`out/${id}/${id}.vtt`, out);
console.log(out);
