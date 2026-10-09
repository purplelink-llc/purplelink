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
from functools import lru_cache

from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

import critters
import pixfont
import seasons

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
    SCREEN = (78, 74, 130, 102)     # the laptop screen, inside its bezel: notifications are drawn here and clipped to it

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
        d.rectangle([73, 104, 135, 112], fill=C["laptop"])      # laptop: base,
        d.rectangle([76, 72, 132, 104], fill=C["laptop"])       # bezel,
        d.rectangle([self.SCREEN[0], self.SCREEN[1], self.SCREEN[2], self.SCREEN[3]], fill=C["panel"])   # and the screen
        d.rectangle([98, 106, 110, 107], fill=C["desk_dark"])   # a trackpad
        return im

    # ---------------------------------------------------------------- the sky and what is moving in it
    def sky(self, hour: float, t: float, rain: bool, ev=None, season: str | None = None) -> Image.Image:
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
        seasons.draw_sky(d, season, t, w, h, hour, rain)
        critters.sky_visitor(im, d, ev, t, w, h, top, bot)
        return im

    # ---------------------------------------------------------------- one frame
    def frame(self, t: float, hour: float, rain: bool, bpm: int, title: str, wall: float | None = None,
              fx: dict | None = None, hud: bool = True, events: bool = True, lights_dy: int = 0, season: str | None = "auto") -> Image.Image:
        """`fx` is optional live engagement: {"toast": (kind, text, age_seconds) or None, "viewers": int or None}. Both are
        drawn ON the laptop screen and clipped to it. `hud=False` leaves out the timer, now-playing and link (frame_hd draws those
        sharply at full size); `events=False` leaves out the cat's morning, the dog and the rest (see critters.py)."""
        t = math.floor(t * ANIM_FPS) / ANIM_FPS
        wall = time.time() if wall is None else wall
        sec = wall % (FOCUS + BREAK)
        focus = sec < FOCUS
        left = int((FOCUS - sec) if focus else (FOCUS + BREAK - sec))
        beat = (t * bpm / 60.0) % 1.0
        im = Image.new("RGB", (W, H), C["wall"])
        ev = critters.active(wall, hour, rain) if events else None
        sn = (seasons.season(wall) if season == "auto" else season) if events else None        # seasonal decor follows the real date
        im.paste(self.sky(hour, t, rain, ev, sn), self.WIN[:2])
        im.paste(self.static, (0, 0), self.static)
        d = ImageDraw.Draw(im)
        night = hour < 6.5 or hour > 18.5
        critters.draw_goldfish(d, t)

        # the laptop screen: a few lines of text scrolling past while working, a calm blank on a break
        sx0, sy0, sx1, sy1 = self.SCREEN
        for i in range(6):
            if focus:
                ln = 8 + (int(t * 3 + i * 7) * 13) % 34
                d.line([sx0 + 3 + (i % 3) * 3, sy0 + 3 + i * 3, sx0 + 3 + (i % 3) * 3 + ln, sy0 + 3 + i * 3], fill=C["screen"])
            elif i in (2, 3):
                d.line([sx0 + 12, sy0 + 4 + i * 3, sx0 + 12 + 26 - i * 4, sy0 + 4 + i * 3], fill=C["text_dim"])
        if fx:
            self._screen_overlay(im, fx)

        # the cat on the sill (on the back wall, so the person walking past is in front of it): asleep and breathing, until its moment to wake, stretch, wash and settle again (critters.py)
        critters.draw_cat(d, t, ev)
        if ev and ev[0] == "bird":
            critters.draw_bird(im, t, ev[1], ev[2], self.WIN)

        # the person, from behind: at the desk with headphones on while focusing; on a break they stretch, get up, walk out, and
        # come back to sit down and put the headphones on again just before the next focus block
        bob = 1 if beat < 0.18 else 0
        cx = 160
        st = self.person_state(None if focus else sec - FOCUS)
        mx, my = 228, 110
        if st["desk_phones"]:                                            # the headphones left on the desk (drawn first, so the person can stand in front of them)
            d.arc([148, 101, 172, 116], 180, 360, fill=C["phones"], width=2)
            d.rectangle([147, 107, 150, 111], fill=C["phones"])
            d.rectangle([170, 107, 173, 111], fill=C["phones"])
        if st["mode"] != "away":
            self._person(im, d, t, st, bob)
        if st["mode"] == "sit":
            if st["arms_up"]:
                sway = int(2 * math.sin(t * 3))
                for sgn in (-1, 1):
                    d.line([cx + sgn * 22, 108, cx + sgn * 31, 82 + sway], fill=C["hoodie"], width=5)
                    d.rectangle([cx + sgn * 31 - 2, 77 + sway, cx + sgn * 31 + 2, 82 + sway], fill=C["skin"])
            elif st["putting_on"] is not None:                           # both hands raise the headphones from the desk to the head
                p = st["putting_on"]
                hx, hy = 160, round(110 - 38 * p) + bob
                for sgn in (-1, 1):
                    d.line([cx + sgn * 22, 108, cx + sgn * (13 + 10 * (1 - p)), hy + 14], fill=C["hoodie"], width=5)
                    d.rectangle([cx + sgn * (13 + 10 * (1 - p)) - 2, hy + 10, cx + sgn * (13 + 10 * (1 - p)) + 2, hy + 14], fill=C["skin"])
                d.arc([hx - 15, hy - 2, hx + 15, hy + 28], 180, 360, fill=C["phones"], width=2)
                d.rectangle([hx - 16, hy + 12, hx - 13, hy + 20], fill=C["phones"])
                d.rectangle([hx + 13, hy + 12, hx + 16, hy + 20], fill=C["phones"])
            elif focus or st["writing"]:
                wx = 190 + int(4 * math.sin(t * 5.0))
                d.line([cx + 22, 108, wx, 114], fill=C["hoodie"], width=5)
                d.rectangle([wx - 1, 112, wx + 2, 115], fill=C["skin"])
                d.line([wx + 2, 113, wx + 6, 110], fill=C["ink"])
            else:
                d.line([cx + 22, 108, 188, 115], fill=C["hoodie"], width=5)
                d.rectangle([186, 113, 189, 116], fill=C["skin"])
        friend = ev if ev and ev[0] == "friend" else None
        if friend:
            critters.draw_friend(im, d, t, friend[1], friend[2])
        if st["mode"] in ("stand", "walk") or (friend and critters.friend_state(friend[1], friend[2])[0] is not None):
            for x0, y0, x1, y1 in ((0, 112, W, H), (272, 70, 302, 112)):       # the desk and its plant stay in front of them; the sill, books and cat are behind
                im.paste(self.static.crop((x0, y0, x1, y1)), (x0, y0), self.static.crop((x0, y0, x1, y1)))
        d.rectangle([mx, 121, mx + 10, 121], fill=C["desk_dark"])        # contact shadow, so it reads as resting on the desk
        d.rectangle([mx, my, mx + 9, my + 10], fill=C["mug"])
        d.rectangle([mx + 9, my + 2, mx + 11, my + 7], fill=C["mug"])
        d.rectangle([mx + 1, my + 1, mx + 8, my + 3], fill=C["coffee"])

        # steam from the mug, drawn after the cat so it rises in front of it
        steamy = bool(friend and critters.friend_state(friend[1], friend[2])[2])
        for k in range(7 if steamy else 4):
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
            y = 4 + lights_dy + int(3 * math.sin(x / 22.0))
            on = int(t * 2 + x / 14) % 3
            col = seasons.light_colours(sn, x // 14, bool(on))
            d.point((x, y), fill=col)
            d.point((x + 1, y), fill=col)
        # radio LEDs bounce on the beat
        for i in range(4):
            lvl = 1 + int(4 * abs(math.sin(beat * math.pi + i * 1.3)))
            d.rectangle([279 + i * 3, 46 - lvl, 280 + i * 3, 46], fill=C["bar"])

        seasons.draw_decor(d, sn, t)
        if ev and ev[0] == "dog":
            critters.draw_dog(im, t, ev[1])
        elif ev and ev[0] == "vacuum":
            critters.draw_vacuum(d, t, ev[1], ev[2])

        if not hud:
            return im
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

    # ---------------------------------------------------------------- the person and their break
    # seconds into the 5 minute break: stretch, stand, walk out, away, walk back in, sit, put the headphones on
    BREAK_STAND, BREAK_OUT, BREAK_AWAY, BREAK_IN, BREAK_SIT, BREAK_PHONES, BREAK_PHONES_END = 6.0, 7.5, 16.0, 282.0, 290.0, 291.5, 298.0
    RISE = 20                                                            # how much taller the standing person's head is

    @classmethod
    def person_state(cls, bt: float | None) -> dict:
        """Where the person is `bt` seconds into a break (None while focusing)."""
        st = {"mode": "sit", "x": 160, "rise": 0, "arms_up": False, "putting_on": None, "phones_on": True, "desk_phones": False,
              "writing": False, "walk": 0.0}
        if bt is None:
            return st
        e = critters._ease
        if bt < cls.BREAK_STAND:
            st["arms_up"] = True
        elif bt < cls.BREAK_OUT:
            st.update(mode="stand", rise=round(cls.RISE * e((bt - cls.BREAK_STAND) / (cls.BREAK_OUT - cls.BREAK_STAND))), phones_on=False,
                      desk_phones=True)
        elif bt < cls.BREAK_AWAY:
            f = (bt - cls.BREAK_OUT) / (cls.BREAK_AWAY - cls.BREAK_OUT)
            st.update(mode="walk", x=round(160 + 190 * f), rise=cls.RISE, phones_on=False, desk_phones=True, walk=bt)
        elif bt < cls.BREAK_IN:
            st.update(mode="away", phones_on=False, desk_phones=True)
        elif bt < cls.BREAK_SIT:
            f = (bt - cls.BREAK_IN) / (cls.BREAK_SIT - cls.BREAK_IN)
            st.update(mode="walk", x=round(350 - 190 * f), rise=cls.RISE, phones_on=False, desk_phones=True, walk=bt)
        elif bt < cls.BREAK_PHONES:
            f = (bt - cls.BREAK_SIT) / (cls.BREAK_PHONES - cls.BREAK_SIT)
            st.update(mode="stand", rise=round(cls.RISE * (1 - e(f))), phones_on=False, desk_phones=True)
            if f >= 1:
                st["mode"] = "sit"
        elif bt < cls.BREAK_PHONES_END:
            p = (bt - cls.BREAK_PHONES) / (cls.BREAK_PHONES_END - cls.BREAK_PHONES)
            lift = e(min(1.0, p / 0.55))                                   # the hands bring them up, then settle them on
            st.update(mode="sit", putting_on=lift if p < 0.62 else None, phones_on=p >= 0.62, desk_phones=p < 0.02, writing=p >= 0.62)
        else:
            st.update(writing=False)
        if st["mode"] == "stand" and st["rise"] == 0:
            st["mode"] = "sit"
        return st

    def _person(self, im: Image.Image, d: ImageDraw.ImageDraw, t: float, st: dict, bob: int) -> None:
        cx, r = st["x"], st["rise"]
        step = math.sin(st["walk"] * 7.0) if st["mode"] == "walk" else 0.0
        bob = int(abs(step) * 2) if st["mode"] == "walk" else bob
        top = 100 + bob - r
        d.rectangle([cx - 24, top, cx + 24, 128], fill=C["hoodie"])
        d.rectangle([cx - 24, top, cx - 20, 128], fill=C["hoodie_dk"])
        d.rectangle([cx - 8, top - 6, cx + 8, top], fill=C["skin"])
        d.ellipse([cx - 13, top - 30, cx + 13, top - 2], fill=C["hair"])
        if st["phones_on"]:
            d.arc([cx - 15, top - 30, cx + 15, top], 180, 360, fill=C["phones"], width=2)
            d.rectangle([cx - 16, top - 16, cx - 13, top - 8], fill=C["phones"])
            d.rectangle([cx + 13, top - 16, cx + 16, top - 8], fill=C["phones"])
        if st["mode"] in ("stand", "walk"):                                # arms hanging at the sides, swinging as they walk
            for sgn in (-1, 1):
                sw = round(sgn * step * 4)
                d.line([cx + sgn * 25, top + 6, cx + sgn * 27, top + 24 + sw], fill=C["hoodie"], width=5)
                d.rectangle([cx + sgn * 27 - 2, top + 24 + sw, cx + sgn * 27 + 2, top + 28 + sw], fill=C["skin"])

    # ---------------------------------------------------------------- the full-size frame: the art, then sharp text on top
    HD_SCALE = 6                                        # 320x180 -> 1920x1080, every art pixel an exact 6x6 square
    # the world clocks along the top: label, IANA zone, and a UTC offset for the odd machine with no zone database
    CLOCKS = [("LA", "America/Los_Angeles", -8), ("NYC", "America/New_York", -5), ("LON", "Europe/London", 0),
              ("DEL", "Asia/Kolkata", 5.5), ("TYO", "Asia/Tokyo", 9), ("SYD", "Australia/Sydney", 10)]
    SUN = ["0001000", "1001001", "0011100", "0111110", "0011100", "1001001", "0001000"]
    MOON = ["0011100", "0111000", "1110000", "1110000", "1110000", "0111100", "0011110"]

    @staticmethod
    @lru_cache(maxsize=4)
    def _zone(name: str):
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name)
        except Exception:                                # no tzdata installed: the caller falls back to a fixed offset
            return None

    def world_clocks(self, wall: float) -> list[tuple[str, str, bool]]:
        """[(label, "HH:MM", is_daytime)] for each city, from the real clock. A fixed offset stands in if the zone is unknown."""
        out = []
        for label, zone, off in self.CLOCKS:
            tz = self._zone(zone)
            now = datetime.fromtimestamp(wall, tz) if tz else datetime.fromtimestamp(wall, timezone.utc) + timedelta(hours=off)
            out.append((label, now.strftime("%H:%M"), 6 <= now.hour < 19))
        return out

    def frame_hd(self, t: float, hour: float, rain: bool, bpm: int, title: str, wall: float | None = None,
                 fx: dict | None = None, season: str | None = "auto") -> Image.Image:
        """The whole frame at 1920x1080: the pixel scene enlarged exactly 6x, with the clocks, timer, now-playing, link and
        like/subscribe nudge drawn at full size in a pixel font so they stay sharp and readable on a phone."""
        wall = time.time() if wall is None else wall
        k = self.HD_SCALE
        art = self.frame(t, hour, rain, bpm, title, wall, fx, hud=False, lights_dy=10, season=season)
        im = art.resize((W * k, H * k), Image.NEAREST)
        d = ImageDraw.Draw(im)
        panel, bar, text, dim = C["panel"], C["bar"], C["text"], C["text_dim"]

        # world clocks along the top: city, time, and a sun or moon for whether it is day there
        d.rectangle([0, 0, W * k, 60], fill=panel)
        d.rectangle([0, 60, W * k, 63], fill=bar)
        cell = W * k // len(self.CLOCKS)
        for i, (label, hhmm, day) in enumerate(self.world_clocks(wall)):
            x = i * cell
            if i:
                d.rectangle([x - 1, 8, x, 52], fill=C["wall3"])
            pixfont.draw(im, x + 18, 22, label, 3, dim)
            tx = x + 18 + pixfont.width(label, 3) + 14
            pixfont.draw(im, tx, 12, hhmm, 5, text if day else dim)
            icon, col = (self.SUN, (255, 214, 110)) if day else (self.MOON, (214, 206, 250))
            ix = tx + pixfont.width(hhmm, 5) + 14
            for ry, row in enumerate(icon):
                for rx, on in enumerate(row):
                    if on == "1":
                        d.rectangle([ix + rx * 4, 17 + ry * 4, ix + rx * 4 + 3, 17 + ry * 4 + 3], fill=col)

        # the Pomodoro timer
        sec = wall % (FOCUS + BREAK)
        focus = sec < FOCUS
        left = int((FOCUS - sec) if focus else (FOCUS + BREAK - sec))
        total = FOCUS if focus else BREAK
        colour = bar if focus else C["plant"]
        d.rectangle([24, 796, 24 + 560, 970], fill=panel)
        d.rectangle([24, 796, 24 + 560, 802], fill=colour)
        pixfont.draw(im, 48, 820, "FOCUS" if focus else "BREAK", 5, colour)
        pixfont.draw(im, 48, 868, f"{left // 60:02d}:{left % 60:02d}", 9, text)
        d.rectangle([48, 942, 48 + 512, 954], fill=C["wall3"])
        d.rectangle([48, 942, 48 + int(512 * (1 - left / total)), 954], fill=colour)

        # what is playing, and the site
        np_text = f"NOW PLAYING: {title}"
        w = pixfont.width(np_text, 4)
        d.rectangle([24, 984, 24 + w + 48, 1054], fill=panel)
        pixfont.draw(im, 48, 1005, np_text, 4, dim)
        link = "PURPLELINK.LLC"
        lw = pixfont.width(link, 5)
        d.rectangle([W * k - 24 - lw - 48, 984, W * k - 24, 1054], fill=panel)
        pixfont.draw(im, W * k - 24 - lw - 24, 1001, link, 5, text)

        # a polite nudge, not a permanent sticker (see NUDGE_EVERY): like, subscribe, share, 15 s every 4 minutes
        cyc = wall % self.NUDGE_EVERY
        if cyc < self.NUDGE_FOR:
            kind, label = self.NUDGES[min(len(self.NUDGES) - 1, int(cyc // (self.NUDGE_FOR / len(self.NUDGES))))]
            tw = pixfont.width(label, 5)
            bw = tw + 48 + 66
            x0, y0 = (W * k - bw) // 2, 896 + int(max(0.0, 0.6 - cyc) * 300)
            d.rectangle([x0, y0, x0 + bw, y0 + 76], fill=panel)
            d.rectangle([x0, y0, x0 + bw, y0 + 6], fill=bar)
            icon_col, rows = self.ICONS[kind]
            for ry, row in enumerate(rows):
                for rx, on in enumerate(row):
                    if on == "1":
                        d.rectangle([x0 + 24 + rx * 6, y0 + 22 + ry * 6, x0 + 24 + rx * 6 + 5, y0 + 22 + ry * 6 + 5], fill=icon_col)
            pixfont.draw(im, x0 + 24 + 66, y0 + 26, label, 5, text)

        # the Pomodoro tally on a wall plaque: one tomato for every focus block finished today
        done = self.pomodoros_today(wall)
        pw, ph = 296, 112
        px, py = W * k - 24 - pw, 130
        d.rectangle([px - 6, py - 6, px + pw + 6, py + ph + 6], fill=C["desk_dark"])
        d.rectangle([px, py, px + pw, py + ph], fill=panel)
        pixfont.draw(im, px + 14, py + 12, "POMODOROS", 3, dim)
        n_txt = f"{done}"
        pixfont.draw(im, px + pw - 14 - pixfont.width(n_txt, 5), py + 8, n_txt, 5, text)
        for i in range(min(done, 24)):
            tx, ty = px + 14 + (i % 12) * 23, py + 50 + (i // 12) * 28
            for ry, row in enumerate(self.TOMATO):
                for rx, ch in enumerate(row):
                    if ch != ".":
                        d.rectangle([tx + rx * 3, ty + ry * 3, tx + rx * 3 + 2, ty + ry * 3 + 2], fill=self.TOMATO_COLOURS[ch])
        if done == 0:
            pixfont.draw(im, px + 14, py + 56, "FIRST ONE SOON", 3, dim)

        # the subscriber goal, bottom right above the link, with a burst of confetti when the count goes up
        subs = (fx or {}).get("subs")
        if subs is not None:
            goal = next((g for g in self.GOALS if g > subs), self.GOALS[-1])
            label = f"SUBS {subs:,} / {goal:,}"
            lw = pixfont.width(label, 4)
            gx, gy = W * k - 24 - (lw + 48), 892
            d.rectangle([gx, gy, W * k - 24, gy + 78], fill=panel)
            d.rectangle([gx, gy, W * k - 24, gy + 5], fill=C["plant"])
            pixfont.draw(im, gx + 24, gy + 16, label, 4, text)
            d.rectangle([gx + 24, gy + 54, W * k - 48, gy + 64], fill=C["wall3"])
            d.rectangle([gx + 24, gy + 54, gx + 24 + int((lw) * min(1.0, subs / goal)), gy + 64], fill=C["plant"])
        toast = (fx or {}).get("toast")
        if toast and toast[0] == "sub" and toast[2] < 4.5:
            self._confetti(im, toast[2])
        return im

    GOALS = [50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000]
    TOMATO = ["..gg...", ".rrrrr.", "rrrrrrr", "rrrrrrr", "rrrrrrr", ".rrrrr.", "..rrr.."]
    TOMATO_COLOURS = {"g": (92, 176, 112), "r": (224, 72, 72)}

    @staticmethod
    def pomodoros_today(wall: float) -> int:
        """Focus blocks finished since local midnight: each ends 25 minutes into a half hour, on the same clock as the timer."""
        mid = seasons.local(wall).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        first = math.ceil((mid - FOCUS) / (FOCUS + BREAK))
        last = math.floor((wall - FOCUS) / (FOCUS + BREAK))
        return max(0, last - first + 1)

    @staticmethod
    def _confetti(im: Image.Image, age: float) -> None:
        """A burst of paper squares falling from the top of the picture for a few seconds; the same every time."""
        d = ImageDraw.Draw(im)
        rr = random.Random(11)
        for _ in range(90):
            x0, vx, vy, size = rr.uniform(0.1, 0.9) * 1920, rr.uniform(-60, 60), rr.uniform(160, 420), rr.choice((8, 10, 12))
            col = rr.choice([(255, 120, 120), (255, 226, 130), (130, 200, 255), (190, 140, 255), (140, 255, 190)])
            y = 70 + vy * age - 25 * age * age * -1
            x = x0 + vx * age + 20 * math.sin(age * 5 + x0)
            if y < 1080 and age < 4.5:
                d.rectangle([int(x), int(y), int(x) + size, int(y) + size], fill=col)

    # ------------------------------------------------------------ notifications, drawn on the laptop's own screen
    TOAST_SECONDS, TOAST_SLIDE = 5.5, 0.35
    TINY = {   # a 3x5 pixel font: the screen is 52 px wide, so the 6 px-wide default font would fit only eight characters
        "A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110", "E": "111100110100111",
        "F": "111100110100100", "G": "011100101101011", "H": "101101111101101", "I": "111010010010111", "J": "001001001101010",
        "K": "101101110101101", "L": "100100100100111", "M": "101111111101101", "N": "110101101101101", "O": "010101101101010",
        "P": "110101110100100", "Q": "010101101111011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
        "U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101", "Y": "101101010010010",
        "Z": "111001010100111", "0": "111101101101111", "1": "010110010010111", "2": "110001010100111", "3": "110001010001110",
        "4": "101101111001001", "5": "111100110001110", "6": "011100111101111", "7": "111001010100100", "8": "111101111101111",
        "9": "111101111001110", "+": "000010111010000", "!": "010010010000010", " ": "000000000000000", ":": "000010000010000",
        ".": "000000000000010", "-": "000000111000000",
    }

    @classmethod
    def tiny_width(cls, text: str) -> int:
        return 4 * len(text) - 1

    @classmethod
    def draw_tiny(cls, d: ImageDraw.ImageDraw, x: int, y: int, text: str, fill) -> None:
        for n, ch in enumerate(text.upper()):
            bits = cls.TINY.get(ch, cls.TINY[" "])
            for i, b in enumerate(bits):
                if b == "1":
                    d.point((x + 4 * n + i % 3, y + i // 3), fill=fill)

    def _screen_overlay(self, im: Image.Image, fx: dict) -> None:
        """A macOS-style banner that slides down from the top of the laptop screen, plus a viewer count on its status line.
        Everything is drawn on a screen-sized layer and pasted back, so nothing can spill outside the screen."""
        sx0, sy0, sx1, sy1 = self.SCREEN
        w, h = sx1 - sx0, sy1 - sy0
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        viewers = fx.get("viewers")
        if viewers:
            d.rectangle([0, h - 8, w, h], fill=C["panel"])
            d.rectangle([3, h - 5, 4, h - 4], fill=(120, 230, 150))                 # a small "online" dot
            self.draw_tiny(d, 7, h - 6, f"{viewers} HERE", C["text_dim"])
        toast = fx.get("toast")
        if toast:
            kind, text, age = toast
            slide = min(1.0, age / self.TOAST_SLIDE, max(0.0, (self.TOAST_SECONDS - age) / self.TOAST_SLIDE))
            top = round(-15 + 17 * slide)                                            # from just above the screen to 2 px below its top
            bw = w - 4
            d.rectangle([2, top, 2 + bw, top + 13], fill=C["text"])
            d.rectangle([2, top, 2 + bw, top + 1], fill=C["bar"])
            colour, rows = self.ICONS.get(kind, self.ICONS["like"])
            for ry, row in enumerate(rows):
                for rx, on in enumerate(row):
                    if on == "1":
                        d.point((5 + rx, top + 4 + ry), fill=colour)
            self.draw_tiny(d, 14, top + 5, text, C["ink"])
        im.paste(layer, (sx0, sy0), layer)

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
