// haea Short (9:16, under 60 s): the long cut's screenshots, six beats.
import { beats, finish } from "../stillplan.js";
import { WL, haeaMedia, IMG, R as RECT, mid } from "./haeashots.js";

export const media = haeaMedia;

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4, 5], { start: 2.4, lead: 0.3, tail: 0.45 });
  const [b0, b1, b2, b3, b4, b5] = B;
  const keys = [], rings = [], lower = [], stills = [];
  const wide = { ax: WL.ax.wide, ay: WL.ay.wide };
  const zoom = { ax: WL.ax.zoom, ay: WL.ay.zoom };
  const Z = [0.56, 0.62];
  const K = (t, rect, s, d) => { const [fx, fy] = mid(rect); keys.push({ t, fx, fy, s, d, ...zoom }); };
  const ring = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (b, tag, text) => lower.push({ t0: b.n + 0.15, t1: b.e - 0.1, tag, text });
  const S = (img, t0) => stills.push({ ...img, t0 });

  S(IMG.today, 0);
  keys.push({ t: 0, fx: 660, fy: 1434, s: WL.wide, d: 0, ...wide });
  K(b0.n + 1.0, RECT.today.briefing, [0.5, 0.55], 1.4);
  L(b0, "Apple Health", "A daily readiness briefing.");

  K(b1.s, RECT.today.briefing, Z, 1.0);
  ring(b1.n + 0.2, b1.cue("warning") - 0.3, RECT.today.ring);
  ring(b1.cue("warning") - 0.1, b1.e, RECT.today.warning);
  L(b1, "Today", "One score. One suggestion.");

  S(IMG.strength, b2.s - 0.1);
  K(b2.s, RECT.strength.summary, Z, 1.0);
  ring(b2.n + 0.2, b2.e, RECT.strength.level);
  L(b2, "Strength", "Volume, records, deload check.");

  S(IMG.route, b3.s - 0.1);
  K(b3.s, RECT.route.path, [0.5, 0.56], 1.0);
  ring(b3.n + 0.2, b3.e, RECT.route.distance);
  L(b3, "Running", "Plan a route on the map.");

  S(IMG.insights, b4.s - 0.1);
  K(b4.s, RECT.insights.picker, Z, 1.0);
  ring(b4.n + 0.2, b4.e, RECT.insights.drivers);
  L(b4, "Insights", "Which habits move your outcomes.");

  S(IMG.terms, b5.s - 0.1);
  K(b5.s, RECT.terms.notMedical, [0.5, 0.56], 1.0);
  ring(b5.n + 0.2, b5.e, RECT.terms.notMedical);
  L(b5, "On your iPhone", "General wellness, not medical advice.");

  const ENDs = b5.e;
  S(IMG.today, ENDs - 0.6);
  keys.push({ t: ENDs - 0.55, fx: 660, fy: 1434, s: [0.27, 0.4], d: 0.9, ...wide });

  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...IMG.today, t0: 0 }],
    keys: [
      { t: 0, fx: 660, fy: 1434, s: [0.3], d: 0, nodrift: true, ax: [0.5], ay: [0.5] },
      { t: 4, fx: 660, fy: 1434, s: [0.32], d: 3, ax: [0.5], ay: [0.5] },
    ],
    rings: [],
  };

  return finish(
    {
      id: "haea-short",
      frame: "phone",
      title: { name: "haea", sub: "Readiness, sleep and training, on your iPhone.", icon: "media/haea-icon.png", iconRadius: 0.22 },
      end: { pill: "Free on iPhone", url: "purplelink.llc/haea" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b1.e - 1.0,
    },
    B, 6, timing,
  );
}
