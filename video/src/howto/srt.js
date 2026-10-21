// SubRip captions for a problem-and-fix video, from the same timeline the video renders with (plan.js + bumper.js), so
// the YouTube caption track lines up with the burned-in captions. Pure data, no JSX; used by build-howto.mjs (writes
// <slug>-<format>.srt next to each video) and write-srt.mjs (tests). Ben, 2026-10-21: upload a caption track per video.
// The SRT text itself comes from rubblefront/plan.js toSrt (same cue shape: {start, end, words: [{display}]}).
//
// A word spoken at `w.start` seconds into scene `s` is heard at  (open - xf)  +  s.t0  +  LEAD  +  w.start  in the
// final video: the content starts where the opening bumper crossfades out (Bumper.jsx), each scene sits at its t0
// (plan.js) and its narration starts LEAD into the scene (HowTo.jsx <Sequence from={fr(0.3)}>).
import { buildHowTo, LEAD } from "./plan.js";
import { BUMPER } from "../bumper.js";
import { toSrt } from "../rubblefront/plan.js";

export const MAX_WORDS = 7;        // words per cue
export const MAX_CUE_S = 3.5;      // longest a cue may last
export const GAP_S = 0.6;          // a pause this long starts a new cue
const END_RX = /[.!?:;]$/;         // a cue ends after a word that ends a sentence or clause

// [{start, end, words: [{display}]}] in final-video seconds
export function cues(storyboard, timing, format = "16x9", bumper = BUMPER) {
  const { segs } = buildHowTo(storyboard, timing, format);
  const base = bumper.open - bumper.xf;
  const out = [];
  for (const s of segs) {
    const words = (timing.scenes[s.index] || {}).words || [];
    let cur = [];
    const flush = () => {
      if (!cur.length) return;
      out.push({ start: cur[0].t0, end: cur[cur.length - 1].t1, words: cur.map((w) => ({ display: w.text })) });
      cur = [];
    };
    for (const w of words) {
      const text = (w.display || w.word || "").trim();
      if (!text) continue;
      const t0 = base + s.t0 + LEAD + w.start, t1 = base + s.t0 + LEAD + Math.max(w.end, w.start);
      if (cur.length && (t0 - cur[cur.length - 1].t1 > GAP_S || cur.length >= MAX_WORDS || t1 - cur[0].t0 > MAX_CUE_S)) flush();
      cur.push({ t0, t1, text });
      if (END_RX.test(text)) flush();
    }
    flush();            // cues never run across a scene cut
  }
  // a cue stays up until the next begins (at most 0.8 s extra), never overlapping it
  for (let i = 0; i < out.length; i++) {
    const next = out[i + 1] ? out[i + 1].start : Infinity;
    out[i].end = Math.min(Math.max(out[i].end, out[i].start + 0.3) + 0.8, next - 0.02);
    if (out[i].end <= out[i].start) out[i].end = out[i].start + 0.3;
  }
  return out;
}

export function buildSrt(storyboard, timing, format = "16x9", bumper = BUMPER) {
  return toSrt(cues(storyboard, timing, format, bumper));
}
