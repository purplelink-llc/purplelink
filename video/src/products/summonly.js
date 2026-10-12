// Summonly: the app's own views, drawn offscreen by Summonly/scripts/live/run-shots.sh on invented files in a throwaway
// home folder (dark appearance, 2x), shown in the mac frame. Nothing is a capture of a real screen. Facts from
// site/summonly/index.html. Every lower-third tag says "Sample data" except where it names the feature's own limit.
// Two storyboards share this plan: summonly-promo (about 24 s of product) and summonly-promo-15 (search, questions, end).
import { beats, finish } from "../stillplan.js";

export const media = {
  "summonly-icon.png": "assets/summonly/icon.png",
  "sm-search.png": "assets/summonly/panel-search-dark.png",
  "sm-question.png": "assets/summonly/panel-question-dark.png",
  "sm-clipboard.png": "assets/summonly/panel-clipboard-dark.png",
  "sm-setup.png": "assets/summonly/setup-dark.png",
};

// sw, sh: source pixels (2x). k: stage pixels per source pixel, so the 660 pt panel is the same size in every shot.
const K0 = 0.74;
const img = (name, sw, sh, k = K0) => ({ src: `media/sm-${name}.png`, sw, sh, w: Math.round(sw * k), h: Math.round(sh * k) });
const SE = img("search", 1320, 870, 0.8);
const QU = img("question", 1320, 484, 1.0);
const CL = img("clipboard", 1320, 774, 0.86);
const SU = img("setup", 1280, 1584, 0.48);

const px = (I, x, y) => [x * (I.w / I.sw), y * (I.h / I.sh)];
const rc = (I, x, y, w, h) => {
  const k = I.w / I.sw;
  return [x * k, y * k, w * k, h * k];
};
const still = (I, t0, extra = {}) => ({ src: I.src, w: I.w, h: I.h, t0, ...extra });

