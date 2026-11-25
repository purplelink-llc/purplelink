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
const VCLIP_TOP = 0; // ends at 1310, the same line as the square window of the landscape-clip vertical shots
const VCLIP_H = 1825; // the portrait captures are 1024x1730 (macOS caps the window there), drawn at 1080 wide = 1825 tall, the same scale on both axes

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

// v6: debris that flies out of the logo slam (deterministic, so every render is identical)
const DEBRIS = Array.from({ length: 46 }, (_, i) => ({ a: rnd(i + 1) * Math.PI * 2, v: 380 + rnd(i + 50) * 900, s: 4 + rnd(i + 99) * 14, r: rnd(i + 7) * 360, hot: rnd(i + 3) > 0.55 }));

function LogoMark({ w, shimmer }) {
  // the logo plus a light sweep clipped to the logo's own alpha
  const url = staticFile("brand/logo.png");
  return (
    <div style={{ position: "relative", width: w }}>
      <Img src={url} style={{ width: w, height: "auto", display: "block" }} />
      {shimmer >= 0 && shimmer <= 1 ? (
        <div style={{ position: "absolute", inset: 0, WebkitMaskImage: `url(${url})`, WebkitMaskSize: "100% 100%", maskImage: `url(${url})`, maskSize: "100% 100%",
          background: `linear-gradient(105deg, rgba(255,255,255,0) ${shimmer * 140 - 30}%, rgba(255,250,235,0.85) ${shimmer * 140 - 18}%, rgba(255,255,255,0) ${shimmer * 140 - 6}%)`, mixBlendMode: "screen" }} />
      ) : null}
    </div>
  );
}

function LogoSlam({ at, dur, vertical, t }) {
  const lt = t - at;
  if (lt < 0 || lt > dur) return null;
  const p = expoOut(clamp01(lt / 0.22));
  const o = Math.min(clamp01(lt / 0.03), clamp01((dur - lt) / 0.3));
  const w = vertical ? 960 : 1300;
  const split = Math.pow(clamp01(1 - lt / 0.16), 2) * 14; // short colour split on impact
  const ring = expoOut(clamp01(lt / 0.7));
  const settle = 1 + 0.015 * Math.sin(clamp01(lt / dur) * Math.PI); // a slow breath while held
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: o }}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(7,6,14,0.35) 0%, rgba(7,6,14,0.72) 70%)" }} />
      <div style={{ position: "absolute", left: "50%", top: "50%", width: 40 + ring * (vertical ? 1500 : 2300), height: 40 + ring * (vertical ? 1500 : 2300), transform: "translate(-50%,-50%)", borderRadius: "50%",
        border: `${Math.max(1, 26 * (1 - ring))}px solid rgba(255,186,120,${0.55 * (1 - ring)})`, boxShadow: `0 0 80px rgba(255,106,31,${0.4 * (1 - ring)})` }} />
      {DEBRIS.map((d, i) => {
        const q = clamp01(lt / 1.4);
        const dist = d.v * expoOut(q);
        const fall = 260 * q * q;
        const op = clamp01(1 - q) * (lt > 0.02 ? 1 : 0);
        return <div key={i} style={{ position: "absolute", left: "50%", top: "50%", width: d.s, height: d.s * 0.7, borderRadius: d.hot ? "50%" : 2, opacity: op,
          background: d.hot ? "#ffb36b" : "#3a3550", boxShadow: d.hot ? "0 0 12px #ff6a1f" : "none",
          transform: `translate(${Math.cos(d.a) * dist}px, ${Math.sin(d.a) * dist * 0.62 + fall}px) rotate(${d.r + q * 400}deg)` }} />;
      })}
      <div style={{ position: "relative", transform: `scale(${(1.34 - 0.34 * p) * settle})`, filter: "drop-shadow(0 0 46px rgba(43,208,222,0.38)) drop-shadow(0 10px 30px rgba(0,0,0,0.8))" }}>
        {split > 0.5 ? <div style={{ position: "absolute", left: -split, top: 0, opacity: 0.55, mixBlendMode: "screen", filter: "sepia(1) hue-rotate(140deg) saturate(4)" }}><Img src={staticFile("brand/logo.png")} style={{ width: w, height: "auto" }} /></div> : null}
        {split > 0.5 ? <div style={{ position: "absolute", left: split, top: 0, opacity: 0.55, mixBlendMode: "screen", filter: "sepia(1) hue-rotate(-20deg) saturate(5)" }}><Img src={staticFile("brand/logo.png")} style={{ width: w, height: "auto" }} /></div> : null}
        <LogoMark w={w} shimmer={(lt - 0.35) / 0.9} />
      </div>
      <AbsoluteFill style={{ background: "#ffffff", opacity: Math.pow(clamp01(1 - lt / 0.22), 2) * 0.75, mixBlendMode: "screen" }} />
    </AbsoluteFill>
  );
}

