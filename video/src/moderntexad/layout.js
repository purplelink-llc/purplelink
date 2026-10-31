// ModernTex Reddit ads: format layout and colors. Colors are the site's dark-theme tokens (hue 310, site/styles.css).

export const C = {
  ground: "oklch(17% 0.035 310)",
  glow: "oklch(42% 0.16 310 / 0.32)",
  text: "oklch(97% 0.008 310)",
  text2: "oklch(80% 0.03 310)",
  accent: "oklch(78% 0.13 310)",
  ring: "oklch(62% 0.22 310)",
  hairline: "oklch(100% 0 0 / 0.08)",
};

export const FPS = 30;

// Reddit's recommended mobile sizes (Video Ad Specifications, business.reddithelp.com, read 2026-10-31):
// Square 1:1 1200x1200 and Portrait 4:5 1200x1500, at most 30 fps.
// cap: the headline strip; media: the box the app window is cropped into; mark: the Purplelink lockup (the maker's signature).
export const FORMATS = {
  "1x1": { W: 1200, H: 1200, cap: { y: 54, h: 250, size: 74 }, media: { x: 70, y: 316, w: 1060, h: 760 }, mark: { y: 1116, h: 46 } },
  "4x5": { W: 1200, H: 1500, cap: { y: 84, h: 330, size: 86 }, media: { x: 56, y: 440, w: 1088, h: 900 }, mark: { y: 1398, h: 50 } },
};

// Captures are the app window at 2x: a 1000 x 860 pt window, 2000 x 1720 px.
export const SRC = { w: 2000, h: 1720 };

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
