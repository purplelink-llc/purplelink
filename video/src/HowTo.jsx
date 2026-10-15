import React from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, FONT_BODY, FONT_DISPLAY, FORMATS } from "./theme.js";
import { Backdrop, useFonts } from "./V2.jsx";
import { Bumpered, BUMPER } from "./Bumper.jsx";
import { buildHowTo } from "./howto/plan.js";

// Daily problem-and-fix videos (storyboards/howto/<slug>.json, built by build-howto.mjs). One storyboard, two cuts:
// 16:9 (every scene) and 9:16 (scenes marked "short"). Scene types:
//   hook     the problem in the viewer's words          { title, sub }
//   symptom  the error as the viewer sees it            { label, lines }
//   cause    one plain sentence on why                  { text }
//   steps    commands or clicks that fix it             { label, lines, ui? }
//   check    proof it worked                            { label, lines, ok }
//   app      how the product removes the problem        { name, line, url, img, icon }
// Terminal text types in step with the narration. Nothing on screen is invented output: every symptom and check
// line comes from the verification run recorded in the storyboard (scripts/howto_gate.py checks that).
const MONO = 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, monospace';
const INK = "oklch(14% 0.07 310)";
const MUTED = "oklch(46% 0.04 300)";
const PURPLE = "oklch(50% 0.24 310)";
const PANEL = "oklch(19% 0.05 310)";
const BAR = "oklch(25% 0.07 310)";
const CODE = "oklch(94% 0.02 310)";
const DIM = "oklch(68% 0.05 310)";
const ERR = "oklch(78% 0.14 15)";
const OKC = "oklch(82% 0.15 150)";
const fr = (s) => Math.round(s * brand.fps);
const up = (p, d = 26) => ({ opacity: p, transform: `translateY(${(1 - p) * d}px)` });

function useT() {
  return useCurrentFrame() / brand.fps;
}

function Card({ v, children, style }) {
  return (
    <div style={{ position: "absolute", left: v ? 56 : 140, right: v ? 56 : 140, top: v ? 560 : 290, ...style }}>{children}</div>
  );
}

function Hook({ sc, v }) {
  const t = useT();
  const rv = (d, l = 0.7) => expoOut(clamp01((t - d) / l));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <Card v={v} style={{ display: "grid", gap: v ? 34 : 30 }}>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: v ? 40 : 34, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE, ...up(rv(0.1)) }}>{sc.kicker || "Problem"}</div>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: v ? 112 : 136, lineHeight: 1.04, letterSpacing: "-0.02em", color: INK, ...up(rv(0.25), 34) }}>{sc.title}</div>
        {sc.sub && <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: v ? 54 : 56, lineHeight: 1.3, color: MUTED, ...up(rv(0.6)) }}>{sc.sub}</div>}
      </Card>
    </AbsoluteFill>
  );
}

// A dark terminal-style panel. Lines type in over `typeFor` seconds; "$ " lines are commands, "! " lines errors.
function Term({ sc, v, typeFor, okText }) {
  const t = useT();
  const lines = sc.lines || [];
  const total = lines.reduce((n, l) => n + l.length, 0) || 1;
  let budget = clamp01((t - 0.35) / Math.max(0.8, typeFor)) * total;
  const size = v ? 40 : 50;
  const inP = expoOut(clamp01(t / 0.6));
  const okP = expoOut(clamp01((t - 0.35 - typeFor - 0.2) / 0.6));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <div style={{ position: "absolute", left: v ? 40 : 120, right: v ? 40 : 120, top: v ? 440 : 150, borderRadius: 22, overflow: "hidden", background: PANEL, boxShadow: "0 40px 90px oklch(30% 0.14 310 / 0.34)", ...up(inP, 50) }}>
        <div style={{ height: 58, background: BAR, display: "flex", alignItems: "center", gap: 10, padding: "0 22px" }}>
          {["oklch(70% 0.17 25)", "oklch(82% 0.15 85)", "oklch(75% 0.17 145)"].map((c, i) => <span key={i} style={{ width: 15, height: 15, borderRadius: 99, background: c }} />)}
          <span style={{ marginLeft: 14, fontFamily: FONT_BODY, fontWeight: 600, fontSize: 25, color: "oklch(84% 0.05 310)" }}>{sc.label || "Terminal"}</span>
        </div>
        <div style={{ padding: v ? "26px 28px 34px" : "30px 40px 40px", fontFamily: MONO, fontSize: size, lineHeight: 1.5, color: CODE, minHeight: v ? 520 : 440 }}>
          {lines.map((l, i) => {
            const shown = l.slice(0, Math.max(0, Math.min(l.length, Math.floor(budget))));
            budget -= l.length;
            const cmd = l.startsWith("$ ");
            const err = l.startsWith("! ");
            const body = cmd || err ? shown.slice(2) : shown;
            return (
              <div key={i} style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", color: err ? ERR : cmd ? CODE : DIM, minHeight: size * 1.5 }}>
                {(cmd || err) && shown.length > 0 && <span style={{ color: err ? ERR : OKC }}>{cmd ? "$ " : "! "}</span>}
                {body}
              </div>
            );
          })}
        </div>
      </div>
      {okText && (
        <div style={{ position: "absolute", left: v ? 56 : 140, bottom: v ? 560 : 110, display: "flex", alignItems: "center", gap: 18, ...up(okP) }}>
          <svg width="56" height="56" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill={OKC} /><path d="M6.5 12.5l3.6 3.6 7.4-8" fill="none" stroke={PANEL} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: v ? 60 : 58, color: INK }}>{okText}</span>
        </div>
      )}
      {sc.ui && (
        <div style={{ position: "absolute", left: v ? 56 : 140, right: v ? 56 : 140, bottom: v ? 460 : 100, fontFamily: FONT_BODY, fontWeight: 600, fontSize: v ? 44 : 42, color: MUTED }}>{sc.ui}</div>
      )}
    </AbsoluteFill>
  );
}

