import React, { createContext, useContext } from "react";
import { AbsoluteFill, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { clamp01, expoOut, lerp, FONT_DISPLAY, FONT_BODY } from "../theme.js";
import { useFonts } from "../V2.jsx";
import { BEAT, PROBLEM, LENGTHS, INTRO, STROBE, END, STARTS as starts, STROBE_AT, END_AT } from "./spot-stills.mjs";

export { SPOT_FRAMES } from "./spot-stills.mjs";

// A fast product spot for Née: a file is dragged, the ring opens at the pointer, the pointer sweeps to a slice, the
// file drops, the converted copy appears. Eight file types, quicker as it goes, then the end card. Cut on a 120 BPM
// grid (one beat = 15 frames) so a music bed lines up. Every ring frame is the app's own drawing
// (`Née --render-spot`, backgrounds cut out), in video/assets/nee/spot/. 1920 x 1080, or 1080 x 1920 with `tall`, 30 fps.

const INK = "oklch(97% 0.01 310)";
const ACCENT = "oklch(70% 0.19 310)";
const RING = 760; // shown size of the 816 px ring frames

// Wide (16:9) and tall (9:16, for Shorts, Reels and TikTok: text kept out of the top 210 px and bottom 400 px).
const LAYOUTS = {
  wide: { CX: 1220, CY: 540, mid: [960, 540], from: [-560, 120], word: { left: 130, top: 440, width: 900, size: 150, align: "left" },
    chore: 150, head: { top: 120, size: 96 }, grid: { cols: 4, x0: 960, y0: 470, dx: 300, dy: 290 }, fold: [960, 560],
    intro: 190, oneApp: 96 },
  tall: { CX: 540, CY: 1030, mid: [540, 1000], from: [-260, 420], word: { left: 0, top: 300, width: 1080, size: 130, align: "center" },
    chore: 120, head: { top: 300, size: 84 }, grid: { cols: 2, x0: 540, y0: 650, dx: 400, dy: 250 }, fold: [540, 960],
    intro: 150, oneApp: 76 },
};
const Layout = createContext(LAYOUTS.wide);

// [word, ext on the tile, input name, frame set, highlight path (last = chosen slice), slices on the page, output name, output tile]
const CUTS = [
  ["Photos.", "HEIC", "IMG_2041.HEIC", "heic", [6, 7, 0], 8, "IMG_2041.jpg", "JPG"],
  ["PDFs.", "PDF", "Scan.pdf", "pdf", [3, 2, 1], 8, "Scan (compressed).pdf", "PDF"],
  ["Video.", "MOV", "demo.mov", "mov", [0, 1, 2], 8, "demo.gif", "GIF"],
  ["Audio.", "M4A", "Interview.m4a", "m4a", [3, 4], 8, "Interview (transcript).txt", "TXT"],
  ["Markdown.", "MD", "Notes.md", "md", [0, 1], 6, "Notes.pdf", "PDF"],
  ["Documents.", "DOCX", "Report.docx", "docx", [1, 0], 8, "Report.pdf", "PDF"],
  ["Archives.", "ZIP", "Photos.zip", "zip", [1, 0], 4, "Photos", "folder"],
  ["Fonts.", "TTF", "Brand.ttf", "ttf", [1, 0], 6, "Brand.woff", "WOFF"],
  // Many files in one drop: every one is converted (a Finder Service takes up to 200 at a time).
  ["All at once.", "HEIC", "24 photos", "heic", [7, 0], 8, "24 JPEGs", "JPG", 24],
];
const TYPE_COLORS = { HEIC: "#e8743b", JPG: "#e8743b", PDF: "#d9433b", MOV: "#4a7fe0", GIF: "#4a7fe0", M4A: "#c2448f",
  TXT: "#6b7280", MD: "#3d8a6e", DOCX: "#2f64c8", ZIP: "#8a6d3b", TTF: "#7a4fc9", WOFF: "#7a4fc9" };

function Wallpaper() {
  return (
    <AbsoluteFill style={{
      background: "radial-gradient(1200px 800px at 70% 45%, oklch(30% 0.13 310) 0%, oklch(16% 0.06 300) 55%, oklch(9% 0.02 290) 100%)",
    }} />
  );
}

function Name({ text }) {
  return (
    <div style={{
      marginTop: 16, fontFamily: FONT_BODY, fontWeight: 600, fontSize: 30, color: INK, whiteSpace: "nowrap",
      textShadow: "0 2px 10px rgba(0,0,0,0.6)",
    }}>{text}</div>
  );
}

function FileTile({ ext, name, showName = true, count = 1 }) {
  if (count > 1) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ position: "relative", width: 190, height: 220 }}>
          {[2, 1, 0].map((k) => (
            <div key={k} style={{ position: "absolute", left: 20 + k * 14, top: k * -12 + 24, transform: `rotate(${(k - 1) * 5}deg)` }}>
              <FileTile ext={ext} name="" showName={false} />
            </div>
          ))}
          <div style={{
            position: "absolute", right: -6, top: 0, minWidth: 64, height: 64, borderRadius: 32, background: ACCENT, color: "white",
            fontFamily: FONT_BODY, fontWeight: 800, fontSize: 32, display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 8px 20px rgba(0,0,0,0.4)",
          }}>{count}</div>
        </div>
        {showName && <Name text={name} />}
      </div>
    );
  }
  if (ext === "folder") {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ position: "relative", width: 190, height: 150 }}>
          <div style={{ position: "absolute", left: 0, top: 0, width: 80, height: 34, borderRadius: "12px 12px 0 0", background: "#5aa6e8" }} />
          <div style={{ position: "absolute", left: 0, top: 18, width: 190, height: 132, borderRadius: 14, background: "linear-gradient(#7cc0f5, #4f9be0)", boxShadow: "0 18px 40px rgba(0,0,0,0.45)" }} />
        </div>
        {showName && <Name text={name} />}
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{
        position: "relative", width: 150, height: 190, borderRadius: 14, background: "linear-gradient(#ffffff, #eceaf0)",
        boxShadow: "0 18px 40px rgba(0,0,0,0.45)", overflow: "hidden",
      }}>
        <div style={{ position: "absolute", right: 0, top: 0, width: 42, height: 42, background: "linear-gradient(225deg, #d6d3dc 50%, transparent 50%)" }} />
        <div style={{
          position: "absolute", left: 0, right: 0, bottom: 26, height: 44, background: TYPE_COLORS[ext] || ACCENT, color: "white",
          fontFamily: FONT_BODY, fontWeight: 800, fontSize: ext.length > 3 ? 24 : 28, letterSpacing: 1,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>{ext}</div>
      </div>
      {showName && <Name text={name} />}
    </div>
  );
}

