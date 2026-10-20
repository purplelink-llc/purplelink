// Watchlight Short (9:16, under 60 s): the long cut's screenshots, six beats for the adult child.
// Script: SmishFilter docs/video/watchlight-howto-script.md (Short table).
import { beats, finish } from "../stillplan.js";
import { WL, wlMedia, IMG, R as RECT, mid } from "./watchlightshots.js";

export const media = wlMedia;

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

  S(IMG.home, 0);
  keys.push({ t: 0, fx: 660, fy: 1434, s: WL.wide, d: 0, ...wide });
  K(b0.n + 1.0, RECT.home.top, [0.5, 0.55], 1.4);
  L(b0, "For a parent's iPhone", "A second opinion on a text.");

  K(b1.s, RECT.home.paste, Z, 1.0);
  rings.push({ t0: b1.cue("paste"), t1: b1.cue("paste") + 0.9, ripple: mid(RECT.home.paste) });
  ring(b1.n, b1.e, RECT.home.check);
  L(b1, "Check a message", "Copy, open Watchlight, tap Paste.");

  S(IMG.shot0, b2.s - 0.1);
  K(b2.s, RECT.shot0.reasons, [0.5, 0.52], 1.0);
  ring(b2.cue("how") - 0.1, b2.e, RECT.shot0.weights);
  L(b2, "Reasons", "Each sign and how much it counts.");

  S(IMG.clean1, b3.s - 0.1);
  K(b3.s, RECT.clean1.green, [0.5, 0.56], 1.0);
  ring(b3.n + 0.2, b3.e, RECT.clean1.green);
  L(b3, "No warning signs found", "Not a guarantee.");

  S(IMG.res0c, b4.s - 0.1);
  K(b4.s, RECT.res0c.buttons, Z, 1.0);
  ring(b4.n + 0.1, b4.cue("or") - 0.2, RECT.res0c.ask);
  ring(b4.cue("or") - 0.1, b4.e, RECT.res0c.report);
  L(b4, "Next steps", "Ask someone I trust, or report to 7726.");

  S(IMG.setup1, b5.s - 0.1);
  K(b5.s, RECT.setup1.filter, [0.5, 0.52], 1.0);
  ring(b5.cue("text") - 0.1, b5.e, RECT.setup1.filter);
  L(b5, "Text filter", "Turn it on in Messages.");

  const ENDs = b5.e;
  S(IMG.home, ENDs - 0.6);
  keys.push({ t: ENDs - 0.55, fx: 660, fy: 1434, s: [0.27, 0.4], d: 0.9, ...wide });

  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...IMG.shot0, t0: 0 }],
    keys: [
      { t: 0, fx: 660, fy: 1434, s: [0.3], d: 0, nodrift: true, ax: [0.5], ay: [0.5] },
      { t: 4, fx: 660, fy: 1434, s: [0.32], d: 3, ax: [0.5], ay: [0.5] },
    ],
    rings: [],
  };

  return finish(
    {
      id: "watchlight-short",
      frame: "phone",
      title: { name: "Watchlight", sub: "Check a message before you trust it.", icon: "media/watchlight-icon.png", iconRadius: 0.22 },
      end: { pill: "Every warning free", url: "purplelink.llc" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b2.e - 1.0,
    },
    B, 6, timing,
  );
}
