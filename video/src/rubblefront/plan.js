// RubbleFront trailer plan: storyboard + narration timing -> an absolute timeline (seconds from the start of the cut).
// Pure data, no React, so the Node build script, the Remotion composition and the SRT writer all read the same numbers.
//
// storyboard.scenes[i]:
//   gameplay shot  { clip: "odds", in: 0.5, dur: 5, narration, narrAt, caption: "text shown when there is no narration",
//                    zoom: {from,to,x,y}, v: {z,x,y}, fade: 0.12 }       clip = build/trailer/clips/<clip>.mp4
//   still          { still: "path from video/", dur, zoom, v }
//   end card       { type: "end", dur, lines: [...] }
// narration plays from scene start + narrAt (default 0.35 s). Its word timings come from narrate.py (timing.json).

export const FPS = 30;

export function chunkWords(words, maxWords, maxChars) {
  const phrases = [];
  let cur = [];
  words.forEach((w, i) => {
    cur.push(w);
    if (/[.!?;:,]$/.test(w.display || w.word) || i === words.length - 1) {
      phrases.push(cur);
      cur = [];
    }
  });
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

export const CAP = {
  "16x9": { maxWords: 7, maxChars: 48 },
  "9x16": { maxWords: 4, maxChars: 24 },
};

export function buildPlan(sb, timing, format = "16x9") {
  const shots = [];
  const captions = [];
  const narration = [];
  const warnings = [];
  let t = 0;
  let end = null;
  sb.scenes.forEach((sc, i) => {
    const dur = sc.dur;
    if (sc.type === "end") {
      end = { start: t, dur, lines: sc.lines || [], vertical: sc.vertical || null };
      shots.push({ i, kind: "end", start: t, dur });
    } else {
      shots.push({
        i,
        kind: sc.still ? "still" : "clip",
        name: sc.clip || sc.still,
        start: t,
        dur,
        in: sc.in ?? 0,
        speed: sc.speed ?? 1,
        zoom: sc.zoom || null,
        v: sc.v || null,
        fade: sc.fade ?? 0,
        hold: sc.hold ?? null, // freeze the clip at this clip-second after `hold`
      });
    }
    const tm = timing?.scenes?.[i];
    if (sc.narration && tm?.duration) {
      const at = t + (sc.narrAt ?? 0.35);
      narration.push({ i, file: tm.audio, t: at, dur: tm.duration, text: sc.narration });
      if (at + tm.duration > t + dur + 0.05) warnings.push(`scene ${i}: narration ends ${(at + tm.duration - t - dur).toFixed(2)} s after the shot`);
      const words = tm.words.map((w) => ({ display: w.display || w.word, start: at + w.start, end: at + w.end }));
      const cfg = CAP[format] || CAP["16x9"];
      chunkWords(words, cfg.maxWords, cfg.maxChars).forEach((ch, k, all) => {
        const nextStart = all[k + 1] ? all[k + 1][0].start : null;
        const s = ch[0].start - 0.04;
        const e = nextStart ? nextStart - 0.02 : ch[ch.length - 1].end + 0.45;
        captions.push({ start: s, end: e, words: ch });
      });
    } else if (sc.caption) {
      captions.push({
        start: t + (sc.capAt ?? 0.2),
        end: t + (sc.capAt ?? 0.2) + (sc.capDur ?? Math.min(dur - 0.3, 3.2)),
        words: sc.caption.split(/\s+/).map((w) => ({ display: w, start: 0, end: 0 })),
        card: true,
      });
    }
    t += dur;
  });
  return { fps: FPS, total: t, shots, captions, narration, end, warnings, format };
}

export function toSrt(captions) {
  const f = (s) => {
    const ms = Math.max(0, Math.round(s * 1000));
    const h = String(Math.floor(ms / 3600000)).padStart(2, "0");
    const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, "0");
    const sec = String(Math.floor((ms % 60000) / 1000)).padStart(2, "0");
    return `${h}:${m}:${sec},${String(ms % 1000).padStart(3, "0")}`;
  };
  return captions.map((c, i) => `${i + 1}\n${f(c.start)} --> ${f(c.end)}\n${c.words.map((w) => w.display).join(" ").replace(/Rubblefront/gi, "RubbleFront")}\n`).join("\n");
}
