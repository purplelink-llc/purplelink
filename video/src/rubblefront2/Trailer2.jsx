import React, { useEffect, useState } from "react";
import { AbsoluteFill, Easing, Freeze, Img, OffthreadVideo, Sequence, continueRender, delayRender, staticFile, useCurrentFrame } from "remotion";
import brand from "../../brand-rubblefront.json";

const C = brand.colors;
const DISPLAY = `"${brand.fonts.display.family}", Georgia, serif`;
const BODY = `"${brand.fonts.body.family}", system-ui, sans-serif`;
const clamp01 = (v) => Math.min(1, Math.max(0, v));
const expoOut = Easing.bezier(0.16, 1, 0.3, 1);
const inOut = Easing.bezier(0.45, 0, 0.25, 1);
const lerp = (a, b, p) => a + (b - a) * p;

const FMT = {
  "16x9": { W: 1920, H: 1080, vertical: false },
  "9x16": { W: 1080, H: 1920, vertical: true },
};

function useFonts() {
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => {
    const faces = Object.values(brand.fonts).map((f) => {
      const face = new FontFace(f.family, `url(${staticFile("fonts/" + f.file.split("/").pop())})`, { weight: f.weight });
      document.fonts.add(face);
      return face.load();
    });
    Promise.all(faces).then(() => continueRender(handle), () => continueRender(handle));
  }, [handle]);
}

const rnd = (n) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };

function Video({ shot, span, fmt, fps }) {
  const src = staticFile(`media/${shot.clip}.mp4`);
  const startFrom = Math.max(0, Math.round(span.src * fps));
  const el = <OffthreadVideo src={src} muted startFrom={startFrom} playbackRate={span.rate || 1} style={{ width: "100%", height: "100%", objectFit: "fill" }} />;
  return span.rate === 0 ? <Freeze frame={0}>{el}</Freeze> : el;
}

function Footage({ shot, fmt, fps }) {
  const f = useCurrentFrame();
  const t = f / fps;
  const dur = shot.dur;
  // camera: crop, animated punch, shake and hit pulses
  let crop = shot.crop || { x: 0.5, y: 0.5, s: 1 };
  if (crop.to) {
    const q = inOut(clamp01(t / dur));
    crop = { x: lerp(crop.x, crop.to.x, q), y: lerp(crop.y, crop.to.y, q), s: lerp(crop.s, crop.to.s ?? crop.s, q) };
  }
  const pn = shot.punch ? lerp(shot.punch.from, shot.punch.to, inOut(clamp01(t / dur))) : 1;
  let dx = 0, dy = 0, pulse = 0;
  for (const s of shot.shake) {
    const lt = t - s.at;
    if (lt < 0 || lt > s.dur) continue;
    const k = Math.pow(1 - lt / s.dur, 2);
    dx += (rnd(f * 3.1) - 0.5) * 2 * s.amp * k;
    dy += (rnd(f * 7.7 + 5) - 0.5) * 2 * s.amp * k;
    pulse += (s.zoom ?? 0.03) * k * 1.6;
  }
  const scale = crop.s * pn * (1 + pulse);
  const origin = fmt.vertical ? "50% 50%" : `${crop.x * 100}% ${crop.y * 100}%`;
  const spans = shot.spans;
  const filter = shot.grade === "cold" ? "contrast(1.1) saturate(1.05) brightness(0.95) hue-rotate(-6deg)" : shot.grade === "warm" ? "contrast(1.1) saturate(1.18) brightness(0.98)" : "contrast(1.1) saturate(1.12) brightness(0.96)";
  let vbox;
  const fit = fmt.vertical && shot.v && shot.v.fit ? shot.v.fit : null;
  if (fmt.vertical) {
    const v = shot.v || { x: 0.5, y: 0.5, s: 1 };
    const H = fmt.H * (v.s ?? 1);
    const W = H * (16 / 9);
    vbox = { position: "absolute", width: W, height: H, left: -(W - fmt.W) * (v.x ?? 0.5), top: -(H - fmt.H) * (v.y ?? 0.5) };
  } else {
    vbox = { position: "absolute", inset: 0 };
  }
  const renderSpans = () =>
    spans.map((sp, k) => {
      const from = Math.round(sp.start * fps);
      const to = k + 1 < spans.length ? Math.round(spans[k + 1].start * fps) : Math.round(dur * fps);
      return (
        <Sequence key={k} from={from} durationInFrames={Math.max(1, to - from)} layout="none">
          <AbsoluteFill><Video shot={shot} span={sp} fmt={fmt} fps={fps} /></AbsoluteFill>
        </Sequence>
      );
    });
  // fit mode (9:16): the whole 16:9 picture in a window under a blurred copy, so a game card is not cut off
  let fitWin = null;
  if (fit) {
    const z = fit.z ?? 1.45;
    const winH = fit.h ?? 780;
    const W = fmt.W * z;
    const H = (fmt.W * 9 / 16) * z;
    fitWin = { top: fit.top ?? 230, h: winH, box: { position: "absolute", width: W, height: H, left: -(W - fmt.W) * (fit.x ?? 0.0), top: -(H - winH) * (fit.y ?? 0.4) } };
  }
  const fadeIn = shot.fadeIn ? clamp01(f / (shot.fadeIn * fps)) : 1;
  const fadeOut = shot.fadeOut ? clamp01((dur - t) / shot.fadeOut) : 1;
  return (
    <AbsoluteFill style={{ background: "#07060e", overflow: "hidden", opacity: Math.min(fadeIn, fadeOut) }}>
      <AbsoluteFill style={{ transform: `translate(${dx}px, ${dy}px) scale(${scale})`, transformOrigin: origin, filter }}>
        {fit ? (
          <>
            <div style={{ ...vbox, filter: "blur(30px) brightness(0.4)" }}>{renderSpans()}</div>
            <div style={{ position: "absolute", left: 0, top: fitWin.top, width: fmt.W, height: fitWin.h, overflow: "hidden", boxShadow: "0 0 70px rgba(0,0,0,0.7)" }}>
              <div style={fitWin.box}>{renderSpans()}</div>
            </div>
          </>
        ) : (
          <div style={vbox}>{renderSpans()}</div>
        )}
      </AbsoluteFill>
      {shot.dim ? <AbsoluteFill style={{ background: `rgba(7,6,14,${shot.dim})` }} /> : null}
      {/* vignette */}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 52%, rgba(4,3,10,0.62) 100%)" }} />
      {shot.flash.map((fl, k) => {
        const lt = t - fl.at;
        if (lt < 0 || lt > fl.dur) return null;
        const o = (fl.amp ?? 0.75) * Math.pow(1 - lt / fl.dur, 2);
        return <AbsoluteFill key={k} style={{ background: fl.color || "#fff7e8", opacity: o, mixBlendMode: "screen" }} />;
      })}
    </AbsoluteFill>
  );
}

