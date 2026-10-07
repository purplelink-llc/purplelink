// Keyfeel: real captures of the running app (version 1.2.0, light appearance), shown in the mac frame.
// Captured with screencapture on 2026-10-07: the Settings window (-l, one window id, tab by tab), and the menu-bar
// dropdown (a region capture of the menu, cropped to the menu and the Keyfeel icon, set on the menu bar's own colour).
// Facts from site/keyfeel/index.html. The sound bed is made from the recordings bundled in the app (see mixbed.py).
import { beats, finish } from "../stillplan.js";

export const media = {
  "keyfeel-icon.png": "assets/keyfeel/icon.png",
  "kf-dropdown.webp": "assets/keyfeel/dropdown.webp",
  "kf-sounds.webp": "assets/keyfeel/sounds.webp",
  "kf-input.webp": "assets/keyfeel/input.webp",
  "kf-feel.webp": "assets/keyfeel/feel.webp",
  "kf-apps.webp": "assets/keyfeel/apps.webp",
  "kf-permission.webp": "assets/keyfeel/permission.webp",
};

// sw, sh: source pixels. h: window height on stage (aspect kept).
const img = (name, sw, sh, h) => ({ src: `media/kf-${name}.webp`, sw, sh, h, w: Math.round((sw * h) / sh) });
const DD = img("dropdown", 640, 862, 800);
const SO = img("sounds", 1208, 660, 640);
const IN = img("input", 1208, 990, 740);
const FE = img("feel", 1208, 945, 720);
const AP = img("apps", 1208, 960, 720);
const PE = img("permission", 1130, 290, 282);

const px = (I, x, y) => [x * (I.w / I.sw), y * (I.h / I.sh)];
const rc = (I, x, y, w, h) => {
  const k = I.w / I.sw;
  return [x * k, y * k, w * k, h * k];
};
const still = (I, t0) => ({ src: I.src, w: I.w, h: I.h, t0 });

