// Vitae: macOS window, five stills at 1440 wide. Facts from site/vitae/index.html.
import { beats, finish, WIDE } from "../stillplan.js";

export const media = {
  "vitae-dashboard.webp": "../site/assets/vitae-screens/dashboard-1440.webp",
  "vitae-submissions.webp": "../site/assets/vitae-screens/submissions-1440.webp",
  "vitae-grants.webp": "../site/assets/vitae-screens/grants-1440.webp",
  "vitae-cv.webp": "../site/assets/vitae-screens/cv-1440.webp",
  "vitae-tenure.webp": "../site/assets/vitae-screens/tenure-1440.webp",
};

const IMG = {
  dashboard: { src: "media/vitae-dashboard.webp", w: 1440, h: 747 },
  submissions: { src: "media/vitae-submissions.webp", w: 1440, h: 648 },
  grants: { src: "media/vitae-grants.webp", w: 1440, h: 782 },
  cv: { src: "media/vitae-cv.webp", w: 1440, h: 1065 },
  tenure: { src: "media/vitae-tenure.webp", w: 1440, h: 852 },
};

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4], { start: 2.5, lead: 0.3, tail: 0.45, hold: { 0: 4.6, 3: 5.2 } });
  const [b0, b1, b2, b3, b4] = B;
  const W = WIDE.mac1440;
  const Z = [1.55, 1.95];
  const keys = [];
  const rings = [];
  const lower = [];
  const cursors = [];
  const K = (t, fx, fy, s, d, extra = {}) => keys.push({ t, fx, fy, s, d, ...extra });
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text });

  // 1 Dashboard
  K(0, 720, 373, W, 0);
  K(b0.n + 0.9, 830, 128, [1.55, 1.3], 1.2, { ay: [0.4, 0.38] });
  K(b0.e - 1.6, 1130, 440, [1.45, 1.5], 1.1, { ay: [0.42, 0.4], fxv: 1090 });
  R(b0.n + 1.1, b0.e - 1.4, [240, 72, 1180, 104]);
  R(b0.e - 1.35, b0.e + 0.1, [838, 318, 582, 190]);
  L(b0.n + 0.15, b0.e - 0.05, "1  Dashboard", "Projects, submissions, funding, deadlines.");

  // 2 Submissions: click a row, then the detail pane
  K(b1.s, 720, 324, W, 0.9);
  K(b1.n + 0.6, 530, 300, [1.5, 1.6], 1.1, { ay: [0.46, 0.42], fxv: 560 });
  K(b1.cue("review") - 0.3, 1130, 250, [1.55, 1.7], 1.1, { ay: [0.44, 0.42], fxv: 1110 });
  K(b1.cue("estimate") - 0.3, 1130, 118, [1.65, 1.7], 1.0, { ay: [0.4, 0.4], fxv: 1110 });
  cursors.push({ t0: b1.n + 0.2, t1: b1.cue("review") - 0.2, pts: [[b1.n + 0.2, 640, 420], [b1.n + 1.0, 520, 292], [b1.cue("review"), 520, 292]] });
  rings.push({ t0: b1.n + 1.05, t1: b1.n + 1.9, ripple: [520, 292] });
  R(b1.n + 1.1, b1.cue("review") - 0.2, [240, 279, 580, 25]);
  R(b1.cue("review") - 0.1, b1.cue("estimate") - 0.2, [845, 205, 570, 105]);
  R(b1.cue("estimate") - 0.1, b1.e + 0.1, [845, 64, 570, 112]);
  L(b1.n + 0.15, b1.e - 0.05, "2  Submissions", "Every round, every decision.");

  // 3 Grants
  K(b2.s, 720, 391, W, 0.9);
  K(b2.n + 0.5, 400, 250, [1.5, 1.7], 1.1, { ay: [0.46, 0.42] });
  K(b2.cue("requested") - 0.35, 1065, 548, [1.55, 1.6], 1.1, { ay: [0.5, 0.42] });
  R(b2.n + 0.7, b2.cue("requested") - 0.3, [252, 62, 225, 44]);
  R(b2.cue("requested") - 0.2, b2.e + 0.1, [720, 455, 690, 186]);
  L(b2.n + 0.15, b2.e - 0.05, "3  Grants", "From proposal to final report.");

  // 4 CV
  K(b3.s, 720, 532, [0.72, 0.56], 0.9);
  K(b3.n + 0.4, 720, 330, [1.3, 1.3], 1.2, { ay: [0.44, 0.4] });
  K(b3.n + 2.4, 1100, 200, [1.5, 1.6], 1.0, { ay: [0.4, 0.38] });
  R(b3.n + 0.6, b3.n + 2.3, [562, 73, 293, 30]);
  R(b3.n + 2.5, b3.e + 0.1, [1382, 12, 48, 38]);
  cursors.push({ t0: b3.n + 2.4, t1: b3.e, pts: [[b3.n + 2.4, 1250, 160], [b3.n + 3.1, 1404, 32], [b3.e, 1404, 32]] });
  rings.push({ t0: b3.n + 3.15, t1: b3.n + 4.0, ripple: [1404, 32] });
  L(b3.n + 0.15, b3.e - 0.05, "4  CV", "Built from your records. Export to PDF, LaTeX or rich text.");

  // 5 Tenure
  K(b4.s, 720, 426, W, 0.9);
  K(b4.n + 0.3, 720, 140, [1.4, 1.2], 1.2, { ay: [0.42, 0.4] });
  K(b4.cue("counts") - 0.3, 720, 300, [1.4, 1.2], 1.2, { ay: [0.4, 0.4] });
  K(b4.cue("each") - 0.3, 720, 640, [1.35, 1.2], 1.2, { ay: [0.5, 0.42] });
  R(b4.n + 0.5, b4.cue("counts") - 0.2, [210, 88, 1016, 105]);
  R(b4.cue("counts") - 0.1, b4.cue("each") - 0.2, [210, 222, 1016, 110]);
  R(b4.cue("each") - 0.1, b4.e + 0.1, [210, 630, 1016, 110]);
  L(b4.n + 0.15, b4.e - 0.05, "5  Tenure", "Your record against each expectation.");

  const ENDs = b4.e;
  K(ENDs - 0.25, 720, 426, [0.8, 0.62], 0.9);

  const stills = [
    { ...IMG.dashboard, t0: 0 },
    { ...IMG.submissions, t0: b1.s - 0.1 },
    { ...IMG.grants, t0: b2.s - 0.1 },
    { ...IMG.cv, t0: b3.s - 0.1 },
    { ...IMG.tenure, t0: b4.s - 0.1 },
  ];

  const hero = {
    T: 8,
    XF: 0.6,
    stills: [{ ...IMG.dashboard, t0: 0 }],
    keys: [
      { t: 0, fx: 720, fy: 373, s: [0.95], d: 0, nodrift: true },
      { t: 0.5, fx: 830, fy: 128, s: [1.5], d: 1.3, ay: [0.42] },
      { t: 3.7, fx: 1130, fy: 440, s: [1.4], d: 1.3, ay: [0.42] },
      { t: 6.8, fx: 720, fy: 373, s: [0.95], d: 1.0, nodrift: true, ay: [0.44] },
    ],
    rings: [
      { t0: 0.8, t1: 3.4, rect: [240, 72, 1180, 104] },
      { t0: 4.6, t1: 6.6, rect: [838, 318, 582, 190] },
    ],
  };

  return finish(
    {
      id: "vitae-promo",
      frame: "mac",
      title: { name: "Vitae", sub: "Academic research management for macOS.", icon: "brand/vitae-icon.png", iconRadius: 0.22 },
      end: { pill: "Free. macOS 15 or later", url: "purplelink.llc/vitae" },
      stills, keys, rings, lower, cursors, hero,
      poster: b0.n + 2.6,
    },
    B, 5, timing,
  );
}
