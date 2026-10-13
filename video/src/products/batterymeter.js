// BatteryMeter: 2x renders of the app's own menu bar item and menu, shown in the mac frame. Nothing is a capture of a screen.
//  - live-charging.png is a live reading from the real app on a Mac (the lower thirds say "Live reading");
//  - sample-draining.png and sample-low.png are drawn by the app's snapshot mode with sample values and carry
//    "Sample values, not a live reading" inside the image (the lower thirds say "Sample values");
//  - the setup scene is a drawn text card, not a screenshot.
// Facts from the brief for this cut and the BatteryMeter README.
import { beats, finish } from "../stillplan.js";

export const media = {
  "batterymeter-icon.png": "assets/batterymeter/icon-1024.png",
  "bm-live.png": "assets/batterymeter/live-charging.png",
  "bm-drain.png": "assets/batterymeter/sample-draining.png",
  "bm-low.png": "assets/batterymeter/sample-low.png",
};

// source pixels (2x render) shown 1:1 in window px
const LIVE = { src: "media/bm-live.png", w: 1120, h: 828 };
const DRAIN = { src: "media/bm-drain.png", w: 1120, h: 732 };
const LOW = { src: "media/bm-low.png", w: 1120, h: 732 };
const CARD = { w: 1120, h: 640 };
const BG = "oklch(24% 0.03 300)";
const ITEM = [940, 36]; // centre of the menu bar item in all three images
const ITEM_RING = [782, 8, 306, 56];
const row = (y) => [60, y - 25, 960, 50];

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4, 5], { start: 0.3, lead: 0.3, tail: 0.12, hold: { 0: 2.6 } });
  const [b0, b1, b2, b3, b4, b5] = B;
  const keys = [];
  const rings = [];
  const lower = [];
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text, maxW: 1300 });
  const AY = { ay: [0.42, 0.4] };
  const ZN = { ay: [0.42, 0.4] };
  const centre = (I) => [I.w / 2, I.h / 2];
  const wide = [0.98, 0.84];

  // 0 title, then the live window rises in
  const titleEnd = b0.e - 0.15;
  keys.push({ t: 0, fx: LIVE.w / 2, fy: LIVE.h / 2, s: wide, d: 0, ...AY });

  // 1 live reading
  keys.push({ t: b1.s, fx: LIVE.w / 2, fy: LIVE.h / 2, s: wide, d: 0.9, ...AY });
  R(b1.cue("percent") - 0.3, b1.e - 0.05, ITEM_RING);
  L(b1.n + 0.15, b1.e - 0.1, "Live reading", "Percent, arrow, battery watts.");

  // 2 draining sample
  const s2 = b2.s - 0.1;
  keys.push({ t: s2, fx: DRAIN.w / 2, fy: DRAIN.h / 2, s: wide, d: 0.9, ...AY });
  R(b2.cue("arrow") - 0.3, b2.e - 0.05, ITEM_RING);
  L(b2.n + 0.15, b2.e - 0.1, "Sample values", "Down arrow, minus watts.");

  // 3 low sample
  const s3 = b3.s - 0.1;
  keys.push({ t: s3, fx: LOW.w / 2, fy: LOW.h / 2, s: wide, d: 0.9, ...AY });
  R(b3.cue("orange") - 0.35, b3.e - 0.05, ITEM_RING);
  L(b3.n + 0.15, b3.e - 0.1, "Sample values", "Orange at 20 percent or below.");

  // 4 menu details, live image again
  const s4 = b4.s - 0.1;
  keys.push({ t: s4, fx: LIVE.w / 2, fy: LIVE.h / 2, s: wide, d: 0.9, ...AY });
  R(b4.cue("time") - 0.1, b4.cue("volts") - 0.15, row(233));
  R(b4.cue("volts") - 0.1, b4.cue("adapter") - 0.15, row(281));
  R(b4.cue("adapter") - 0.1, b4.cue("cycle") - 0.15, row(425));
  R(b4.cue("cycle") - 0.1, b4.e - 0.05, row(665));
  L(b4.n + 0.15, b4.e - 0.1, "Live reading", "The menu adds the details.");

  // 5 setup card
  const s5 = b5.s - 0.1;
  const card = {
    bg: BG, ink: "oklch(97% 0.01 300)", muted: "oklch(76% 0.04 300)", accent: "oklch(56% 0.22 310)", accentInk: "oklch(99% 0.01 310)",
    tag: "Setup", heading: "Put it where Apple's icon was",
    steps: [
      { t: b5.cue("hide") - s5 - 0.2, text: "Hide Apple's icon: System Settings, Control Center, Battery." },
      { t: b5.cue("hold") - s5 - 0.2, text: "Hold Command and drag BatteryMeter's item into its place." },
    ],
  };
  keys.push({ t: s5, fx: CARD.w / 2, fy: CARD.h / 2, s: [1.25, 0.9], d: 0.9, ...AY });

  const ENDs = b5.e;
  const stills = [
    { ...LIVE, t0: 0 },
    { ...LIVE, t0: b1.s - 0.1 },
    { ...DRAIN, t0: s2 },
    { ...LOW, t0: s3 },
    { ...LIVE, t0: s4 },
    { src: null, ...CARD, card, t0: s5 },
  ];
  // the first two entries are the same picture; drop the duplicate so there is no needless crossfade
  stills.splice(1, 1);

  return finish(
    {
      id: "batterymeter-promo",
      frame: "mac",
      introAt: titleEnd - 0.35,
      titleT1: titleEnd,
      title: { name: "BatteryMeter", sub: "A free Mac battery meter that shows more.", icon: "media/batterymeter-icon.png", iconRadius: 0.22 },
      end: { pill: "Free for Mac", url: "purplelink.llc/batterymeter", note: "No email. No account.\nmacOS 13 or later, Apple silicon." },
      stills, keys, rings, lower, cursors: [], hero: heroPlan(),
      poster: b1.cue("watts") + 0.5,
      windowBg: BG, windowRadius: 24,
    },
    B, 6, timing, { endLead: 0.2, endTail: 0.35 },
  );
}

// 8 second silent loop of the live reading: wide, a slow push in on the menu bar item with a ring, back out.
function heroPlan() {
  return {
    T: 8,
    XF: 0.6,
    stills: [{ ...LIVE, t0: 0 }],
    keys: [
      { t: 0, fx: LIVE.w / 2, fy: LIVE.h / 2, s: [1.0], d: 0, nodrift: true, ay: [0.46] },
      { t: 0.8, fx: 800, fy: 160, s: [1.55], d: 1.6, nodrift: true, ay: [0.46] },
      { t: 6.0, fx: LIVE.w / 2, fy: LIVE.h / 2, s: [1.0], d: 1.4, nodrift: true, ay: [0.46] },
    ],
    rings: [{ t0: 1.8, t1: 5.6, rect: ITEM_RING }],
  };
}
