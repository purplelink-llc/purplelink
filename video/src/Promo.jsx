import React, { useEffect, useState } from "react";
import { AbsoluteFill, Audio, Sequence, continueRender, delayRender, interpolate, staticFile, useCurrentFrame } from "remotion";
import { FORMATS, C, FONT_BODY, brand, lerp, clamp01, camOut } from "./theme.js";
import { buildTimeline, XFADE } from "./timeline.js";
import { SCENES } from "./scenes.jsx";
import { CameraFrame } from "./parts.jsx";

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

export function Promo({ format, storyboard, timing }) {
  useFonts();
  const fmt = FORMATS[format];
  const tl = buildTimeline(storyboard, timing, brand.fps);
  return (
    <AbsoluteFill style={{ background: C.ink }}>
      {storyboard.scenes.map((sc, i) => {
        const row = tl[i];
        const Scene = SCENES[sc.type];
        const last = i === tl.length - 1;
        return (
          <Sequence key={i} from={row.start} durationInFrames={row.frames + (last ? 0 : XFADE)} layout="none">
            <Fade first={i === 0}>
              <Sequence from={0} layout="none">
                <Scene sc={sc} row={row} fmt={fmt} />
              </Sequence>
            </Fade>
          </Sequence>
        );
      })}
      {storyboard.scenes.map((sc, i) =>
        tl[i].audio ? (
          <Sequence key={"a" + i} from={tl[i].start + tl[i].leadFrames} durationInFrames={Math.ceil(tl[i].audioSec * brand.fps) + 2}>
            <Audio src={staticFile(tl[i].audio)} />
          </Sequence>
        ) : null
      )}
    </AbsoluteFill>
  );
}

// Crossfade in over XFADE frames. The previous scene continues underneath for the same span.
function Fade({ first, children }) {
  const frame = useCurrentFrame();
  const o = first ? 1 : interpolate(frame, [0, XFADE], [0, 1], { extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
}

// Silent, text-free loop for website embedding. The camera and ring follow a closed cycle so the
// last frame matches the first.
export function Hero({ storyboard }) {
  useFonts();
  const frame = useCurrentFrame();
  const fmt = FORMATS["16x9"];
  const cfg = storyboard.hero || { scene: 1, seconds: 6 };
  const sc = storyboard.scenes[cfg.scene];
  const T = Math.round(cfg.seconds * brand.fps);
  const ph = (frame / T) * Math.PI * 2;
  const breathe = (1 - Math.cos(ph)) / 2; // 0 -> 1 -> 0
  const media = sc.media;
  const aspect = media.w / media.h;
  const fh = 900;
  const fw = fh * aspect;
  const h0 = Array.isArray(sc.highlight) ? sc.highlight[0] : sc.highlight;
  const hl = h0 ? [{ ...h0, p: clamp01(Math.sin(ph - 0.6) * 2.2 + 0.2) }] : [];
  const z = sc.zoom || { from: 1, to: 1.06, x: 0.5, y: 0.5 };
  const zoom = { ...z, from: 1, to: Math.min(z.to, 1.08) };
  return (
    <AbsoluteFill style={{ background: C.bg, alignItems: "center", justifyContent: "center" }}>
      <CameraFrame fw={fw} fh={fh} media={media} frame={frame} zoom={zoom} p={breathe} fit="contain" highlights={hl} />
    </AbsoluteFill>
  );
}
