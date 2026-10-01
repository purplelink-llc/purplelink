// Haea: iPhone frame, 1206x2622 stills. Facts from site/haea/index.html.
import { beats, finish, WIDE, PHONE_AX, PHONE_AY } from "../stillplan.js";

export const media = {
  "haea-today.webp": "../site/assets/haea-screens/01-today.webp",
  "haea-strength.webp": "../site/assets/haea-screens/02-strength.webp",
  "haea-nutrition.webp": "../site/assets/haea-screens/03-nutrition.webp",
};
const P = { w: 1206, h: 2622 };
const IMG = {
  today: { src: "media/haea-today.webp", ...P },
  strength: { src: "media/haea-strength.webp", ...P },
  nutrition: { src: "media/haea-nutrition.webp", ...P },
};
const CX = 603, CY = 1311;

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4], { start: 2.5, lead: 0.25, tail: 0.4 });
  const [b0, b1, b2, b3, b4] = B;
  const W = WIDE.phone;
  const Z = [0.62, 0.72];
  const keys = [], rings = [], lower = [];
  const wide = { ax: PHONE_AX.wide, ay: PHONE_AY.wide };
  const zoom = { ax: PHONE_AX.zoom, ay: PHONE_AY.zoom };
  const K = (t, fx, fy, s, d, extra = {}) => keys.push({ t, fx, fy, s, d, ...extra });
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text, maxW: 640 });

  // 1 Today
  K(0, CX, CY, W, 0, wide);
  K(b0.n + 1.2, 603, 1700, [0.52, 0.64], 1.6, zoom);
  R(b0.cue("biometrics") - 0.2, b0.e + 0.1, [55, 1572, 1096, 600]);
  L(b0.n + 0.15, b0.e - 0.05, "1  Today", "Sleep, nutrition, activity, biometrics.");

  // 2 Apple Health and the briefing
  K(b1.s, 603, 900, Z, 1.2, zoom);
  R(b1.cue("apple") - 0.1, b1.cue("briefing") - 0.2, [75, 560, 1056, 570]);
  R(b1.cue("briefing") - 0.1, b1.e + 0.1, [75, 1190, 1056, 320]);
  K(b1.cue("briefing") - 0.3, 603, 1150, [0.6, 0.72], 1.2, zoom);
  L(b1.n + 0.15, b1.e - 0.05, "2  Apple Health", "One short morning briefing.");

  // 3 Strength: tap Start Workout
  K(b2.s, CX, CY, W, 1.0, wide);
  K(b2.n + 0.4, 603, 1000, Z, 1.2, zoom);
  rings.push({ t0: b2.cue("workouts") + 0.1, t1: b2.cue("workouts") + 1.0, ripple: [603, 992] });
  R(b2.cue("workouts") + 0.3, b2.e + 0.1, [48, 915, 1110, 155]);
  L(b2.n + 0.15, b2.e - 0.05, "3  Logging", "Workouts, food, water, weight, mood.");

  // 4 Nutrition: macro targets
  K(b3.s, CX, CY, W, 1.0, wide);
  K(b3.cue("macros") - 0.3, 603, 2000, [0.6, 0.7], 1.2, { ax: PHONE_AX.zoom, ay: [0.5, 0.42] });
  R(b3.cue("targets") - 0.1, b3.e + 0.1, [48, 1793, 1110, 515]);
  L(b3.n + 0.15, b3.e - 0.05, "4  Nutrition", "Macros against targets. 7 and 30 day trends.");

  // 5 Free, Premium, on-device
  K(b4.s, 603, 1000, [0.46, 0.58], 1.3, { ax: PHONE_AX.zoom, ay: [0.47, 0.4] });
  K(b4.cue("nothing") - 0.4, CX, CY, [0.34, 0.5], 1.4, wide);
  L(b4.n + 0.15, b4.cue("nothing") - 0.1, "5  Free tier", "Premium $1.99 a month or $14.99 a year.");
  L(b4.cue("nothing") + 0.05, b4.e - 0.05, "6  On-device", "No cloud sync. No third-party SDKs. No ads.");

  const ENDs = b4.e;
  K(ENDs - 0.25, CX, CY, [0.3, 0.44], 0.9, wide);

  const stills = [
    { ...IMG.today, t0: 0 },
    { ...IMG.strength, t0: b2.s - 0.1 },
    { ...IMG.nutrition, t0: b3.s - 0.1 },
  ];
  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...IMG.today, t0: 0 }],
    keys: [
      { t: 0, fx: CX, fy: CY, s: [0.34], d: 0, nodrift: true, ax: [0.5], ay: [0.5] },
      { t: 0.5, fx: 603, fy: 900, s: [0.62], d: 1.5, ax: [0.5], ay: [0.46] },
      { t: 3.8, fx: 603, fy: 1700, s: [0.58], d: 1.5, ax: [0.5], ay: [0.46] },
      { t: 6.7, fx: CX, fy: CY, s: [0.34], d: 1.1, nodrift: true, ax: [0.5], ay: [0.5] },
    ],
    rings: [
      { t0: 1.0, t1: 3.5, rect: [75, 560, 1056, 570] },
      { t0: 4.5, t1: 6.5, rect: [55, 1572, 1096, 600] },
    ],
  };
  return finish(
    {
      id: "haea-promo", frame: "phone",
      title: { name: "Haea", sub: "Your complete health picture, on your phone.", icon: "brand/haea-icon.png", iconRadius: 0.22 },
      end: { pill: "In development. Join the waitlist", url: "purplelink.llc/haea" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b1.n + 1.4,
    },
    B, 5, timing,
  );
}
