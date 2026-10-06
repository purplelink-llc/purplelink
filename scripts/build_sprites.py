#!/usr/bin/env python3
"""Cut the generated art sheets in docs/art-source/ into the WebP sprites the games load.

  python3 scripts/build_sprites.py tanklink       # writes site/assets/games/tanklink/*.webp and pack.json

The sheets are flat magenta (#FF00FF) backgrounds with one sprite per cell. Boxes below are pixel regions of those
sheets. Sizes and names follow docs/games-sprites.md. Needs Pillow, numpy and scipy.
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "art-source"
OUT = ROOT / "site" / "assets" / "games"


def key_solid(img):
    """Sprites with dark outlines: magenta becomes transparent, the purple ground shadow becomes soft black."""
    a = np.array(img.convert("RGB")).astype(float)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    fam = (G < 70) & (np.abs(R - B) < 70) & (R > 90) & (B > 90)
    m = ((R + B) / 2) / 250.0
    alpha = np.where(fam, np.clip(1 - m, 0, 1), 1.0)
    alpha = np.where(fam & (m > 0.93), 0, alpha)
    rgb = a.copy(); rgb[fam] = 0
    solid = alpha > 0.9
    edge = solid & ~ndi.binary_erosion(solid, iterations=2)
    pink = edge & (R > G + 50) & (B > G + 50) & (np.abs(R - B) < 60)       # remove the magenta fringe on outlines
    rgb[pink, 0] = np.minimum(R[pink], G[pink] + 25); rgb[pink, 2] = np.minimum(B[pink], G[pink] + 25)
    return Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")


def key_fx(img):
    """Effects: smoke is purple too, so only saturated magenta is removed and the ground shadow turns soft black."""
    a = np.array(img.convert("RGB")).astype(float)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    d = np.sqrt((255 - R) ** 2 + G ** 2 + (255 - B) ** 2)
    alpha = np.clip((d - 40) / 60, 0, 1)
    mn = np.minimum(R, B)
    shadow = (G < 0.32 * mn) & (mn > 70) & (np.abs(R - B) < 70)
    out = a.copy(); out[shadow] = 0
    alpha = np.where(shadow, np.minimum(alpha, np.clip(np.clip(1 - mn / 255.0, 0, 1) * 1.1, 0, 0.55)), alpha)
    semi = (alpha > 0) & (alpha < 1) & ~shadow
    for c in (0, 2):
        out[..., c][semi] = np.clip((a[..., c][semi] - (1 - alpha[semi]) * 255) / np.maximum(alpha[semi], 0.05), 0, 255)
    out[..., 1][semi] = np.clip(a[..., 1][semi] / np.maximum(alpha[semi], 0.05), 0, 255)
    return Image.fromarray(np.dstack([out, alpha * 255]).astype(np.uint8), "RGBA")


def fit(sprite, box_w, box_h, anchor_x=None, bottom=None, scale=None, flip=False):
    """Scale a cut-out to fit inside box_w x box_h and place it in a transparent 128 x 128 frame."""
    if flip: sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
    s = scale or min(box_w / sprite.width, box_h / sprite.height)
    sp = sprite.resize((max(1, round(sprite.width * s)), max(1, round(sprite.height * s))), Image.LANCZOS)
    frame = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    x = round((128 - sp.width) / 2) if anchor_x is None else round(anchor_x - sp.width / 2)
    y = round(bottom - sp.height) if bottom is not None else round((128 - sp.height) / 2)
    frame.alpha_composite(sp, (x, y))
    return frame


def save(img, folder, name, q=88):
    folder.mkdir(parents=True, exist_ok=True)
    img.save(folder / f"{name}.webp", "WEBP", quality=q, method=6)



def _smooth(a, sigma):
    return np.dstack([ndi.gaussian_filter(a[..., i], sigma) for i in range(a.shape[2])])


def full_background(strip, sky_extend=True, bottom_y=585):
    """Turn a wide landscape strip into the 1648 x 848 picture the Tanklink field expects (opaque).
    The strip is scaled to the full width and set low in the picture; the sky above it is its own top row stretched
    upward (slightly darker toward the top), and the ground below it is its bottom row stretched down."""
    W, H = 1648, 848
    strip = strip.crop((4, 5, strip.width - 4, strip.height - 4))             # the sheet's cut lines leave a thin magenta edge
    sc = W / strip.width
    st = strip.convert("RGB").resize((W, round(strip.height * sc)), Image.LANCZOS)
    a = np.array(st).astype(float); h = a.shape[0]
    top = _smooth(a[:6].mean(axis=0, keepdims=True), (0, 40))[0]          # one colour per column, softened sideways
    bot = _smooth(a[-6:].mean(axis=0, keepdims=True), (0, 60))[0]
    y0 = bottom_y - h
    canvas = np.zeros((H, W, 3))
    # continue the strip's own sky gradient upward: the top 18 rows of the strip show how its colour changes with height
    rows = a[:max(30, h // 4)].mean(axis=1)
    slope = (rows[min(len(rows) - 1, 28)] - rows[0]) / 28.0                  # colour change per pixel going down
    dist = (y0 - np.arange(y0))[:, None]                                    # pixels above the strip
    offset = np.clip(-slope[None, :] * 220 * np.tanh(dist / 260.0), -38, 38)     # keep going the same way, but flatten out and stay gentle
    canvas[:y0] = np.clip(top[None] + offset[:, None, :], 0, 255)
    canvas[y0:bottom_y] = a
    canvas[bottom_y:] = _smooth(bot[None], (0, 160))[0][None] * 0.8
    # soften the seams where the stretched colour meets the picture
    out = canvas.copy()
    for yy, span in ((y0, 70), (bottom_y, 24)):
        lo, hi = max(0, yy - span), min(H, yy + span)
        blur = _smooth(canvas[lo:hi], (6, 0))
        wgt = np.clip(1 - np.abs(np.arange(lo, hi) - yy) / span, 0, 1)[:, None, None]
        out[lo:hi] = canvas[lo:hi] * (1 - wgt * 0.85) + blur * wgt * 0.85
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB"), y0


def near_layer(strip, bottom_y=655):
    """The nearer hills as a 1648 x 848 layer: the strip's sky is keyed out (flood from the top), the ground below stays."""
    W, H = 1648, 848
    strip = strip.crop((4, 5, strip.width - 4, strip.height - 4))
    sc = W / strip.width
    st = strip.convert("RGB").resize((W, round(strip.height * sc)), Image.LANCZOS)
    a = np.array(st).astype(float); h = a.shape[0]
    model = np.median(a[:, :, :], axis=1)                                      # the typical colour on each row: the sky model
    d = np.abs(a - model[:, None, :]).sum(axis=2)
    skyish = d < 70
    lab, n = ndi.label(skyish)
    top_labels = set(np.unique(lab[0][lab[0] > 0]))
    sky = np.isin(lab, list(top_labels))
    sky = ndi.binary_opening(sky, iterations=2)
    alpha = ndi.gaussian_filter((~sky).astype(float), 2.0)
    y0 = bottom_y - h
    out = np.zeros((H, W, 4), dtype=np.uint8)
    out[y0:bottom_y, :, :3] = np.clip(a, 0, 255).astype(np.uint8); out[y0:bottom_y, :, 3] = (alpha * 255).astype(np.uint8)
    bot = np.clip(_smooth(a[-6:].mean(axis=0, keepdims=True), (0, 60))[0] * 0.85, 0, 255).astype(np.uint8)
    out[bottom_y:, :, :3] = bot[None]; out[bottom_y:, :, 3] = 255
    return Image.fromarray(out, "RGBA")


