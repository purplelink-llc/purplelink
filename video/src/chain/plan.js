// Timeline for a chain video, pure data from the narration word timings (cut-local seconds).
// Scene 0 is the hook, scenes 1..L reveal one link each, the last scene is the finale (links count and call to action).
import { BUMPER } from "../bumper.js";

const spoken = (sc) => (sc.words.length ? sc.words[sc.words.length - 1].end : sc.duration);

const norm = (w) => (w.display || w.word).toLowerCase().replace(/[^a-z0-9]/g, "");
// Start time (scene-local seconds) of the first word that starts with `prefix`, searching from word index `from`.
export function cue(sc, prefix, from = 0, fallback = 0) {
  const p = prefix.toLowerCase().replace(/[^a-z0-9]/g, "");
  for (let i = from; i < sc.words.length; i++) if (norm(sc.words[i]).startsWith(p)) return sc.words[i].start;
  return fallback;
}

export function build(chain, timing) {
  const START = 0.45, GAP = 0.3;
  let t = START;
  const S = timing.scenes.map((sc, i) => {
    const n = t;
    const e = n + Math.max(spoken(sc) + 0.15, 1.7) + GAP;
    t = e;
    return { i, n, e, sc, kind: i === 0 ? "hook" : i === timing.scenes.length - 1 ? "end" : "hop", hop: i - 1 };
  });
  const end = S[S.length - 1];
  const total = end.n + Math.max(spoken(end.sc) + 0.15, 1.7) + 0.5 + BUMPER.xf;
  // when the hook's lines appear, tied to the words that name them (the voice leads, the picture follows within a beat)
  const h0 = timing.scenes[0], a0 = chain.players[0].name.split(" ")[0], b0 = chain.players.at(-1).name.split(" ")[0];
  const ai = Math.max(0, h0.words.findIndex((w) => norm(w).startsWith(a0.toLowerCase().replace(/[^a-z0-9]/g, ""))));
  const aT = cue(h0, a0, 0, 0.3);
  const bT = cue(h0, b0, ai + 1, 1.6);
  const pillT = cue(h0, chain.kind === "daily" ? "shortest" : "through", 0, bT + 0.9);
  const hook = { a: START + aT - 0.12, conn: START + Math.max(aT + 0.5, bT - 0.55), b: START + bT - 0.12, pill: START + pillT - 0.1 };
  return { S, total, hop0: S[1] ? S[1].n : START, endAt: end.n, links: chain.players.length - 1, hook };
}
