import React, { useEffect, useState } from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT_BODY, FONT_DISPLAY, brand, clamp01, expoOut, lerp } from "./theme.js";
import { buildPlan, SRC_W, SRC_H } from "./v2plan.js";
import { buildLong } from "./v2long.js";
import { Bumpered, BUMPER } from "./Bumper.jsx";

const INK = "oklch(14% 0.07 310)";
const PURPLE = "oklch(50% 0.24 310)";
const PURPLE_SOFT = "oklch(82% 0.11 310)";

export function useFonts() {
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

export const FMT = {
  "16x9": { W: 1920, H: 1080, v: false, ax: 0.5, ay: 0.44, sIdx: 0, wide: 0.86 },
  "9x16": { W: 1080, H: 1920, v: true, ax: 0.5, ay: 0.4, sIdx: 1, wide: 0.66 },
};

// ---- camera -------------------------------------------------------------------------------
function keyBase(k, f) {
  const s = k.s.length > 1 ? k.s[f.sIdx] : k.s[0];
  const ax = k.ax ? k.ax[f.sIdx] : f.ax;
  const ay = k.ay ? k.ay[f.sIdx] : f.ay;
  const fx = f.v && k.fxv != null ? k.fxv : k.fx;
  const fy = f.v && k.fyv != null ? k.fyv : k.fy;
  return { fx, fy, ls: Math.log(s), ax, ay };
}
export function camAt(keys, t, f) {
  const val = (i, tt) => {
    const k = keys[i];
    const b = keyBase(k, f);
    const drift = k.nodrift ? 0 : 0.03 * expoOut(clamp01((tt - k.t) / 5));
    b.ls += Math.log(1 + drift);
    if (i === 0) return b;
    const pv = val(i - 1, k.t);
    const p = k.d > 0 ? expoOut(clamp01((tt - k.t) / k.d)) : 1;
    return { fx: lerp(pv.fx, b.fx, p), fy: lerp(pv.fy, b.fy, p), ls: lerp(pv.ls, b.ls, p), ax: lerp(pv.ax, b.ax, p), ay: lerp(pv.ay, b.ay, p) };
  };
  let i = 0;
  keys.forEach((k, j) => {
    if (t >= k.t) i = j;
  });
  const r = val(i, t);
  return { fx: r.fx, fy: r.fy, s: Math.exp(r.ls), ax: r.ax, ay: r.ay };
}

// ---- backdrop ------------------------------------------------------------------------------
export { Ring };
export function Backdrop({ px, py }) {
  return (
    <AbsoluteFill style={{ background: "linear-gradient(160deg, oklch(96.5% 0.028 310), oklch(91% 0.06 312) 55%, oklch(88% 0.075 305))" }}>
      <div style={{ position: "absolute", width: 1500, height: 1100, left: -300 + px * 0.05, top: -420 + py * 0.05, borderRadius: "50%", background: "radial-gradient(closest-side, oklch(92% 0.08 322 / 0.9), transparent)" }} />
      <div style={{ position: "absolute", width: 1600, height: 1200, right: -500 - px * 0.08, bottom: -520 - py * 0.08, borderRadius: "50%", background: "radial-gradient(closest-side, oklch(80% 0.12 295 / 0.65), transparent)" }} />
      <div style={{ position: "absolute", width: 900, height: 900, left: "45%", top: "30%", borderRadius: "50%", background: "radial-gradient(closest-side, oklch(98% 0.03 310 / 0.7), transparent)" }} />
    </AbsoluteFill>
  );
}

// ---- rings ---------------------------------------------------------------------------------
function Ring({ r, t, s }) {
  const dt = t - r.t0;
  if (dt < 0 || t > r.t1 + 0.4) return null;
  const inP = expoOut(clamp01(dt / 0.5));
  const outP = clamp01((t - r.t1) / 0.4);
  const o = inP * (1 - outP);
  const bw = 3 / s;
  if (r.ripple) {
    const [cx, cy] = r.ripple;
    return (
      <>
        {[0, 0.28].map((d, i) => {
          const p = expoOut(clamp01((dt - d) / 0.9));
          const size = 20 + p * 90;
          return <div key={i} style={{ position: "absolute", left: cx - size / 2, top: cy - size / 2, width: size, height: size, borderRadius: "50%", border: `${bw}px solid ${PURPLE}`, opacity: (1 - p) * 0.9 }} />;
        })}
      </>
    );
  }
  const [x, y, w, h] = r.rect;
  const pad = 5 + (1 - inP) * 10;
  const pulse = 0.5 + 0.5 * Math.sin(dt * 5);
  return (
    <div
      style={{
        position: "absolute",
        left: x - pad,
        top: y - pad,
        width: w + pad * 2,
        height: h + pad * 2,
        borderRadius: 10 / 1,
        border: `${bw}px solid ${PURPLE}`,
        background: "oklch(50% 0.24 310 / 0.09)",
        boxShadow: `0 0 ${(18 + pulse * 10) / s}px oklch(55% 0.24 310 / ${0.45 * o})`,
        opacity: o,
      }}
    />
  );
}

// ---- window --------------------------------------------------------------------------------
// size: content box in window px (defaults to the ModernTex capture). chrome: decoration drawn around the
// content box (phone bezel, browser bar); radius: corner radius of the content box; bg: colour behind the media.
export function Window({ videos, s, rings, t, size, chrome = null, overlay = null, radius = 24, bg = "oklch(97% 0.01 80)", shadow = true }) {
  const R = radius;
  const w = size ? size.w : SRC_W;
  const h = size ? size.h : SRC_H;
  return (
    <div style={{ position: "relative", width: w, height: h }}>
      {shadow && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: R,
            background: bg,
            boxShadow: `0 ${60 / s * 1.0}px ${120}px oklch(30% 0.14 310 / 0.38), 0 ${18}px ${40}px oklch(30% 0.14 310 / 0.25), 0 0 0 ${1.2 / s}px oklch(30% 0.1 310 / 0.35)`,
          }}
        />
      )}
      {chrome}
      <div style={{ position: "absolute", inset: 0, borderRadius: R, overflow: "hidden", background: bg }}>{videos}</div>
      <div style={{ position: "absolute", inset: 0 }}>
        {rings.map((r, i) => (
          <Ring key={i} r={r} t={t} s={s} />
        ))}
        {typeof overlay === "function" ? overlay(s) : overlay}
      </div>
    </div>
  );
}

