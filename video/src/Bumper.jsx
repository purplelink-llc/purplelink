import React from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { brand, clamp01, expoOut, FONT_BODY, FONT_DISPLAY } from "./theme.js";
import { FMT } from "./V2.jsx";

// Purplelink LLC brand bumper: opening (about 2.2 s, sting-intro at frame 0) and closing (about 2.5 s after the
// product end card, sting-outro at its start, fade to the background at the very end). One light background
// everywhere: site off-white with a soft purple glow.
import { BUMPER, BUMPER_BG, bumperTotal } from "./bumper.js";
export { BUMPER, BUMPER_BG, bumperTotal };
const INK = "oklch(14% 0.07 310)";
const MUTED = "oklch(46% 0.04 300)";

export function Bumper({ format, t, mode, dur, url, xf = BUMPER.xf }) {
  const f = FMT[format];
  const rv = (d, len = 0.75) => expoOut(clamp01((t - d) / len));
  const fadeIn = mode === "close" ? clamp01(t / xf) : clamp01(t / 0.12);
  const fadeOut = mode === "open" ? expoOut(clamp01((t - (dur - xf)) / xf)) : 0;
  const toBg = mode === "close" ? clamp01((t - (dur - 0.45)) / 0.45) : 0;
  const logo = f.v ? 340 : 300;
  const pop = 0.9 + 0.1 * rv(0.05, 0.8);
  return (
    <AbsoluteFill style={{ opacity: fadeIn * (1 - fadeOut) }}>
      <AbsoluteFill style={{ background: BUMPER_BG }}>
        <div style={{ position: "absolute", left: "50%", top: f.v ? "40%" : "44%", width: f.v ? 1500 : 1700, height: f.v ? 1500 : 1300, transform: "translate(-50%, -50%)", borderRadius: "50%", background: "radial-gradient(closest-side, oklch(92% 0.07 312 / 0.85), oklch(96% 0.03 310 / 0.5) 55%, transparent)" }} />
        <div style={{ position: "absolute", right: -300, bottom: -350, width: 1000, height: 1000, borderRadius: "50%", background: "radial-gradient(closest-side, oklch(88% 0.09 300 / 0.45), transparent)" }} />
      </AbsoluteFill>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: f.v ? 22 : 16, transform: `translateY(${f.v ? -120 : -30}px)` }}>
          <Img src={staticFile("brand/purplelink-logo.png")} style={{ width: logo, height: logo, opacity: rv(0.05, 0.5), transform: `scale(${pop})`, filter: "drop-shadow(0 24px 40px oklch(45% 0.2 310 / 0.25))" }} />
          <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: f.v ? 104 : 108, letterSpacing: "-0.02em", color: INK, lineHeight: 1.05, opacity: rv(0.18), transform: `translateY(${(1 - rv(0.18)) * 26}px)`, whiteSpace: "nowrap" }}>Purplelink LLC</div>
          <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: f.v ? 44 : 40, color: MUTED, opacity: rv(0.32), transform: `translateY(${(1 - rv(0.32)) * 20}px)` }}>purplelink.llc</div>
          {mode === "close" && url && (
            <div style={{ marginTop: f.v ? 30 : 22, fontFamily: FONT_BODY, fontWeight: 600, fontSize: f.v ? 46 : 44, color: INK, background: "oklch(93% 0.06 310)", borderRadius: 999, padding: f.v ? "16px 44px" : "14px 40px", opacity: rv(0.46), transform: `translateY(${(1 - rv(0.46)) * 20}px)` }}>{url}</div>
          )}
        </div>
      </AbsoluteFill>
      {toBg > 0 && <AbsoluteFill style={{ background: BUMPER_BG, opacity: toBg }} />}
    </AbsoluteFill>
  );
}

// Wraps a product cut of `total` seconds between the opening and closing bumpers. Children keep their own
// local timeline (they start at open - xf, under the opening bumper's fade). `url` is the product URL line.
export function Bumpered({ format, total, url, bumper = BUMPER, children }) {
  const frame = useCurrentFrame();
  const t = frame / brand.fps;
  const p0 = bumper.open - bumper.xf;
  const c0 = p0 + total - bumper.xf;
  return (
    <AbsoluteFill style={{ background: BUMPER_BG }}>
      <Sequence from={Math.round(p0 * brand.fps)} layout="none">{children}</Sequence>
      {t < bumper.open + 0.05 && <Bumper format={format} t={t} mode="open" dur={bumper.open} xf={bumper.xf} />}
      {t >= c0 - 0.01 && <Bumper format={format} t={t - c0} mode="close" dur={bumper.close} url={url} xf={bumper.xf} />}
      <Audio src={staticFile("brand/sting-intro.wav")} />
      <Sequence from={Math.round(c0 * brand.fps)}>
        <Audio src={staticFile("brand/sting-outro.wav")} />
      </Sequence>
    </AbsoluteFill>
  );
}