function BlackScene({ fmt }) {
  return (
    <AbsoluteFill style={{ background: "#07060e" }}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 55%, rgba(122,63,216,0.22) 0%, rgba(7,6,14,0) 62%)" }} />
    </AbsoluteFill>
  );
}

function LogoScene({ shot, fmt, fps }) {
  const f = useCurrentFrame();
  const t = f / fps;
  const p = expoOut(clamp01(t / 0.28));
  const drift = 1 + 0.035 * clamp01(t / shot.dur);
  const w = fmt.vertical ? 980 : 1360;
  const flash = Math.pow(clamp01(1 - t / 0.35), 2);
  return (
    <AbsoluteFill style={{ background: "#07060e", alignItems: "center", justifyContent: "center" }}>
      <Img src={staticFile("media/herobg.png")} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", opacity: 0.3, filter: "blur(10px) brightness(0.7)", transform: `scale(${1.05 + 0.04 * clamp01(t / shot.dur)})` }} />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(43,208,222,0.20) 0%, rgba(122,63,216,0.16) 38%, rgba(7,6,14,0.6) 80%)" }} />
      <div style={{ transform: `scale(${(1.32 - 0.32 * p) * drift})`, opacity: clamp01(t / 0.05), filter: "drop-shadow(0 0 40px rgba(43,208,222,0.35))" }}>
        <Img src={staticFile("brand/logo.png")} style={{ width: w, height: "auto" }} />
      </div>
      <AbsoluteFill style={{ background: "#ffffff", opacity: flash * 0.8, mixBlendMode: "screen" }} />
    </AbsoluteFill>
  );
}

