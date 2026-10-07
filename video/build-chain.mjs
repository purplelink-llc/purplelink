// node build-chain.mjs --of-the-day [--date YYYY-MM-DD] [--sport nba] [--format 9x16|16x9|both] [--stills t1,t2]
// node build-chain.mjs --daily [--date YYYY-MM-DD]                   yesterday's Lockerlink puzzle and its shortest chain
// node build-chain.mjs --player "LeBron James" [--to "Cooper Flagg"] [--sport nba]
// node build-chain.mjs --batch nba --tier 5 [--limit N]              one video per star in a league
// "Chain of the day" videos (src/Chain.jsx): two players and the teammates between them, one link at a time, with narration,
// captions, the Purplelink bumpers and a Lockerlink call to action. Outputs video/out/chain/<id>/: <id>-<format>.mp4,
// caption.json + caption.txt (title, description, hashtags for the upload), poster, frames, run-log.txt. Nothing is posted.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { ofTheDay, daily, player, load, narration, captionFor } from "./chain-data.mjs";
import { build } from "./src/chain/plan.js";
import { stageNarration, stageBrandAudio } from "./audio.mjs";
import { bumperTotal, BUMPER } from "./src/bumper.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PY = fs.existsSync("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3") ? "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" : "python3";
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes(`--${n}`);
const ff = (a) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...a]);
const mb = (f) => (fs.statSync(f).size / 1e6).toFixed(2);
const slug = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const date = opt("date") ? new Date(`${opt("date")}T12:00:00`) : new Date();
const formats = opt("format", "9x16") === "both" ? ["9x16", "16x9"] : [opt("format", "9x16")];

