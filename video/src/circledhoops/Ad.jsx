// Circled Hoops Reddit ad renderer. Every app screen is a real capture of the app's sample league (see build-circledhoops.mjs);
// the only drawn graphics are the 4-games hook, type cards, the group chat, and the end card.
import React, { useEffect, useState } from "react";
import { AbsoluteFill, Easing, Img, OffthreadVideo, Sequence, continueRender, delayRender, interpolate, spring, staticFile, useCurrentFrame } from "remotion";
import { C, FORMATS, FPS, SRC, cropFor, lerpRect } from "./layout.js";

const DISPLAY = "Barlow Condensed";
const BODY = "Inter";

function useFonts() {
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => {
    const faces = [
      new FontFace(DISPLAY, `url(${staticFile("fonts/BarlowCondensed-ExtraBold.ttf")})`, { weight: "800" }),
      new FontFace(DISPLAY, `url(${staticFile("fonts/BarlowCondensed-Bold.ttf")})`, { weight: "700" }),
      new FontFace(DISPLAY, `url(${staticFile("fonts/BarlowCondensed-SemiBold.ttf")})`, { weight: "600" }),
      new FontFace(BODY, `url(${staticFile("fonts/Inter.ttf")})`, { weight: "100 900" }),
    ];
    Promise.all(faces.map((f) => f.load())).then((loaded) => { loaded.forEach((f) => document.fonts.add(f)); continueRender(handle); });
  }, [handle]);
}

