// Outbound Veil: real screen footage (a fictional client note typed into a plain text field in Chrome, with the
// app's highlights, findings list and Redact all), one 1100 x 579 window. Facts from site/outbound-veil/index.html.
import { beats, finish } from "../stillplan.js";

export const media = {
  "ov-marked.png": "/private/tmp/claude-501/-Volumes-Extreme-SSD-Purplelink-LLC/fbe7b481-1525-4503-93ca-ca5790689a49/scratchpad/capture/ov-marked.png",
  "outbound-veil-demo.mp4": "/private/tmp/claude-501/-Volumes-Extreme-SSD-Purplelink-LLC/fbe7b481-1525-4503-93ca-ca5790689a49/scratchpad/capture/outbound-veil-demo.mp4",
};

const F = { src: "media/ov-marked.png", w: 1100, h: 579 };
const V = { src: "media/outbound-veil-demo.mp4", w: 1100, h: 579, video: true };
const W = [1.24, 0.9]; // wide camera scale per format

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3], { start: 2.5, lead: 0.3, tail: 0.5, hold: { 0: 3.6, 1: 7.2, 2: 6.4, 3: 7.8 } });
  const [b0, b1, b2, b3] = B;
  const keys = [];
  const rings = [];
  const lower = [];
  const K = (t, fx, fy, s, d, extra = {}) => keys.push({ t, fx, fy, s, d, ...extra });
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text });

  K(0, 550, 290, W, 0);
  // 1 typing: the field, then the name and date
  K(b1.s, 440, 210, [1.6, 1.25], 1.1, { ay: [0.4, 0.4] });
  K(b1.e - 2.2, 560, 235, [1.4, 1.1], 1.2, { ay: [0.42, 0.4] });
  L(b1.n + 0.2, b1.e - 0.1, "1  Live check", "It reads the field as you type.");
  // 2 everything marked, badge
  K(b2.s, 550, 290, W, 1.0);
  K(b2.cue("card") - 0.3, 985, 450, [1.7, 1.35], 1.1, { ay: [0.55, 0.5] });
  R(b2.cue("card") - 0.1, b2.e + 0.1, [950, 426, 70, 42]);
  L(b2.n + 0.2, b2.e - 0.1, "2  Marked in place", "Highlights stay on the text as you edit.");
  // 3 findings list, redact all
  K(b3.s, 740, 240, [1.25, 1.0], 1.1, { ay: [0.5, 0.45] });
  K(b3.cue("redact") + 1.4, 550, 270, [1.1, 0.86], 1.1, { ay: [0.5, 0.44] });
  R(b3.n + 0.4, b3.cue("redact") - 0.2, [705, 82, 322, 340]);
  R(b3.cue("redact") - 0.5, b3.cue("redact") + 0.3, [716, 385, 90, 26]);
  L(b3.n + 0.2, b3.e - 0.1, "3  Your call", "Redact all, or ignore a finding.");

  const ENDs = b3.e;
  K(ENDs - 0.25, 550, 290, [0.95, 0.72], 0.9);

  // footage times from the recording (s): typing 2.0 to 13, all marked about 13.8, list open 16, Redact all 20.3
  const stills = [
    { ...V, t0: 0, trim: 0.4, rate: 0.955 }, // plays straight through beats 0 and 1 (typing, live marks)
    { ...F, t0: b2.s - 0.1 }, // beat 2 holds the all-marked state
    { ...V, t0: b3.s - 0.1, trim: 15.7 },
    { ...V, t0: b3.cue("redact") - 0.9, trim: 19.3 },
  ];

  const hero = {
    T: 8,
    XF: 0.6,
    stills: [{ ...V, t0: 0, trim: 11.5 }],
    keys: [
      { t: 0, fx: 550, fy: 290, s: [1.0], d: 0, nodrift: true },
      { t: 0.5, fx: 480, fy: 250, s: [1.45], d: 1.3, ay: [0.42] },
      { t: 4.2, fx: 820, fy: 270, s: [1.4], d: 1.3, ay: [0.45] },
      { t: 7.0, fx: 550, fy: 290, s: [1.0], d: 1.0, nodrift: true, ay: [0.44] },
    ],
    rings: [{ t0: 4.6, t1: 7.0, rect: [705, 82, 322, 340] }],
  };

  return finish(
    {
      id: "outbound-veil-promo",
      frame: "mac",
      title: { name: "Outbound Veil", sub: "Check what you type before you send it.", icon: "brand/outbound-veil-icon.png", iconRadius: 0.22 },
      end: { pill: "Free 7-day trial, then $29", url: "purplelink.llc/outbound-veil" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b2.n + 2.5,
    },
    B, 4, timing,
  );
}