// ---- stage: gradient + floating framed window + camera ---------------------------------------
// t is stage-local seconds. `intro`/`outro` control the window entrance and exit.
export function Stage({ format, keys, rings, videos, intro = true, introAt = 1.4, outroAt = null, tiltOffset = 0, tiltPeriod = 0, window: win = {} }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const f = FMT[format];
  const cam = camAt(keys, t, f);
  const inP = intro ? expoOut(clamp01((t - introAt) / 1.1)) : 1;
  const outP = outroAt != null ? expoOut(clamp01((t - outroAt) / 0.9)) : 0;
  const vis = inP * (1 - outP);
  const ax = f.W * cam.ax;
  const ay = f.H * cam.ay + (1 - inP) * 320 + outP * 260;
  const zoomRel = cam.s / f.wide;
  const amp = 7 / (1 + 2.6 * Math.max(0, zoomRel - 1));
  const tt = t + tiltOffset;
  const w1 = tiltPeriod ? (Math.PI * 2) / tiltPeriod : 0.55;
  const w2 = tiltPeriod ? (Math.PI * 2) / tiltPeriod : 0.42;
  const ry = amp * Math.sin(tt * w1 + 0.6) - amp * 0.4;
  const rx = amp * 0.45 * Math.cos(tt * w2);
  const sc = cam.s * (0.93 + 0.07 * inP) * (1 - 0.06 * outP);
  const px = -cam.fx * cam.s * 0.4;
  const py = -cam.fy * cam.s * 0.4;
  return (
    <AbsoluteFill>
      <Backdrop px={px} py={py} />
      <AbsoluteFill style={{ opacity: vis, filter: outP > 0 ? `blur(${outP * 10}px)` : undefined }}>
        <div style={{ position: "absolute", left: ax, top: ay, width: 0, height: 0, perspective: 2600 }}>
          <div style={{ transformOrigin: "0 0", transformStyle: "preserve-3d", transform: `rotateX(${rx}deg) rotateY(${ry}deg) scale(${sc}) translate(${-cam.fx}px, ${-cam.fy}px)` }}>
            <Window videos={videos} s={sc} rings={rings} t={t} {...(typeof win === "function" ? win(t) : win)} />
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

// ---- lower third -----------------------------------------------------------------------------
export function LowerThird({ item, t, format }) {
  const f = FMT[format];
  if (t < item.t0 || t > item.t1 + 0.5) return null;
  const dt = t - item.t0;
  const out = expoOut(clamp01((t - item.t1) / 0.45));
  const size = f.v ? 50 : 48;
  const words = item.text.split(" ");
  const tagP = expoOut(clamp01(dt / 0.5));
  return (
    <div
      style={{
        position: "absolute",
        left: f.v ? 60 : 96,
        right: f.v ? 60 : undefined,
        bottom: f.v ? 430 : 78,
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: f.v ? 18 : 14,
        opacity: 1 - out,
        transform: `translateY(${out * 18}px)`,
      }}
    >
      <div style={{ opacity: tagP, transform: `translateY(${(1 - tagP) * 16}px)`, fontFamily: FONT_BODY, fontWeight: 700, fontSize: f.v ? 30 : 26, letterSpacing: "0.06em", textTransform: "uppercase", color: INK, background: PURPLE_SOFT, borderRadius: 999, padding: "8px 22px" }}>{item.tag}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: `0 ${size * 0.27}px`, maxWidth: f.v ? 960 : item.maxW || 1300, background: "oklch(14% 0.07 310 / 0.94)", borderRadius: size * 0.5, padding: `${size * 0.3}px ${size * 0.6}px`, boxShadow: "0 24px 60px oklch(20% 0.1 310 / 0.35)" }}>
        {words.map((w, i) => {
          const p = expoOut(clamp01((dt - 0.12 - i * 0.07) / 0.5));
          return (
            <span key={i} style={{ display: "inline-block", fontFamily: FONT_BODY, fontWeight: 650, fontSize: size, lineHeight: 1.25, color: "oklch(98% 0.01 310)", opacity: p, transform: `translateY(${(1 - p) * 26}px)`, filter: `blur(${(1 - p) * 6}px)` }}>
              {w}
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ---- title and end cards --------------------------------------------------------------------
export function TitleCard({ format, t, t0 = 0, t1 = 1.6, sub = "A native LaTeX editor for Mac.", name = "ModernTex", icon = "brand/moderntex-icon.png", iconRadius = 0.22 }) {
  const f = FMT[format];
  const out = expoOut(clamp01((t - t1) / 0.5));
  if (t > t1 + 0.6) return null;
  const rv = (d) => expoOut(clamp01((t - t0 - d) / 0.8));
  const ico = f.v ? 190 : 200;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: 1 - out, transform: `translateY(${-out * 40}px)` }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: f.v ? 30 : 26 }}>
        <img src={staticFile(icon)} style={{ width: ico, height: ico, borderRadius: ico * iconRadius, boxShadow: "0 30px 70px oklch(35% 0.16 310 / 0.35)", opacity: rv(0), transform: `translateY(${(1 - rv(0)) * 30}px) scale(${0.92 + 0.08 * rv(0)})` }} />
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: f.v ? (name.length > 10 ? 104 : 132) : name.length > 10 ? 120 : 144, letterSpacing: "-0.02em", color: INK, opacity: rv(0.12), transform: `translateY(${(1 - rv(0.12)) * 30}px)`, textAlign: "center", lineHeight: 1.05, maxWidth: f.v ? 960 : 1500 }}>{name}</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: f.v ? 44 : 42, color: C.muted, opacity: rv(0.26), transform: `translateY(${(1 - rv(0.26)) * 24}px)`, textAlign: "center", maxWidth: f.v ? 900 : 1400, lineHeight: 1.3 }}>{sub}</div>
      </div>
    </AbsoluteFill>
  );
}

