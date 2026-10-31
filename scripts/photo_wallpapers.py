#!/usr/bin/env python3
"""Mac wallpapers from Ben's travel photographs: render, pack, upload, count.

The free pack (five photographs, chosen by Ben 2026-10-31) is served by netlify/functions/wallpaper-download.mjs
from the private `wallpaper-files` Blobs store; the page is site/photography/wallpapers/. Two sizes per photograph:

  6k       6016 x 3384  the Pro Display XDR's native size; 16:9, so it also fits 5K, 4K and 1080p screens
  macbook  3456 x 2234  the 16-inch MacBook Pro's native size; the 14-inch Pro and MacBook Air have the same shape

Every crop is the largest box of the target shape inside the original, placed by per-photo anchors, then resized
with Lanczos. Nothing is stretched. Where the box is smaller than the target (three of the 6K crops), the resize is
an upscale of at most about 23% with a light unsharp mask.

  python3 scripts/photo_wallpapers.py render   # JPEGs, zips and README into the workspace, previews into site/
  python3 scripts/photo_wallpapers.py upload   # the JPEGs and zips into the wallpaper-files Blobs store
  python3 scripts/photo_wallpapers.py stats    # downloads so far, per file and per day, from wallpaper-stats

The paid 30-pack is not built; when it is, it gets its own list here and must stay disjoint from the free five.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(os.environ.get("PL_PHOTOS", "/Volumes/Extreme SSD/Nikon Photos"))
WS = Path(os.environ.get("PL_WORKSPACE", ROOT / "photo-licensing-workspace"))
if not WS.is_dir():
    WS = Path("/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace")
OUT = WS / "wallpapers" / "free"
PREVIEWS = ROOT / "site" / "assets" / "photography" / "wallpapers"
SITE_ID = "b264591f-fbbe-4048-9d9d-7051cf497823"  # purplelink
SIZES = {"6k": (6016, 3384), "macbook": (3456, 2234)}
ZIP_LIMIT = 18_000_000  # the function streams from Blobs; Netlify caps a streamed response at 20 MB

# stem, slug, title, (6k anchors x, y), (macbook anchors x, y). Anchors place the crop box: 0 = left/top, 1 = right/bottom.
FREE = [
    ("DSC_8669", "matterhorn-riffelsee", "The Matterhorn in Riffelsee, Switzerland", (0.5, 0.45), (0.5, 0.40)),
    ("DSC_1584", "fjadrargljufur-canyon", "Fjaðrárgljúfur canyon, Iceland", (0.5, 0.55), (0.5, 0.55)),
    ("DSC_4380", "waipio-valley", "Waipio Valley, Hawaii", (0.5, 0.55), (0.5, 0.5)),
    ("DSC_8263", "desert-sunset-peaks", "Sunset between desert peaks, Arizona", (0.5, 0.45), (0.5, 0.45)),
    ("DSC_3638", "hozu-gorge-kyoto", "Mist over the Hozu gorge, Kyoto", (0.5, 0.5), (0.5, 0.5)),
]

README = """Purplelink Mac wallpapers, free pack
Photographs by Benjamin Ampel. https://purplelink.llc/photography/wallpapers/

{lines}

Set one as your wallpaper: open System Settings, choose Wallpaper, then Add Photo (or Add Folder to rotate
through all five) and pick Fill Screen. Or Control-click a file in Finder and choose Set Desktop Picture.

Sizes: 6k files are 6016 x 3384 (Pro Display XDR; the same 16:9 shape as 5K, 4K and 1080p screens).
macbook files are 3456 x 2234 (16-inch MacBook Pro; the same shape as the 14-inch Pro and MacBook Air).

