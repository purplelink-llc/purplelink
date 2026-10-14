import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { FONT_BODY, FONT_DISPLAY } from "./theme.js";
import { Backdrop, useFonts } from "./V2.jsx";

// YouTube thumbnails, 1280x720. Three templates:
//   error    - one LaTeX error or warning, as it reads in the log, with "How to fix it" (the series)
//   long     - an error plus a numbered promise ("5 causes") that the video keeps
//   split    - before and after: the error, an arrow, the page that compiles (a Test & Compare variant)
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

function ErrorThumb({ level = "error", msg }) {
  const size = fit(msg, [[12, 140], [18, 124], [26, 106], [36, 90], [48, 76], [99, 64]]);
  const tone = level === "warning" ? WARN : ERR;
  return (
    <Dark>
      <div style={{ position: "absolute", left: 80, top: 70, right: 80, display: "grid", gap: 34 }}>
        <Pill text={level === "warning" ? "LaTeX warning" : "LaTeX error"} color={tone} />
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

function LongThumb({ msg, n = 5, unit = "causes", sub = "and the fix for each" }) {
  return (
    <Dark>
      <div style={{ position: "absolute", left: 80, top: 70, width: 700, display: "grid", gap: 30 }}>
        <Pill text="LaTeX error" color={ERR} />
        <div style={{ fontFamily: MONO, fontWeight: 700, fontSize: fit(msg, [[14, 104], [22, 86], [99, 68]]), lineHeight: 1.1, color: CODE, letterSpacing: "-0.02em" }}>
          <span style={{ color: ERR }}>! </span>{msg}
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
function ProductThumb({ name, line, img, icon, icons, pos = "center", zoom = 1, portrait = false, box }) {
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
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          {icon && <Img src={staticFile(icon)} style={{ width: 84, height: 84, borderRadius: 20 }} />}
          <span style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: 42, color: PURPLE }}>{name}</span>
        </div>
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

export function Thumb(props) {
  useFonts();
  if (props.kind === "split") return <SplitThumb {...props} />;
  if (props.kind === "error") return <ErrorThumb {...props} />;
  if (props.kind === "long") return <LongThumb {...props} />;
  return <ProductThumb {...props} />;
}
