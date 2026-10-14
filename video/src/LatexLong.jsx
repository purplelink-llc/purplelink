import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, FONT_BODY, FONT_DISPLAY } from "./theme.js";
import { Backdrop, useFonts } from "./V2.jsx";
import { Bumpered, BUMPER } from "./Bumper.jsx";
import { Cut } from "./LatexFix.jsx";
import { buildLong } from "./latexfix/longplan.js";

// The long "LaTeX Error: File not found" tutorial: title card, one cut per cause (the same typed log, highlighted
// source and fix as the Shorts, minus the end card), then a ModernTex card with the product's own editor screenshot.
// Everything on screen is text drawn here, a real screenshot from the site, or a real recording of ModernTex
// (assets/footage, window-only, invented sample projects); nothing is simulated.
const INK = "oklch(14% 0.07 310)";
const MUTED = "oklch(46% 0.04 300)";
const PURPLE = "oklch(50% 0.24 310)";
const up = (p, d = 26) => ({ opacity: p, transform: `translateY(${(1 - p) * d}px)` });
const fr = (s) => Math.round(s * brand.fps);

const CAUSES = [
  "The package is not installed",
  "The package name is misspelled",
  "A style file from a template is not in the project folder",
  "The class name is wrong",
  "An \\input path does not match the file on disk",
];

function TitleCard({ timing }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const rv = (d, len = 0.7) => expoOut(clamp01((t - d) / len));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center", gap: 30 }}>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: 34, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE, ...up(rv(0.1)) }}>LaTeX error</div>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: 118, letterSpacing: "-0.02em", lineHeight: 1.04, color: INK, ...up(rv(0.25), 34) }}>File not found</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: 44, color: MUTED, ...up(rv(0.5)) }}>The five usual causes, most likely first, and the fix for each.</div>
        <div style={{ display: "grid", gap: 14, marginTop: 18 }}>
          {CAUSES.map((c, i) => {
            const p = rv(3.2 + i * 1.0, 0.6);
            return (
              <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 22, ...up(p, 18) }}>
                <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: 40, color: PURPLE, width: 44 }}>{i + 1}</span>
                <span style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: 40, color: INK }}>{c}</span>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
      <Sequence from={fr(0.25)}><Audio src={staticFile(timing.scenes[0].audio)} /></Sequence>
    </AbsoluteFill>
  );
}

const MT_POINTS = [
  "Lists each build error in plain language",
  "Offers an Install button with the package name when one is missing",
  "Free 7-day trial, no account",
];

function ModernTexCard({ timing }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const rv = (d, len = 0.7) => expoOut(clamp01((t - d) / len));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <div style={{ position: "absolute", left: 120, top: 120, width: 760, display: "grid", gap: 26 }}>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: 104, letterSpacing: "-0.02em", color: INK, lineHeight: 1.04, ...up(rv(0.15), 30) }}>ModernTex</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: 42, color: MUTED, ...up(rv(0.35)) }}>A native LaTeX editor for the Mac</div>
        <div style={{ display: "grid", gap: 20, marginTop: 14 }}>
          {MT_POINTS.map((m, i) => (
            <div key={i} style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: 38, color: INK, lineHeight: 1.25, ...up(rv(1.2 + i * 0.7, 0.6), 18) }}>{m}</div>
          ))}
        </div>
        <div style={{ marginTop: 26, alignSelf: "start", justifySelf: "start", fontFamily: FONT_BODY, fontWeight: 700, fontSize: 40, color: "oklch(99% 0.01 310)", background: PURPLE, borderRadius: 999, padding: "16px 40px", ...up(rv(3.6), 20) }}>purplelink.llc/moderntex</div>
      </div>
      <div style={{ position: "absolute", left: 940, top: 150, width: 900, borderRadius: 22, overflow: "hidden", boxShadow: "0 40px 90px oklch(30% 0.14 310 / 0.34), 0 12px 30px oklch(30% 0.14 310 / 0.22)", ...up(rv(0.6, 0.9), 50) }}>
        <Img src={staticFile("img/moderntex-editor.webp")} style={{ width: 900, display: "block" }} />
      </div>
      <Sequence from={fr(0.25)}><Audio src={staticFile(timing.scenes[0].audio)} /></Sequence>
    </AbsoluteFill>
  );
}

// Real ModernTex footage: a window-only recording of the app (invented sample project) fixing the cause just shown.
function ClipCard({ id, timing }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const rv = (d, len = 0.7) => expoOut(clamp01((t - d) / len));
  const H = 860, W = Math.round(H * 1800 / 1304);
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 46, textAlign: "center", fontFamily: FONT_BODY, fontWeight: 700, fontSize: 34, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE, ...up(rv(0.05)) }}>In ModernTex</div>
      <div style={{ position: "absolute", left: (1920 - W) / 2, top: 130, width: W, height: H, borderRadius: 20, overflow: "hidden", boxShadow: "0 40px 90px oklch(30% 0.14 310 / 0.34), 0 12px 30px oklch(30% 0.14 310 / 0.22)", ...up(rv(0.1, 0.8), 40) }}>
        <OffthreadVideo src={staticFile(`clips/${id}.mp4`)} muted style={{ width: W, height: H, display: "block" }} />
      </div>
      <Sequence from={fr(0.25)}><Audio src={staticFile(timing.scenes[0].audio)} /></Sequence>
    </AbsoluteFill>
  );
}

export function LatexLong({ parts, bumper = BUMPER }) {
  useFonts();
  const { segs, total } = buildLong(parts);
  return (
    <Bumpered format="16x9" total={total} url="purplelink.llc/latex-errors/file-not-found" bumper={bumper}>
      <AbsoluteFill>
        {segs.map((s, i) => (
          <Sequence key={i} from={fr(s.t0)} durationInFrames={fr(s.dur)}>
            {s.kind === "title" && <TitleCard timing={s.timing} />}
            {s.kind === "cut" && <Cut id={s.id} format="16x9" timing={s.timing} storyboard={s.storyboard} showEnd={false} />}
            {s.kind === "clip" && <ClipCard id={s.id} timing={s.timing} />}
            {s.kind === "moderntex" && <ModernTexCard timing={s.timing} />}
          </Sequence>
        ))}
      </AbsoluteFill>
    </Bumpered>
  );
}
