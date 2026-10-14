import React, { useEffect, useState } from "react";
import { AbsoluteFill, Easing, Img, OffthreadVideo, Sequence, continueRender, delayRender, interpolate, staticFile, useCurrentFrame } from "remotion";
import brand from "../../brand-rubblefront.json";

const C = brand.colors;
const DISPLAY = `"${brand.fonts.display.family}", Georgia, serif`;
const BODY = `"${brand.fonts.body.family}", system-ui, sans-serif`;
const clamp01 = (v) => Math.min(1, Math.max(0, v));
const expoOut = Easing.bezier(0.16, 1, 0.3, 1);
const inOut = Easing.bezier(0.45, 0, 0.25, 1);

// 16:9 and 9:16 geometry. Vertical keeps the top 210 px and bottom 410 px clear of Shorts, Reels and TikTok interface.
const FMT = {
  "16x9": { W: 1920, H: 1080, vertical: false, cap: { bottom: 26, size: 46, maxW: 1560 } },
  "9x16": { W: 1080, H: 1920, vertical: true, cap: { top: 1250, size: 56, maxW: 940 }, win: { y: 400, h: 800 } },
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

function zoomAt(z, frame, dur) {
  if (!z) return { s: 1, x: 0.5, y: 0.5 };
  const p = inOut(clamp01(frame / Math.max(1, dur)));
  return { s: z.from + (z.to - z.from) * p, x: z.x ?? 0.5, y: z.y ?? 0.5 };
}

function Media({ shot, fmt, fps }) {
  const frame = useCurrentFrame();
  const dur = Math.round(shot.dur * fps);
  const src = staticFile(`media/${shot.name}.${shot.kind === "still" ? "png" : "mp4"}`);
  const startFrom = Math.max(0, Math.round(shot.in * fps));
  const z = zoomAt(shot.zoom, frame, dur);
  const mediaEl = (style) =>
    shot.kind === "still" ? (
      <Img src={src} style={style} />
    ) : (
      <OffthreadVideo src={src} muted startFrom={startFrom} playbackRate={shot.speed || 1} style={style} />
    );
  if (!fmt.vertical) {
    return (
      <AbsoluteFill style={{ overflow: "hidden", background: C.bg }}>
        {mediaEl({ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${z.s})`, transformOrigin: `${z.x * 100}% ${z.y * 100}%` })}
      </AbsoluteFill>
    );
  }
  // vertical: blurred, darkened copy as the backdrop, a 1080 x 840 window on the action in front (cover-fit, so nothing is stretched)
  const v = shot.v || { z: 1.4, x: 0.4, y: 0.5 };
  const zz = v.z ?? 1.4;
  const vz = zoomAt(shot.zoom && shot.v === null ? shot.zoom : null, frame, dur);
  const winH = fmt.win.h;
  const baseW = fmt.W; // fit width: the video is 1080 wide, 607.5 tall at z = 1
  const baseH = (fmt.W * 9) / 16;
  const scale = Math.max(zz * vz.s, winH / baseH);
  const vw = baseW * scale;
  const vh = baseH * scale;
  const left = -(vw - fmt.W) * clamp01(v.x ?? 0.5);
  const top = -(vh - winH) * clamp01(v.y ?? 0.5);
  return (
    <AbsoluteFill style={{ background: C.bg, overflow: "hidden" }}>
      {mediaEl({ position: "absolute", left: -300, top: -100, width: fmt.W + 600, height: fmt.H + 200, objectFit: "cover", filter: "blur(36px) brightness(0.38) saturate(1.1)" })}
      <div style={{ position: "absolute", left: 0, top: fmt.win.y, width: fmt.W, height: winH, overflow: "hidden", boxShadow: "0 0 60px rgba(0,0,0,0.6)" }}>
        {mediaEl({ position: "absolute", left, top, width: vw, height: vh, objectFit: "cover" })}
      </div>
    </AbsoluteFill>
  );
}

function Shot({ shot, fmt, fps, last }) {
  const frame = useCurrentFrame();
  const fadeF = Math.round((shot.fade || 0) * fps);
  const op = fadeF > 0 ? interpolate(frame, [0, fadeF], [0, 1], { extrapolateRight: "clamp" }) : 1;
  return (
    <AbsoluteFill style={{ opacity: op }}>
      <Media shot={shot} fmt={fmt} fps={fps} />
    </AbsoluteFill>
  );
}

function Captions({ plan, fmt, t }) {
  const cur = plan.captions.find((c) => t >= c.start && t <= c.end);
  if (!cur) return null;
  const inP = clamp01((t - cur.start) / 0.12);
  const outP = clamp01((cur.end - t) / 0.12);
  const size = fmt.cap.size;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, ...(fmt.vertical ? { top: fmt.cap.top } : { bottom: fmt.cap.bottom }), display: "flex", justifyContent: "center", pointerEvents: "none", opacity: Math.min(inP, outP) }}>
      <div
        style={{
          maxWidth: fmt.cap.maxW,
          padding: `${size * 0.3}px ${size * 0.62}px`,
          borderRadius: size * 0.6,
          background: "rgba(12, 10, 24, 0.86)",
          color: C.ink,
          fontFamily: BODY,
          fontWeight: 650,
          fontSize: size,
          lineHeight: 1.22,
          textAlign: "center",
        }}
      >
        {cur.card
          ? cur.words.map((w) => w.display).join(" ")
          : cur.words.map((w, i) => (
              <span key={i} style={{ color: t >= w.start - 0.02 && t <= w.end + 0.02 ? C.purpleLight : C.ink }}>
                {w.display}
                {i < cur.words.length - 1 ? " " : ""}
              </span>
            ))}
      </div>
    </div>
  );
}

function Logo({ width, style }) {
  return <Img src={staticFile("brand/logo.png")} style={{ width, height: "auto", ...style }} />;
}

function EndCard({ end, fmt, fps, total }) {
  const frame = useCurrentFrame(); // local to the end sequence
  const t = frame / fps;
  const v = fmt.vertical;
  const logoP = expoOut(clamp01(t / 0.6));
  const row = (delay) => expoOut(clamp01((t - delay) / 0.5));
  const fadeOut = clamp01((end.dur - t) / 0.45);
  const lines = end.lines;
  const logoW = v ? 900 : 1180;
  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeOut }}>
      <Img src={staticFile("media/endbg.png")} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", opacity: 0.55, filter: "blur(2px)" }} />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 45%, rgba(15,19,32,0.35) 0%, rgba(15,19,32,0.88) 78%)" }} />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", paddingTop: v ? 40 : 0 }}>
        <div style={{ transform: `scale(${0.92 + 0.08 * logoP})`, opacity: logoP, marginTop: v ? -180 : -90 }}>
          <Logo width={logoW} />
        </div>
        <div style={{ marginTop: v ? 70 : 54, display: "flex", flexDirection: "column", alignItems: "center", gap: v ? 26 : 22 }}>
          <div style={{ opacity: row(0.7), transform: `translateY(${(1 - row(0.7)) * 16}px)`, background: C.purple, color: "#fff", fontFamily: BODY, fontWeight: 750, fontSize: v ? 60 : 56, padding: v ? "18px 52px" : "16px 52px", borderRadius: 999 }}>
            {lines[0]}
          </div>
          <div style={{ opacity: row(1.0), fontFamily: DISPLAY, fontWeight: 650, fontSize: v ? 78 : 70, color: C.ink }}>{lines[1]}</div>
          <div style={{ opacity: row(1.3), fontFamily: BODY, fontWeight: 600, fontSize: v ? 44 : 40, color: C.purpleLight, letterSpacing: 0.5 }}>{lines[2]}</div>
          {lines[3] ? <div style={{ opacity: row(1.6), fontFamily: BODY, fontWeight: 500, fontSize: v ? 30 : 28, color: C.muted, marginTop: 12 }}>{lines[3]}</div> : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

export function Trailer({ format, plan }) {
  useFonts();
  const frame = useCurrentFrame();
  const fmt = FMT[format];
  const fps = plan.fps;
  const t = frame / fps;
  const last = plan.shots.length - 1;
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      {plan.shots.map((s, i) => {
        const from = Math.round(s.start * fps);
        const frames = Math.round(s.dur * fps);
        if (s.kind === "end") {
          return (
            <Sequence key={i} from={from} durationInFrames={frames} layout="none">
              <EndCard end={plan.end} fmt={fmt} fps={fps} total={plan.total} />
            </Sequence>
          );
        }
        return (
          <Sequence key={i} from={from} durationInFrames={frames} layout="none">
            <Shot shot={s} fmt={fmt} fps={fps} last={i === last} />
          </Sequence>
        );
      })}
      {fmt.vertical && !plan.end ? null : null}
      {fmt.vertical && plan.showLogo !== false && (!plan.end || t < plan.end.start) ? (
        <div style={{ position: "absolute", top: 236, left: 0, right: 0, display: "flex", justifyContent: "center", opacity: 0.96 }}>
          <Logo width={520} />
        </div>
      ) : null}
      {!plan.end || t < plan.end.start ? <Captions plan={plan} fmt={fmt} t={t} /> : null}
    </AbsoluteFill>
  );
}
