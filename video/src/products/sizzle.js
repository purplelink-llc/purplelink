// Purplelink brand sizzle: browser frame scrolling /products/ (1440 CSS px, view 1440x900).
// Facts from site/products/index.html.
import { beats, finish, WIDE } from "../stillplan.js";

export const media = { "products.png": ".cache/captures/products.png" };
const PAGE = { src: "media/products.png", w: 1440, h: 6879, view: { w: 1440, h: 900 } };
const Y = { hero: 0, moderntex: 1500, vitae: 2140, review: 2760, free: 3820, ios: 4400 };

export function build(timing) {
  const B = beats(timing, [0, 1, 2], { start: 2.3, lead: 0.2, tail: 0.35 });
  const [b0, b1, b2] = B;
  const W = WIDE.browser1440;
  const keys = [], rings = [], lower = [], scroll = [];
  const K = (t, fx, fy, s, d, extra = {}) => keys.push({ t, fx, fy, s, d, ...extra });
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text });
  const S = (t, y, d = 1.0) => scroll.push({ t, y, d });

  // hero
  S(0, Y.hero, 0);
  K(0, 720, 450, W, 0);
  K(b0.n + 0.3, 520, 300, [1.25, 1.5], 1.4, { ay: [0.42, 0.4] });

  // ModernTex, Vitae, Paper Review
  const tM = b1.cue("moderntex") - 0.2, tV = b1.cue("vitae") - 0.2, tP = b1.cue("paper") - 0.2;
  S(tM, Y.moderntex, 1.0);
  K(tM, 720, 330, [1.1, 1.35], 1.1, { ay: [0.44, 0.42] });
  R(tM + 0.6, tV, [80, 1545 - Y.moderntex, 1280, 528]);
  L(tM + 0.2, tV - 0.05, "ModernTex", "LaTeX editor for Mac. $10 once.");
  S(tV, Y.vitae, 1.0);
  R(tV + 0.6, tP, [80, 2420 - Y.vitae, 630, 272]);
  L(tV + 0.15, tP - 0.05, "Vitae", "Your academic record. Free.");
  S(tP, Y.review, 1.0);
  K(tP, 520, 380, [1.2, 1.5], 1.1, { ay: [0.44, 0.42] });
  R(tP + 0.6, b1.e + 0.1, [80, 3066 - Y.review, 416, 414]);
  L(tP + 0.15, b1.e - 0.05, "Paper Review", "Four AI reviewers. $9, $11 or $15.");

  // Scholar Utility Belt, GlobePin and Haea
  const tS = b2.s, tG = b2.cue("globepin") - 0.2;
  S(tS, Y.free, 1.0);
  K(tS, 520, 420, [1.2, 1.5], 1.1, { ay: [0.44, 0.42] });
  R(tS + 0.6, tG, [80, 4050 - Y.free, 630, 290]);
  L(tS + 0.15, tG - 0.05, "Scholar Utility Belt", "Journal rankings in Google Scholar. Free.");
  S(tG, Y.ios, 1.0);
  K(tG, 720, 420, [1.1, 1.35], 1.1, { ay: [0.44, 0.42] });
  R(tG + 0.6, b2.e + 0.1, [80, 4600 - Y.ios, 1280, 300]);
  L(tG + 0.15, b2.e - 0.05, "GlobePin and Haea", "For iPhone. GlobePin is free on the App Store.");

  const ENDs = b2.e;
  K(ENDs - 0.25, 720, 450, [0.82, 0.64], 0.9);

  const stills = [{ ...PAGE, t0: 0, scroll }];
  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...PAGE, t0: 0, scroll: [{ t: 0, y: 0, d: 0 }, { t: 1.0, y: 1500, d: 5.4 }, { t: 6.5, y: 0, d: 1.3 }] }],
    keys: [
      { t: 0, fx: 720, fy: 450, s: [0.9], d: 0, nodrift: true },
      { t: 0.6, fx: 720, fy: 400, s: [1.05], d: 1.6, ay: [0.44] },
      { t: 6.5, fx: 720, fy: 450, s: [0.9], d: 1.3, nodrift: true },
    ],
    rings: [],
  };
  return finish(
    {
      id: "purplelink-sizzle", frame: "browser", url: "purplelink.llc/products",
      title: { name: "Purplelink", sub: "Tools for the paper, from first draft to accepted.", icon: "brand/purplelink-tile.png", iconRadius: 0.26 },
      end: { pill: "No account needed", url: "purplelink.llc/products" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b1.cue("vitae") + 0.9,
      titleT1: 1.2,
    },
    B, 3, timing,
  );
}
