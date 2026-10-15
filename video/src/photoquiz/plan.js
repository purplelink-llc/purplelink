// Timeline of the weekly photo quiz (shared by src/PhotoQuiz.jsx and build-photoquiz.mjs).
// Narration scenes, in order: intro, then guess + answer for each photo, then outro (timing.scenes follows it).
// A guess lasts its line plus THINK seconds (the countdown runs over the last 3); an answer its line plus a beat.
export const THINK = 3.0;
const spoken = (sc) => (sc && sc.words && sc.words.length ? sc.words[sc.words.length - 1].end : (sc ? sc.duration || 0 : 0));

export function quizLines(spec) {
  const ord = ["one", "two", "three", "four", "five", "six", "seven"];
  const the = (c) => (/^(United|Netherlands|Czech|Philippines|Bahamas)/.test(c) ? `the ${c}` : c);
  const lines = [`Where in the world? ${spec.items.length} travel photos. Guess each one.`];
  spec.items.forEach((it, i) => {
    lines.push(`Number ${ord[i] || i + 1}. Where is this?`);
    lines.push(`It's ${it.place}, in ${the(it.country)}.`);   // the caption stays on screen, unread
  });
  lines.push(`How many did you get? Comment your score out of ${spec.items.length}.`);
  return lines;
}

export function buildQuiz(spec, timing) {
  const total = spec.items.length;
  const segs = [];
  let t = 0;
  const push = (kind, k, extra, min, pad) => {
    const tm = timing.scenes[k] || {};
    const dur = Math.max(min, 0.2 + spoken(tm) + pad);
    segs.push({ kind, t0: t, dur, audio: tm.audio || null, total, url: spec.url, ...extra });
    t += dur;
  };
  push("intro", 0, {}, 2.6, 0.4);
  spec.items.forEach((item, i) => {
    push("guess", 1 + 2 * i, { item, index: i }, 5.0, THINK);
    push("answer", 2 + 2 * i, { item, index: i }, 4.0, 1.2);
    const g = segs[segs.length - 2], a = segs[segs.length - 1];
    g.next = a.dur; a.prev = g.dur;
  });
  push("outro", 1 + 2 * total, {}, 4.0, 1.4);
  return { segs, total: t };
}