export function EndCard({ format, t, t0, name = "ModernTex", icon = "brand/moderntex-icon.png", iconRadius = 0.22, pill = "$10, one purchase", url = "purplelink.llc/moderntex" }) {
  const f = FMT[format];
  if (t < t0) return null;
  const rv = (d) => expoOut(clamp01((t - t0 - d) / 0.8));
  const ico = 180;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: f.v ? 34 : 28 }}>
        <img src={staticFile(icon)} style={{ width: ico, height: ico, borderRadius: ico * iconRadius, boxShadow: "0 30px 70px oklch(35% 0.16 310 / 0.35)", opacity: rv(0), transform: `translateY(${(1 - rv(0)) * 30}px)` }} />
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: f.v ? (name.length > 10 ? 100 : 128) : name.length > 10 ? 116 : 136, letterSpacing: "-0.02em", color: INK, opacity: rv(0.1), transform: `translateY(${(1 - rv(0.1)) * 30}px)`, textAlign: "center", lineHeight: 1.05, maxWidth: f.v ? 960 : 1500 }}>{name}</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: f.v ? (pill.length > 22 ? 46 : 56) : pill.length > 22 ? 46 : 52, color: "oklch(99% 0.01 310)", background: PURPLE, borderRadius: 999, padding: "16px 48px", opacity: rv(0.22), transform: `translateY(${(1 - rv(0.22)) * 26}px)`, boxShadow: "0 20px 50px oklch(45% 0.22 310 / 0.4)", textAlign: "center", maxWidth: f.v ? 940 : 1400 }}>{pill}</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: f.v ? (url.length > 26 ? 38 : 46) : 44, color: INK, opacity: rv(0.36), transform: `translateY(${(1 - rv(0.36)) * 20}px)` }}>{url}</div>
      </div>
    </AbsoluteFill>
  );
}

