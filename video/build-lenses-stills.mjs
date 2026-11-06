// node build-lenses-stills.mjs [--only hidpi,edges,...]
// Renders the Lenses before/after stills (src/LensesSim.jsx) into site/assets/lenses/: lenses-<name>-before|after|pair
// as PNG (source) and WebP (1600 px wide). All simulated views; each carries the label baked in.
// hidpi: "before" is a half-resolution frame stretched to the panel (what a non-native mode looks like), "after" is
// rendered at the panel's own pixels. Both are real Chrome text rasterisation.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(ROOT, "..");
const OUT = path.join(REPO, "site", "assets", "lenses");
const RAW = path.join(ROOT, ".cache", "lenses-raw");
const PY = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3";
const args = process.argv.slice(2);
const only = (args.indexOf("--only") >= 0 ? args[args.indexOf("--only") + 1] : "").split(",").filter(Boolean);
fs.mkdirSync(OUT, { recursive: true });
fs.rmSync(RAW, { recursive: true, force: true });
fs.mkdirSync(RAW, { recursive: true });

const PAIRS = [
  { name: "hidpi", beforeSub: "Low-resolution mode", afterSub: "Sharp HiDPI mode", zoom: { x: 400, y: 165, s: 2.1 }, note: "Zoomed to the same text in both" },
  { name: "edges", beforeSub: "Soft lens edges", afterSub: "Edge margin at 90%" },
  { name: "night", beforeSub: "Full white", afterSub: "Night tint" },
  { name: "dark", beforeSub: "Light Mac, room hidden", afterSub: "Dark Mode, room visible" },
  { name: "seethrough", beforeSub: "Mac as it ships, room hidden", afterSub: "See-Through Mode, room visible", note: "Room: a real photograph" },
  { name: "pointer", beforeSub: "Standard pointer", afterSub: "Bigger pointer", zoom: { x: 640, y: 340, s: 2.1 }, note: "Zoomed to the same area in both" },
  { name: "hz", beforeSub: "60 Hz", afterSub: "120 Hz", note: "Eye tracking the motion" },
].filter((p) => !only.length || only.includes(p.name));

const pub = path.join(ROOT, ".cache", "public-lenses");
fs.rmSync(pub, { recursive: true, force: true });
for (const d of ["fonts", "img"]) fs.mkdirSync(path.join(pub, d), { recursive: true });
const brand = JSON.parse(fs.readFileSync(path.join(ROOT, "brand.json"), "utf8"));
for (const f of Object.values(brand.fonts)) fs.copyFileSync(path.resolve(ROOT, f.file), path.join(pub, "fonts", path.basename(f.file)));
// the room behind the glasses in the see-through still: Ben's own photograph (DSC_7720), cropped to 16:9
fs.copyFileSync(path.join(ROOT, "assets", "lenses-room.jpg"), path.join(pub, "img", "room.jpg"));

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
const still = async (scene, side, out, scale) => {
  const comp = await selectComposition({ serveUrl, id: "LensesStill", inputProps: { scene, side } });
  await renderStill({ composition: comp, serveUrl, output: out, imageFormat: "png", inputProps: { scene, side }, scale });
};
const py = (code, ...a) => execFileSync(PY, ["-I", "-c", code, ...a], { stdio: "inherit" });

for (const p of PAIRS) {
  for (const side of ["before", "after"]) {
    const png = path.join(OUT, `lenses-${p.name}-${side}.png`);
    if (p.name === "hidpi" && side === "before") {
      const tmp = path.join(RAW, "hidpi-half.png");
      await still("hidpi", "before", tmp, 0.5);
      py("import sys;from PIL import Image;im=Image.open(sys.argv[1]).convert('RGB');im.resize((1600,900),Image.BICUBIC).save(sys.argv[2])", tmp, png);
    } else {
      await still(p.name, side, png, 1);
    }
    fs.copyFileSync(png, path.join(pub, "img", `${p.name}-${side}.png`));
  }
}
// second bundle so the pair compositions can read the stills just rendered
const serve2 = await bundle({ entryPoint: path.join(ROOT, "src", "index.jsx"), publicDir: pub });
for (const p of PAIRS) {
  const props = { before: `img/${p.name}-before.png`, after: `img/${p.name}-after.png`, beforeSub: p.beforeSub, afterSub: p.afterSub, zoom: p.zoom, note: p.note };
  const comp = await selectComposition({ serveUrl: serve2, id: "LensesPair", inputProps: props });
  await renderStill({ composition: comp, serveUrl: serve2, output: path.join(OUT, `lenses-${p.name}-pair.png`), imageFormat: "png", inputProps: props });
}
// magnified crops of the same frames for the video (and the site): the text and the pointer
const ZOOMS = { hidpi: [400, 232, 640, 360], pointer: [640, 340, 640, 360] };
for (const p of PAIRS) {
  const z = ZOOMS[p.name];
  if (!z) continue;
  for (const side of ["before", "after"]) {
    py("import sys;from PIL import Image;x,y,w,h=map(int,sys.argv[3:7]);im=Image.open(sys.argv[1]).convert('RGB').crop((x,y,x+w,y+h)).resize((1600,900),Image.BICUBIC);im.save(sys.argv[2])", path.join(OUT, `lenses-${p.name}-${side}.png`), path.join(OUT, `lenses-${p.name}-zoom-${side}.png`), ...z.map(String));
  }
}
// WebP for the site, 1600 px wide; optimise the PNG sources a little
for (const f of fs.readdirSync(OUT).filter((n) => /^lenses-.*\.png$/.test(n))) {
  const src = path.join(OUT, f);
  py("import sys;from PIL import Image;im=Image.open(sys.argv[1]).convert('RGB');im.save(sys.argv[2],'WEBP',quality=88,method=6);im.save(sys.argv[1],optimize=True)", src, src.replace(/\.png$/, ".webp"));
}
console.log("done", fs.readdirSync(OUT).join(" "));
