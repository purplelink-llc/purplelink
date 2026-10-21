import React, { createContext, useContext, useLayoutEffect, useRef } from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, FONT_BODY, FONT_DISPLAY, FORMATS } from "./theme.js";
import { Backdrop, useFonts } from "./V2.jsx";
import { Bumpered, BUMPER } from "./Bumper.jsx";
import { buildHowTo, DRIFT } from "./howto/plan.js";

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
// QA: one frame per scene (once its entrances are done) logs the on-screen box of every text element to the browser
// console ("QA_RECT {...}"); build-howto.mjs collects them into <slug>-<format>.qa.json for the contrast check in
// scripts/howto_gate.py. Boxes are measured, not estimated, so they follow whatever the layout does.
const QaCtx = createContext(null);
function Q({ name, as: Tag = "div", style, children }) {
  const q = useContext(QaCtx);
  const frame = useCurrentFrame();
  const ref = useRef(null);
  useLayoutEffect(() => {
    if (q && ref.current && frame === q.frame) {
      const r = ref.current.getBoundingClientRect();
      console.log("QA_RECT " + JSON.stringify({ scene: q.index, name, t: q.t, rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] }));
    }
  });
  return <Tag ref={ref} style={style}>{children}</Tag>;
}
const up = (p, d = 26) => ({ opacity: p, transform: `translateY(${(1 - p) * d}px)` });

function useT() {
  return useCurrentFrame() / brand.fps;
}

// Slow scale drift once a scene's entrances are done (the hold): 1.000 to 1 + DRIFT, smoothstep-eased, a pure
// function of the frame so renders are deterministic. Text is re-rasterised each frame at the drifted size.
function Drift({ cues, dur, children }) {
  const t = useT();
  const p = clamp01((t - cues.hold) / Math.max(0.5, dur - cues.hold));
  const e = p * p * (3 - 2 * p);
  return <AbsoluteFill style={{ transform: `scale(${(1 + DRIFT * e).toFixed(5)})`, transformOrigin: "50% 50%" }}>{children}</AbsoluteFill>;
}

function Card({ v, children, style }) {
  return (
    <div style={{ position: "absolute", left: v ? 56 : 140, right: v ? 56 : 140, top: v ? 560 : 290, ...style }}>{children}</div>
  );
}

function Hook({ sc, v, cues, dur }) {
  const t = useT();
  const rv = (d, l = 0.7) => expoOut(clamp01((t - d) / l));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <Drift cues={cues} dur={dur}>
      <Card v={v} style={{ display: "grid", gap: v ? 34 : 30 }}>
        <Q name="kicker" style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: v ? 40 : 34, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE, ...up(rv(cues.kicker)) }}>{sc.kicker || "Problem"}</Q>
        <Q name="title" style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: v ? 112 : 136, lineHeight: 1.04, letterSpacing: "-0.02em", color: INK, ...up(rv(cues.title), 34) }}>{sc.title}</Q>
        {sc.sub && <Q name="sub" style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: v ? 54 : 56, lineHeight: 1.3, color: MUTED, ...up(rv(cues.sub)) }}>{sc.sub}</Q>}
      </Card>
      </Drift>
    </AbsoluteFill>
  );
}

// A dark terminal-style panel. Each line types in on its own cue (plan.js); "$ " lines are commands, "! " lines errors.
function Term({ sc, v, cues, dur, okText }) {
  const t = useT();
  const lines = sc.lines || [];
  const size = v ? 40 : 50;
  const inP = expoOut(clamp01(t / 0.6));
  const okP = expoOut(clamp01((t - (cues.ok ?? 0)) / 0.6));
  const uiP = expoOut(clamp01((t - (cues.ui ?? 0)) / 0.6));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <Drift cues={cues} dur={dur}>
      <div style={{ position: "absolute", left: v ? 40 : 120, right: v ? 40 : 120, top: v ? 440 : 150, borderRadius: 22, overflow: "hidden", background: PANEL, boxShadow: "0 40px 90px oklch(30% 0.14 310 / 0.34)", ...up(inP, 50) }}>
        <div style={{ height: 58, background: BAR, display: "flex", alignItems: "center", gap: 10, padding: "0 22px" }}>
          {["oklch(70% 0.17 25)", "oklch(82% 0.15 85)", "oklch(75% 0.17 145)"].map((c, i) => <span key={i} style={{ width: 15, height: 15, borderRadius: 99, background: c }} />)}
          <span style={{ marginLeft: 14, fontFamily: FONT_BODY, fontWeight: 600, fontSize: 25, color: "oklch(84% 0.05 310)" }}>{sc.label || "Terminal"}</span>
        </div>
        <div style={{ padding: v ? "26px 28px 34px" : "30px 40px 40px", fontFamily: MONO, fontSize: size, lineHeight: 1.5, color: CODE, minHeight: v ? 520 : 440 }}>
          {lines.map((l, i) => {
            const cl = cues.lines[i] || { s: 0, d: 0.3 };
            const shown = l.slice(0, Math.max(0, Math.min(l.length, Math.floor(clamp01((t - cl.s) / cl.d) * l.length))));
            const cmd = l.startsWith("$ ");
            const err = l.startsWith("! ");
            const body = cmd || err ? shown.slice(2) : shown;
            return (
              <Q key={i} name={`line ${i}`} style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", color: err ? ERR : cmd ? CODE : DIM, minHeight: size * 1.5 }}>
                {(cmd || err) && shown.length > 0 && <span style={{ color: err ? ERR : OKC }}>{cmd ? "$ " : "! "}</span>}
                {body}
              </Q>
            );
          })}
        </div>
      </div>
      {okText && (
        <div style={{ position: "absolute", left: v ? 56 : 140, bottom: v ? 560 : 110, display: "flex", alignItems: "center", gap: 18, ...up(okP) }}>
          <svg width="56" height="56" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill={OKC} /><path d="M6.5 12.5l3.6 3.6 7.4-8" fill="none" stroke={PANEL} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <Q as="span" name="ok" style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: v ? 60 : 58, color: INK }}>{okText}</Q>
        </div>
      )}
      {sc.ui && (
        <Q name="ui" style={{ position: "absolute", left: v ? 56 : 140, right: v ? 56 : 140, bottom: v ? 460 : 100, fontFamily: FONT_BODY, fontWeight: 600, fontSize: v ? 44 : 42, color: MUTED, opacity: uiP }}>{sc.ui}</Q>
      )}
      </Drift>
    </AbsoluteFill>
  );
}

