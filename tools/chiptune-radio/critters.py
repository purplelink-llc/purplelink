"""Things that happen in the study room during the day: the cat wakes, stretches, washes and goes back to sleep; a blonde English
Labrador wanders in and lies down; a robin lands on the sill; the robot vacuum crosses the floor; at night a shooting star, in the
rain a flash of lightning, in the day a hot-air balloon. All drawn in code on the 320x180 canvas, nothing loaded from disk.

What happens when comes from the wall clock alone: time is cut into 4 minute slots and each slot draws one event (or nothing) from
a seeded generator, so the same minute has the same event on every restart and nothing needs saving.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageChops, ImageDraw

SLOT = 240.0
# name: (weight, seconds, when). "day" and "night" are the scene's own hours; "rain" needs rain falling. None is a quiet slot.
EVENTS = {
    None: (14, 0, "any"), "cat": (22, 48, "any"), "dog": (22, 130, "any"), "bird": (10, 30, "day"),
    "vacuum": (8, 58, "any"), "star": (9, 9, "night"), "balloon": (8, 80, "day"), "storm": (9, 9, "rain"),
    "friend": (10, 90, "any"), "plane": (8, 46, "any"),
}

P = {
    "cat": (230, 150, 96), "cat_dk": (190, 112, 70), "belly": (250, 224, 190), "ink": (24, 18, 34), "pink": (240, 130, 150),
    "coat": (238, 208, 142), "coat_dk": (208, 170, 104), "coat_lt": (250, 232, 184), "nose": (42, 30, 38), "collar": (180, 120, 240),
    "tongue": (240, 120, 134), "robin": (150, 104, 84), "breast": (240, 132, 70), "beak": (250, 210, 90), "white": (250, 246, 240),
    "vac": (126, 124, 148), "vac_hi": (170, 168, 192), "vac_dk": (84, 82, 104),
    "glass": (170, 214, 236), "water": (112, 176, 214), "fish": (252, 148, 52), "fish_dk": (222, 104, 34), "sand": (226, 204, 150),
    "weed": (74, 170, 110), "fhoodie": (84, 196, 170), "fhoodie_dk": (58, 150, 130), "fhair": (178, 118, 64), "pot": (176, 180, 196),
    "skin": (236, 184, 148), "coffee": (92, 56, 44),
}


def active(wall: float, hour: float, rain: bool):
    """(name, seconds into it, its length) for the event running at `wall`, or None."""
    slot = int(wall // SLOT)
    into = wall - slot * SLOT
    h0 = (hour - (wall - slot * SLOT) / 300.0) % 24.0              # the scene hour when this slot began (a scene day is 2 real hours)
    night, day = h0 < 5.5 or h0 > 19.5, 6.5 <= h0 <= 18.5
    r = random.Random(slot * 7919 + 17)
    ok = {k: v for k, v in EVENTS.items() if v[2] == "any" or (v[2] == "night" and night) or (v[2] == "day" and day and not rain)
          or (v[2] == "rain" and rain)}
    pick = r.uniform(0, sum(v[0] for v in ok.values()))
    name = None
    for k, v in ok.items():
        pick -= v[0]
        if pick <= 0:
            name = k
            break
    if name is None:
        return None
    dur = EVENTS[name][1]
    start = r.uniform(6, SLOT - dur - 6)
    return (name, into - start, dur) if start <= into < start + dur else None


def _ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# --------------------------------------------------------------------------------------------------------------- the cat
CAT_PLAN = [(2, "sleep"), (5, "wake"), (13, "stretch"), (24, "wash"), (28, "yawn"), (37, "look"), (44, "curl"), (99, "sleep")]


def cat_pose(ev) -> str:
    if not ev or ev[0] != "cat":
        return "sleep"
    for until, pose in CAT_PLAN:
        if ev[1] < until:
            return pose
    return "sleep"


def _z(d, x, y, col):
    for dx, dy in ((0, 0), (1, 0), (2, 0), (1, 1), (0, 2), (1, 2), (2, 2)):
        d.point((x + dx, y + dy), fill=col)


def draw_cat(d: ImageDraw.ImageDraw, t: float, ev, tail_col=None) -> None:
    pose = cat_pose(ev)
    c, dk, ink = P["cat"], P["cat_dk"], P["ink"]
    br = 1 if int(t * 1.2) % 2 else 0
    swish = int(3 * math.sin(t * 2.6))
    if pose in ("sleep", "curl"):
        d.ellipse([214, 96 - br, 244, 108], fill=c)
        d.ellipse([238, 92, 252, 106], fill=c)
        d.polygon([(239, 92), (242, 86), (245, 92)], fill=c)
        d.polygon([(246, 92), (249, 86), (252, 92)], fill=c)
        if pose == "curl" and int(t * 2) % 4:                       # settling down: eyes still half open
            d.point((243, 99), fill=ink)
            d.point((249, 99), fill=ink)
            d.line([242, 100, 244, 100], fill=ink)
            d.line([248, 100, 250, 100], fill=ink)
        else:
            d.line([241, 99, 244, 99], fill=ink)
            d.line([248, 99, 250, 99], fill=ink)
        flick = 3 if int(t * 0.6) % 5 == 0 else 0
        d.line([214, 104, 208, 100 - flick], fill=dk, width=2)
        if pose == "sleep":                                          # a few z's drift up now and then
            ph = (t % 9.0)
            if ph < 6:
                for k in range(3):
                    f = ph - k * 1.6
                    if 0 <= f < 3.2:
                        _z(d, 254 + k * 3 + int(math.sin(f * 2)), 86 - int(f * 5) - k * 2, (232, 224, 250))
    elif pose == "wake":
        d.ellipse([214, 96, 244, 108], fill=c)
        d.ellipse([238, 86, 252, 100], fill=c)
        d.polygon([(239, 86), (242, 80), (245, 86)], fill=c)
        d.polygon([(246, 86), (249, 80), (252, 86)], fill=c)
        d.rectangle([241, 92, 242, 93], fill=ink)
        d.rectangle([248, 92, 249, 93], fill=ink)
        d.line([214, 104, 208, 98 + swish], fill=dk, width=2)
    elif pose == "stretch":
        sway = int(math.sin(t * 4) * 1)
        d.polygon([(211, 104), (214, 88 + sway), (230, 90), (244, 102), (246, 108), (213, 108)], fill=c)
        d.rectangle([243, 104, 262, 107], fill=dk)                  # front paws reaching out along the sill
        d.rectangle([260, 104, 264, 107], fill=c)
        d.ellipse([247, 96, 259, 106], fill=c)
        d.polygon([(248, 97), (250, 92), (252, 97)], fill=c)
        d.polygon([(254, 97), (256, 92), (258, 97)], fill=c)
        d.line([250, 101, 252, 101], fill=ink)
        d.line([255, 101, 257, 101], fill=ink)
        d.line([214, 90 + sway, 211, 78], fill=dk, width=2)         # the tail straight up
    else:                                                            # the sitting poses: wash, yawn, look
        d.ellipse([226, 88, 246, 108], fill=c)
        d.ellipse([230, 100, 244, 108], fill=P["belly"])
        d.ellipse([228, 76, 244, 90], fill=c)
        d.polygon([(229, 78), (231, 71), (234, 77)], fill=c)
        d.polygon([(238, 77), (241, 71), (243, 78)], fill=c)
        d.line([226, 106, 216, 107, 212, 101 + swish], fill=dk, width=2)
        if pose == "wash":
            up = int(t * 3) % 2
            d.line([232, 84, 232, 88], fill=ink)
            d.line([240, 84, 240, 88], fill=ink)                    # eyes shut
            d.rectangle([239 + up * 2, 79 + up * 3, 242 + up * 2, 87 + up * 3], fill=dk)   # a paw going over the face
        elif pose == "yawn":
            d.rectangle([233, 82, 239, 87], fill=P["pink"])
            d.line([231, 80, 233, 80], fill=ink)
            d.line([239, 80, 241, 80], fill=ink)
        else:                                                        # look: eyes follow something out of the window
            ex = 1 + int(round(math.sin(t * 0.9)))
            d.rectangle([231 + ex, 82, 232 + ex, 83], fill=ink)
            d.rectangle([238 + ex, 82, 239 + ex, 83], fill=ink)
            d.line([235, 85, 237, 85], fill=P["pink"])


# --------------------------------------------------------------------------------------------------------------- the dog
GROUND = 175
DOG_X = 188


def dog_state(age: float):
    """(pose, x, facing_left) for the Labrador `age` seconds into its 130 s visit."""
    if age < 9:
        return "walk", 345 - (345 - DOG_X) * _ease(age / 9) if age > 0 else 345, True
    if age < 14:
        return "stand", DOG_X, True
    if age < 34:
        return "sit", DOG_X, True
    if age < 100:
        return "down", DOG_X, True
    if age < 108:
        return "sit", DOG_X, True
    if age < 118:
        return "stand", DOG_X, True
    return "walk", DOG_X + (345 - DOG_X) * _ease((age - 118) / 12), False


def draw_dog(im: Image.Image, t: float, age: float) -> None:
    """A blonde English Labrador in profile, facing left (so it walks in from the right). Drawn on a small layer and flipped to
    face right when it leaves."""
    pose, x0, left = dog_state(age)
    layer = Image.new("RGBA", (80, 56), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ox, g = 40, 52                                                   # the dog's x0 and its ground line, in layer coordinates
    coat, dk, lt, nose, ink = P["coat"], P["coat_dk"], P["coat_lt"], P["nose"], P["ink"]
    wag = math.sin(t * (16 if pose in ("sit", "stand") else 7 if pose == "down" else 10)) * (5 if pose != "walk" else 3)
    blink = int(t * 1.3) % 9 == 0
    pant = pose in ("sit", "stand") and int(t * 4) % 2 == 0

    def head(hx, hy, tilt=0):
        ld.ellipse([hx - 6, hy - 5 + tilt, hx + 6, hy + 5 + tilt], fill=coat)                 # skull
        ld.rectangle([hx - 12, hy - 1 + tilt, hx - 4, hy + 4 + tilt], fill=lt)                # muzzle
        ld.rectangle([hx - 14, hy - 1 + tilt, hx - 12, hy + 2 + tilt], fill=nose)             # nose
        ld.ellipse([hx + 1, hy - 5 + tilt, hx + 7, hy + 6 + tilt], fill=dk)                   # a floppy ear
        if blink or pose == "down" and int(t * 0.7) % 3 == 0:
            ld.line([hx - 4, hy - 2 + tilt, hx - 2, hy - 2 + tilt], fill=ink)
        else:
            ld.rectangle([hx - 4, hy - 3 + tilt, hx - 3, hy - 2 + tilt], fill=ink)
        if pant:
            ld.rectangle([hx - 9, hy + 4 + tilt, hx - 7, hy + 7 + tilt], fill=P["tongue"])

    if pose in ("walk", "stand"):
        step = int(t * 9) % 2 if pose == "walk" else 0
        ld.ellipse([ox - 15, g - 26, ox + 16, g - 10], fill=coat)                              # body
        ld.rectangle([ox - 17, g - 28, ox - 9, g - 17], fill=coat)                             # chest and neck
        for lx, off in ((-13, step), (-8, 1 - step), (8, 1 - step), (13, step)):
            ld.rectangle([ox + lx, g - 12, ox + lx + 3, g - (2 if off else 0) - 1], fill=coat if lx < 0 else dk)
        ld.line([ox + 14, g - 22, ox + 22, g - 28 + int(wag), ox + 25, g - 33 + int(wag)], fill=coat, width=3)   # tail
        head(ox - 22, g - 32, tilt=1 if pose == "stand" and int(t * 0.4) % 4 == 0 else 0)
        ld.rectangle([ox - 20, g - 28, ox - 16, g - 25], fill=P["collar"])
    elif pose == "sit":
        ld.ellipse([ox - 6, g - 18, ox + 14, g], fill=coat)                                    # haunch
        ld.ellipse([ox - 17, g - 32, ox + 3, g - 2], fill=coat)                                # chest and belly
        ld.rectangle([ox - 15, g - 12, ox - 11, g], fill=lt)
        ld.rectangle([ox - 10, g - 12, ox - 6, g], fill=coat)
        ld.line([ox + 12, g - 2, ox + 26 + int(wag), g - 3], fill=coat, width=3)                # the tail sweeping the floor
        head(ox - 19, g - 38)
        ld.rectangle([ox - 17, g - 33, ox - 13, g - 30], fill=P["collar"])
    else:                                                            # down: lying like a loaf, head on the paws
        ld.ellipse([ox - 14, g - 15, ox + 19, g], fill=coat)
        ld.ellipse([ox + 4, g - 17, ox + 19, g - 3], fill=dk)
        ld.rectangle([ox - 28, g - 5, ox - 12, g], fill=coat)                                   # front paws
        ld.line([ox + 18, g - 4, ox + 28, g - 3 - int(wag * 0.4)], fill=coat, width=3)
        head(ox - 22, g - 12, tilt=1 if int(t * 0.5) % 6 == 0 else 0)
        ld.rectangle([ox - 16, g - 9, ox - 12, g - 6], fill=P["collar"])
    if not left:
        layer = layer.transpose(Image.FLIP_LEFT_RIGHT)
        # the flipped layer is anchored by its mirror: x0 maps to 79 - ox
        im.paste(layer, (int(x0) - (79 - ox), GROUND - g), layer)
    else:
        im.paste(layer, (int(x0) - ox, GROUND - g), layer)


# ----------------------------------------------------------------------------------------------------------- the robin
SILL_X, SILL_Y = 198, 101


def bird_state(age: float, dur: float):
    """(x, y, perched, beak_down) for a robin that flies in from the right, hops about on the sill, and leaves."""
    if age < 5:
        f = _ease(age / 5)
        return 262 - 64 * f, 22 + 79 * f + 8 * math.sin(f * math.pi) * -1, False, False
    if age < 22:
        a = age - 5
        hop = 3 * (int(a / 3.5) % 2) + 0
        return SILL_X - hop, SILL_Y - (1 if (a % 3.5) < 0.25 else 0), True, (int(a * 1.5) % 4 == 0)
    f = _ease((age - 22) / 6.5)
    return SILL_X + 66 * f, SILL_Y - 86 * f - 6 * math.sin(f * math.pi), False, False


def draw_bird(im: Image.Image, t: float, age: float, dur: float, win: tuple) -> None:
    x, y, perched, peck = bird_state(age, dur)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    x, y = int(x), int(y)
    body, breast = P["robin"], P["breast"]
    ld.ellipse([x - 5, y - 6, x + 5, y + 1], fill=body)
    ld.ellipse([x - 5, y - 4, x, y + 1], fill=breast)
    hy = y - 7 + (3 if peck else 0)
    ld.ellipse([x - 7, hy - 3, x - 2, hy + 2], fill=body)
    ld.point((x - 6, hy - 1), fill=P["ink"])
    ld.polygon([(x - 8, hy - 1), (x - 11, hy + (1 if peck else 0)), (x - 8, hy + 1)], fill=P["beak"])
    ld.line([x + 4, y - 3, x + 8, y - 1 + (0 if perched else 2)], fill=body, width=2)           # tail
    if perched:
        ld.line([x - 1, y + 1, x - 1, y + 3], fill=P["beak"])
        ld.line([x + 2, y + 1, x + 2, y + 3], fill=P["beak"])
    else:
        up = int(t * 12) % 2
        ld.polygon([(x - 1, y - 4), (x + 5, y - 4 + (-7 if up else 4)), (x + 6, y - 2)], fill=P["white"] if up else body)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rectangle([win[0], win[1], win[2], win[3] + 4], fill=255)
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    im.paste(layer, (0, 0), layer)


# --------------------------------------------------------------------------------------------------------------- the vacuum
def draw_vacuum(d: ImageDraw.ImageDraw, t: float, age: float, dur: float) -> None:
    x = int(-24 + (age / dur) * 372)
    y = 172
    d.ellipse([x, y - 1, x + 18, y + 5], fill=P["vac_dk"])
    d.ellipse([x, y - 4, x + 18, y + 3], fill=P["vac"])
    d.ellipse([x + 3, y - 4, x + 15, y], fill=P["vac_hi"])
    d.point((x + 9, y - 2), fill=(120, 230, 150) if int(t * 2) % 2 else (230, 90, 100))        # the status light
    if int(t * 10) % 2:
        d.point((x + 20, y + 4), fill=(210, 200, 220))                                        # a brush flicking dust ahead of it
        d.point((x + 22, y + 3), fill=(180, 170, 200))


# ---------------------------------------------------------------------------------------------------- the sky's visitors
def sky_visitor(im: Image.Image, d: ImageDraw.ImageDraw, ev, t: float, w: int, h: int, top, bot) -> None:
    """Drawn on the sky image itself, so the window frame clips it: a shooting star, a hot-air balloon, a flash of lightning."""
    if not ev:
        return
    name, age, dur = ev
    if name == "plane":
        sky_plane(d, ev, t, w, h, (top[0] + top[1] + top[2]) < 260)
    elif name == "star":
        for k, (t0, x0, y0) in enumerate(((0.5, 0.82, 0.06), (3.6, 0.55, 0.14), (6.4, 0.9, 0.22))):
            a = age - t0
            if 0 <= a < 1.4:
                f = a / 1.4
                hx, hy = (x0 - 0.35 * f) * w, (y0 + 0.28 * f) * h
                for i in range(16):
                    fade = (1 - i / 16) * (1 - f * 0.5)
                    px, py = int(hx + i * 2.0), int(hy - i * 0.7)
                    d.rectangle([px, py, px + (1 if i < 8 else 0), py], fill=tuple(int(c * fade + 30) for c in (255, 250, 220)))
                d.rectangle([int(hx), int(hy) - 1, int(hx) + 1, int(hy) + 1], fill=(255, 255, 255))
    elif name == "balloon":
        f = age / dur
        bx = int(w + 24 - f * (w + 60))
        by = int(h * 0.22 + 6 * math.sin(t * 0.7) + 8 * f)
        d.ellipse([bx, by, bx + 16, by + 19], fill=(220, 70, 90))
        d.polygon([(bx + 8, by), (bx + 3, by + 14), (bx + 13, by + 14)], fill=(250, 214, 110))
        d.line([bx + 8, by, bx + 8, by + 17], fill=(220, 70, 90))
        d.line([bx + 4, by + 17, bx + 6, by + 22], fill=(90, 60, 50))
        d.line([bx + 12, by + 17, bx + 10, by + 22], fill=(90, 60, 50))
        d.rectangle([bx + 5, by + 22, bx + 11, by + 25], fill=(150, 100, 70))
    elif name == "storm":
        for t0 in (2.0, 2.25, 5.4):
            a = age - t0
            if 0 <= a < 0.18:
                flash = Image.new("RGB", im.size, (235, 240, 255))
                im.paste(Image.blend(im, flash, 0.55 if a < 0.09 else 0.3))
                if t0 < 3:
                    x = int(w * 0.6)
                    pts, y = [(x, 0)], 0
                    rr = random.Random(int(age * 100) // 9)
                    while y < h * 0.55:
                        y += 8
                        x += rr.randint(-6, 6)
                        pts.append((x, y))
                    d.line(pts, fill=(255, 255, 235), width=2)


# ----------------------------------------------------------------------------------------------------------- the goldfish
BOWL = (50, 94, 70, 112)


def draw_goldfish(d: ImageDraw.ImageDraw, t: float) -> None:
    """A bowl on the desk beside the laptop with a goldfish turning lazy laps, a bit of weed, and a bubble now and then."""
    x0, y0, x1, y1 = BOWL
    d.ellipse([x0, y0 + 3, x1, y1], fill=P["water"], outline=P["glass"])
    d.rectangle([x0 + 4, y0 + 1, x1 - 4, y0 + 3], fill=P["glass"])                              # the rim
    d.chord([x0 + 1, y1 - 7, x1 - 1, y1], 0, 180, fill=P["sand"])
    d.line([x0 + 14, y1 - 3, x0 + 13, y1 - 11], fill=P["weed"])
    d.line([x0 + 16, y1 - 3, x0 + 17, y1 - 9], fill=P["weed"])
    ph = t * 0.55
    fx = x0 + 10 + 4.2 * math.sin(ph)
    dirn = 1 if math.cos(ph) > 0 else -1                                                         # heading right or left
    fy = y0 + 10 + 1.5 * math.sin(t * 1.3)
    ix = int(fx)
    d.ellipse([ix - 3, int(fy) - 2, ix + 3, int(fy) + 2], fill=P["fish"])
    tx = ix - 4 * dirn
    d.polygon([(ix - 2 * dirn, int(fy)), (tx - dirn, int(fy) - 2), (tx - dirn, int(fy) + 2)], fill=P["fish_dk"])
    d.point((ix + 2 * dirn, int(fy) - 1), fill=P["ink"])
    b = (t * 0.7) % 4.0
    if b < 1.6:
        d.point((x0 + 7 + int(math.sin(t * 3)), y0 + 15 - int(b * 5)), fill=(236, 248, 255))


# ------------------------------------------------------------------------------------------------------------ the friend
FRIEND_X = 252


def friend_state(age: float, dur: float):
    """(x, pouring, steaming): a friend walks in from the right with the coffee pot, refills the mug, waves and goes."""
    if age < 7:
        return 350 - (350 - FRIEND_X) * _ease(age / 7), False, False
    if age < 21:
        return FRIEND_X, 9 <= age < 15, age >= 12
    if age < 28:
        return FRIEND_X + (350 - FRIEND_X) * _ease((age - 21) / 7), False, True
    return None, False, True


def draw_friend(im: Image.Image, d: ImageDraw.ImageDraw, t: float, age: float, dur: float) -> None:
    x, pouring, _ = friend_state(age, dur)
    if x is None:
        return
    x = int(x)
    walking = age < 7 or age >= 21
    step = math.sin(t * 7.0) if walking else 0.0
    top = 100 - 20 + (int(abs(step) * 2) if walking else 0)
    d.rectangle([x - 22, top, x + 22, 128], fill=P["fhoodie"])
    d.rectangle([x - 22, top, x - 18, 128], fill=P["fhoodie_dk"])
    d.rectangle([x - 7, top - 6, x + 7, top], fill=P["skin"])
    d.ellipse([x - 12, top - 28, x + 12, top - 2], fill=P["fhair"])
    d.ellipse([x - 8, top - 33, x + 2, top - 22], fill=P["fhair"])                              # a bun
    if 7 <= age < 21:                                                                            # the near arm reaches the mug with the pot
        wave = 14 <= age
        d.line([x - 22, top + 6, 238, 101], fill=P["fhoodie"], width=5) if not wave else d.line([x - 22, top + 6, x - 24, top + 24], fill=P["fhoodie"], width=5)
        if not wave:
            d.rectangle([236, 96, 244, 103], fill=P["pot"])                                      # the pot, tilted over the mug
            d.line([244, 98, 247, 100], fill=P["pot"], width=2)
        if wave and int(t * 4) % 2:                                                              # a wave with the other hand
            d.line([x + 22, top + 6, x + 30, top - 8], fill=P["fhoodie"], width=5)
            d.rectangle([x + 28, top - 13, x + 32, top - 8], fill=P["skin"])
        else:
            d.line([x + 22, top + 6, x + 24, top + 24], fill=P["fhoodie"], width=5)
        if pouring:
            d.line([237, 103, 235, 111], fill=P["coffee"])
    else:
        for sgn in (-1, 1):
            sw = round(sgn * step * 4)
            d.line([x + sgn * 24, top + 6, x + sgn * 26, top + 24 + sw], fill=P["fhoodie"], width=5)
            d.rectangle([x + sgn * 26 - 2, top + 24 + sw, x + sgn * 26 + 2, top + 28 + sw], fill=P["skin"])


# --------------------------------------------------------------------------------------------------------------- the plane
def sky_plane(d: ImageDraw.ImageDraw, ev, t: float, w: int, h: int, night: bool) -> None:
    """A small plane crossing the window high up: a white shape with a contrail by day, blinking lights at night."""
    name, age, dur = ev
    f = age / dur
    x = int(-26 + f * (w + 60))
    y = int(h * 0.16 + 6 * f)
    if night:
        if int(t * 2) % 2:
            d.rectangle([x + 4, y, x + 5, y + 1], fill=(255, 90, 90))
        d.rectangle([x + 2, y + 1, x + 3, y + 2], fill=(120, 255, 140))
        if int(t * 4) % 4 == 0:
            d.rectangle([x, y, x + 1, y + 1], fill=(255, 255, 255))
        return
    for i in range(1, 30):
        d.point((x - i, y + 1 - i // 14), fill=tuple(int(c * (1 - i / 30) + 150 * (i / 30)) for c in (255, 255, 255)))
    d.rectangle([x, y, x + 9, y + 2], fill=(246, 246, 252))
    d.polygon([(x + 3, y), (x + 5, y - 4), (x + 6, y)], fill=(222, 222, 236))
    d.polygon([(x + 3, y + 2), (x + 5, y + 6), (x + 6, y + 2)], fill=(222, 222, 236))
    d.polygon([(x, y), (x - 1, y - 3), (x + 1, y)], fill=(200, 200, 220))
