import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, delayRender, continueRender } from "remotion";
import { brand, clamp01, expoOut, FONT_BODY, FONT_DISPLAY } from "../theme.js";
import { Bumpered } from "../Bumper.jsx";
import { NARRATION_LEAD } from "./plan.js";

// ModernTex 3.0 demo (16:9) and Short (9:16). Each scene plays a screen capture from public/clips/<clip>.mp4 when the
// build staged one, and a labelled placeholder card when not, so the composition renders end to end before phase 2.
// The captured clip's own audio (the read-aloud voice) plays only where the storyboard marks the scene appAudio.
const C = brand.colors;
const V = (format) => format === "9x16";

function useFonts() {
  const [h] = React.useState(() => delayRender("fonts"));
  React.useEffect(() => {
    Promise.all(Object.values(brand.fonts).map((f) => {
      const face = new FontFace(f.family, `url(${staticFile("fonts/" + f.file.split("/").pop())})`, { weight: f.weight });
      return face.load().then((x) => document.fonts.add(x));
    })).catch(() => {}).finally(() => continueRender(h));
  }, [h]);
}

function Placeholder({ seg, v }) {
  return (
    <AbsoluteFill style={{ background: C.deep, alignItems: "center", justifyContent: "center" }}>
      <div style={{ border: `3px dashed ${C.purpleDim}`, borderRadius: 28, padding: v ? "80px 60px" : "70px 110px", textAlign: "center", color: C.onPurple, fontFamily: FONT_BODY }}>
        <div style={{ fontSize: v ? 40 : 34, opacity: 0.7 }}>PLACEHOLDER CLIP</div>
        <div style={{ fontFamily: FONT_DISPLAY, fontSize: v ? 84 : 76, fontWeight: 500, margin: "18px 0" }}>{seg.clip}</div>
        <div style={{ fontSize: v ? 36 : 32, opacity: 0.7 }}>{seg.dur} s, {seg.tag}</div>
      </div>
    </AbsoluteFill>
  );
}

function Caption({ seg, v, local }) {
  const a = expoOut(clamp01(local / 0.5));
  const out = clamp01((seg.dur - local) / 0.3);
  return (
    <div style={{ position: "absolute", left: v ? 70 : 140, right: v ? 70 : 140, bottom: v ? 430 : 78, display: "flex", justifyContent: "center", opacity: a * out, transform: `translateY(${(1 - a) * 18}px)` }}>
      <div style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: v ? 58 : 44, lineHeight: 1.2, color: C.ink, background: "oklch(98.5% 0.007 310 / 0.94)", borderRadius: 20, padding: v ? "22px 34px" : "16px 30px", textAlign: "center", boxShadow: "0 18px 40px oklch(24% 0.12 310 / 0.28)" }}>{seg.cap}</div>
    </div>
  );
}

function Tag({ seg, v }) {
  return <div style={{ position: "absolute", left: v ? 60 : 70, top: v ? 230 : 56, fontFamily: FONT_BODY, fontWeight: 700, fontSize: v ? 34 : 28, letterSpacing: 1.2, textTransform: "uppercase", color: C.onPurple, background: C.purple, borderRadius: 999, padding: v ? "10px 26px" : "8px 22px" }}>{seg.tag}</div>;
}

function EndCard({ seg, v }) {
  return (
    <AbsoluteFill style={{ background: C.deep, alignItems: "center", justifyContent: "center", fontFamily: FONT_BODY }}>
      <div style={{ fontFamily: FONT_DISPLAY, fontSize: v ? 130 : 120, fontWeight: 500, color: C.onPurple }}>ModernTex 3.0</div>
      <div style={{ fontSize: v ? 48 : 42, color: C.purpleLight, marginTop: 18, textAlign: "center", maxWidth: v ? 880 : 1300 }}>{seg.cap}</div>
    </AbsoluteFill>
  );
}

function Scene({ seg, v, hasClip }) {
  const frame = useCurrentFrame();
  const local = frame / brand.fps;
  return (
    <AbsoluteFill>
      {seg.end ? <EndCard seg={seg} v={v} /> : hasClip ? (
        <OffthreadVideo src={staticFile(`clips/${seg.clip}.mp4`)} muted={!seg.appAudio} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : <Placeholder seg={seg} v={v} />}
      {!seg.end && <Tag seg={seg} v={v} />}
      {!seg.end && <Caption seg={seg} v={v} local={local} />}
      {seg.audio && <Sequence from={Math.round(NARRATION_LEAD * brand.fps)} layout="none"><Audio src={staticFile(seg.audio)} /></Sequence>}
    </AbsoluteFill>
  );
}

export function Demo({ plan, format = "16x9", clips = [] }) {
  useFonts();
  const v = V(format);
  const have = new Set(clips);
  return (
    <Bumpered format={format} total={plan.total} url={plan.url} bumper={plan.bumper}>
      {plan.scenes.map((s) => (
        <Sequence key={s.id} from={Math.round(s.t0 * brand.fps)} durationInFrames={Math.round(s.dur * brand.fps)} layout="none">
          <Scene seg={s} v={v} hasClip={have.has(s.clip)} />
        </Sequence>
      ))}
    </Bumpered>
  );
}