function Grade({ fmt }) {
  // film grade over everything but the text: animated grain, cool shadows and warm highlights, letterbox-free
  const f = useCurrentFrame();
  const seed = Math.floor(f / 2);
  const W = fmt.W, H = fmt.H;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(43,208,222,0.05) 0%, rgba(0,0,0,0) 40%, rgba(255,106,31,0.05) 100%)", mixBlendMode: "soft-light" }} />
      <svg width={W} height={H} style={{ position: "absolute", inset: 0, opacity: 0.075, mixBlendMode: "overlay" }}>
        <filter id={`g${seed}`}><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={seed % 97} stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter>
        <rect width={W} height={H} filter={`url(#g${seed})`} />
      </svg>
    </AbsoluteFill>
  );
}

function Glint({ g, t }) {
  // a cut accent: "flash" is a 3-frame warm flash, "whip" a sideways light streak (used on drops and section changes, never as a kill effect)
  const dur = g.dur ?? 0.22;
  if (t > dur) return null;
  const q = clamp01(t / dur);
  if (g.kind === "whip") {
    return (
      <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: 0, bottom: 0, width: "60%", left: `${-60 + q * 160}%`, background: "linear-gradient(90deg, rgba(199,168,255,0) 0%, rgba(199,168,255,0.45) 45%, rgba(255,255,255,0.7) 50%, rgba(43,208,222,0.4) 55%, rgba(43,208,222,0) 100%)", mixBlendMode: "screen", filter: "blur(18px)" }} />
      </AbsoluteFill>
    );
  }
  return <AbsoluteFill style={{ background: g.color || "#fff2df", opacity: (g.amp ?? 0.55) * Math.pow(1 - q, 2), mixBlendMode: "screen", pointerEvents: "none" }} />;
}

function Title({ ti, fmt, t }) {
  // the opening genre line: letters open out from tight tracking, cyan rules grow from the centre
  const lt = t - (ti.at ?? 0);
  if (lt < 0 || lt > ti.dur) return null;
  const p = expoOut(clamp01(lt / 0.5));
  const o = Math.min(clamp01(lt / 0.12), clamp01((ti.dur - lt) / 0.25));
  const v = fmt.vertical;
  const top = v ? 1580 : ti.y ?? 150;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top, display: "flex", flexDirection: "column", alignItems: "center", opacity: o }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: -50, height: ti.sub ? 250 : 200, background: "linear-gradient(180deg, rgba(7,6,14,0) 0%, rgba(7,6,14,0.72) 28%, rgba(7,6,14,0.72) 72%, rgba(7,6,14,0) 100%)" }} />
      <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 28 }}>
        <div style={{ height: 3, width: 160 * p, background: `linear-gradient(90deg, rgba(43,208,222,0), ${C.cyan})` }} />
        <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: v ? 78 : 92, color: C.ink, textTransform: "uppercase", letterSpacing: `${0.02 + 0.16 * p}em`, filter: `blur(${(1 - p) * 6}px)`,
          textShadow: "0 3px 0 rgba(7,6,14,0.9), 0 6px 40px rgba(0,0,0,0.95)", WebkitTextStroke: "6px rgba(7,6,14,0.9)", paintOrder: "stroke fill" }}>{ti.text}</div>
        <div style={{ height: 3, width: 160 * p, background: `linear-gradient(90deg, ${C.cyan}, rgba(43,208,222,0))` }} />
      </div>
      {ti.sub ? <div style={{ position: "relative", marginTop: 10, fontFamily: BODY, fontWeight: 650, fontSize: v ? 40 : 36, color: C.purpleLight, letterSpacing: "0.3em", textTransform: "uppercase", opacity: expoOut(clamp01((lt - 0.3) / 0.4)), textShadow: "0 2px 12px rgba(0,0,0,0.95)" }}>{ti.sub}</div> : null}
    </div>
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
  const filter = "contrast(1.09) saturate(1.16) brightness(1.02)";
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
      {shot.glint ? <Glint g={shot.glint} t={t} /> : null}
      {shot.title ? <Title ti={shot.title} fmt={fmt} t={t} /> : null}
      {shot.logo ? <LogoSlam at={shot.logo.at} dur={shot.logo.dur} vertical={fmt.vertical} t={t} /> : null}
    </AbsoluteFill>
  );
}

