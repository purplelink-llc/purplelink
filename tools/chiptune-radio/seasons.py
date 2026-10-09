"""Seasonal touches for the study room, chosen from the real date (in STREAM_TZ, New York by default): a jack-o'-lantern, cobwebs
and bats for Halloween; a tree, presents and snow for the holidays; balloons and fireworks for New Year's Eve. Everything is drawn
in code on the 320x180 canvas, like the rest of the scene.

    seasons.season(time.time())           -> "halloween" | "christmas" | "newyear" | None
    STREAM_SEASON=halloween               forces one (for previews and tests); STREAM_SEASON=off turns them all off
"""
from __future__ import annotations

import math
import os
import random
from datetime import datetime, timezone
from functools import lru_cache

from PIL import ImageDraw

TZ_NAME = os.environ.get("STREAM_TZ", "America/New_York")
NAMES = ("halloween", "christmas", "newyear")


@lru_cache(maxsize=1)
def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(TZ_NAME)
    except Exception:
        return timezone.utc


def local(wall: float) -> datetime:
    return datetime.fromtimestamp(wall, _tz())


def season(wall: float, forced: str | None = None) -> str | None:
    """Which season's decor to show at `wall`. The date rules: Halloween Oct 20-Nov 1, holidays Dec 12-26, New Year's Eve from
    5 pm on Dec 31 until 3 am on Jan 1."""
    forced = forced if forced is not None else os.environ.get("STREAM_SEASON", "")
    if forced:
        return forced if forced in NAMES else None
    n = local(wall)
    md = (n.month, n.day)
    if (10, 20) <= md <= (11, 1):
        return "halloween"
    if (12, 12) <= md <= (12, 26):
        return "christmas"
    if (md == (12, 31) and n.hour >= 17) or (md == (1, 1) and n.hour < 3):
        return "newyear"
    return None


# the colour the string lights take, as (lit, dim) pairs that alternate along the string
LIGHTS = {
    None: [((255, 210, 120), (150, 110, 70))],
    "halloween": [((255, 140, 40), (130, 70, 30)), ((176, 96, 236), (84, 50, 120))],
    "christmas": [((240, 70, 70), (120, 40, 44)), ((90, 220, 120), (44, 110, 62)), ((255, 220, 110), (130, 110, 60))],
    "newyear": [((255, 226, 130), (130, 112, 66)), ((236, 236, 250), (118, 118, 128))],
}


def light_colours(name: str | None, i: int, on: bool):
    pal = LIGHTS.get(name) or LIGHTS[None]
    lit, dim = pal[i % len(pal)]
    return lit if on else dim


