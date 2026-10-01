import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, FONT_BODY, FONT_DISPLAY } from "./theme.js";
import { Backdrop, FMT, LowerThird, useFonts } from "./V2.jsx";
import { Bumpered, BUMPER } from "./Bumper.jsx";
import { build, TYPE_T0, TYPE_CPS } from "./latexfix/plan.js";

// "Fix this LaTeX error" shorts: a log panel typed out, the source line highlighted and corrected, a plain
// "Compiles" state, an end card. Everything is text drawn here; no screenshots. Brand purple palette only,
// plus one restrained rose tint for the error line.
const MONO = 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, "Courier New", monospace';
const INK = "oklch(14% 0.07 310)";
const MUTED = "oklch(46% 0.04 300)";
const PURPLE = "oklch(50% 0.24 310)";
const PANEL = "oklch(19% 0.05 310)";
const BAR = "oklch(25% 0.07 310)";
const CODE = "oklch(94% 0.02 310)";
const DIM = "oklch(68% 0.05 310)";
const ERR = "oklch(84% 0.08 10)";
const TINT = {
  bad: { band: "oklch(62% 0.17 10 / 0.13)", tok: "oklch(62% 0.17 10 / 0.42)", line: "oklch(78% 0.12 10)" },
  good: { band: "oklch(62% 0.2 310 / 0.18)", tok: "oklch(60% 0.22 310 / 0.62)", line: "oklch(82% 0.13 310)" },
  note: { band: "oklch(62% 0.2 310 / 0.12)", tok: "oklch(60% 0.2 310 / 0.4)", line: "oklch(78% 0.1 310)" },
};
// Layout per format. size: code px. cols: characters that fit one log line.
const LAY = {
  "16x9": { x: 120, w: 1680, top: 56, bottom: 846, size: 36, pad: 44, cols: 73, gap: 22, bar: 54 },
  "9x16": { x: 40, w: 1000, top: 210, bottom: 1240, size: 36, pad: 30, cols: 43, gap: 26, bar: 58 },
};

// 9:16 only: a continuation line indented past the panel width keeps its text and is moved left so it ends at
// the panel edge. Characters are unchanged; only the count of leading spaces differs from the log.
function fitLog(lines, cols) {
  return lines.map((l) => {
    const body = l.trimStart();
    const indent = l.length - body.length;
    if (!indent || l.length <= cols) return l;
    return " ".repeat(Math.max(2, cols - 1 - body.length)) + body; // one column spare for the cursor
  });
}

function Panel({ title, L, children, style }) {
  return (
    <div style={{ width: L.w, borderRadius: 22, background: PANEL, boxShadow: "0 40px 90px oklch(30% 0.14 310 / 0.34), 0 12px 30px oklch(30% 0.14 310 / 0.22)", overflow: "hidden", ...style }}>
      <div style={{ height: L.bar, background: BAR, display: "flex", alignItems: "center", padding: `0 ${L.pad - 8}px`, gap: 10 }}>
        {[0.62, 0.52, 0.42].map((l, i) => (
          <div key={i} style={{ width: 13, height: 13, borderRadius: 7, background: `oklch(${l * 100}% 0.1 310)` }} />
        ))}
        <div style={{ marginLeft: 14, display: "grid" }}>{title}</div>
      </div>
      <div style={{ padding: `${Math.round(L.size * 0.62)}px ${L.pad}px`, fontFamily: MONO, fontSize: L.size, lineHeight: 1.5, color: CODE, display: "grid" }}>{children}</div>
    </div>
  );
}
const titleStyle = { gridArea: "1 / 1", fontFamily: FONT_BODY, fontWeight: 600, fontSize: 25, color: "oklch(84% 0.05 310)", letterSpacing: "0.01em", whiteSpace: "nowrap" };

function split(text, token, last) {
  const i = last ? text.lastIndexOf(token) : text.indexOf(token);
  if (i < 0) return [text, "", ""];
  return [text.slice(0, i), token, text.slice(i + token.length)];
}
function Tok({ children, tint, p }) {
  return (
    <span style={{ background: tint.tok.replace(/\/ ([\d.]+)\)/, (m, a) => `/ ${(a * p).toFixed(3)})`), borderRadius: 7, boxShadow: `0 0.09em 0 0 ${tint.line.replace(")", ` / ${p.toFixed(3)})`)}`, padding: "0.06em 0", WebkitBoxDecorationBreak: "clone", boxDecorationBreak: "clone" }}>{children}</span>
  );
}

