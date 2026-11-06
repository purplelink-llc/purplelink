import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { FONT_BODY, FONT_DISPLAY } from "./theme.js";
import { useFonts } from "./V2.jsx";

// Simulated views through display glasses (Lenses launch visuals). Nothing here is footage through the glasses: the
// Mac UI is real HTML text rendered by Chrome at the stated pixel scale, and each glasses effect is a simple model of
// what it does (soft lens edge, an additive see-through display, a warm channel gain, a sample-and-hold display).
// Every still carries the label "Simulated view through the glasses".
//   build-lenses-stills.mjs renders these to site/assets/lenses/*, src/HowTo.jsx plays MotionPane in the video.

export const PW = 1600; // logical size of the glasses picture in the stills
export const PH = 900;
export const LABEL = "Simulated view through the glasses";
const SYS = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", system-ui, sans-serif';
const INK = "oklch(14% 0.07 310)";
const PURPLE = "oklch(50% 0.24 310)";

// ---- sample document (invented, harmless) ----------------------------------------------------------------------
const HEAD = "Reading group notes, week 3";
const PARAS = [
  "We met on Tuesday to compare how each of us keeps track of sources. Most of the group still uses a folder per project, with a short note next to every file that says why it was saved.",
  "Maria suggested writing the question first and the citation second, so that a half-read paper never ends up in the pile without a reason. Dev agreed, and added that dates in the file name save an hour a month.",
  "The longest part of the discussion was about reading on a small screen. Two people prefer a large window with wide margins. One person prefers two narrow columns. Nobody liked tiny print.",
  "Next week we try the same exercise with figures: pick one chart from each paper and write one plain sentence about what it shows. We will keep the sentences in this document.",
  "Open questions: how often to review the pile, whether to keep a separate list of papers we decided against, and who brings the coffee.",
];
const SCROLL_TEXT = [
  "The reading group met on Tuesday to compare how each of us keeps track of sources and notes.",
  "Most of us use one folder per project, with a short note beside each file saying why it was saved.",
  "Maria suggested writing the question first and the citation second, so no paper sits unread.",
  "Dev added that a date in the file name saves about an hour a month, and nobody argued.",
  "The longest talk was about reading on a small screen: wide margins, two columns, or neither.",
  "Nobody liked tiny print. Everyone liked a quiet room and a pot of tea on the table.",
  "Next week we try the same exercise with figures: one chart from each paper, one plain sentence.",
  "We will keep those sentences in this document and read them aloud at the end of the hour.",
  "Open questions: how often to review the pile, and whether to list the papers we decided against.",
  "Someone has to bring the biscuits. The notes do not say who, which is itself a finding.",
];

const T = {
  light: { win: "#ffffff", bar: "#f3f2f6", ink: "#1d1b22", sub: "#6b6773", rule: "#e3e1ea", menu: "rgba(255,255,255,0.55)", menuInk: "#1d1b22" },
  dark: { win: "#1c1b20", bar: "#27252d", ink: "#f1eff7", sub: "#a09cab", rule: "#383541", menu: "rgba(20,18,26,0.6)", menuInk: "#f1eff7" },
};
const WALL = {
  light: "linear-gradient(135deg, oklch(66% 0.17 285) 0%, oklch(78% 0.13 320) 48%, oklch(88% 0.09 20) 100%)",
  dark: "linear-gradient(135deg, oklch(18% 0.06 290) 0%, oklch(22% 0.09 310) 55%, oklch(16% 0.05 270) 100%)",
};