function Cause({ sc, v }) {
  const t = useT();
  const p = expoOut(clamp01((t - 0.15) / 0.7));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <Card v={v} style={{ top: v ? 640 : 300, display: "grid", gap: 26 }}>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: v ? 40 : 34, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE, ...up(p) }}>Why it happens</div>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: v ? 84 : 96, lineHeight: 1.12, color: INK, ...up(p, 30) }}>{sc.text}</div>
      </Card>
    </AbsoluteFill>
  );
}

function App({ sc, v }) {
  const t = useT();
  const rv = (d, l = 0.7) => expoOut(clamp01((t - d) / l));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <div style={{ position: "absolute", left: v ? 56 : 120, top: v ? 200 : 120, width: v ? 968 : 760, display: "grid", gap: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20, ...up(rv(0.1)) }}>
          {sc.icon && <Img src={staticFile(sc.icon)} style={{ width: 96, height: 96, borderRadius: 22 }} />}
          <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: v ? 84 : 88, color: INK }}>{sc.name}</span>
        </div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: v ? 48 : 44, lineHeight: 1.3, color: INK, ...up(rv(0.4)) }}>{sc.line}</div>
        <div style={{ justifySelf: "start", fontFamily: FONT_BODY, fontWeight: 700, fontSize: v ? 42 : 38, color: "oklch(99% 0.01 310)", background: PURPLE, borderRadius: 999, padding: "14px 36px", ...up(rv(0.9), 20) }}>{sc.url}</div>
      </div>
      {sc.img && (
        <div style={{ position: "absolute", ...(v ? { left: 56, right: 56, top: 820, height: 640 } : { left: 940, right: 100, top: 150, height: 640 }), borderRadius: 22, overflow: "hidden", background: "white", boxShadow: "0 40px 90px oklch(30% 0.14 310 / 0.34)", ...up(rv(0.5, 0.9), 50) }}>
          <Img src={staticFile(sc.img)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: sc.pos || "left top", display: "block" }} />
        </div>
      )}
    </AbsoluteFill>
  );
}

function Scene({ seg, v }) {
  const sc = seg.scene;
  const typeFor = Math.min(4, Math.max(0.8, seg.spoken * 0.5)); // readable while the narration explains it
  if (sc.type === "hook") return <Hook sc={sc} v={v} />;
  if (sc.type === "cause") return <Cause sc={sc} v={v} />;
  if (sc.type === "app") return <App sc={sc} v={v} />;
  if (sc.type === "check") return <Term sc={sc} v={v} typeFor={typeFor} okText={sc.ok || "Fixed"} />;
  return <Term sc={sc} v={v} typeFor={typeFor} />; // symptom, steps
}

export function HowTo({ storyboard, timing, format = "16x9", bumper = BUMPER }) {
  useFonts();
  const v = FORMATS[format].vertical;
  const { segs, total } = buildHowTo(storyboard, timing, format);
  return (
    <Bumpered format={format} total={total} url={storyboard.url} bumper={bumper}>
      <AbsoluteFill>
        {segs.map((s, i) => (
          <Sequence key={i} from={fr(s.t0)} durationInFrames={fr(s.dur)}>
            <Scene seg={s} v={v} />
            {s.audio && <Sequence from={fr(0.3)}><Audio src={staticFile(s.audio)} /></Sequence>}
          </Sequence>
        ))}
      </AbsoluteFill>
    </Bumpered>
  );
}
