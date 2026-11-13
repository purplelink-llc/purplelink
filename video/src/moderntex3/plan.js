// Timeline for the ModernTex 3.0 demo and Short, from a storyboard (storyboards/moderntex-3-*.json).
// Pure JS (no JSX) so the build script and the composition share it. Times are seconds inside the product cut.
import { BUMPER, bumperTotal } from "../bumper.js";

export const NARRATION_LEAD = 0.3;

export function buildPlan(sb, timing = null) {
  let t = 0;
  const scenes = sb.scenes.map((s, i) => {
    const seg = { ...s, i, t0: t, t1: t + s.dur };
    t += s.dur;
    const tm = timing && timing.scenes ? timing.scenes[i] : null;
    seg.narrationDur = tm && tm.duration ? tm.duration : 0;
    seg.audio = tm && tm.audio ? tm.audio : null;
    return seg;
  });
  return { id: sb.id, total: t, scenes, bumper: sb.bumper ? { ...BUMPER, open: sb.bumper.open, close: sb.bumper.close, xf: sb.bumper.xf } : BUMPER, url: sb.bumper ? sb.bumper.url : "purplelink.llc/moderntex" };
}

export const planTotal = (plan) => bumperTotal(plan.total, plan.bumper);

// A scene's narration must fit inside the scene, or the cut talks over the next shot.
export function overruns(plan) {
  return plan.scenes.filter((s) => s.narrationDur && NARRATION_LEAD + s.narrationDur > s.dur + 0.05).map((s) => `${s.id}: narration ${s.narrationDur.toFixed(2)} s in a ${s.dur} s scene`);
}
