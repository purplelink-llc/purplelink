// Timing of the AKA spot, shared by AKASpot.jsx and build-aka-spot.mjs (which cannot import JSX).
// 120 BPM at 30 fps: one beat = 15 frames.
export const BEAT = 15;
// The problem: four everyday conversions (4 beats), an app for each (4), the apps collapse into AKA (4).
export const PROBLEM = 12 * BEAT;
export const INTRO = 4 * BEAT;
export const SETS = ["heic", "pdf", "mov", "m4a", "md", "docx", "zip", "ttf", "batch"];
// Beats per cut: the first three get room, the rest get quicker; the batch cut gets room again.
export const LENGTHS = [4, 4, 4, 2, 2, 2, 2, 2, 4].map((b) => b * BEAT);
export const STROBE = 2 * BEAT;
export const END = 8 * BEAT;
export const STARTS = LENGTHS.reduce((acc, l, i) => [...acc, acc[i] + l], [PROBLEM + INTRO]);
export const STROBE_AT = STARTS[SETS.length];
export const END_AT = STROBE_AT + STROBE;
export const SPOT_FRAMES = END_AT + END;
// One still per picker: the pointer resting on the chosen slice.
export const SPOT_STILLS = SETS.map((name, i) => ({ name, frame: STARTS[i] + Math.round(LENGTHS[i] * 0.6) }));