function Cursor({ x, y }) {
  return (
    <svg width="44" height="64" viewBox="0 0 22 32" style={{ position: "absolute", left: x - 4, top: y - 2, filter: "drop-shadow(0 3px 4px rgba(0,0,0,0.5))" }}>
      <path d="M2 2 L2 26 L8 20 L12 30 L16 28 L12 18 L20 18 Z" fill="black" stroke="white" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

// A point inside slice i of n (slice 0 at the top, clockwise).
function slicePoint(i, n, { CX, CY }) {
  const a = (i / n) * Math.PI * 2;
  const r = RING * 0.4; // the outer band of the slice, past its label
  return [CX + Math.sin(a) * r, CY - Math.cos(a) * r];
}

function Cut({ cut, len }) {
  const [word, ext, name, set, path, n, outName, outExt, count = 1] = cut;
  const frame = useCurrentFrame();
  const L = useContext(Layout), { CX, CY } = L;
  const k = len / (4 * BEAT); // 1 for long cuts, 0.5 for short ones
  const t = (x) => Math.max(1, Math.round(x * k));
  const DRAG = t(12), BLOOM = t(8), SWEEP_END = t(40), DROP = t(6), RESULT = t(44);

  const wordIn = expoOut(clamp01(frame / 8));
  // Drag the file from the left to where the ring opens.
  const d = expoOut(clamp01(frame / DRAG));
  const start = [CX + L.from[0], CY + L.from[1]];
  let cur = [lerp(start[0], CX, d), lerp(start[1], CY, d)];
  const bloom = expoOut(clamp01((frame - DRAG) / BLOOM));
  // Sweep through the path between the bloom and SWEEP_END.
  const sweepStart = DRAG + BLOOM;
  const step = (SWEEP_END - sweepStart) / path.length;
  const si = frame < sweepStart ? -1 : Math.min(path.length - 1, Math.floor((frame - sweepStart) / step));
  if (si >= 0) {
    const from = si === 0 ? [CX, CY] : slicePoint(path[si - 1], n, L);
    const to = slicePoint(path[si], n, L);
    const p = expoOut(clamp01((frame - sweepStart - si * step) / Math.max(2, step * 0.7)));
    cur = [lerp(from[0], to[0], p), lerp(from[1], to[1], p)];
  }
  const highlighted = si >= 0 ? path[si] : "none";
  // Once the ring is open the carried file sits just outside the pointer, away from the centre, so the slice label shows.
  const dx = cur[0] - CX, dy = cur[1] - CY, dl = Math.hypot(dx, dy) || 1;
  const out = [(dx / dl) * 46 * bloom, (dy / dl) * (dy > 0 ? 14 : 46) * bloom + lerp(30, 0, bloom)];
  const drop = clamp01((frame - SWEEP_END) / DROP);
  const ringScale = lerp(0.82, 1, bloom) * lerp(1, 0.7, drop);
  const res = expoOut(clamp01((frame - RESULT) / t(10)));

  return (
    <AbsoluteFill>
      <div style={{
        position: "absolute", left: L.word.left, top: L.word.top, width: L.word.width, textAlign: L.word.align,
        fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: L.word.size, color: INK,
        letterSpacing: -2, lineHeight: 1, opacity: wordIn, transform: `translateY(${(1 - wordIn) * 18}px)`,
      }}>{word}</div>
      <Img src={staticFile(`nee/spot/ring-${set}-${highlighted}.png`)} style={{
        position: "absolute", left: CX - RING / 2, top: CY - RING / 2, width: RING, height: RING,
        opacity: bloom * (1 - drop), transform: `scale(${ringScale})`,
      }} />
      <div style={{
        position: "absolute", left: cur[0] + out[0], top: cur[1] + out[1], opacity: (1 - drop) * lerp(1, 0.9, bloom),
        transform: `translate(-50%, -50%) scale(${lerp(1, 0.42, bloom) * lerp(1, 0.6, drop)})`,
      }}>
        <FileTile ext={ext} name={name} showName={bloom < 0.5} count={count} />
      </div>
      {res > 0 && (
        <div style={{ position: "absolute", left: CX, top: CY - 30, transform: `translate(-50%, -50%) scale(${lerp(0.7, 1, res)})`, opacity: res }}>
          <FileTile ext={outExt} name={outName} count={count} />
        </div>
      )}
      {drop < 1 && <Cursor x={cur[0]} y={cur[1]} />}
    </AbsoluteFill>
  );
}

// The problem: everyday conversions, an app downloaded for each, and all of them folding into Née.
const CHORES = ["HEIC to JPEG.", "Shrink a PDF.", "A clip as a GIF.", "The words in a recording."];
const APPS = [["HEIC Converter", 30], ["PDF Shrinker", 25], ["GIF Maker", 250], ["Transcriber", 340],
  ["Markdown to PDF", 150], ["Word to PDF", 260], ["Unarchiver", 70], ["Font Converter", 290]];

function AppTile({ label, hue }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 260 }}>
      <div style={{
        width: 168, height: 168, borderRadius: 38, boxShadow: "0 16px 36px rgba(0,0,0,0.45)",
        background: `linear-gradient(160deg, oklch(62% 0.08 ${hue}), oklch(40% 0.06 ${hue}))`,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <div style={{ width: 70, height: 88, borderRadius: 10, background: "rgba(255,255,255,0.85)" }} />
      </div>
      <div style={{ marginTop: 14, fontFamily: FONT_BODY, fontWeight: 600, fontSize: 28, color: INK, whiteSpace: "nowrap" }}>{label}</div>
    </div>
  );
}

function Problem() {
  const frame = useCurrentFrame();
  const L = useContext(Layout);
  if (frame < 4 * BEAT) {
    const i = Math.floor(frame / BEAT);
    const p = expoOut(clamp01((frame - i * BEAT) / 6));
    return (
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: L.chore, color: INK, letterSpacing: -2, opacity: p,
          maxWidth: 940, textAlign: "center", lineHeight: 1.05, transform: `translateY(${(1 - p) * 20}px)` }}>{CHORES[i]}</div>
      </AbsoluteFill>
    );
  }
  const f = frame - 4 * BEAT;
  const fold = expoOut(clamp01((f - 4 * BEAT) / 14)); // the apps fly into the centre
  const head = expoOut(clamp01(f / 8));
  const icon = expoOut(clamp01((f - 4 * BEAT - 10) / 12));
  const line = expoOut(clamp01((f - 4 * BEAT - 18) / 12));
  return (
    <AbsoluteFill>
      <div style={{
        position: "absolute", top: L.head.top, left: "50%", transform: "translateX(-50%)", width: Math.min(1700, 940 * (L.grid.cols / 2)),
        textAlign: "center", fontFamily: FONT_DISPLAY, fontWeight: 600, lineHeight: 1.05, fontSize: L.head.size, color: INK, letterSpacing: -1, opacity: head * (1 - fold),
        whiteSpace: L.grid.cols === 2 ? "pre-line" : "normal" }}>{"So you download\nan app for each."}</div>
      {APPS.map(([label, hue], i) => {
        const { cols, x0, y0, dx, dy } = L.grid;
        const x = x0 + ((i % cols) - (cols - 1) / 2) * dx, y = y0 + Math.floor(i / cols) * dy;
        const pop = expoOut(clamp01((f - i * (BEAT / 2)) / 8));
        return (
          <div key={label} style={{
            position: "absolute", left: lerp(x, L.fold[0], fold), top: lerp(y, L.fold[1], fold),
            transform: `translate(-50%, -50%) scale(${lerp(0.6, 1, pop) * lerp(1, 0.2, fold)})`, opacity: pop * (1 - fold),
          }}><AppTile label={label} hue={hue} /></div>
        );
      })}
      {icon > 0 && (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
          <Img src={staticFile("nee/icon.png")} style={{ width: 260, height: 260, opacity: icon, transform: `scale(${lerp(0.6, 1, icon)})` }} />
          <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: L.oneApp, color: INK, marginTop: 20, letterSpacing: -1, opacity: line, textAlign: "center" }}>Or one app for all of it.</div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
}