// ---- sound bed: the app's own recordings --------------------------------------------------------------------------
const SAMP = "assets/keyfeel/samples";
const COUNT = { tactile: 15, brown: 1, dome: 16 };
const num = (i) => String(i).padStart(2, "0");
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function bed(plan, cues) {
  const R = rng(20261007);
  const ev = [];
  const pick = (n) => 1 + Math.floor(R() * n);
  // one key press and its release, a different recording each time, panned left to right across the keyboard
  const key = (t, pack, gain, space = false) => {
    const pan = -0.7 + 1.4 * R();
    const rate = 1 + (R() - 0.5) * 0.07;
    if (space) {
      ev.push({ t, file: `${SAMP}/${pack}/space-press-0${pick(2)}.wav`, gain, pan: 0, rate });
      ev.push({ t: t + 0.09, file: `${SAMP}/${pack}/space-release-0${pick(2)}.wav`, gain: gain * 0.7, pan: 0, rate });
      return;
    }
    ev.push({ t, file: `${SAMP}/${pack}/press-${num(pick(COUNT[pack]))}.wav`, gain, pan, rate });
    ev.push({ t: t + 0.07 + R() * 0.05, file: `${SAMP}/${pack}/release-${num(pick(COUNT[pack]))}.wav`, gain: gain * 0.7, pan, rate });
  };
  // typing rhythm: short runs with small gaps, now and then a space bar
  const typing = (t0, t1, pack, gain) => {
    let t = t0;
    let n = 0;
    while (t < t1) {
      key(t, pack, gain * (0.85 + R() * 0.3), n % 6 === 5);
      n++;
      t += n % 6 === 0 ? 0.3 + R() * 0.15 : 0.11 + R() * 0.1;
    }
  };
  const burst = (t0, pack, count, gain) => {
    let t = t0;
    for (let i = 0; i < count; i++) {
      key(t, pack, gain * (0.9 + R() * 0.2));
      t += 0.1 + R() * 0.07;
    }
  };

  // 1  typing starts under the title card and carries on, quietly, under the first line
  typing(cues.b0.s - 0.7, cues.b0.n + 2.7, "tactile", 0.62);
  // 2  each profile plays as it is named
  burst(cues.b1.cue("tactile") + 0.02, "tactile", 3, 0.6);
  burst(cues.b1.cue("cherry") + 0.02, "brown", 3, 0.6);
  burst(cues.b1.cue("dome") + 0.02, "dome", 4, 0.6);
  // 3  two mouse clicks (press and release), then a scroll flick that slows down
  const click = (t, g) => {
    ev.push({ t, file: `${SAMP}/mouse/press-01.wav`, gain: g, pan: 0, rate: 1 });
    ev.push({ t: t + 0.1, file: `${SAMP}/mouse/release-01.wav`, gain: g * 0.7, pan: 0, rate: 1 });
  };
  const c0 = cues.b2.cue("clicks");
  click(c0, 0.7);
  click(c0 + 0.5, 0.7);
  let ts = cues.b2.cue("scrolling") + 0.05;
  let gap = 0.035;
  for (let i = 0; i < 16; i++) {
    ev.push({ t: ts, file: `${SAMP}/scroll/brush-${num(pick(21))}.wav`, gain: 0.5 * (1 - i * 0.025), pan: 0.1, rate: 1 + (R() - 0.5) * 0.05 });
    ts += gap;
    gap *= 1.17;
  }
  // 4  typing runs until the narration says "silent", then the bed goes quiet
  typing(cues.b3.n - 1.25, cues.b3.n + 0.1, "tactile", 0.6);

  const duck = plan.audio.map((a) => [a.at - 0.05, a.at + cues.dur[a.i] + 0.05]);
  return { duckGain: 0.55, duck, events: ev };
}

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4], { start: 1.7, lead: 0.15, tail: 0.15 });
  const [b0, b1, b2, b3, b4] = B;
  const keys = [];
  const rings = [];
  const lower = [];
  const K = (t, I, sx, sy, s, d, extra = {}) => {
    const [fx, fy] = sx == null ? [I.w / 2, I.h / 2] : px(I, sx, sy);
    keys.push({ t, fx, fy, s, d, ...extra });
  };
  const R = (t0, t1, I, x, y, w, h) => rings.push({ t0, t1, rect: rc(I, x, y, w, h) });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text, maxW: 1300 });
  const AY = { ay: [0.43, 0.4] };
  const Z = { ay: [0.4, 0.4] };
  const ZN = { ay: [0.4, 0.4], ax: [0.6, 0.5] }; // narrow window: sit right of centre so the lower third stays clear

  // 1 menu-bar icon and its dropdown
  K(0, DD, null, null, [1.0, 0.95], 0, { ay: [0.44, 0.4], ax: [0.6, 0.5] });
  K(b0.cue("keyfeel") - 0.3, DD, 320, 200, [1.5, 1.15], 1.3, ZN);
  R(b0.cue("keyfeel") - 0.1, b0.cue("switch") - 0.1, DD, 34, 6, 94, 54);
  K(b0.cue("switch") - 0.4, DD, 320, 400, [1.4, 1.1], 1.3, ZN);
  R(b0.cue("switch") - 0.05, b0.e + 0.1, DD, 36, 322, 568, 52);
  L(b0.n + 0.15, b0.e - 0.1, "1  Menu bar", "Runs in the menu bar.");

  // 2 profiles
  K(b1.s, SO, null, null, [1.0, 0.88], 1.0, AY);
  K(b1.cue("tactile") - 0.3, SO, null, null, [1.15, 0.88], 1.3, AY);
  R(b1.cue("tactile") - 0.1, b1.cue("cherry") - 0.1, SO, 70, 322, 1068, 104);
  R(b1.cue("cherry") - 0.05, b1.cue("dome") - 0.1, SO, 70, 436, 1068, 88);
  R(b1.cue("dome") - 0.05, b1.e - 0.15, SO, 70, 534, 1068, 104);
  L(b1.n + 0.15, b1.e - 0.1, "2  Profiles", "Recorded Tactile, Cherry MX Brown and Dome.");

  // 3 mouse and scroll, then trackpad haptics
  const tFE = b2.cue("optional") - 0.35;
  K(b2.s, IN, null, null, [1.0, 1.05], 1.0, AY);
  K(b2.cue("clicks") - 0.35, IN, 600, 660, [1.3, 1.25], 1.3, Z);
  R(b2.cue("clicks") - 0.1, b2.cue("scrolling") - 0.1, IN, 70, 592, 1068, 156);
  R(b2.cue("scrolling") - 0.05, tFE - 0.05, IN, 70, 746, 1068, 78);
  K(b2.cue("scrolling") - 0.3, IN, 600, 760, [1.3, 1.25], 1.0, Z);
  K(tFE - 0.05, FE, null, null, [1.0, 1.05], 0.9, AY);
  K(b2.cue("trackpad") - 0.4, FE, 600, 400, [1.25, 1.2], 1.2, Z);
  R(b2.cue("trackpad") - 0.1, b2.e - 0.15, FE, 70, 240, 1068, 410);
  L(b2.n + 0.15, tFE - 0.1, "3  Mouse and scroll", "Click sounds and scroll ticks.");
  L(tFE + 0.1, b2.e - 0.1, "4  Trackpad", "Optional haptics on scroll and click.");

  // 4 per-app silence and the microphone
  K(b3.s, AP, null, null, [1.0, 1.05], 1.0, AY);
  K(b3.cue("apps") - 0.4, AP, 600, 320, [1.25, 1.2], 1.3, Z);
  R(b3.cue("apps") - 0.1, b3.cue("microphone") - 0.2, AP, 70, 240, 1068, 160);
  K(b3.cue("microphone") - 0.4, AP, 600, 800, [1.25, 1.2], 1.2, Z);
  R(b3.cue("microphone") - 0.15, b3.e - 0.15, AP, 70, 798, 1068, 150);
  L(b3.n + 0.15, b3.e - 0.1, "5  Quiet", "Silent in chosen apps and during mic use.");

  // 5 privacy: key codes, offline
  K(b4.s, PE, null, null, [1.15, 0.9], 1.0, AY);
  K(b4.cue("codes") - 0.3, PE, 560, 150, [1.35, 0.9], 1.2, Z);
  R(b4.cue("codes") - 0.1, b4.cue("characters") - 0.1, PE, 40, 104, 1050, 64);
  R(b4.cue("characters") - 0.05, b4.e + 0.1, PE, 40, 196, 1050, 66);
  K(b4.cue("characters") - 0.4, PE, 560, 230, [1.35, 0.9], 1.0, Z);
  L(b4.n + 0.15, b4.e - 0.1, "6  Privacy", "Key codes, not characters. Works offline.");

  const ENDs = b4.e;
  K(ENDs - 0.25, PE, null, null, [1.0, 0.85], 0.9, AY);

  const stills = [still(DD, 0), still(SO, b1.s - 0.1), still(IN, b2.s - 0.1), { ...still(FE, tFE - 0.05), xf: 0.25 }, still(AP, b3.s - 0.1), still(PE, b4.s - 0.1)];

  const hero = {
    T: 8,
    XF: 0.6,
    stills: [still(SO, 0)],
    keys: [
      { t: 0, fx: SO.w / 2, fy: SO.h / 2, s: [1.0], d: 0, nodrift: true, ay: [0.44] },
      { t: 0.5, fx: SO.w / 2, fy: SO.h / 2, s: [1.25], d: 1.4, nodrift: true, ay: [0.46] },
      { t: 6.6, fx: SO.w / 2, fy: SO.h / 2, s: [1.0], d: 1.2, nodrift: true, ay: [0.44] },
    ],
    rings: [
      { t0: 0.9, t1: 2.7, rect: rc(SO, 70, 322, 1068, 104) },
      { t0: 2.8, t1: 4.5, rect: rc(SO, 70, 436, 1068, 88) },
      { t0: 4.6, t1: 6.5, rect: rc(SO, 70, 534, 1068, 104) },
    ],
  };

  const plan = finish(
    {
      id: "keyfeel-promo",
      frame: "mac",
      introAt: 1.15,
      titleT1: 1.05,
      title: { name: "Keyfeel", sub: "Real keyboard-switch sounds as you type.", icon: "media/keyfeel-icon.png", iconRadius: 0.22 },
      end: { pill: "$9.99 once. 7-day free trial.", url: "purplelink.llc/keyfeel" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b1.cue("cherry") + 0.9,
    },
    B, 5, timing, { endLead: 0.2, endTail: 0.35 },
  );
  plan.sfx = bed(plan, { b0, b1, b2, b3, dur: timing.scenes.map((s) => s.duration) });
  return plan;
}
