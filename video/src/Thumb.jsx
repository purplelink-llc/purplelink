import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { FONT_BODY, FONT_DISPLAY } from "./theme.js";
import { Backdrop, useFonts } from "./V2.jsx";

// YouTube thumbnails, 1280x720. Three templates:
//   error    - one LaTeX error or warning, as it reads in the log, with "How to fix it" (the series)
//   long     - an error plus a numbered promise ("5 causes") that the video keeps
//   split    - before and after: the error, an arrow, the page that compiles (a Test & Compare variant)
//   (error and long take `pill` to label a non-LaTeX problem, e.g. "Homebrew cache")
//   product  - an app's real screen (site screenshot or a frame of its own promo) with a 2-4 word outcome
// Rules (research 2026-10-14): show only what the video shows; 1-5 words of display text; large type that reads at
// 168x94; no prices (they go stale); the bottom-right corner (x > 1080, y > 620) stays empty for the duration stamp.
const MONO = 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, monospace';
const INK = "oklch(14% 0.07 310)";
const PANEL = "oklch(19% 0.05 310)";
const CODE = "oklch(96% 0.02 310)";
const ERR = "oklch(78% 0.14 15)";
const WARN = "oklch(84% 0.13 80)";
const OKC = "oklch(82% 0.15 150)";
const LIGHT = "oklch(86% 0.1 310)";
const PURPLE = "oklch(50% 0.24 310)";

const fit = (s, steps) => steps.find(([n]) => s.length <= n)?.[1] ?? steps[steps.length - 1][1];

function Check({ size = 54, color = OKC }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ flex: "none" }}>
      <circle cx="12" cy="12" r="11" fill={color} />
      <path d="M6.5 12.5l3.6 3.6 7.4-8" fill="none" stroke={PANEL} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Dark({ children }) {
  return (
    <AbsoluteFill style={{ background: PANEL }}>
      <div style={{ position: "absolute", width: 1100, height: 900, left: -260, top: -380, borderRadius: "50%", background: "radial-gradient(closest-side, oklch(34% 0.12 310 / 0.85), transparent)" }} />
      <div style={{ position: "absolute", width: 900, height: 800, right: -320, bottom: -420, borderRadius: "50%", background: "radial-gradient(closest-side, oklch(30% 0.1 290 / 0.7), transparent)" }} />
      {children}
    </AbsoluteFill>
  );
}

function Pill({ text, color }) {
  return (
    <div style={{ alignSelf: "start", justifySelf: "start", fontFamily: FONT_BODY, fontWeight: 800, fontSize: 34, letterSpacing: "0.08em", textTransform: "uppercase", color: PANEL, background: color, borderRadius: 999, padding: "8px 26px" }}>{text}</div>
  );
}

function ErrorThumb({ level = "error", msg, pill }) {
  const size = fit(msg, [[12, 140], [18, 124], [26, 106], [36, 90], [48, 76], [99, 64]]);
  const tone = level === "warning" ? WARN : ERR;
  return (
    <Dark>
      <div style={{ position: "absolute", left: 80, top: 70, right: 80, display: "grid", gap: 34 }}>
        <Pill text={pill || (level === "warning" ? "LaTeX warning" : "LaTeX error")} color={tone} />
        <div style={{ fontFamily: MONO, fontWeight: 700, fontSize: size, lineHeight: 1.12, color: CODE, letterSpacing: "-0.02em", wordBreak: "break-word" }}>
          <span style={{ color: tone }}>! </span>{msg}
        </div>
      </div>
      <div style={{ position: "absolute", left: 80, bottom: 70, display: "flex", alignItems: "center", gap: 20 }}>
        <Check />
        <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: 64, color: CODE, letterSpacing: "-0.01em" }}>How to fix it</span>
      </div>
    </Dark>
  );
}

