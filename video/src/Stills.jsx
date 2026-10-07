import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, lerp, FONT_BODY } from "./theme.js";
import { Stage, TitleCard, EndCard, LowerThird, useFonts } from "./V2.jsx";
import { PRODUCTS } from "./products/index.js";
import { Bumpered, BUMPER } from "./Bumper.jsx";

const XF = 0.5; // still crossfade seconds

function scrollAt(still, t) {
  const keys = still.scroll || [];
  if (!keys.length) return 0;
  let i = -1;
  keys.forEach((k, j) => {
    if (t >= k.t) i = j;
  });
  if (i < 0) return keys[0].y0 ?? 0;
  const k = keys[i];
  const from = i === 0 ? k.y0 ?? k.y : keys[i - 1].y;
  const p = k.d > 0 ? expoOut(clamp01((t - k.t) / k.d)) : 1;
  return lerp(from, k.y, p);
}

function stillIndex(stills, t) {
  let i = 0;
  stills.forEach((s, j) => {
    if (t >= s.t0) i = j;
  });
  return i;
}

export function viewAt(plan, t) {
  const i = stillIndex(plan.stills, t);
  const cur = plan.stills[i];
  const cv = cur.view || { w: cur.w, h: cur.h };
  if (i === 0) return cv;
  const prev = plan.stills[i - 1];
  const pv = prev.view || { w: prev.w, h: prev.h };
  const p = expoOut(clamp01((t - cur.t0) / XF));
  return { w: lerp(pv.w, cv.w, p), h: lerp(pv.h, cv.h, p) };
}

function StillLayer({ stills }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const i = stillIndex(stills, t);
  return (
    <>
      {stills.map((s, j) => {
        if (j > i) return null;
        if (j < i - 1) return null;
        const o = j === 0 ? 1 : expoOut(clamp01((t - s.t0) / XF));
        const y = -scrollAt(s, t);
        if (s.video) {
          return (
            <Sequence key={j} from={Math.round(s.t0 * brand.fps)} layout="none">
              <OffthreadVideo src={staticFile(s.src)} startFrom={Math.round((s.trim || 0) * brand.fps)} playbackRate={s.rate || 1} muted style={{ position: "absolute", left: 0, top: y, width: s.w, height: s.h, opacity: o, display: "block" }} />
            </Sequence>
          );
        }
        return <Img key={j} src={staticFile(s.src)} style={{ position: "absolute", left: 0, top: y, width: s.w, height: s.h, opacity: o, display: "block" }} />;
      })}
    </>
  );
}

// ---- frame chrome ----------------------------------------------------------------------------
const SHADOW = `0 60px 120px oklch(30% 0.14 310 / 0.38), 0 18px 40px oklch(30% 0.14 310 / 0.25)`;

function PhoneBezel() {
  const B = 24;
  return (
    <>
      <div style={{ position: "absolute", inset: -B, borderRadius: 150 + B, background: "oklch(15% 0.012 300)", boxShadow: SHADOW }} />
      <div style={{ position: "absolute", inset: -B, borderRadius: 150 + B, boxShadow: "inset 0 0 0 3px oklch(38% 0.01 300), inset 0 0 0 6px oklch(22% 0.01 300)" }} />
    </>
  );
}

