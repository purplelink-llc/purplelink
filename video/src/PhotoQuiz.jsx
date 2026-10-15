import React from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, FONT_BODY, FONT_DISPLAY } from "./theme.js";
import { Backdrop, useFonts } from "./V2.jsx";
import { buildQuiz } from "./photoquiz/plan.js";

// Weekly "Where in the world?" Short (1080x1920): an intro, five of Ben's travel photographs (each a guess with a
// countdown, then the answer: place, country, one fact), and an outro asking for the viewer's score. Built by
// build-photoquiz.mjs from a spec that TikTokPipeline/PhotoPipeline/quiz.py writes each week.
const INK = "oklch(14% 0.07 310)";
const PURPLE = "oklch(50% 0.24 310)";
const LIGHT = "oklch(96% 0.02 310)";
const fr = (s) => Math.round(s * brand.fps);
const up = (p, d = 30) => ({ opacity: p, transform: `translateY(${(1 - p) * d}px)` });
const useT = () => useCurrentFrame() / brand.fps;

// The photo fills the frame and drifts across it (a landscape picture in a vertical frame shows more of itself).
function Photo({ img, t, dur, from = 0, dir = 1 }) {
  const k = clamp01((t + from) / Math.max(1, dur));
  const scale = 1.06 + 0.06 * k;
  const x = dir > 0 ? 35 + 30 * k : 65 - 30 * k;
  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "black" }}>
      <Img src={staticFile(img)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: `${x}% 50%`, transform: `scale(${scale})` }} />
    </AbsoluteFill>
  );
}

function Shade({ top = 0.45, bottom = 0.0 }) {
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, rgba(10,6,14,${top}) 0%, rgba(10,6,14,0) 26%, rgba(10,6,14,0) 52%, rgba(10,6,14,${bottom}) 100%)` }} />
  );
}

function Badge({ n, total }) {
  return (
    <div style={{ position: "absolute", top: 120, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
      <div style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: 40, letterSpacing: "0.08em", color: LIGHT, background: "rgba(20,10,28,0.62)", borderRadius: 999, padding: "12px 34px" }}>
        WHERE IN THE WORLD?  {n}/{total}
      </div>
    </div>
  );
}

function Guess({ seg }) {
  const t = useT();
  const left = Math.max(0, seg.dur - t);
  const n = Math.min(3, Math.ceil(left - 0.15));
  const ring = clamp01(1 - left / Math.min(3.2, seg.dur));
  const p = expoOut(clamp01(t / 0.6));
  const R = 92, C = 2 * Math.PI * R;
  return (
    <AbsoluteFill>
      <Photo img={seg.item.img} t={t} dur={seg.dur + seg.next} dir={seg.index % 2 ? -1 : 1} />
      <Shade top={0.5} bottom={0.55} />
      <Badge n={seg.index + 1} total={seg.total} />
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 520, textAlign: "center", fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 112, color: "white", textShadow: "0 6px 30px rgba(0,0,0,0.55)", ...up(p) }}>Where is this?</div>
      {left <= 3.2 && n > 0 && (
        <div style={{ position: "absolute", left: "50%", bottom: 250, width: 220, height: 220, marginLeft: -110 }}>
          <svg width="220" height="220" viewBox="0 0 220 220" style={{ position: "absolute", inset: 0 }}>
            <circle cx="110" cy="110" r={R} fill="rgba(20,10,28,0.55)" stroke="rgba(255,255,255,0.25)" strokeWidth="12" />
            <circle cx="110" cy="110" r={R} fill="none" stroke="white" strokeWidth="12" strokeLinecap="round"
              strokeDasharray={C} strokeDashoffset={C * ring} transform="rotate(-90 110 110)" />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 104, color: "white" }}>{n}</div>
        </div>
      )}
    </AbsoluteFill>
  );
}

function Answer({ seg }) {
  const t = useT();
  const rv = (d, l = 0.6) => expoOut(clamp01((t - d) / l));
  return (
    <AbsoluteFill>
      <Photo img={seg.item.img} t={t} from={seg.prev} dur={seg.prev + seg.dur} dir={seg.index % 2 ? -1 : 1} />
      <Shade top={0.5} bottom={0.85} />
      <Badge n={seg.index + 1} total={seg.total} />
      <div style={{ position: "absolute", left: 64, right: 64, bottom: 230, display: "grid", gap: 22 }}>
        <div style={{ justifySelf: "start", fontFamily: FONT_BODY, fontWeight: 800, fontSize: 40, letterSpacing: "0.06em", textTransform: "uppercase", color: "white", background: PURPLE, borderRadius: 999, padding: "10px 30px", ...up(rv(0.05)) }}>{seg.item.country}</div>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: seg.item.place.length > 16 ? 96 : 120, lineHeight: 1.0, color: "white", textShadow: "0 6px 30px rgba(0,0,0,0.5)", ...up(rv(0.15), 40) }}>{seg.item.place}</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: 44, lineHeight: 1.32, color: LIGHT, ...up(rv(0.55)) }}>{seg.item.caption || seg.item.fact}</div>
      </div>
      <div style={{ position: "absolute", top: 60, right: 40, fontFamily: FONT_BODY, fontWeight: 600, fontSize: 26, color: "rgba(255,255,255,0.75)" }}>Photo: Benjamin Ampel</div>
    </AbsoluteFill>
  );
}

function Card({ seg }) {
  const t = useT();
  const rv = (d, l = 0.7) => expoOut(clamp01((t - d) / l));
  const intro = seg.kind === "intro";
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <div style={{ position: "absolute", left: 72, right: 72, top: 700, display: "grid", gap: 34 }}>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: 40, letterSpacing: "0.1em", textTransform: "uppercase", color: PURPLE, ...up(rv(0.05)) }}>{intro ? "Travel photo quiz" : "Your score?"}</div>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 128, lineHeight: 1.0, letterSpacing: "-0.02em", color: INK, ...up(rv(0.2), 40) }}>{intro ? "Where in the world?" : "How many did you get?"}</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: 52, lineHeight: 1.3, color: INK, ...up(rv(0.6)) }}>{intro ? `${seg.total} travel photos. Guess each one before the answer.` : `Comment your score out of ${seg.total}.`}</div>
        {!intro && <div style={{ justifySelf: "start", marginTop: 20, fontFamily: FONT_BODY, fontWeight: 700, fontSize: 44, color: "white", background: PURPLE, borderRadius: 999, padding: "16px 40px", ...up(rv(1.0), 20) }}>{seg.url}</div>}
      </div>
    </AbsoluteFill>
  );
}

export function PhotoQuiz({ spec, timing }) {
  useFonts();
  const { segs } = buildQuiz(spec, timing);
  return (
    <AbsoluteFill style={{ background: "black" }}>
      {segs.map((s, i) => (
        <Sequence key={i} from={fr(s.t0)} durationInFrames={fr(s.dur)}>
          {s.kind === "guess" && <Guess seg={s} />}
          {s.kind === "answer" && <Answer seg={s} />}
          {(s.kind === "intro" || s.kind === "outro") && <Card seg={s} />}
          {s.audio && <Sequence from={fr(0.2)}><Audio src={staticFile(s.audio)} /></Sequence>}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}
