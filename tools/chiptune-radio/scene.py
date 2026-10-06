#!/usr/bin/env python3.12
"""A pixel-art study room, drawn in code: someone working at a desk in front of a window, with a day and night cycle, rain,
a cat, a lamp, steam from a mug and a clock-synced focus timer. Nothing is loaded from disk, so there is nothing to license.

The canvas is 320x180; the stream upscales it by 4 with nearest-neighbour scaling for crisp pixels.

    python3.12 scene.py --out frame.png --hour 22 --rain
"""
from __future__ import annotations

import argparse
import math
import random
import time

from PIL import Image, ImageDraw, ImageFont

W, H = 320, 180
ANIM_FPS = 12                       # the animation steps at this rate, whatever rate the stream runs at
FOCUS, BREAK = 25 * 60, 5 * 60      # the timer follows the wall clock: :00 to :25 focus, :25 to :30 break

C = {
    "wall": (44, 33, 62), "wall2": (52, 39, 72), "wall3": (36, 27, 52), "floor": (52, 36, 50), "floor2": (62, 43, 58),
    "frame": (28, 20, 40), "frame_hi": (74, 56, 96), "desk": (104, 70, 78), "desk_top": (138, 94, 98), "desk_dark": (74, 50, 60),
    "hoodie": (150, 96, 205), "hoodie_dk": (112, 68, 160), "skin": (236, 184, 148), "hair": (34, 26, 40), "phones": (236, 226, 250),
    "mug": (240, 236, 230), "coffee": (92, 56, 44), "lamp": (255, 198, 112), "lamp_hi": (255, 230, 170), "plant": (92, 176, 112),
    "plant_dk": (58, 128, 86), "pot": (186, 108, 92), "cat": (230, 150, 96), "cat_dk": (190, 112, 70), "cat_belly": (250, 224, 190),
    "book1": (186, 70, 100), "book2": (86, 130, 200), "book3": (236, 190, 80), "book4": (110, 190, 150), "paper": (246, 240, 226),
    "laptop": (84, 82, 104), "screen": (150, 232, 214), "ink": (24, 18, 34), "text": (244, 236, 250), "text_dim": (178, 160, 204),
    "panel": (24, 17, 36), "bar": (180, 120, 240), "rain": (170, 200, 240), "star": (255, 246, 214), "moon": (250, 244, 214),
}

SKY_KEYS = [  # hour, top colour, bottom colour
    (0, (14, 12, 38), (30, 24, 66)), (5, (20, 18, 54), (60, 40, 90)), (6.5, (120, 80, 150), (240, 150, 130)),
    (8, (110, 150, 230), (190, 210, 250)), (16, (100, 140, 224), (200, 200, 246)), (18, (160, 100, 170), (250, 150, 110)),
    (19.5, (60, 40, 100), (140, 70, 110)), (21, (22, 18, 54), (44, 32, 84)), (24, (14, 12, 38), (30, 24, 66)),
]


def lerp(a, b, t):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def sky_colors(hour: float):
    for (h0, t0, b0), (h1, t1, b1) in zip(SKY_KEYS, SKY_KEYS[1:]):
        if h0 <= hour <= h1:
            f = (hour - h0) / (h1 - h0)
            return lerp(t0, t1, f), lerp(b0, b1, f)
    return SKY_KEYS[0][1], SKY_KEYS[0][2]


