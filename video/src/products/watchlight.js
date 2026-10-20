// Watchlight how-to (long, 16:9): iPhone frame, 1320x2868 simulator screenshots of build 1.0 (14).
// Script and footage rules: SmishFilter docs/video/watchlight-howto-script.md. Every message on screen is made up
// (ContentView.screenshotSamples 0 and one typed ordinary text); no real company names.
import { beats, finish } from "../stillplan.js";
import { WL, wlMedia, IMG, R as RECT, mid } from "./watchlightshots.js";

export const media = wlMedia;

export function build(timing) {
  const order = Array.from({ length: 16 }, (_, i) => i);
  const B = beats(timing, order, { start: 2.5, lead: 0.35, tail: 0.6 });
  const [b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15] = B;
  const keys = [], rings = [], lower = [], stills = [];
  const Z = WL.zoom;
  const wide = { ax: WL.ax.wide, ay: WL.ay.wide };
  const zoom = { ax: WL.ax.zoom, ay: WL.ay.zoom };
  // 16:9 zooms 30% further than the preset numbers so the phone's text reads at YouTube's player size.
  const K = (t, rect, s, d, o = zoom) => { const [fx, fy] = mid(rect); keys.push({ t, fx, fy, s: [s[0] * 1.3, s[1]], d, ...o }); };
  const ring = (t0, t1, rect) => rings.push({ t0, t1, rect });
  const tap = (t, rect) => rings.push({ t0: t, t1: t + 0.9, ripple: mid(rect) });
  const L = (b, tag, text) => lower.push({ t0: b.n + 0.15, t1: b.e - 0.1, tag, text, maxW: 660 });
  const S = (img, t0) => stills.push({ ...img, t0 });

  // 0 What it is
  S(IMG.home, 0);
  keys.push({ t: 0, fx: 660, fy: 1434, s: WL.wide, d: 0, ...wide });
  K(b0.n + 1.2, RECT.home.top, [0.5, 0.6], 1.6);
  L(b0, "Watchlight", "A second opinion on a text, with reasons.");

  // 1 Paste
  K(b1.s, RECT.home.paste, Z, 1.1);
  ring(b1.cue("copy"), b1.e, RECT.home.check);
  tap(b1.cue("paste") + 0.05, RECT.home.paste);
  L(b1, "1  Check a message", "Copy it in Messages, then tap Paste.");

  // 2 Try one
  K(b2.s, RECT.home.chips, Z, 1.0);
  ring(b2.cue("try") - 0.1, b2.e, RECT.home.chips);
  L(b2, "Try one", "Made-up examples, so you can see a result.");

  // 3 Other ways in: share steps, then the QR and screenshot tiles
  S(IMG.home2, b3.s - 0.1);
  K(b3.s, RECT.home2.share, Z, 1.0);
  ring(b3.n + 0.4, b3.cue("scan") - 0.5, RECT.home2.share);
  S(IMG.home, b3.cue("scan") - 0.45);
  K(b3.cue("scan") - 0.4, RECT.home.tiles, Z, 0.9);
  ring(b3.cue("scan"), b3.e, RECT.home.tiles);
  L(b3, "Other ways in", "Share, scan a QR code, or check a screenshot.");

  // 4 Checking, then the answer
  S(IMG.checking, b4.s - 0.1);
  K(b4.s, RECT.checking.card, Z, 1.0);
  S(IMG.shot0, b4.cue("answer") - 0.5);
  K(b4.cue("answer") - 0.45, RECT.shot0.verdict, Z, 1.0);
  ring(b4.cue("likely") - 0.1, b4.e, RECT.shot0.verdict);
  L(b4, "2  Read the result", "The answer comes first.");

  // 5 Warning signs, weights and the bar
  K(b5.s, RECT.shot0.reasons, [0.5, 0.6], 1.1);
  ring(b5.cue("number") - 0.1, b5.cue("signs") - 0.2, RECT.shot0.weights);
  ring(b5.cue("bar") - 0.2, b5.e, RECT.shot0.bar);
  L(b5, "Warning signs", "Each sign shows how much it counts.");

  // 6 Link check and what to do
  S(IMG.res0b, b6.s - 0.1);
  K(b6.s, RECT.res0b.link, [0.48, 0.58], 1.0);
  K(b6.cue("lists") - 0.3, RECT.res0b.todo, [0.52, 0.6], 1.0);
  ring(b6.cue("lists") - 0.1, b6.e, RECT.res0b.todo);
  L(b6, "What to do", "Steps for this kind of text.");

  // 7 No warning signs found
  S(IMG.clean1, b7.s - 0.1);
  K(b7.s, RECT.clean1.green, Z, 1.0);
  ring(b7.cue("guarantee") - 0.4, b7.e, RECT.clean1.green);
  L(b7, "No warning signs found", "Not a guarantee. Check another way.");

  // 8 Ask someone I trust, Report to 7726
  S(IMG.res0c, b8.s - 0.1);
  K(b8.s, RECT.res0c.buttons, Z, 1.0);
  ring(b8.cue("ask") - 0.1, b8.cue("report") - 0.2, RECT.res0c.ask);
  ring(b8.cue("report") - 0.1, b8.e, RECT.res0c.report);
  L(b8, "3  Next steps", "Ask someone I trust, or report to 7726.");

  // 9 Already tapped, replied or paid?
  K(b9.s, RECT.res0c.already, Z, 0.8);
  tap(b9.n + 0.3, RECT.res0c.already);
  S(IMG.recov1, b9.cue("pick") - 0.5);
  K(b9.cue("pick") - 0.45, RECT.recov1.tapped, [0.5, 0.6], 1.0);
  ring(b9.cue("pick"), b9.e, RECT.recov1.tapped);
  L(b9, "Already tapped?", "Pick what happened. Do the first step now.");

  // 10 Turn on protection
  S(IMG.home, b10.s - 0.1);
  K(b10.s, RECT.home.card, Z, 1.0);
  tap(b10.cue("dark") + 0.1, RECT.home.card);
  S(IMG.setup1, b10.cue("four") - 0.6);
  K(b10.cue("four") - 0.55, RECT.setup1.night, Z, 1.0);
  L(b10, "4  Turn on protection", "Four parts, each under a minute.");

  // 11 Text filter
  K(b11.s, RECT.setup1.filter, [0.52, 0.6], 1.0);
  ring(b11.cue("messages") - 0.1, b11.e, RECT.setup1.steps);
  L(b11, "Text filter", "Messages, filter button, Manage Filtering.");

  // 12 Caller labels, Safari warning, Report
  S(IMG.calls, b12.s - 0.1);
  K(b12.s, RECT.calls.label, Z, 1.0);
  ring(b12.n + 0.3, b12.cue("safari") - 0.5, RECT.calls.label);
  S(IMG.setup2, b12.cue("safari") - 0.45);
  K(b12.cue("safari") - 0.4, RECT.setup2.safari, [0.5, 0.6], 1.0);
  ring(b12.cue("safari"), b12.cue("with") - 0.4, RECT.setup2.safari);
  S(IMG.setup3, b12.cue("with") - 0.35);
  K(b12.cue("with") - 0.3, RECT.setup3.report, [0.52, 0.6], 1.0);
  ring(b12.cue("with"), b12.e, RECT.setup3.report);
  L(b12, "More settings", "Caller labels, Safari warning, Report.");

  // 13 Missing a text?
  S(IMG.missing1, b13.s - 0.1);
  K(b13.s, RECT.missing1.intro, Z, 1.0);
  K(b13.cue("messages") - 0.3, RECT.missing1.find, [0.52, 0.6], 1.0);
  ring(b13.cue("messages"), b13.e, RECT.missing1.find);
  L(b13, "5  Missing a text?", "Look in Junk. Mark it Not Junk.");

  // 14 Unlock: every warning free, then what the unlock adds
  S(IMG.unlock, b14.s - 0.1);
  K(b14.s, RECT.unlock.free, Z, 1.0);
  ring(b14.n + 0.2, b14.cue("optional") - 0.4, RECT.unlock.free);
  S(IMG.unlock2, b14.cue("optional") - 0.35);
  K(b14.cue("optional") - 0.3, RECT.unlock2.button, Z, 1.0);
  ring(b14.cue("nine") - 0.2, b14.cue("adds") - 0.3, RECT.unlock2.button);
  K(b14.cue("adds") - 0.3, RECT.unlock2.adds, [0.52, 0.6], 1.0);
  ring(b14.cue("adds") - 0.1, b14.e, RECT.unlock2.adds);
  L(b14, "Unlock, optional", "Every warning stays free.");

  // 15 For a parent
  S(IMG.setup3, b15.s - 0.1);
  K(b15.s, RECT.setup3.family, Z, 1.0);
  ring(b15.n + 0.4, b15.e, RECT.setup3.family);
  L(b15, "For a parent", "Set it up together. Try one example.");

  const ENDs = b15.e;
  S(IMG.home, ENDs - 0.6);
  keys.push({ t: ENDs - 0.55, fx: 660, fy: 1434, s: [0.27, 0.4], d: 0.9, ...wide });

  const hero = {
    T: 8, XF: 0.6,
    stills: [{ ...IMG.shot0, t0: 0 }],
    keys: [
      { t: 0, fx: 660, fy: 1434, s: [0.3], d: 0, nodrift: true, ax: [0.5], ay: [0.5] },
      { t: 0.5, ...xy(RECT.shot0.verdict), s: [0.55], d: 1.5, ax: [0.5], ay: [0.46] },
      { t: 3.8, ...xy(RECT.shot0.reasons), s: [0.55], d: 1.4, ax: [0.5], ay: [0.46] },
      { t: 6.7, fx: 660, fy: 1434, s: [0.3], d: 1.1, nodrift: true, ax: [0.5], ay: [0.5] },
    ],
    rings: [{ t0: 4.2, t1: 6.4, rect: RECT.shot0.weights }],
  };

  return finish(
    {
      id: "watchlight-howto",
      frame: "phone",
      title: { name: "Watchlight", sub: "Check a message before you trust it.", icon: "media/watchlight-icon.png", iconRadius: 0.22 },
      end: { pill: "Free on iPhone. Every warning free.", url: "purplelink.llc" },
      stills, keys, rings, lower, cursors: [], hero,
      poster: b4.e - 1.0,
    },
    B, 16, timing,
  );
}

function xy(rect) { const [fx, fy] = mid(rect); return { fx, fy }; }
