// Long, chaptered cut: hook (error to fix to build), TikZ designer, table editor, symbols, sidebar, submission check, end.
// Scenes in the long storyboard: 0-2 hook narration, 3-4 TikZ, 5 table, 6 symbols, 7 sidebar, 8 checker, 9 end.
import { buildPlan } from "./v2plan.js";

const cue = (sc, prefix) => {
  const w = sc.words.find((x) => (x.display || x.word).toLowerCase().replace(/[^a-z]/g, "").startsWith(prefix));
  return w ? w.start : 0;
};

export function buildLong(timing) {
  const T = timing.scenes;
  const shortTiming = { scenes: [T[0], T[1], T[2], T[8], T[9]] };
  const p = buildPlan(shortTiming);
  const cut = p.B4s; // hook ends where the short cut's checker begins
  const keys = p.keys.filter((k) => k.t < cut - 0.01);
  const rings = p.rings.filter((r) => r.t0 < cut - 0.01);
  const lower = p.lower.filter((l) => l.t0 < cut - 0.01);
  const audio = [{ i: 0, at: p.n0s }, { i: 1, at: p.n1s }, { i: 2, at: p.n2s }];
  // source edit list: f = 0 clip2, 1 clip3, 2 clip4. dur = output seconds.
  const segs = [];
  const S = (f, a, b, dur) => segs.push({ f, a, b, dur, rate: (b - a) / dur });
  p.segs.slice(0, 4).forEach((s, i) => {
    S(0, s.a, s.b, s.dur);
    if (i === 3) {
      const have = p.segs[1].dur + p.segs[2].dur + p.segs[3].dur;
      const extra = p.B2d - have;
      if (extra > 0.01) S(0, 13.3, 13.35, extra);
    }
  });
  S(0, p.segs[4].a, p.segs[4].b, p.segs[4].dur);

  let c = cut; // chapter start
  const K = (t, fx, fy, s, d, extra = {}) => keys.push({ t, fx, fy, s, d, ...extra });
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text });
  const WIDE = [735, 461];

  // ---- TikZ designer -------------------------------------------------------------------
  {
    const d3 = T[3].duration, d4 = T[4].duration;
    const n3s = c + 0.3;
    const s3 = n3s + d3 + 0.25;
    const n4s = s3 + 0.2;
    const pre = s3 - c;
    S(1, 1.2, 8.0, pre - 1.75);
    S(1, 8.0, 22.0, 1.75);
    S(1, 22.0, 29.0, d4 + 0.6);
    const end = s3 + d4 + 0.6;
    audio.push({ i: 3, at: n3s }, { i: 4, at: n4s });
    K(c + 0.0, ...WIDE, [0.95, 0.8], 1.0);
    K(c + 0.9, 735, 470, [1.15, 1.05], 1.1);
    K(n3s + cue(T[3], "canvas") - 2.4, 720, 400, [1.6, 1.6], 1.0);
    K(c + 5.9, 560, 300, [1.5, 1.45], 1.0);
    K(n3s + cue(T[3], "code") - 0.4, 727, 745, [1.75, 1.5], 1.0, { ay: [0.5, 0.4] });
    K(s3, 940, 660, [2.2, 2.4], 0.9, { ay: [0.45, 0.4] });
    K(s3 + 2.3, 1030, 380, [1.7, 2.2], 1.1, { ax: [0.56, 0.5] });
    R(n3s + cue(T[3], "draw") + 0.2, n3s + cue(T[3], "canvas") + 1.2, [440, 145, 560, 500]);
    R(c + 6.3, n3s + cue(T[3], "connect") + 0.4, [247, 205, 175, 205]);
    R(n3s + cue(T[3], "code") - 0.2, s3 + 0.1, [430, 690, 590, 135]);
    R(s3 + 0.25, s3 + 1.5, [872, 660, 136, 34]);
    rings.push({ t0: s3 + 0.75, t1: s3 + 1.6, ripple: [942, 677] });
    R(s3 + 2.7, end + 0.2, [955, 195, 145, 375]);
    L(n3s + 0.4, s3 - 0.1, "4  TikZ designer", "Draw the figure, get the TikZ code.");
    L(s3 + 0.15, end, "4  TikZ designer", "Insert it and the preview updates.");
    c = end;
  }
  // ---- Table editor ----------------------------------------------------------------------
  {
    const d = T[5].duration;
    const ns = c + 0.3;
    const D = 0.3 + d + 0.45;
    S(1, 30.0, 32.6, 2.6);
    S(1, 32.6, 56.3, 2.0);
    S(1, 56.3, 60.0, D - 4.6);
    audio.push({ i: 5, at: ns });
    K(c + 0.0, 735, 470, [1.15, 1.05], 1.0);
    K(ns + cue(T[5], "add") - 1.0, 520, 340, [1.75, 1.9], 1.0, { ay: [0.5, 0.45] });
    K(c + 4.4, 720, 410, [2.0, 1.9], 1.0);
    K(ns + cue(T[5], "booktabs") - 0.5, 720, 745, [1.8, 1.6], 0.9, { ay: [0.5, 0.4] });
    R(ns + cue(T[5], "add") - 0.1, ns + cue(T[5], "type") + 0.2, [238, 168, 170, 180]);
    R(c + 4.7, ns + cue(T[5], "booktabs") - 0.3, [455, 360, 530, 110]);
    R(ns + cue(T[5], "booktabs") - 0.2, ns + cue(T[5], "insert") + 0.1, [430, 672, 575, 140]);
    R(ns + cue(T[5], "insert") - 0.1, c + D + 0.2, [870, 646, 135, 30]);
    L(ns + 0.3, c + D - 0.1, "5  Table editor", "Fill in a grid, get booktabs LaTeX.");
    c += D;
  }
  // ---- Symbols -----------------------------------------------------------------------------
  {
    const d = T[6].duration;
    const ns = c + 0.3;
    const D = 0.3 + d + 0.5;
    S(2, 11.5, 19.5, D);
    audio.push({ i: 6, at: ns });
    K(c + 0.0, 737, 460, [1.1, 1.5], 1.0, { ay: [0.44, 0.42] });
    K(ns + cue(T[6], "search") - 0.2, 737, 260, [1.75, 2.0], 1.0, { ay: [0.4, 0.36] });
    K(ns + cue(T[6], "operators") - 0.3, 737, 660, [1.75, 2.0], 1.0, { ay: [0.4, 0.36] });
    K(ns + cue(T[6], "with") - 0.3, 737, 470, [1.3, 1.6], 1.0, { ay: [0.4, 0.4] });
    R(ns + cue(T[6], "search") - 0.1, ns + cue(T[6], "greek") + 0.4, [462, 78, 410, 36]);
    R(ns + cue(T[6], "greek") - 0.1, ns + cue(T[6], "operators") - 0.1, [462, 132, 545, 365]);
    R(ns + cue(T[6], "operators") - 0.1, ns + cue(T[6], "with") - 0.1, [462, 505, 545, 320]);
    L(ns + 0.3, c + D - 0.1, "6  Symbols", "Search by name, see the command.");
    c += D;
  }
  // ---- Sidebar: outline, bibliography, revisions ----------------------------------------------
  {
    const d = T[7].duration;
    const ns = c + 0.3;
    const D = 0.3 + d + 0.5;
    const co = ns + cue(T[7], "outline") - 0.15;
    const cb = ns + cue(T[7], "bibliography") - 0.1;
    const cr = ns + cue(T[7], "revision") - 0.1;
    S(2, 1.4, 1.9, co - c);
    S(2, 1.9, 5.03, cb - co);
    S(2, 5.03, 8.5, cr - cb);
    S(2, 8.5, 11.7, c + D - cr);
    audio.push({ i: 7, at: ns });
    K(c + 0.0, 85, 240, [2.4, 3.6], 1.1, { ax: [0.3, 0.5], ay: [0.42, 0.36] });
    R(co, cb, [22, 180, 155, 190]);
    R(co - 0.05, cb, [40, 138, 46, 42]);
    R(cb, cr, [5, 205, 165, 58]);
    R(cb - 0.05, cr, [82, 138, 46, 42]);
    R(cr, c + D + 0.2, [5, 186, 165, 96]);
    R(cr - 0.05, c + D + 0.2, [124, 138, 46, 42]);
    L(ns + 0.3, c + D - 0.1, "7  Sidebar", "Outline, bibliography and revisions.");
    c += D;
  }
  // ---- Submission checker (from the short cut) --------------------------------------------------
  const ck = c;
  p.keys.filter((k) => k.t >= p.B4s - 0.01 && k.t < p.ENDs - 0.3).forEach((k) => keys.push({ ...k, t: k.t - p.B4s + ck }));
  p.rings.filter((r) => r.t0 >= p.B4s - 0.01).forEach((r) => rings.push({ ...r, t0: r.t0 - p.B4s + ck, t1: r.t1 - p.B4s + ck }));
  lower.push({ ...p.lower[3], t0: p.lower[3].t0 - p.B4s + ck, t1: p.lower[3].t1 - p.B4s + ck, tag: "8  Before you submit" });
  S(0, 22.2, 22.2 + p.B4d, p.B4d);
  audio.push({ i: 8, at: ck + 0.1 });
  const ENDs = ck + p.B4d;
  K(ENDs - 0.25, ...WIDE, [0.8, 0.62], 0.9, { ax: [0.5, 0.5] });
  audio.push({ i: 9, at: ENDs + 0.3 });
  const total = ENDs + 0.3 + T[9].duration + 0.7;
  // chapter map for the report
  return { tv0: p.tv0, ENDs, total, keys, rings, lower, audio, segs, chapters: { hook: 0, tikz: cut, ck } };
}