function Intro() {
  const frame = useCurrentFrame();
  const L = useContext(Layout);
  const words = ["Drag.", "Hold Option.", "Drop.", "Done."];
  const i = Math.min(words.length - 1, Math.floor(frame / BEAT));
  const p = expoOut(clamp01((frame - i * BEAT) / 6));
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{
        fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: L.intro, color: i === 3 ? ACCENT : INK, letterSpacing: -3,
        opacity: p, transform: `scale(${lerp(1.06, 1, p)})`,
      }}>{words[i]}</div>
    </AbsoluteFill>
  );
}

// Every ring, a few frames each.
function Strobe() {
  const frame = useCurrentFrame();
  const { mid } = useContext(Layout);
  const sets = [...new Set(CUTS.map((c) => c[3]))];
  const per = Math.max(1, Math.floor(STROBE / sets.length));
  const i = Math.min(sets.length - 1, Math.floor(frame / per));
  return (
    <Img src={staticFile(`nee/spot/ring-${sets[i]}-none.png`)} style={{
      position: "absolute", left: mid[0] - RING / 2, top: mid[1] - RING / 2, width: RING, height: RING,
    }} />
  );
}

function End() {
  const frame = useCurrentFrame();
  const a = expoOut(clamp01(frame / 14));
  const b = expoOut(clamp01((frame - 10) / 16));
  const c = expoOut(clamp01((frame - 24) / 16));
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
      <Img src={staticFile("nee/icon.png")} style={{ width: 230, height: 230, opacity: a, transform: `scale(${lerp(0.9, 1, a)})` }} />
      <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: 150, color: INK, marginTop: 6, letterSpacing: -2, lineHeight: 1.05, opacity: a }}>Née</div>
      <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: 50, color: INK, marginTop: 12, opacity: b }}>51 actions. All on your Mac.</div>
      <div style={{ fontFamily: FONT_BODY, fontWeight: 600, fontSize: 36, color: ACCENT, marginTop: 30, opacity: c }}>purplelink.llc/nee</div>
    </AbsoluteFill>
  );
}

export function NeeSpot({ tall = false }) {
  useFonts();
  return (
    <Layout.Provider value={tall ? LAYOUTS.tall : LAYOUTS.wide}>
    <AbsoluteFill style={{ background: "black" }}>
      <Wallpaper />
      <Sequence durationInFrames={PROBLEM}><Problem /></Sequence>
      <Sequence from={PROBLEM} durationInFrames={INTRO}><Intro /></Sequence>
      {CUTS.map((cut, i) => (
        <Sequence key={i} from={starts[i]} durationInFrames={LENGTHS[i]}><Cut cut={cut} len={LENGTHS[i]} /></Sequence>
      ))}
      <Sequence from={STROBE_AT} durationInFrames={STROBE}><Strobe /></Sequence>
      <Sequence from={END_AT} durationInFrames={END}><End /></Sequence>
    </AbsoluteFill>
    </Layout.Provider>
  );
}
