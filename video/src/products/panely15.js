// Panely, 15 second cut: title, shortcut and drag, layouts, end card. Same drawn desk as panely.js, no Settings window.
import { beats, finish } from "../stillplan.js";
import { DESK } from "../panely/geom.js";
import { deskDrag, deskLayouts, afterDrag } from "../panely/desk.js";
import { media as fullMedia, heroPlan } from "./panely.js";

export const media = { "panely-icon.png": fullMedia["panely-icon.png"] };
const stillDesk = (spec, t0) => ({ desk: spec, w: DESK.W, h: DESK.H, t0 });
const C = [DESK.W / 2, DESK.H / 2];

export function build(timing) {
  const B = beats(timing, [0, 1], { start: 1.35, lead: 0.15, tail: 0.2, hold: { 0: 4.5, 1: 3.8 } });
  const [b0, b1] = B;
  const shortcut = b0.cue("shortcut") - 0.15;
  const drag1 = b0.cue("drag") + 0.2;
  const drag = deskDrag({ shortcut, drag1, drag2: drag1 + 1.5 });
  const t1 = b1.s - 0.1;
  const c = (p) => b1.cue(p) - t1 - 0.3;
  const layouts = deskLayouts([["halves", c("halves") - 0.3], ["thirds", c("thirds") - 0.3], ["quarters", c("quarters") - 0.3], ["sixths", c("sixths") - 0.3]], { start: afterDrag() });
  const AY = { ay: [0.42, 0.4] };
  const keys = [
    { t: 0, fx: C[0], fy: C[1], s: [1.0, 0.7], d: 0, ...AY },
    { t: b0.s, fx: C[0], fy: C[1], s: [0.96, 0.68], d: 1.2, ...AY },
  ];
  const lower = [
    { t0: b0.n + 0.15, t1: b0.e - 0.1, tag: "Shortcut or drag  ·  Illustration", text: "A preview shows where it will land.", maxW: 1300 },
    { t0: b1.n + 0.15, t1: b1.e - 0.1, tag: "Layouts  ·  Illustration", text: "Halves, thirds, quarters, sixths.", maxW: 1300 },
  ];
  return finish(
    {
      id: "panely-promo-15",
      frame: "mac",
      introAt: 1.0,
      titleT1: 0.95,
      title: { name: "Panely", sub: "Window snapping for Mac.", icon: "media/panely-icon.png", iconRadius: 0.22 },
      end: { pill: "$9.99 once. 7-day free trial.", url: "purplelink.llc/panely" },
      stills: [stillDesk(drag, 0), stillDesk(layouts, t1)],
      keys, rings: [], lower, cursors: [], hero: heroPlan(),
      poster: b1.cue("sixths") + 0.35,
    },
    B, 2, timing, { endLead: 0.2, endTail: 0.3 },
  );
}
