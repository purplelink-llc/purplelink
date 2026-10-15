// Timeline of a problem-and-fix video (pure data; shared by src/HowTo.jsx and build-howto.mjs).
// The 16:9 cut plays every scene; the 9:16 Short plays only scenes marked "short". A scene lasts its narration
// (spoken from 0.3 s) plus TAIL, and never less than its type's minimum, so typed terminal text can be read.
export const LEAD = 0.3;
export const TAIL = 0.9;
export const MIN = { hook: 3.5, symptom: 4.5, cause: 4, steps: 5.5, check: 4.5, app: 6 };

const spokenOf = (sc) => (sc && sc.words && sc.words.length ? sc.words[sc.words.length - 1].end : (sc ? sc.duration || 0 : 0));

export function buildHowTo(storyboard, timing, format = "16x9") {
  const vertical = format === "9x16";
  let t = 0;
  const segs = [];
  storyboard.scenes.forEach((scene, i) => {
    if (vertical && !scene.short) return;
    const tm = timing.scenes[i] || {};
    const spoken = spokenOf(tm);
    const dur = Math.max(MIN[scene.type] ?? 4, LEAD + spoken + TAIL);
    segs.push({ index: i, scene, spoken, audio: tm.audio || null, t0: t, dur });
    t += dur;
  });
  return { segs, total: t };
}
