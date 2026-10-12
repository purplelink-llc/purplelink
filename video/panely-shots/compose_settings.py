#!/usr/bin/env python3
"""Crops the tall offscreen renders of Panely's Settings view into window-sized shots and adds a title bar.
usage: compose_settings.py <renders dir from render.sh> <out dir>
Output 2x PNG (1080 wide), rounded corners transparent, plus web webp copies at 1x/2x width 1080 and 720."""
import sys, os
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
W, CH, TB = 1080, 1280, 56
CORNER = 20

def title_bar(title="Panely Settings"):
    bar = Image.new("RGB", (W, TB), (236, 236, 238))
    d = ImageDraw.Draw(bar)
    for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx = 36 + i * 40
        d.ellipse((cx - 12, TB // 2 - 12, cx + 12, TB // 2 + 12), fill=c)
    try:
        f = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 26)
    except Exception:
        f = ImageFont.load_default()
    tw = d.textlength(title, font=f)
    d.text(((W - tw) / 2, TB // 2 - 15), title, fill=(60, 60, 67), font=f)
    d.line((0, TB - 1, W, TB - 1), fill=(210, 210, 214), width=2)
    return bar

def shot(name, renders, y0, ch=CH, title="Panely Settings"):
    im = Image.open(os.path.join(src, renders + ".png")).convert("RGB").crop((0, y0, W, y0 + ch))
    full = Image.new("RGB", (W, TB + ch), (255, 255, 255))
    full.paste(title_bar(title), (0, 0))
    full.paste(im, (0, TB))
    mask = Image.new("L", full.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, full.size[0] - 1, full.size[1] - 1), CORNER, fill=255)
    rgba = full.convert("RGBA"); rgba.putalpha(mask)
    rgba.save(os.path.join(out, name + ".png"), optimize=True)
    print("wrote", name, rgba.size)

shot("settings-behavior", "full", 0)
shot("settings-shortcuts", "full", 1000)
shot("settings-recorder", "recording", 1500, 840)
shot("settings-recorder-refused", "problem", 1500, 840)
shot("settings-custom-areas", "full", 4410, 800)
