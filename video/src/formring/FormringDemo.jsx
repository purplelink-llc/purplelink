import React from "react";
import { AbsoluteFill, Img, Sequence, staticFile, useCurrentFrame, interpolate } from "remotion";
import { brand, clamp01, expoOut, lerp, FONT_DISPLAY, FONT_BODY } from "../theme.js";
import { useFonts } from "../V2.jsx";

// Silent 24-second demo of Formring for the product page: a title card, the ring over a photo, the PDF ring, the
// video ring, the menu-bar window with its history, and a closing line. Built only from the app's own screenshots
// (video/assets/formring/, copied from the Formring repo's docs/screenshots). Every scene carries its own caption
// as burned-in text, since the video has no sound. 1920 x 1080, 30 fps.

const FPS = brand.fps;
const BG = "oklch(17% 0.03 310)";
const INK = "oklch(96% 0.01 310)";
const MUTED = "oklch(76% 0.03 310)";
const ACCENT = "oklch(72% 0.17 310)";

// scene = [start s, end s]
export const SCENES = {
  title: [0, 3.5],
  photo: [3.5, 9.5],
  pdf: [9.5, 13.5],
  video: [13.5, 17.5],
  history: [17.5, 21.5],
  end: [21.5, 24],
};
export const TOTAL_FRAMES = Math.round(24 * FPS);

const f = (s) => Math.round(s * FPS);

function Fade({ scene, children }) {
  const frame = useCurrentFrame();
  const [a, b] = SCENES[scene];
  const len = f(b - a);
  const o = Math.min(clamp01(frame / 12), clamp01((len - frame) / 12));
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
}

function Caption({ lines, delay = 6, left = 120, top = 380, width = 760 }) {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left, top, width }}>
      {lines.map((l, i) => {
        const p = expoOut(clamp01((frame - delay - i * 10) / 22));
        return (
          <div key={i} style={{
            fontFamily: i === 0 ? FONT_DISPLAY : FONT_BODY, fontWeight: i === 0 ? 600 : 400,
            fontSize: i === 0 ? 68 : 38, lineHeight: 1.22, color: i === 0 ? INK : MUTED,
            marginTop: i === 0 ? 0 : 22, opacity: p, transform: `translateY(${(1 - p) * 24}px)`,
          }}>{l}</div>
        );
      })}
    </div>
  );
}

function Shot({ file, size, right = 150, top = (1080 - size) / 2, scaleFrom = 0.94 }) {
  const frame = useCurrentFrame();
  const p = expoOut(clamp01(frame / 26));
  return (
    <Img src={staticFile(`formring/${file}`)} style={{
      position: "absolute", right, top, width: size, height: size === 0 ? "auto" : undefined,
      borderRadius: 28, boxShadow: "0 30px 80px rgba(0,0,0,0.45)", opacity: p, transform: `scale(${lerp(scaleFrom, 1, p)})`,
    }} />
  );
}

function Title() {
  const frame = useCurrentFrame();
  const p = expoOut(clamp01(frame / 28));
  const q = expoOut(clamp01((frame - 14) / 28));
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
      <Img src={staticFile("formring/icon.png")} style={{ width: 300, height: 300, opacity: p, transform: `scale(${lerp(0.9, 1, p)})` }} />
      <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: 132, color: INK, marginTop: 10, opacity: q }}>Formring</div>
      <div style={{ fontFamily: FONT_BODY, fontSize: 44, color: MUTED, marginTop: 14, opacity: q }}>Convert files from a ring at the pointer</div>
    </AbsoluteFill>
  );
}

// A file name chip that is carried from the left of the ring onto the highlighted slice of the 544 px ring image.
function Chip({ size, right, top, from, to, label, startF, dur = 34 }) {
  const frame = useCurrentFrame();
  const t = expoOut(clamp01((frame - startF) / dur));
  const k = size / 544;
  const x = lerp(from[0], to[0] * k + (1920 - right - size), t);
  const y = lerp(from[1], to[1] * k + top, t);
  const shrink = lerp(1, 0.9, t);
  const o = clamp01((frame - startF + 8) / 8);
  return (
    <div style={{
      position: "absolute", left: x, top: y, transform: `translate(-50%, -50%) scale(${shrink})`, opacity: o,
      background: "oklch(95% 0.02 310)", color: "oklch(20% 0.05 310)", fontFamily: FONT_BODY, fontWeight: 600, fontSize: 30,
      padding: "12px 22px", borderRadius: 14, boxShadow: "0 10px 30px rgba(0,0,0,0.5)", whiteSpace: "nowrap",
    }}>{label}</div>
  );
}

function Photo() {
  const SIZE = 780, RIGHT = 150, TOP = (1080 - SIZE) / 2;
  const frame = useCurrentFrame();
  const second = frame > f(3.2);
  return (
    <>
      <Shot file="ring-photo.png" size={SIZE} right={RIGHT} top={TOP} />
      <Chip size={SIZE} right={RIGHT} top={TOP} from={[960, 330]} to={[272, 150]} label="IMG_2041.jpg" startF={f(1.9)} dur={40} />
      <Caption
        lines={second ? ["Drop it on a slice", "The copy is saved next to the original. The original is not changed."] : ["Hold Option while dragging", "The ring opens at the pointer, with the actions that fit the file."]}
        top={360}
      />
    </>
  );
}

function Pdf() {
  const SIZE = 780;
  return (
    <>
      <Shot file="ring-pdf.png" size={SIZE} />
      <Caption lines={["PDFs", "Merge, split, compress, rotate, to images, to Word, and make scans searchable."]} />
    </>
  );
}

function Video() {
  const SIZE = 780;
  return (
    <>
      <Shot file="ring-video.png" size={SIZE} />
      <Caption lines={["Video and audio", "MP4 and MOV, a shorter file, a GIF, the sound track, or a transcript with subtitles."]} />
    </>
  );
}

function History() {
  const frame = useCurrentFrame();
  const p = expoOut(clamp01(frame / 26));
  const H = 880, W = Math.round(H * 680 / 812);
  return (
    <>
      <Img src={staticFile("formring/menu-bar.png")} style={{
        position: "absolute", right: 210, top: (1080 - H) / 2, width: W, height: H, borderRadius: 24,
        boxShadow: "0 30px 80px rgba(0,0,0,0.45)", opacity: p, transform: `scale(${lerp(0.94, 1, p)})`,
      }} />
      <Caption lines={["Every result is listed", "Undo moves a job's results to the Trash. Files you drop on the menu-bar item or the Dock icon work too."]} />
    </>
  );
}

function End() {
  const frame = useCurrentFrame();
  const p = expoOut(clamp01(frame / 26));
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", opacity: p }}>
      <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: 96, color: INK }}>50 actions, all on your Mac</div>
      <div style={{ fontFamily: FONT_BODY, fontSize: 42, color: MUTED, marginTop: 22 }}>Images, PDFs, video, audio, documents, fonts and archives. Nothing is uploaded.</div>
      <div style={{ width: 120, height: 6, borderRadius: 3, background: ACCENT, marginTop: 40 }} />
    </AbsoluteFill>
  );
}

export function FormringDemo() {
  useFonts();
  const scenes = [["title", Title], ["photo", Photo], ["pdf", Pdf], ["video", Video], ["history", History], ["end", End]];
  return (
    <AbsoluteFill style={{ background: BG }}>
      {scenes.map(([name, Comp]) => (
        <Sequence key={name} from={f(SCENES[name][0])} durationInFrames={f(SCENES[name][1] - SCENES[name][0])}>
          <Fade scene={name}><Comp /></Fade>
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}
