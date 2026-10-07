import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT_BODY, FONT_DISPLAY, brand, camOut, clamp01, reveal } from "./theme.js";
import { CameraFrame, LogoTile, Mark, Row, Words } from "./parts.jsx";
import { Captions } from "./Captions.jsx";
import { cueFrame } from "./timeline.js";

const lineCount = (t) => t.split("\n").length;

function SceneCaptions({ sc, row, fmt, frame, fps }) {
  if (sc.captions === false || !row.words.length) return null;
  return <Captions words={row.words} t={(frame - row.leadFrames) / fps} fmt={fmt} />;
}

export function TitleScene({ sc, row, fmt }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { box } = fmt;
  const bar = reveal(frame, 14, 40);
  return (
    <AbsoluteFill style={{ background: C.purple }}>
      <Mark frame={frame} color={C.onPurple} x={box.x} y={box.y} size={fmt.type.mark} />
      <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ height: 8, width: 120 * bar, background: C.purpleLight, borderRadius: 4, marginBottom: 44 }} />
        <Words text={sc.text} frame={frame} start={row.leadFrames} size={fmt.type.hero} color={C.onPurple} weight={500} stagger={6} />
      </div>
      <SceneCaptions sc={sc} row={row} fmt={fmt} frame={frame} fps={fps} />
    </AbsoluteFill>
  );
}

export function MediaScene({ sc: base, row, fmt }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sc = fmt.vertical && base.vertical ? { ...base, ...base.vertical } : base;
  const { box } = fmt;
  const media = sc.media;
  const layout = sc.layout || "side";
  const aspect = media.w / media.h;
  const enter = reveal(frame, 2, 26);
  const p = camOut(clamp01(frame / row.frames));

  const hl = (Array.isArray(sc.highlight) ? sc.highlight : sc.highlight ? [sc.highlight] : []).map((h) => ({
    ...h,
    p: reveal(frame, cueFrame(row, h.cue, fps, Math.round(row.frames * 0.4)), 20),
  }));

  const fit = sc.fit || (layout === "side" && !fmt.vertical ? "contain" : "cover");
  const headSize = fmt.type.head;
  let head = null;
  let fw;
  let fh;
  let fx;
  let fy;
  if (layout === "bleed") {
    fw = box.w;
    fh = box.h;
    fx = box.x;
    fy = box.y;
  } else if (!fmt.vertical) {
    const colW = 520;
    const availW = box.w - colW - 72;
    fw = availW;
    fh = fit === "contain" ? availW / aspect : box.h;
    if (fh > box.h) {
      fh = box.h;
      fw = fit === "contain" ? fh * aspect : availW;
    }
    fx = box.x + box.w - fw;
    fy = box.y + (box.h - fh) / 2;
    head = { x: box.x, y: box.y, w: colW, h: box.h, center: true };
  } else {
    const headH = headSize * 1.06 * lineCount(sc.text) + 40;
    const remH = box.h - headH;
    fw = box.w;
    fh = fit === "contain" ? fw / aspect : remH;
    fx = box.x;
    fy = box.y + headH + (fit === "contain" ? (remH - fh) / 2 : 0);
    head = { x: box.x, y: box.y, w: box.w, h: headH, center: false };
  }

  return (
    <AbsoluteFill style={{ background: C.bg }}>
      {head && (
        <div style={{ position: "absolute", left: head.x, top: head.y, width: head.w, height: head.h, display: "flex", flexDirection: "column", justifyContent: head.center ? "center" : "flex-start" }}>
          <Words text={sc.text} frame={frame} start={row.leadFrames} size={headSize} color={C.ink} weight={500} />
        </div>
      )}
      <div style={{ position: "absolute", left: fx, top: fy, opacity: enter, transform: `translateY(${(1 - enter) * 28}px)` }}>
        <CameraFrame fw={fw} fh={fh} media={media} trim={sc.trim} frame={frame} zoom={sc.zoom} p={p} fit={fit} highlights={hl} />
        {layout === "bleed" && (
          <div style={{ position: "absolute", left: 32, top: 32, padding: `${fmt.type.small * 0.32}px ${fmt.type.small * 0.8}px`, borderRadius: 100, background: C.purple, color: C.onPurple, fontFamily: FONT_BODY, fontWeight: 700, fontSize: fmt.type.small + 4, opacity: reveal(frame, row.leadFrames, 20) }}>
            {sc.text}
          </div>
        )}
      </div>
      <SceneCaptions sc={sc} row={row} fmt={fmt} frame={frame} fps={fps} />
    </AbsoluteFill>
  );
}

