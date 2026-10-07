// Pure timing helpers shared by the renderer (Remotion) and the CLI (render.mjs).
// Scene length = max(storyboard "seconds", lead + narration + tail). "seconds" is a minimum.

export const LEAD = 0.3; // silence before narration starts in a scene
export const TAIL = 0.3; // default hold after narration ends
export const XFADE = 8; // frames of crossfade into the next scene (overlap)

export function buildTimeline(storyboard, timing, fps) {
  let start = 0;
  return storyboard.scenes.map((sc, i) => {
    const t = (timing && timing.scenes && timing.scenes[i]) || { duration: 0, words: [] };
    const audio = t.duration || 0;
    const tail = sc.tail ?? TAIL;
    const secs = Math.max(sc.seconds || 0, audio ? LEAD + audio + tail : 0);
    const frames = Math.ceil(secs * fps);
    const row = {
      index: i,
      start,
      frames,
      leadFrames: Math.round(LEAD * fps),
      audioSec: audio,
      words: t.words || [],
      audio: t.audio || null,
    };
    start += frames;
    return row;
  });
}

export const totalFrames = (tl) => tl.reduce((a, r) => a + r.frames, 0);

const norm = (s) => String(s).toLowerCase().replace(/[^a-z0-9]/g, "");

// Scene-local frame at which the first word matching `cue` begins (a few frames early so the
// visual lands with the word, not after it). Falls back to `fallback`.
export function cueFrame(row, cue, fps, fallback) {
  if (!cue) return fallback;
  const c = norm(cue);
  const w = row.words.find((x) => norm(x.display || x.word).startsWith(c));
  if (!w) return fallback;
  return Math.max(0, row.leadFrames + Math.round(w.start * fps) - 4);
}
