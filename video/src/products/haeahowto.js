// haea how-to (long, 16:9): iPhone frame, 1320x2868 simulator screenshots with demo data.
// Script and YouTube text: docs/video/haea-howto-script.md. Nothing on screen is a real person's data.
import { beats, finish } from "../stillplan.js";
import { WL, haeaMedia, IMG, R as RECT, mid } from "./haeashots.js";

export const media = haeaMedia;

export function build(timing) {
  const order = Array.from({ length: 14 }, (_, i) => i);
  const B = beats(timing, order, { start: 2.5, lead: 0.35, tail: 0.6 });
  const [b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13] = B;
  const keys = [], rings = [], lower = [], stills = [];
  const Z = WL.zoom;
  const wide = { ax: WL.ax.wide, ay: WL.ay.wide };
  const zoom = { ax: WL.ax.zoom, ay: WL.ay.zoom };
  const K = (t, rect, s, d, o = zoom) => { const [fx, fy] = mid(rect); keys.push({ t, fx, fy, s: [s[0] * 1.3, s[1]], d, ...o }); };
  const ring = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const tap = (t, rect) => rings.push({ t0: t, t1: t + 0.9, ripple: mid(rect) });
  const L = (b, tag, text) => lower.push({ t0: b.n + 0.15, t1: b.e - 0.1, tag, text, maxW: 660 });
  const S = (img, t0) => stills.push({ ...img, t0 });

  // 0 What it is
  S(IMG.today, 0);
  keys.push({ t: 0, fx: 660, fy: 1434, s: WL.wide, d: 0, ...wide });
  K(b0.n + 1.2, RECT.today.briefing, [0.5, 0.6], 1.6);
  L(b0, "haea", "A daily readiness briefing from Apple Health.");

  // 1 The briefing
  K(b1.s, RECT.today.briefing, [0.52, 0.62], 1.1);
  ring(b1.cue("score") - 0.1, b1.cue("suggestion") - 0.3, RECT.today.ring);
  ring(b1.cue("suggestion") - 0.1, b1.e, RECT.today.action);
  L(b1, "1  Today", "Readiness score and one suggestion.");

  // 2 Warning and today's health
  K(b2.s, RECT.today.warning, [0.52, 0.62], 1.0);
  ring(b2.cue("warning") - 0.1, b2.cue("health") - 0.3, RECT.today.warning);
  K(b2.cue("health") - 0.3, RECT.today.tiles, [0.5, 0.58], 1.0);
  ring(b2.cue("health"), b2.e, RECT.today.tiles);
  L(b2, "Warnings and trends", "A warning only when something stands out.");

  // 3 Where the data comes from
  K(b3.s, RECT.today.tiles, [0.5, 0.58], 1.0);
  ring(b3.cue("sleep") - 0.1, b3.e, RECT.today.tiles);
  L(b3, "Apple Health", "Sleep, heart rate, HRV, workouts, weight.");

  // 4 Strength: start workout
  S(IMG.strength, b4.s - 0.1);
  K(b4.s, RECT.strength.summary, Z, 1.0);
  tap(b4.cue("start") + 0.1, RECT.strength.start);
  ring(b4.cue("start") - 0.1, b4.e, RECT.strength.start);
  L(b4, "2  Strength", "Start workout: your routines or a program.");

  // 5 Strength: level, volume, deload
  K(b5.s, RECT.strength.level, [0.5, 0.58], 1.0);
  ring(b5.cue("level") - 0.2, b5.cue("deload") - 0.3, RECT.strength.level);
  K(b5.cue("deload") - 0.3, RECT.strength.volume, [0.5, 0.58], 1.0);
  ring(b5.cue("deload") - 0.1, b5.e, RECT.strength.volume);
  L(b5, "Volume, records, deload", "Strength level and a deload check.");

  // 6 Running
  S(IMG.running, b6.s - 0.1);
  K(b6.s, RECT.running.allTime, Z, 1.0);
  K(b6.cue("suggests") - 0.3, RECT.running.week, [0.5, 0.58], 1.0);
  ring(b6.cue("suggests"), b6.cue("training") - 0.3, RECT.running.suggested);
  K(b6.cue("training") - 0.3, RECT.running.load, [0.5, 0.58], 1.0);
  ring(b6.cue("training") - 0.1, b6.e, RECT.running.load);
  L(b6, "3  Running", "iPhone or Apple Watch. Training load.");

  // 7 Route planning
  S(IMG.route, b7.s - 0.1);
  K(b7.s, RECT.route.path, [0.5, 0.6], 1.0);
  ring(b7.cue("tap") - 0.1, b7.cue("follow") - 0.3, RECT.route.path);
  ring(b7.cue("follow") - 0.1, b7.cue("distance") - 0.3, RECT.route.follow);
  K(b7.cue("distance") - 0.3, RECT.route.bar, [0.52, 0.6], 1.0);
  ring(b7.cue("distance") - 0.1, b7.e, RECT.route.distance);
  L(b7, "Route planning", "Tap points on the map. Follow paths.");

  // 8 Insights: pick an outcome, ranked habits
  S(IMG.insights, b8.s - 0.1);
  K(b8.s, RECT.insights.picker, Z, 1.0);
  ring(b8.cue("pick") - 0.1, b8.cue("ranks") - 0.3, RECT.insights.picker);
  K(b8.cue("ranks") - 0.3, RECT.insights.drivers, [0.5, 0.58], 1.0);
  ring(b8.cue("ranks") - 0.1, b8.e, RECT.insights.drivers);
  L(b8, "4  Insights", "Which habits move sleep, pace, weight, mood.");

  // 9 A link is not proof; small test
  K(b9.s, RECT.insights.chart, [0.5, 0.58], 1.0);
  K(b9.cue("try") - 0.4, RECT.insights.test, Z, 0.9);
  ring(b9.cue("try") - 0.2, b9.e, RECT.insights.test);
  L(b9, "Not proof", "Try a small test to check a change.");

  // 10 Coach
  S(IMG.coach, b10.s - 0.1);
  K(b10.s, RECT.coach.chips, Z, 1.0);
  ring(b10.n + 0.4, b10.e, RECT.coach.chips);
  L(b10, "Coach", "On the device, with Apple Intelligence.");

  // 11 Private
  S(IMG.today, b11.s - 0.1);
  keys.push({ t: b11.s, fx: 660, fy: 1434, s: [0.29 * 1.15, 0.44], d: 1.0, ...wide });
  L(b11, "Private", "No account. No cloud sync. No ads.");

  // 12 Not medical advice
  S(IMG.terms, b12.s - 0.1);
  K(b12.s, RECT.terms.notMedical, Z, 1.0);
  ring(b12.n + 0.2, b12.e, RECT.terms.notMedical);
  L(b12, "General wellness", "Not medical advice.");

  // 13 Free, optional Premium
  S(IMG.today, b13.s - 0.1);
  keys.push({ t: b13.s, fx: 660, fy: 1434, s: [0.29 * 1.15, 0.44], d: 1.0, ...wide });
  L(b13, "Free, with optional Premium", "Briefing, strength and running are free.");

  const ENDs = b13.e;
  S(IMG.today, ENDs - 0.6);
  keys.push({ t: ENDs - 0.55, fx: 660, fy: 1434, s: [0.27, 0.4], d: 0.9, ...wide });

  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...IMG.today, t0: 0 }],
    keys: [
      { t: 0, fx: 660, fy: 1434, s: [0.3], d: 0, nodrift: true, ax: [0.5], ay: [0.5] },
      { t: 0.5, ...xy(RECT.today.briefing), s: [0.55], d: 1.5, ax: [0.5], ay: [0.46] },
      { t: 6.7, fx: 660, fy: 1434, s: [0.3], d: 1.1, nodrift: true, ax: [0.5], ay: [0.5] },
    ],
    rings: [{ t0: 1.5, t1: 4, rect: RECT.today.ring }],
  };

  return finish(
    {
      id: "haea-howto",
      frame: "phone",
      title: { name: "haea", sub: "Readiness, sleep and training, on your iPhone.", icon: "media/haea-icon.png", iconRadius: 0.22 },
      end: { pill: "Free on iPhone", url: "purplelink.llc/haea" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b1.e - 1.0,
    },
    B, 14, timing,
  );
}

function xy(rect) { const [fx, fy] = mid(rect); return { fx, fy }; }