export function build(timing) {
  const short = timing.scenes.length === 3; // summonly-promo-15
  const order = short ? [0, 1] : [0, 1, 2, 3];
  const B = beats(timing, order, { start: 1.7, lead: 0.15, tail: 0.15 });
  const [b0, b1, b2, b3] = B;
  const keys = [];
  const rings = [];
  const lower = [];
  const K = (t, I, sx, sy, s, d, extra = {}) => {
    const [fx, fy] = sx == null ? [I.w / 2, I.h / 2] : px(I, sx, sy);
    keys.push({ t, fx, fy, s, d, ...extra });
  };
  const R = (t0, t1, I, x, y, w, h) => rings.push({ t0, t1, rect: rc(I, x, y, w, h) });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text, maxW: 1300 });
  const AY = { ay: [0.38, 0.38] };
  const Z = { ay: [0.38, 0.38] };
  const WIDE = [1.0, 0.92];

  // 1 search
  K(0, SE, null, null, WIDE, 0, AY);
  K(b0.cue("type") - 0.3, SE, 660, 330, [1.06, 1.0], 1.2, AY);
  R(b0.cue("option") - 0.1, b0.cue("type") + 0.2, SE, 0, 0, 1320, 108);
  R(b0.cue("return") - 0.35, b0.e + 0.1, SE, 12, 122, 1296, 96);
  K(b0.cue("return") - 0.5, SE, 660, 400, [1.08, 1.0], 1.2, AY);
  L(b0.n + 0.15, b0.e - 0.1, "1  Search  ·  Sample data", "Option-Space, type, Return.");

  // 2 questions
  K(b1.s, QU, null, null, [1.0, 0.72], 1.0, AY);
  K(b1.cue("passage") - 0.3, QU, 660, 190, [1.1, 0.76], 1.3, Z);
  R(b1.cue("passage") - 0.1, b1.cue("page") - 0.1, QU, 12, 122, 1296, 96);
  R(b1.cue("page") - 0.05, b1.cue("words") - 0.3, QU, 110, 168, 160, 44);
  K(b1.cue("words") - 0.5, QU, null, null, [1.04, 0.74], 1.2, AY);
  L(b1.n + 0.15, b1.e - 0.1, "2  Questions  ·  Optional", "It finds the words you use.");

  if (short) {
    const ENDs = b1.e;
    K(ENDs - 0.25, QU, null, null, [1.0, 0.72], 0.9, AY);
    const stills = [still(SE, 0), still(QU, b1.s - 0.1)];
    const hero = heroPlan();
    return finish({ id: "summonly-promo-15", frame: "mac", introAt: 1.15, titleT1: 1.05, title: titleCard(), end: endCard(), stills, keys, rings, lower, cursors: [], hero, poster: b1.cue("page") + 0.9, windowBg: WINBG, windowRadius: 24 }, B, 2, timing, { endLead: 0.2, endTail: 0.35 });
  }

  // 3 clipboard
  K(b2.s, CL, null, null, [1.0, 0.85], 1.0, AY);
  K(b2.cue("keeps") - 0.4, CL, 660, 330, [1.06, 0.88], 1.3, Z);
  R(b2.cue("keeps") - 0.1, b2.e + 0.1, CL, 12, 122, 1296, 580);
  L(b2.n + 0.15, b2.e - 0.1, "3  Clipboard  ·  Sample data", "Search what you copied.");

  // 4 clipboard privacy, in the first-run window
  K(b3.s, SU, null, null, [1.0, 0.8], 1.0, AY);
  K(b3.cue("off") - 0.5, SU, 640, 1270, [1.25, 1.1], 1.3, Z);
  R(b3.cue("off") - 0.1, b3.cue("skips") - 0.1, SU, 36, 1328, 340, 56);
  R(b3.cue("skips") - 0.05, b3.e + 0.1, SU, 36, 1204, 1208, 112);
  K(b3.cue("skips") - 0.4, SU, 640, 1240, [1.25, 1.1], 1.1, Z);
  L(b3.n + 0.15, b3.e - 0.1, "4  Privacy  ·  First-run window", "Off until you turn it on.");

  const ENDs = b3.e;
  K(ENDs - 0.25, SU, 640, 1000, [1.0, 0.75], 0.9, AY);

  const stills = [still(SE, 0), still(QU, b1.s - 0.1), still(CL, b2.s - 0.1), still(SU, b3.s - 0.1)];
  const hero = heroPlan();

  return finish({ id: "summonly-promo", frame: "mac", introAt: 1.15, titleT1: 1.05, title: titleCard(), end: endCard(), stills, keys, rings, lower, cursors: [], hero, poster: b1.cue("page") + 0.9, windowBg: WINBG, windowRadius: 24 }, B, 4, timing, { endLead: 0.2, endTail: 0.35 });
}

const WINBG = "oklch(27% 0.01 300)";
const titleCard = () => ({ name: "Summonly", sub: "Files, apps and clipboard history, from one box.", icon: "media/summonly-icon.png", iconRadius: 0 });
const endCard = () => ({ pill: "$9.99 once. 7-day free trial.", url: "purplelink.llc/summonly" });

// Silent loop: the search panel, a slow push in, a ring down the file rows, back out.
function heroPlan() {
  const c = (x, y) => px(SE, x, y);
  return {
    T: 8,
    XF: 0.6,
    stills: [still(SE, 0)],
    keys: [
      { t: 0, fx: SE.w / 2, fy: SE.h / 2, s: [0.9], d: 0, nodrift: true, ay: [0.5] },
      { t: 0.5, fx: c(660, 300)[0], fy: c(660, 300)[1], s: [1.0], d: 1.4, nodrift: true, ay: [0.5] },
      { t: 6.6, fx: SE.w / 2, fy: SE.h / 2, s: [0.9], d: 1.2, nodrift: true, ay: [0.5] },
    ],
    rings: [
      { t0: 0.9, t1: 2.7, rect: rc(SE, 0, 0, 1320, 108) },
      { t0: 2.8, t1: 4.8, rect: rc(SE, 12, 122, 1296, 96) },
      { t0: 4.9, t1: 6.5, rect: rc(SE, 12, 410, 1296, 96) },
    ],
  };
}
