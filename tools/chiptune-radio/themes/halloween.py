"""A Halloween porch at night: jack-o'-lanterns with flickering faces, a big moon with clouds crossing it, a bare tree, a lit house on the hill,
a black cat on the railing, drifting fog, string lights, a spider on a thread, and now and then a flock of bats or a small friendly ghost.
Spooky and cozy, not scary: minor-mode chiptune, a hollow wind and a few late crickets."""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

import px
from themes import Theme, register, schedule

W, H = px.W, px.H
MOON = (236, 46)
PUMPKINS = [(46, 166, 30, 24, 0), (112, 172, 36, 28, 1), (190, 170, 34, 26, 2), (252, 164, 30, 24, 3), (296, 174, 24, 20, 4)]   # x, base y, width, height, face
FACES = {   # eyes and mouth as polygons relative to the pumpkin centre, in units of (w/2, h/2)
    0: ([[(-.6, -.4), (-.2, -.4), (-.4, -.05)], [(.2, -.4), (.6, -.4), (.4, -.05)]], [[(-.55, .25), (-.3, .45), (-.1, .25), (.1, .45), (.3, .25), (.55, .45), (.55, .6), (-.55, .6)]]),
    1: ([[(-.65, -.3), (-.15, -.45), (-.3, 0)], [(.15, -.45), (.65, -.3), (.3, 0)]], [[(-.6, .2), (0, .5), (.6, .2), (.45, .6), (-.45, .6)]]),
    2: ([[(-.55, -.45), (-.25, -.45), (-.25, -.1), (-.55, -.1)], [(.25, -.45), (.55, -.45), (.55, -.1), (.25, -.1)]], [[(-.5, .15), (.5, .15), (.5, .35), (.25, .6), (-.25, .6), (-.5, .35)]]),
    3: ([[(-.6, -.35), (-.2, -.45), (-.2, -.05), (-.6, -.05)], [(.2, -.45), (.6, -.35), (.6, -.05), (.2, -.05)]], [[(-.4, .25), (-.1, .1), (.2, .25), (.45, .1), (.45, .5), (-.4, .5)]]),
    4: ([[(-.5, -.4), (-.1, -.4), (-.3, 0)], [(.1, -.4), (.5, -.4), (.3, 0)]], [[(-.4, .3), (0, .15), (.4, .3), (.2, .55), (-.2, .55)]]),
}


