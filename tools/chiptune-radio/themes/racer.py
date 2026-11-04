"""A neon hover-racer on an endless night highway: a gradient sky with stars and a banded planet, a city skyline with lit windows, and a
perspective road (each screen row is one depth, the old "Mode 7" trick) with rumble strips, centre dashes, guard-rail lights and a glowing grid
on the ground. The player's craft hovers at the bottom with a flickering thruster and leans into the curves. Now and then it boosts (the road
rushes, speed lines streak past), a rival craft overtakes, or a shooting star crosses the sky. Music is original 16-bit racing chiptune at a
running tempo (no existing game's music, vehicles or tracks are used)."""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

import px
from themes import Theme, register, schedule

W, H = px.W, px.H
HOR = 92                         # the horizon row
ROWS = H - HOR                   # rows of ground below it
K = 300.0                        # depth of row p is K / p (p = 1 at the horizon, ROWS at the bottom)
SPEED = 24.0                     # world units a second at cruise; a stripe is STRIPE long, so about six stripes a second pass
STRIPE = 4.0
ROAD = 120.0                     # half the road's width in world units (the screen-bottom row is 1:1 with pixels at scale 1)
RUMBLE = 12.0
GRID = 40.0
BOOST = 0.9                      # how much faster a boost is, at its peak
FAR_FADE = 14                    # rows nearer the horizon than this blend their stripes to one colour (they would only shimmer)


def _curve(t: float) -> float:
    """How far the road bends, -1 to 1: two slow waves, so the bends never repeat in an obvious rhythm."""
    return 0.65 * math.sin(2 * math.pi * t / 41.0) + 0.35 * math.sin(2 * math.pi * t / 17.3 + 1.1)