function EndCard({ end, fmt, fps }) {
  const f = useCurrentFrame();
  const t = f / fps;
  const v = fmt.vertical;
  const logoP = expoOut(clamp01(t / 0.6));
  const row = (d) => expoOut(clamp01((t - d) / 0.5));
  const fadeOut = clamp01((end.dur - t) / 0.5);
  const L = end.lines;
  return (
    <AbsoluteFill style={{ background: "#07060e", opacity: fadeOut }}>
      <Img src={staticFile("media/herobg.png")} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", objectPosition: v ? "32% 50%" : "50% 50%", opacity: 0.62, filter: "blur(3px) saturate(1.1)", transform: `scale(${1.04 + 0.03 * clamp01(t / end.dur)})` }} />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 48%, rgba(7,6,14,0.72) 0%, rgba(7,6,14,0.5) 46%, rgba(7,6,14,0.88) 100%)" }} />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
        <div style={{ transform: `scale(${0.94 + 0.06 * logoP})`, opacity: logoP, marginTop: v ? -140 : -70 }}>
          <Img src={staticFile("brand/logo.png")} style={{ width: v ? 940 : 1240, height: "auto" }} />
        </div>
        <div style={{ marginTop: v ? 70 : 46, display: "flex", flexDirection: "column", alignItems: "center", gap: v ? 28 : 20 }}>
          <div style={{ opacity: row(0.6), transform: `translateY(${(1 - row(0.6)) * 16}px)`, fontFamily: DISPLAY, fontWeight: 700, fontSize: v ? 96 : 84, color: C.ink, letterSpacing: "0.04em" }}>{L[0]}</div>
          <div style={{ opacity: row(0.95), fontFamily: BODY, fontWeight: 650, fontSize: v ? 52 : 44, color: C.cyan, letterSpacing: "0.02em" }}>{L[1]}</div>
          {L[2] ? <div style={{ opacity: row(1.25), fontFamily: BODY, fontWeight: 500, fontSize: v ? 36 : 30, color: C.muted, marginTop: 10 }}>{L[2]}</div> : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

function renderText(text, accentColor) {
  // *word* is drawn in the accent colour; "\n" breaks the line
  return text.split("\n").map((line, li) => (
    <div key={li}>
      {line.split(/(\*[^*]+\*)/).map((part, i) =>
        part.startsWith("*") ? <span key={i} style={{ color: accentColor }}>{part.slice(1, -1)}</span> : <span key={i}>{part}</span>
      )}
    </div>
  ));
}

function Card({ c, fmt, t }) {
  const lt = t - c.start;
  if (lt < 0 || t > c.end) return null;
  const inP = expoOut(clamp01(lt / 0.2));
  const op = Math.min(clamp01(lt / 0.05), clamp01((c.end - t) / 0.2));
  const v = fmt.vertical;
  const size = c.size ?? (v ? 112 : 124);
  const accent = c.accent === "cyan" ? C.cyan : c.accent === "purple" ? C.purpleLight : C.orange;
  const pos = c.pos || "low";
  const place = v
    ? { top: pos === "mid" ? 700 : pos === "top" ? 250 : 980, left: 0, right: 0, height: pos === "mid" ? 400 : 440 }
    : pos === "mid" ? { top: 0, bottom: 0, left: 0, right: 0 } : pos === "lowright" ? { bottom: 70, left: "40%", right: 0, height: 360 } : pos === "top" ? { top: 60, left: 0, right: 0, height: 360 } : { bottom: 70, left: 0, right: 0, height: 360 };
  const grad = pos === "mid" ? "radial-gradient(ellipse at 50% 50%, rgba(7,6,14,0.58) 0%, rgba(7,6,14,0) 66%)" : "linear-gradient(to top, rgba(7,6,14,0.82) 0%, rgba(7,6,14,0) 100%)";
  return (
    <AbsoluteFill style={{ opacity: op, pointerEvents: "none" }}>
      {(pos === "low" || pos === "lowright") && !v ? <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 440, background: grad }} /> : null}
      {pos === "top" && !v ? <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 440, background: "linear-gradient(to bottom, rgba(7,6,14,0.82) 0%, rgba(7,6,14,0) 100%)" }} /> : null}
      {pos === "mid" || v ? <AbsoluteFill style={{ background: pos === "mid" ? grad : "linear-gradient(to top, rgba(7,6,14,0.7) 0%, rgba(7,6,14,0) 40%)" }} /> : null}
      <div style={{ position: "absolute", display: "flex", alignItems: pos === "mid" && !v ? "center" : pos === "top" && !v ? "flex-start" : "flex-end", justifyContent: "center", ...place, paddingBottom: pos === "low" && !v ? 0 : 0 }}>
        <div
          style={{
            transform: `scale(${1.2 - 0.2 * inP})`,
            fontFamily: DISPLAY,
            fontWeight: 800,
            fontSize: size,
            lineHeight: 1.02,
            color: C.ink,
            textAlign: "center",
            textTransform: "uppercase",
            letterSpacing: `${0.02 + (1 - inP) * 0.1}em`,
            textShadow: "0 4px 36px rgba(0,0,0,0.85), 0 2px 6px rgba(0,0,0,0.7)",
            maxWidth: v ? 960 : 1700,
          }}
        >
          {renderText(c.text, accent)}
        </div>
      </div>
    </AbsoluteFill>
  );
}

export function Trailer2({ format, plan }) {
  useFonts();
  const frame = useCurrentFrame();
  const fmt = FMT[format];
  const fps = plan.fps;
  const t = frame / fps;
  return (
    <AbsoluteFill style={{ background: "#07060e" }}>
      {plan.shots.map((s, i) => {
        const from = Math.round(s.start * fps);
        const next = plan.shots[i + 1];
        const frames = (next ? Math.round(next.start * fps) : Math.round(plan.total * fps)) - from;
        return (
          <Sequence key={i} from={from} durationInFrames={frames} layout="none">
            {s.type === "end" ? <EndCard end={plan.end} fmt={fmt} fps={fps} /> : s.type === "logo" ? <LogoScene shot={s} fmt={fmt} fps={fps} /> : s.type === "black" ? <BlackScene fmt={fmt} /> : <Footage shot={s} fmt={fmt} fps={fps} />}
          </Sequence>
        );
      })}
      {plan.cards.map((c, i) => <Card key={i} c={c} fmt={fmt} t={t} />)}
    </AbsoluteFill>
  );
}