@register
class Halloween(Theme):
    name = "halloween"
    label = "Halloween Porch"
    thumb_lines = ("HALLOWEEN", "PORCH")
    accent = (255, 148, 44)
    thumb_at = 0.22
    music = {"modes": {"minor": 5, "dorian": 3, "mixolydian": 1}, "eras": ["16bit", "hybrid", "16bit", "synth"], "mood": (0.0, 0.42),
             "sound": {"lead": ["fm_bell", "fm_ep"], "arp": ["pluck", "fm_bell"], "pad": "organ", "bass": "sub_sine", "kit": "lofi"}}
    bed = {"hollow_wind": 0.9, "crickets": 0.25, "room": 1.0}
    bed_solo = {"hollow_wind": 1.0, "crickets": 0.3, "room": 1.0}
    music_bed_level = 0.45

    def __init__(self, seed, seconds, bpm_at=None, options=None):
        super().__init__(seed, seconds, bpm_at, options)
        ev = schedule(seed, seconds, {"bats": (560.0, 22.0), "ghost": (780.0, 30.0), "star": (500.0, 1.4)})
        self.events = ev + [(e[0] + 4, "gust", 14.0) for e in ev if e[1] == "ghost"]
        r = random.Random(seed)
        self.stars = px.star_field(seed + 3, 70, 0, 0, W, 90, bias=1.3)
        self.cloud_spec = [(r.uniform(0, 1), r.randrange(14, 70), r.randrange(40, 90), r.uniform(1.2, 2.6)) for _ in range(5)]
        self.pumpkin_glows = [px.glow_map(x, by - h // 2, 58 + w, 0.7) for x, by, w, h, _ in PUMPKINS]
        self.lantern_glow = px.glow_map(26, 46, 52, 0.9)
        self.window_glow = px.glow_map(124, 104, 30, 0.8)
        self.fg = self._build_fg()
        self.pumpkin_layer = self._build_pumpkins()
        self.bg = self._build_bg()
        self._sky = None

    # ---------------------------------------------------------------- static pieces
    def _branch(self, d, x, y, ang, ln, depth, r):
        if depth == 0 or ln < 3:
            return
        x2, y2 = x + math.cos(ang) * ln, y - math.sin(ang) * ln
        d.line([x, y, x2, y2], fill=(8, 5, 14), width=max(1, depth // 2 + (1 if depth > 5 else 0)))
        for da in (r.uniform(0.3, 0.6), -r.uniform(0.3, 0.6)):
            if r.random() < 0.85:
                self._branch(d, x2, y2, ang + da, ln * r.uniform(0.62, 0.8), depth - 1, r)

    def _build_bg(self) -> Image.Image:
        r = random.Random(self.seed + 21)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        # far hills and a house on the hill
        d.polygon([(0, 116), (40, 100), (92, 108), (150, 92), (214, 104), (270, 96), (320, 108), (320, 140), (0, 140)], fill=(26, 14, 46))
        hx, hy = 102, 94
        d.rectangle([hx, hy, hx + 44, hy + 30], fill=(14, 8, 26))
        d.polygon([(hx - 4, hy), (hx + 22, hy - 16), (hx + 48, hy)], fill=(14, 8, 26))
        d.rectangle([hx + 30, hy - 26, hx + 38, hy], fill=(14, 8, 26))
        d.polygon([(hx + 28, hy - 26), (hx + 34, hy - 36), (hx + 40, hy - 26)], fill=(14, 8, 26))
        d.rectangle([hx + 4, hy + 8, hx + 10, hy + 16], fill=(255, 160, 60))
        d.rectangle([hx + 24, hy + 8, hx + 30, hy + 16], fill=(255, 160, 60))
        d.rectangle([hx + 15, hy + 18, hx + 21, hy + 30], fill=(40, 20, 50))
        # dead trees
        for tx, ty, ang, ln, dep in ((34, 142, 1.5, 34, 8), (284, 138, 1.62, 26, 7), (214, 112, 1.5, 12, 5)):
            self._branch(d, tx, ty, ang, ln, dep, r)
        # a picket fence along the garden, a few boards missing
        d.rectangle([0, 130, W, 132], fill=(12, 7, 22))
        d.rectangle([0, 138, W, 140], fill=(12, 7, 22))
        for x in range(2, W, 7):
            if r.random() < 0.09:
                continue
            top = 122 + r.randrange(-1, 3)
            d.polygon([(x, 142), (x, top + 3), (x + 2, top), (x + 4, top + 3), (x + 4, 142)], fill=(14, 8, 26))
        d.rectangle([0, 141, W, H], fill=(18, 10, 30))
        return im

    def _build_fg(self) -> Image.Image:
        r = random.Random(self.seed + 22)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        # porch floor and the front edge of the porch
        d.rectangle([0, 146, W, H], fill=(58, 36, 40))
        for y in (146, 158, 170):
            d.rectangle([0, y, W, y + 1], fill=(36, 22, 28))
        for x0 in range(0, W, 46):
            for row in range(3):
                d.line([x0 + 20 * row % 46, 147 + row * 12, x0 + 20 * row % 46, 157 + row * 12], fill=(40, 26, 30))
        d.rectangle([0, 144, W, 146], fill=(84, 54, 52))
        # railing: top rail, bottom rail, balusters, and chunky posts at both ends and the middle
        d.rectangle([0, 126, W, 129], fill=(44, 28, 38))
        d.rectangle([0, 127, W, 127], fill=(74, 50, 62))
        d.rectangle([0, 142, W, 144], fill=(38, 24, 34))
        for x in range(8, W, 14):
            d.rectangle([x, 130, x + 2, 142], fill=(40, 26, 36))
        for x in (0, 154, 314):
            d.rectangle([x - 2, 108, x + 5, 146], fill=(34, 22, 32))
            d.rectangle([x - 3, 106, x + 6, 109], fill=(60, 40, 52))
        # a hanging lantern top left with its chain
        d.line([26, 0, 26, 30], fill=(60, 50, 60))
        d.rectangle([20, 30, 32, 33], fill=(40, 34, 44))
        d.rectangle([20, 33, 32, 54], fill=(30, 24, 36))
        d.rectangle([22, 36, 30, 51], fill=(255, 190, 80))
        d.rectangle([20, 54, 32, 57], fill=(40, 34, 44))
        # a cobweb in the top right corner
        webc = (150, 144, 176)
        for k, ang in enumerate((90, 112, 135, 158, 180)):
            d.line([W, 0, W + 62 * math.cos(math.radians(ang)), 62 * math.sin(math.radians(ang))], fill=webc)
        for rad in (14, 28, 44, 60):
            d.arc([W - rad, -rad, W + rad, rad], 90, 180, fill=webc)
        return im

    def _build_pumpkins(self) -> Image.Image:
        """The pumpkin bodies, pasted after the lighting so the candle inside them is not lit twice."""
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for x, by, w, h, face in PUMPKINS:
            cy = by - h // 2
            d.rectangle([x - 2, by - h - 3, x + 2, by - h + 1], fill=(70, 96, 44))
            d.ellipse([x - w // 2, cy - h // 2, x + w // 2, cy + h // 2], fill=(190, 82, 18))
            d.ellipse([x - w // 4, cy - h // 2, x + w // 4, cy + h // 2], fill=(212, 100, 24))
            d.line([x, cy - h // 2, x, cy + h // 2], fill=(160, 66, 16))
            d.line([x - w // 3, cy - h // 3, x - w // 3 + 1, cy + h // 3], fill=(176, 74, 18))
            d.line([x + w // 3, cy - h // 3, x + w // 3 - 1, cy + h // 3], fill=(176, 74, 18))
            d.ellipse([x - w // 2 + 2, by - 2, x + w // 2 - 2, by + 2], fill=(30, 18, 26))
        return im

    def _sky_img(self) -> Image.Image:
        if self._sky is None:
            im = Image.new("RGB", (W, H), (10, 6, 20))
            px.vgradient(im, 0, 60, (12, 6, 34), (36, 16, 70))
            px.vgradient(im, 60, 120, (36, 16, 70), (124, 52, 90))
            self._sky = im
        return self._sky

    # ---------------------------------------------------------------- live pieces
    def _event(self, kind, t):
        for e in self.events:
            if e[1] == kind and e[0] <= t <= e[0] + e[2]:
                return e, t - e[0]
        return None, 0.0

    def _bats(self, d, age, dur, seed):
        r = random.Random(seed)
        f = age / dur
        for k in range(7):
            ph = r.uniform(0, 0.2)
            x = W + 24 - (f * 1.15 + ph - 0.08) * (W + 60)
            y = 22 + r.uniform(0, 44) + 9 * math.sin(age * 1.4 + k * 1.9)
            if not -12 < x < W + 12:
                continue
            flap = int(age * 7 + k) % 3
            wing = (0, -3, 2)[flap]
            col = (6, 3, 12)
            d.rectangle([x - 1, y, x + 1, y + 2], fill=col)
            d.polygon([(x - 1, y), (x - 7, y + wing), (x - 3, y + 2)], fill=col)
            d.polygon([(x + 1, y), (x + 7, y + wing), (x + 3, y + 2)], fill=col)
            d.point((x - 1, y - 1), fill=col)
            d.point((x + 1, y - 1), fill=col)

    def _ghost(self, im, age, dur):
        f = age / dur
        x = -20 + (W + 40) * f
        y = 84 + 6 * math.sin(age * 0.9)
        layer = Image.new("RGBA", (24, 30), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        body = (236, 232, 252, 150)
        d.ellipse([2, 0, 21, 18], fill=body)
        d.rectangle([2, 9, 21, 25], fill=body)
        for i in range(4):
            d.rectangle([2 + i * 5, 25, 6 + i * 5, 25 + (3 if (i + int(age * 3)) % 2 else 1)], fill=body)
        d.rectangle([7, 8, 9, 11], fill=(30, 20, 50, 220))
        d.rectangle([15, 8, 17, 11], fill=(30, 20, 50, 220))
        d.rectangle([10, 14, 14, 15], fill=(30, 20, 50, 200))
        im.paste(layer, (int(x), int(y)), layer)

    def _cat(self, d, t):
        cx, by = 80, 126
        col = (6, 3, 12)
        d.ellipse([cx - 9, by - 20, cx + 9, by + 1], fill=col)
        d.ellipse([cx - 6, by - 30, cx + 6, by - 18], fill=col)
        d.polygon([(cx - 6, by - 27), (cx - 5, by - 34), (cx - 2, by - 29)], fill=col)
        d.polygon([(cx + 6, by - 27), (cx + 5, by - 34), (cx + 2, by - 29)], fill=col)
        sway = int(3 * math.sin(t * 0.8))
        d.line([cx + 8, by - 3, cx + 17 + sway, by - 8, cx + 20 + sway * 2, by - 18], fill=col, width=2)
        blink = (t % 7.0) < 0.2
        for ex in (-3, 3):
            if not blink:
                d.rectangle([cx + ex - 1, by - 25, cx + ex, by - 24], fill=(150, 255, 90))
            else:
                d.point((cx + ex, by - 24), fill=(60, 110, 40))

    # ---------------------------------------------------------------- the frame
    def frame(self, t: float) -> Image.Image:
        t = math.floor(t * self.fps) / self.fps
        p = self.progress(t)
        im = self._sky_img().copy()
        d = ImageDraw.Draw(im)
        px.draw_stars(d, self.stars, t, dim=0.8)
        mx, my = MOON[0] - int(26 * p), MOON[1] + int(6 * p)
        for rad, col in ((34, (46, 24, 80)), (28, (62, 34, 96)), (24, (84, 46, 110))):        # a dithered halo
            for ang in range(0, 360, 3):
                for rr in range(rad - 2, rad):
                    if (ang // 3 + rr) % 2 == 0:
                        d.point((mx + rr * math.cos(math.radians(ang)), my + rr * math.sin(math.radians(ang))), fill=col)
        d.ellipse([mx - 20, my - 20, mx + 20, my + 20], fill=(248, 218, 150))
        d.ellipse([mx - 20, my - 20, mx + 20, my + 20], outline=(255, 232, 176))
        for cx_, cy_, cr in ((-8, -6, 5), (6, 5, 4), (-3, 9, 3), (10, -9, 3)):
            d.ellipse([mx + cx_ - cr, my + cy_ - cr, mx + cx_ + cr, my + cy_ + cr], fill=(226, 190, 130))
        for cxf, cy_, cw, sp in self.cloud_spec:                                                 # clouds drifting across, some over the moon
            x = int((cxf * (W + cw * 2) + t * sp) % (W + cw * 2)) - cw
            d.rectangle([x, cy_, x + cw, cy_ + 4], fill=(40, 22, 70))
            d.rectangle([x + 6, cy_ - 3, x + cw - 10, cy_], fill=(40, 22, 70))
            d.line([x + 2, cy_, x + cw - 3, cy_], fill=(76, 48, 110))
        e, age = self._event("star", t)
        if e:
            rr = random.Random(int(e[0]))
            px.shooting_star(d, age, e[2], rr.uniform(20, 200), rr.uniform(6, 30), rr.uniform(50, 70), rr.uniform(14, 26))
        e, age = self._event("bats", t)
        if e:
            self._bats(d, age, e[2], int(e[0]))
        im.paste(self.bg, (0, 0), self.bg)
        d = ImageDraw.Draw(im)
        im.paste(self.fog_back(t), (0, 0), self.fog_back(t))
        im.paste(self.fg, (0, 0), self.fg)
        ge, gage = self._event("ghost", t)
        if ge:
            self._ghost(im, gage, ge[2])
        d = ImageDraw.Draw(im)
        self._cat(d, t)
        # a spider bobbing on its thread
        sy = 24 + int(10 * (0.5 + 0.5 * math.sin(t * 0.35)))
        d.line([296, 0, 296, sy], fill=(170, 164, 196))
        d.ellipse([293, sy, 299, sy + 5], fill=(14, 8, 20))
        for k in (-1, 1):
            d.line([296, sy + 2, 296 + k * 5, sy - 1], fill=(14, 8, 20))
            d.line([296, sy + 3, 296 + k * 6, sy + 6], fill=(14, 8, 20))
        # candlelight: each pumpkin and the lantern flicker on their own
        glow = np.zeros((H, W), np.float32)
        flick = []
        for i, g in enumerate(self.pumpkin_glows):
            f = 0.8 + 0.2 * math.sin(t * (3.1 + i * 0.7) + i * 2) + 0.08 * math.sin(t * 11 + i)
            flick.append(f)
            glow += g * f
        glow += self.lantern_glow * (0.9 + 0.1 * math.sin(t * 5.3))
        glow += self.window_glow * 0.5
        arr = px.light(np.asarray(im), np.clip(glow, 0, 1.1), (255, 150, 50), 0.9, 1.0)
        im = Image.fromarray(arr, "RGB")
        im.paste(self.pumpkin_layer, (0, 0), self.pumpkin_layer)
        d = ImageDraw.Draw(im)
        # faces go on after the lighting so they stay bright, and flicker between three strengths
        for i, (x, by, w, h, face) in enumerate(PUMPKINS):
            cy = by - h // 2
            lvl = (int(t * 7 + i * 3) + int(flick[i] * 5)) % 5
            fill = (255, 228, 120) if lvl > 0 else (255, 176, 60)
            eyes, mouths = FACES[face]
            for poly in eyes + mouths:
                d.polygon([(x + a * w / 2, cy + b * h / 2) for a, b in poly], fill=fill)
        # string lights: orange and purple bulbs
        for xx in range(4, W, 12):
            yy = 5 + int(4 * math.sin(xx / 24.0))
            on = (int(t * 2) + xx // 12) % 4 != 0
            col = (255, 150, 44) if (xx // 12) % 2 else (170, 100, 240)
            d.point((xx, yy), fill=col if on else tuple(v // 3 for v in col))
            d.point((xx + 1, yy), fill=col if on else tuple(v // 3 for v in col))
            d.point((xx, yy - 1), fill=(34, 24, 40))
        # fog in front
        f2 = self.fog_front(t)
        im.paste(f2, (0, 0), f2)
        return im

    # the fog drifts slowly, so it is rebuilt five times a second and reused between
    def fog_back(self, t):
        return self._fog("back", int(t * 5) / 5.0)

    def fog_front(self, t):
        return self._fog("front", int(t * 5) / 5.0)

    def _fog(self, which, tq):
        cache = self.__dict__.setdefault("_fog_c", {})
        if cache.get(which, (None, None))[0] != tq:
            layer = (px.fog_layer(self.seed + 1, tq, 112, 142, (96, 70, 130), 52, speed=2.2, scale=46) if which == "back"
                     else px.fog_layer(self.seed + 2, tq, 160, 180, (110, 84, 142), 64, speed=-3.4, scale=60))
            cache[which] = (tq, layer)
        return cache[which][1]
