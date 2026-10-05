// Legroom: sample-data window captures from the app's QA harness (dark appearance), shown in the mac frame.
// Source PNGs were converted to lossless webp in assets/legroom/. Facts from site/legroom/index.html.
// Every lower-third tag carries "Sample data" because the numbers and files on screen are invented.
import { beats, finish } from "../stillplan.js";

export const media = {
  "legroom-icon.png": "assets/legroom/icon.png",
  "lg-dropdown.webp": "assets/legroom/dropdown.webp",
  "lg-alerts.webp": "assets/legroom/alerts.webp",
  "lg-clean-now.webp": "assets/legroom/clean-now.webp",
  "lg-recommended.webp": "assets/legroom/recommended.webp",
  "lg-what-grew.webp": "assets/legroom/what-grew.webp",
  "lg-space-map.webp": "assets/legroom/space-map.webp",
  "lg-find-files.webp": "assets/legroom/find-files.webp",
};

// sw, sh: source pixels. w, h: window px used on stage (aspect kept).
const img = (name, sw, sh, h) => ({ src: `media/lg-${name}.webp`, sw, sh, h, w: Math.round((sw * h) / sh) });
const DD = img("dropdown", 600, 1042, 760);
const AL = img("alerts", 1400, 1304, 750);
const CN = img("clean-now", 600, 762, 760);
const RC = img("recommended", 1400, 1184, 720);
const WG = img("what-grew", 1400, 1504, 760);
const SM = img("space-map", 1760, 1624, 760);
const FF = img("find-files", 1800, 1664, 760);

