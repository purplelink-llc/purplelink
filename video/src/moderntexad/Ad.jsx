// ModernTex Reddit ad renderer. Every app screen is a real background capture of ModernTex on a synthetic sample project
// (see build-moderntex-ad.mjs): frame sequences of typing, a build, PDF sync, a mistyped command and its fix. The only
// drawn graphics are the headline captions, the marker rings and the end card.
import React, { useEffect, useState } from "react";
import { AbsoluteFill, Easing, Img, Sequence, continueRender, delayRender, interpolate, spring, staticFile, useCurrentFrame } from "remotion";
import { C, FORMATS, FPS, SRC, cropFor, lerpRect } from "./layout.js";

const DISPLAY = "Fraunces";
const BODY = "Plus Jakarta Sans";

function useFonts() {
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => {
    const faces = [
      new FontFace(DISPLAY, `url(${staticFile("fonts/fraunces-latin.woff2")})`, { weight: "300 900" }),
      new FontFace(BODY, `url(${staticFile("fonts/plus-jakarta-sans-latin.woff2")})`, { weight: "200 800" }),
    ];
    Promise.all(faces.map((f) => f.load())).then((loaded) => { loaded.forEach((f) => document.fonts.add(f)); continueRender(handle); });
  }, [handle]);
}

const ease = Easing.bezier(0.2, 0.8, 0.2, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
const sec = (f) => f / FPS;

function Ground({ fmt }) {
  const f = useCurrentFrame();
  const drift = Math.sin(f / 80) * 4;
  return (
    <AbsoluteFill style={{ background: C.ground }}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse 75% 50% at 50% ${58 + drift}%, ${C.glow}, transparent 72%)` }} />
    </AbsoluteFill>
  );
}

// A hand-drawn marker loop that draws on (the same mark the other ads use).
function MarkerLoop({ x, y, w, h, progress, color = C.ring, stroke = 7, seed = 0 }) {
  const n = 64, pts = [];
  const a0 = -Math.PI * 0.62 + seed;
  for (let i = 0; i <= n; i++) {
    const a = a0 + (i / n) * Math.PI * 2.12;
    const k = 1 + 0.045 * Math.sin(i * 0.55 + seed * 3);
    pts.push([x + w / 2 + (w / 2) * k * Math.cos(a), y + h / 2 + (h / 2) * k * Math.sin(a)]);
  }
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const len = 4000;
  return (
    <path d={d} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
      strokeDasharray={len} strokeDashoffset={len * (1 - Math.min(1, Math.max(0, progress)))} pathLength={len} />
  );
}

// Headline caption: one or two lines, words rise in one after another; `hl` words take the accent color.
function Caption({ fmt, cap, instant }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const hl = new Set((cap.hl || []).map((w) => w.toLowerCase()));
  const size = cap.size?.[fmt.W === fmt.H ? "1x1" : "4x5"] || fmt.cap.size;
  let k = 0;
  return (
    <div style={{ position: "absolute", left: 64, right: 64, top: fmt.cap.y, height: fmt.cap.h, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
      {cap.lines.map((ln, li) => (
        <div key={li} style={{ fontFamily: DISPLAY, fontWeight: 620, fontSize: size, lineHeight: 1.08, textAlign: "center", color: C.text, letterSpacing: -0.5 }}>
          {ln.split(" ").map((w, i) => {
            const at = instant ? -1 : 0.05 + 0.07 * k++;
            const on = interpolate(t, [at, at + 0.22], [0, 1], { ...clamp, easing: ease });
            const key = w.toLowerCase().replace(/[^\w$.'-]/g, "");
            return (
              <span key={i} style={{ display: "inline-block", marginRight: size * 0.24, opacity: on, color: hl.has(key) ? C.accent : C.text, transform: `translateY(${(1 - on) * 14}px)` }}>{w}</span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// The app window from a frame sequence: capture time = from + t * rate, showing the last frame captured by then.
function Screen({ fmt, sc, dur }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const box = fmt.media;
  const p = interpolate(t, [sc.panAt ?? 0, sc.panEnd ?? dur], [0, 1], { ...clamp, easing: Easing.bezier(0.45, 0, 0.2, 1) });
  const focus = sc.focusTo ? lerpRect(sc.focus, sc.focusTo, p) : sc.focus;
  const cr = cropFor(focus, box);
  const ct = (sc.from || 0) + t * (sc.rate || 1);
  const frames = sc.frames;
  let fi = 0;
  for (let i = 0; i < frames.length; i++) if (frames[i].t <= ct) fi = i;
  const src = frames[fi].src;
  const media = { position: "absolute", left: -cr.x * cr.scale, top: -cr.y * cr.scale, width: SRC.w * cr.scale, height: SRC.h * cr.scale };
  const toBox = (r) => ({ x: (r.x * SRC.w - cr.x) * cr.scale, y: (r.y * SRC.h - cr.y) * cr.scale, w: r.w * SRC.w * cr.scale, h: r.h * SRC.h * cr.scale });
  // A focus on the whole window shows all of it, fitted inside the box with the window's own rounded corners (the macOS
  // chrome is part of the hook); a closer crop fills the box as a card.
  const whole = sc.focus.w >= 0.98 && !sc.focusTo;
  const fit = Math.min(box.w / SRC.w, box.h / SRC.h);
  const radius = whole ? 20 * fit : 28;
  return (
    <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "relative", width: whole ? SRC.w * fit : box.w, height: whole ? SRC.h * fit : box.h, borderRadius: radius, overflow: "hidden", boxShadow: `0 28px 80px oklch(0% 0 0 / 0.55), 0 0 0 1.5px ${C.hairline}` }}>
        <div style={{ position: "absolute", inset: 0, transform: `scale(${1 + (sc.push ?? 0.03) * (t / dur)})`, transformOrigin: "50% 50%" }}>
          <Img src={staticFile(src)} style={whole ? { position: "absolute", left: 0, top: 0, width: SRC.w * fit, height: SRC.h * fit } : media} />
          <svg width={box.w} height={box.h} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
            {(sc.rings || []).map((r, i) => {
              const b = toBox(r);
              const pr = interpolate(t, [r.at, r.at + (r.dur || 0.45)], [0, 1], { ...clamp, easing: ease });
              const fade = r.until != null ? interpolate(t, [r.until, r.until + 0.2], [1, 0], clamp) : 1;
              return t >= r.at && fade > 0 ? <g key={i} opacity={fade}><MarkerLoop {...b} progress={pr} seed={i} stroke={r.stroke || 7} /></g> : null;
            })}
          </svg>
        </div>
      </div>
    </div>
  );
}

function Mark({ fmt, big }) {
  const h = big ? fmt.mark.h * 1.3 : fmt.mark.h;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top: fmt.mark.y - (big ? 10 : 0), height: h, display: "flex", justifyContent: "center", opacity: big ? 1 : 0.86 }}>
      <Img src={staticFile("brand/lockup.png")} style={{ height: h }} />
    </div>
  );
}

function EndCard({ fmt, sc }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const sq = fmt.W === fmt.H;
  const pop = spring({ frame: f, fps: FPS, config: { damping: 16, stiffness: 170 } });
  const line = (i) => interpolate(t, [0.15 + i * 0.12, 0.45 + i * 0.12], [0, 1], { ...clamp, easing: ease });
  const icon = sq ? 200 : 236;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingBottom: sq ? 90 : 110 }}>
      <Img src={staticFile("brand/icon.png")} style={{ width: icon, height: icon, transform: `scale(${0.88 + 0.12 * pop})`, opacity: pop }} />
      <div style={{ fontFamily: DISPLAY, fontWeight: 620, fontSize: sq ? 104 : 118, color: C.text, marginTop: 18, letterSpacing: -1, opacity: line(0) }}>ModernTex</div>
      <div style={{ fontFamily: BODY, fontWeight: 500, fontSize: sq ? 42 : 46, color: C.text2, marginTop: 4, opacity: line(1) }}>{sc.tagline}</div>
      <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: sq ? 46 : 50, color: C.text, marginTop: sq ? 40 : 54, padding: "16px 34px", borderRadius: 999, background: "oklch(100% 0 0 / 0.08)", border: `1.5px solid ${C.hairline}`, opacity: line(2) }}>{sc.price}</div>
      <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: sq ? 52 : 58, color: C.accent, marginTop: sq ? 34 : 44, opacity: line(3) }}>{sc.url}</div>
    </AbsoluteFill>
  );
}

export function Ad({ format, plan }) {
  useFonts();
  const fmt = FORMATS[format];
  return (
    <AbsoluteFill>
      <Ground fmt={fmt} />
      {plan.scenes.map((sc, i) => {
        const from = Math.round(sc.t0 * FPS), len = Math.max(1, Math.round((sc.t1 - sc.t0) * FPS));
        return (
          <Sequence key={i} from={from} durationInFrames={len}>
            <SceneFade first={i === 0 || sc.capSame} len={len}>
              {sc.kind === "end" ? <EndCard fmt={fmt} sc={sc} /> : <Screen fmt={fmt} sc={sc} dur={sc.t1 - sc.t0} />}
              {sc.cap ? <Caption fmt={fmt} cap={sc.cap} instant={i === 0 || sc.capSame} /> : null}
            </SceneFade>
          </Sequence>
        );
      })}
      <Mark fmt={fmt} big={false} />
    </AbsoluteFill>
  );
}

// Scenes cut in with a short fade; the first scene is fully visible on frame 0, so the hook reads from the first second.
function SceneFade({ first, len, children }) {
  const f = useCurrentFrame();
  const o = first ? 1 : interpolate(f, [0, 5], [0, 1], clamp);
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
}
