import React from "react";
import { Img, OffthreadVideo, staticFile } from "remotion";
import { C, FONT_BODY, FONT_DISPLAY, brand, clamp01, lerp, reveal } from "./theme.js";

// Headline that sets in word by word. `\n` in text starts a new line.
export function Words({ text, frame, start = 0, size, color, weight = 500, stagger = 5, lineHeight = 1.06, align = "left", font = FONT_DISPLAY, dur = 24 }) {
  const lines = text.split("\n");
  let n = 0;
  return (
    <div style={{ fontFamily: font, fontSize: size, fontWeight: weight, color, lineHeight, textAlign: align, letterSpacing: "-0.01em" }}>
      {lines.map((line, li) => (
        <div key={li}>
          {line.split(" ").map((w, wi) => {
            const p = reveal(frame, start + n++ * stagger, dur);
            return (
              <span key={wi} style={{ display: "inline-block", opacity: p, transform: `translateY(${(1 - p) * 0.28}em)`, marginRight: "0.26em" }}>
                {w}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// The logo is purple on transparent, so it sits on a light tile to stay legible on purple and dark frames.
export function LogoTile({ size }) {
  return (
    <div style={{ width: size, height: size, borderRadius: size * 0.26, background: C.purpleXLight, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
      <Img src={staticFile("brand/logo.png")} style={{ width: size * 0.78, height: size * 0.78 }} />
    </div>
  );
}

export function Mark({ frame, color, x, y, size = 34 }) {
  const p = reveal(frame, 4, 24);
  return (
    <div style={{ position: "absolute", left: x, top: y, display: "flex", alignItems: "center", gap: size * 0.4, opacity: p, fontFamily: FONT_BODY, fontWeight: 600, fontSize: size, color }}>
      <LogoTile size={size * 1.7} />
      <span>{brand.wordmark}</span>
    </div>
  );
}

// Displays image or video media at (Mw x Mh) px inside a camera transform.
export function MediaNode({ media, trim, frame }) {
  const src = staticFile(media.path);
  if (media.kind === "video") {
    return <OffthreadVideo src={src} muted startFrom={trim || 0} style={{ width: "100%", height: "100%" }} />;
  }
  return <Img src={src} style={{ width: "100%", height: "100%", display: "block" }} />;
}

// A window-shaped frame (fw x fh) with a camera that pans and zooms over the media.
// zoom: {from,to,x,y,x0?,y0?}. Media coordinates are normalized 0..1. `p` is camera progress 0..1.
export function CameraFrame({ fw, fh, media, trim, frame, zoom, p, fit, highlights, radius = 22 }) {
  const z = { from: 1, to: 1, x: 0.5, y: 0.5, ...(zoom || {}) };
  const base = fit === "cover" ? Math.max(fw / media.w, fh / media.h) : Math.min(fw / media.w, fh / media.h);
  const Mw = media.w * base;
  const Mh = media.h * base;
  const s = lerp(z.from, z.to, p);
  const c0x = z.x0 ?? 0.5;
  const c0y = z.y0 ?? 0.5;
  const clampC = (c, half) => (half >= 0.5 ? 0.5 : Math.min(1 - half, Math.max(half, c)));
  const cx = clampC(lerp(c0x, z.x, p), fw / (2 * Mw * s));
  const cy = clampC(lerp(c0y, z.y, p), fh / (2 * Mh * s));
  const tx = fw / 2 - cx * Mw * s;
  const ty = fh / 2 - cy * Mh * s;
  return (
    <div style={{ width: fw, height: fh, borderRadius: radius, overflow: "hidden", position: "relative", background: C.panel, boxShadow: `0 40px 90px -30px oklch(30% 0.16 310 / 0.45), 0 0 0 1.5px oklch(30% 0.1 310 / 0.18)` }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: Mw, height: Mh, transformOrigin: "0 0", transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
        <MediaNode media={media} trim={trim} frame={frame} />
        {(highlights || []).map((h, i) => (
          <Ring key={i} h={h} s={s} />
        ))}
      </div>
    </div>
  );
}

// Spotlight ring: dims everything outside the rectangle slightly and outlines it.
// h: {x,y,w,h,p} where p is 0..1 visibility. Border is divided by the camera scale so it stays constant on screen.
function Ring({ h, s }) {
  const p = clamp01(h.p);
  if (p <= 0) return null;
  const grow = (1 - p) * 0.012;
  return (
    <div
      style={{
        position: "absolute",
        left: `${(h.x - grow) * 100}%`,
        top: `${(h.y - grow) * 100}%`,
        width: `${(h.w + grow * 2) * 100}%`,
        height: `${(h.h + grow * 2) * 100}%`,
        border: `${5 / s}px solid oklch(70% 0.2 310 / ${p})`,
        borderRadius: 14 / s,
        boxShadow: `0 0 0 6000px oklch(14% 0.07 310 / ${0.22 * p})`,
        boxSizing: "border-box",
      }}
    />
  );
}

export function Row({ title, detail, p, fmt }) {
  return (
    <div style={{ opacity: p, transform: `translateY(${(1 - p) * 26}px)`, display: "flex", gap: 28, alignItems: "stretch" }}>
      <div style={{ width: 8, borderRadius: 4, background: C.purple, flex: "none" }} />
      <div style={{ fontFamily: FONT_BODY }}>
        <div style={{ fontSize: fmt.type.body, fontWeight: 700, color: C.ink, lineHeight: 1.2 }}>{title}</div>
        <div style={{ fontSize: fmt.type.small, fontWeight: 500, color: C.muted, marginTop: 8, lineHeight: 1.35 }}>{detail}</div>
      </div>
    </div>
  );
}
