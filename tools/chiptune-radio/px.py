"""Small pixel-art toolkit shared by the long-form themes. Everything is drawn in code on a 320x180 canvas and enlarged by exactly 6
(1920x1080) or 4 (1280x720), so every art pixel stays a crisp square. Nothing is loaded from disk.

    Fire        a heat-propagation flame (the classic demoscene effect) that flickers and tapers; deterministic by frame number
    sparks()    closed-form rising embers, so any frame can be drawn without replaying the ones before it
    glow_map()  a soft radial light that is multiplied into a picture, for the warm light of a fire or a lantern
    star_field(), twinkle(), fog_layer(), snowflakes(), pine(), lerp_color(), vgradient()
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

W, H = 320, 180


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def vgradient(im: Image.Image, y0: int, y1: int, top, bottom, x0: int = 0, x1: int = W) -> None:
    """Fill rows y0..y1 with a vertical gradient. The gradient is banded to `steps` flat rows so it reads as pixel art, not a smooth blend."""
    d = ImageDraw.Draw(im)
    n = max(1, y1 - y0)
    steps = 14
    for y in range(y0, y1):
        k = int((y - y0) / n * steps) / (steps - 1)
        d.line([x0, y, x1, y], fill=lerp_color(top, bottom, k))


def glow_map(cx: float, cy: float, radius: float, squash: float = 1.0) -> np.ndarray:
    """A float32 (H, W) light falloff: 1 at the centre, 0 at `radius`. `squash` < 1 flattens it vertically (light pooling on the ground)."""
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xs - cx) ** 2 + ((ys - cy) / squash) ** 2) / radius
    return np.clip(1.0 - d, 0.0, 1.0) ** 2


def light(arr: np.ndarray, glow: np.ndarray, colour, amount: float, ambient: float = 1.0) -> np.ndarray:
    """arr (uint8 HxWx3) lit by `glow` in `colour`: the picture dims to `ambient` everywhere, brightens where the light falls and warms toward `colour`."""
    g = (glow * amount)[..., None]
    f = arr.astype(np.float32) * ambient * (1.0 + g * 0.9) + g * np.array(colour, np.float32)[None, None, :] * 0.35
    return np.clip(f, 0, 255).astype(np.uint8)


class Fire:
    """A flame on a small heat grid (one cell per art pixel). Each step every cell takes the average of the three cells below it, cools a
    little at random and a lot toward the edges, and the bottom row is fed. The heat is then drawn through a palette: black, deep red,
    orange, yellow, pale yellow. Steps are made in order as frames are drawn; a jump to a far-off frame warms the flame up instead of replaying."""

    PALETTES = {
        "fire": [(0, 0, 0, 0), (96, 20, 16, 200), (176, 40, 20, 255), (232, 96, 24, 255), (255, 160, 40, 255), (255, 208, 84, 255), (255, 240, 160, 255)],
        "ghostly": [(0, 0, 0, 0), (40, 24, 90, 200), (84, 44, 160, 255), (150, 90, 220, 255), (206, 150, 250, 255), (236, 206, 255, 255), (250, 240, 255, 255)],
    }

    def __init__(self, width: int = 28, height: int = 34, seed: int = 1, palette: str = "fire", cooling: float = 0.024):
        self.w, self.h, self.seed, self.cooling = width, height, seed, cooling
        self.pal = np.array(self.PALETTES[palette], np.uint8)
        xs = np.arange(width, dtype=np.float32)
        self.edge = 1.0 - np.abs(xs - (width - 1) / 2) / (width / 2)            # 1 in the middle, 0 at the sides
        self.reset()

    def reset(self) -> None:
        self.rng = np.random.default_rng(self.seed)
        self.heat = np.zeros((self.h, self.w), np.float32)
        self.n = 0

    def step(self, level: float) -> None:
        hh, rng = self.heat, self.rng
        below = hh[1:]
        avg = (np.roll(below, 1, 1) * 0.8 + below * 1.4 + np.roll(below, -1, 1) * 0.8 + np.vstack([below[1:], below[-1:]]) * 0.5) / 3.5
        rows = np.linspace(0.0, 1.0, self.h - 1, dtype=np.float32)[:, None]   # 0 at the top
        cool = self.cooling * (1.0 + (1.0 - self.edge[None, :]) ** 2 * 4.0) * (1.1 - 0.5 * level) * (1.0 + (1 - rows) * 0.6)
        hh[:-1] = np.clip(avg - cool * rng.random((self.h - 1, self.w), dtype=np.float32) * 2.0, 0, 1)
        feed = (0.55 + 0.45 * rng.random(self.w, dtype=np.float32)) * (0.45 + 0.55 * self.edge) * min(1.0, 0.6 + 0.6 * level)
        hh[-1] = feed
        hh[-2] = np.maximum(hh[-2], feed * 0.95)
        self.n += 1

    def advance(self, n: int, level: float = 1.0) -> None:
        """Bring the flame to step n. Rendering in order just steps forward. A jump (a preview or a thumbnail asking for a frame an hour in) does not
        replay the hours: it reseeds from n and warms up for 60 steps, which gives a flame that looks the same as the one a full run would have."""
        if n < self.n or n - self.n > 120:
            self.rng = np.random.default_rng((self.seed, n))
            self.heat[:] = 0.0
            for _ in range(60):
                self.step(level)
            self.n = n
            return
        while self.n < n:
            self.step(level)

    def image(self) -> Image.Image:
        """RGBA, one pixel per cell. Heat is quantised to the palette steps; the coolest step is transparent."""
        idx = np.clip((self.heat * (len(self.pal) - 0.01)).astype(int), 0, len(self.pal) - 1)
        return Image.fromarray(self.pal[idx], "RGBA")


def sparks(seed: int, t: float, x: float, y: float, spread: float = 10.0, rate: float = 1.4, life: float = 3.2, rise: float = 22.0,
           burst: tuple | None = None):
    """Embers rising from (x, y) at time t: [(px, py, brightness 0..1)]. Position is a closed-form function of age, so a frame never needs the
    ones before it. `rate` is embers per second; `burst` = (start, count) adds a puff of extra ones (a log settling)."""
    out = []
    s0 = int(t - life) - 1
    for s in range(s0, int(t) + 1):
        r = random.Random(seed * 100003 + s)
        k = int(rate) + (1 if r.random() < rate - int(rate) else 0)
        if burst and s == int(burst[0]):
            k += int(burst[1])
        for _ in range(k):
            born = s + r.random()
            age = t - born
            if not 0 <= age < life:
                continue
            vx, vy = r.uniform(-4, 4), rise * r.uniform(0.5, 1.2)
            x0 = x + r.uniform(-spread, spread)
            f = age / life
            px = x0 + vx * age + 4 * math.sin(age * 2.3 + born * 7)
            py = y - vy * age * (1 - 0.35 * f)
            out.append((px, py, 1.0 - f))
    return out


def draw_sparks(d: ImageDraw.ImageDraw, pts) -> None:
    for px, py, b in pts:
        if b > 0.66:
            col = (255, 222, 120)
        elif b > 0.33:
            col = (255, 150, 50)
        else:
            col = (200, 70, 30)
        d.point((int(px), int(py)), fill=col)
        if b > 0.8:
            d.point((int(px), int(py) + 1), fill=(255, 190, 80))


def star_field(seed: int, n: int, x0: int, y0: int, x1: int, y1: int, bias: float = 1.6):
    """n stars as (x, y, phase, size); denser toward the top (bias > 1)."""
    r = random.Random(seed)
    return [(r.randrange(x0, x1), int(y0 + (y1 - y0) * r.random() ** bias), r.random(), 1 if r.random() < 0.85 else 2) for _ in range(n)]


def draw_stars(d: ImageDraw.ImageDraw, stars, t: float, dim: float = 1.0, mask=None, base: Image.Image | None = None) -> None:
    """Twinkling stars. With `base` (the image being drawn on) a star is never darker than the sky behind it, so dim stars at dusk do not leave dark dots."""
    for x, y, ph, size in stars:
        if mask is not None and not mask(x, y):
            continue
        tw = 0.55 + 0.45 * math.sin(t * (0.6 + ph) + ph * 40)
        c = int(255 * dim * (0.55 + 0.45 * tw))
        col = (c, c, min(255, c + 12))
        if base is not None and 0 <= x < base.width and 0 <= y < base.height:
            col = tuple(max(a, b) for a, b in zip(col, base.getpixel((x, y))))
        d.point((x, y), fill=col)
        if size == 2:
            d.point((x + 1, y), fill=tuple(int(v * 0.6) for v in col))
            d.point((x, y + 1), fill=tuple(int(v * 0.6) for v in col))


def shooting_star(d: ImageDraw.ImageDraw, age: float, dur: float, x0: float, y0: float, dx: float, dy: float) -> None:
    f = age / dur
    if not 0 <= f <= 1:
        return
    hx, hy = x0 + dx * f, y0 + dy * f
    for i in range(10):
        tf = max(0.0, f - i * 0.025)
        px, py = x0 + dx * tf, y0 + dy * tf
        c = int(255 * (1 - i / 10) * (1 - f * 0.4))
        d.point((int(px), int(py)), fill=(c, c, min(255, c + 20)))
    d.point((int(hx), int(hy)), fill=(255, 255, 255))


def fog_layer(seed: int, t: float, y0: int, y1: int, colour, alpha: int, speed: float = 3.0, scale: int = 40) -> Image.Image:
    """A band of drifting fog as an RGBA layer, built from a few soft wide blobs whose edges are dithered (ordered 2x2), so it keeps a pixel look."""
    layer = np.zeros((H, W), np.float32)
    r = random.Random(seed)
    ys = np.arange(H, dtype=np.float32)[:, None]
    xs = np.arange(W, dtype=np.float32)[None, :]
    for _ in range(9):
        cx0, cy, rw, rh, sp = r.uniform(0, W), r.uniform(y0, y1), r.uniform(scale * 0.8, scale * 1.9), r.uniform(5, 13), r.uniform(0.5, 1.5)
        cx = (cx0 + t * speed * sp) % (W + 2 * rw) - rw
        layer += np.clip(1.0 - (((xs - cx) / rw) ** 2 + ((ys - cy) / rh) ** 2), 0, 1)
    layer = np.clip(layer, 0, 1)
    bayer = np.array([[0.1, 0.6], [0.85, 0.35]], np.float32)
    thr = np.tile(bayer, (H // 2 + 1, W // 2 + 1))[:H, :W]
    on = layer > thr * 0.85
    out = np.zeros((H, W, 4), np.uint8)
    out[on] = (*colour, alpha)
    return Image.fromarray(out, "RGBA")


def snowflakes(d: ImageDraw.ImageDraw, seed: int, t: float, box, count: int, speed: float, sway: float = 6.0, col=(240, 246, 255), big_every: int = 9) -> None:
    """Falling snow inside box=(x0,y0,x1,y1): each flake wraps top to bottom; every `big_every`th is a 2x2 flake nearer the viewer."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    r = random.Random(seed)
    for i in range(count):
        fx, fy, sp, ph = r.random(), r.random(), 0.6 + r.random() * 0.8, r.random() * 6.28
        x = x0 + (fx * w + sway * math.sin(t * 0.7 * sp + ph) + t * 2.0 * sp * 0.3) % w
        y = y0 + (fy * h + t * speed * sp) % h
        if i % big_every == 0:
            d.rectangle([int(x), int(y), int(x) + 1, int(y) + 1], fill=col)
        else:
            d.point((int(x), int(y)), fill=tuple(int(v * 0.82) for v in col))


def pine(d: ImageDraw.ImageDraw, x: int, base: int, height: int, colour, tiers: int = 5, width: int | None = None, snow=None) -> None:
    """A stacked-triangle pine with its trunk bottom at (x, base). `snow` is an optional colour drawn along the left of each tier's edge."""
    width = width or height // 2
    d.rectangle([x - 1, base - height // 10, x, base], fill=colour)
    for i in range(tiers):
        top = base - height + int(i * height * 0.8 / tiers)
        bot = top + int(height * 0.34)
        half = int(width * (0.35 + 0.65 * (i + 1) / tiers) / 2) + 1
        d.polygon([(x, top), (x - half, bot), (x + half, bot)], fill=colour)
        if snow:
            d.line([(x - 1, top + 1), (x - half + 2, bot - 1)], fill=snow)


def scale_up(im: Image.Image, k: int) -> Image.Image:
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def sine_ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)
