// Timeline of a problem-and-fix video (pure data; shared by src/HowTo.jsx and build-howto.mjs).
// The 16:9 cut plays every scene; the 9:16 Short plays only scenes marked "short". A scene lasts its narration
// (spoken from 0.3 s) plus TAIL, and never less than its type's minimum, so typed terminal text can be read.
export const LEAD = 0.3;
export const TAIL = 0.9;
export const MIN = { hook: 3.5, symptom: 4.5, cause: 4, steps: 5.5, check: 4.5, app: 6 };

// Visual cues (a line starting to type, a title, a step reveal) start CUE_LEAD seconds before the spoken word they
// match, so the picture reads as in sync with the voice (2 to 3 frames at 30 fps).
export const CUE_LEAD = 0.08;
// Slow scale drift during holds: 1.000 up to 1.000 + DRIFT over the hold, eased.
export const DRIFT = 0.015;

const spokenOf = (sc) => (sc && sc.words && sc.words.length ? sc.words[sc.words.length - 1].end : (sc ? sc.duration || 0 : 0));

const STOP = new Set("the and for with that this you are not from into then what one can your has have its all but out use run will they them when just more also how why".split(" "));
const toks = (s) => (String(s).toLowerCase().match(/[a-z0-9]+/g) || []).filter((w) => w.length >= 3 && !STOP.has(w));
const norm = (w) => String(w).toLowerCase().replace(/[^a-z0-9]/g, "");

// Start (seconds in the scene, minus CUE_LEAD) of the first spoken word at or after word index `from` that shares a
// token with `text`. Returns { at, idx } or null.
export function anchor(text, words, from = 0, tokens = toks(text)) {
  const set = new Set(tokens);
  for (let i = from; i < words.length; i++) {
    if (set.has(norm(words[i].word))) return { at: Math.max(0.05, LEAD + words[i].start - CUE_LEAD), idx: i };
  }
  return null;
}

const typeLen = (l) => (l.startsWith("$ ") ? Math.min(2.2, Math.max(0.4, l.length / 28)) : Math.min(0.8, Math.max(0.2, l.length / 60)));

// Cue times for one scene, in seconds from the scene's start. `words` are the scene's narration word timings
// (start relative to the audio, which begins at LEAD); `dur` is the scene length. Without word timings the cues fall
// back to fixed delays. `hold` is when the last entrance has finished: the drift runs from there to the scene end.
export function sceneCues(sc, words, dur) {
  const have = words && words.length;
  const first = have ? Math.max(0.05, LEAD + words[0].start - CUE_LEAD) : 0.25;
  const lastEnd = have ? LEAD + words[words.length - 1].end : dur;
  if (sc.type === "hook") {
    const sub = sc.sub && have ? anchor(sc.sub, words) : null;
    const title = Math.max(first, 0.2);
    return fin({ kicker: 0.1, title, sub: Math.max(sub ? sub.at : title + 0.5, title + 0.4) }, 0.7, dur);
  }
  if (sc.type === "cause") return fin({ text: first }, 0.7, dur);
  if (sc.type === "app") {
    const name = Math.max(0.1, have ? (anchor(sc.name, words) || { at: first }).at : 0.1);
    let from = 0;
    const l = have ? anchor(sc.line, words) : null;
    const line = Math.max(l ? l.at : name + 0.4, name + 0.3);
    if (l) from = l.idx;
    const u = have ? anchor(sc.url || sc.name, words, from) : null;
    const url = Math.max(u ? u.at : line + 0.6, line + 0.5);
    return fin({ name, line, img: line + 0.1, url }, 0.9, dur);
  }
  // symptom, steps, check: terminal lines
  const lines = sc.lines || [];
  const total = lines.reduce((n, l) => n + l.length, 0) || 1;
  const span = Math.max(1, (lastEnd - first) * 0.75);
  let cum = 0;
  let from = 0;
  const plan = lines.map((l, li) => {
    const guess = first + (cum / total) * span;
    cum += l.length;
    let at = guess;
    if (have && li > 0) {
      const key = l.startsWith("$ ") ? l.slice(2).split(/\s+/)[0] : l;
      const a = anchor(key, words, from, toks(key));
      if (a && Math.abs(a.at - guess) <= 2) { at = a.at; from = a.idx + 1; } // a far-off match is probably the wrong word
    }
    return { s: at, d: typeLen(l) };
  });
  let t = plan.length ? Math.max(plan[0].s, 0.2) : 0;
  plan.forEach((p, i) => {
    p.s = Math.max(i === 0 ? t : p.s, i === 0 ? 0 : plan[i - 1].s + plan[i - 1].d + 0.05);
  });
  const budgetEnd = Math.max(1.2, dur - 0.6);
  const over = plan.length ? plan[plan.length - 1].s + plan[plan.length - 1].d - budgetEnd : 0;
  if (over > 0) { // squeeze: pull the schedule earlier proportionally, keep the order
    const k = Math.max(0.4, (budgetEnd - plan[0].s) / (budgetEnd - plan[0].s + over));
    plan.forEach((p) => { p.s = plan[0].s + (p.s - plan[0].s) * k; p.d *= k; });
  }
  const end = plan.length ? plan[plan.length - 1].s + plan[plan.length - 1].d : first;
  const ok = sc.type === "check" ? Math.max(end + 0.15, have ? (anchor(sc.ok || "fixed", words) || { at: 0 }).at : 0) : null;
  const ui = sc.ui ? Math.max(end, have ? (anchor(sc.ui, words) || { at: end }).at : end) : null;
  const c = { lines: plan, ok, ui };
  c.hold = Math.min(dur - 1, Math.max(end + 0.1, (ok == null ? 0 : ok + 0.6), (ui == null ? 0 : ui + 0.6)));
  return c;
}

// Adds `hold`: the time the last entrance (starting at the latest of the cue times, lasting `len`) completes.
function fin(c, len, dur) {
  const times = Object.values(c).filter((v) => typeof v === "number").map((v) => v + len);
  c.hold = Math.min(dur - 1, Math.max(...times, 0.5));
  return c;
}

export function buildHowTo(storyboard, timing, format = "16x9") {
  const vertical = format === "9x16";
  let t = 0;
  const segs = [];
  storyboard.scenes.forEach((scene, i) => {
    if (vertical && !scene.short) return;
    const tm = timing.scenes[i] || {};
    const spoken = spokenOf(tm);
    const dur = Math.max(MIN[scene.type] ?? 4, LEAD + spoken + TAIL);
    segs.push({ index: i, scene, spoken, audio: tm.audio || null, t0: t, dur, cues: sceneCues(scene, tm.words, dur) });
    t += dur;
  });
  return { segs, total: t };
}