// The macOS arrow pointer. `s` scales it; 1 is the normal size.
export function Pointer({ s = 1, x = 0, y = 0 }) {
  return (
    <svg width={22 * s} height={28 * s} viewBox="0 0 22 28" style={{ position: "absolute", left: x, top: y, overflow: "visible", filter: "drop-shadow(0 1px 1.5px rgba(0,0,0,0.35))" }}>
      <path d="M2 1.5 V21.5 L7.2 17 L10.6 25 L14 23.6 L10.7 15.9 H17.6 Z" fill="#111" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function Lights() {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      {["#ff5f57", "#febc2e", "#28c840"].map((c) => <span key={c} style={{ width: 13, height: 13, borderRadius: 99, background: c }} />)}
    </div>
  );
}

// A Mac desktop at PW x PH: menu bar, one Notes-style window with real text. `full` runs the window to the edges.
export function Desktop({ theme = "light", full = false, big = 1, children, wall = true }) {
  const c = T[theme];
  const win = full ? { left: 0, top: 30, width: PW, height: PH - 30, borderRadius: 0 } : { left: 190, top: 92, width: 1220, height: 730, borderRadius: 14 };
  const col = full ? 900 : 780;
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: wall ? WALL[theme] : c.win, fontFamily: SYS }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 30, background: c.menu, display: "flex", alignItems: "center", gap: 26, padding: "0 20px", fontSize: 14, fontWeight: 600, color: c.menuInk }}>
        <span style={{ fontWeight: 800 }}>Notes</span><span>File</span><span>Edit</span><span>Format</span><span>View</span><span>Window</span><span>Help</span>
        <span style={{ marginLeft: "auto", fontWeight: 500 }}>Thu 9:41 AM</span>
      </div>
      <div style={{ position: "absolute", ...win, background: c.win, boxShadow: full ? "none" : "0 30px 80px rgba(20,10,40,0.38), 0 0 0 1px rgba(0,0,0,0.12)", overflow: "hidden" }}>
        <div style={{ height: 52, background: c.bar, borderBottom: `1px solid ${c.rule}`, display: "flex", alignItems: "center", padding: "0 18px", position: "relative" }}>
          <Lights />
          <span style={{ position: "absolute", left: 0, right: 0, textAlign: "center", fontSize: 14, fontWeight: 600, color: c.ink }}>Reading notes</span>
        </div>
        <div style={{ width: col, margin: "0 auto", paddingTop: 38, color: c.ink }}>
          <div style={{ fontSize: 30 * big, fontWeight: 700, letterSpacing: "-0.01em", marginBottom: 18 }}>{HEAD}</div>
          {PARAS.map((p, i) => <p key={i} style={{ margin: "0 0 15px", fontSize: 16 * big, lineHeight: 1.55, color: i ? c.ink : c.ink }}>{p}</p>)}
          <p style={{ margin: 0, fontSize: 13 * big, lineHeight: 1.5, color: c.sub }}>Last edited Thursday. 5 paragraphs, 212 words.</p>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---- lens: soft outer band ---------------------------------------------------------------------------------------
// Three blurred copies, each masked to a thinner outer ring, over the sharp picture. The mask is an ellipse that
// touches the middle of each side, so the corners (further out) get the most blur, as in real optics.
const ring = (from) => `radial-gradient(ellipse closest-side at 50% 50%, transparent ${from}%, #000 ${from + 7}%)`;
export function Lens({ children }) {
  const layers = [[2.5, 86], [6, 93], [12, 99]];
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: "#000" }}>
      <div style={{ position: "absolute", inset: 0 }}>{children}</div>
      {layers.map(([b, from], i) => (
        <div key={i} style={{ position: "absolute", inset: 0, filter: `blur(${b}px)`, WebkitMaskImage: ring(from), maskImage: ring(from) }}>{children}</div>
      ))}
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse closest-side at 50% 50%, transparent 92%, rgba(0,0,0,0.38) 122%)" }} />
    </div>
  );
}
export function Underscan({ pct, children }) {
  return (
    <div style={{ position: "absolute", inset: 0, background: "#000" }}>
      <div style={{ position: "absolute", inset: 0, transform: `scale(${pct})`, transformOrigin: "50% 50%", overflow: "hidden" }}>{children}</div>
    </div>
  );
}

// ---- warm tint: per-channel gain, applied to everything the display shows ----------------------------------------
export function Tint({ children, id = "warm" }) {
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <filter id={id} colorInterpolationFilters="sRGB">
          <feColorMatrix type="matrix" values="0.98 0 0 0 0  0 0.84 0 0 0  0 0 0.58 0 0  0 0 0 1 0" />
        </filter>
      </svg>
      <div style={{ position: "absolute", inset: 0, filter: `url(#${id})` }}>{children}</div>
    </div>
  );
}