function LogBody({ plan, t, L, vertical }) {
  const E = plan.E;
  const lines = vertical ? fitLog(E.log, L.cols) : E.log;
  // typing: count visible (non-space) characters; whitespace comes for free
  let budget = Math.max(0, (t - TYPE_T0) * TYPE_CPS);
  const typedAll = budget >= E.log.join("").replace(/\s/g, "").length;
  const markP = expoOut(clamp01((t - plan.markT) / 0.5));
  const okP = expoOut(clamp01((t - plan.okT) / 0.6));
  let cursorPlaced = false;
  return (
    <>
      <div style={{ gridArea: "1 / 1", opacity: 1 - okP, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
        {lines.map((line, k) => {
          let n = 0;
          for (const ch of line) {
            if (!/\s/.test(ch)) {
              if (budget < 1) break;
              budget -= 1;
            }
            n++;
          }
          const done = n >= line.length;
          if (!done) budget = 0;
          const shown = line.slice(0, n);
          const rest = line.slice(n);
          const color = k === 0 ? ERR : CODE;
          let content = shown;
          if (done && E.mark.line === k && markP > 0) {
            const [a, b, c] = split(line, E.mark.token, E.mark.last);
            content = (
              <>
                {a}
                <Tok tint={E.warning ? TINT.note : TINT.bad} p={markP}>{b}</Tok>
                {c}
              </>
            );
          }
          const cursor = !cursorPlaced && (!done || k === lines.length - 1);
          if (cursor) cursorPlaced = true;
          const blink = typedAll ? (Math.floor(t * 2) % 2 === 0 ? 1 : 0) : 1;
          return (
            <div key={k} style={{ color, minHeight: "1.5em" }}>
              {content}
              {cursor && t > 0.3 && <span style={{ display: "inline-block", width: "0.55em", height: "1.05em", verticalAlign: "-0.16em", background: "oklch(80% 0.12 310)", opacity: blink * 0.9 }} />}
              <span style={{ opacity: 0 }}>{rest}</span>
            </div>
          );
        })}
      </div>
      {okP > 0 && (
        <div style={{ gridArea: "1 / 1", alignSelf: "center", opacity: okP, transform: `translateY(${(1 - okP) * 14}px)`, display: "flex", alignItems: "baseline", flexWrap: "wrap", gap: `4px ${L.size * 0.8}px` }}>
          <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: L.size * 1.9, lineHeight: 1.1, letterSpacing: "-0.01em", color: "oklch(90% 0.09 310)" }}>{E.ok.head}</span>
          <span style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: L.size * 0.95, color: DIM }}>{E.ok.sub}</span>
        </div>
      )}
    </>
  );
}

function StageBody({ stage, p, hiP, L }) {
  const tint = TINT[stage.hi.kind];
  return (
    <div style={{ gridArea: "1 / 1", opacity: p }}>
      {stage.label && <div style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: L.size * 0.62, letterSpacing: "0.08em", textTransform: "uppercase", color: DIM, marginBottom: 6 }}>{stage.label}</div>}
      {stage.lines.map((line, k) => {
        const hot = stage.hi.line === k;
        const also = stage.hi.alsoLine === k;
        const [a, b, c] = hot ? split(line, stage.hi.token) : [line, "", ""];
        return (
          <div key={k} style={{ display: "flex", margin: `0 ${-L.pad * 0.4}px`, padding: `0 ${L.pad * 0.4}px`, borderRadius: 9, background: hot || also ? tint.band.replace(/\/ ([\d.]+)\)/, (m, x) => `/ ${(x * hiP).toFixed(3)})`) : "transparent" }}>
            {stage.gutter && <span style={{ flex: "none", width: "2ch", marginRight: 18, color: hot ? tint.line : DIM, opacity: hot ? 1 : 0.75, textAlign: "right" }}>{k + 1}</span>}
            <span style={{ flex: 1, minWidth: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
              {a}
              {b && <Tok tint={tint} p={hiP}>{b}</Tok>}
              {c}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function EndCard({ plan, t, f }) {
  const t0 = plan.ENDs + 0.1;
  if (t < t0) return null;
  const rv = (d) => expoOut(clamp01((t - t0 - d) / 0.7));
  const [l1, l2] = plan.end.lines;
  const [h1, u1] = l1.split(": ");
  const m = l2.match(/^(.*\.)\s+(\S+)$/);
  const up = (p, d = 24) => ({ opacity: p, transform: `translateY(${(1 - p) * d}px)` });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: f.v ? 30 : 26, transform: `translateY(${f.v ? -110 : -10}px)`, maxWidth: f.v ? 960 : 1600 }}>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: f.v ? 92 : 104, letterSpacing: "-0.02em", lineHeight: 1.08, color: INK, textAlign: "center", ...up(rv(0), 30) }}>{h1}:</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: f.v ? 54 : 58, color: "oklch(99% 0.01 310)", background: PURPLE, borderRadius: 999, padding: f.v ? "18px 44px" : "18px 54px", boxShadow: "0 20px 50px oklch(45% 0.22 310 / 0.4)", whiteSpace: "nowrap", ...up(rv(0.12)) }}>{u1}</div>
        <div style={{ marginTop: f.v ? 44 : 30, display: "flex", flexDirection: f.v ? "column" : "row", alignItems: "center", gap: f.v ? 14 : 22, ...up(rv(0.28), 20) }}>
          <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: f.v ? 44 : 42, color: MUTED, textAlign: "center" }}>{m[1]}</div>
          <div style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: f.v ? 44 : 42, color: INK, background: "oklch(93% 0.06 310)", borderRadius: 999, padding: "10px 30px", whiteSpace: "nowrap" }}>{m[2]}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