function Cause({ sc, v, cues, dur }) {
  const t = useT();
  const p = expoOut(clamp01((t - cues.text) / 0.7));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <Drift cues={cues} dur={dur}>
      <Card v={v} style={{ top: v ? 640 : 300, display: "grid", gap: 26 }}>
        <Q name="label" style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: v ? 40 : 34, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE, ...up(p) }}>Why it happens</Q>
        <Q name="text" style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: v ? 84 : 96, lineHeight: 1.12, color: INK, ...up(p, 30) }}>{sc.text}</Q>
      </Card>
      </Drift>
    </AbsoluteFill>
  );
}

function App({ sc, v, cues, dur }) {
  const t = useT();
  const rv = (d, l = 0.7) => expoOut(clamp01((t - d) / l));
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <Drift cues={cues} dur={dur}>
      <div style={{ position: "absolute", left: v ? 56 : 120, top: v ? 200 : 120, width: v ? 968 : 760, display: "grid", gap: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20, ...up(rv(cues.name)) }}>
          {sc.icon && <Img src={staticFile(sc.icon)} style={{ width: 96, height: 96, borderRadius: 22 }} />}
          <Q as="span" name="name" style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: v ? 84 : 88, color: INK }}>{sc.name}</Q>
        </div>
        <Q name="line" style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: v ? 48 : 44, lineHeight: 1.3, color: INK, ...up(rv(cues.line)) }}>{sc.line}</Q>
        <Q name="url" style={{ justifySelf: "start", fontFamily: FONT_BODY, fontWeight: 700, fontSize: v ? 42 : 38, color: "oklch(99% 0.01 310)", background: PURPLE, borderRadius: 999, padding: "14px 36px", ...up(rv(cues.url), 20) }}>{sc.url}</Q>
      </div>
      {sc.img && (
        <div style={{ position: "absolute", ...(v ? { left: 56, right: 56, top: 820, height: 640 } : { left: 940, right: 100, top: 150, height: 640 }), borderRadius: 22, overflow: "hidden", background: "white", boxShadow: "0 40px 90px oklch(30% 0.14 310 / 0.34)", ...up(rv(cues.img, 0.9), 50) }}>
          <Img src={staticFile(sc.img)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: sc.pos || "left top", display: "block" }} />
        </div>
      )}
      </Drift>
    </AbsoluteFill>
  );
}

function Scene({ seg, v, qa }) {
  const sc = seg.scene;
  const { cues, dur } = seg; // cue times come from the word timings (src/howto/plan.js)
  const body =
    sc.type === "hook" ? <Hook sc={sc} v={v} cues={cues} dur={dur} /> :
    sc.type === "cause" ? <Cause sc={sc} v={v} cues={cues} dur={dur} /> :
    sc.type === "app" ? <App sc={sc} v={v} cues={cues} dur={dur} /> :
    sc.type === "check" ? <Term sc={sc} v={v} cues={cues} dur={dur} okText={sc.ok || "Fixed"} /> :
    <Term sc={sc} v={v} cues={cues} dur={dur} />; // symptom, steps
  const frame = Math.max(1, Math.round(Math.min(cues.hold + 0.15, dur - 0.2) * brand.fps));
  return <QaCtx.Provider value={qa ? { index: seg.index, frame, t: qa.offset + seg.t0 + frame / brand.fps } : null}>{body}</QaCtx.Provider>;
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
            <Scene seg={s} v={v} qa={bumper ? { offset: bumper.open - bumper.xf } : null} />
            {s.audio && <Sequence from={fr(0.3)}><Audio src={staticFile(s.audio)} /></Sequence>}
          </Sequence>
        ))}
      </AbsoluteFill>
    </Bumpered>
  );
}
