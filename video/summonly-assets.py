#!/usr/bin/env python3
"""Summonly screenshots: PNG sources for the promo, and web copies for the product page.

  1. Render the app's own views offscreen (invented files, throwaway home folder, nothing on screen):
       DEVELOPER_DIR=... bash "/Volumes/Extreme SSD/Summonly/scripts/live/run-shots.sh" /tmp/summonly-shots
  2. python3 summonly-assets.py /tmp/summonly-shots

Writes video/assets/summonly/*.png (2x, panels transparent, windows opaque, dialog given its window fill) and, when
../site/summonly/img exists, the web-sized webp copies the product page uses.
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

SRC = Path(sys.argv[1])
HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets" / "summonly"
IMG = HERE.parent / "site" / "summonly" / "img"
ASSETS.mkdir(parents=True, exist_ok=True)

DIALOG_FILL = {"light": (236, 235, 240), "dark": (40, 38, 46)}


def rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius, fill=255)
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def dialog(im, look):
    base = Image.new("RGBA", im.size, DIALOG_FILL[look] + (255,))
    base.alpha_composite(im.convert("RGBA"))
    return rounded(base, 44)


def backdrop(size, look):
    w, h = size
    top, bot = ((38, 27, 63), (69, 35, 94)) if look == "dark" else ((243, 239, 251), (221, 212, 243))
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        g.putpixel((0, y), tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((w, h)).convert("RGBA")


def on_backdrop(im, look, size=(1600, 900)):
    """Centre an image on the purple stage the existing page image uses, with a soft shadow."""
    bg = backdrop(size, look)
    x, y = (size[0] - im.width) // 2, (size[1] - im.height) // 2
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 150 if look == "dark" else 70))
    sh.putalpha(im.getchannel("A").point(lambda a: a * 150 // 255 if look == "dark" else a * 70 // 255))
    shadow.alpha_composite(sh, (x, y + 24))
    bg.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28)))
    bg.alpha_composite(im, (x, y))
    return bg.convert("RGB")


names = sorted(p.stem for p in SRC.glob("*.png"))
for n in names:
    im = Image.open(SRC / f"{n}.png").convert("RGBA")
    look = "dark" if n.endswith("-dark") else "light"
    if n.startswith("why-not-found"):
        im = dialog(im, look)
    im.save(ASSETS / f"{n}.png", optimize=True)
    print("asset", n, im.size)

if IMG.exists():
    def web(name, im, **kw):
        im.save(IMG / f"{name}.webp", "WEBP", quality=88, method=6, **kw)
        print("web", name, (IMG / f"{name}.webp").stat().st_size // 1024, "KB")

    for n in ("panel-question", "panel-clipboard", "panel-operators"):
        web(n, on_backdrop(Image.open(ASSETS / f"{n}-dark.png"), "dark"))
    for n in ("settings", "setup"):
        web(n, Image.open(ASSETS / f"{n}-dark.png").convert("RGB"))
    web("why-not-found", Image.open(ASSETS / "why-not-found-dark.png"), lossless=True)
