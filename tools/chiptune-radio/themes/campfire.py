"""A night forest clearing with a campfire: stars, a moon that crosses the sky, flickering pixel flames and rising embers, fireflies, an owl that
lands now and then, shooting stars, a tent and log seats. The sky goes from dusk to deep night to the first grey of dawn over the length
of the video. Sound: crackle, a low roar, wind in the pines and crickets under soft music (or on their own)."""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

import px
from themes import Theme, register, schedule

W, H = px.W, px.H
FX, FY = 160, 148                        # the middle of the fire's base


@register
class Campfire(Theme):
    name = "campfire"
    label = "Cozy Campfire"
    thumb_lines = ("COZY", "CAMPFIRE")
    accent = (255, 176, 70)
    thumb_at = 0.28
    music = {"modes": {"major": 3, "mixolydian": 3, "dorian": 3, "lydian": 1, "minor": 1}, "eras": ["16bit", "16bit", "hybrid", "16bit", "8bit"],
             "mood": (0.0, 0.4), "sound": {"lead": ["flute", "fm_ep"], "arp": ["pluck", "fm_ep"], "pad": "warm_pad", "bass": "sub_sine", "kit": "lofi"}}
    bed = {"fire": 1.0, "wind": 0.45, "crickets": 0.5, "room": 1.0}
    bed_solo = {"fire": 1.0, "wind": 0.55, "crickets": 0.55, "room": 1.0}
    music_bed_level = 0.5

    def __init__(self, seed, seconds, bpm_at=None, options=None):
        super().__init__(seed, seconds, bpm_at, options)
        self.events = schedule(seed, seconds, {"owl": (1500.0, 46.0), "star": (420.0, 1.4), "settle": (540.0, 3.0), "gust": (700.0, 9.0)})
        r = random.Random(seed)
        self.stars = px.star_field(seed + 1, 150, 0, 0, W, 112, bias=1.5)
        self.milky = [(int(60 + 200 * f + r.gauss(0, 14)), int(8 + 80 * f + r.gauss(0, 9))) for f in (r.random() for _ in range(260))]
        self.flies = [(r.uniform(10, 310), r.uniform(100, 145), r.uniform(0, 6.3), r.uniform(0.15, 0.4), r.uniform(0.3, 0.9)) for _ in range(14)]
        self.fire = px.Fire(28, 36, seed=seed)
        self.glow = px.glow_map(FX, FY - 12, 118, 0.62)
        self.glow_hi = px.glow_map(FX, FY - 8, 46, 0.7)
        self._sky: dict = {}
        self.fg = self._build_fg()
        self.back_stones = [(FX + dx, FY - 6 + dy) for dx, dy in ((-19, 1), (-10, -3), (0, -4), (10, -3), (19, 1))]
        self.front_stones = [(FX + dx, FY + 6 + dy) for dx, dy in ((-22, -3), (-14, 3), (-5, 6), (5, 6), (14, 3), (22, -3))]

    # ---------------------------------------------------------------- sky: dusk, night, then the first grey of dawn
    def sky(self, p: float) -> Image.Image:
        tw = max(0.0, 1.0 - p / 0.12)                     # twilight at the start
        dw = max(0.0, (p - 0.88) / 0.12)                  # dawn at the end
        key = (round(tw * 12), round(dw * 12))
        if key not in self._sky:
            top = px.lerp_color(px.lerp_color((7, 9, 28), (30, 36, 84), tw), (28, 34, 66), dw * 0.8)
            mid = px.lerp_color(px.lerp_color((12, 20, 48), (96, 70, 120), tw), (84, 84, 120), dw)
            bot = px.lerp_color(px.lerp_color((26, 48, 78), (236, 130, 96), tw), (232, 150, 120), dw)
            im = Image.new("RGB", (W, H), (6, 10, 14))
            px.vgradient(im, 0, 64, top, mid)
            px.vgradient(im, 64, 122, mid, bot)
            self._sky[key] = im
        return self._sky[key]

    def _build_fg(self) -> Image.Image:
        """The trees, the ground, the tent and the log seats: everything that never moves, with the sky left transparent."""
        r = random.Random(self.seed + 5)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for x in range(-6, W + 8, 9):                                     # far tree line, hazy
            px.pine(d, x + r.randrange(-3, 3), 122, r.randrange(26, 46), (14, 28, 44), tiers=4)
        d.rectangle([0, 119, W, 124], fill=(14, 28, 44))
        for x in range(-4, W + 10, 14):                                   # nearer trees
            px.pine(d, x + r.randrange(-4, 4), 128, r.randrange(40, 70), (8, 18, 30), tiers=5)
        d.rectangle([0, 126, W, 130], fill=(8, 18, 30))
        # ground: dark grass with a clearing of bare earth around the fire
        d.rectangle([0, 128, W, H], fill=(16, 30, 30))
        for _ in range(420):
            gx, gy = r.randrange(0, W), r.randrange(130, H)
            d.point((gx, gy), fill=r.choice([(22, 40, 36), (12, 24, 26), (28, 48, 40)]))
        d.ellipse([FX - 96, FY - 26, FX + 96, FY + 28], fill=(48, 38, 36))
        d.ellipse([FX - 74, FY - 19, FX + 74, FY + 22], fill=(60, 47, 42))
        for _ in range(160):
            gx, gy = FX + r.randrange(-90, 90), FY + r.randrange(-20, 24)
            if ((gx - FX) / 92) ** 2 + ((gy - FY) / 24) ** 2 < 1:
                d.point((gx, gy), fill=r.choice([(70, 55, 48), (44, 34, 32), (82, 64, 54)]))
        # the tent, left
        d.polygon([(62, 98), (22, 150), (104, 150)], fill=(40, 70, 82))
        d.polygon([(62, 98), (62, 150), (104, 150)], fill=(32, 58, 70))
        d.polygon([(62, 112), (50, 150), (74, 150)], fill=(10, 14, 20))
        d.line([(62, 98), (22, 150)], fill=(68, 106, 118))
        d.line([(62, 98), (104, 150)], fill=(52, 86, 98))
        d.line([(62, 96), (62, 90)], fill=(96, 70, 52))
        # log seats either side, and a stack of firewood by the tent
        for lx, ly, flip in ((92, 166, 1), (232, 164, -1)):
            d.rounded_rectangle([lx, ly, lx + 54, ly + 11], 4, fill=(86, 58, 42))
            d.rectangle([lx + 2, ly + 1, lx + 52, ly + 3], fill=(112, 78, 56))
            d.ellipse([lx - 3 if flip > 0 else lx + 49, ly, lx + 5 if flip > 0 else lx + 57, ly + 11], fill=(150, 112, 80))
        for row, (n, y) in enumerate(((4, 128), (3, 120), (2, 112))):             # a woodpile seen end-on: round log ends in rows
            for k in range(n):
                ox = 249 + (k - (n - 1) / 2) * 9
                d.ellipse([ox - 4, y - 4, ox + 4, y + 4], fill=(70, 46, 34))
                d.ellipse([ox - 3, y - 3, ox + 3, y + 3], fill=(138, 98, 66))
                d.ellipse([ox - 2, y - 2, ox + 2, y + 2], fill=(112, 78, 52))
                d.ellipse([ox - 1, y - 1, ox + 1, y + 1], fill=(150, 108, 74))
        # two big pines at the frame edges: a barky trunk with a flared base, and heavy boughs with layered needles
        bark, bark_dk, bark_hi, needle, needle_hi = (30, 20, 22), (18, 12, 16), (46, 32, 30), (10, 26, 28), (18, 44, 42)
        for bx, side in ((9, 1), (311, -1)):
            d.rectangle([bx - 8, 0, bx + 8, H], fill=bark)
            d.rectangle([bx - 8, 0, bx - 6, H], fill=bark_dk)
            d.rectangle([bx + 6, 0, bx + 8, H], fill=bark_dk)
            for _ in range(70):                                                   # ridges in the bark
                ry, rx = r.randrange(0, H), bx + r.randrange(-6, 6)
                d.line([rx, ry, rx, ry + r.randrange(4, 14)], fill=r.choice([bark_hi, bark_dk]))
            d.polygon([(bx - 8, 150), (bx - 18, H), (bx + 18, H), (bx + 8, 150)], fill=bark)
            for k in range(11):
                y = 4 + k * 15
                reach = 26 + (k % 3) * 8 + (10 - k) * 2
                for tier in range(3):                                             # three overlapping needle masses per bough
                    ex = bx + side * (reach * (0.45 + 0.3 * tier))
                    ey = y + 10 + tier * 3
                    d.polygon([(bx + side * 6, y + tier * 2), (ex, ey), (bx + side * (reach * 0.25 + tier * 4), y + 16 + tier * 3)], fill=needle if tier != 1 else needle_hi)
                    d.line([bx + side * 6, y + tier * 2, ex, ey], fill=needle_hi)
        return im

    # ---------------------------------------------------------------- pieces
    def _event(self, kind: str, t: float):
        for e in self.events:
            if e[1] == kind and e[0] <= t <= e[0] + e[2]:
                return e, t - e[0]
        return None, 0.0

    def _owl(self, d: ImageDraw.ImageDraw, im: Image.Image, age: float, dur: float) -> None:
        """Glides in from the right to a bough, sits blinking and turning its head, then glides out."""
        px_, py_ = 289, 66
        if age < 2.0:
            f = px.sine_ease(age / 2.0)
            x, y = 360 - (360 - px_) * f, py_ - 34 * (1 - f) ** 2
            flap = int(age * 9) % 2
            col = (20, 16, 20)
            d.polygon([(x, y), (x - 11, y - (5 if flap else 1)), (x - 4, y + 3)], fill=col)
            d.polygon([(x, y), (x + 11, y - (5 if flap else 1)), (x + 4, y + 3)], fill=col)
            d.rectangle([x - 3, y - 2, x + 3, y + 6], fill=col)
            return
        if age > dur - 2.0:
            f = px.sine_ease((age - (dur - 2.0)) / 2.0)
            x, y = px_ + (-110) * f, py_ - 22 * f
            flap = int(age * 9) % 2
            d.polygon([(x, y), (x - 11, y - (5 if flap else 1)), (x - 4, y + 3)], fill=(20, 16, 20))
            d.polygon([(x, y), (x + 11, y - (5 if flap else 1)), (x + 4, y + 3)], fill=(20, 16, 20))
            d.rectangle([x - 3, y - 2, x + 3, y + 6], fill=(20, 16, 20))
            return
        d.rectangle([px_ - 14, py_ + 12, px_ + 14, py_ + 14], fill=(34, 24, 20))                  # the bough
        body, belly = (62, 48, 40), (96, 76, 60)
        d.rectangle([px_ - 4, py_ + 1, px_ + 4, py_ + 12], fill=body)
        d.rectangle([px_ - 2, py_ + 5, px_ + 2, py_ + 11], fill=belly)
        d.rectangle([px_ - 5, py_ - 5, px_ + 5, py_ + 2], fill=body)
        d.point((px_ - 5, py_ - 6), fill=body)
        d.point((px_ + 5, py_ - 6), fill=body)
        turn = int(2 * math.sin(age * 0.5))                                                       # a slow look left and right
        blink = (age * 1.0) % 5.0 < 0.25
        for ex in (-2, 2):
            if blink:
                d.point((px_ + ex + turn, py_ - 2), fill=(30, 22, 20))
            else:
                d.point((px_ + ex + turn, py_ - 2), fill=(255, 214, 70))
                d.point((px_ + ex + turn, py_ - 3), fill=(255, 214, 70))

    def _fireflies(self, d: ImageDraw.ImageDraw, t: float) -> None:
        for x, y, ph, sp, dim in self.flies:
            fx = x + 22 * math.sin(t * sp + ph) + 9 * math.sin(t * sp * 2.3 + ph * 2)
            fy = y + 9 * math.sin(t * sp * 1.4 + ph * 1.7)
            on = math.sin(t * (0.7 + dim) + ph * 5) > 0.35
            if on:
                a = 0.6 + 0.4 * math.sin(t * 3 + ph)
                c = (int(190 * a), int(255 * a), int(110 * a))
                d.point((int(fx), int(fy)), fill=c)
                d.point((int(fx) + 1, int(fy)), fill=tuple(int(v * 0.4) for v in c))
                d.point((int(fx) - 1, int(fy)), fill=tuple(int(v * 0.4) for v in c))

    # ---------------------------------------------------------------- the frame
    def frame(self, t: float) -> Image.Image:
        t = math.floor(t * self.fps) / self.fps
        p = self.progress(t)
        im = self.sky(p).copy()
        d = ImageDraw.Draw(im)
        night = 1.0 - 0.75 * max(0.0, 1.0 - p / 0.12) - 0.6 * max(0.0, (p - 0.9) / 0.1)
        px.draw_stars(d, self.stars, t, dim=night, mask=lambda x, y: y < 118, base=im)
        for mx, my in self.milky:                                         # a faint band of far stars, fixed
            d.point((mx, my), fill=tuple(max(a, b) for a, b in zip((int(70 * night), int(78 * night), int(104 * night)), im.getpixel((min(W - 1, max(0, mx)), min(H - 1, max(0, my)))))))
        mf = 0.12 + 0.76 * p                                              # the moon rises on the left and crosses to the right
        cx, cy = int(W * mf), int(70 - 46 * math.sin(math.pi * min(1.0, mf * 1.05)))
        d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(238, 232, 200))
        d.ellipse([cx - 3, cy - 8, cx + 10, cy + 5], fill=self.sky(p).getpixel((min(W - 1, max(0, cx + 3)), max(0, cy - 2))))
        e, age = self._event("star", t)
        if e:
            r = random.Random(int(e[0]))
            px.shooting_star(d, age, e[2], r.uniform(80, 240), r.uniform(8, 40), r.choice([-1, 1]) * r.uniform(50, 80), r.uniform(18, 34))
        im.paste(self.fg, (0, 0), self.fg)
        d = ImageDraw.Draw(im)
        own, oage = self._event("owl", t)
        if own:
            self._owl(d, im, oage, own[2])
        for sx, sy in self.back_stones:
            d.ellipse([sx - 4, sy - 2, sx + 4, sy + 2], fill=(40, 40, 52))
        # logs under the flames
        d.polygon([(FX - 20, FY - 1), (FX - 17, FY - 6), (FX + 8, FY + 2), (FX + 5, FY + 6)], fill=(70, 46, 34))
        d.polygon([(FX + 20, FY - 1), (FX + 17, FY - 6), (FX - 8, FY + 2), (FX - 5, FY + 6)], fill=(82, 54, 38))
        arr = np.asarray(im)
        # the fire itself: heat steps twice per frame; a log settling makes a brighter, taller burst
        settle, sage = self._event("settle", t)
        level = 0.95 + 0.12 * math.sin(t * 0.21) + (0.5 * math.exp(-sage / 1.2) if settle else 0.0)
        self.fire.advance(int(t * self.fps) * 2, level)
        flick = 0.78 + 0.9 * float(self.fire.heat[-10:].mean())
        arr = px.light(arr, self.glow, (255, 150, 60), 0.8 * flick, 1.0)
        arr = px.light(arr, self.glow_hi, (255, 190, 100), 0.18 * flick, 1.0)
        im = Image.fromarray(arr, "RGB")
        im.paste(self.fire.image(), (FX - 14, FY - 34 + 4), self.fire.image())
        d = ImageDraw.Draw(im)
        for i in range(10):                                               # a bed of embers at the foot of the flames
            ex = FX - 16 + (i * 7 + int(t * 3)) % 33
            if (int(t * 4) + i) % 3:
                d.point((ex, FY + 1 + (i % 3)), fill=(255, 140 + 10 * (i % 4), 40))
        px.draw_sparks(d, px.sparks(self.seed, t, FX, FY - 20, spread=9, rate=1.5, life=3.4, rise=24, burst=(settle[0] + 0.2, 26) if settle else None))
        for sx, sy in self.front_stones:
            lit = (120, 100, 92)
            d.ellipse([sx - 4, sy - 3, sx + 4, sy + 3], fill=(66, 62, 74))
            d.line([sx - 3, sy - 2, sx + 1, sy - 2], fill=lit)
        self._fireflies(d, t)
        return im
