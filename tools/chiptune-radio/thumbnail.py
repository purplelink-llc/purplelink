"""Make the stream's thumbnail (1280x720) and the website's social-card image (1200x630) from the pixel scene.

    python3.12 thumbnail.py                      # writes thumbnail.png here and ../../site/assets/og/focus-radio.png

The scene is drawn at 320x180, so it scales by an exact integer and every pixel stays a clean square. We render it at
night (lamp on, rain at the window), drop the timer panels, and put a bold two-line title in a band underneath with a
LIVE badge, which is what makes a stream thumbnail read at small sizes. Needs a bold system font to make the image;
the PNG is committed, so the server never runs this.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import scene as sc

HERE = Path(__file__).parent
OG_OUT = HERE.parent.parent / "site" / "assets" / "og" / "focus-radio.png"
BOLD_FONTS = ["/System/Library/Fonts/Supplemental/Arial Black.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
CROP_H = 138                              # the scene above the timer panels
BG, PURPLE, WHITE, RED, GOLD = (25, 20, 29), (170, 120, 255), (255, 255, 255), (232, 52, 60), (255, 210, 120)


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in BOLD_FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("no bold font found; install one or edit BOLD_FONTS")


def fit(d: ImageDraw.ImageDraw, text: str, max_w: int, start: int) -> ImageFont.FreeTypeFont:
    size = start
    while size > 12 and d.textlength(text, font=font(size)) > max_w:
        size -= 2
    return font(size)


def make(w: int, h: int) -> Image.Image:
    s = sc.Scene()
    frame = s.frame(12.0, 21.0, True, 80, "", wall=60.0, events=False).crop((0, 0, sc.W, CROP_H))   # night, rain, mid-focus
    band = round(h * 0.235)
    art_h = h - band
    # scale to fill the width, then crop to the art area; the scene stays centred
    k = w / sc.W
    art = frame.resize((w, round(CROP_H * k)), Image.NEAREST)
    art = art.crop((0, max(0, (art.height - art_h) // 2), w, max(0, (art.height - art_h) // 2) + art_h))
    im = Image.new("RGB", (w, h), BG)
    im.paste(art, (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, art_h, w, h], fill=BG)
    d.rectangle([0, art_h, w, art_h + max(4, h // 90)], fill=PURPLE)
    pad = round(w * 0.035)
    big = fit(d, "24/7 STUDY MUSIC", w - 2 * pad, round(band * 0.46))
    d.text((pad, art_h + round(band * 0.10)), "24/7 STUDY MUSIC", font=big, fill=WHITE)
    small = fit(d, "LOFI CHIPTUNE  ·  POMODORO TIMER 25/5", w - 2 * pad, round(band * 0.24))
    d.text((pad, art_h + round(band * 0.62)), "LOFI CHIPTUNE  ·  POMODORO TIMER 25/5", font=small, fill=GOLD)
    # LIVE badge, top left
    f = font(round(h * 0.055))
    tw = d.textlength("LIVE", font=f)
    bx, by, bh = round(w * 0.025), round(h * 0.04), round(h * 0.095)
    d.rounded_rectangle([bx, by, bx + tw + bh * 1.35, by + bh], radius=round(bh * 0.2), fill=RED)
    d.ellipse([bx + bh * 0.28, by + bh * 0.33, bx + bh * 0.28 + bh * 0.34, by + bh * 0.33 + bh * 0.34], fill=WHITE)
    d.text((bx + bh * 0.8, by + bh * 0.16), "LIVE", font=f, fill=WHITE)
    return im


def main() -> int:
    thumb = make(1280, 720)
    thumb.save(HERE / "thumbnail.png", optimize=True)
    OG_OUT.parent.mkdir(parents=True, exist_ok=True)
    make(1200, 630).save(OG_OUT, optimize=True)
    for p in (HERE / "thumbnail.png", OG_OUT):
        print(f"{p}  {p.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
