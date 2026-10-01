// Timing for the LaTeX error shorts, pure data from the narration word timings (cut-local seconds).
// Beats 0..3: error line, log + source, fix, compiles. Scene 4 is the end card. Speech length is the end of
// the last spoken word (the mp3s carry trailing silence), so the cut stays inside 20 to 25 s with the bumpers.
import { ERRORS } from "./data.js";
import { BUMPER } from "../bumper.js";

const spoken = (sc) => (sc.words.length ? sc.words[sc.words.length - 1].end : sc.duration);
const cueOf = (sc, prefix) => {
  const w = sc.words.find((x) => (x.display || x.word).toLowerCase().replace(/[^a-z0-9]/g, "").startsWith(prefix));
  return w ? w.start : 0;
};
export const TYPE_T0 = 0.55;
export const TYPE_CPS = 42;

export function build(id, timing, storyboard) {
  const E = ERRORS[id];
  const START = 0.5, GAP = 0.28;
  const typed = E.log.join("").replace(/\s/g, "").length / TYPE_CPS;
  const hold = { 0: TYPE_T0 + typed + 0.35 - START, 3: 2.0 };
  let t = START;
  const B = [];
  for (const i of [0, 1, 2, 3]) {
    const sc = timing.scenes[i];
    const n = t;
    const e = Math.max(n + spoken(sc) + GAP, n + (hold[i] || 0));
    B.push({ i, n, e, sc });
    t = e;
  }
  const at = (o) => {
    const b = B[o.beat];
    return b.n + (o.cue ? cueOf(b.sc, o.cue) - (o.lead ?? 0.15) : o.dt || 0);
  };
  const ENDs = B[3].e;
  const nEnd = ENDs + 0.25;
  const total = nEnd + spoken(timing.scenes[4]) + 0.3 + BUMPER.xf;
  const stages = E.stages.map((s) => ({ ...s, t: at(s), hiT: s.hi.beat != null ? at(s.hi) : at(s) + 0.45 }));
  const lower = storyboard.scenes.slice(0, 4).map((s, k) => ({ t0: B[k].n + 0.1, t1: B[k].e - 0.12, tag: s.tag, text: s.caption, maxW: 1300 }));
  return {
    E, B, stages, lower, ENDs, total,
    markT: at(E.mark),
    okT: B[3].n + 0.1,
    audio: [...B.map((b) => ({ i: b.i, at: b.n })), { i: 4, at: nEnd }],
    poster: B[2].e - 0.3,
    end: storyboard.end,
  };
}
