// Helpers shared by the still-driven product plans (src/products/*.js).
//
// A plan is pure data computed from the narration timing:
//   frame: "mac" | "phone" | "browser"      url: text in the browser bar
//   title: { name, sub, icon, iconRadius }  end: { pill, url }
//   stills: [{ src, w, h, view: {w,h}, t0, scroll: [{t, y, d}] }]   window px; view = window content box
//   keys:   camera keys in window px (see camAt in V2.jsx), s = [16x9, 9x16]
//   rings:  { t0, t1, rect:[x,y,w,h] } or { t0, t1, ripple:[cx,cy] }
//   lower:  lower thirds { t0, t1, tag, text, maxW }
//   cursors:[{ t0, t1, pts: [[t, x, y], ...] }]     mac arrow cursor inside the window
//   audio:  [{ i, at }]                              narration scene i starts at `at`
//   ENDs, total, poster (seconds), hero: { T, XF, stills, keys, rings }

export const cue = (sc, prefix) => {
  const w = sc.words.find((x) => (x.display || x.word).toLowerCase().replace(/[^a-z0-9]/g, "").startsWith(prefix));
  return w ? w.start : 0;
};

// Sequential beats. Each beat starts where the previous ended; narration i starts `lead` after the beat
// and the beat holds `tail` after the narration. hold[i] is a minimum beat length.
export function beats(timing, order, { start = 2.6, lead = 0.3, tail = 0.55, hold = {} } = {}) {
  let t = start;
  const out = [];
  for (const i of order) {
    const d = timing.scenes[i].duration;
    const n = t + lead;
    const e = Math.max(n + d + tail, t + (hold[i] || 0));
    out.push({ i, s: t, n, e, d, sc: timing.scenes[i], cue: (p) => n + cue(timing.scenes[i], p) });
    t = e;
  }
  return out;
}

export function finish(plan, B, endIndex, timing, { endLead = 0.3, endTail = 0.7 } = {}) {
  const ENDs = B[B.length - 1].e;
  const nEnd = ENDs + endLead;
  plan.ENDs = ENDs;
  plan.audio = [...B.map((b) => ({ i: b.i, at: b.n })), { i: endIndex, at: nEnd }];
  plan.total = nEnd + timing.scenes[endIndex].duration + endTail;
  return plan;
}

// Frame presets: wide camera scale per format for a window of the given width/height.
export const WIDE = {
  mac1440: [0.86, 0.66],
  browser1440: [0.86, 0.7],
  browser1280: [0.96, 0.78],
  phone: [0.32, 0.48],
};
export const PHONE_AX = { wide: [0.66, 0.5], zoom: [0.77, 0.5] };
export const PHONE_AY = { wide: [0.47, 0.35], zoom: [0.46, 0.35] };