const EMBERS = Array.from({ length: 34 }, (_, i) => ({ x: rnd(i + 200), v: 0.12 + rnd(i + 300) * 0.22, o: rnd(i + 400), s: 3 + rnd(i + 500) * 5, w: 1 + rnd(i + 600) * 2 }));

function EndCard({ end, fmt, fps }) {
  const f = useCurrentFrame();
  const t = f / fps;
  const v = fmt.vertical;
  const logoP = expoOut(clamp01(t / 0.7));
  const row = (d) => expoOut(clamp01((t - d) / 0.5));
  const fadeOut = clamp01((end.dur - t) / 0.45); // ends on black, not on a cut
  const L = end.lines;
  const W = fmt.W, H = fmt.H;
  return (
    <AbsoluteFill style={{ background: "#07060e" }}>
     <AbsoluteFill style={{ opacity: fadeOut }}>
      <Img src={staticFile("media/herobg.png")} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", objectPosition: v ? "32% 50%" : "50% 50%", opacity: 0.66, filter: `blur(${4 - 2 * logoP}px) saturate(1.15)`, transform: `scale(${1.1 - 0.05 * expoOut(clamp01(t / end.dur))}) translateX(${-12 * clamp01(t / end.dur)}px)` }} />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 46%, rgba(7,6,14,0.7) 0%, rgba(7,6,14,0.45) 42%, rgba(7,6,14,0.9) 100%)" }} />
      {EMBERS.map((e, i) => {
        const life = (t * e.v + e.o) % 1;
        return <div key={i} style={{ position: "absolute", left: e.x * W + Math.sin((t + e.o * 9) * e.w) * 22, top: H * (1.04 - life * 1.1), width: e.s, height: e.s, borderRadius: "50%", background: "#ffc08a", boxShadow: "0 0 10px #ff6a1f", opacity: Math.sin(life * Math.PI) * 0.8 * logoP }} />;
      })}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
        <div style={{ transform: `scale(${0.92 + 0.08 * logoP})`, opacity: logoP, marginTop: v ? -140 : -70, filter: `blur(${(1 - logoP) * 10}px) drop-shadow(0 0 36px rgba(122,63,216,0.45))` }}>
          <LogoMark w={v ? 940 : 1240} shimmer={(t - 0.6) / 1.1} />
        </div>
        <div style={{ marginTop: v ? 26 : 18, height: 2, width: (v ? 620 : 760) * row(0.35), background: `linear-gradient(90deg, rgba(199,168,255,0), ${C.purpleLight}, rgba(199,168,255,0))` }} />
        <div style={{ marginTop: v ? 70 : 46, display: "flex", flexDirection: "column", alignItems: "center", gap: v ? 28 : 20 }}>
          <div style={{ opacity: row(0.5), transform: `translateY(${(1 - row(0.5)) * 16}px)`, fontFamily: DISPLAY, fontWeight: 700, fontSize: v ? 96 : 84, color: C.ink, letterSpacing: "0.04em" }}>{L[0]}</div>
          {end.wishlist ? <div style={{ opacity: row(0.8), fontFamily: BODY, fontWeight: 750, fontSize: v ? 56 : 50, color: "#fff", background: C.purple, borderRadius: 999, padding: v ? "16px 48px" : "12px 44px" }}>{end.wishlist}</div> : null}
          <div style={{ opacity: row(1.0), fontFamily: BODY, fontWeight: 650, fontSize: v ? 52 : 44, color: C.cyan, letterSpacing: "0.02em" }}>{L[1]}</div>
          {L[2] ? <div style={{ opacity: row(1.2), fontFamily: BODY, fontWeight: 500, fontSize: v ? 38 : 32, color: C.muted, marginTop: 8 }}>{L[2]}</div> : null}
        </div>
      </AbsoluteFill>
     </AbsoluteFill>
    </AbsoluteFill>
  );
}

