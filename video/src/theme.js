import { Easing, interpolate } from "remotion";
import brand from "../brand.json";

export { brand };
export const C = brand.colors;
export const FONT_DISPLAY = `"${brand.fonts.display.family}", Georgia, serif`;
export const FONT_BODY = `"${brand.fonts.body.family}", system-ui, sans-serif`;

// Exponential ease-out for entrances. No bounce, no overshoot.
export const expoOut = Easing.bezier(0.16, 1, 0.3, 1);
// Gentler ease-out for long camera moves.
export const camOut = Easing.bezier(0.33, 1, 0.68, 1);

export const clamp01 = (v) => Math.min(1, Math.max(0, v));

// 0 -> 1 progress of an entrance that starts at `start` frames and lasts `dur` frames.
export function reveal(frame, start, dur = 22) {
  return expoOut(clamp01((frame - start) / dur));
}

export const lerp = (a, b, t) => a + (b - a) * t;

// Frame geometry. `box` is the content area inside the safe margins; captions live below it.
// 9:16 keeps the top 210 px and bottom ~400 px clear of Shorts/Reels/TikTok interface overlays.
export const FORMATS = {
  "16x9": {
    name: "16x9",
    W: 1920,
    H: 1080,
    vertical: false,
    box: { x: 120, y: 90, w: 1680, h: 760 },
    cap: { bottom: 70, maxW: 1560, size: 48, maxWords: 6, maxChars: 44 },
    type: { hero: 136, head: 84, body: 46, small: 34, mark: 34 },
  },
  "9x16": {
    name: "9x16",
    W: 1080,
    H: 1920,
    vertical: true,
    box: { x: 72, y: 210, w: 936, h: 1080 },
    cap: { bottom: 410, maxW: 936, size: 58, maxWords: 4, maxChars: 26 },
    type: { hero: 124, head: 88, body: 52, small: 38, mark: 34 },
  },
};

export { interpolate };
