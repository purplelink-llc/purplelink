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
const FMT = { "16x9": { W: 1920, H: 1080, vertical: false }, "9x16": { W: 1080, H: 1920, vertical: true } };
// 9:16 layout: a square window of the game (kept inside the platform-safe band) and the card zone under it
const VWIN = { top: 230, size: 1080 };
const VCARD = { top: 1560, h: 260 };
const VCARD_TOP = 1480;
const VCLIP_TOP = 95; // ends at 1310, the same line as the square window of the landscape-clip vertical shots
const VCLIP_H = 1215; // the full-frame vertical captures are 1920x2160 (8:9), so at 1080 wide they are 1215 tall; never stretch them

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

function Video({ shot, span, fps }) {
  const src = staticFile(`media/${shot.clip}.mp4`);
  const startFrom = Math.max(0, Math.round(span.src * fps));
  const el = <OffthreadVideo src={src} muted startFrom={startFrom} playbackRate={span.rate || 1} style={{ width: "100%", height: "100%", objectFit: "fill" }} />;
  return span.rate === 0 ? <Freeze frame={0}>{el}</Freeze> : el;
}

function Spans({ shot, fps }) {
  const spans = shot.spans;
  return spans.map((sp, k) => {
    const from = Math.round(sp.start * fps);
    const to = k + 1 < spans.length ? Math.round(spans[k + 1].start * fps) : Math.round(shot.dur * fps);
    return (
      <Sequence key={k} from={from} durationInFrames={Math.max(1, to - from)} layout="none">
        <AbsoluteFill><Video shot={shot} span={sp} fps={fps} /></AbsoluteFill>
      </Sequence>
    );
  });
}

function LogoSlam({ at, dur, vertical, t }) {
  const lt = t - at;
  if (lt < 0 || lt > dur) return null;
  const p = expoOut(clamp01(lt / 0.2));
  const o = Math.min(clamp01(lt / 0.04), clamp01((dur - lt) / 0.25));
  const w = vertical ? 960 : 1300;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: o }}>
      <AbsoluteFill style={{ background: "rgba(7,6,14,0.55)" }} />
      <div style={{ transform: `scale(${1.28 - 0.28 * p})`, filter: "drop-shadow(0 0 40px rgba(43,208,222,0.4))" }}>
        <Img src={staticFile("brand/logo.png")} style={{ width: w, height: "auto" }} />
      </div>
      <AbsoluteFill style={{ background: "#ffffff", opacity: Math.pow(clamp01(1 - lt / 0.25), 2) * 0.7, mixBlendMode: "screen" }} />
    </AbsoluteFill>
  );
}

function Inset({ ins, fmt, fps, t }) {
  // a picture-in-picture of another clip (the run map), cropped to its useful part, sliding in over live board footage
  const lt = t - ins.at;
  if (lt < 0 || lt > ins.dur) return null;
  const p = expoOut(clamp01(lt / 0.2));
  const o = Math.min(clamp01(lt / 0.05), clamp01((ins.dur - lt) / 0.15));
  const v = fmt.vertical;
  const w = v ? 900 : ins.w ?? 760;
  const k = w / ins.crop.w;
  const h = ins.crop.h * k;
  const left = v ? (1080 - w) / 2 : ins.x ?? 60;
  const top = v ? VWIN.top + 20 : ins.y ?? 160;
  const src = staticFile(`media/${ins.clip}.mp4`);
  return (
    <div style={{ position: "absolute", left, top, width: w, height: h, overflow: "hidden", borderRadius: 18, border: `3px solid ${C.purpleLight}`, boxShadow: "0 12px 50px rgba(0,0,0,0.7)", opacity: o, transform: `translateY(${(1 - p) * -30}px) scale(${0.96 + 0.04 * p})`, background: "#0f1320" }}>
      <div style={{ position: "absolute", width: 1920 * k, height: 1080 * k, left: -ins.crop.x * k, top: -ins.crop.y * k }}>
        <OffthreadVideo src={src} muted startFrom={Math.round((ins.src + lt) * fps)} style={{ width: "100%", height: "100%", objectFit: "fill" }} />
      </div>
    </div>
  );
}

