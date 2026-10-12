// Panely: two kinds of picture, neither a recording of anyone's screen.
//  - the real Settings window, drawn by the app's own SwiftUI view rendered offscreen with invented sample data
//    (video/panely-shots/render.sh and compose_settings.py), shown in the mac frame;
//  - a drawn desktop with invented windows (src/PanelyDesk.jsx, specs in src/panely/desk.js), with tile sizes from the
//    same arithmetic as the app. It is an illustration of the idea, and every lower third says so.
// Facts from site/panely/index.html and site/llms.txt.
import { beats, finish } from "../stillplan.js";
import { DESK, ignoreRowRect } from "../panely/geom.js";
import { deskDrag, deskLayouts, deskIgnore, afterDrag } from "../panely/desk.js";

export const media = {
  "panely-icon.png": "assets/panely/icon.png",
  "pn-recorder.png": "assets/panely/settings-recorder.png",
  "pn-areas.png": "assets/panely/settings-custom-areas.png",
};

// settings stills: source px, shown 720 px tall (window px)
const mk = (sw, sh) => ({ sw, sh, h: 720, w: Math.round((sw * 720) / sh), k: Math.round((sw * 720) / sh) / sw });
const SR = mk(1080, 896); // recorder: 56 px title bar + 840
const SA = mk(1080, 856); // areas:    56 px title bar + 800
const rcS = (I, x, y, w, h) => [x * I.k, y * I.k, w * I.k, h * I.k];
const stillS = (name, I, t0) => ({ src: `media/${name}`, w: I.w, h: I.h, t0 });
const stillDesk = (spec, t0) => ({ desk: spec, w: DESK.W, h: DESK.H, t0 });
const centerD = [DESK.W / 2, DESK.H / 2];