// ---- see-through: an additive display over the room ---------------------------------------------------------------
// Optical see-through glasses add light to what you see. Black adds nothing, so the room shows through; white hides it.
export function Room() {
  const blob = (l, t, w, h, bg, b = 0, r = "50%", extra = {}) => <div style={{ position: "absolute", left: l, top: t, width: w, height: h, background: bg, borderRadius: r, filter: b ? `blur(${b}px)` : "none", ...extra }} />;
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: "linear-gradient(180deg, oklch(70% 0.05 70) 0%, oklch(62% 0.06 55) 62%, oklch(38% 0.05 50) 62.2%, oklch(30% 0.04 45) 100%)" }}>
      <div style={{ position: "absolute", inset: -40, filter: "blur(5px)" }}>
        {blob(1020, 90, 420, 520, "linear-gradient(180deg, oklch(97% 0.03 230), oklch(90% 0.07 215))", 0, "10px", { boxShadow: "0 0 160px 60px oklch(95% 0.05 220 / 0.55)" })}
        {blob(1228, 90, 6, 520, "oklch(55% 0.04 60)", 0, "2px")}
        {blob(1020, 340, 420, 6, "oklch(55% 0.04 60)", 0, "2px")}
        {blob(60, 120, 330, 560, "oklch(34% 0.06 45)", 0, "6px")}
        {[0, 1, 2, 3].map((r) => blob(80, 150 + r * 130, 290, 8, "oklch(48% 0.06 50)", 0, "3px"))}
        {[["oklch(56% 0.16 25)", 90, 74], ["oklch(62% 0.12 140)", 140, 60], ["oklch(66% 0.14 260)", 190, 82], ["oklch(76% 0.12 85)", 246, 56], ["oklch(52% 0.14 330)", 296, 70]].map(([c, x, w], i) => blob(x, 56 + 150 + 0, w * 0.55, 92 - (i % 2) * 14, c, 0, "4px", { top: 156 - (i % 2) * 0 + 0 }))}
        {[["oklch(60% 0.15 40)", 96, 290], ["oklch(66% 0.1 190)", 160, 420], ["oklch(58% 0.13 300)", 226, 550]].map(([c, x, y], i) => blob(x, y - 150 + 20, 44, 100, c, 0, "4px"))}
        {blob(560, 520, 560, 40, "oklch(24% 0.04 45)", 0, "6px")}
        {blob(580, 470, 520, 70, "oklch(42% 0.06 50)", 0, "8px")}
        {blob(720, 360, 36, 140, "oklch(26% 0.03 60)", 0, "8px")}
        {blob(660, 290, 150, 90, "oklch(86% 0.14 80)", 18, "50%", { boxShadow: "0 0 140px 70px oklch(88% 0.13 80 / 0.6)" })}
        {blob(1130, 600, 240, 240, "oklch(48% 0.12 145)", 8, "50%")}
        {blob(1100, 660, 160, 200, "oklch(40% 0.12 150)", 6, "50%")}
        {blob(1180, 740, 110, 120, "oklch(50% 0.09 40)", 4, "14px")}
        {blob(110, 760, 150, 100, "oklch(60% 0.14 30)", 5, "14px")}
      </div>
    </div>
  );
}
export function SeeThrough({ children }) {
  return (
    <div style={{ position: "absolute", inset: 0, isolation: "isolate", background: "#000" }}>
      <Room />
      <div style={{ position: "absolute", inset: 0, mixBlendMode: "screen" }}>{children}</div>
    </div>
  );
}

// ---- motion: a sample-and-hold display, redrawn `hz` times a second ---------------------------------------------
// Logical pane 960 x 540. Text scrolls at SCROLL px/s and a pointer sweeps along a ruler at SWEEP px/s. The picture is
// redrawn hz times a second, so each redraw moves it SCROLL/hz (SWEEP/hz) px. Still mode draws what an eye tracking
// the motion sees: a smear as long as one step for the text, one pointer copy per redraw. Live mode draws the actual
// steps for the slowed-down video.
export const MW = 960;
export const MH = 540;
export const SCROLL = 720;
export const SWEEP = 1080;
const LANE = { x: 40, w: 880, y: 440 };
const LINE_H = 34;
const BLOCK = SCROLL_TEXT.length * LINE_H * 2;

