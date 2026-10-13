// RubbleFront trailer v2 plan: storyboard -> timeline. Pure data, shared by the build script and the Remotion composition.
//
// scene types:
//   clip   { clip, in, dur, speed=1, slow:[{at,dur,speed}]  (speed 0 = freeze; `at` is seconds from the scene start),
//            crop:{x,y,s}  static punch-in on the source (origin x,y in 0..1, scale s),
//            punch:{from,to}  extra animated scale over the scene, shake:[{at,amp,dur,zoom}], flash:[{at,dur,amp,color}],
//            cards:[{text,at,dur,pos,size,accent}],   *word* in text is drawn in the accent colour
//            v:{x,y,s}  vertical (9:16) crop: x,y = which part of the 16:9 picture sits in the window, s = extra zoom,
//            sfx:false  leave the clip's own sound out, grade:"cold"|"warm"|null }
//   black  { dur, cards }   a held dark frame with text
//   logo   { dur }          the RUBBLEFRONT logo slam
//   end    { dur, lines }   end card
export const FPS = 30;

export function spans(sc) {
  const base = sc.speed ?? 1;
  const slow = [...(sc.slow || [])].sort((a, b) => a.at - b.at);
  const out = [];
  let t = 0;
  let src = sc.in ?? 0;
  for (const s of slow) {
    if (s.at > t + 1e-6) { out.push({ start: t, dur: s.at - t, src, rate: base }); src += (s.at - t) * base; t = s.at; }
    out.push({ start: t, dur: s.dur, src, rate: s.speed }); src += s.dur * s.speed; t = s.at + s.dur;
  }
  if (sc.dur > t + 1e-6) out.push({ start: t, dur: sc.dur - t, src, rate: base });
  return out;
}

export function buildPlan(sb, format = "16x9") {
  const shots = [];
  const cards = [];
  const sfx = []; // synthesised hits the mixer should add: {t, kind, gain_db}
  const gameAudio = []; // pieces of the clips' own sound
  let t = 0;
  let end = null;
  sb.scenes.forEach((sc, i) => {
    const dur = sc.dur;
    const type = sc.type || "clip";
    if (type === "end") end = { start: t, dur, lines: sc.lines || [], wishlist: sc.wishlist || false };
    const sp = type === "clip" ? spans(sc) : [];
    shots.push({ i, type, start: t, dur, clip: sc.clip, spans: sp, crop: sc.crop || null, punch: sc.punch || null, shake: sc.shake || [], flash: sc.flash || [], v: sc.v || null, grade: sc.grade || null, dim: sc.dim ?? 0, logo: sc.logo || null, vclip: sc.vclip || null, insets: sc.insets || [], vig: sc.vig ?? 0.35, fadeIn: sc.fadeIn ?? 0, fadeOut: sc.fadeOut ?? 0 });
    for (const c of sc.cards || []) {
      cards.push({ ...c, start: t + (c.at ?? 0.15), end: Math.min(t + (c.at ?? 0.15) + (c.dur ?? Math.min(dur - 0.2, 1.6)), c.span ? 1e9 : t + dur - 0.02), scene: i });
      if (c.sfx !== false) sfx.push({ t: t + (c.at ?? 0.15), kind: c.sfx || "slam", gain_db: c.sfxDb ?? 0 });
    }
    for (const f of sc.flash || []) if (f.sfx !== false) sfx.push({ t: t + f.at, kind: f.sfx || "hit", gain_db: f.sfxDb ?? 0 });
    for (const f of sc.hits || []) sfx.push({ t: t + f.at, kind: f.kind || "hit", gain_db: f.gain_db ?? 0, dur: f.dur });
    if (type === "logo") sfx.push({ t, kind: "boom", gain_db: 2 });
    if (sc.logo) sfx.push({ t: t + sc.logo.at, kind: "boom", gain_db: 10 });
    if (type === "clip" && sc.clip && sc.sfx !== false) {
      for (const s of sp) if (s.rate === 1) gameAudio.push({ clip: sc.clip, in: s.src, dur: s.dur, t: t + s.start, gain_db: sc.sfxDb ?? sb.sfxDb ?? -6 });
    }
    t += dur;
  });
  return { fps: FPS, total: t, shots, cards, sfx, gameAudio, end, format };
}