// camera key on the desk: fx, fy in desk px; s = [16:9, 9:16]
export const kd = (t, fx, fy, s, d, extra = {}) => ({ t, fx, fy, s, d, ...extra });

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4], { start: 1.3, lead: 0.15, tail: 0.2, hold: { 1: 4.9, 2: 4.4, 4: 3.9 } });
  const [b0, b1, b2, b3, b4] = B;
  const keys = [];
  const rings = [];
  const lower = [];
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text, maxW: 1300 });
  const AY = { ay: [0.42, 0.4] };
  const Z = { ay: [0.4, 0.4] };
  const ZN = { ay: [0.4, 0.4], ax: [0.62, 0.5] };

  // ---- 1 + 2: loose windows, then a shortcut and two drags (one continuous desk) ----------------------
  const shortcut = b1.cue("shortcut") - 0.15;
  const drag1 = b1.cue("drag") + 0.25;
  const drag2 = drag1 + 1.4;
  const drag = deskDrag({ shortcut, drag1, drag2 });
  keys.push(kd(0, ...centerD, [1.0, 0.7], 0, AY));
  keys.push(kd(b1.s, ...centerD, [0.96, 0.68], 1.2, AY));
  L(b0.n + 0.15, b0.e - 0.1, "1  Snapping  ·  Illustration", "Windows snap into place.");
  L(b1.n + 0.15, b1.e - 0.1, "2  Shortcut or drag  ·  Illustration", "A preview shows where it will land.");

  // ---- 3: halves, thirds, quarters, sixths, then the area editor ------------------------------------------
  const t2 = b2.s - 0.1;
  const c = (p) => b2.cue(p) - t2;
  const layouts = deskLayouts(
    [["halves", c("halves") - 0.3], ["thirds", c("thirds") - 0.3], ["quarters", c("quarters") - 0.3], ["sixths", c("sixths") - 0.3]],
    { start: afterDrag() },
  );
  const tArea = b2.cue("area") - 0.2;
  keys.push(kd(t2, ...centerD, [0.96, 0.68], 0.8, AY));
  L(b2.n + 0.15, tArea - 0.15, "3  Layouts  ·  Illustration", "Halves, thirds, quarters, sixths.");

  const A = stillS("pn-areas.png", SA, tArea);
  keys.push({ t: tArea, fx: A.w / 2, fy: A.h / 2, s: [0.96, 0.95], d: 0.9, ay: [0.39, 0.38] });
  keys.push({ t: tArea + 0.5, fx: A.w / 2, fy: A.h * 0.44, s: [1.0, 1.0], d: 1.1, ay: [0.39, 0.38] });
  R(tArea + 0.3, b2.e + 0.1, rcS(SA, 40, 240, 1000, 272));
  L(tArea + 0.1, b2.e - 0.1, "4  Custom areas  ·  Sample data", "Left, top, width, height as percentages.");

  // ---- 4: shortcut recorder ----------------------------------------------------------------------------
  const S = stillS("pn-recorder.png", SR, b3.s - 0.1);
  keys.push({ t: b3.s - 0.1, fx: S.w / 2, fy: S.h / 2, s: [0.96, 0.95], d: 1.0, ay: [0.39, 0.38] });
  keys.push({ t: b3.cue("click") - 0.3, fx: S.w * 0.62, fy: 461 * SR.k, s: [1.12, 1.0], d: 1.2, ay: [0.39, 0.38] });
  R(b3.cue("click") - 0.05, b3.e + 0.1, rcS(SR, 40, 425, 1000, 72));
  L(b3.n + 0.15, b3.e - 0.1, "5  Shortcuts  ·  Sample data", "Click a shortcut, press the keys you want.");

  // ---- 5: ignored apps ------------------------------------------------------------------------------------
  const t4 = b4.s - 0.1;
  const o = b4.n - t4 + 0.05;
  const ign = deskIgnore({ open: o, hover: b4.cue("never") - t4 - 0.1, check: b4.cue("never") - t4 + 0.45, close: b4.cue("never") - t4 + 1.1, k1: b4.cue("never") - t4 + 1.3, k2: b4.cue("never") - t4 + 2.0 });
  const row = ignoreRowRect();
  keys.push(kd(t4, ...centerD, [0.96, 0.68], 0.8, AY));
  keys.push(kd(t4 + o + 0.1, 900, 330, [1.28, 0.92], 1.1, { ay: [0.44, 0.4], ax: [0.42, 0.5] }));
  keys.push(kd(b4.cue("never") + 1.5, ...centerD, [0.96, 0.68], 1.0, AY));
  R(b4.cue("never") - 0.1, b4.cue("never") + 1.1, row);
  L(b4.n + 0.15, b4.e - 0.1, "6  Ignored apps  ·  Illustration", "Chosen apps are never moved.");

  // desk windows move in desk-local time; the plan's rings are in window px, which is desk px for desk stills
  const stills = [stillDesk(drag, 0), stillDesk(layouts, t2), A, S, stillDesk(ign, t4)];

  const hero = heroPlan();
  return finish(
    {
      id: "panely-promo",
      frame: "mac",
      introAt: 1.15,
      titleT1: 1.05,
      title: { name: "Panely", sub: "Window snapping for Mac.", icon: "media/panely-icon.png", iconRadius: 0.22 },
      end: { pill: "$9.99 once. 7-day free trial.", url: "purplelink.llc/panely" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b2.cue("sixths") + 0.35,
    },
    B, 5, timing, { endLead: 0.2, endTail: 0.35 },
  );
}

// 8 second silent loop: halves, thirds, quarters, sixths, one custom area, back to halves. Static at both ends so the cross-fade is invisible.
export function heroPlan() {
  const spec = deskLayouts([["thirds", 1.0], ["quarters", 2.3], ["sixths", 3.6], ["area", 4.9]], { start: "halves", loopBack: { name: "halves", t: 6.2 } });
  return {
    T: 8,
    XF: 0.6,
    stills: [stillDesk(spec, 0)],
    keys: [{ t: 0, fx: DESK.W / 2, fy: DESK.H / 2, s: [1.02], d: 0, nodrift: true, ay: [0.46] }],
    rings: [],
  };
}