def seamless_tile(tex, size=384, patches=140, seed=7):
    """A tile that repeats in both directions: soft-edged random patches of the source texture, pasted with wrap-around."""
    rng = np.random.default_rng(seed)
    src = np.array(tex.convert("RGB")).astype(float)
    sh, sw = src.shape[:2]; ps = min(sh, 110)
    acc = np.zeros((size, size, 3)); wsum = np.full((size, size, 1), 1e-6)
    yy, xx = np.mgrid[0:ps, 0:ps]
    r = np.sqrt(((yy - ps / 2) / (ps / 2)) ** 2 + ((xx - ps / 2) / (ps / 2)) ** 2)
    mask = np.clip(1.25 - r * 1.15, 0, 1)[..., None] ** 1.5
    for _ in range(patches):
        sy = rng.integers(0, sh - ps + 1); sx = rng.integers(0, sw - ps + 1); patch = src[sy:sy + ps, sx:sx + ps]
        py = rng.integers(0, size); px = rng.integers(0, size)
        ys = (np.arange(ps) + py) % size; xs = (np.arange(ps) + px) % size
        acc[np.ix_(ys, xs)] += patch * mask; wsum[np.ix_(ys, xs)] += mask
    return Image.fromarray(np.clip(acc / wsum, 0, 255).astype(np.uint8), "RGB")


