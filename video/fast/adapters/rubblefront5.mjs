// Adapter: describes a RubbleFront v4 trailer build to the fast pipeline (entry, composition, plan, assets, clips).
// A new project only needs an adapter with the same shape; the cache, proxies, benchmark and render code are shared.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildPlan } from "../../src/rubblefront5/plan5.js";

export const id = "rubblefront5";
const VIDEO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const FL = process.env.RF_FRONTLINK || "/Volumes/Extreme SSD/Frontlink";

export function prepare({ sbPath, format = "16x9", wishlist = false }) {
  const sb = JSON.parse(fs.readFileSync(path.resolve(VIDEO, sbPath), "utf8"));
  const brand = JSON.parse(fs.readFileSync(path.join(VIDEO, "brand-rubblefront.json"), "utf8"));
  const clipDirs = ["v5", "v4", "v3", "v2"].map((v) => path.join(FL, "build", "trailer", v, "clips"));
  const find = (name, ext) => clipDirs.map((d) => path.join(d, `${name}.${ext}`)).find((f) => fs.existsSync(f));
  const art = path.join(FL, "art", "store", "rubblefront");
  const sbf = sb.verticalScenes && format === "9x16" ? { ...sb, scenes: sb.verticalScenes } : sb;
  const sbw = JSON.parse(JSON.stringify(sbf));
  if (wishlist) sbw.scenes.forEach((s) => { if (s.type === "end") s.wishlist = sb.wishlistText || "Wishlist on Steam"; });
  const plan = buildPlan(sbw, format);
  const assets = [];
  for (const f of Object.values(brand.fonts)) assets.push({ dest: `fonts/${path.basename(f.file)}`, src: path.resolve(VIDEO, f.file) });
  assets.push({ dest: "brand/logo.png", src: path.join(art, "library-logo.png") });
  assets.push({ dest: "media/herobg.png", src: path.join(art, "library-hero-3840x1240.png") });
  const clips = new Map();
  for (const sc of sbw.scenes) {
    for (const ins of sc.insets || []) if (!clips.has(ins.clip)) clips.set(ins.clip, find(ins.clip, "mp4"));
    if (sc.clip && !clips.has(sc.clip)) clips.set(sc.clip, find(sc.clip, "mp4"));
    if (sc.vclip && !clips.has(sc.vclip)) clips.set(sc.vclip, find(sc.vclip, "mp4"));
  }
  for (const [n, p] of clips) if (!p) throw new Error(`missing clip ${n}`);
  return {
    sb, plan, format,
    entryPoint: path.join(VIDEO, "src", "rubblefront5", "index.jsx"),
    sourceDir: path.join(VIDEO, "src", "rubblefront5"),
    compositionId: "Trailer5",
    inputProps: { format, plan },
    assets,
    clips: [...clips].map(([name, src]) => ({ name, src, dest: `media/${name}.mp4` })),
    fps: plan.fps,
    outDir: path.join(FL, "build", "trailer", "v5"),
    outName: (wl) => { const n = (sb.outputs || {})[format] || `${sb.id}-${format}.mp4`; return wl ? n.replace(".mp4", "-wishlist.mp4") : n; },
    musicDir: path.join(FL, "game", "audio", "music"),
    mixSpec: () => ({
      dur: plan.total,
      music: (sb.music || []).map((m) => ({ ...m, file: path.join(FL, "game", "audio", "music", m.file) })),
      music_env: sb.musicEnv || [],
      synth: [...(sb.synth || []), ...plan.sfx.filter(() => !sb.noAutoSfx)],
      synth_db: sb.synthDb ?? -3,
      peak_db: -1.5,
    }),
    crf: sb.crf ?? 16,
    sourceDirs: [path.join(VIDEO, "src", "rubblefront5")],
    sourceFiles: [path.join(VIDEO, "brand-rubblefront.json")],
    totalFrames: Math.max(1, Math.round(plan.total * plan.fps)),
  };
}
