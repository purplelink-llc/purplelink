// Scholar Utility Belt: browser frame, mockups rendered from the extension repo with invented names
// (video/capture.py), displayed at 1280x756. Facts from site/scholar-utility-belt/index.html.
import { beats, finish, WIDE } from "../stillplan.js";

export const media = {
  "sub-badges.png": ".cache/captures/sub-1.png",
  "sub-author.png": ".cache/captures/sub-2.png",
  "sub-lineage.png": ".cache/captures/sub-3.png",
};
const D = { w: 1280, h: 756 };
const IMG = {
  badges: { src: "media/sub-badges.png", ...D },
  author: { src: "media/sub-author.png", ...D },
  lineage: { src: "media/sub-lineage.png", ...D },
};

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4, 5], { start: 2.5, lead: 0.3, tail: 0.4 });
  const [b0, b1, b2, b3, b4, b5] = B;
  const W = WIDE.browser1280;
  const Z = [1.7, 2.1];
  const keys = [], rings = [], lower = [], cursors = [];
  const K = (t, fx, fy, s, d, extra = {}) => keys.push({ t, fx, fy, s, d, ...extra });
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text });

  // 1 Badges
  K(0, 640, 400, W, 0);
  K(b0.cue("badges") - 0.3, 330, 200, Z, 1.2, { ay: [0.44, 0.42] });
  R(b0.cue("badges") - 0.1, b0.cue("beside") - 0.1, [22, 150, 353, 28]);
  R(b0.cue("beside") - 0.05, b0.e + 0.1, [22, 380, 293, 29]);
  K(b0.cue("beside") - 0.3, 330, 330, Z, 1.1, { ay: [0.44, 0.42] });
  L(b0.n + 0.15, b0.e - 0.05, "1  Journal quality", "ABDC, FT50, UTD24 and SJR badges.");

  // 2 Citation velocity
  K(b1.s, 330, 215, [2.0, 2.4], 1.1, { ay: [0.44, 0.42] });
  R(b1.cue("velocity") - 0.1, b1.e + 0.1, [297, 150, 78, 28]);
  R(b1.cue("quickly") - 0.1, b1.e + 0.1, [173, 266, 70, 28]);
  cursors.push({ t0: b1.n, t1: b1.e, pts: [[b1.n, 480, 240], [b1.n + 0.9, 345, 165], [b1.e, 345, 165]] });
  L(b1.n + 0.15, b1.e - 0.05, "2  Citation velocity", "How quickly each paper is being cited.");

  // 3 Retraction alert
  K(b2.s, 330, 560, Z, 1.2, { ay: [0.46, 0.42] });
  R(b2.cue("retracted") - 0.1, b2.e + 0.1, [22, 546, 460, 75]);
  L(b2.n + 0.15, b2.e - 0.05, "3  Retraction alerts", "A visible warning before you cite.");

  // 4 Author metrics
  K(b3.s, 640, 378, W, 0.9);
  K(b3.n + 0.5, 300, 110, [1.9, 2.3], 1.2, { ay: [0.42, 0.4] });
  R(b3.cue("hindex") - 0.1, b3.e + 0.1, [22, 108, 470, 26]);
  R(b3.cue("gindex") - 0.1, b3.e + 0.1, [22, 140, 372, 26]);
  L(b3.n + 0.15, b3.e - 0.05, "4  Author metrics", "h-index and g-index on profile pages.");

  // 5 Lineage
  K(b4.s, 640, 378, W, 0.9);
  K(b4.n + 0.5, 1040, 250, [1.55, 1.9], 1.2, { ay: [0.46, 0.42] });
  R(b4.cue("advisors") - 0.1, b4.e + 0.1, [828, 196, 432, 50]);
  R(b4.cue("students") - 0.1, b4.e + 0.1, [848, 330, 412, 50]);
  R(b4.cue("among") - 0.1, b4.e + 0.1, [828, 263, 432, 50]);
  L(b4.n + 0.15, b4.e - 0.05, "5  Academic lineage", "Advisors and students, in a tree.");

  // 6 Private by design
  K(b5.s, 640, 378, [0.9, 0.72], 1.2);
  L(b5.n + 0.15, b5.e - 0.05, "6  Private by design", "About 1,000 researchers. 4.5 of 5 on the Chrome Web Store.");

  const ENDs = b5.e;
  K(ENDs - 0.25, 640, 378, [0.86, 0.68], 0.9);

  const stills = [
    { ...IMG.badges, t0: 0 },
    { ...IMG.author, t0: b3.s - 0.1 },
    { ...IMG.lineage, t0: b4.s - 0.1 },
    { ...IMG.badges, t0: b5.s - 0.1 },
  ];
  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...IMG.badges, t0: 0 }],
    keys: [
      { t: 0, fx: 640, fy: 378, s: [1.0], d: 0, nodrift: true },
      { t: 0.5, fx: 330, fy: 200, s: [1.7], d: 1.4, ay: [0.44] },
      { t: 3.8, fx: 330, fy: 560, s: [1.7], d: 1.4, ay: [0.46] },
      { t: 6.7, fx: 640, fy: 378, s: [1.0], d: 1.1, nodrift: true },
    ],
    rings: [
      { t0: 1.0, t1: 3.5, rect: [22, 150, 353, 28] },
      { t0: 4.5, t1: 6.5, rect: [22, 546, 460, 75] },
    ],
  };
  return finish(
    {
      id: "scholar-utility-belt-promo", frame: "browser", url: "scholar.google.com",
      title: { name: "Scholar Utility Belt", sub: "Journal rankings and h-index in Google Scholar.", icon: "brand/sub-icon.png", iconRadius: 0.22 },
      end: { pill: "Free core. Add to Chrome", url: "purplelink.llc/scholar-utility-belt" },
      stills, keys, rings, lower, cursors, hero,
      poster: b0.e - 0.8,
    },
    B, 6, timing,
  );
}