function Cut({ id, format, timing, storyboard }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const f = FMT[format];
  const L = LAY[format];
  const plan = build(id, timing, storyboard);
  const inP = expoOut(clamp01((t - 0.1) / 0.8));
  const outP = expoOut(clamp01((t - (plan.ENDs - 0.1)) / 0.6));
  const s1 = plan.stages[0];
  const srcP = expoOut(clamp01((t - s1.t) / 0.8));
  let cur = 0;
  plan.stages.forEach((s, k) => {
    if (t >= s.t) cur = k;
  });
  const titles = [...new Set(plan.stages.map((s) => s.title))];
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <div style={{ position: "absolute", left: L.x, top: L.top, width: L.w, height: L.bottom - L.top, display: "flex", flexDirection: "column", justifyContent: "center", gap: L.gap, opacity: 1 - outP, transform: `translateY(${-outP * 40}px)`, filter: outP > 0 ? `blur(${outP * 8}px)` : undefined }}>
        <Panel L={L} title={<span style={titleStyle}>main.log</span>} style={{ opacity: inP, transform: `translateY(${(1 - inP) * 60}px)` }}>
          <LogBody plan={plan} t={t} L={L} vertical={f.v} />
        </Panel>
        <Panel
          L={L}
          style={{ opacity: srcP, transform: `translateY(${(1 - srcP) * 60}px)` }}
          title={titles.map((ti) => {
            const first = plan.stages.find((s) => s.title === ti);
            const on = plan.stages[cur].title === ti;
            const p = on ? expoOut(clamp01((t - first.t) / 0.45)) : 1 - expoOut(clamp01((t - plan.stages[cur].t) / 0.45));
            return <span key={ti} style={{ ...titleStyle, opacity: ti === titles[0] && cur === 0 ? 1 : p }}>{ti}</span>;
          })}
        >
          {plan.stages.map((s, k) => {
            const next = plan.stages[k + 1];
            const a = k === 0 ? 1 : expoOut(clamp01((t - s.t) / 0.45));
            const b = next ? 1 - expoOut(clamp01((t - next.t) / 0.3)) : 1;
            const hiP = expoOut(clamp01((t - s.hiT) / 0.7));
            return <StageBody key={k} stage={s} p={a * b} hiP={hiP} L={L} />;
          })}
        </Panel>
      </div>
      {plan.lower.map((l, i) => (
        <LowerThird key={i} item={l} t={t} format={format} />
      ))}
      <EndCard plan={plan} t={t} f={f} />
      {plan.audio.map((a) => (
        <Sequence key={a.i} from={Math.round(a.at * brand.fps)}>
          <Audio src={staticFile(timing.scenes[a.i].audio)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}

export function LatexFix({ id, format, timing, storyboard, bumper = BUMPER }) {
  useFonts();
  const plan = build(id, timing, storyboard);
  return (
    <Bumpered format={format} total={plan.total} url="purplelink.llc/latex-errors" bumper={bumper}>
      <Cut id={id} format={format} timing={timing} storyboard={storyboard} />
    </Bumpered>
  );
}