function ScrollText({ y, color }) {
  const one = SCROLL_TEXT.map((l, i) => <div key={i} style={{ height: LINE_H * 2, fontSize: 21, lineHeight: `${LINE_H}px`, color, fontWeight: 500 }}>{l}</div>);
  return <div style={{ position: "absolute", left: 0, top: 0, width: 880, transform: `translateY(${-y}px)` }}>{one}{one}</div>;
}

function Ruler() {
  return (
    <>
      <div style={{ position: "absolute", left: LANE.x, top: LANE.y + 62, width: LANE.w, height: 2, background: "#cfcbd8" }} />
      {Array.from({ length: 45 }, (_, i) => <div key={i} style={{ position: "absolute", left: LANE.x + i * 20, top: LANE.y + (i % 5 === 0 ? 50 : 56), width: 2, height: i % 5 === 0 ? 12 : 6, background: "#cfcbd8" }} />)}
    </>
  );
}

const tri = (p, w) => { const m = ((p % (2 * w)) + 2 * w) % (2 * w); return m < w ? m : 2 * w - m; };

export function MotionPane({ hz, mode = "still", tReal = 0, theme = "light" }) {
  const c = T[theme];
  const blurPx = Math.round(SCROLL / hz);
  const kern = Array.from({ length: blurPx }, () => 1).join(" ");
  const n = Math.floor(tReal * hz + 1e-6);
  const scrollY = mode === "live" ? (SCROLL * n / hz) % BLOCK : 420;
  const ghosts = mode === "live"
    ? [3, 2, 1].map((k) => ({ x: tri(SWEEP * (n - k) / hz, LANE.w - 30), a: 0.5 / k }))
    : [];
  const stepPx = SWEEP / hz;
  const count = mode === "still" ? Math.round(380 / stepPx) : 0;
  const strobe = Array.from({ length: count }, (_, i) => ({ x: 120 + i * stepPx, a: 0.12 + 0.88 * (i / Math.max(1, count - 1)) ** 1.6 }));
  const cursorX = mode === "live" ? tri(SWEEP * n / hz, LANE.w - 30) : 120 + (count - 1) * stepPx;
  return (
    <div style={{ position: "absolute", left: 0, top: 0, width: MW, height: MH, background: c.win, overflow: "hidden", fontFamily: SYS }}>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <filter id={`hold${hz}`} x="0" y="-5%" width="100%" height="110%" colorInterpolationFilters="sRGB">
          <feConvolveMatrix order={`1 ${blurPx}`} kernelMatrix={kern} divisor={blurPx} targetX={0} targetY={Math.floor(blurPx / 2)} edgeMode="none" />
        </filter>
      </svg>
      <div style={{ height: 40, background: c.bar, borderBottom: `1px solid ${c.rule}`, display: "flex", alignItems: "center", padding: "0 16px", position: "relative" }}>
        <Lights />
        <span style={{ position: "absolute", left: 0, right: 0, textAlign: "center", fontSize: 13, fontWeight: 600, color: c.ink }}>Reading notes</span>
      </div>
      <div style={{ position: "absolute", left: 40, top: 62, width: 880, height: 340, overflow: "hidden", filter: mode === "still" ? `url(#hold${hz})` : "none" }}>
        <ScrollText y={scrollY} color={c.ink} />
      </div>
      <div style={{ position: "absolute", left: 40, right: 40, top: 412, height: 1, background: c.rule }} />
      <Ruler />
      {strobe.map((g, i) => <div key={i} style={{ position: "absolute", left: 0, top: 0, opacity: g.a }}><Pointer s={1.7} x={LANE.x + g.x} y={LANE.y + 4} /></div>)}
      {ghosts.map((g, i) => <div key={i} style={{ position: "absolute", left: 0, top: 0, opacity: g.a }}><Pointer s={1.7} x={LANE.x + g.x} y={LANE.y + 4} /></div>)}
      <div style={{ position: "absolute", left: 0, top: 0 }}><Pointer s={1.7} x={LANE.x + cursorX} y={LANE.y + 4} /></div>
    </div>
  );
}

