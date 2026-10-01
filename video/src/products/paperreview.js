// Paper Review: browser frame over a full-page capture of /tools/paper-review/ (1440 CSS px wide,
// window view 1440x900, scrolled between beats). Facts from site/tools/paper-review/index.html.
import { beats, finish, WIDE } from "../stillplan.js";

export const media = { "paper-review.png": ".cache/captures/paper-review.png" };
const PAGE = { src: "media/paper-review.png", w: 1440, h: 6010, view: { w: 1440, h: 900 } };

// page y of the sections (CSS px, from capture.py geometry and the preview)
const Y = { hero: 120, tiers: 440, compare: 830, steps: 1430, sample: 1790 };

export function build(timing) {
  const B = beats(timing, [0, 1, 2, 3, 4], { start: 2.5, lead: 0.3, tail: 0.4 });
  const [b0, b1, b2, b3, b4] = B;
  const W = WIDE.browser1440;
  const Z = [1.5, 1.85];
  const keys = [], rings = [], lower = [], cursors = [], scroll = [];
  const K = (t, fx, fy, s, d, extra = {}) => keys.push({ t, fx, fy, s, d, ...extra });
  const R = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const L = (t0, t1, tag, text) => lower.push({ t0, t1, tag, text });
  const S = (t, y, d = 1.0) => scroll.push({ t, y, d });

  // 1 Hero
  S(0, Y.hero, 0);
  K(0, 720, 450, W, 0);
  K(b0.n + 0.4, 720, 300, [1.25, 1.55], 1.3, { ay: [0.42, 0.4] });
  R(b0.cue("quote") - 0.1, b0.e + 0.1, [330, 240 - Y.hero + 60, 780, 130]);
  L(b0.n + 0.15, b0.e - 0.05, "1  Four reviewers", "Methods, statistics, data integrity, editor.");

  // 2 Tiers
  S(b1.s, Y.tiers, 1.1);
  K(b1.s, 720, 300, Z, 1.2, { ay: [0.44, 0.42] });
  const tierY = (y) => y - Y.tiers;
  R(b1.cue("standard") - 0.1, b1.cue("journal") - 0.1, [330, tierY(520), 780, 110]);
  R(b1.cue("journal") - 0.05, b1.cue("deep") - 0.1, [330, tierY(640), 780, 105]);
  R(b1.cue("deep") - 0.05, b1.e + 0.1, [330, tierY(740), 780, 95]);
  cursors.push({ t0: b1.n, t1: b1.e, pts: [[b1.n, 900, 420], [b1.cue("standard") + 0.2, 350, tierY(560)], [b1.cue("journal"), 350, tierY(660)], [b1.cue("deep"), 350, tierY(760)], [b1.e, 350, tierY(760)]] });
  L(b1.n + 0.15, b1.e - 0.05, "2  Three tiers", "Standard $9. Journal Pack $11. Deep Review $15.");

  // 3 Compare table
  S(b2.s, Y.compare, 1.1);
  K(b2.s, 720, 330, [1.45, 1.8], 1.2, { ay: [0.44, 0.42] });
  const cmpY = (y) => y - Y.compare;
  R(b2.cue("crossref") - 0.3, b2.cue("scans") - 0.1, [365, cmpY(1040), 710, 42]);
  R(b2.cue("scans") - 0.05, b2.e + 0.1, [365, cmpY(1128), 710, 42]);
  L(b2.n + 0.15, b2.e - 0.05, "3  Every tier", "References checked against CrossRef. Figures scanned.");

  // 4 Sample report
  S(b3.s, Y.sample, 1.1);
  K(b3.s, 720, 380, [1.35, 1.7], 1.2, { ay: [0.44, 0.42] });
  const smpY = (y) => y - Y.sample;
  R(b3.cue("blind") - 0.1, b3.cue("contradictions") - 0.2, [325, smpY(1920), 790, 150]);
  K(b3.cue("contradictions") - 0.4, 720, 520, [1.35, 1.7], 1.2, { ay: [0.44, 0.42] });
  R(b3.cue("contradictions") - 0.1, b3.cue("fix") - 0.2, [325, smpY(2125), 790, 130]);
  R(b3.cue("fix") - 0.05, b3.e + 0.1, [325, smpY(2285), 790, 150]);
  L(b3.n + 0.15, b3.e - 0.05, "4  The report", "Blind spots, contradictions, fix checklist.");

  // 5 Steps and deletion
  S(b4.s, Y.steps, 1.1);
  K(b4.s, 720, 260, [1.5, 1.85], 1.2, { ay: [0.42, 0.4] });
  const stpY = (y) => y - Y.steps;
  R(b4.cue("stripe") - 0.1, b4.cue("read") + 1.2, [400, stpY(1540), 640, 100]);
  R(b4.cue("read") + 1.3, b4.e + 0.1, [430, stpY(1665), 580, 90]);
  K(b4.cue("read") + 1.0, 720, 300, [1.5, 1.85], 1.1, { ay: [0.42, 0.4] });
  L(b4.n + 0.15, b4.e - 0.05, "5  Pay, upload, read", "One-time payment. Deleted soon after delivery.");

  const ENDs = b4.e;
  K(ENDs - 0.25, 720, 450, [0.82, 0.64], 0.9);

  const stills = [{ ...PAGE, t0: 0, scroll }];
  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...PAGE, t0: 0, scroll: [{ t: 0, y: Y.hero, d: 0 }, { t: 3.3, y: Y.tiers, d: 1.4 }, { t: 6.6, y: Y.hero, d: 1.2 }] }],
    keys: [
      { t: 0, fx: 720, fy: 450, s: [0.9], d: 0, nodrift: true },
      { t: 0.5, fx: 720, fy: 300, s: [1.25], d: 1.4, ay: [0.42] },
      { t: 3.3, fx: 720, fy: 300, s: [1.4], d: 1.4, ay: [0.44] },
      { t: 6.6, fx: 720, fy: 450, s: [0.9], d: 1.2, nodrift: true },
    ],
    rings: [{ t0: 4.4, t1: 6.4, rect: [330, 520 - Y.tiers, 780, 110] }],
  };
  return finish(
    {
      id: "paper-review-promo", frame: "browser", url: "purplelink.llc/tools/paper-review",
      title: { name: "Paper Review", sub: "Four AI reviewers read your manuscript before a journal does.", icon: "brand/purplelink-tile.png", iconRadius: 0.26 },
      end: { pill: "From $9 per review", url: "purplelink.llc/tools/paper-review" },
      stills, keys, rings, lower, cursors, hero,
      poster: b1.cue("deep") + 0.4,
    },
    B, 5, timing,
  );
}