// ---- compositions ----------------------------------------------------------------------------
export function PromoV2({ format, timing, bumper = null }) {
  useFonts();
  const plan = buildPlan(timing);
  if (bumper) {
    return (
      <Bumpered format={format} total={plan.total} url="purplelink.llc/moderntex" bumper={bumper}>
        <PromoV2 format={format} timing={timing} />
      </Bumpered>
    );
  }
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const videos = (
    <Sequence from={Math.round(plan.tv0 * brand.fps)} layout="none">
      <OffthreadVideo src={staticFile("media/edit.mp4")} style={{ position: "absolute", left: 0, top: 0, width: SRC_W, height: SRC_H, clipPath: "inset(2px round 22px)" }} muted />
    </Sequence>
  );
  return (
    <AbsoluteFill>
      <Stage format={format} keys={plan.keys} rings={plan.rings} videos={videos} outroAt={plan.ENDs - 0.1} />
      <TitleCard format={format} t={t} t1={1.1} />
      {plan.lower.map((l, i) => (
        <LowerThird key={i} item={l} t={t} format={format} />
      ))}
      <EndCard format={format} t={t} t0={plan.ENDs + 0.35} />
      {plan.audio.map((a) => (
        <Sequence key={a.i} from={Math.round(a.at * brand.fps)}>
          <Audio src={staticFile(timing.scenes[a.i].audio)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}

export function HeroV2({ timing }) {
  useFonts();
  const plan = buildPlan(timing);
  const h = plan.hero;
  const layer = (off) => (
    <Stage format="16x9" keys={h.keys} rings={h.rings} intro={false} tiltOffset={off} tiltPeriod={h.T} videos={<OffthreadVideo src={staticFile("media/hero-edit.mp4")} style={{ position: "absolute", left: 0, top: 0, width: SRC_W, height: SRC_H, clipPath: "inset(2px round 22px)" }} muted />} />
  );
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const a = clamp01((t - (h.T - h.XF)) / h.XF);
  return (
    <AbsoluteFill>
      {layer(0)}
      {a > 0 && (
        <Sequence from={Math.round((h.T - h.XF) * brand.fps)} layout="none">
          <AbsoluteFill style={{ opacity: a }}>{layer(h.T - h.XF)}</AbsoluteFill>
        </Sequence>
      )}
    </AbsoluteFill>
  );
}

export function PromoLong({ format, timing, bumper = null }) {
  useFonts();
  const plan = buildLong(timing);
  if (bumper) {
    return (
      <Bumpered format={format} total={plan.total} url="purplelink.llc/moderntex" bumper={bumper}>
        <PromoLong format={format} timing={timing} />
      </Bumpered>
    );
  }
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const videos = (
    <Sequence from={Math.round(plan.tv0 * brand.fps)} layout="none">
      <OffthreadVideo src={staticFile("media/long-edit.mp4")} style={{ position: "absolute", left: 0, top: 0, width: SRC_W, height: SRC_H, clipPath: "inset(2px round 22px)" }} muted />
    </Sequence>
  );
  return (
    <AbsoluteFill>
      <Stage format={format} keys={plan.keys} rings={plan.rings} videos={videos} outroAt={plan.ENDs - 0.1} />
      <TitleCard format={format} t={t} t1={1.1} />
      {plan.lower.map((l, i) => (
        <LowerThird key={i} item={l} t={t} format={format} />
      ))}
      <EndCard format={format} t={t} t0={plan.ENDs + 0.35} />
      {plan.audio.map((a) => (
        <Sequence key={a.i} from={Math.round(a.at * brand.fps)}>
          <Audio src={staticFile(timing.scenes[a.i].audio)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}