// ---- the stills ------------------------------------------------------------------------------------------------------
function Hz({ hz }) {
  const k = PW / MW;
  return (
    <div style={{ position: "absolute", inset: 0, background: "#fff" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: MW, height: MH, transform: `scale(${k})`, transformOrigin: "0 0" }}><MotionPane hz={hz} mode="still" /></div>
      <div style={{ position: "absolute", right: 26, bottom: 74, fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 64, letterSpacing: "-0.02em", color: hz === 60 ? "#7a5a00" : PURPLE, background: "rgba(255,255,255,0.92)", borderRadius: 18, padding: "6px 26px", boxShadow: "0 8px 30px rgba(40,10,80,0.18)" }}>{hz} Hz</div>
    </div>
  );
}

export function glassesView(scene, side) {
  const after = side === "after";
  switch (scene) {
    case "hidpi": return <Desktop theme="light" />;
    case "edges": return <Lens>{after ? <Underscan pct={0.9}><Desktop theme="light" full /></Underscan> : <Desktop theme="light" full />}</Lens>;
    case "night": return after ? <Tint><Desktop theme="light" full big={1.12} /></Tint> : <Desktop theme="light" full big={1.12} />;
    case "dark": return <SeeThrough><Desktop theme={after ? "dark" : "light"} /></SeeThrough>;
    case "pointer": return <Desktop theme="light" full big={1.12}><Pointer s={after ? 2.8 : 1.1} x={820} y={430} /></Desktop>;
    case "hz": return <Hz hz={after ? 120 : 60} />;
    default: throw new Error(`unknown scene ${scene}`);
  }
}

export function LensesStill({ scene = "hidpi", side = "before" }) {
  useFonts();
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: PW, height: PH, overflow: "hidden" }}>{glassesView(scene, side)}</div>
      <div style={{ position: "absolute", left: 22, bottom: 20, fontFamily: FONT_BODY, fontWeight: 600, fontSize: 19, color: "#fff", background: "rgba(14,8,26,0.72)", borderRadius: 99, padding: "7px 18px" }}>{LABEL}</div>
    </AbsoluteFill>
  );
}

// Before and after side by side, for the site's comparison layout. `zoom` { x, y, s } shows a magnified, unsmoothed
// crop of both (the text-sharpness pair), otherwise both are shown whole.
export const PAIR_H = 628;
export function LensesPair({ before, after, beforeSub, afterSub, zoom, note }) {
  useFonts();
  const PWD = 756, PHT = 425;
  const pane = (src) => zoom
    ? <div style={{ width: PWD, height: PHT, borderRadius: 14, overflow: "hidden", backgroundImage: `url(${staticFile(src)})`, backgroundRepeat: "no-repeat", backgroundSize: `${PW * zoom.s}px ${PH * zoom.s}px`, backgroundPosition: `${-zoom.x * zoom.s}px ${-zoom.y * zoom.s}px`, imageRendering: "pixelated" }} />
    : <Img src={staticFile(src)} style={{ width: PWD, height: PHT, borderRadius: 14, display: "block" }} />;
  const head = (word, sub, solid) => (
    <div style={{ display: "flex", alignItems: "center", gap: 16, height: 56 }}>
      <span style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: 24, letterSpacing: "0.1em", color: "#fff", background: solid ? PURPLE : INK, borderRadius: 99, padding: "8px 24px" }}>{word}</span>
      <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: 32, color: INK }}>{sub}</span>
    </div>
  );
  return (
    <AbsoluteFill style={{ background: "oklch(97% 0.025 310)" }}>
      <div style={{ position: "absolute", left: 28, top: 22, display: "grid", gap: 10 }}>{head("BEFORE", beforeSub, false)}{pane(before)}</div>
      <div style={{ position: "absolute", left: 28 + PWD + 32, top: 22, display: "grid", gap: 10 }}>{head("AFTER", afterSub, true)}{pane(after)}</div>
      <div style={{ position: "absolute", left: 28, right: 28, bottom: 16, display: "flex", justifyContent: "space-between", fontFamily: FONT_BODY, fontWeight: 600, fontSize: 19, color: "oklch(42% 0.04 300)" }}>
        <span>{LABEL}{note ? `. ${note}` : ""}</span><span>purplelink.llc/lenses</span>
      </div>
    </AbsoluteFill>
  );
}