const ease = Easing.bezier(0.2, 0.8, 0.2, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
const sec = (f) => f / FPS;

// ---------- background ----------
function Court({ fmt, glow = 0.5 }) {
  const f = useCurrentFrame();
  const { W, H } = fmt;
  const drift = Math.sin(f / 90) * 12;
  return (
    <AbsoluteFill style={{ background: C.ground }}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse 70% 45% at 50% ${55 + drift / 10}%, rgba(255,122,26,${0.13 * glow}), transparent 70%)` }} />
      <svg width={W} height={H} style={{ position: "absolute", opacity: 0.09 }}>
        <circle cx={W / 2} cy={H + 40 + drift} r={W * 0.62} fill="none" stroke={C.text} strokeWidth={3} />
        <circle cx={W / 2} cy={H + 40 + drift} r={W * 0.2} fill="none" stroke={C.text} strokeWidth={3} />
        <line x1={0} y1={H * 0.5 + drift} x2={W} y2={H * 0.5 + drift} stroke={C.text} strokeWidth={2} strokeDasharray="2 18" />
      </svg>
    </AbsoluteFill>
  );
}

// A hand-drawn marker loop, the app's signature: a slightly open ellipse whose stroke draws on.
export function MarkerLoop({ x, y, w, h, progress, color = C.accent, stroke = 7, seed = 0 }) {
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
      strokeDasharray={len} strokeDashoffset={len * (1 - Math.min(1, Math.max(0, progress)))} pathLength={len} vectorEffect="non-scaling-stroke" />
  );
}

// ---------- captions ----------
function Caption({ fmt, cap }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const hl = new Set((cap.hl || []).map((w) => w.toLowerCase()));
  const circled = new Set((cap.circle || []).map((w) => w.toLowerCase()));
  const size = cap.center ? Math.round(fmt.cap.size * (fmt.H > 1500 ? 1.75 : 1.6)) : cap.size || fmt.cap.size;
  const box = cap.center ? { top: 0, height: fmt.H } : { top: fmt.cap.y, height: fmt.cap.h };
  return (
    <div style={{ position: "absolute", left: 60, right: 60, ...box, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: size, lineHeight: 1.02, textAlign: "center", color: C.text, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {cap.words.map((w, i) => {
          const on = interpolate(t, [w.s - 0.06, w.s + 0.08], [0, 1], clamp);
          const key = w.w.toLowerCase().replace(/[^\w'-]/g, "");
          const color = hl.has(key) ? C.accent : C.text;
          return (
            <span key={i} style={{ position: "relative", display: "inline-block", marginRight: size * 0.22, opacity: 0.6 + 0.4 * on, color, transform: `translateY(${(1 - on) * 8}px)` }}>
              {w.w}
              {circled.has(key) && t >= w.e - 0.05 ? (
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", left: "-9%", top: "-4%", width: "118%", height: "112%", overflow: "visible" }}>
                  <MarkerLoop x={0} y={0} w={100} h={100} progress={interpolate(t, [w.e - 0.05, w.e + 0.4], [0, 1], { ...clamp, easing: ease })} stroke={size * 0.09} />
                </svg>
              ) : null}
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ---------- the app screen, cropped to a focus box ----------
function Screen({ fmt, shot, dur }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const box = shot.boxes?.[fmt.W === fmt.H ? "1x1" : fmt.H > 1500 ? "9x16" : "4x5"] || fmt.media;
  const p = interpolate(t, [shot.panAt ?? 0, shot.panEnd ?? dur], [0, 1], { ...clamp, easing: Easing.bezier(0.45, 0, 0.2, 1) });
  const focus = shot.focusTo ? lerpRect(shot.focus, shot.focusTo, p) : shot.focus;
  const cr = cropFor(focus, box);
  const enter = spring({ frame: f, fps: FPS, config: { damping: 18, stiffness: 180 } });
  const scale = shot.noEnter ? 1 : 0.94 + 0.06 * enter;
  const media = { position: "absolute", left: -cr.x * cr.scale, top: -cr.y * cr.scale, width: SRC.w * cr.scale, height: SRC.h * cr.scale };
  const toBox = (r) => ({ x: (r.x * SRC.w - cr.x) * cr.scale, y: (r.y * SRC.h - cr.y) * cr.scale, w: r.w * SRC.w * cr.scale, h: r.h * SRC.h * cr.scale });
  return (
    <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, transform: `scale(${scale})`, opacity: shot.noEnter ? 1 : enter }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: 44, overflow: "hidden", background: C.ground, boxShadow: `0 30px 90px rgba(0,0,0,0.6), 0 0 0 2px ${C.hairline}` }}>
        <div style={{ position: "absolute", inset: 0, transform: `scale(${1 + (shot.push ?? 0.04) * (t / dur)})`, transformOrigin: "50% 50%" }}>
        {shot.video
          ? <OffthreadVideo src={staticFile(`media/${shot.src}`)} startFrom={Math.round((shot.from || 0) * FPS)} playbackRate={shot.rate || 1} muted style={media} />
          : <Img src={staticFile(`media/${shot.src}`)} style={media} />}
        <svg width={box.w} height={box.h} style={{ position: "absolute", left: 0, top: 0 }}>
          {(shot.rings || []).map((r, i) => {
            const b = toBox(r);
            const pr = interpolate(t, [r.at, r.at + (r.dur || 0.5)], [0, 1], { ...clamp, easing: ease });
            return t >= r.at ? <MarkerLoop key={i} {...b} progress={pr} seed={i} stroke={r.stroke || 8} color={C[r.color] || r.color || C.accent} /> : null;
          })}
          {(shot.taps || []).map((tp, i) => {
            const k = interpolate(t, [tp.at, tp.at + 0.45], [0, 1], clamp);
            if (t < tp.at || k >= 1) return null;
            const cx = (tp.x * SRC.w - cr.x) * cr.scale, cy = (tp.y * SRC.h - cr.y) * cr.scale;
            return <circle key={i} cx={cx} cy={cy} r={24 + 50 * k} fill={`rgba(255,255,255,${0.35 * (1 - k)})`} stroke={`rgba(255,255,255,${0.8 * (1 - k)})`} strokeWidth={4} />;
          })}
        </svg>
        </div>
      </div>
      {shot.chip ? (
        <div style={{ position: "absolute", left: 24, bottom: 24, padding: "10px 20px", borderRadius: 999, background: "rgba(10,10,13,0.82)", color: C.text, fontFamily: BODY, fontWeight: 600, fontSize: 26, border: `1px solid ${C.hairline}` }}>{shot.chip}</div>
      ) : null}
    </div>
  );
}

// ---------- concept A hook: four games against two ----------
const DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
function GamesHook({ fmt, shot }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const box = fmt.media;
  const d = shot.delays || [0.15, 1.9];
  const rows = [
    { label: "THEIR STARTER", games: [0, 2, 4, 6], color: C.out, delay: d[0] },
    { label: "YOUR STARTER", games: [1, 5], color: C.locked, delay: d[1] },
  ];
  const cell = (fmt.W - 100 - 60) / 7;
  const rowH = cell * (fmt.H > 1500 ? 2.1 : fmt.W === fmt.H ? 1.05 : 1.3);
  const gap = fmt.H > 1500 ? 110 : fmt.W === fmt.H ? 24 : 50;
  const blockH = rows.length * (rowH + 64) + gap;
  const top = box.y + (box.h - blockH) / 2;
  return (
    <div style={{ position: "absolute", inset: 0, opacity: shot.dim ?? 1 }}>
      {rows.map((r, ri) => {
        const y = top + ri * (rowH + 64 + gap);
        const shown = r.games.filter((g, gi) => t >= r.delay + gi * 0.28).length;
        return (
          <div key={ri} style={{ position: "absolute", left: (fmt.W - (cell * 7 + 60)) / 2, top: y, width: cell * 7 + 60 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 14, fontFamily: DISPLAY, fontWeight: 700, fontSize: fmt.H > 1500 ? 52 : 42, color: C.text2, letterSpacing: 1 }}>
              <span>{r.label}</span>
              <span style={{ color: r.color, fontWeight: 800, fontSize: fmt.H > 1500 ? 96 : 72, lineHeight: 1, opacity: shown ? 1 : 0 }}>{shown} {shown === 1 ? "GAME" : "GAMES"}</span>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              {DAYS.map((d, di) => {
                const gi = r.games.indexOf(di);
                const on = gi >= 0 ? spring({ frame: f - Math.round((r.delay + gi * 0.28) * FPS), fps: FPS, config: { damping: 12, stiffness: 220 } }) : 0;
                return (
                  <div key={di} style={{ width: cell, height: rowH, borderRadius: 18, background: gi >= 0 && on > 0.05 ? C.surface2 : C.surface, border: `3px solid ${gi >= 0 ? `rgba(${r.color === C.out ? "255,138,138" : "77,163,255"},${0.9 * on})` : "transparent"}`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", transform: `scale(${1 + 0.08 * on * (1 - on)})` }}>
                    <div style={{ fontFamily: BODY, fontWeight: 600, fontSize: cell * 0.2, color: C.text3 }}>{d}</div>
                    <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: cell * 0.36, color: gi >= 0 ? C.text : C.text3, opacity: gi >= 0 ? 0.3 + 0.7 * on : 0.35 }}>{gi >= 0 ? "GAME" : "—"}</div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------- type card ----------
function TypeCard({ fmt, shot }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const size = shot.size?.[fmt.W === fmt.H ? "1x1" : fmt.H > 1500 ? "9x16" : "4x5"] || (fmt.H > 1500 ? 150 : 120);
  const pop = spring({ frame: f, fps: FPS, config: { damping: 14, stiffness: 200 } });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: 70 }}>
      <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: size, lineHeight: 0.98, textAlign: "center", textTransform: "uppercase", color: C.text, transform: `scale(${0.9 + 0.1 * pop})`, opacity: pop }}>
        {shot.lines.map((ln, i) => (
          <div key={i} style={{ position: "relative", color: ln.color ? C[ln.color] : C.text }}>
            {ln.circle ? (
              <span style={{ position: "relative", display: "inline-block" }}>
                {ln.text}
                <svg style={{ position: "absolute", left: -40, top: -26, overflow: "visible" }} width={10} height={10}>
                  <MarkerLoop x={0} y={0} w={ln.circle.w} h={size * 1.25} progress={interpolate(t, [ln.circle.at, ln.circle.at + 0.45], [0, 1], { ...clamp, easing: ease })} stroke={10} />
                </svg>
              </span>
            ) : ln.text}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
}

// ---------- group chat (concept C) ----------
function Chat({ fmt, shot }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const box = { x: 60, y: fmt.H > 1500 ? 200 : 60, w: fmt.W - 120, h: fmt.H - (fmt.H > 1500 ? 400 : 120) };
  const big = fmt.H > 1500 ? 60 : fmt.W === fmt.H ? 42 : 50;
  const visible = shot.msgs.filter((m) => t >= m.at);
  const typing = shot.msgs.find((m) => t >= m.at - 0.55 && t < m.at && !m.me);
  return (
    <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, display: "flex", flexDirection: "column", justifyContent: "flex-start", gap: fmt.H > 1500 ? 30 : 16, paddingTop: big * 1.6 }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, textAlign: "center", fontFamily: BODY, fontWeight: 600, fontSize: big * 0.7, color: C.text2 }}>{shot.title}</div>
      {visible.map((m, i) => {
        const k = spring({ frame: f - Math.round(m.at * FPS), fps: FPS, config: { damping: 15, stiffness: 240 } });
        return (
          <div key={i} style={{ alignSelf: m.me ? "flex-end" : "flex-start", maxWidth: "82%", transform: `translateY(${(1 - k) * 40}px) scale(${0.9 + 0.1 * k})`, opacity: k, transformOrigin: m.me ? "right bottom" : "left bottom" }}>
            {!m.me ? <div style={{ fontFamily: BODY, fontWeight: 600, fontSize: big * 0.62, color: C.accentText, margin: "0 0 6px 22px" }}>{m.from}</div> : null}
            {m.card ? (
              <div style={{ background: C.surface2, borderRadius: 30, overflow: "hidden", border: `2px solid rgba(255,122,26,0.5)` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 22, padding: 22 }}>
                  <Img src={staticFile("brand/icon.png")} style={{ width: big * 2.4, height: big * 2.4, borderRadius: big * 0.55 }} />
                  <div>
                    <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: big * 1.2, color: C.text }}>Circled Hoops</div>
                    <div style={{ fontFamily: BODY, fontSize: big * 0.72, color: C.text2 }}>{m.card}</div>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ padding: "18px 28px", borderRadius: 34, background: m.me ? C.accent : C.surface2, color: m.me ? C.ground : C.text, fontFamily: BODY, fontWeight: m.me ? 600 : 500, fontSize: big, lineHeight: 1.25 }}>{m.text}</div>
            )}
          </div>
        );
      })}
      {typing ? (
        <div style={{ alignSelf: "flex-start", padding: "22px 30px", borderRadius: 34, background: C.surface2, display: "flex", gap: 10 }}>
          {[0, 1, 2].map((d) => <div key={d} style={{ width: 16, height: 16, borderRadius: 8, background: C.text3, opacity: 0.4 + 0.6 * Math.abs(Math.sin(f / 5 + d)) }} />)}
        </div>
      ) : null}
    </div>
  );
}

// ---------- title and end card ----------
function Title({ fmt, shot }) {
  const f = useCurrentFrame();
  const t = sec(f);
  const k = spring({ frame: f, fps: FPS, config: { damping: 13, stiffness: 160 } });
  const icon = fmt.H > 1500 ? 300 : 220;
  const isEnd = shot.kind === "end";
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 26, transform: `scale(${1 + 0.012 * t})` }}>
      <div style={{ position: "relative", width: icon, height: icon, transform: `scale(${0.7 + 0.3 * k}) rotate(${(1 - k) * -8}deg)`, opacity: k }}>
        <Img src={staticFile("brand/icon.png")} style={{ width: icon, height: icon, borderRadius: icon * 0.225, boxShadow: "0 30px 80px rgba(255,122,26,0.25)" }} />
      </div>
      <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: fmt.H > 1500 ? 150 : 124, lineHeight: 1, color: C.text, textTransform: "uppercase", opacity: interpolate(t, [0.1, 0.35], [0, 1], clamp), transform: `translateY(${interpolate(t, [0.1, 0.4], [20, 0], clamp)}px)` }}>Circled Hoops</div>
      <div style={{ fontFamily: BODY, fontWeight: 500, fontSize: fmt.H > 1500 ? 46 : 40, color: C.text2, opacity: interpolate(t, [0.3, 0.6], [0, 1], clamp) }}>{shot.sub || "Weekly fantasy basketball"}</div>
      {isEnd ? (
        <>
          <div style={{ marginTop: 26, padding: "24px 56px", borderRadius: 999, background: C.accent, color: C.ground, fontFamily: BODY, fontWeight: 700, fontSize: fmt.H > 1500 ? 58 : 50, transform: `scale(${spring({ frame: f - 12, fps: FPS, config: { damping: 10, stiffness: 200 } })})` }}>Free on the App Store</div>
          <div style={{ fontFamily: BODY, fontSize: fmt.H > 1500 ? 40 : 34, color: C.text2, marginTop: 10, opacity: interpolate(t, [0.6, 0.9], [0, 1], clamp) }}>iPhone · No betting · circledhoops.com</div>
        </>
      ) : null}
    </AbsoluteFill>
  );
}

function Shot({ fmt, shot }) {
  const dur = shot.t1 - shot.t0;
  switch (shot.kind) {
    case "screen": return <Screen fmt={fmt} shot={shot} dur={dur} />;
    case "games": return <GamesHook fmt={fmt} shot={shot} />;
    case "type": return <TypeCard fmt={fmt} shot={shot} />;
    case "chat": return <Chat fmt={fmt} shot={shot} />;
    case "title": case "end": return <Title fmt={fmt} shot={shot} />;
    default: return null;
  }
}

function Flash({ at }) {
  const f = useCurrentFrame();
  const o = interpolate(f, [at * FPS, at * FPS + 4], [0.55, 0], clamp);
  return f >= at * FPS ? <AbsoluteFill style={{ background: "#fff", opacity: o, pointerEvents: "none" }} /> : null;
}

export function Ad({ format, plan }) {
  useFonts();
  const fmt = FORMATS[format];
  const fr = (s) => Math.round(s * FPS);
  return (
    <AbsoluteFill style={{ background: C.ground }}>
      <Court fmt={fmt} />
      {plan.shots.map((s, i) => (
        <Sequence key={i} from={fr(s.t0)} durationInFrames={Math.max(1, fr(s.t1) - fr(s.t0))}>
          <Shot fmt={fmt} shot={s} />
        </Sequence>
      ))}
      {plan.caps.map((c, i) => (
        <Sequence key={`c${i}`} from={fr(c.t0)} durationInFrames={Math.max(1, fr(c.t1) - fr(c.t0))}>
          <Caption fmt={fmt} cap={{ ...c, words: c.words.map((w) => ({ ...w, s: w.s - c.t0, e: w.e - c.t0 })) }} />
        </Sequence>
      ))}
      {(plan.flashes || []).map((t, i) => <Flash key={`f${i}`} at={t} />)}
      {plan.note ? (
        <div style={{ position: "absolute", left: 0, right: 0, top: fmt.note.y, textAlign: "center", fontFamily: BODY, fontSize: fmt.H > 1500 ? 26 : 22, color: C.text3, opacity: 0.9 }}>{plan.note}</div>
      ) : null}
    </AbsoluteFill>
  );
}