function LongThumb({ msg, n = 5, unit = "causes", sub = "and the fix for each", pill = "LaTeX error", bang = true }) {
  return (
    <Dark>
      <div style={{ position: "absolute", left: 80, top: 70, width: 700, display: "grid", gap: 30 }}>
        <Pill text={pill} color={ERR} />
        <div style={{ fontFamily: MONO, fontWeight: 700, fontSize: fit(msg, [[14, 104], [22, 86], [99, 68]]), lineHeight: 1.1, color: CODE, letterSpacing: "-0.02em" }}>
          {bang && <span style={{ color: ERR }}>! </span>}{msg}
        </div>
      </div>
      <div style={{ position: "absolute", left: 80, bottom: 70, display: "flex", alignItems: "center", gap: 20 }}>
        <Check />
        <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: 56, color: CODE }}>{sub}</span>
      </div>
      <div style={{ position: "absolute", right: 90, top: 20, width: 380, textAlign: "center" }}>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 380, lineHeight: 1, color: LIGHT }}>{n}</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: 64, letterSpacing: "0.04em", textTransform: "uppercase", color: CODE, marginTop: -20 }}>{unit}</div>
      </div>
    </Dark>
  );
}

// One real screen, cropped in (`zoom` around the `pos` focus point) so a single element reads at feed size; it runs
// off the right edge and stops above the duration stamp. `icons` instead of `img` shows a grid of app icons.
function ProductThumb({ name, line, img, icon, lockup, icons, pos = "center", zoom = 1, portrait = false, box }) {
  const shot = box ? { radius: 20, ...box } : portrait
    ? { left: 780, top: 34, width: 320, height: 586, radius: 44 }
    : { left: 560, top: 40, width: 760, height: 540, radius: 24 };
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <div style={{ position: "absolute", ...shot, borderRadius: shot.radius, overflow: "hidden", background: icons ? "transparent" : "white", boxShadow: icons ? "none" : "0 30px 70px oklch(30% 0.14 310 / 0.36), 0 10px 24px oklch(30% 0.14 310 / 0.22)" }}>
        {icons ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 150px)", gap: 34, padding: "26px 60px" }}>
            {icons.map((s, i) => <Img key={i} src={staticFile(s)} style={{ width: 150, height: 150, borderRadius: 34, boxShadow: "0 14px 30px oklch(30% 0.14 310 / 0.25)" }} />)}
          </div>
        ) : (
          <Img src={staticFile(img)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: pos, transform: `scale(${zoom})`, transformOrigin: pos, display: "block" }} />
        )}
      </div>
      <div style={{ position: "absolute", left: 64, top: 64, width: portrait ? 680 : 470, display: "grid", gap: 22 }}>
        {lockup ? (
          <Img src={staticFile(lockup)} style={{ width: 200, height: "auto" }} />
        ) : (
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            {icon && <Img src={staticFile(icon)} style={{ width: 84, height: 84, borderRadius: 20 }} />}
            <span style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: 42, color: PURPLE }}>{name}</span>
          </div>
        )}
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: fit(line, [[14, 104], [22, 92], [99, 80]]), lineHeight: 1.0, letterSpacing: "-0.02em", color: INK }}>{line}</div>
      </div>
    </AbsoluteFill>
  );
}

// Before and after: the error on the dark log panel, an arrow, and the page that compiles once it is fixed.
function SplitThumb({ msg, img, after = "Compiles" }) {
  return (
    <Dark>
      <div style={{ position: "absolute", left: 70, top: 70, width: 560, display: "grid", gap: 30 }}>
        <Pill text="LaTeX error" color={ERR} />
        <div style={{ fontFamily: MONO, fontWeight: 700, fontSize: fit(msg, [[14, 92], [22, 80], [99, 64]]), lineHeight: 1.1, color: CODE, letterSpacing: "-0.02em" }}>
          <span style={{ color: ERR }}>! </span>{msg}
        </div>
      </div>
      <svg width="110" height="90" viewBox="0 0 120 90" style={{ position: "absolute", left: 640, top: 250 }}>
        <path d="M8 45h88M70 16l30 29-30 29" fill="none" stroke={LIGHT} strokeWidth="12" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div style={{ position: "absolute", left: 780, top: 150, width: 440, padding: "34px 30px", borderRadius: 16, background: "white", boxShadow: "0 30px 70px oklch(5% 0.05 310 / 0.6)" }}>
        <Img src={staticFile(img)} style={{ width: "100%", display: "block" }} />
      </div>
      <div style={{ position: "absolute", left: 70, bottom: 70, display: "flex", alignItems: "center", gap: 20 }}>
        <Check />
        <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: 64, color: CODE }}>{after}</span>
      </div>
    </Dark>
  );
}


