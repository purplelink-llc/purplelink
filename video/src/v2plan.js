// Pure plan for the v2 promo: beat timings (seconds), source-clip edit list, camera keys, rings, lower thirds.
// Shared by build-v2.mjs (ffmpeg edit) and the Remotion composition.

export const SRC_W = 1470;
export const SRC_H = 922;

export function buildPlan(timing) {
  const nd = (i) => timing.scenes[i].duration;
  const tv0 = 1.2; // video (and window) enters
  const n0s = 1.7;
  const B1s = tv0;
  const B2s = n0s + nd(0) + 0.2;
  const n1s = B2s + 2.0;
  const B2d = 4.3;
  const B3s = B2s + B2d;
  const n2s = B3s + 0.05;
  const B3d = nd(2) + 0.15;
  const B4s = B3s + B3d;
  const n3s = B4s + 0.1;
  const B4d = nd(3) + 0.4;
  const ENDs = B4s + B4d;
  const n4s = ENDs + 0.3;
  const total = n4s + nd(4) + 0.7;

  // Edited source: segments of the real capture with speed ramps. dur = output seconds.
  const rate3 = 0.6;
  const seg = (a, b, rate) => ({ a, b, rate, dur: (b - a) / rate });
  const segs = [
    seg(1.3, 7.0, 1.0), // B1: error stays flagged (5.7 s window)
    seg(7.0, 9.4, 0.9), // fix, slowed on the key moment
    seg(9.4, 12.1, 4.5), // dead time skipped
    seg(12.1, 13.3, 1.2), // Full build
    seg(13.3, 13.3 + (B3d) * rate3, rate3), // resolved citations, slow
    seg(22.2, 22.2 + B4d, 1.0), // submission checker opens and holds
  ];
  // B1 seg must fill tv0..B2s exactly: adjust its rate
  segs[0] = { a: 1.3, b: 7.0, rate: 5.7 / (B2s - B1s), dur: B2s - B1s };
  // B2 ramps sum to 2.667 + 0.6 + 1.0 = 4.267 ; pad to B2d with a final hold handled by clone at build
  const buildAt = B2s + segs[1].dur + segs[2].dur + 0.3 / 1.2;

  const PURPLE_LINE = [246, 376, 402, 36];
  const FIXED_LINE = [246, 376, 402, 36];
  const rings = [
    { t0: n0s + 0.55, t1: B2s + 0.5, rect: [244, 380, 382, 28] },
    { t0: n0s + 2.15, t1: B2s + 0.3, rect: [192, 784, 372, 86] },
    { t0: B2s + 2.9, t1: B2s + 3.9, rect: [841, 36, 84, 34] },
    { t0: B2s + 2.9, t1: B2s + 3.9, ripple: [882, 52] },
    { t0: B2s + 2.85, t1: B2s + 3.4, rect: [244, 380, 408, 28] },
    { t0: B3s + 0.25, t1: B3s + 2.0, rect: [909, 425, 490, 36] },
    { t0: B3s + 2.1, t1: B4s - 0.1, rect: [909, 425, 490, 36] },
    { t0: B3s + 2.9, t1: B4s - 0.1, rect: [909, 626, 490, 68] },
    { t0: B4s + 1.9, t1: B4s + 3.0, rect: [1176, 226, 290, 72] },
    { t0: B4s + 3.15, t1: B4s + 4.7, rect: [1174, 476, 294, 76] },
  ];
  const keys = [
    { t: 0, fx: 735, fy: 461, s: [0.86, 0.66], d: 0 },
    { t: n0s + 0.05, fx: 445, fy: 396, s: [2.05, 2.3], d: 1.2 },
    { t: n0s + 2.05, fx: 375, fy: 815, s: [1.75, 2.3], ay: [0.56, 0.42], d: 1.0 },
    { t: B2s + 0.15, fx: 445, fy: 396, s: [2.2, 2.4], d: 1.1 },
    { t: B2s + 2.75, fx: 862, fy: 62, s: [2.4, 3.0], ay: [0.3, 0.22], d: 0.5 },
    { t: B3s - 0.1, fx: 1150, fy: 545, s: [1.6, 1.95], ay: [0.38, 0.34], d: 1.0 },
    { t: B3s + 1.9, fx: 1150, fy: 445, s: [2.2, 2.1], ay: [0.36, 0.34], d: 1.0 },
    { t: B3s + 2.8, fx: 1150, fy: 560, s: [1.9, 2.0], ay: [0.36, 0.34], d: 0.9 },
    { t: B4s + 0.0, fx: 1318, fy: 330, s: [1.55, 2.0], ax: [0.66, 0.5], d: 1.2 },
    { t: B4s + 1.75, fx: 1318, fy: 262, s: [2.25, 2.7], ax: [0.66, 0.5], d: 1.0 },
    { t: B4s + 3.0, fx: 1318, fy: 512, s: [2.25, 2.7], ax: [0.66, 0.5], d: 1.0 },
    { t: ENDs - 0.25, fx: 735, fy: 461, s: [0.8, 0.62], ax: [0.5, 0.5], d: 0.9 },
  ];
  const lower = [
    { t0: n0s + 0.2, t1: B2s + 0.1, tag: "1  Catch it", text: "Typos are flagged as you write." },
    { t0: B2s + 0.35, t1: B3s + 0.05, tag: "2  Fix and build", text: "Rebuilds in about half a second." },
    { t0: B3s + 0.35, t1: B4s + 0.05, tag: "3  Read the result", text: "Every citation resolves in the PDF." },
    { t0: B4s + 0.3, t1: ENDs - 0.1, tag: "4  Before you submit", text: "Checked against submission rules." },
  ];
  const audio = [
    { i: 0, at: n0s }, { i: 1, at: n1s }, { i: 2, at: n2s }, { i: 3, at: n3s }, { i: 4, at: n4s },
  ];

  // Hero loop: silent, 8 s, made from a 8.5 s edit whose first 0.5 s blends into the end.
  const hseg = [seg(6.2, 7.0, 1.0), seg(7.0, 9.4, 1.0), seg(9.4, 12.1, 4.5), seg(12.1, 13.3, 1.0), seg(13.3, 16.8, 1.0)];
  const hero = {
    T: 8.0,
    XF: 0.5,
    segs: hseg,
    keys: [
      { t: 0, fx: 735, fy: 461, s: [0.95], d: 0, nodrift: true },
      { t: 0.5, fx: 445, fy: 396, s: [1.75], d: 1.2 },
      { t: 3.75, fx: 1000, fy: 470, s: [1.3], d: 1.2 },
      { t: 6.0, fx: 1150, fy: 545, s: [1.55], d: 1.1 },
      { t: 6.9, fx: 735, fy: 461, s: [0.95], d: 0.9, nodrift: true },
    ],
    rings: [
      { t0: 0.7, t1: 3.3, rect: [244, 380, 382, 28] },
      { t0: 4.7, t1: 6.8, rect: [909, 425, 490, 36] },
    ],
  };

  return { tv0, n0s, B2s, n1s, B3s, n2s, B4s, n3s, ENDs, n4s, total, segs, buildAt, keys, rings, lower, audio, hero, B2d, B3d, B4d };
}