Free for personal use as a wallpaper on your own devices. Please do not resell, redistribute or upload the
files elsewhere; link to the page above instead. For any other use of a photograph, see
https://purplelink.llc/photography/license/ or write to ben@purplelink.llc.
"""


def window(w: int, h: int, ratio: float, ax: float, ay: float) -> tuple[int, int, int, int]:
    """The largest box of the given aspect inside w x h, placed by the anchors. Never stretches."""
    if w / h > ratio:
        cw, ch = round(h * ratio), h
    else:
        cw, ch = w, round(w / ratio)
    x, y = round((w - cw) * ax), round((h - ch) * ay)
    return x, y, x + cw, y + ch


def render() -> None:
    from PIL import Image, ImageFilter

    Image.MAX_IMAGE_PIXELS = None
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    for stem, slug, title, a6k, amb in FREE:
        im = Image.open(SRC / f"{stem}.jpeg")
        icc = im.info.get("icc_profile")
        im = im.convert("RGB")
        for size, (tw, th) in SIZES.items():
            box = window(*im.size, tw / th, *(a6k if size == "6k" else amb))
            out = im.crop(box).resize((tw, th), Image.LANCZOS)
            scale = tw / (box[2] - box[0])
            if scale > 1:
                out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
            quality = 85 if size == "6k" else 88
            path = OUT / f"purplelink-{slug}-{size}.jpg"
            out.save(path, quality=quality, optimize=True, progressive=True, icc_profile=icc)
            print(f"{path.name}: crop {box[2] - box[0]}x{box[3] - box[1]}, scale {scale:.3f}, {path.stat().st_size / 1e6:.1f} MB")
            if size == "6k":
                for w in (1600, 800):
                    p = out.resize((w, round(w * th / tw)), Image.LANCZOS)
                    p.save(PREVIEWS / f"{slug}-{w}.webp", quality=78, method=6)
                if slug == FREE[0][1]:
                    card = out.crop(window(tw, th, 1200 / 630, 0.5, 0.5)).resize((1200, 630), Image.LANCZOS)
                    card.save(PREVIEWS / "og-card.jpg", quality=82, optimize=True, progressive=True)
        subprocess.run(
            ["exiftool", "-q", "-overwrite_original", "-Artist=Benjamin Ampel",
             "-Copyright=(c) Benjamin Ampel, Purplelink LLC. Free for personal use as a wallpaper.",
             f"-ImageDescription={title}", "-XMP-dc:Rights=Free for personal use as a wallpaper. Not for resale.",
             *[str(OUT / f"purplelink-{slug}-{s}.jpg") for s in SIZES]],
            check=True,
        )
    lines = "\n".join(f"  purplelink-{slug}-*.jpg  {title}" for _, slug, title, _, _ in FREE)
    readme = README.format(lines=lines).encode("utf-8")
    for size in SIZES:
        zpath = OUT / f"purplelink-wallpapers-{size}.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:  # JPEGs do not compress further
            folder = f"Purplelink wallpapers ({size})"
            z.writestr(f"{folder}/README.txt", readme)
            for _, slug, _, _, _ in FREE:
                name = f"purplelink-{slug}-{size}.jpg"
                z.write(OUT / name, f"{folder}/{name}")
        zpath.write_bytes(buf.getvalue())
        print(f"{zpath.name}: {zpath.stat().st_size / 1e6:.1f} MB")
        if zpath.stat().st_size > ZIP_LIMIT:
            sys.exit(f"{zpath.name} is over {ZIP_LIMIT / 1e6:.0f} MB; lower the quality for {size}")


def netlify_token() -> str:
    if os.environ.get("NETLIFY_AUTH_TOKEN"):
        return os.environ["NETLIFY_AUTH_TOKEN"]
    cfg = json.loads((Path.home() / "Library/Preferences/netlify/config.json").read_text())
    user = (cfg.get("users") or {}).get(cfg.get("userId")) or next(iter((cfg.get("users") or {}).values()), {})
    token = ((user or {}).get("auth") or {}).get("token")
    if not token:
        sys.exit("No Netlify token: run `netlify login` or set NETLIFY_AUTH_TOKEN.")
    return token


def upload() -> None:
    """Upload with the @netlify/blobs client, which records each file's size as metadata (the function sends it as
    Content-Length). node_modules lives in the main checkout, so it is resolved from there."""
    node_dir = ROOT if (ROOT / "node_modules/@netlify/blobs").is_dir() else Path("/Volumes/Extreme SSD/Purplelink LLC")
    files = sorted(OUT.glob("purplelink-*.jpg")) + sorted(OUT.glob("purplelink-wallpapers-*.zip"))
    if not files:
        sys.exit(f"Nothing in {OUT}; run render first.")
    script = """
const { createRequire } = await import("node:module");
const { readFile } = await import("node:fs/promises");
const path = await import("node:path");
const { getStore } = await import(createRequire(path.join(process.env.PL_NODE_DIR, "package.json")).resolve("@netlify/blobs"));
const store = getStore({ name: "wallpaper-files", siteID: process.env.PL_SITE_ID, token: process.env.PL_TOKEN });
for (const f of JSON.parse(process.env.PL_FILES)) {
  const body = await readFile(f);
  for (let attempt = 1; ; attempt++) {
    try {
      await store.set(path.basename(f), body, { metadata: { size: body.byteLength } });
      break;
    } catch (err) {
      console.log(`retry ${path.basename(f)} after: ${String(err.message || err).slice(0, 120)}`);
      if (attempt === 4) throw err;
      await new Promise((r) => setTimeout(r, 2000 * attempt));
    }
  }
  console.log(`uploaded ${path.basename(f)} (${Math.round(body.byteLength / 1024)} KB)`);
}
"""
    env = dict(os.environ, PL_NODE_DIR=str(node_dir), PL_SITE_ID=SITE_ID, PL_TOKEN=netlify_token(),
               PL_FILES=json.dumps([str(f) for f in files]))
    subprocess.run(["node", "--input-type=module", "-e", script], env=env, check=True)


def stats() -> None:
    """Read wallpaper-stats the way the traffic dashboard reads vitae-stats (blobs_read in traffic_dashboard.py)."""
    base = f"https://api.netlify.com/api/v1/blobs/{SITE_ID}/site:wallpaper-stats"
    hdr = {"Authorization": f"Bearer {netlify_token()}", "User-Agent": "purplelink-wallpaper-stats"}

    def get(url: str) -> bytes:
        with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=20) as r:
            return r.read()

    keys = [b["key"] for b in json.loads(get(base)).get("blobs", [])]
    counts = {k: int(get(f"{base}/{urllib.parse.quote(k, safe=':')}").decode().strip() or 0) for k in sorted(keys)}
    total = sum(v for k, v in counts.items() if k.startswith("downloads:"))
    for k, v in counts.items():
        print(f"{v:6d}  {k}")
    print(f"{total:6d}  total downloads (stop rule: under 50 in the first 30 days means no paid pack)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"render": render, "upload": upload, "stats": stats}.get(cmd, lambda: sys.exit(__doc__))()
