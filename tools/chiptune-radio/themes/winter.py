"""A snowed-in cabin on a winter night: a big window onto falling snow and pines, a stone fireplace with stockings and a wreath, a lit tree
with presents, a cat asleep on the rug, a mug steaming on the sill. Now and then a sleigh crosses the sky, a gust stirs the snow, or a log
settles in the fire. Music is original chiptune in major keys with bells and plucks (no carol or existing tune is used); under it, a soft
fireplace crackle and a muffled wind outside."""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

import px
from themes import Theme, register, schedule

W, H = px.W, px.H
WIN = (78, 22, 178, 112)                 # the window: x0, y0, x1, y1
FP = (206, 62, 292, 146)                 # the fireplace surround
FX, FY = 249, 143                        # the fire's base
TREE = (28, 144)                         # the tree: middle x and the floor y
FIRE_CROP = (160, 60)                    # --view fireplace: the top-left of the 160x90 part of the room that is enlarged 2x (hearth in view)


@register
class Winter(Theme):
    name = "winter"
    label = "Winter Cabin"
    thumb_lines = ("WINTER", "CABIN")
    accent = (150, 210, 255)
    thumb_at = 0.3
    music = {"modes": {"major": 5, "lydian": 3, "mixolydian": 2, "dorian": 1}, "eras": ["16bit", "16bit", "hybrid"], "mood": (0.0, 0.42),
             "sound": {"lead": ["fm_bell", "fm_ep"], "arp": ["pluck", "fm_bell"], "pad": "warm_pad", "bass": "sub_sine", "kit": "lofi"}}
    bed = {"fire": 0.8, "muffled_wind": 0.7, "room": 1.0}
    bed_solo = {"fire": 1.0, "muffled_wind": 0.8, "room": 1.0}
    music_bed_level = 0.45

    def __init__(self, seed, seconds, bpm_at=None, options=None):
        super().__init__(seed, seconds, bpm_at, options)
        self.events = schedule(seed, seconds, {"sleigh": (1500.0, 15.0), "star": (480.0, 1.4), "settle": (500.0, 3.0), "gust": (620.0, 10.0)})
        r = random.Random(seed)
        self.stars = px.star_field(seed + 2, 60, WIN[0] + 3, WIN[1] + 3, WIN[2] - 3, WIN[1] + 46, bias=1.2)
        self.baubles = []
        for _ in range(26):
            y = r.randrange(40, 138)
            half = 4 + (y - 30) * 0.2
            self.baubles.append((TREE[0] + int(r.uniform(-half, half) * 0.85), y, r.choice([(240, 70, 70), (255, 214, 100), (110, 170, 255), (255, 150, 220), (150, 255, 170)]), r.uniform(0, 6.3)))
        close = (options or {}).get("view") == "fireplace"
        # the close-up gets a fire that fills the opening (58x58 art pixels); the whole room keeps the small one
        self.fire = px.Fire(52, 52, seed=seed + 4, cooling=0.016) if close else px.Fire(32, 40, seed=seed + 4, cooling=0.02)
        self.fire_glow = px.glow_map(FX, FY - 14, 150, 0.8)
        self.fire_hi = px.glow_map(FX, FY - 8, 56, 0.8)
        self.tree_glow = px.glow_map(TREE[0], 90, 54, 1.0)
        self.interior = self._build_interior()
        self.outside_static = self._build_outside()

    # ---------------------------------------------------------------- the room
    def _build_interior(self) -> Image.Image:
        r = random.Random(self.seed + 8)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W, 146], fill=(70, 44, 38))                       # log-cabin wall: horizontal boards
        for y in range(0, 146, 12):
            d.rectangle([0, y, W, y + 1], fill=(48, 29, 28))
            d.rectangle([0, y + 2, W, y + 2], fill=(88, 58, 48))
            for _ in range(5):
                gx = r.randrange(0, W)
                d.line([gx, y + 5, gx + r.randrange(6, 20), y + 5], fill=(60, 38, 34))
        d.rectangle([0, 146, W, H], fill=(86, 56, 44))                        # floor
        for y in range(146, H, 10):
            d.rectangle([0, y, W, y], fill=(56, 36, 32))
        for x in range(0, W, 38):
            d.line([x, 146, x - 8, H], fill=(60, 38, 34))
        d.rectangle([0, 143, W, 146], fill=(40, 26, 26))                     # skirting
        # the window: frame, crossbars, sill. The glass is cut out so the outside shows through.
        x0, y0, x1, y1 = WIN
        d.rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], fill=(44, 28, 28))
        d.rectangle([x0 - 6, y0 - 6, x1 + 6, y0 - 5], fill=(96, 64, 52))
        im.paste((0, 0, 0, 0), [x0, y0, x1, y1])
        d.rectangle([(x0 + x1) // 2 - 1, y0, (x0 + x1) // 2 + 1, y1], fill=(44, 28, 28))
        d.rectangle([x0, (y0 + y1) // 2 - 1, x1, (y0 + y1) // 2 + 1], fill=(44, 28, 28))
        d.rectangle([x0 - 10, y1 + 6, x1 + 10, y1 + 10], fill=(110, 76, 58))
        d.rectangle([x0 - 10, y1 + 10, x1 + 10, y1 + 11], fill=(54, 34, 32))
        d.rectangle([x0 - 8, y1 + 3, x1 + 8, y1 + 5], fill=(226, 236, 250))      # snow on the sill
        d.rectangle([x0 - 8, y1 + 5, x1 + 8, y1 + 5], fill=(170, 190, 224))
        for k in range(7):                                                      # frost creeping in at the corners
            d.point((x0 + k, y0 + (k * k) % 5), fill=(220, 236, 252))
            d.point((x1 - k, y0 + (k * 3) % 5), fill=(220, 236, 252))
            d.point((x0 + (k * 2) % 6, y1 - k), fill=(200, 224, 248))
        # the fireplace: stone, mantel, hearth, black opening
        fx0, fy0, fx1, fy1 = FP
        d.rectangle([fx0, fy0, fx1, fy1], fill=(104, 92, 104))
        for row, y in enumerate(range(fy0, fy1, 8)):
            for x in range(fx0 + (row % 2) * 6, fx1, 14):
                d.rectangle([x, y, min(x + 12, fx1), y + 6], fill=(r.choice([(116, 104, 116), (96, 84, 96), (124, 110, 120)])))
        d.rectangle([fx0 - 8, fy0 - 6, fx1 + 8, fy0], fill=(110, 74, 56))        # mantel
        d.rectangle([fx0 - 8, fy0 - 6, fx1 + 8, fy0 - 5], fill=(150, 104, 78))
        d.rectangle([fx0 + 14, fy0 + 26, fx1 - 14, fy1], fill=(14, 10, 12))       # the opening
        d.rectangle([fx0 + 12, fy0 + 24, fx1 - 12, fy0 + 27], fill=(70, 62, 72))
        d.rectangle([fx0 - 6, fy1, fx1 + 6, fy1 + 4], fill=(78, 68, 80))          # hearth
        d.rectangle([FX - 17, FY - 4, FX + 5, FY], fill=(60, 38, 28))              # logs
        d.rectangle([FX - 5, FY - 7, FX + 17, FY - 3], fill=(76, 48, 34))
        # stockings hang from the mantel; a wreath above it
        for sx, col in ((fx0 + 6, (186, 40, 52)), (fx0 + 26, (44, 130, 78)), (fx0 + 46, (186, 40, 52)), (fx0 + 66, (44, 130, 78))):
            d.rectangle([sx, fy0, sx + 7, fy0 + 14], fill=col)
            d.rectangle([sx, fy0 + 14, sx + 11, fy0 + 19], fill=col)
            d.rectangle([sx - 1, fy0, sx + 8, fy0 + 3], fill=(240, 240, 244))
        wx, wy = (fx0 + fx1) // 2, 30
        d.ellipse([wx - 15, wy - 15, wx + 15, wy + 15], outline=(40, 120, 70), width=5)
        for k in range(10):
            a = k / 10 * math.tau
            d.point((wx + 14 * math.cos(a), wy + 14 * math.sin(a)), fill=(86, 170, 100))
        for a in (0.6, 2.3, 4.4):
            d.rectangle([wx + 13 * math.cos(a) - 1, wy + 13 * math.sin(a) - 1, wx + 13 * math.cos(a) + 1, wy + 13 * math.sin(a) + 1], fill=(220, 50, 60))
        d.polygon([(wx - 7, wy + 14), (wx, wy + 18), (wx + 7, wy + 14), (wx + 5, wy + 22), (wx - 5, wy + 22)], fill=(200, 40, 54))
        # a braided rug before the fire
        d.ellipse([170, 154, 296, 178], fill=(110, 40, 52))
        d.ellipse([176, 156, 290, 175], fill=(226, 200, 170))
        d.ellipse([184, 158, 282, 172], fill=(70, 100, 90))
        d.ellipse([194, 160, 272, 170], fill=(236, 214, 180))
        # the tree: three green tiers, a trunk, a star, presents
        tx, ty = TREE
        d.rectangle([tx - 3, ty - 6, tx + 3, ty + 2], fill=(84, 54, 40))
        for i, (hw, y0_) in enumerate(((26, 82), (21, 54), (15, 28))):
            d.polygon([(tx, y0_ - 26), (tx - hw, y0_ + 28 if i == 0 else y0_ + 24), (tx + hw, y0_ + 28 if i == 0 else y0_ + 24)], fill=(24, 84, 52))
            d.polygon([(tx, y0_ - 26), (tx - hw // 2, y0_ + 10), (tx + hw // 2, y0_ + 10)], fill=(32, 104, 62))
        d.polygon([(tx - 16, ty + 2), (tx + 16, ty + 2), (tx + 22, ty - 6), (tx - 22, ty - 6)], fill=(150, 40, 48))
        for px_, py_, w_, col, rib in ((tx + 14, ty - 2, 14, (66, 110, 190), (240, 220, 140)), (tx - 26, ty - 1, 12, (236, 200, 90), (200, 60, 70)), (tx + 30, ty, 10, (60, 150, 100), (240, 240, 240))):
            d.rectangle([px_ - w_ // 2, py_ - 9, px_ + w_ // 2, py_ + 3], fill=col)
            d.rectangle([px_ - 1, py_ - 9, px_ + 1, py_ + 3], fill=rib)
        beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(beam).polygon([(x0 + 4, y1 + 12), (x1 - 4, y1 + 12), (x1 + 34, 168), (x0 - 18, 168)], fill=(130, 160, 220, 34))
        im = Image.alpha_composite(im, beam)
        return im

    def _build_outside(self) -> Image.Image:
        """The view through the window without the falling snow: sky, moon, hills, pines, a small lit cabin and drifts."""
        x0, y0, x1, y1 = WIN
        w, h = x1 - x0, y1 - y0
        r = random.Random(self.seed + 9)
        im = Image.new("RGB", (w, h))
        px.vgradient(im, 0, h, (8, 12, 40), (50, 70, 118))
        d = ImageDraw.Draw(im)
        d.ellipse([w - 28, 8, w - 14, 22], fill=(236, 238, 226))                    # the moon
        d.ellipse([w - 24, 6, w - 11, 19], fill=(14, 20, 52))
        d.polygon([(0, h - 30), (24, h - 38), (60, h - 30), (92, h - 40), (w, h - 28), (w, h), (0, h)], fill=(120, 142, 190))      # far snowy hills
        for x in range(2, w, 10):
            px.pine(d, x + r.randrange(-3, 3), h - 26 + r.randrange(-2, 3), r.randrange(18, 30), (20, 40, 60), tiers=4, snow=(190, 210, 236))
        cx, cy = 18, h - 26                                                         # a small cabin in the trees, window lit
        d.rectangle([cx, cy - 10, cx + 16, cy], fill=(34, 24, 30))
        d.polygon([(cx - 2, cy - 10), (cx + 8, cy - 18), (cx + 18, cy - 10)], fill=(214, 226, 246))
        d.rectangle([cx + 5, cy - 7, cx + 10, cy - 3], fill=(255, 200, 90))
        d.polygon([(0, h - 14), (30, h - 20), (70, h - 12), (w, h - 22), (w, h), (0, h)], fill=(214, 226, 248))                      # near drifts
        d.polygon([(0, h - 6), (44, h - 12), (96, h - 5), (w, h - 9), (w, h), (0, h)], fill=(236, 242, 252))
        for k in range(8):
            d.rectangle([r.randrange(0, w - 4), h - r.randrange(3, 16), r.randrange(0, w - 4) + 3, h - 1], fill=(200, 214, 240)) if False else None
        return im

    # ---------------------------------------------------------------- live pieces
    def _event(self, kind, t):
        for e in self.events:
            if e[1] == kind and e[0] <= t <= e[0] + e[2]:
                return e, t - e[0]
        return None, 0.0

    def _outside(self, t: float) -> Image.Image:
        x0, y0, x1, y1 = WIN
        w, h = x1 - x0, y1 - y0
        im = self.outside_static.copy()
        d = ImageDraw.Draw(im)
        px.draw_stars(d, [(sx - x0, sy - y0, ph, sz) for sx, sy, ph, sz in self.stars], t, dim=1.0)
        e, age = self._event("star", t)
        if e:
            rr = random.Random(int(e[0]))
            px.shooting_star(d, age, e[2], rr.uniform(8, w - 30), rr.uniform(6, 22), rr.uniform(30, 50), rr.uniform(10, 22))
        e, age = self._event("sleigh", t)
        if e:
            self._sleigh(d, age, e[2], w)
        # snowfall: lighter and heavier stretches over the hour, a gust on top
        p = self.progress(t)
        base = 0.55 + 0.45 * math.sin(p * math.tau * 1.5 + self.seed)
        ge, gage = self._event("gust", t)
        gust = math.sin(math.pi * gage / ge[2]) ** 2 if ge else 0.0
        far_n, near_n = int(26 + 34 * base + 30 * gust), int(8 + 14 * base + 20 * gust)
        px.snowflakes(d, self.seed + 1, t, (0, 0, w, h), far_n, 12 + 14 * gust, sway=4 + 8 * gust, big_every=10 ** 6)
        px.snowflakes(d, self.seed + 2, t, (0, 0, w, h), near_n, 26 + 22 * gust, sway=7 + 12 * gust, big_every=2)
        return im

    def _sleigh(self, d, age, dur, w):
        f = age / dur
        x = -40 + (w + 80) * f
        y = 30 - 18 * math.sin(math.pi * f) + 2 * math.sin(age * 3)
        col = (10, 8, 22)
        gallop = int(age * 5) % 2
        for k in range(4):                                                        # reindeer in a line
            rx = x + 14 + k * 9
            d.rectangle([rx, y, rx + 5, y + 2], fill=col)
            d.rectangle([rx + 4, y - 2, rx + 7, y + 0], fill=col)
            d.line([rx + 6, y - 2, rx + 8, y - 5], fill=col)
            d.line([rx + 1, y + 3, rx + (0 if gallop else 2), y + 5], fill=col)
            d.line([rx + 4, y + 3, rx + (5 if gallop else 3), y + 5], fill=col)
            d.line([x + 8, y + 1, rx, y + 1], fill=(60, 56, 84))
        d.point((x + 14 + 3 * 9 + 8, y - 1), fill=(255, 70, 70))                    # the lead reindeer's red nose
        d.polygon([(x - 8, y - 2), (x + 8, y - 2), (x + 6, y + 4), (x - 6, y + 4)], fill=col)
        d.polygon([(x - 9, y - 6), (x - 4, y - 2), (x - 9, y - 2)], fill=col)
        d.line([x - 8, y + 6, x + 9, y + 6], fill=col)
        for k in range(6):                                                         # a short glitter trail behind
            d.point((x - 12 - k * 4, y + (k % 3) - 1), fill=(200, 220, 255) if (int(age * 6) + k) % 2 else (120, 150, 210))

    def _log_bed(self, d, t, flick):
        """Close-up only: three logs lying across the foot of the flames, their top edges lit, and embers twinkling between them."""
        for x0, x1, y0, y1 in ((FX - 27, FX - 2, FY - 5, FY - 1), (FX - 4, FX + 25, FY - 6, FY - 2), (FX - 17, FX + 13, FY - 2, FY + 2)):
            d.rectangle([x0, y0, x1, y1], fill=(52, 32, 24))
            d.rectangle([x0, y0, x1, y0], fill=(150, 62, 30))
            d.rectangle([x0, y1, x1, y1], fill=(34, 22, 18))
            d.rectangle([x0, y0, x0 + 1, y1], fill=(96, 52, 34))               # the cut end
        for k in range(30):
            ex, ey = FX - 27 + (k * 7) % 52, FY - 6 + (k * 5) % 8
            glow = 0.5 + 0.5 * math.sin(t * (1.1 + (k % 5) * 0.3) + k * 1.7)
            d.point((ex, ey), fill=(int(190 + 65 * glow * min(1.0, flick)), int(70 + 90 * glow), 30))

    def _cat(self, d, t):
        cx, cy = 196, 164
        breath = 1 if (t % 2.6) < 1.3 else 0
        d.ellipse([cx - 13, cy - 6 - breath, cx + 13, cy + 5], fill=(104, 66, 52))
        d.ellipse([cx - 7, cy - 4 - breath, cx + 9, cy + 4], fill=(138, 92, 68))
        d.ellipse([cx + 7, cy - 6, cx + 17, cy + 4], fill=(104, 66, 52))
        d.polygon([(cx + 8, cy - 5), (cx + 9, cy - 9), (cx + 11, cy - 6)], fill=(104, 66, 52))
        d.polygon([(cx + 14, cy - 5), (cx + 15, cy - 9), (cx + 16, cy - 5)], fill=(104, 66, 52))
        d.line([cx + 10, cy - 1, cx + 14, cy - 1], fill=(40, 26, 26))
        d.arc([cx - 18, cy - 4, cx - 6, cy + 8], 90, 270, fill=(84, 52, 44), width=2)
        zt = (t % 6.0) / 6.0                                                        # a z drifts up and fades
        if zt < 0.8:
            zx, zy = cx + 16 + zt * 8, cy - 12 - zt * 16
            col = tuple(int(v * (1 - zt)) for v in (240, 236, 255))
            d.line([zx, zy, zx + 3, zy], fill=col)
            d.line([zx + 3, zy, zx, zy + 3], fill=col)
            d.line([zx, zy + 3, zx + 3, zy + 3], fill=col)

    # ---------------------------------------------------------------- the frame
    def frame(self, t: float) -> Image.Image:
        """The whole room, or with `--view fireplace` a close-up: the same drawing (so the fire, the glow, the sparks and the tree's lights behave as
        always) cropped to FIRE_CROP and enlarged exactly 2x, so every art pixel is 12x12 in a 1080p frame and the edges stay hard."""
        im = self._room(t)
        if self.options.get("view") == "fireplace":
            x0, y0 = FIRE_CROP
            im = im.crop((x0, y0, x0 + W // 2, y0 + H // 2)).resize((W, H), Image.NEAREST)
        return im

    def _room(self, t: float) -> Image.Image:
        t = math.floor(t * self.fps) / self.fps
        im = Image.new("RGB", (W, H), (16, 10, 14))
        im.paste(self._outside(t), WIN[:2])
        im.paste(self.interior, (0, 0), self.interior)
        d = ImageDraw.Draw(im)
        # the mug on the sill, steaming
        mx, my = 160, 106
        d.rectangle([mx, my, mx + 8, my + 9], fill=(240, 236, 228))
        d.rectangle([mx + 8, my + 2, mx + 10, my + 6], fill=(240, 236, 228))
        d.rectangle([mx + 1, my + 1, mx + 7, my + 2], fill=(110, 66, 50))
        for k in range(4):
            d.point((mx + 4 + int(2 * math.sin(t * 1.6 + k)), my - 2 - k * 3 - int((t * 5 + k * 2) % 3)), fill=(200, 210, 230))
        self._cat(d, t)
        # string lights along the top of the wall and across the window frame
        for xx in range(2, W, 10):
            yy = 6 + int(3 * math.sin(xx / 19.0))
            on = (int(t * 1.5) + xx // 10) % 3
            col = [(255, 214, 130), (255, 130, 110), (130, 190, 255), (160, 240, 170)][(xx // 10) % 4]
            col = col if on else tuple(v // 3 for v in col)
            d.rectangle([xx, yy, xx + 1, yy + 1], fill=col)
        arr0 = np.asarray(im)
        settle, sage = self._event("settle", t)
        level = 0.95 + 0.1 * math.sin(t * 0.17) + (0.5 * math.exp(-sage / 1.2) if settle else 0.0)
        self.fire.advance(int(t * self.fps) * 2, level)
        flick = 0.8 + 0.8 * float(self.fire.heat[-9:].mean())
        arr = px.light(arr0, self.fire_glow, (255, 150, 60), 0.85 * flick, 0.93)
        arr = px.light(arr, self.fire_hi, (255, 190, 100), 0.15 * flick, 1.0)
        arr = px.light(arr, self.tree_glow, (255, 220, 140), 0.12, 1.0)
        x0, y0, x1, y1 = WIN
        arr[y0:y1, x0:x1] = arr0[y0:y1, x0:x1]                                       # the snowy night outside is not lit by the room
        im = Image.fromarray(arr, "RGB")
        fw, fh = self.fire.image().size
        im.paste(self.fire.image(), (FX - fw // 2, FY - fh + 3), self.fire.image())
        d = ImageDraw.Draw(im)
        if self.options.get("view") == "fireplace":
            self._log_bed(d, t, flick)
        px.draw_sparks(d, px.sparks(self.seed, t, FX, FY - 12, spread=6, rate=1.0, life=2.0, rise=18, burst=(settle[0] + 0.2, 18) if settle else None))
        for bx, by, col, ph in self.baubles:                                          # the tree's lights twinkle
            c2 = col if math.sin(t * 1.3 + ph * 3) > -0.3 else tuple(v // 3 for v in col)
            d.rectangle([bx, by, bx + 1, by + 1], fill=c2)
        sx, sy = TREE[0], 28 + 2 * int(math.sin(t * 3))
        d.polygon([(sx, sy - 6), (sx + 2, sy), (sx + 6, sy), (sx + 3, sy + 3), (sx + 4, sy + 7), (sx, sy + 4), (sx - 4, sy + 7), (sx - 3, sy + 3), (sx - 6, sy), (sx - 2, sy)], fill=(255, 230, 120))
        return im