@register
class Racer(Theme):
    name = "racer"
    label = "Night Racer"
    thumb_lines = ("MUSIC TO", "RUN TO")
    accent = (90, 240, 255)
    fps = 30
    thumb_at = 0.42
    music = {"style": "racer", "modes": {"minor": 4, "dorian": 3, "mixolydian": 2}, "eras": ["synth", "16bit", "synth"], "mood": (0.4, 1.0),
             "sound": {"lead": ["fm_brass", "saw_lead"], "arp": ["saw_pluck", "pluck"], "pad": "strings", "bass": "fm_bass", "kit": "electro"}}
    bed = {"wind": 0.35}
    bed_solo = {"wind": 1.0}
    music_bed_level = 0.18
    bg_loop = "racer-highway-v1"   # the Blender skyway (blender/racer_highway.py); AMBIENT_BG=code draws the old road instead

    def __init__(self, seed, seconds, bpm_at=None, options=None):
        super().__init__(seed, seconds, bpm_at, options)
        self.events = schedule(seed, seconds, {"boost": (95.0, 6.0), "rival": (160.0, 7.0), "star": (300.0, 1.4)}, min_gap=12.0)
        self._snapped: dict = {}
        self.boosts = [e for e in self.events if e[1] == "boost"]
        self.stars = px.star_field(seed + 2, 90, 0, 0, W, HOR - 22, bias=1.4)
        self.sky = self._build_sky()
        self.city_far = self._build_city(seed + 5, 640, 22, 50, (44, 24, 80), (150, 110, 220), 0.08)
        self.city_near = self._build_city(seed + 6, 640, 8, 30, (18, 10, 36), (255, 200, 120), 0.18)
        p = np.arange(1, ROWS + 1, dtype=np.float64)
        self.p = p
        self.z = K / p                                           # depth of each ground row
        self.scale = p / ROWS                                    # pixels per world unit on each row
        self.xs = np.arange(W, dtype=np.float64)
        self.fog = np.clip((p - 2) / 40.0, 0.0, 1.0)[:, None]    # 0 at the horizon (all haze), 1 from row 42 down
        self.grid_fade = np.clip((p - 10) / 30.0, 0.0, 1.0)[:, None]
        self.far = np.clip((p - FAR_FADE * 0.5) / FAR_FADE, 0.0, 1.0)[:, None]

    # ---------------------------------------------------------------- pieces drawn once
    def _build_sky(self) -> Image.Image:
        im = Image.new("RGB", (W, HOR), (0, 0, 0))
        px.vgradient(im, 0, 40, (8, 6, 30), (30, 14, 70))
        px.vgradient(im, 40, HOR, (30, 14, 70), (140, 40, 120))
        d = ImageDraw.Draw(im)
        cx, cy, r = 250, 34, 22                                  # a banded planet low in the sky
        bands = [(70, 40, 120), (110, 60, 150), (150, 80, 160), (200, 110, 150), (240, 150, 140)]
        for y in range(cy - r, cy + r + 1):
            half = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
            band = bands[min(len(bands) - 1, max(0, (y - cy + r) * len(bands) // (2 * r + 1)))]
            shade = 0.55 + 0.45 * (1 - (y - cy + r) / (2 * r))
            d.line([cx - half, y, cx + half, y], fill=tuple(int(v * shade) for v in band))
            if half > 2:
                d.point((cx + half, y), fill=(255, 190, 220))           # a thin lit rim on the sun-side edge
        d.ellipse([cx - 36, cy - 3, cx + 36, cy + 3], outline=(200, 150, 220))   # the ring, drawn over the planet...
        d.line([cx - 21, cy - 2, cx + 21, cy - 2], fill=tuple(int(v * 0.7) for v in bands[2]))   # ...and hidden where it passes behind
        return im

    def _build_city(self, seed: int, width: int, lo: int, hi: int, body, lit, density: float) -> Image.Image:
        """A strip of skyline `width` wide that tiles left to right, so it can scroll forever."""
        r = random.Random(seed)
        im = Image.new("RGBA", (width, hi + 4), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x = 0
        while x < width:
            w = r.randrange(10, 26)
            h = r.randrange(lo, hi)
            x1 = min(width - 1, x + w)
            top = hi + 4 - h
            d.rectangle([x, top, x1, hi + 4], fill=body)
            if r.random() < 0.3:                                 # an antenna with a red light
                ax = x + w // 2
                d.line([ax, top - 6, ax, top], fill=body)
                d.point((ax, top - 7), fill=(255, 70, 90))
            for wy in range(top + 3, hi + 2, 4):
                for wx in range(x + 2, x1 - 1, 3):
                    if r.random() < density:
                        d.point((wx, wy), fill=lit)
            x = x1 + r.randrange(0, 3)
        return im

    # ---------------------------------------------------------------- motion
    def _event(self, kind, t):
        for e in self.events:
            if e[1] == kind and e[0] <= t < e[0] + e[2]:
                return e, t - e[0]
        return None, 0.0

    def _boost_level(self, t: float) -> float:
        e, a = self._event("boost", t)
        return math.sin(math.pi * a / e[2]) ** 2 if e else 0.0

    def _travel(self, t: float) -> float:
        """Distance driven by time t: cruise plus every boost so far (each boost's envelope is sin^2, which integrates in closed form)."""
        d = SPEED * t
        for s, _, dur in self.boosts:
            if t <= s:
                break
            a = min(t - s, dur)
            d += SPEED * BOOST * (a / 2 - dur / (4 * math.pi) * math.sin(2 * math.pi * a / dur))
        return d

    def _c(self, rgb) -> tuple:
        """A colour for something drawn over the picture: as given on the code road, the nearest palette colour over the loop."""
        if self.loop is None:
            return rgb
        rgb = tuple(int(v) for v in rgb)
        if rgb not in self._snapped:
            self._snapped[rgb] = self.loop.snap(rgb)
        return self._snapped[rgb]

    # ---------------------------------------------------------------- the frame
    def frame(self, t: float) -> Image.Image:
        if self.loop is not None:
            return self._frame_loop(t)
        t = math.floor(t * self.fps) / self.fps
        bend = _curve(t)
        boost = self._boost_level(t)
        im = self.sky.copy()
        d = ImageDraw.Draw(im)
        px.draw_stars(d, self.stars, t)
        e, a = self._event("star", t)
        if e:
            px.shooting_star(d, a, e[2], 40 + (e[0] * 37) % 180, 8, 70, 26)
        # the skyline drifts against the bend, the near one faster (parallax)
        for layer, k, base in ((self.city_far, 26.0, HOR - self.city_far.height + 3), (self.city_near, 60.0, HOR - self.city_near.height + 4)):
            off = int(round(-bend * k + t * k * 0.05)) % layer.width
            im.paste(layer, (-off, base), layer)
            im.paste(layer, (layer.width - off, base), layer)
        frame = np.zeros((H, W, 3), dtype=np.uint8)
        frame[:HOR] = np.asarray(im)
        frame[HOR:] = self._ground(t, bend, boost)
        out = Image.fromarray(frame, "RGB")
        d = ImageDraw.Draw(out)
        e, a = self._event("rival", t)
        if e:
            self._rival(d, a, e[2], bend, int(e[0]))
        if boost > 0.05:
            self._speed_lines(d, t, boost)
        self._craft(d, t, bend, boost)
        return out

    def _frame_loop(self, t: float) -> Image.Image:
        """The Blender skyway: loop frame n mod N at a constant rate (boosts show as speed lines and thruster glow, never as a faster road),
        with the shooting star only where sky is open and the rival hidden behind anything nearer than it."""
        n = int(round(t * self.fps)) * (30 // self.fps)
        lp = self.loop
        t = n / 30.0
        bend = float(lp.bend[n % lp.frames])
        boost = self._boost_level(t)
        out = Image.fromarray(lp.rgb(n), "RGB")
        e, a = self._event("star", t)
        if e:
            layer = Image.new("RGB", (W, H), (0, 0, 0))
            px.shooting_star(ImageDraw.Draw(layer), a, e[2], 40 + (e[0] * 37) % 180, 6, 70, 22)
            arr = np.asarray(layer)
            hit = (arr.max(-1) > 0) & lp.sky(n)
            if hit.any():
                base = np.asarray(out).copy()
                for y, x in zip(*np.nonzero(hit)):
                    base[y, x] = self._c(arr[y, x])
                out = Image.fromarray(base, "RGB")
        e, a = self._event("rival", t)
        if e:
            out = self._rival_loop(out, n, a, e[2], int(e[0]))
        d = ImageDraw.Draw(out)
        if boost > 0.05:
            self._speed_lines(d, t, boost, hor=lp.horizon)
        self._craft(d, t, bend, boost)
        return out

    def _rival_loop(self, out: Image.Image, n: int, a: float, dur: float, key: int) -> Image.Image:
        """The rival on the 3D road: it overtakes in the next lane and pulls away to about 300 m. Its row, centre and size come from the
        loop's per-row road data; pixels behind nearer geometry (a gantry leg, a bend's wall) are left as they are."""
        lp = self.loop
        z = 3.0 + (a / dur) ** 1.6 * 300.0
        dz, cx, hw = lp.road_dz[n % lp.frames], lp.road_cx[n % lp.frames], lp.road_hw[n % lp.frames]
        ok = np.isfinite(dz)
        if not ok.any() or z > np.nanmax(dz) or z < np.nanmin(dz):
            return out
        rows = np.arange(H)[ok]
        order = np.argsort(dz[ok])
        y = float(np.interp(z, dz[ok][order], rows[order]))
        r = int(round(y))
        if not 0 <= r < H or not np.isfinite(cx[r]):
            return out
        ppm = float(hw[r]) / 8.1                                 # pixels per metre at that row (road_hw measures to the kerb edge, 8.1 m)
        lane = (-5.4 if key % 2 else 5.4) * ppm
        x0 = float(cx[r]) + lane
        w, h = 1.1 * ppm, 0.9 * ppm
        if w < 0.6:
            return out
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        col = self._c((255, 180, 40) if key % 3 else (60, 220, 120))
        d.polygon([(x0 - w, y), (x0 - w * 0.6, y - h), (x0 + w * 0.6, y - h), (x0 + w, y)], fill=col + (255,))
        if w > 3:
            lamp = self._c((255, 140, 70)) + (255,)
            d.ellipse([x0 - w * 0.5 - 1, y - 1, x0 - w * 0.5 + 1, y + 1], fill=lamp)
            d.ellipse([x0 + w * 0.5 - 1, y - 1, x0 + w * 0.5 + 1, y + 1], fill=lamp)
        al = np.asarray(layer)
        show = (al[..., 3] > 0) & (lp.depth_m(n) > z - 1.5)       # hidden where the scene is nearer than the rival
        base = np.asarray(out).copy()
        base[show] = al[..., :3][show]
        return Image.fromarray(base, "RGB")

    def _ground(self, t: float, bend: float, boost: float) -> np.ndarray:
        travel = self._travel(t)
        cx = 160.0 + bend * 90.0 * (1.0 - self.scale) ** 2       # the road bends away near the horizon
        u = (self.xs[None, :] - cx[:, None]) / self.scale[:, None]    # world x of every ground pixel
        au = np.abs(u)
        ph = ((self.z + travel) % (2 * STRIPE)) < STRIPE          # which stripe each row falls in
        ph = ph[:, None]
        out = np.empty((ROWS, W, 3), dtype=np.float64)
        # the ground: dark violet with a glowing grid, brighter near the road
        out[:] = (16, 8, 34)
        gz = ((self.z + travel) % GRID) < (GRID * 0.04 + 0.6 / self.scale)    # lines across, at least about a pixel thick
        gx = (np.abs(((u + GRID / 2) % GRID) - GRID / 2) < 0.9 / self.scale[:, None])
        grid = (gz[:, None] | gx) & (au > ROAD + 6)
        glow = np.array((150, 50, 230), dtype=np.float64) * (1.0 + 0.6 * boost)
        fade = np.broadcast_to(self.grid_fade, (ROWS, W))[grid][:, None]            # the grid fades out with distance before it can alias
        out[grid] = out[grid] * (1 - fade) + np.minimum(255, glow) * fade
        # the road
        road = au < ROAD
        out[road & ph] = (44, 40, 70)
        out[road & ~ph] = (36, 32, 60)
        rum = (au >= ROAD - RUMBLE) & road
        out[rum & ph] = (255, 60, 150)
        out[rum & ~ph] = (235, 235, 255)
        dash = (au < 2.2) & ph
        out[dash] = (255, 220, 110)
        lane = (np.abs(au - ROAD / 2) < 1.4) & ~ph
        out[lane] = (110, 100, 150)
        # guard-rail lights just off the road, one per two stripes, pulsing a little
        rail = (np.abs(au - (ROAD + 4)) < 2.0 + 0.5 / self.scale[:, None]) & (((self.z + travel) % (4 * STRIPE)) < 1.4)[:, None]
        out[rail] = (90, 240, 255)
        # far rows: blend the stripes to their average so the distance does not shimmer, then haze into the horizon glow
        avg = out.copy()
        avg[road] = (40, 36, 65)
        avg[rum] = (245, 150, 200)
        f = self.far[:, :, None]                                 # (ROWS, 1, 1)
        out = avg * (1 - f) + out * f
        h = self.fog[:, :, None]
        out = np.array((140, 40, 120), dtype=np.float64) * (1 - h) + out * h
        return np.clip(out, 0, 255).astype(np.uint8)

    def _craft(self, d: ImageDraw.ImageDraw, t: float, bend: float, boost: float) -> None:
        """The player's craft seen from behind: a wide low wedge, a canopy, two fins and two thrusters."""
        x = 160 - bend * 10 + 2.5 * math.sin(t * 0.9)
        y = 150 + 1.5 * math.sin(t * 3.1) - boost * 3
        lean = -bend * 3.0                                       # the left side drops on a left bend
        c = self._c
        def pt(dx, dy):
            return (x + dx, y + dy + lean * dx / 18.0)
        d.ellipse([x - 20, 166, x + 20, 172], fill=c((10, 6, 20)))  # shadow on the road
        body = [pt(-21, 6), pt(-15, -2), pt(-7, -8), pt(7, -8), pt(15, -2), pt(21, 6), pt(12, 10), pt(-12, 10)]
        d.polygon(body, fill=c((70, 80, 170)))
        d.polygon([pt(-21, 6), pt(-15, -2), pt(15, -2), pt(21, 6)], fill=c((110, 130, 230)))     # the lit top deck
        d.line([pt(-21, 6), pt(21, 6)], fill=c((255, 70, 150)))                                  # a magenta stripe along the side
        d.polygon([pt(-13, -2), pt(-11, -12), pt(-9, -2)], fill=c((200, 60, 120)))               # fins
        d.polygon([pt(13, -2), pt(11, -12), pt(9, -2)], fill=c((200, 60, 120)))
        d.polygon([pt(-5, -8), pt(-3, -12), pt(3, -12), pt(5, -8)], fill=c((120, 230, 255)))     # canopy
        d.point(pt(-2, -11), fill=c((240, 255, 255)))
        flick = 0.5 + 0.5 * math.sin(t * 47.0) * math.sin(t * 13.0)
        for side in (-8, 8):
            tx, ty = pt(side, 8)
            r = 3 + boost * 2 + flick
            d.ellipse([tx - r - 1, ty - r + 1, tx + r + 1, ty + r + 1], fill=c((255, 120, 60) if boost < 0.3 else (120, 200, 255)))
            d.ellipse([tx - 2, ty - 1, tx + 2, ty + 2], fill=c((255, 245, 210)))

    def _rival(self, d: ImageDraw.ImageDraw, a: float, dur: float, bend: float, key: int) -> None:
        """Another craft overtaking on the left lane: it passes us and pulls away up the road, shrinking."""
        z = 2.2 + (a / dur) ** 1.6 * 110.0
        p = K / z
        if p > ROWS or p < 2:
            return
        s = p / ROWS
        y = HOR + p
        lane = -ROAD / 2 if key % 2 else ROAD / 2
        cx = 160.0 + bend * 90.0 * (1.0 - s) ** 2 + lane * s
        w, h = 18 * s, 8 * s
        col = (255, 180, 40) if key % 3 else (60, 220, 120)
        d.polygon([(cx - w, y), (cx - w * 0.6, y - h), (cx + w * 0.6, y - h), (cx + w, y)], fill=col)
        if w > 3:
            d.ellipse([cx - w * 0.5 - 1, y - 1, cx - w * 0.5 + 1, y + 1], fill=(255, 140, 70))
            d.ellipse([cx + w * 0.5 - 1, y - 1, cx + w * 0.5 + 1, y + 1], fill=(255, 140, 70))

    def _speed_lines(self, d: ImageDraw.ImageDraw, t: float, boost: float, hor: float = HOR) -> None:
        """White streaks flying out from the vanishing point during a boost."""
        r = random.Random(int(t * self.fps))
        for _ in range(int(14 * boost)):
            ang = r.uniform(0, 2 * math.pi)
            if math.sin(ang) > 0.35:                             # keep them off the road surface itself
                continue
            r0 = r.uniform(60, 140)
            r1 = r0 + r.uniform(20, 50) * boost
            x0, y0 = 160 + math.cos(ang) * r0, hor + math.sin(ang) * r0 * 0.6
            x1, y1 = 160 + math.cos(ang) * r1, hor + math.sin(ang) * r1 * 0.6
            d.line([x0, y0, x1, y1], fill=self._c((230, 240, 255)))