function Footage({ shot, fmt, fps }) {
  const f = useCurrentFrame();
  const t = f / fps;
  const dur = shot.dur;
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
    pulse += (s.zoom ?? 0.03) * k * 1.4;
  }
  const scale = crop.s * pn * (1 + pulse);
  const filter = "contrast(1.06) saturate(1.1)";
  const fadeIn = shot.fadeIn ? clamp01(f / (shot.fadeIn * fps)) : 1;
  const fadeOut = shot.fadeOut ? clamp01((dur - t) / shot.fadeOut) : 1;
  let body;
  if (fmt.vertical && shot.vclip) {
    const vsrc = staticFile(`media/${shot.vclip}.mp4`);
    const sp0 = shot.spans[0];
    body = (
      <>
        <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: 1920, background: "linear-gradient(to bottom, #120f22, #07060e)" }} />
        <div style={{ position: "absolute", left: 0, top: VCLIP_TOP, width: 1080, height: VCLIP_H, overflow: "hidden", transform: `translate(${dx}px, ${dy}px) scale(${pn * (1 + pulse)})`, transformOrigin: "50% 40%", filter }}>
          <OffthreadVideo src={vsrc} muted startFrom={Math.max(0, Math.round(sp0.src * fps))} playbackRate={sp0.rate || 1} style={{ position: "absolute", width: 1080, height: VCLIP_H, left: 0, top: 0, objectFit: "fill" }} />
        </div>
        
      </>
    );
  } else if (fmt.vertical) {
    const v = shot.v || { cx: 640, cy: 540, s: 1 };
    const k = v.s ?? 1;
    const W = 1920 * k, H = 1080 * k;
    const box = { position: "absolute", width: W, height: H, left: -(v.cx * k - VWIN.size / 2), top: -(v.cy * k - VWIN.size / 2) };
    body = (
      <>
        <div style={{ position: "absolute", left: -260, top: -80, width: 3 * 1080 * 16 / 9 / 1.9, height: 1920 + 160, overflow: "hidden", filter: "blur(34px) brightness(0.38) saturate(1.1)" }}>
          <div style={{ position: "absolute", width: 1920 * 1.9, height: 1080 * 1.9, left: -(v.cx * 1.9 - 640), top: -(v.cy * 1.9 - 960) }}><Spans shot={shot} fps={fps} /></div>
        </div>
        <div style={{ position: "absolute", left: 0, top: VWIN.top, width: VWIN.size, height: VWIN.size, overflow: "hidden", boxShadow: "0 0 60px rgba(0,0,0,0.7)", transform: `translate(${dx}px, ${dy}px) scale(${pn * (1 + pulse)})`, filter }}>
          <div style={box}><Spans shot={shot} fps={fps} /></div>
        </div>
      </>
    );
  } else {
    body = (
      <AbsoluteFill style={{ transform: `translate(${dx}px, ${dy}px) scale(${scale})`, transformOrigin: `${crop.x * 100}% ${crop.y * 100}%`, filter }}>
        <div style={{ position: "absolute", inset: 0 }}><Spans shot={shot} fps={fps} /></div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ background: "#07060e", overflow: "hidden", opacity: Math.min(fadeIn, fadeOut) }}>
      {body}
      {shot.dim ? <AbsoluteFill style={{ background: `rgba(7,6,14,${shot.dim})` }} /> : null}
      {!fmt.vertical && shot.vig ? <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 62%, rgba(4,3,10,${shot.vig}) 100%)` }} /> : null}
      {shot.flash.map((fl, k) => {
        const lt = t - fl.at;
        if (lt < 0 || lt > fl.dur) return null;
        const o = (fl.amp ?? 0.6) * Math.pow(1 - lt / fl.dur, 2);
        return <AbsoluteFill key={k} style={{ background: fl.color || "#fff4e0", opacity: o, mixBlendMode: "screen" }} />;
      })}
      {(shot.insets || []).map((ins, k) => <Inset key={k} ins={ins} fmt={fmt} fps={fps} t={t} />)}
      {shot.logo ? <LogoSlam at={shot.logo.at} dur={shot.logo.dur} vertical={fmt.vertical} t={t} /> : null}
    </AbsoluteFill>
  );
}

function EndCard({ end, fmt, fps }) {
  const f = useCurrentFrame();
  const t = f / fps;
  const v = fmt.vertical;
  const logoP = expoOut(clamp01(t / 0.6));
  const row = (d) => expoOut(clamp01((t - d) / 0.5));
  const fadeOut = clamp01((end.dur - t) / 0.4);
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
          <div style={{ opacity: row(0.5), transform: `translateY(${(1 - row(0.5)) * 16}px)`, fontFamily: DISPLAY, fontWeight: 700, fontSize: v ? 96 : 84, color: C.ink, letterSpacing: "0.04em" }}>{L[0]}</div>
          {end.wishlist ? <div style={{ opacity: row(0.8), fontFamily: BODY, fontWeight: 750, fontSize: v ? 56 : 50, color: "#fff", background: C.purple, borderRadius: 999, padding: v ? "16px 48px" : "12px 44px" }}>{end.wishlist}</div> : null}
          <div style={{ opacity: row(1.0), fontFamily: BODY, fontWeight: 650, fontSize: v ? 52 : 44, color: C.cyan, letterSpacing: "0.02em" }}>{L[1]}</div>
          {L[2] ? <div style={{ opacity: row(1.2), fontFamily: BODY, fontWeight: 500, fontSize: v ? 38 : 32, color: C.muted, marginTop: 8 }}>{L[2]}</div> : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

function renderText(text, accent) {
  return text.split("\n").map((line, li) => (
    <div key={li}>{line.split(/(\*[^*]+\*)/).map((part, i) => (part.startsWith("*") ? <span key={i} style={{ color: accent }}>{part.slice(1, -1)}</span> : <span key={i}>{part}</span>))}</div>
  ));
}

function Card({ c, fmt, t }) {
  const lt = t - c.start;
  if (lt < 0 || t > c.end) return null;
  const inP = expoOut(clamp01(lt / 0.18));
  const op = Math.min(clamp01(lt / 0.05), clamp01((c.end - t) / 0.15));
  const v = fmt.vertical;
  const size = v ? (c.vsize ?? 84) : (c.size ?? 104);
  const accent = c.accent === "cyan" ? C.cyan : c.accent === "purple" ? C.purpleLight : C.orange;
  // 16:9: "board" centres over the board area (the HUD's right panel is x > 1430), "top"/"mid" as named. 9:16: always the card zone under the game window.
  let place, plate;
  if (v) {
    place = { left: 0, right: 0, top: VCARD.top, height: VCARD.h, alignItems: "center", justifyContent: "center" };
    plate = null;
  } else if (c.pos === "mid") {
    place = { left: 0, right: 0, top: 0, bottom: 0, alignItems: "center", justifyContent: "center" };
    plate = "radial-gradient(ellipse at 50% 50%, rgba(7,6,14,0.62) 0%, rgba(7,6,14,0) 66%)";
  } else if (c.pos === "top") {
    place = { left: 0, width: 1920, top: 150, height: 240, alignItems: "flex-start", justifyContent: "center" };
    plate = null;
  } else {
    place = { left: 0, width: 1920, bottom: 130, height: 260, alignItems: "flex-end", justifyContent: "center" };
    plate = null;
  }
  return (
    <AbsoluteFill style={{ opacity: op, pointerEvents: "none" }}>
      {plate ? <AbsoluteFill style={{ background: plate }} /> : null}
      <div style={{ position: "absolute", display: "flex", ...place }}>
        <div
          style={{
            transform: `scale(${1.18 - 0.18 * inP})`, fontFamily: DISPLAY, fontWeight: 800, fontSize: size, lineHeight: 1.02, color: C.ink, textAlign: "center", textTransform: "uppercase",
            letterSpacing: `${0.02 + (1 - inP) * 0.08}em`, textShadow: "0 3px 0 rgba(7,6,14,0.9), 0 4px 30px rgba(0,0,0,0.9), 0 0 6px rgba(0,0,0,0.8)", maxWidth: v ? 1000 : 1700,
            WebkitTextStroke: v ? "5px rgba(7,6,14,0.92)" : "7px rgba(7,6,14,0.92)", paintOrder: "stroke fill",
            background: "rgba(7,6,14,0.52)", padding: v ? "8px 30px" : "10px 40px", borderRadius: 26,
          }}
        >
          {renderText(c.text, accent)}
        </div>
      </div>
    </AbsoluteFill>
  );
}

export function Trailer5({ format, plan }) {
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
            {s.type === "end" ? <EndCard end={plan.end} fmt={fmt} fps={fps} /> : <Footage shot={s} fmt={fmt} fps={fps} />}
          </Sequence>
        );
      })}
      {plan.cards.map((c, i) => <Card key={i} c={c} fmt={fmt} t={t} />)}
    </AbsoluteFill>
  );
}
