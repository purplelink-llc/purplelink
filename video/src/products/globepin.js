// GlobePin: iPhone frame, 1206x2622 stills. Facts from site/globepin/index.html.
import { beats, finish, WIDE, PHONE_AX, PHONE_AY } from "../stillplan.js";

export const media = {
  "globepin-map.webp": "../site/assets/globepin-screens/02-map.webp",
  "globepin-globe.webp": "../site/assets/globepin-screens/03-globe.webp",
  "globepin-stats.webp": "../site/assets/globepin-screens/04-stats.webp",
  "globepin-goals.webp": "../site/assets/globepin-screens/05-goals.webp",
};
const P = { w: 1206, h: 2622 };
const IMG = {
  map: { src: "media/globepin-map.webp", ...P },
  globe: { src: "media/globepin-globe.webp", ...P },
  stats: { src: "media/globepin-stats.webp", ...P },
  goals: { src: "media/globepin-goals.webp", ...P },
};
const CX = 603, CY = 1311;

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4], { start: 2.5, lead: 0.3, tail: 0.45, hold: { 2: 4.4 } });
  const [b0, b1, b2, b3, b4] = B;
  const W = WIDE.phone;
  const Z = [0.62, 0.72];
  const keys = [], rings = [], lower = [];
  const wide = { ax: PHONE_AX.wide, ay: PHONE_AY.wide };
  const zoom = { ax: PHONE_AX.zoom, ay: PHONE_AY.zoom };
  const K = (t, fx, fy, s, d, extra = {}) => keys.push({ t, fx, fy, s, d, ...extra });
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text, maxW: 640 });

  // 1 Map
  K(0, CX, CY, W, 0, wide);
  K(b0.cue("map") - 0.2, 620, 760, Z, 1.4, zoom);
  R(b0.cue("flights") - 0.1, b0.e + 0.1, [520, 640, 560, 340]);
  L(b0.n + 0.15, b0.e - 0.05, "1  Map", "Every place, every flight.");

  // 2 Log a flight: tap plus
  K(b1.s, 960, 560, [0.66, 0.78], 1.1, zoom);
  rings.push({ t0: b1.cue("plus") + 0.05, t1: b1.cue("plus") + 1.0, ripple: [1098, 409] });
  R(b1.cue("plus") + 0.3, b1.cue("airports") + 0.6, [1030, 341, 136, 136]);
  R(b1.cue("route") - 0.1, b1.e + 0.1, [500, 540, 620, 470]);
  K(b1.cue("route") - 0.3, 760, 760, [0.58, 0.72], 1.3, zoom);
  L(b1.n + 0.15, b1.e - 0.05, "2  Flights", "Tap plus, enter two airports.");

  // 3 Globe
  K(b2.s, CX, CY, [0.34, 0.5], 1.0, wide);
  K(b2.s + 1.1, 620, 1150, [0.46, 0.56], 3.0, { ax: [0.7, 0.5], ay: [0.46, 0.4] });
  L(b2.n + 0.15, b2.e - 0.05, "3  Globe", "The same history in 3D.");

  // 4 Stats
  K(b3.s, CX, CY, W, 1.0, wide);
  K(b3.cue("countries") - 0.3, 616, 1380, [0.6, 0.7], 1.2, zoom);
  R(b3.cue("countries") - 0.1, b3.e + 0.1, [70, 1085, 1090, 540]);
  L(b3.n + 0.15, b3.e - 0.05, "4  Stats", "Countries, continents, trips.");

  // 5 Goals
  K(b4.s, CX, CY, W, 1.0, wide);
  K(b4.cue("goal") - 0.3, 603, 620, Z, 1.2, zoom);
  rings.push({ t0: b4.cue("goal") + 0.2, t1: b4.cue("goal") + 1.1, ripple: [1091, 252] });
  R(b4.cue("watch") - 0.2, b4.e + 0.1, [48, 555, 1110, 246]);
  L(b4.n + 0.15, b4.e - 0.05, "5  Goals", "Where you are going next.");

  const ENDs = b4.e;
  K(ENDs - 0.25, CX, CY, [0.3, 0.44], 0.9, wide);

  const stills = [
    { ...IMG.map, t0: 0 },
    { ...IMG.globe, t0: b2.s - 0.1 },
    { ...IMG.stats, t0: b3.s - 0.1 },
    { ...IMG.goals, t0: b4.s - 0.1 },
  ];
  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...IMG.map, t0: 0 }],
    keys: [
      { t: 0, fx: CX, fy: CY, s: [0.34], d: 0, nodrift: true, ax: [0.5], ay: [0.5] },
      { t: 0.5, fx: 660, fy: 720, s: [0.62], d: 1.5, ax: [0.5], ay: [0.46] },
      { t: 3.8, fx: 1000, fy: 480, s: [0.66], d: 1.4, ax: [0.5], ay: [0.46] },
      { t: 6.7, fx: CX, fy: CY, s: [0.34], d: 1.1, nodrift: true, ax: [0.5], ay: [0.5] },
    ],
    rings: [
      { t0: 1.0, t1: 3.5, rect: [520, 640, 560, 340] },
      { t0: 4.6, t1: 5.6, ripple: [1098, 409] },
    ],
  };
  return finish(
    {
      id: "globepin-promo", frame: "phone",
      title: { name: "GlobePin", sub: "Track every place you have been.", icon: "brand/globepin-icon.png", iconRadius: 0.22 },
      end: { pill: "Free on the App Store", url: "purplelink.llc/globepin" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b0.e - 0.6,
    },
    B, 5, timing,
  );
}