function BrowserBar({ url, w }) {
  const H = 64;
  return (
    <>
      <div style={{ position: "absolute", left: 0, right: 0, top: -H, bottom: 0, borderRadius: 24, background: "oklch(95.5% 0.012 310)", boxShadow: SHADOW + ", 0 0 0 1.2px oklch(30% 0.1 310 / 0.3)" }} />
      <div style={{ position: "absolute", left: 22, top: -H / 2 - 7, display: "flex", gap: 9 }}>
        {["oklch(68% 0.19 25)", "oklch(82% 0.17 85)", "oklch(72% 0.2 145)"].map((c, i) => (
          <div key={i} style={{ width: 14, height: 14, borderRadius: 7, background: c }} />
        ))}
      </div>
      <div style={{ position: "absolute", left: w * 0.2, right: w * 0.2, top: -H + 13, height: H - 26, borderRadius: 19, background: "oklch(99% 0.003 310)", boxShadow: "0 0 0 1px oklch(85% 0.03 310)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT_BODY, fontSize: 18, fontWeight: 500, color: "oklch(40% 0.04 300)", letterSpacing: "0.005em" }}>
        {url}
      </div>
    </>
  );
}

// ---- cursor -----------------------------------------------------------------------------------
function cursorPos(c, t) {
  const pts = c.pts;
  if (t <= pts[0][0]) return pts[0];
  for (let i = 1; i < pts.length; i++) {
    const [ta, xa, ya] = pts[i - 1];
    const [tb, xb, yb] = pts[i];
    if (t <= tb) {
      const p = expoOut(clamp01((t - ta) / Math.max(0.01, tb - ta)));
      return [t, lerp(xa, xb, p), lerp(ya, yb, p)];
    }
  }
  return pts[pts.length - 1];
}

function Cursors({ cursors, t, s }) {
  return (
    <>
      {cursors.map((c, i) => {
        if (t < c.t0 || t > c.t1 + 0.4) return null;
        const o = expoOut(clamp01((t - c.t0) / 0.35)) * (1 - clamp01((t - c.t1) / 0.4));
        const [, x, y] = cursorPos(c, t);
        const size = 34 / s;
        return (
          <svg key={i} viewBox="0 0 24 24" width={size} height={size} style={{ position: "absolute", left: x - 2 / s, top: y - 2 / s, opacity: o, filter: "drop-shadow(0 2px 3px oklch(20% 0.05 310 / 0.5))" }}>
            <path d="M5 3 L19 12.5 L12.6 13.6 L16.2 20.6 L13.7 21.8 L10.2 14.9 L5 19.4 Z" fill="oklch(99% 0.005 310)" stroke="oklch(18% 0.05 310)" strokeWidth="1.4" strokeLinejoin="round" />
          </svg>
        );
      })}
    </>
  );
}

function windowFor(plan, t) {
  const view = viewAt(plan, t);
  const base = { size: view };
  const overlay = plan.cursors && plan.cursors.length ? (s) => <Cursors cursors={plan.cursors} t={t} s={s} /> : null;
  if (plan.frame === "phone") return { ...base, chrome: <PhoneBezel />, radius: 150, bg: "oklch(8% 0.01 300)", shadow: false, overlay };
  if (plan.frame === "browser") return { ...base, chrome: <BrowserBar url={plan.url} w={view.w} />, radius: "0 0 24px 24px", bg: "oklch(99% 0.003 310)", shadow: false, overlay };
  return { ...base, overlay };
}

// ---- compositions ---------------------------------------------------------------------------------
export function StillPromo({ id, format, timing, bumper = BUMPER }) {
  useFonts();
  const plan = PRODUCTS[id].build(timing);
  return (
    <Bumpered format={format} total={plan.total} url={plan.end.url} bumper={bumper}>
      <StillCut plan={plan} format={format} timing={timing} />
    </Bumpered>
  );
}

function StillCut({ plan, format, timing }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  return (
    <AbsoluteFill>
      <Stage format={format} keys={plan.keys} rings={plan.rings} videos={<StillLayer stills={plan.stills} />} window={(tt) => windowFor(plan, tt)} introAt={plan.introAt ?? 1.5} outroAt={plan.ENDs - 0.1} />
      <TitleCard format={format} t={t} t1={plan.titleT1 ?? 1.3} {...plan.title} />
      {plan.lower.map((l, i) => (
        <LowerThird key={i} item={l} t={t} format={format} />
      ))}
      <EndCard format={format} t={t} t0={plan.ENDs + 0.35} name={plan.title.name} icon={plan.title.icon} iconRadius={plan.title.iconRadius} {...plan.end} />
      {plan.audio.map((a) => (
        <Sequence key={a.i} from={Math.round(a.at * brand.fps)}>
          <Audio src={staticFile(timing.scenes[a.i].audio)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}

// Silent seamless loop: two copies of the same stage, the second offset by T - XF and faded in over the last XF seconds.
export function StillHero({ id, timing }) {
  useFonts();
  const plan = PRODUCTS[id].build(timing);
  const h = plan.hero;
  const hp = { ...plan, stills: h.stills, cursors: [] };
  const layer = (off) => <Stage format="16x9" keys={h.keys} rings={h.rings} intro={false} tiltOffset={off} tiltPeriod={h.T} videos={<StillLayer stills={h.stills} />} window={(tt) => windowFor(hp, tt)} />;
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
