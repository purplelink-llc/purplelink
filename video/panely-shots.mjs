// node panely-shots.mjs [shot ...]   renders the schematic desk stills (2560x1600 PNG, transparent corners) to assets/panely/
// No narration, no audio. Uses the same Remotion bundle approach as build-stills.mjs.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { SHOTS } from "./src/panely/shots.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
const names = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(SHOTS);
const pub = path.join(ROOT, ".cache", "public-panely-shots");
fs.rmSync(pub, { recursive: true, force: true });
fs.mkdirSync(path.join(pub, "fonts"), { recursive: true });
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
const outDir = path.join(ROOT, "assets", "panely");
fs.mkdirSync(outDir, { recursive: true });
for (const n of names) {
  const inputProps = { shot: n };
  const comp = await selectComposition({ serveUrl, id: "PanelyShot", inputProps });
  const out = path.join(outDir, `${n}.png`);
  await renderStill({ composition: comp, serveUrl, output: out, inputProps, imageFormat: "png", scale: 2 });
  console.log("wrote", path.relative(ROOT, out));
}
