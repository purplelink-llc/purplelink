// Builds edited (speed-ramped, cleaned) source clips: node build-edit.mjs
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { buildPlan } from "./src/v2plan.js";
import { buildLong } from "./src/v2long.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const DIR = "/Users/benampel/ModernTex-Demo-Clips/";
const SRCS = [DIR + "clip2.mp4", DIR + "clip3-tour.mp4", DIR + "clip4-panels.mp4"];
const cache = path.join(ROOT, ".cache/v2");
fs.mkdirSync(cache, { recursive: true });
const rd = (id) => JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", id, "timing.json"), "utf8"));
// stray recorder click marker on the PDF (clip2 only, before the checker layout appears)
const CLEAN = "drawbox=x=1026:y=259:w=21:h=26:color=white:t=fill:enable='lt(t,20)'";

function edit(segs, out, minDur = 0) {
  const inputs = SRCS.flatMap((s) => ["-i", s]);
  const parts = segs.map((s, i) => {
    const pre = s.f === 0 ? CLEAN + "," : "";
    return `[${s.f}:v]${pre}trim=start=${s.a}:end=${s.b},setpts=(PTS-STARTPTS)/${s.rate},fps=30,scale=1470:922,setsar=1[v${i}]`;
  });
  const total = segs.reduce((a, s) => a + s.dur, 0);
  const pad = Math.max(0, minDur - total);
  const cat = segs.map((_, i) => `[v${i}]`).join("") + `concat=n=${segs.length}:v=1:a=0[c]`;
  const tail = pad > 0 ? `;[c]tpad=stop_mode=clone:stop_duration=${pad.toFixed(3)}[o]` : `;[c]null[o]`;
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...inputs, "-filter_complex", parts.join(";") + ";" + cat + tail, "-map", "[o]", "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30", out]);
  console.log(path.basename(out), "dur", (total + pad).toFixed(2));
}

const which = process.argv[2] || "all";
if (which === "all" || which === "short") {
  const plan = buildPlan(rd("moderntex-promo-v2"));
  const main = [];
  plan.segs.forEach((s, i) => {
    main.push({ ...s, f: 0 });
    if (i === 3) {
      const extra = plan.B2d - (plan.segs[1].dur + plan.segs[2].dur + plan.segs[3].dur);
      if (extra > 0.01) main.push({ f: 0, a: 13.3, b: 13.35, dur: extra, rate: 0.05 / extra });
    }
  });
  edit(main, path.join(cache, "edit.mp4"));
  edit(plan.hero.segs.map((s) => ({ ...s, f: 0 })), path.join(cache, "hero-edit.mp4"), 8.5);
}
if (which === "all" || which === "long") {
  const plan = buildLong(rd("moderntex-promo-v2-long"));
  edit(plan.segs, path.join(cache, "long-edit.mp4"));
  console.log("long total", plan.total.toFixed(2), "chapters", JSON.stringify(plan.chapters));
}