def tanklink():
    raw = Image.open(SRC / "tanklink-sheet.webp").convert("RGB")
    solid, fx = key_solid(raw), key_fx(raw)
    out = OUT / "tanklink"; names = []
    S = 2                                               # files are 2x the nominal sizes in docs/games-sprites.md
    def place(sprite, w, h, ax, ay, flip=False, rot=0, fitw=None, fith=None):
        """Scale to fit, put the sprite so its bottom-centre (or centre when ay is None) lands on the anchor."""
        if rot: sprite = sprite.rotate(rot, expand=True, resample=Image.BICUBIC)
        sc = min((fitw or w) * S / sprite.width, (fith or h) * S / sprite.height)
        sp = sprite.resize((max(1, round(sprite.width * sc)), max(1, round(sprite.height * sc))), Image.LANCZOS)
        frame = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        frame.alpha_composite(sp, (round(ax * S - sp.width / 2), round(ay * S - sp.height)))
        return frame
    # tanks: whole tank without the barrel, facing right; the game mirrors the enemy. Ground contact is at (54, 69)
    save(place(solid.crop((48, 21, 458, 243)), 108, 72, 54, 69, fitw=104), out, "tank-player")
    save(place(solid.crop((899, 21, 1314, 243)), 108, 72, 54, 69, fitw=104), out, "tank-enemy")
    # barrel: one sprite for both teams, so it is desaturated to a neutral steel; pivot 12 px from the left, centred vertically
    bar = solid.crop((530, 76, 840, 157)); r, g, b, a = bar.split()
    gray = Image.merge("RGB", (r, g, b)).convert("L").point(lambda v: int(60 + v * 0.62)).convert("RGB")
    bar = Image.merge("RGBA", (*gray.split(), a))
    bf = Image.new("RGBA", (72 * S, 24 * S), (0, 0, 0, 0)); bs = bar.resize((72 * S, round(bar.height * 72 * S / bar.width)), Image.LANCZOS)
    bf.alpha_composite(bs, (0, round(12 * S - bs.height / 2)))
    save(bf, out, "barrel")
    # shells point up on the sheet; the game wants them pointing right
    for name, box, (w, h) in (("shell-normal", (1374, 78, 1455, 234), (36, 18)), ("shell-heavy", (1490, 48, 1610, 234), (54, 27)), ("shell-cluster", (1638, 104, 1727, 234), (45, 30))):
        sp = solid.crop(box).rotate(-90, expand=True, resample=Image.BICUBIC)
        sc = min((w - 2) * S / sp.width, (h - 2) * S / sp.height); sp = sp.resize((round(sp.width * sc), round(sp.height * sc)), Image.LANCZOS)
        frame = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); frame.alpha_composite(sp, (round(w * S / 2 - sp.width / 2), round(h * S / 2 - sp.height / 2)))
        save(frame, out, name)
    # explosion: six 256 x 256 frames in one strip, all at the same scale so the blast grows and fades believably
    ex = [(78, 315, 228, 440), (259, 261, 528, 440), (518, 238, 843, 440), (834, 240, 1148, 440), (1139, 240, 1442, 440), (1432, 262, 1700, 440)]
    sc = 244 / max(b[2] - b[0] for b in ex)
    strip = Image.new("RGBA", (1536, 256), (0, 0, 0, 0))
    for i, b in enumerate(ex):
        sp = fx.crop(b); sp = sp.resize((round(sp.width * sc), round(sp.height * sc)), Image.LANCZOS)
        if i >= 4:                                      # the smoke frames are strongly purple; mute them so they sit on any sky
            from PIL import ImageEnhance
            r, g, bb, a = sp.split(); sp = Image.merge("RGBA", (*ImageEnhance.Color(Image.merge("RGB", (r, g, bb))).enhance(0.4).split(), a))
        strip.alpha_composite(sp, (i * 256 + round(128 - sp.width / 2), round(150 - sp.height / 2)))   # blast sits a little below centre
    save(strip, out, "explosion")
    # grass strip: 192 x 36 at 2x, made seamless along x by cross-fading its two ends; the surface sits at y = 12 (24 at 2x)
    gs = raw.convert("RGBA").crop((432, 790, 432 + 394 + 60, 864)); gh = round(74 * 72 / 74)
    core = gs.crop((0, 0, 394, 74)); tail = gs.crop((394, 0, 454, 74)); head = core.crop((0, 0, 60, 74))
    mask = Image.linear_gradient("L").rotate(90).resize((60, 74))          # 0 on the left .. 255 on the right after rotate
    blend = Image.composite(head, tail, mask.transpose(Image.FLIP_LEFT_RIGHT))
    core.paste(blend, (0, 0)); core = core.crop((0, 0, 394, 74)).resize((384, 72), Image.LANCZOS)
    save(core, out, "grass-strip")
    # backgrounds: dusk pair for the dark theme and a daytime pair for the light theme
    for tag, far_box, near_box in (("", (0, 450, 898, 598), (909, 450, 1774, 598)), ("-day", (0, 606, 899, 757), (909, 606, 1774, 757))):
        far, y0 = full_background(raw.crop(far_box)); far.save(out / f"bg-far{tag}.webp", "WEBP", quality=82, method=6)
        near_layer(raw.crop(near_box)).save(out / f"bg-near{tag}.webp", "WEBP", quality=82, method=6)
    seamless_tile(raw.crop((37, 765, 389, 882))).save(out / "terrain-tile.webp", "WEBP", quality=85, method=6)
    names = ["tank-player", "tank-enemy", "barrel", "shell-normal", "shell-heavy", "shell-cluster", "explosion", "grass-strip", "bg-far", "bg-near", "bg-far-day", "bg-near-day", "terrain-tile"]
    (out / "pack.json").write_text(json.dumps({"sprites": names}, indent=2) + "\n")
    print("tanklink:", len(names), "sprites,", sum(p.stat().st_size for p in out.glob("*.webp")) // 1024, "KB")


if __name__ == "__main__":
    {"tanklink": tanklink}[sys.argv[1]]()