function renderText(text, accent, lt, instant) {
  // v6: each word drops in on its own beat (40 ms apart) from a slight blur and a larger size
  let n = 0;
  return text.split("\n").map((line, li) => (
    <div key={li}>
      {line.split(/(\*[^*]+\*)/).filter(Boolean).flatMap((part, i) => {
        const hot = part.startsWith("*");
        const words = (hot ? part.slice(1, -1) : part).split(/(\s+)/);
        return words.map((w, j) => {
          if (/^\s+$/.test(w) || !w) return <span key={`${i}-${j}`}>{w}</span>;
          const q = instant ? 1 : expoOut(clamp01((lt - 0.04 * n++) / 0.2));
          return <span key={`${i}-${j}`} style={{ display: "inline-block", color: hot ? accent : undefined, opacity: clamp01(q * 3), transform: `translateY(${(1 - q) * -22}px) scale(${1.25 - 0.25 * q})`, filter: q < 0.98 ? `blur(${(1 - q) * 7}px)` : "none" }}>{w}</span>;
        });
      })}
    </div>
  ));
}

function Card({ c, fmt, t }) {
  const lt = t - c.start;
  if (lt < 0 || t > c.end) return null;
  const inP = c.instant ? 1 : expoOut(clamp01(lt / 0.18));
  const op = c.instant ? clamp01((c.end - t) / 0.15) : Math.min(clamp01(lt / 0.05), clamp01((c.end - t) / 0.15));
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
  } else if (c.pos === "floor") {
    place = { left: 0, width: 1920, bottom: 28, height: 130, alignItems: "flex-end", justifyContent: "center" };
    plate = null;
  } else if (c.pos === "left") {
    place = { left: 24, width: 620, top: 130, height: 240, alignItems: "flex-start", justifyContent: "flex-start" };
    plate = null;
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
            position: "relative", transform: `scale(${1.06 - 0.06 * inP})`, fontFamily: DISPLAY, fontWeight: 800, fontSize: size, lineHeight: 1.02, color: C.ink, textAlign: "center", textTransform: "uppercase",
            letterSpacing: `${0.02 + (1 - inP) * 0.08}em`, textShadow: "0 3px 0 rgba(7,6,14,0.9), 0 4px 30px rgba(0,0,0,0.9), 0 0 6px rgba(0,0,0,0.8)", maxWidth: v ? 1000 : 1700,
            WebkitTextStroke: v ? "5px rgba(7,6,14,0.92)" : (c.strong ? "10px rgba(7,6,14,0.98)" : "7px rgba(7,6,14,0.92)"), paintOrder: "stroke fill",
            background: c.strong ? "rgba(7,6,14,0.82)" : "rgba(7,6,14,0.52)", padding: v ? "8px 30px" : "10px 40px", borderRadius: 26,
          }}
        >
          {renderText(c.text, accent, lt, c.instant)}
          <div style={{ position: "absolute", left: "50%", bottom: v ? -6 : -8, height: v ? 6 : 7, borderRadius: 4, width: `${(c.instant ? 1 : expoOut(clamp01((lt - 0.08) / 0.35))) * 64}%`, transform: "translateX(-50%)", background: `linear-gradient(90deg, rgba(0,0,0,0), ${accent}, rgba(0,0,0,0))`, boxShadow: `0 0 18px ${accent}` }} />
        </div>
      </div>
    </AbsoluteFill>
  );
}

export function Trailer6({ format, plan }) {
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
      <Grade fmt={fmt} />
      {plan.cards.map((c, i) => <Card key={i} c={c} fmt={fmt} t={t} />)}
    </AbsoluteFill>
  );
}
