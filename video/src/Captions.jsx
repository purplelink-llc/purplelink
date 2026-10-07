import React from "react";
import { C, FONT_BODY, clamp01 } from "./theme.js";

// Group word timings into caption chunks that break at punctuation or at the format's word/char limit.
export function chunkWords(words, maxWords, maxChars) {
  // 1. split into phrases at punctuation
  const phrases = [];
  let cur = [];
  words.forEach((w, i) => {
    cur.push(w);
    if (/[.!?;:,]$/.test(w.display || w.word) || i === words.length - 1) {
      phrases.push(cur);
      cur = [];
    }
  });
  // 2. split long phrases into equal parts so no chunk is a lone orphan word
  const len = (arr) => arr.map((w) => w.display || w.word).join(" ").length;
  const chunks = [];
  phrases.forEach((ph) => {
    let parts = Math.ceil(ph.length / maxWords);
    while (parts < ph.length && len(ph) / parts > maxChars) parts++;
    const size = Math.ceil(ph.length / parts);
    for (let i = 0; i < ph.length; i += size) chunks.push(ph.slice(i, i + size));
  });
  return chunks;
}

// Burned-in captions. `t` is seconds since narration started in this scene.
export function Captions({ words, t, fmt }) {
  if (!words || !words.length) return null;
  const chunks = chunkWords(words, fmt.cap.maxWords, fmt.cap.maxChars);
  let idx = -1;
  chunks.forEach((c, i) => {
    if (t >= c[0].start - 0.04) idx = i;
  });
  if (idx < 0) return null;
  const chunk = chunks[idx];
  const last = chunk[chunk.length - 1];
  const next = chunks[idx + 1];
  const holdUntil = next ? next[0].start : last.end + 0.35;
  if (t > holdUntil) return null;
  const inP = clamp01((t - (chunk[0].start - 0.04)) / 0.12);
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: fmt.cap.bottom, display: "flex", justifyContent: "center", pointerEvents: "none" }}>
      <div
        style={{
          maxWidth: fmt.cap.maxW,
          padding: `${fmt.cap.size * 0.28}px ${fmt.cap.size * 0.6}px`,
          borderRadius: fmt.cap.size * 0.55,
          background: "oklch(14% 0.07 310 / 0.9)",
          color: "oklch(98% 0.01 310)",
          fontFamily: FONT_BODY,
          fontWeight: 650,
          fontSize: fmt.cap.size,
          lineHeight: 1.25,
          textAlign: "center",
          opacity: inP,
        }}
      >
        {chunk.map((w, i) => {
          const active = t >= w.start - 0.02 && t <= w.end + 0.02;
          return (
            <span key={i} style={{ color: active ? "oklch(88% 0.13 310)" : "oklch(98% 0.01 310)" }}>
              {w.display || w.word}
              {i < chunk.length - 1 ? " " : ""}
            </span>
          );
        })}
      </div>
    </div>
  );
}