// ---- Refresh templates (2026-11-06). One focal object, 2-3 display words that add to the title instead of repeating it,
// no small pills or footers, a light or vivid background so the feed does not read as one dark wall.
//   focus - light background, big hook on the left, one dark card with the real error text (`hl` is marked)
//   diff  - vivid background, hook, then the real before line (red) and after line (green) from the video
//   face  - reaction face slot on the left, hook and the real error text on the right. `face` is a repo-relative image
//           (a ChatGPT-made synthetic face on a flat background); without it a marked placeholder is drawn.
const LILAC = "oklch(95% 0.035 310)";
const HL = "oklch(88% 0.17 95)";
const GREEN = "oklch(72% 0.17 150)";
const RED = "oklch(66% 0.2 22)";

function Marked({ text, hl, color = HL }) {
  if (!hl || !text.includes(hl)) return <>{text}</>;
  const [a, ...rest] = text.split(hl);
  return <>{a}<span style={{ background: color, color: INK, borderRadius: 8, padding: "0 8px" }}>{hl}</span>{rest.join(hl)}</>;
}

function CodeCard({ lines, hl, size, style, tone = ERR }) {
  const longest = Math.max(...lines.map((l) => l.length));
  const px = size ?? fit("x".repeat(longest), [[16, 78], [22, 66], [30, 54], [40, 44], [99, 36]]);
  return (
    <div style={{ position: "absolute", background: PANEL, borderRadius: 28, padding: "34px 40px", boxShadow: "0 30px 70px oklch(20% 0.1 310 / 0.4)", fontFamily: MONO, fontWeight: 700, fontSize: px, lineHeight: 1.22, color: CODE, letterSpacing: "-0.02em", ...style }}>
      {lines.map((l, i) => (
        <div key={i} style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {i === 0 && <span style={{ color: tone }}>! </span>}<Marked text={l} hl={hl} />
        </div>
      ))}
    </div>
  );
}

const hookSize = (h, width = 560) => { const w = Math.max(...h.split("\n").map((x) => x.length)); return Math.min(180, Math.floor(width / (w * 0.5))); };

function FocusThumb({ hook, lines, hl, big }) {
  return (
    <AbsoluteFill style={{ background: `linear-gradient(135deg, ${LILAC}, oklch(90% 0.06 310))` }}>
      <div style={{ position: "absolute", left: 70, top: 90, width: 560, fontFamily: FONT_DISPLAY, fontWeight: 800, fontSize: hookSize(hook, 540), lineHeight: 0.98, letterSpacing: "-0.03em", color: INK, whiteSpace: "pre-line" }}>{hook}</div>
      {big && <div style={{ position: "absolute", left: 640, top: 40, fontFamily: FONT_DISPLAY, fontWeight: 800, fontSize: 330, lineHeight: 1, color: PURPLE }}>{big}</div>}
      <CodeCard lines={lines} hl={hl} size={lines.join("").length > 30 ? 46 : 58} style={{ left: 630, top: big ? 400 : 180, width: 600 }} />
    </AbsoluteFill>
  );
}

