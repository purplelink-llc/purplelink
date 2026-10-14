// Timeline of the long "File not found" tutorial (pure data; shared by the Remotion composition and the builder).
// Parts, in order: a title card, one cut per cause (the Short's own cut without its end card), a ModernTex card.
import { build } from "./plan.js";

const spoken = (sc) => (sc && sc.words && sc.words.length ? sc.words[sc.words.length - 1].end : (sc ? sc.duration : 0));

export const TITLE_MIN = 9.5; // the five causes are revealed one by one after the first line is spoken
export const CARD_TAIL = 1.6;
// seconds of footage that must play before a clip may end (the built PDF is on screen by 6 s in the package clip and 9 s in the others)
export const CLIP_MIN = { "fnf-long-clip-package": 10.5, "fnf-long-clip-template": 10.5, "fnf-long-clip-input": 10.5 };
export const CUT_TAIL = 0.75; // the cut's panels blur out over 0.6 s after ENDs; the next part starts right after

export function buildLong(parts) {
  let t = 0;
  const segs = [];
  for (const p of parts) {
    let dur;
    let plan = null;
    if (p.kind === "cut") {
      plan = build(p.id, p.timing, p.storyboard);
      dur = plan.ENDs + CUT_TAIL;
    } else if (p.kind === "clip") {
      // real ModernTex footage: at least CLIP_MIN so the fix and the built PDF are on screen, longer if the line is
      dur = Math.max(CLIP_MIN[p.id] ?? 12, spoken(p.timing.scenes[0]) + CARD_TAIL);
    } else if (p.kind === "title") {
      dur = Math.max(TITLE_MIN, spoken(p.timing.scenes[0]) + CARD_TAIL);
    } else {
      dur = spoken(p.timing.scenes[0]) + CARD_TAIL + 0.6;
    }
    segs.push({ ...p, plan, t0: t, dur });
    t += dur;
  }
  return { segs, total: t };
}
