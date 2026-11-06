import React, { useEffect, useState } from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, continueRender, delayRender, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, camOut, FONT_BODY } from "../theme.js";
import { Bumpered, BUMPER } from "../Bumper.jsx";
import { SHOTS, CAPTIONS, XF, TOTAL } from "./plan.js";

// GlobePin App Store preview (886x1920) and 16:9 film. Real Simulator footage of the app in a frameless
// rounded screen, one caption per idea. Storyboard: storyboards/globepin-preview.md. Clips, icon and music
// are staged by globepin/build.mjs into .cache/globepin-preview/public.

const ORANGE = "rgb(255, 107, 43)"; // Color.Theme.accentDeep in the app
const NIGHT = "#05070d";
const SRC_W = 1320, SRC_H = 2868;

export const LAYOUT = {
  preview: { W: 886, H: 1920, screenH: 1440, screenX: null, screenY: 410, capX: 70, capY: 150, capW: 746, capSize: 76, subSize: 34, align: "center" },
  "16x9": { W: 1920, H: 1080, screenH: 940, screenX: 1180, screenY: 70, capX: 170, capY: null, capW: 860, capSize: 96, subSize: 42, align: "left" },
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

// Fixed star field so every render is identical.
const STARS = Array.from({ length: 90 }, (_, i) => {
  const r = (n) => { const x = Math.sin(i * 127.1 + n * 311.7) * 43758.5453; return x - Math.floor(x); };
  return { x: r(1), y: r(2), s: 1 + r(3) * 2.2, a: 0.25 + r(4) * 0.55, tw: r(5) * 6.28 };
});

function Sky({ L, frame }) {
  const t = frame / brand.fps;
  const gx = 50 + 8 * Math.sin(t * 0.21), gy = L.H > L.W ? 62 : 55;
  return (
    <AbsoluteFill style={{ background: NIGHT }}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse 70% 55% at ${gx}% ${gy}%, rgba(255,107,43,0.20), transparent 70%), radial-gradient(ellipse 60% 45% at ${100 - gx}% 18%, rgba(70,110,255,0.16), transparent 70%)` }} />
      {STARS.map((s, i) => (
        <div key={i} style={{ position: "absolute", left: `${s.x * 100}%`, top: `${s.y * 100}%`, width: s.s, height: s.s, borderRadius: "50%", background: "white", opacity: s.a * (0.75 + 0.25 * Math.sin(t * 1.3 + s.tw)) }} />
      ))}
    </AbsoluteFill>
  );
}

// The app screen. Shots cross-fade; each eases in from 0.97 and may push in slowly (shot.zoom).
function Screen({ L, frame }) {
  const h = L.screenH, w = (h * SRC_W) / SRC_H;
  const x = L.screenX ?? (L.W - w) / 2;
  const radius = w * 0.125;
  const intro = expoOut(clamp01(frame / 22));
  return (
    <div style={{ position: "absolute", left: x, top: L.screenY, width: w, height: h, transform: `translateY(${(1 - intro) * 60}px)`, opacity: intro }}>
      <div style={{ position: "absolute", inset: -40, borderRadius: radius + 40, background: "radial-gradient(closest-side, rgba(255,107,43,0.28), transparent)", filter: "blur(30px)" }} />
      <div style={{ position: "absolute", inset: 0, borderRadius: radius, overflow: "hidden", background: "black", boxShadow: "0 40px 90px rgba(0,0,0,0.65), 0 0 0 1.5px rgba(255,255,255,0.10)" }}>
        {SHOTS.map((s) => {
          const local = frame - s.from;
          if (local < 0 || local >= s.dur + XF) return null;
          const fadeIn = s.from === 0 ? 1 : clamp01(local / XF);
          const settle = 0.97 + 0.03 * camOut(clamp01(local / 18));
          const push = s.zoom ? 1 + (s.zoom - 1) * camOut(clamp01(local / s.dur)) : 1;
          return (
            <Sequence key={s.id} from={s.from} durationInFrames={s.dur + XF} layout="none">
              <AbsoluteFill style={{ opacity: fadeIn, transform: `scale(${(s.from === 0 ? 1 : settle) * push})`, transformOrigin: s.origin || "50% 40%" }}>
                <OffthreadVideo src={staticFile(s.src)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              </AbsoluteFill>
            </Sequence>
          );
        })}
      </div>
    </div>
  );
}

// One caption per idea: words rise in one after another, the whole line lifts out before the next.
function Caption({ L, frame, caption }) {
  const c = caption || CAPTIONS.find((k) => frame >= k.from && frame < k.to);
  if (!c) return null;
  const local = frame - c.from, left = c.to - frame;
  const out = clamp01(1 - left / 9);
  const words = c.text.split(" ");
  const leftAligned = L.align === "left";
  const box = {
    position: "absolute", left: L.capX, width: L.capW, textAlign: L.align,
    ...(L.capY != null ? { top: L.capY } : { top: 0, bottom: 0, display: "flex", flexDirection: "column", justifyContent: "center" }),
    opacity: 1 - out, transform: `translateY(${-out * 24}px)`,
  };
  return (
    <div style={box}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: leftAligned ? "flex-start" : "center", gap: L.capSize * 0.3 }}>
        {c.icon && (
          <Img src={staticFile("icon.png")} style={{ width: L.capSize * 1.15, height: L.capSize * 1.15, borderRadius: L.capSize * 0.26, opacity: expoOut(clamp01(local / 16)), transform: `scale(${0.85 + 0.15 * expoOut(clamp01(local / 20))})`, boxShadow: "0 16px 40px rgba(255,107,43,0.35)" }} />
        )}
        <div style={{ fontFamily: FONT_BODY, fontWeight: 800, fontSize: L.capSize, lineHeight: 1.06, letterSpacing: "-0.02em", color: "white", textWrap: "balance" }}>
          {words.map((w, i) => {
            const p = expoOut(clamp01((local - 2 - i * 3) / 14));
            const hot = c.hot && c.hot.includes(w.replace(/[.,]/g, ""));
            return (
              <span key={i} style={{ display: "inline-block", marginRight: i < words.length - 1 ? "0.24em" : 0, opacity: p, transform: `translateY(${(1 - p) * 0.45}em)`, color: hot ? ORANGE : "white" }}>{w}</span>
            );
          })}
        </div>
      </div>
      {c.sub && (
        <div style={{ marginTop: 18, fontFamily: FONT_BODY, fontWeight: 500, fontSize: L.subSize, lineHeight: 1.3, color: "rgba(255,255,255,0.72)", opacity: expoOut(clamp01((local - 10 - words.length * 3) / 16)) }}>{c.sub}</div>
      )}
    </div>
  );
}

function Film({ L }) {
  useFonts();
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Sky L={L} frame={frame} />
      <Screen L={L} frame={frame} />
      <Caption L={L} frame={frame} />
      <Audio src={staticFile("music.wav")} />
      {/* fade to night at the very end so the loop on the App Store page doesn't jump */}
      <AbsoluteFill style={{ background: NIGHT, opacity: clamp01((frame - (TOTAL - 12)) / 12) }} />
    </AbsoluteFill>
  );
}

export function GlobePinPreview() {
  return <Film L={LAYOUT.preview} />;
}

// App Store screenshot (1320x2868 for 6.9" iPhone, 2064x2752 for 13" iPad): one real screenshot in the same
// frameless screen, caption fully revealed. `img` is a path inside the staged public dir.
const SHOT_LAYOUT = {
  iphone: { W: 1320, H: 2868, screenH: 2140, screenX: null, screenY: 650, capX: 80, capY: 170, capW: 1160, capSize: 104, subSize: 46, align: "center", srcW: 1320, srcH: 2868 },
  ipad: { W: 2064, H: 2752, screenH: 2050, screenX: null, screenY: 620, capX: 160, capY: 160, capW: 1744, capSize: 112, subSize: 50, align: "center", srcW: 2064, srcH: 2752 },
};

export function GlobePinShot({ device = "iphone", img, text, sub, hot }) {
  useFonts();
  const L = SHOT_LAYOUT[device];
  const h = L.screenH, w = (h * L.srcW) / L.srcH;
  const radius = device === "iphone" ? w * 0.125 : w * 0.035;
  return (
    <AbsoluteFill>
      <Sky L={L} frame={0} />
      <div style={{ position: "absolute", left: (L.W - w) / 2, top: L.screenY, width: w, height: h }}>
        <div style={{ position: "absolute", inset: -60, borderRadius: radius + 60, background: "radial-gradient(closest-side, rgba(255,107,43,0.28), transparent)", filter: "blur(40px)" }} />
        <Img src={staticFile(img)} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", borderRadius: radius, boxShadow: "0 50px 110px rgba(0,0,0,0.65), 0 0 0 2px rgba(255,255,255,0.10)" }} />
      </div>
      <Caption L={L} frame={1000} caption={{ from: 0, to: 1e9, text, sub, hot }} />
    </AbsoluteFill>
  );
}

export function GlobePinFilm({ bumper = BUMPER }) {
  return (
    <Bumpered format="16x9" total={TOTAL / brand.fps} url="purplelink.llc/globepin" bumper={bumper}>
      <Film L={LAYOUT["16x9"]} />
    </Bumpered>
  );
}
