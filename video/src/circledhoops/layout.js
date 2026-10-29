// Circled Hoops Reddit ads: format layout and colors. Colors are the app's own tokens (lockin apps/web globals.css).

export const C = {
  ground: "#0a0a0d",
  surface: "#16161c",
  surface2: "#1f1f27",
  hairline: "rgba(255,255,255,0.07)",
  text: "#f5f5f7",
  text2: "#a1a1aa",
  text3: "#8a8a93",
  accent: "#ff7a1a",
  accentText: "#ffb37a",
  locked: "#4da3ff",
  lockedText: "#8cc4ff",
  live: "#34d399",
  out: "#ff8a8a",
};

export const FPS = 30;

// cap: the caption headline strip; media: the box the app screen is cropped into; note: the small disclosure line.
export const FORMATS = {
  "9x16": { W: 1080, H: 1920, cap: { y: 150, h: 380, size: 86 }, media: { x: 90, y: 560, w: 900, h: 1150 }, note: { y: 1760 } },
  "4x5": { W: 1080, H: 1350, cap: { y: 56, h: 270, size: 68 }, media: { x: 80, y: 340, w: 920, h: 910 }, note: { y: 1272 } },
  "1x1": { W: 1080, H: 1080, cap: { y: 40, h: 230, size: 60 }, media: { x: 100, y: 285, w: 880, h: 720 }, note: { y: 1022 } },
};

export const SRC = { w: 1170, h: 2532 };

/** Crop rect in source pixels with the box's aspect that covers `focus` (fractions), centred on it, kept inside the source. */
export function cropFor(focus, box, src = SRC) {
  const aspect = box.w / box.h;
  const fx = focus.x * src.w, fy = focus.y * src.h, fw = focus.w * src.w, fh = focus.h * src.h;
  let w = Math.max(fw, fh * aspect);
  let h = w / aspect;
  if (w > src.w) { w = src.w; h = w / aspect; }
  if (h > src.h) { h = src.h; w = h * aspect; }
  let x = fx + fw / 2 - w / 2, y = fy + fh / 2 - h / 2;
  x = Math.min(Math.max(0, x), src.w - w);
  y = Math.min(Math.max(0, y), src.h - h);
  return { x, y, w, h, scale: box.w / w };
}

export const lerp = (a, b, t) => a + (b - a) * t;
export const lerpRect = (a, b, t) => ({ x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t), w: lerp(a.w, b.w, t), h: lerp(a.h, b.h, t) });