function DiffThumb({ hook, before, after, beforeLabel = "Before", afterLabel = "After" }) {
  const longest = Math.max((before || "").length, after.length);
  const px = fit("x".repeat(longest), [[24, 62], [32, 50], [44, 40], [99, 32]]);
  const row = (text, color, label, top, mark) => (
    <div style={{ position: "absolute", left: 70, top, width: 1130, borderRadius: 24, background: PANEL, borderLeft: `20px solid ${color}`, padding: "20px 36px", display: "flex", alignItems: "center", gap: 28, boxShadow: "0 24px 60px oklch(10% 0.1 310 / 0.45)" }}>
      <span style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: 30, letterSpacing: "0.06em", textTransform: "uppercase", color, width: 130, flex: "none" }}>{label}</span>
      <span style={{ fontFamily: MONO, fontWeight: 700, fontSize: px, color: CODE, letterSpacing: "-0.02em", wordBreak: "break-all" }}>{mark}{text}</span>
    </div>
  );
  return (
    <AbsoluteFill style={{ background: `linear-gradient(150deg, oklch(46% 0.24 310), oklch(30% 0.17 300))` }}>
      <div style={{ position: "absolute", left: 70, top: 70, fontFamily: FONT_DISPLAY, fontWeight: 800, fontSize: 190, lineHeight: 1, letterSpacing: "-0.03em", color: "white", whiteSpace: "pre-line" }}>{hook}</div>
      {before && row(before, RED, beforeLabel, 330, null)}
      {row(after, GREEN, afterLabel, before ? 480 : 380, null)}
    </AbsoluteFill>
  );
}

function FaceSlot({ face, mood }) {
  const box = { position: "absolute", left: 0, top: 0, width: 560, height: 720 };
  if (face) {
    return (
      <div style={{ ...box, overflow: "hidden" }}>
        <Img src={staticFile(face)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% 30%", display: "block" }} />
      </div>
    );
  }
  return (
    <div style={{ ...box, background: "oklch(58% 0.12 310)", overflow: "hidden" }}>
      <svg width="560" height="720" viewBox="0 0 560 720" style={{ position: "absolute" }}>
        <circle cx="280" cy="300" r="120" fill="oklch(72% 0.06 310)" />
        <path d="M60 720c0-170 90-260 220-260s220 90 220 260z" fill="oklch(72% 0.06 310)" />
        <rect x="14" y="14" width="532" height="692" rx="26" fill="none" stroke="white" strokeWidth="6" strokeDasharray="22 14" />
      </svg>
      <div style={{ position: "absolute", left: 40, right: 40, top: 560, textAlign: "center", fontFamily: FONT_BODY, fontWeight: 800, fontSize: 40, color: "white", lineHeight: 1.1 }}>FACE PLACEHOLDER<br /><span style={{ fontSize: 30, fontWeight: 600 }}>{mood}</span></div>
    </div>
  );
}

function FaceThumb({ hook, lines, hl, face, mood = "shocked" }) {
  return (
    <AbsoluteFill style={{ background: "linear-gradient(135deg, oklch(44% 0.24 310), oklch(26% 0.15 295))" }}>
      <FaceSlot face={face} mood={mood} />
      <div style={{ position: "absolute", left: 600, top: 60, width: 640, fontFamily: FONT_DISPLAY, fontWeight: 800, fontSize: Math.min(170, hookSize(hook, 620)), lineHeight: 0.98, letterSpacing: "-0.03em", color: "white", whiteSpace: "pre-line" }}>{hook}</div>
      <CodeCard lines={lines} hl={hl} size={lines.join("").length > 44 ? 38 : 46} style={{ left: 600, top: 400, width: 600 }} />
    </AbsoluteFill>
  );
}

export function Thumb(props) {
  useFonts();
  if (props.kind === "focus") return <FocusThumb {...props} />;
  if (props.kind === "diff") return <DiffThumb {...props} />;
  if (props.kind === "face") return <FaceThumb {...props} />;
  if (props.kind === "split") return <SplitThumb {...props} />;
  if (props.kind === "error") return <ErrorThumb {...props} />;
  if (props.kind === "long") return <LongThumb {...props} />;
  return <ProductThumb {...props} />;
}
