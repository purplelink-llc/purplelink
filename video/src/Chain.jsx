import React from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, camOut, FONT_BODY, FONT_DISPLAY, FORMATS, lerp } from "./theme.js";
import { Backdrop, FMT, useFonts } from "./V2.jsx";
import { Bumpered, BUMPER } from "./Bumper.jsx";
import { Captions } from "./Captions.jsx";
import { build } from "./chain/plan.js";

// "Chain of the day": two players, the teammates that connect them, one link at a time. Same look as the product
// videos: brand backdrop, Fraunces names, expo-out motion with no bounce, narration with word-synced captions, and the
// Purplelink bumpers. Everything is drawn here; there are no photographs.
const INK = "oklch(14% 0.07 310)";
const MUTED = "oklch(46% 0.04 300)";
const PURPLE = "oklch(50% 0.24 310)";
const CARD = "oklch(99% 0.008 310)";
const LINE = "oklch(84% 0.07 310)";
const GREEN = "oklch(72% 0.15 118)";   // Lockerlink's colour

const LAY = {
  "9x16": { v: true, cw: 900, ch: 184, gap: 150, fx: 540, fy: 790, name: 62, sub: 34, chip: 36, hook: 112, big: 260 },
  "16x9": { v: false, cw: 600, ch: 220, gap: 190, fx: 960, fy: 470, name: 56, sub: 30, chip: 32, hook: 108, big: 280 },
};

const hueOf = (s) => { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
const initials = (n) => { const w = n.replace(/[.,]/g, "").split(" ").filter(Boolean); return (w[0][0] + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase(); };
const words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];

function Monogram({ name, size }) {
  const h = hueOf(name);
  return (
    <div style={{ width: size, height: size, borderRadius: size / 2, flex: "none", background: `linear-gradient(145deg, oklch(94% 0.05 ${h}), oklch(86% 0.09 ${h}))`, color: `oklch(32% 0.14 ${h})`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: size * 0.4, letterSpacing: "-0.02em" }}>
      {initials(name)}
    </div>
  );
}

function Card({ p, L, tag, appear, focus, ring }) {
  const o = appear;
  const s = lerp(0.9, 1, appear) * lerp(0.96, 1, focus);
  const nameSize = Math.min(L.name, (L.cw - L.ch - 80) / (p.name.length * 0.52));
  return (
    <div style={{ position: "absolute", left: -L.cw / 2, top: -L.ch / 2, width: L.cw, height: L.ch, opacity: o * lerp(0.62, 1, focus), transform: `scale(${s})`, transformOrigin: "50% 50%" }}>
      {ring > 0 && <div style={{ position: "absolute", inset: -ring * 40, borderRadius: 46 + ring * 40, border: `4px solid oklch(60% 0.22 310 / ${(1 - ring) * 0.7})` }} />}
      <div style={{ width: "100%", height: "100%", borderRadius: 40, background: CARD, display: "flex", alignItems: "center", gap: 30, padding: `0 ${L.ch * 0.22}px`, boxSizing: "border-box", border: `${focus > 0.5 ? 3 : 2}px solid ${focus > 0.5 ? "oklch(62% 0.2 310)" : LINE}`, boxShadow: focus > 0.5 ? "0 38px 80px oklch(40% 0.16 310 / 0.30), 0 10px 24px oklch(40% 0.16 310 / 0.18)" : "0 18px 40px oklch(40% 0.12 310 / 0.14)" }}>
        <Monogram name={p.name} size={L.ch * 0.56} />
        <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
          {tag && <div style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: L.sub * 0.7, letterSpacing: "0.14em", color: PURPLE }}>{tag}</div>}
          <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: nameSize, letterSpacing: "-0.02em", color: INK, lineHeight: 1.05, whiteSpace: "nowrap" }}>{p.name}</div>
          <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: L.sub, color: MUTED, whiteSpace: "nowrap" }}>{[p.pos, p.span].filter(Boolean).join("  ·  ")}</div>
        </div>
      </div>
    </div>
  );
}