# ---------------------------------------------------------------------------------------------------------------- the room
def draw_decor(d: ImageDraw.ImageDraw, name: str | None, t: float) -> None:
    """Floor-right decor and wall pieces. Drawn after the room and before the on-screen text."""
    if name == "halloween":
        for r in (8, 15, 22):                                                                   # a cobweb in the top-left corner

            d.arc([-r, 11 - r, r, 11 + r], 0, 90, fill=(176, 170, 196))
        d.line([0, 11, 20, 28], fill=(176, 170, 196))
        d.line([0, 11, 12, 33], fill=(176, 170, 196))
        d.line([0, 11, 26, 18], fill=(176, 170, 196))
        flick = int(t * 6) % 3
        d.ellipse([264, 146, 290, 165], fill=(236, 112, 28))                                    # the jack-o'-lantern
        d.ellipse([270, 146, 284, 165], fill=(250, 134, 38))
        d.line([277, 147, 277, 164], fill=(196, 88, 20))
        d.rectangle([275, 141, 279, 146], fill=(80, 110, 50))
        glow = (255, 232, 110) if flick else (255, 190, 70)
        for ex in (269, 281):
            d.polygon([(ex, 153), (ex + 5, 153), (ex + 2, 148)], fill=glow)
        d.line([268, 159, 271, 157, 274, 160, 277, 157, 280, 160, 283, 157, 286, 159], fill=glow)
    elif name == "christmas":
        for i, (hw, col) in enumerate(((16, (52, 150, 84)), (22, (42, 124, 70)), (28, (34, 100, 58)))):   # three tiers
            y = 122 + i * 13
            d.polygon([(279, y - 10), (279 - hw, y + 14), (279 + hw, y + 14)], fill=col)
        d.rectangle([276, 161, 282, 166], fill=(110, 70, 50))
        star = (255, 230, 110) if int(t * 3) % 2 else (255, 250, 200)
        d.polygon([(279, 105), (281, 111), (287, 111), (282, 115), (284, 121), (279, 117), (274, 121), (276, 115), (271, 111), (277, 111)], fill=star)
        for k, (ox, oy) in enumerate(((270, 132), (287, 140), (272, 148), (289, 154), (278, 138), (281, 152))):
            on = (int(t * 2) + k) % 3
            d.rectangle([ox, oy, ox + 1, oy + 1], fill=((240, 70, 70), (110, 170, 255), (255, 220, 110))[on])
        d.rectangle([246, 156, 258, 166], fill=(200, 64, 78))                                    # presents
        d.rectangle([251, 156, 253, 166], fill=(255, 226, 150))
        d.rectangle([258, 160, 268, 166], fill=(80, 130, 210))
        d.rectangle([262, 160, 264, 166], fill=(255, 226, 150))
    elif name == "newyear":
        for k, (bx, col) in enumerate(((258, (255, 214, 110)), (272, (230, 230, 246)), (286, (255, 214, 110)))):
            by = 142 + int(3 * math.sin(t * 1.4 + k * 1.7))
            d.ellipse([bx, by, bx + 12, by + 16], fill=col)
            d.ellipse([bx + 2, by + 2, bx + 5, by + 6], fill=(255, 255, 255))
            d.line([bx + 6, by + 16, bx + 6 + int(2 * math.sin(t + k)), 172], fill=(190, 190, 206))
        d.polygon([(248, 166), (254, 150), (260, 166)], fill=(176, 96, 236))                      # a party hat on the floor
        d.point((254, 149), fill=(255, 226, 150))


def draw_sky(d: ImageDraw.ImageDraw, name: str | None, t: float, w: int, h: int, hour: float, rain: bool) -> None:
    """Seasonal things outside the window (drawn on the sky image, so the frame clips them)."""
    night = hour < 5.5 or hour > 18.5
    if name == "halloween" and (night or 17 <= hour <= 19):
        for k in range(3):                                                                       # bats crossing in a loose flock
            ph = (t * 0.07 + k * 0.11) % 1.0
            x = int(w + 10 - ph * (w + 40))
            y = int(18 + 14 * math.sin(t * 0.9 + k * 2.1) + k * 9)
            flap = int(t * 8 + k) % 2
            col = (18, 12, 28)
            d.rectangle([x, y, x + 2, y + 1], fill=col)
            d.polygon([(x, y), (x - 5, y - (4 if flap else 0)), (x - 2, y + 1)], fill=col)
            d.polygon([(x + 2, y), (x + 7, y - (4 if flap else 0)), (x + 4, y + 1)], fill=col)
    elif name == "christmas" and not rain:
        rr = random.Random(7)
        for _ in range(60):
            fx, fy, sp = rr.random(), rr.random(), 0.5 + rr.random() * 0.8
            x = int((fx * w + 6 * math.sin(t * 0.8 + fy * 9)) % w)
            y = int((fy * h + t * 14 * sp) % h)
            d.rectangle([x, y, x + 1, y + 1], fill=(246, 248, 255))
    elif name == "newyear" and night:
        i = int(t // 5)
        rr = random.Random(i * 31 + 5)
        for b in range(2):                                                                       # two bursts overlapping each 5 s
            f = ((t % 5) - b * 1.6) / 2.4
            if not 0 <= f < 1:
                continue
            cx, cy = rr.uniform(0.2, 0.8) * w, rr.uniform(0.16, 0.46) * h
            col = rr.choice([(255, 120, 120), (255, 226, 130), (130, 200, 255), (190, 140, 255), (140, 255, 190)])
            rad = 30 * (1 - (1 - f) ** 2)
            fade = 1 - f
            for ring, rr_ in enumerate((1.0, 0.6)):
              for k in range(22):
                a = k / 22 * math.tau + ring * 0.14
                px, py = cx + math.cos(a) * rad * rr_, cy + math.sin(a) * rad * rr_ + 6 * f * f
                c = tuple(int(v * fade + 20) for v in col)
                d.rectangle([int(px), int(py), int(px) + 2, int(py) + 2], fill=c)