// helpers in source pixels -> window px
const px = (I, x, y) => [x * (I.w / I.sw), y * (I.h / I.sh)];
const rc = (I, x, y, w, h) => {
  const k = I.w / I.sw;
  return [x * k, y * k, w * k, h * k];
};
const still = (I, t0) => ({ src: I.src, w: I.w, h: I.h, t0 });

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4, 5], { start: 2.3, lead: 0.25, tail: 0.3, hold: { 0: 5.2, 1: 4.4, 2: 6.8, 3: 5.2, 4: 4.2, 5: 7.4 } });
  const [b0, b1, b2, b3, b4, b5] = B;
  const keys = [];
  const rings = [];
  const lower = [];
  const K = (t, I, sx, sy, s, d, extra = {}) => {
    const [fx, fy] = sx == null ? [I.w / 2, I.h / 2] : px(I, sx, sy);
    keys.push({ t, fx, fy, s: [s], d, ...extra });
  };
  const R = (t0, t1, I, x, y, w, h) => rings.push({ t0, t1, rect: rc(I, x, y, w, h) });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag: `${tag}  ·  Sample data`, text, maxW: 1300 });
  const AY = { ay: [0.43] };
  const Z = { ay: [0.4] };
  const ZN = { ay: [0.4], ax: [0.6] }; // narrow windows sit right of centre so the lower third stays clear

  // 1 menu-bar readout and dropdown
  K(0, DD, null, null, 1.05, 0, AY);
  K(b0.cue("free") - 0.3, DD, 300, 250, 1.6, 1.3, ZN);
  R(b0.cue("free") - 0.1, b0.cue("menu") - 0.3, DD, 24, 92, 548, 190);
  K(b0.cue("menu") - 0.4, DD, 300, 440, 1.5, 1.3, ZN);
  R(b0.cue("menu") - 0.1, b0.e + 0.1, DD, 24, 296, 548, 180);
  L(b0.n + 0.15, b0.e - 0.1, "1  Menu bar", "Free space, always in view.");

  // 2 low-space alerts
  K(b1.s, AL, null, null, 1.0, 1.0, AY);
  K(b1.cue("line") - 0.2, AL, 700, 420, 1.7, 1.2, Z);
  R(b1.cue("line") - 0.1, b1.cue("warns") - 0.15, AL, 40, 290, 1320, 268);
  R(b1.cue("warns") - 0.05, b1.e + 0.1, AL, 40, 104, 1320, 74);
  L(b1.n + 0.15, b1.e - 0.1, "2  Alerts", "Warns you before the disk fills.");

  // 3 rules: preview, approval, Trash
  K(b2.s, CN, null, null, 1.0, 1.0, AY);
  K(b2.cue("previews") - 0.3, CN, 300, 330, 1.55, 1.3, ZN);
  R(b2.cue("previews") - 0.1, b2.cue("approve") - 0.2, CN, 24, 142, 552, 470);
  R(b2.cue("approve") - 0.1, b2.cue("trash") - 0.3, CN, 296, 678, 282, 60);
  K(b2.cue("approve") - 0.4, CN, 300, 520, 1.45, 1.2, ZN);
  R(b2.cue("trash") - 0.2, b2.e + 0.1, CN, 24, 142, 552, 56);
  K(b2.cue("trash") - 0.5, CN, 300, 300, 1.55, 1.2, ZN);
  L(b2.n + 0.15, b2.e - 0.1, "3  Rules", "Preview first. You approve.");

  // 4 Recommended
  K(b3.s, RC, null, null, 1.0, 1.0, AY);
  K(b3.cue("caches") - 0.2, RC, 700, 330, 1.7, 1.3, Z);
  R(b3.cue("caches") - 0.1, b3.cue("npm") - 0.1, RC, 30, 90, 1340, 70);
  R(b3.cue("npm") - 0.1, b3.cue("playwright") - 0.1, RC, 30, 180, 1340, 125);
  R(b3.cue("playwright") - 0.05, b3.e + 0.1, RC, 30, 462, 1340, 170);
  K(b3.cue("playwright") - 0.4, RC, 700, 450, 1.7, 1.2, Z);
  L(b3.n + 0.15, b3.e - 0.1, "4  Recommended", "Known caches you can add as rules.");

  // 5 What Grew
  K(b4.s, WG, null, null, 1.0, 1.0, AY);
  K(b4.cue("folders") - 0.5, WG, 700, 600, 1.9, 1.3, Z);
  R(b4.cue("folders") - 0.1, b4.cue("last") - 0.1, WG, 28, 385, 1344, 380);
  R(b4.cue("last") - 0.05, b4.e + 0.1, WG, 196, 270, 440, 50);
  K(b4.cue("last") - 0.4, WG, 700, 480, 1.9, 1.2, Z);
  L(b4.n + 0.15, b4.e - 0.1, "5  What Grew", "Which folders grew since last time.");

  // 6 Space Map, then Find Files
  K(b5.s, SM, null, null, 1.0, 1.0, AY);
  K(b5.n + 0.3, SM, 880, 1090, 2.6, 1.3, Z);
  R(b5.n + 0.5, b5.cue("find") - 0.4, SM, 620, 890, 500, 385);
  K(b5.cue("find") - 0.5, FF, null, null, 1.0, 1.0, AY);
  K(b5.cue("find") + 0.3, FF, 900, 1100, 2.2, 1.3, Z);
  R(b5.cue("large") - 0.2, b5.cue("duplicate") - 0.2, FF, 32, 823, 531, 50);
  R(b5.cue("duplicate") - 0.1, b5.e + 0.1, FF, 32, 823, 531, 50);
  K(b5.cue("duplicate") - 0.5, FF, 900, 1100, 2.2, 1.3, Z);
  L(b5.n + 0.15, b5.cue("find") - 0.5, "6  Space Map", "Where the space went.");
  L(b5.cue("find") - 0.1, b5.e - 0.1, "7  Find Files", "Large, old and duplicate files.");

  const ENDs = b5.e;
  K(ENDs - 0.25, FF, null, null, 0.95, 0.9, AY);

  const stills = [still(DD, 0), still(AL, b1.s - 0.1), still(CN, b2.s - 0.1), still(RC, b3.s - 0.1), still(WG, b4.s - 0.1), still(SM, b5.s - 0.1), still(FF, b5.cue("find") - 0.2)];

  const hero = {
    T: 8,
    XF: 0.6,
    stills: [still(SM, 0)],
    keys: [
      { t: 0, fx: SM.w / 2, fy: SM.h / 2, s: [1.0], d: 0, nodrift: true },
      { t: 0.5, fx: px(SM, 880, 1090)[0], fy: px(SM, 880, 1090)[1], s: [1.7], d: 1.5, ay: [0.44] },
      { t: 3.8, fx: px(SM, 880, 640)[0], fy: px(SM, 880, 640)[1], s: [1.4], d: 1.4, ay: [0.44] },
      { t: 6.7, fx: SM.w / 2, fy: SM.h / 2, s: [1.0], d: 1.1, nodrift: true, ay: [0.44] },
    ],
    rings: [{ t0: 1.0, t1: 3.5, rect: rc(SM, 620, 890, 500, 385) }],
  };

  return finish(
    {
      id: "legroom-promo",
      frame: "mac",
      title: { name: "Legroom", sub: "Your Mac's free space, in the menu bar.", icon: "media/legroom-icon.png", iconRadius: 0.22 },
      end: { pill: "$9 once. 7-day free trial.", url: "purplelink.llc/legroom" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b4.n + 2.4,
    },
    B, 6, timing, { endTail: 0.6 },
  );
}