function Link({ hop, L, draw }) {
  const h = hueOf(hop.team);
  const len = L.gap;
  return (
    <div style={{ position: "absolute", left: 0, top: 0 }}>
      <div style={{ position: "absolute", [L.v ? "left" : "top"]: -3, [L.v ? "top" : "left"]: 0, [L.v ? "width" : "height"]: 6, [L.v ? "height" : "width"]: len * draw, borderRadius: 3, background: `linear-gradient(${L.v ? 180 : 90}deg, oklch(70% 0.14 310), oklch(60% 0.2 310))` }} />
      <div style={{ position: "absolute", left: L.v ? 0 : len / 2, top: L.v ? len / 2 : 0, transform: `translate(-50%, -50%) scale(${lerp(0.85, 1, draw)})`, opacity: clamp01((draw - 0.25) / 0.5), padding: `${L.chip * 0.3}px ${L.chip * 0.8}px`, borderRadius: 999, background: `oklch(93% 0.06 ${h})`, border: `2.5px solid oklch(70% 0.13 ${h})`, color: `oklch(30% 0.13 ${h})`, fontFamily: FONT_BODY, fontWeight: 700, fontSize: L.chip, whiteSpace: "nowrap", boxShadow: "0 12px 26px oklch(40% 0.12 310 / 0.16)" }}>
        {hop.team}  <span style={{ fontWeight: 500, opacity: 0.8 }}>{hop.seasons}</span>
      </div>
    </div>
  );
}

function Hook({ chain, L, f, t, plan }) {
  const out = expoOut(clamp01((t - (plan.hop0 - 0.35)) / 0.5));
  const rv = (d, len = 0.7) => expoOut(clamp01((t - d) / len));
  const rvAt = (at) => expoOut(clamp01((t - at) / 0.7));
  const a = chain.players[0], b = chain.players[chain.players.length - 1];
  const small = f.v ? 44 : 42;
  const nm = (n) => ({ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: Math.min(L.hook, (f.v ? 940 : 1500) / (n.length * 0.5)), letterSpacing: "-0.025em", color: INK, lineHeight: 1.04, whiteSpace: "nowrap" });
  const label = chain.kind === "daily" ? "Yesterday's Lockerlink" : chain.kind === "of-the-day" ? "Chain of the day" : "How are they connected?";
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: 1 - out, transform: `translateY(${-out * 50}px)`, filter: out > 0 ? `blur(${out * 10}px)` : undefined }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: f.v ? 26 : 22, transform: `translateY(${f.v ? -90 : -10}px)` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18, opacity: rv(0.05), transform: `translateY(${(1 - rv(0.05)) * 24}px)` }}>
          <Img src={staticFile("brand/lockerlink.png")} style={{ width: 84, height: 84, borderRadius: 20 }} />
          <div style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: small * 0.82, letterSpacing: "0.16em", color: PURPLE, textTransform: "uppercase" }}>{label}  ·  {chain.league}</div>
        </div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: small, color: MUTED, opacity: rv(0.2), transform: `translateY(${(1 - rv(0.2)) * 24}px)` }}>{chain.kind === "daily" ? "Link" : "How is"}</div>
        <div style={{ ...nm(a.name), opacity: rvAt(plan.hook.a), transform: `translateY(${(1 - rvAt(plan.hook.a)) * 36}px)` }}>{a.name}</div>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: small, color: MUTED, opacity: rvAt(plan.hook.conn), transform: `translateY(${(1 - rvAt(plan.hook.conn)) * 24}px)` }}>{chain.kind === "daily" ? "to" : "connected to"}</div>
        <div style={{ ...nm(b.name), color: PURPLE, opacity: rvAt(plan.hook.b), transform: `translateY(${(1 - rvAt(plan.hook.b)) * 36}px)` }}>{b.name}{chain.kind === "daily" ? "" : "?"}</div>
        <div style={{ marginTop: 14, fontFamily: FONT_BODY, fontWeight: 650, fontSize: small, color: INK, background: "oklch(93% 0.06 310)", borderRadius: 999, padding: "14px 40px", opacity: rvAt(plan.hook.pill), transform: `translateY(${(1 - rvAt(plan.hook.pill)) * 20}px)` }}>{chain.kind === "daily" ? "The shortest chain" : "Through teammates"}, in {words[chain.players.length - 1]} links</div>
      </div>
    </AbsoluteFill>
  );
}

