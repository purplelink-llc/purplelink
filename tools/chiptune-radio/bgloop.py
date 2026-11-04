"""Pre-rendered background loops for the long-form themes (docs/designs/blender-loop-backgrounds.md).

A loop is a folder under $AMBIENT_LOOPS (default /Volumes/Extreme SSD/PurplelinkVideos/ambient/_loops):
    <name>/loop.npz        idx [N,180,320] uint8 palette indices, palette [P,3] uint8 sRGB, depth [N,180,320] uint8 (255 = sky),
                           road_cx, road_hw, road_dz [N,180] float32 (NaN where a row has no road), bend [N] float32 (smoothed, -1..1),
                           horizon float32
    <name>/manifest.json   sha256 of loop.npz, frame count, fps, seam and flicker figures, Blender version, the assets used
A theme plays frame n mod N at the video's frame rate and draws its events on top, in the loop's palette.

    python3.12 bgloop.py build --frames DIR --name racer-highway-v1     pack the Blender frames (blender/build_loop.sh calls this)
    python3.12 bgloop.py check racer-highway-v1                         load, verify the hash and print the manifest
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "blender"))
import skyway_geom as G  # noqa: E402

DEFAULT_ROOT = "/Volumes/Extreme SSD/PurplelinkVideos/ambient/_loops"
PALETTE_SIZE = 40
DITHER = 0.25                     # ordered dither strength, in palette steps
SEAM_MAX = 0.005                  # RMS of frame N against frame 0, as a fraction of full scale
FLICKER_MAX = 0.02                # fraction of sky pixels whose index changes from one frame to the next
BLOOM_THRESHOLD, BLOOM_GAIN = 0.9, 0.35
# today's racer colours, kept in the palette so the craft, rival and speed lines need nothing new
SEED_COLOURS = [(16, 8, 34), (44, 40, 70), (36, 32, 60), (255, 60, 150), (235, 235, 255), (255, 220, 110), (110, 100, 150), (90, 240, 255),
                (150, 50, 230), (140, 40, 120), (8, 6, 30), (30, 14, 70), (70, 80, 170), (110, 130, 230), (200, 60, 120), (120, 230, 255),
                (255, 120, 60), (120, 200, 255), (255, 245, 210), (230, 240, 255), (10, 6, 20), (255, 180, 40), (60, 220, 120), (255, 140, 70)]
BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float64) + 0.5) / 16 - 0.5


def root() -> Path:
    return Path(os.environ.get("AMBIENT_LOOPS", DEFAULT_ROOT))


# ------------------------------------------------------------------------------------------------ colour
def srgb8_to_oklab(c) -> np.ndarray:
    lin = G.srgb_to_linear(c)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]])
    lms = np.cbrt(lin @ m1.T)
    return lms @ m2.T


def nearest(lab: np.ndarray, pal_lab: np.ndarray) -> np.ndarray:
    """Index of the nearest palette colour for every row of lab [..., 3]."""
    flat = lab.reshape(-1, 3)
    out = np.empty(len(flat), dtype=np.uint8)
    for i in range(0, len(flat), 65536):
        d = ((flat[i:i + 65536, None, :] - pal_lab[None, :, :]) ** 2).sum(-1)
        out[i:i + 65536] = d.argmin(1)
    return out.reshape(lab.shape[:-1])


def build_palette(samples_srgb: np.ndarray, size: int = PALETTE_SIZE, seed: int = 7) -> np.ndarray:
    """SEED_COLOURS fixed, the rest found by k-means in OKLab over the sample pixels (fixed seed, so a rebuild gives the same palette)."""
    fixed = np.array(SEED_COLOURS, dtype=np.float64)
    lab = srgb8_to_oklab(samples_srgb.reshape(-1, 3))
    rng = np.random.default_rng(seed)
    if len(lab) > 200_000:
        lab = lab[rng.choice(len(lab), 200_000, replace=False)]
    fixed_lab = srgb8_to_oklab(fixed)
    k = size - len(fixed)
    free = lab[rng.choice(len(lab), k, replace=False)].copy()
    for _ in range(25):
        cent = np.concatenate([fixed_lab, free])
        lab_idx = nearest(lab, cent).astype(np.int64)
        for j in range(k):
            sel = lab[lab_idx == len(fixed) + j]
            if len(sel):
                free[j] = sel.mean(0)
    # back to sRGB through a fine search of the cube near each centre (OKLab has no closed-form inverse here worth carrying)
    grid = np.stack(np.meshgrid(*[np.arange(0, 256, 3)] * 3, indexing="ij"), -1).reshape(-1, 3).astype(np.float64)
    glab = srgb8_to_oklab(grid)
    free_rgb = grid[[int(((glab - f) ** 2).sum(1).argmin()) for f in free]]
    return np.clip(np.round(np.concatenate([fixed, free_rgb])), 0, 255).astype(np.uint8)


def palette_step(pal: np.ndarray) -> float:
    """Median distance (sRGB units) from each palette colour to its nearest neighbour."""
    p = pal.astype(np.float64)
    d = np.sqrt(((p[:, None] - p[None]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    return float(np.median(d.min(1)))


def quantise(srgb: np.ndarray, pal: np.ndarray, pal_lab: np.ndarray, step: float) -> np.ndarray:
    """sRGB floats [h,w,3] to palette indices with a light 4x4 ordered dither."""
    h, w = srgb.shape[:2]
    bay = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w, None]
    return nearest(srgb8_to_oklab(np.clip(srgb + bay * DITHER * step, 0, 255)), pal_lab)


def snap(rgb, pal: np.ndarray) -> tuple:
    """The palette colour nearest to one RGB colour (overlays are drawn in these)."""
    lab = srgb8_to_oklab(np.array(rgb, dtype=np.float64)[None])
    return tuple(int(v) for v in pal[int(nearest(lab, srgb8_to_oklab(pal.astype(np.float64)))[0])])


# ------------------------------------------------------------------------------------------------ sky, bloom, tone
def _blur(x: np.ndarray, sigma: float) -> np.ndarray:
    r = int(math.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    for axis in (0, 1):
        pad = [(0, 0)] * x.ndim
        pad[axis] = (r, r)
        xp = np.pad(x, pad, mode="edge")
        n = x.shape[axis]
        x = sum(k[i] * np.take(xp, range(i, i + n), axis=axis) for i in range(2 * r + 1))
    return x


class Sky:
    """The sky behind the geometry, in display-linear light: the gradient, twinkling stars and a ringed planet, both fixed in the world (at
    infinity), so they slide across the screen as the camera turns. Every twinkle repeats a whole number of times in the loop."""

    def __init__(self, seed: int = 11, frames: int = G.FRAMES):
        self.frames = frames
        r = random.Random(seed)
        self.grad = G.srgb_to_linear(G.sky_rows(G.H))[:, None, :] * np.ones((1, G.W, 1))
        n = 150
        az = np.array([r.uniform(-1.0, 1.0) for _ in range(n)])
        el = np.radians(1.0 + 18.0 * np.array([r.random() ** 0.7 for _ in range(n)]))
        self.dirs = np.stack([np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), np.sin(el)], -1)
        self.cycles = np.array([r.randint(3, 11) for _ in range(n)])
        self.phase = np.array([r.random() * 2 * math.pi for _ in range(n)])
        self.size = np.array([2 if r.random() < 0.15 else 1 for _ in range(n)])
        self.planet = self._planet()
        pa, pe = 0.55, math.radians(10.7)                  # centre near row 34, as on the old sky
        self.planet_dir = np.array([math.sin(pa) * math.cos(pe), math.cos(pa) * math.cos(pe), math.sin(pe)])

    @staticmethod
    def _planet() -> Image.Image:
        im = Image.new("RGBA", (80, 50), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx, cy, r = 40, 25, 22
        bands = [(70, 40, 120), (110, 60, 150), (150, 80, 160), (200, 110, 150), (240, 150, 140)]
        for y in range(cy - r, cy + r + 1):
            half = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
            band = bands[min(len(bands) - 1, max(0, (y - cy + r) * len(bands) // (2 * r + 1)))]
            shade = 0.55 + 0.45 * (1 - (y - cy + r) / (2 * r))
            d.line([cx - half, y, cx + half, y], fill=tuple(int(v * shade) for v in band) + (255,))
            if half > 2:
                d.point((cx + half, y), fill=(255, 190, 220, 255))
        d.ellipse([cx - 36, cy - 3, cx + 36, cy + 3], outline=(200, 150, 220, 255))
        d.line([cx - 21, cy - 2, cx + 21, cy - 2], fill=tuple(int(v * 0.7) for v in bands[2]) + (255,))
        return im

    def _screen(self, dirs: np.ndarray, n: int):
        _, yaw = G.camera(n)
        f, rt, up = G.basis(yaw)
        z = dirs @ f
        with np.errstate(divide="ignore", invalid="ignore"):
            col = G.W / 2 + G.F * (dirs @ rt) / z
            row = G.H / 2 - G.F * (dirs @ up) / z
        return col, row, z

    def frame(self, n: int) -> np.ndarray:
        """Display-linear sky [180,320,3] for loop frame n."""
        im = Image.fromarray(np.round(G.linear_to_srgb(self.grad)).astype(np.uint8), "RGB")
        col, row, z = self._screen(self.planet_dir[None], n)
        if z[0] > 0:
            im.paste(self.planet, (int(round(col[0])) - 40, int(round(row[0])) - 25), self.planet)
        d = ImageDraw.Draw(im)
        col, row, z = self._screen(self.dirs, n)
        tw = 0.55 + 0.45 * np.sin(2 * np.pi * self.cycles * n / self.frames + self.phase)
        for i in np.nonzero((z > 0) & (row < G.horizon_row() - 2))[0]:
            x, y = int(col[i]), int(row[i])
            if not (0 <= x < G.W and 0 <= y < G.H):
                continue
            c = int(255 * (0.55 + 0.45 * tw[i]))
            d.point((x, y), fill=(c, c, min(255, c + 12)))
            if self.size[i] == 2:
                d.point((x + 1, y), fill=(int(c * 0.6),) * 2 + (min(255, int(c * 0.6) + 8),))
                d.point((x, y + 1), fill=(int(c * 0.6),) * 2 + (min(255, int(c * 0.6) + 8),))
        return G.srgb_to_linear(np.asarray(im))


def finish(rgb: np.ndarray, alpha: np.ndarray, sky: np.ndarray) -> np.ndarray:
    """One Blender frame (scene-linear, premultiplied, fogged) plus the sky to display sRGB floats 0..255: bloom, tone map, then the sky
    behind whatever the geometry leaves uncovered. Fog was blended towards the sky's own colour before the tone map's inverse, so far
    geometry meets the sky without a seam."""
    rgb = rgb.astype(np.float64)
    a = alpha.astype(np.float64)[..., None]
    hot = np.maximum(rgb - BLOOM_THRESHOLD, 0.0)
    rgb = rgb + BLOOM_GAIN * (0.6 * _blur(hot, 1.5) + 0.4 * _blur(hot, 5.0))
    disp = G.tone(rgb) + (1.0 - np.clip(a, 0, 1)) * sky
    return G.linear_to_srgb(disp)


# ------------------------------------------------------------------------------------------------ building a loop
def smooth_bend(bend: np.ndarray, seconds: float = 0.5, fps: int = G.FPS) -> np.ndarray:
    """Circular moving average, so the lean stays periodic with the loop."""
    k = max(1, int(round(seconds * fps)))
    ext = np.concatenate([bend[-k:], bend, bend[:k]])
    c = np.convolve(ext, np.ones(k) / k, mode="same")
    return c[k:-k].astype(np.float32)


def write_loop(dest: Path, idx, palette, depth, road_cx, road_hw, road_dz, bend, horizon: float, meta: dict) -> dict:
    """Save loop.npz and manifest.json atomically; returns the manifest."""
    dest.mkdir(parents=True, exist_ok=True)
    tmp = dest / "loop.tmp.npz"
    np.savez_compressed(tmp, idx=idx.astype(np.uint8), palette=palette.astype(np.uint8), depth=depth.astype(np.uint8),
                        road_cx=road_cx.astype(np.float32), road_hw=road_hw.astype(np.float32), road_dz=road_dz.astype(np.float32),
                        bend=bend.astype(np.float32), horizon=np.float32(horizon))
    os.replace(tmp, dest / "loop.npz")
    man = {"name": dest.name, "frames": int(idx.shape[0]), "fps": G.FPS, "size": [int(idx.shape[2]), int(idx.shape[1])],
           "palette": int(len(palette)), "sha256": _sha(dest / "loop.npz"), "built": datetime.date.today().isoformat()}
    man.update(meta)
    (dest / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    return man


def build(frames_dir: Path, name: str) -> dict:
    n_all = G.FRAMES
    files = [frames_dir / f"f{n:04d}.npz" for n in range(n_all + 1)]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        sys.exit(f"{len(missing)} frames missing, first {missing[0]}")
    sky = Sky()
    print("finishing frames", flush=True)
    disp = np.empty((n_all + 1, G.H, G.W, 3), dtype=np.float32)
    depth = np.empty((n_all + 1, G.H, G.W), dtype=np.uint8)
    for n, f in enumerate(files):
        z = np.load(f)
        disp[n] = finish(z["rgb"], z["alpha"], sky.frame(n % n_all))
        depth[n] = z["depth"]
    seam = float(np.sqrt(np.mean((disp[n_all] - disp[0]) ** 2)) / 255.0)
    print(f"seam RMS {seam:.4%}", flush=True)
    if seam > SEAM_MAX:
        sys.exit(f"the loop does not join: frame {n_all} differs from frame 0 by {seam:.3%} RMS (limit {SEAM_MAX:.1%})")
    print("palette", flush=True)
    pick = np.linspace(0, n_all - 1, 60).astype(int)
    pal = build_palette(np.round(disp[pick]).astype(np.uint8))
    pal_lab = srgb8_to_oklab(pal.astype(np.float64))
    step = palette_step(pal)
    idx = np.empty((n_all, G.H, G.W), dtype=np.uint8)
    for n in range(n_all):
        idx[n] = quantise(disp[n].astype(np.float64), pal, pal_lab, step)
    sky_px = (depth[:n_all] == G.DEPTH_SKY) & (np.roll(depth[:n_all], -1, 0) == G.DEPTH_SKY)
    changed = (idx != np.roll(idx, -1, 0)) & sky_px
    flicker = float(changed.sum() / max(1, sky_px.sum()))
    print(f"sky flicker {flicker:.3%}", flush=True)
    if flicker > FLICKER_MAX:
        sys.exit(f"the dither shimmers: {flicker:.2%} of sky pixels change each frame (limit {FLICKER_MAX:.0%})")
    rows = [G.road_rows(n) for n in range(n_all)]
    assets = json.loads((HERE / "blender" / "assets.json").read_text())
    meta = {"seam_rms": round(seam, 6), "sky_flicker": round(flicker, 6), "palette_step": round(step, 2),
            "blender": os.environ.get("BLENDER_VERSION", "5.2.3"), "scene": "blender/racer_highway.py",
            "assets": [{"path": a["path"], "sha256": a["sha256"]} for a in assets["assets"]]}
    man = write_loop(root() / name, idx, pal, depth[:n_all], np.stack([r[0] for r in rows]), np.stack([r[1] for r in rows]),
                     np.stack([r[2] for r in rows]), smooth_bend(G.bends()), G.horizon_row(), meta)
    Image.fromarray(pal[idx[0]]).resize((G.W * 3, G.H * 3), Image.NEAREST).save(root() / name / "frame0.png")
    print(json.dumps(man, indent=1))
    return man


# ------------------------------------------------------------------------------------------------ playing a loop
@dataclass
class Loop:
    name: str
    idx: np.ndarray
    palette: np.ndarray
    depth: np.ndarray
    road_cx: np.ndarray
    road_hw: np.ndarray
    road_dz: np.ndarray
    bend: np.ndarray
    horizon: float
    manifest: dict

    @property
    def frames(self) -> int:
        return int(self.idx.shape[0])

    def rgb(self, n: int) -> np.ndarray:
        return self.palette[self.idx[n % self.frames]]

    def sky(self, n: int) -> np.ndarray:
        return self.depth[n % self.frames] == G.DEPTH_SKY

    def depth_m(self, n: int) -> np.ndarray:
        return G.depth_of_code(self.depth[n % self.frames])

    def snap(self, rgb) -> tuple:
        return snap(rgb, self.palette)


_CACHE: dict[str, Loop] = {}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def path(name: str) -> Path:
    return root() / name


def exists(name: str) -> bool:
    return (path(name) / "loop.npz").exists() and (path(name) / "manifest.json").exists()


def load(name: str) -> Loop:
    """The loop called name, checked against its manifest's hash; loaded once per process (each render worker has its own copy, about
    100 MB for a 900-frame loop)."""
    key = f"{root()}/{name}"
    if key in _CACHE:
        return _CACHE[key]
    d = path(name)
    if not exists(name):
        raise FileNotFoundError(f"background loop {name!r} is not built: no {d}/loop.npz (run tools/chiptune-radio/blender/build_loop.sh, or set AMBIENT_BG=code)")
    man = json.loads((d / "manifest.json").read_text())
    if _sha(d / "loop.npz") != man.get("sha256"):
        raise ValueError(f"background loop {name!r}: loop.npz does not match its manifest's sha256")
    z = np.load(d / "loop.npz")
    lp = Loop(name, z["idx"], z["palette"], z["depth"], z["road_cx"], z["road_hw"], z["road_dz"], z["bend"], float(z["horizon"]), man)
    _CACHE[key] = lp
    return lp


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--frames", required=True)
    b.add_argument("--name", required=True)
    c = sub.add_parser("check")
    c.add_argument("name")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        build(Path(a.frames), a.name)
    else:
        lp = load(a.name)
        print(json.dumps(lp.manifest, indent=1))
        print(f"ok: {lp.frames} frames, {len(lp.palette)} colours")


if __name__ == "__main__":
    main()
