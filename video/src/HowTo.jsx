import React, { createContext, useContext, useLayoutEffect, useRef } from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, FONT_BODY, FONT_DISPLAY, FORMATS } from "./theme.js";
import { Backdrop, useFonts } from "./V2.jsx";
import { Bumpered, BUMPER } from "./Bumper.jsx";
import { buildHowTo, DRIFT } from "./howto/plan.js";
import { MotionPane, MW, MH, SWEEP } from "./LensesSim.jsx";

// Daily problem-and-fix videos (storyboards/howto/<slug>.json, built by build-howto.mjs). One storyboard, two cuts:
// 16:9 (every scene) and 9:16 (scenes marked "short"). Scene types:
//   hook     the problem in the viewer's words          { title, sub }
//   symptom  the error as the viewer sees it            { label, lines }
//   cause    one plain sentence on why                  { text }
//   steps    commands or clicks that fix it             { label, lines, ui? }
//   panel    a settings step with a before/after wipe  { label, lines, before, after, before_sub?, after_sub?, ui? }, or
//            kind "slowmo" (60 Hz and 120 Hz panes slowed 4x)  (Lenses how-to; stills from build-lenses-stills.mjs)
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

// A settings step with a drawn illustration (Lenses how-to): numbered lines on one side, the drawing on the other.
// The drawing moves from its before state to its after state when the last line starts.
const sm = (x) => x * x * (3 - 2 * x);
const CHIP = { fontFamily: FONT_BODY, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", borderRadius: 999, color: "white" };

// Before and after stills with a divider that sweeps from BEFORE to AFTER on the wipe cue, then keeps moving slowly
// so the picture is never frozen. The stills are simulated views (src/LensesSim.jsx), and the frame says so.
function Wipe({ before, after, beforeSub, afterSub, w, h, wipe, t }) {
  const pre = clamp01(t / Math.max(0.5, wipe)) * 0.04;
  const sweep = clamp01((t - wipe) / 1.6);
  const t1 = wipe + 1.6;
  const pong = t > t1 ? 1 - 0.55 * (0.5 - 0.5 * Math.cos((2 * Math.PI * (t - t1)) / 9)) : 1;
  const x = t < wipe ? pre : sweep < 1 ? 0.04 + (1 - 0.04) * sm(sweep) : pong;
  const chip = (txt, left, on) => (
    <span style={{ ...CHIP, position: "absolute", top: 16, ...(left ? { left: 16 } : { right: 16 }), fontSize: Math.round(w / 38), padding: "6px 22px", background: on ? PURPLE : "oklch(14% 0.07 310)", opacity: on ? 1 : 0.9 }}>{txt}</span>
  );
  return (
    <div style={{ position: "relative", width: w, height: h, borderRadius: 18, overflow: "hidden", background: "#000", boxShadow: "0 40px 90px oklch(30% 0.14 310 / 0.34)" }}>
      <Img src={staticFile(before)} style={{ position: "absolute", inset: 0, width: w, height: h, display: "block" }} />
      <div style={{ position: "absolute", inset: 0, clipPath: `inset(0 ${(1 - x) * 100}% 0 0)` }}>
        <Img src={staticFile(after)} style={{ position: "absolute", inset: 0, width: w, height: h, display: "block" }} />
      </div>
      <div style={{ position: "absolute", top: 0, bottom: 0, left: x * w - 2, width: 4, background: "white", boxShadow: "0 0 18px rgba(0,0,0,0.45)" }} />
      <div style={{ position: "absolute", top: h / 2 - 22, left: x * w - 22, width: 44, height: 44, borderRadius: 99, background: "white", boxShadow: "0 4px 18px rgba(0,0,0,0.4)" }} />
      {chip(`Before  ${beforeSub || ""}`, true, x < 0.5)}
      {chip(`After  ${afterSub || ""}`, false, x >= 0.5)}
    </div>
  );
}

function Lines({ sc, v, cues, t }) {
  const lines = sc.lines || [];
  return (
    <>
      <Q name="label" style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: v ? 40 : 34, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE }}>{sc.label}</Q>
      {lines.map((l, i) => {
        const p = expoOut(clamp01((t - (cues.lines[i] || { s: 0 }).s) / 0.5));
        return (
          <div key={i} style={{ display: "flex", gap: 20, alignItems: "baseline", ...up(p, 18) }}>
            <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 650, fontSize: v ? 52 : 44, color: PURPLE, minWidth: 44 }}>{i + 1}</span>
            <Q as="span" name={`line ${i}`} style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: v ? 52 : 44, lineHeight: 1.15, color: INK }}>{l}</Q>
          </div>
        );
      })}
      {sc.ui && <Q name="ui" style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: v ? 40 : 32, lineHeight: 1.3, color: MUTED, opacity: expoOut(clamp01((t - (cues.ui ?? 0)) / 0.6)) }}>{sc.ui}</Q>}
    </>
  );
}

const NOTE = { fontFamily: FONT_BODY, fontWeight: 600, color: MUTED };