function End({ chain, L, f, t, plan }) {
  const rv = (d, len = 0.8) => expoOut(clamp01((t - plan.endAt - d) / len));
  const a = chain.players[0], b = chain.players[chain.players.length - 1];
  if (t < plan.endAt - 0.05) return null;
  const P = chain.players, N = P.length;
  const listTop = f.v ? 480 : 270, listH = f.v ? 590 : 430;
  const row = Math.min(f.v ? 104 : 96, listH / N);
  const nameSize = Math.min(f.v ? 56 : 52, row * 0.62);
  return (
    <AbsoluteFill style={{ alignItems: "center", pointerEvents: "none" }}>
      <div style={{ position: "absolute", top: f.v ? 170 : 40, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, opacity: rv(0.15), transform: `translateY(${(1 - rv(0.15)) * 30}px) scale(${lerp(0.94, 1, rv(0.15))})` }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 22 }}>
          <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: f.v ? 230 : 200, lineHeight: 0.95, letterSpacing: "-0.04em", color: PURPLE }}>{plan.links}</div>
          <div style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: f.v ? 54 : 50, letterSpacing: "0.12em", color: INK, textTransform: "uppercase" }}>links</div>
        </div>
      </div>
      <div style={{ position: "absolute", top: listTop, width: f.v ? 900 : 860, height: listH, display: "flex", flexDirection: "column", justifyContent: "center", gap: 0 }}>
        {P.map((p, i) => {
          const k = rv(0.45 + i * 0.16, 0.6);
          const hop = i < N - 1 ? chain.hops[i] : null;
          return (
            <div key={i} style={{ height: row, display: "flex", flexDirection: "column", justifyContent: "center", opacity: k, transform: `translateY(${(1 - k) * 24}px)` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
                <Monogram name={p.name} size={row * 0.6} />
                <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: nameSize, letterSpacing: "-0.02em", color: INK, whiteSpace: "nowrap" }}>{p.name}</div>
                {hop && <div style={{ marginLeft: "auto", fontFamily: FONT_BODY, fontWeight: 700, fontSize: nameSize * 0.5, color: `oklch(32% 0.13 ${hueOf(hop.team)})`, background: `oklch(93% 0.06 ${hueOf(hop.team)})`, borderRadius: 999, padding: "6px 22px", whiteSpace: "nowrap" }}>{hop.team}</div>}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", bottom: f.v ? 575 : 200, display: "flex", alignItems: "center", gap: 26, padding: "22px 44px 22px 26px", borderRadius: 40, background: CARD, border: `2.5px solid oklch(62% 0.2 310)`, boxShadow: "0 30px 70px oklch(40% 0.16 310 / 0.28)", opacity: rv(1.2), transform: `translateY(${(1 - rv(1.2)) * 50}px)` }}>
        <Img src={staticFile("brand/lockerlink.png")} style={{ width: f.v ? 112 : 100, height: f.v ? 112 : 100, borderRadius: 26 }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: f.v ? 60 : 54, color: INK, letterSpacing: "-0.02em", lineHeight: 1.05 }}>Lockerlink</div>
          <div style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: f.v ? 34 : 30, color: MUTED }}>Link two players. New puzzle daily.</div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

function Cut({ chain, format, timing }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const f = FMT[format], L = LAY[format], fmt = FORMATS[format];
  const plan = build(chain, timing);
  const P = chain.players, N = P.length, pitch = (L.v ? L.ch : L.cw) + L.gap;
  const axisHalf = (L.v ? L.ch : L.cw) / 2;

  // camera: which card is in focus (continuous index); moves to card k as hop scene k begins
  let cam = 0;
  plan.S.filter((s) => s.kind === "hop" && t >= s.n + 0.05).forEach((s) => { cam = Math.max(cam, s.hop + camOut(clamp01((t - (s.n + 0.05)) / 0.85))); });
  cam = Math.min(cam, N - 1);
  // finale: pull back so the whole chain shows
  const endP = expoOut(clamp01((t - (plan.endAt - 0.1)) / 0.55));
  const total = (N - 1) * pitch + (L.v ? L.ch : L.cw);
  const areaLen = L.v ? 880 : 1500;
  const scale = 1, camPos = cam;
  const origin = { x: L.fx, y: L.fy };
  const chainOpacity = expoOut(clamp01((t - (plan.hop0 - 0.5)) / 0.55)) * (1 - endP);
  const cards = P.map((p, i) => {
    const hop = plan.S[i]; // scene i (i>=1) reveals player i
    const appear = i === 0 ? chainOpacity : expoOut(clamp01((t - (plan.S[i].n + 0.38)) / 0.6));
    const dist = Math.abs(i - cam);
    const focus = clamp01(1 - dist);
    const ringT = i === 0 ? plan.hop0 : plan.S[i].n + 0.38;
    const ring = clamp01((t - ringT) / 0.9);
    const celebrate = 0;
    return { p, i, appear, focus, ring: ring < 1 && ring > 0 ? ring : 0, celebrate };
  });
  const place = (i) => (L.v ? { x: 0, y: (i - camPos) * pitch } : { x: (i - camPos) * pitch, y: 0 });
  return (
    <AbsoluteFill>
      <Backdrop px={0} py={0} />
      <Hook chain={chain} L={L} f={f} t={t} plan={plan} />
      <div style={{ position: "absolute", left: origin.x, top: origin.y, width: 0, height: 0, transform: `scale(${scale})`, transformOrigin: "0 0", opacity: chainOpacity * (1 - 0) }}>
        {chain.hops.map((h, k) => {
          const draw = expoOut(clamp01((t - (plan.S[k + 1].n + 0.0)) / 0.55));
          if (draw <= 0) return null;
          const a = place(k);
          const off = axisHalf;
          return (
            <div key={`l${k}`} style={{ position: "absolute", left: a.x + (L.v ? 0 : off), top: a.y + (L.v ? off : 0) }}>
              <Link hop={h} L={L} draw={draw} />
            </div>
          );
        })}
        {cards.map(({ p, i, appear, focus, ring, celebrate }) => {
          if (appear <= 0) return null;
          const q = place(i);
          return (
            <div key={`c${i}`} style={{ position: "absolute", left: q.x, top: q.y }}>
              <Card p={p} L={L} tag={i === 0 ? "START" : i === N - 1 ? "FINISH" : null} appear={appear} focus={focus} ring={ring} />
            </div>
          );
        })}
      </div>
      <End chain={chain} L={L} f={f} t={t} plan={plan} />
      {plan.S.map((s) => (
        <Sequence key={s.i} from={Math.round(s.n * brand.fps)}>
          <Audio src={staticFile(timing.scenes[s.i].audio)} />
          {s.kind === "hop" && <Audio src={staticFile("brand/clink.wav")} volume={0.32} />}
        </Sequence>
      ))}
      {plan.S.map((s) => (
        <Captions key={`cap${s.i}`} words={t >= s.n && t < s.e + 0.2 ? timing.scenes[s.i].words : null} t={t - s.n} fmt={fmt} />
      ))}
    </AbsoluteFill>
  );
}

export function ChainDay({ chain, format, timing, bumper = BUMPER }) {
  useFonts();
  const plan = build(chain, timing);
  return (
    <Bumpered format={format} total={plan.total} url="purplelink.llc/games/lockerlink" bumper={bumper}>
      <Cut chain={chain} format={format} timing={timing} />
    </Bumpered>
  );
}