class Scene:
    WIN = (62, 16, 258, 100)        # the window: x0, y0, x1, y1

    def __init__(self, seed: int = 1):
        self.font = ImageFont.load_default()
        r = random.Random(seed)
        self.stars = [(r.randrange(self.WIN[0] + 4, self.WIN[2] - 4), r.randrange(self.WIN[1] + 4, self.WIN[1] + 44), r.random()) for _ in range(46)]
        self.drops = [(r.random(), r.random(), 0.6 + r.random() * 0.8) for _ in range(70)]
        self.towers = []
        x = self.WIN[0] + 2
        while x < self.WIN[2] - 4:
            w, h = r.randrange(10, 22), r.randrange(18, 46)
            self.towers.append((x, w, h, [(r.randrange(2, w - 2), r.randrange(3, h - 2), r.random()) for _ in range(w * h // 26)]))
            x += w + r.randrange(0, 4)
        self.clouds = [(r.random(), r.randrange(self.WIN[1] + 6, self.WIN[1] + 34), r.randrange(14, 30)) for _ in range(4)]
        self.static = self._static()

    # ---------------------------------------------------------------- the parts that never move
    def _static(self) -> Image.Image:
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W, 130], fill=C["wall"])
        for x in range(0, W, 16):                              # a quiet wallpaper stripe
            d.rectangle([x, 0, x + 7, 130], fill=C["wall2"])
        d.rectangle([0, 122, W, H], fill=C["floor"])
        for x in range(0, W, 24):
            d.rectangle([x, 150, x + 11, H], fill=C["floor2"])
        x0, y0, x1, y1 = self.WIN
        d.rectangle([x0 - 5, y0 - 5, x1 + 5, y1 + 5], fill=C["frame"])
        d.rectangle([x0 - 4, y0 - 4, x1 + 4, y0 - 3], fill=C["frame_hi"])
        im.paste((0, 0, 0, 0), [x0, y0, x1, y1])               # the window itself stays transparent for the sky
        d.rectangle([x0 + (x1 - x0) // 3 - 1, y0, x0 + (x1 - x0) // 3, y1], fill=C["frame"])
        d.rectangle([x0 + 2 * (x1 - x0) // 3, y0, x0 + 2 * (x1 - x0) // 3 + 1, y1], fill=C["frame"])
        d.rectangle([x0 - 8, y1 + 5, x1 + 8, y1 + 9], fill=C["desk_top"])            # the sill
        d.rectangle([x0 - 8, y1 + 9, x1 + 8, y1 + 10], fill=C["desk_dark"])
        # shelf on the left with books and a plant
        d.rectangle([6, 54, 52, 57], fill=C["desk_top"])
        for i, (bx, col, bh) in enumerate([(9, "book1", 18), (14, "book2", 22), (19, "book3", 16), (24, "book4", 20), (29, "book1", 14)]):
            d.rectangle([bx, 54 - bh, bx + 3, 53], fill=C[col])
        d.rectangle([40, 44, 49, 53], fill=C["pot"])
        d.rectangle([38, 32, 51, 44], fill=C["plant"])
        d.rectangle([42, 26, 47, 32], fill=C["plant_dk"])
        # a small framed poster, and a second shelf on the right
        d.rectangle([14, 76, 40, 100], fill=C["frame"])
        d.rectangle([16, 78, 38, 98], fill=C["wall3"])
        d.rectangle([19, 82, 25, 94], fill=C["bar"])
        d.rectangle([25, 82, 32, 87], fill=C["bar"])
        d.rectangle([272, 54, 314, 57], fill=C["desk_top"])
        d.rectangle([276, 40, 292, 53], fill=C["frame"])         # a little radio
        d.rectangle([278, 42, 290, 46], fill=C["wall3"])
        d.rectangle([300, 36, 310, 53], fill=C["book2"])
        d.rectangle([296, 42, 299, 53], fill=C["book3"])
        # the desk
        d.rectangle([0, 112, W, 124], fill=C["desk_top"])
        d.rectangle([0, 124, W, 134], fill=C["desk"])
        d.rectangle([0, 134, W, 135], fill=C["desk_dark"])
        d.rectangle([14, 135, 20, H], fill=C["desk_dark"])
        d.rectangle([300, 135, 306, H], fill=C["desk_dark"])
        # books and a notebook with a pencil
        d.rectangle([228, 104, 262, 108], fill=C["book1"])
        d.rectangle([230, 100, 260, 104], fill=C["book3"])
        d.rectangle([232, 96, 258, 100], fill=C["book2"])
        d.rectangle([186, 108, 224, 118], fill=C["paper"])
        d.rectangle([204, 108, 205, 118], fill=C["wall3"])
        d.line([210, 112, 220, 111], fill=C["ink"])
        d.rectangle([34, 98, 42, 112], fill=C["laptop"])        # lamp base and arm
        d.rectangle([37, 80, 38, 98], fill=C["laptop"])
        d.polygon([(28, 80), (50, 80), (46, 70), (32, 70)], fill=C["lamp_hi"])
        d.rectangle([278, 96, 296, 112], fill=C["pot"])         # plant on the desk
        d.rectangle([274, 82, 300, 96], fill=C["plant"])
        d.rectangle([282, 72, 292, 82], fill=C["plant_dk"])
        d.rectangle([90, 100, 130, 112], fill=C["laptop"])      # laptop
        d.rectangle([92, 90, 128, 100], fill=C["panel"])
        return im

    # ---------------------------------------------------------------- the sky and what is moving in it
    def sky(self, hour: float, t: float, rain: bool) -> Image.Image:
        x0, y0, x1, y1 = self.WIN
        w, h = x1 - x0, y1 - y0
        top, bot = sky_colors(hour)
        im = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(im)
        for y in range(h):
            d.line([0, y, w, y], fill=lerp(top, bot, y / (h - 1)))
        night = hour < 5.5 or hour > 19.5
        dusk = 5.5 <= hour < 7 or 18 <= hour <= 19.5
        if night or dusk:
            for sx, sy, ph in self.stars:
                if int(t * 1.5 + ph * 10) % 7:
                    d.point((sx - x0, sy - y0), fill=C["star"])
        mh = (hour - 19) % 24                                        # the moon crosses the sky from evening to morning
        if night:
            mx = int(w * min(1.0, max(0.0, mh / 11)))
            d.ellipse([mx - 7, 12 + int(abs(mx - w / 2) / 5), mx + 7, 26 + int(abs(mx - w / 2) / 5)], fill=C["moon"])
        for cx, cy, cw in self.clouds:
            px = int((cx * (w + 60) + t * 2.2) % (w + 60)) - 30
            col = lerp((255, 255, 255), bot, 0.55 if night else 0.2)
            d.rectangle([px, cy - y0, px + cw, cy - y0 + 5], fill=col)
            d.rectangle([px + 4, cy - y0 - 3, px + cw - 5, cy - y0], fill=col)
        for tx, tw, th, wins in self.towers:
            ax = tx - x0
            d.rectangle([ax, h - th, ax + tw, h], fill=lerp((22, 16, 40), top, 0.25))
            for wx, wy, p in wins:
                if night or dusk:
                    if p > 0.45 and (int(t / 9 + p * 40) % 19):
                        d.point((ax + wx, h - th + wy), fill=(255, 214, 120))
        if rain:
            for dx, dy, sp in self.drops:
                x = int((dx * w + t * 18 * sp) % w)
                y = int((dy * h + t * 120 * sp) % h)
                d.line([x, y, x - 1, y + 3], fill=C["rain"])
        return im

    # ---------------------------------------------------------------- one frame
    def frame(self, t: float, hour: float, rain: bool, bpm: int, title: str, wall: float | None = None) -> Image.Image:
        t = math.floor(t * ANIM_FPS) / ANIM_FPS
        wall = time.time() if wall is None else wall
        sec = wall % (FOCUS + BREAK)
        focus = sec < FOCUS
        left = int((FOCUS - sec) if focus else (FOCUS + BREAK - sec))
        beat = (t * bpm / 60.0) % 1.0
        im = Image.new("RGB", (W, H), C["wall"])
        im.paste(self.sky(hour, t, rain), self.WIN[:2])
        im.paste(self.static, (0, 0), self.static)
        d = ImageDraw.Draw(im)
        night = hour < 6.5 or hour > 18.5

        # the laptop screen: a few lines of text scrolling past while working, a calm blank on a break
        for i in range(5):
            if focus:
                ln = 8 + (int(t * 3 + i * 7) * 13) % 22
                d.line([95, 93 + i * 2, 95 + ln, 93 + i * 2], fill=C["screen"])
            else:
                d.line([104, 95 + i * 2, 118, 95 + i * 2], fill=C["text_dim"]) if i == 2 else None

        # the person, from behind: hoodie, head, hair and headphones; the head nods on the beat
        bob = 1 if beat < 0.18 else 0
        cx = 160
        d.rectangle([cx - 24, 100 + bob, cx + 24, 128], fill=C["hoodie"])
        d.rectangle([cx - 24, 100 + bob, cx - 20, 128], fill=C["hoodie_dk"])
        d.rectangle([cx - 8, 94 + bob, cx + 8, 100 + bob], fill=C["skin"])
        d.ellipse([cx - 13, 70 + bob, cx + 13, 98 + bob], fill=C["hair"])
        d.arc([cx - 15, 70 + bob, cx + 15, 100 + bob], 180, 360, fill=C["phones"], width=2)
        d.rectangle([cx - 16, 84 + bob, cx - 13, 92 + bob], fill=C["phones"])
        d.rectangle([cx + 13, 84 + bob, cx + 16, 92 + bob], fill=C["phones"])
        # the mug sits on the desktop, right of the notebook, and stays there
        mx, my = 228, 110
        # the arm: writing while focusing, resting on the desk on a break
        if focus:
            wx = 190 + int(4 * math.sin(t * 5.0))
            d.line([cx + 22, 108, wx, 114], fill=C["hoodie"], width=5)
            d.rectangle([wx - 1, 112, wx + 2, 115], fill=C["skin"])
            d.line([wx + 2, 113, wx + 6, 110], fill=C["ink"])
        else:
            d.line([cx + 22, 108, 188, 115], fill=C["hoodie"], width=5)
            d.rectangle([186, 113, 189, 116], fill=C["skin"])
        d.rectangle([mx, 121, mx + 10, 121], fill=C["desk_dark"])        # contact shadow, so it reads as resting on the desk
        d.rectangle([mx, my, mx + 9, my + 10], fill=C["mug"])
        d.rectangle([mx + 9, my + 2, mx + 11, my + 7], fill=C["mug"])
        d.rectangle([mx + 1, my + 1, mx + 8, my + 3], fill=C["coffee"])

        # the cat on the sill: asleep, breathing, with an occasional tail flick
        br = 1 if int(t * 1.2) % 2 else 0
        d.ellipse([214, 96 - br, 244, 108], fill=C["cat"])
        d.ellipse([238, 92, 252, 106], fill=C["cat"])
        d.polygon([(239, 92), (242, 86), (245, 92)], fill=C["cat"])
        d.polygon([(246, 92), (249, 86), (252, 92)], fill=C["cat"])
        d.line([241, 99, 244, 99], fill=C["ink"])
        d.line([248, 99, 250, 99], fill=C["ink"])
        flick = 3 if int(t * 0.6) % 5 == 0 else 0
        d.line([214, 104, 208, 100 - flick], fill=C["cat_dk"], width=2)

        # steam from the mug, drawn after the cat so it rises in front of it
        for k in range(4):
            sy = my - 3 - k * 4 - int((t * 6 + k * 3) % 4)
            d.point((mx + 4 + int(2 * math.sin(t * 2 + k)), sy), fill=C["text_dim"])

        # lamp light: a warm cone, a little unsteady, stronger at night
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        a = (70 if night else 34) + int(6 * math.sin(t * 3.1))
        gd.polygon([(30, 80), (52, 80), (94, 126), (-12, 126)], fill=C["lamp"] + (a,))
        im.paste(glow, (0, 0), glow)
        # string lights along the top
        for x in range(4, W, 14):
            y = 4 + int(3 * math.sin(x / 22.0))
            on = int(t * 2 + x / 14) % 3
            d.point((x, y), fill=(255, 210, 120) if on else (150, 110, 70))
            d.point((x + 1, y), fill=(255, 210, 120) if on else (150, 110, 70))
        # radio LEDs bounce on the beat
        for i in range(4):
            lvl = 1 + int(4 * abs(math.sin(beat * math.pi + i * 1.3)))
            d.rectangle([279 + i * 3, 46 - lvl, 280 + i * 3, 46], fill=C["bar"])

        # overlays: the timer, what is playing, and the site
        d.rectangle([4, 141, 94, 162], fill=C["panel"])
        d.rectangle([4, 141, 94, 142], fill=C["bar"])
        label = "FOCUS" if focus else "BREAK"
        d.text((8, 146), f"{label} {left // 60:02d}:{left % 60:02d}", font=self.font, fill=C["text"])
        total = FOCUS if focus else BREAK
        frac = 1 - left / total
        d.rectangle([8, 157, 90, 159], fill=C["wall3"])
        d.rectangle([8, 157, 8 + int(82 * frac), 159], fill=C["bar"] if focus else C["plant"])
        d.rectangle([4, 165, 4 + 6 * (len(title) + 13) + 8, 177], fill=C["panel"])
        d.text((8, 167), f"now playing: {title}", font=self.font, fill=C["text_dim"])
        d.rectangle([226, 165, 316, 177], fill=C["panel"])
        d.text((230, 167), "purplelink.llc", font=self.font, fill=C["text_dim"])
        self._nudge(d, wall)
        return im

    # A polite nudge, not a permanent sticker: 15 s out of every 4 minutes it slides up between the timer and the
    # site name and cycles like, subscribe, share. 1 is a lit pixel in the 7-wide icon.
    NUDGE_EVERY, NUDGE_FOR = 240.0, 15.0
    ICONS = {
        "like": ((220, 70, 90), ["0110110", "1111111", "1111111", "0111110", "0011100", "0001000"]),
        "sub": ((255, 210, 100), ["0001000", "0011100", "0111110", "0111110", "1111111", "0001000"]),
        "share": ((110, 200, 255), ["0001100", "0000110", "1111111", "0000110", "0001100", "0000000"]),
    }
    NUDGES = [("like", "LIKE this stream"), ("sub", "SUBSCRIBE + bell"), ("share", "SHARE w/ a friend")]

    def _nudge(self, d: ImageDraw.ImageDraw, wall: float) -> None:
        cyc = wall % self.NUDGE_EVERY
        if cyc >= self.NUDGE_FOR:
            return
        kind, text = self.NUDGES[min(len(self.NUDGES) - 1, int(cyc // (self.NUDGE_FOR / len(self.NUDGES))))]
        rise = int(max(0.0, 0.6 - cyc) * 50)                       # slides up over the first 0.6 s
        x0, y0 = 102, 143 + rise
        d.rectangle([x0, y0, x0 + 117, y0 + 19], fill=C["panel"])
        d.rectangle([x0, y0, x0 + 117, y0 + 1], fill=C["bar"])
        colour, rows = self.ICONS[kind]
        for ry, row in enumerate(rows):
            for rx, on in enumerate(row):
                if on == "1":
                    d.point((x0 + 7 + rx, y0 + 7 + ry), fill=colour)
        d.text((x0 + 19, y0 + 7), text, font=self.font, fill=C["text"])


def hour_at(t: float, cycle_hours: float = 2.0) -> float:
    """A day lasts `cycle_hours` of real time on the stream, so a viewer sees dusk and dawn happen."""
    return (t / (cycle_hours * 3600.0) * 24.0) % 24.0


def rain_at(t: float, cycle_hours: float = 2.0) -> bool:
    day = int(t / (cycle_hours * 3600.0))
    return (day * 7919 + 3) % 10 < 4


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="frame.png")
    ap.add_argument("--hour", type=float, default=22)
    ap.add_argument("--rain", action="store_true")
    ap.add_argument("--break", dest="brk", action="store_true")
    a = ap.parse_args()
    s = Scene()
    wall = (FOCUS + 60) if a.brk else 600
    s.frame(1.0, a.hour, a.rain, 84, "D major, 80 BPM", wall).resize((W * 4, H * 4), Image.NEAREST).save(a.out)
    print(a.out)