export function CalloutScene({ sc, row, fmt }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { box } = fmt;
  const items = sc.items || [];
  const gap = fmt.vertical ? 56 : 52;
  const rows = (
    <div style={{ display: "flex", flexDirection: "column", gap }}>
      {items.map((it, i) => (
        <Row key={i} title={it.title} detail={it.detail} fmt={fmt} p={reveal(frame, cueFrame(row, it.cue, fps, 20 + i * 45), 22)} />
      ))}
    </div>
  );
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, display: "flex", flexDirection: fmt.vertical ? "column" : "row", alignItems: fmt.vertical ? "flex-start" : "center", justifyContent: fmt.vertical ? "center" : "space-between", gap: fmt.vertical ? 72 : 96 }}>
        <div style={{ width: fmt.vertical ? box.w : 560, flex: "none" }}>
          <Words text={sc.text} frame={frame} start={row.leadFrames} size={fmt.type.head} color={C.ink} weight={500} />
        </div>
        <div style={{ flex: 1, maxWidth: fmt.vertical ? box.w : 900 }}>{rows}</div>
      </div>
      <SceneCaptions sc={sc} row={row} fmt={fmt} frame={frame} fps={fps} />
    </AbsoluteFill>
  );
}

export function EndCardScene({ sc, row, fmt }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { box } = fmt;
  const logo = reveal(frame, 0, 26);
  const url = reveal(frame, 30, 26);
  const lines = sc.lines || [];
  return (
    <AbsoluteFill style={{ background: C.ink }}>
      <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: fmt.vertical ? "flex-start" : "flex-start", gap: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 24, opacity: logo, transform: `translateY(${(1 - logo) * 22}px)`, fontFamily: FONT_BODY, fontWeight: 600, fontSize: fmt.type.body - 6, color: C.purpleLight }}>
          <LogoTile size={104} />
          <span>{brand.wordmark}</span>
        </div>
        <div style={{ marginTop: 44 }}>
          <Words text={sc.text} frame={frame} start={8} size={fmt.type.hero + 24} color={C.onPurple} weight={500} />
        </div>
        <div style={{ marginTop: 40, display: "flex", flexDirection: "column", gap: 14, maxWidth: fmt.vertical ? box.w : 860 }}>
          {lines.map((l, i) => {
            const p = reveal(frame, 18 + i * 8, 24);
            return (
              <div key={i} style={{ opacity: p, transform: `translateY(${(1 - p) * 18}px)`, fontFamily: FONT_BODY, fontWeight: i === 0 ? 700 : 500, fontSize: i === 0 ? fmt.type.body : fmt.type.small, color: i === 0 ? C.onPurple : "oklch(84% 0.05 310)", lineHeight: 1.3 }}>
                {l}
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 56, alignSelf: "flex-start", opacity: url, transform: `translateY(${(1 - url) * 18}px)`, background: C.purple, color: C.onPurple, borderRadius: 100, padding: "20px 48px", fontFamily: FONT_BODY, fontWeight: 700, fontSize: fmt.type.body }}>
          {sc.url}
        </div>
      </div>
      {sc.media && !fmt.vertical && (
        <div style={{ position: "absolute", right: box.x, top: box.y + (box.h - 420) / 2, opacity: reveal(frame, 24, 30), transform: `translateY(${(1 - reveal(frame, 24, 30)) * 24}px)` }}>
          <CameraFrame fw={420 * (sc.media.w / sc.media.h)} fh={420} media={sc.media} frame={frame} zoom={{ from: 1, to: 1.04, x: 0.5, y: 0.5 }} p={camOut(clamp01(frame / row.frames))} fit="contain" highlights={[]} />
        </div>
      )}
      <SceneCaptions sc={sc} row={row} fmt={fmt} frame={frame} fps={fps} />
    </AbsoluteFill>
  );
}

export const SCENES = { title: TitleScene, clip: MediaScene, still: MediaScene, callout: CalloutScene, endcard: EndCardScene };