// 60 Hz and 120 Hz panes, slowed 4x. At 30 fps one video frame is 1/120 s of real time: the 120 Hz pane takes a new
// step every frame, the 60 Hz pane every second frame, twice as far. Nothing is interpolated.
function Slowmo({ sc, v, cues, t }) {
  const real = Math.max(0, t - 0.4) / 4;
  const k = v ? 1.0 : 0.9;
  const W = Math.round(MW * k), H = Math.round(MH * k);
  const pane = (hz, left, top) => {
    const n = Math.floor(real * hz + 1e-6);
    return (
      <div style={{ position: "absolute", left, top }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 18, marginBottom: 10 }}>
          <Q as="span" name={`hz ${hz}`} style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: v ? 72 : 64, color: INK }}>{hz} Hz</Q>
          <Q as="span" name={`count ${hz}`} style={{ ...NOTE, fontSize: v ? 32 : 28 }}>{`${n} redraws, step ${Math.round(SWEEP / hz)} px`}</Q>
        </div>
        <div style={{ width: W, height: H, borderRadius: 16, overflow: "hidden", boxShadow: "0 30px 70px oklch(30% 0.14 310 / 0.34)", position: "relative" }}>
          <div style={{ width: MW, height: MH, transform: `scale(${k})`, transformOrigin: "0 0" }}>
            <MotionPane hz={hz} mode="live" tReal={real} />
          </div>
        </div>
      </div>
    );
  };
  const lines = sc.lines || [];
  return (
    <>
      <Q name="label" style={{ position: "absolute", left: v ? 56 : 90, top: v ? 120 : 70, fontFamily: FONT_BODY, fontWeight: 800, fontSize: v ? 40 : 34, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE }}>{sc.label}</Q>
      <span style={{ ...CHIP, position: "absolute", right: v ? 56 : 90, top: v ? 112 : 60, fontSize: v ? 40 : 34, padding: "8px 28px", background: PURPLE }}>Slowed 4x</span>
      {v ? <>{pane(60, 56, 220)}{pane(120, 56, 220 + H + 120)}</> : <>{pane(60, 90, 160)}{pane(120, 90 + W + 60, 160)}</>}
      <div style={{ position: "absolute", left: v ? 56 : 90, right: v ? 56 : 90, top: v ? 220 + 2 * (H + 120) - 30 : 160 + H + 120, display: "grid", gap: 8 }}>
        {lines.map((l, i) => (
          <Q key={i} name={`cap ${i}`} style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: v ? 44 : 38, lineHeight: 1.2, color: INK, opacity: expoOut(clamp01((t - (cues.lines[i] || { s: 0 }).s) / 0.5)) }}>{l}</Q>
        ))}
        <Q name="note" style={{ ...NOTE, fontSize: v ? 30 : 26, marginTop: 6 }}>Simulated, not footage through the glasses. Slowed 4x because video plays at most 60 frames a second.</Q>
      </div>
    </>
  );
}

function Panel({ sc, v, cues, dur }) {
  const t = useT();
  const inP = expoOut(clamp01(t / 0.6));
  const slow = sc.kind === "slowmo";
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <Drift cues={cues} dur={dur}>
        {slow ? <Slowmo sc={sc} v={v} cues={cues} t={t} /> : (
          <>
            <div style={{ position: "absolute", ...(v ? { left: 56, top: 130 } : { left: 60, top: 190 }), ...up(inP, 50) }}>
              <Wipe before={sc.before} after={sc.after} beforeSub={sc.before_sub} afterSub={sc.after_sub} w={v ? 968 : 1060} h={v ? 545 : 596} wipe={cues.wipe ?? 1.5} t={t} />
              <div style={{ ...NOTE, fontSize: v ? 28 : 24, marginTop: 14 }}>Simulated view through the glasses{sc.zoomed ? ". Zoomed in" : ""}</div>
            </div>
            <div style={{ position: "absolute", ...(v ? { left: 56, top: 860, width: 968 } : { left: 1160, top: 190, width: 700 }), display: "grid", gap: v ? 24 : 20, ...up(inP, 30) }}>
              <Lines sc={sc} v={v} cues={cues} t={t} />
            </div>
          </>
        )}
      </Drift>
    </AbsoluteFill>
  );
}

function App({ sc, v, cues, dur }) {
  const t = useT();
  const rv = (d, l = 0.7) => expoOut(clamp01((t - d) / l));
  const imgs = sc.imgs || [];
  const cw = v ? 474 : 430, ch = v ? 267 : 242;
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
      {imgs.length > 0 && (
        <div style={{ position: "absolute", ...(v ? { left: 56, top: 900 } : { left: 940, top: 200 }), display: "grid", gridTemplateColumns: `${cw}px ${cw}px`, gap: 20 }}>
          {imgs.map((m, i) => (
            <div key={i} style={{ width: cw, height: ch, borderRadius: 14, overflow: "hidden", boxShadow: "0 24px 60px oklch(30% 0.14 310 / 0.34)", ...up(rv(cues.img + i * 0.25, 0.8), 40) }}>
              <Img src={staticFile(m)} style={{ width: "100%", height: "100%", display: "block" }} />
            </div>
          ))}
          <div style={{ ...NOTE, gridColumn: "1 / span 2", fontSize: v ? 26 : 24 }}>Simulated views through the glasses</div>
        </div>
      )}
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
    sc.type === "panel" ? <Panel sc={sc} v={v} cues={cues} dur={dur} /> :
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