async function renderOne(chain, serveCache) {
  const A = chain.players[0].name, B = chain.players.at(-1).name;
  const ID = `chain-${chain.sport}-${slug(A)}-to-${slug(B)}-${ymd(chain.day instanceof Date ? chain.day : new Date(chain.day))}`;
  const OUT = path.join(ROOT, "out", "chain", ID);
  fs.mkdirSync(OUT, { recursive: true });
  const log = [];
  const say = (m) => { console.log(m); log.push(m); };
  const t0 = Date.now();
  say(`# ${ID}, ${new Date().toISOString()}`);
  say(`chain: ${chain.players.map((p) => p.name).join(" > ")}  (${chain.hops.map((h) => `${h.team} ${h.seasons}`).join(" | ")})`);

  const lines = narration(chain);
  const sb = { id: ID, series: "chain", title: `${A} to ${B}`, voice: "en-GB-SoniaNeural", rate: "-4%", scenes: lines.map((narration) => ({ narration })) };
  const sbPath = path.join(ROOT, "storyboards", "chain", `${ID}.json`);
  fs.mkdirSync(path.dirname(sbPath), { recursive: true });
  fs.writeFileSync(sbPath, JSON.stringify(sb, null, 2));
  execFileSync(PY, [path.join(ROOT, "narrate.py"), sbPath], { stdio: "inherit" });
  const timing = JSON.parse(fs.readFileSync(path.join(ROOT, ".cache", ID, "timing.json"), "utf8"));
  const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
  const plan = build(chain, timing);
  const bumper = { open: BUMPER.open, close: BUMPER.close, xf: BUMPER.xf };
  const TOTAL = bumperTotal(plan.total, bumper);
  say(`cut ${plan.total.toFixed(2)}s, with bumpers ${TOTAL.toFixed(2)}s`);

  const pub = path.join(ROOT, ".cache", `public-${ID}`);
  fs.rmSync(pub, { recursive: true, force: true });
  for (const d of ["fonts", "brand", "audio"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
  for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
  stageBrandAudio(path.join(ROOT, "assets"), path.join(pub, "brand"));
  for (const f of ["lockerlink.png", "clink.wav"]) fs.copyFileSync(path.join(ROOT, "assets", f), path.join(pub, "brand", f));
  say(`narration -16 LUFS: ${stageNarration(path.join(ROOT, ".cache", ID, "audio"), path.join(pub, "audio", ID)).join(", ")}`);

  let t = Date.now();
  const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
  say(`bundle: ${((Date.now() - t) / 1000).toFixed(1)}s`);
  const stills = opt("stills", "");
  for (const format of formats) {
    t = Date.now();
    const inputProps = { chain, format, timing, bumper };
    const comp = await selectComposition({ serveUrl, id: "ChainDay", inputProps });
    if (stills) {
      const sd = path.join(ROOT, ".cache/stills", ID); fs.mkdirSync(sd, { recursive: true });
      for (const s of stills.split(",")) await renderStill({ composition: comp, serveUrl, output: path.join(sd, `${format}-${Number(s).toFixed(1).padStart(5, "0")}.jpg`), imageFormat: "jpeg", jpegQuality: 85, inputProps, frame: Math.min(comp.durationInFrames - 1, Math.round(Number(s) * brand.fps)) });
      say(`stills -> ${path.relative(ROOT, sd)}`);
      continue;
    }
    const raw = path.join(ROOT, ".cache", `${ID}-${format}-raw.mp4`);
    await renderMedia({ composition: comp, serveUrl, codec: "h264", crf: 18, outputLocation: raw, inputProps, audioCodec: "aac", concurrency: 4 });
    const file = path.join(OUT, `${ID}-${format}.mp4`);
    ff(["-i", raw, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", file]);
    fs.rmSync(raw, { force: true });
    say(`render ${format} (${comp.width}x${comp.height}, ${(comp.durationInFrames / brand.fps).toFixed(2)}s): ${((Date.now() - t) / 1000).toFixed(1)}s, ${mb(file)} MB`);
    const fdir = path.join(OUT, "frames"); fs.mkdirSync(fdir, { recursive: true });
    const P0 = bumper.open - bumper.xf;
    const marks = [P0 + 1.4, P0 + plan.S[1].n + 1.6, P0 + plan.S[Math.min(2, plan.S.length - 2)].n + 1.6, P0 + plan.S.at(-2).n + 1.6, P0 + plan.endAt + 2.4, TOTAL - 1.0];
    for (const m of marks) ff(["-ss", m.toFixed(2), "-i", file, "-frames:v", "1", "-q:v", "3", path.join(fdir, `${format}-${m.toFixed(1).padStart(5, "0")}.jpg`)]);
    if (format === "9x16") ff(["-ss", (P0 + plan.S.at(-2).n + 1.6).toFixed(2), "-i", file, "-frames:v", "1", "-q:v", "2", path.join(OUT, `${ID}-poster.jpg`)]);
  }
  if (!stills) {
    const cap = captionFor(chain);
    fs.writeFileSync(path.join(OUT, "caption.json"), JSON.stringify(cap, null, 2));
    fs.writeFileSync(path.join(OUT, "caption.txt"), `${cap.title}\n\n${cap.text}\n`);
    fs.writeFileSync(path.join(OUT, "run-log.txt"), log.join("\n") + `\ntotal: ${((Date.now() - t0) / 1000).toFixed(1)}s\n`);
  }
  say(`done: ${path.relative(ROOT, OUT)}`);
}

if (flag("daily")) { const y = new Date(date); y.setDate(y.getDate() - 1); await renderOne(await daily(y)); }
else if (opt("player")) await renderOne(await player(opt("player"), opt("to"), opt("sport")));
else if (opt("batch")) {
  const D = await load(opt("batch"));
  const tier = Number(opt("tier", "5"));
  let names = D.players.filter((p) => p.tier >= tier).map((p) => p.n);
  if (opt("limit")) names = names.slice(0, Number(opt("limit")));
  for (const n of names) { try { await renderOne(await player(n, null, opt("batch"))); } catch (e) { console.error(`${n}: ${e.message}`); } }
} else await renderOne(await ofTheDay(date, opt("sport")));
