"""Geometry of the racer's night skyway, shared by the Blender scene script (racer_highway.py), the loop builder (bgloop.py) and the tests.
Pure numpy, no bpy, so it runs inside Blender's Python and the normal one alike.

The world: +Y is forward, +X right, +Z up, metres. The road's centre line is x(v) = A sin(2 pi v / L) + B sin(4 pi v / L + PHI) at forward
coordinate v, so everything repeats exactly when v grows by L. The camera drives along it at constant arc-length speed and covers one period
(S metres of road) in FRAMES frames, which makes frame FRAMES the same picture as frame 0 shifted by L: the loop joins with no crossfade.

Screen coordinates are on the 320x180 art grid: column c, row r, pixel centres at c + 0.5, r + 0.5.
"""
from __future__ import annotations

import math

import numpy as np

FPS = 30
FRAMES = 900                      # 30 s
L = 1760.0                        # forward period, metres
A, B, PHI = 42.0, 16.0, 1.0       # the two bends' sizes and the second one's phase
CAM_H = 3.2                       # camera height above the road
PITCH = math.radians(3.6)         # looking down a little, so the horizon sits near row 76
HFOV = math.radians(72.0)
W, H = 320, 180                   # art grid
RENDER_W, RENDER_H = 1280, 720    # Blender's output; each 4x4 block becomes one art pixel
F = (W / 2) / math.tan(HFOV / 2)  # focal length in art pixels
LANE = 3.6
ROAD_HW = 2 * LANE                # half the width of the four lanes
RUMBLE = 0.9                      # the striped kerb outside each edge
EDGE = ROAD_HW + RUMBLE           # what road_hw measures to
LOOK = 18.0                       # the camera aims along the road this far ahead, which smooths its turn
BEND_AHEAD = 160.0                # how far ahead "the bend" is judged, for the craft's lean
FAR = 1400.0                      # nothing farther than this is drawn; fog is complete before it
FOG_D = 520.0                     # fog: 1 - exp(-d / FOG_D), forced to 1 at FAR
HAZE_ROWS = ((0, (8, 6, 30)), (34, (30, 14, 70)), (76, (140, 40, 120)))   # the sky gradient, sRGB, by row; constant below the last row
SECTIONS = {"causeway": (0.0, 0.40), "gantry": (0.40, 0.60), "canyon": (0.60, 1.0)}   # fractions of the period


def centre_x(v):
    v = np.asarray(v, dtype=np.float64)
    return A * np.sin(2 * np.pi * v / L) + B * np.sin(4 * np.pi * v / L + PHI)


def slope(v):
    v = np.asarray(v, dtype=np.float64)
    return A * 2 * np.pi / L * np.cos(2 * np.pi * v / L) + B * 4 * np.pi / L * np.cos(4 * np.pi * v / L + PHI)


_N = 200_001
_V = np.linspace(0.0, L, _N)
_DS = np.sqrt(1.0 + slope(_V) ** 2)
_S = np.concatenate(([0.0], np.cumsum((_DS[1:] + _DS[:-1]) * 0.5 * (L / (_N - 1)))))
S = float(_S[-1])                 # arc length of one period
SPEED = S / (FRAMES / FPS)        # metres a second


def v_of_s(s):
    """Forward coordinate at arc length s (any s; one period is S long and L forward)."""
    s = np.asarray(s, dtype=np.float64)
    k = np.floor(s / S)
    return np.interp(s - k * S, _S, _V) + k * L


def s_of_v(v):
    v = np.asarray(v, dtype=np.float64)
    k = np.floor(v / L)
    return np.interp(v - k * L, _V, _S) + k * S


def point(s):
    """World (x, y) of the road centre at arc length s."""
    v = v_of_s(s)
    return np.stack([centre_x(v), v], axis=-1)


def heading(s):
    """Angle of the road from +Y towards +X, radians."""
    return np.arctan(slope(v_of_s(s)))


def section(v) -> str:
    f = (float(v) / L) % 1.0
    for name, (a, b) in SECTIONS.items():
        if a <= f < b:
            return name
    return "canyon"


def camera(n: int):
    """Camera at frame n: position (x, y, z) and yaw (radians, from +Y towards +X). Pitch is PITCH, roll is zero."""
    s = S * n / FRAMES
    x, y = point(s)
    return (float(x), float(y), CAM_H), float(heading(s + LOOK))


def basis(yaw: float):
    """Camera forward, right and up vectors."""
    cp, sp = math.cos(PITCH), math.sin(PITCH)
    f = np.array([math.sin(yaw) * cp, math.cos(yaw) * cp, -sp])
    r = np.array([math.cos(yaw), -math.sin(yaw), 0.0])
    u = np.cross(r, f)
    return f, r, u


def project(pts, n: int):
    """World points [..., 3] to art-grid (col, row, depth along the view). Points behind the camera get NaN."""
    (cx, cy, cz), yaw = camera(n)
    f, r, u = basis(yaw)
    d = np.asarray(pts, dtype=np.float64) - np.array([cx, cy, cz])
    z = d @ f
    with np.errstate(divide="ignore", invalid="ignore"):
        col = W / 2 + F * (d @ r) / z
        row = H / 2 - F * (d @ u) / z
    bad = z <= 0.05
    col = np.where(bad, np.nan, col)
    row = np.where(bad, np.nan, row)
    return col, row, z


def horizon_row() -> float:
    """Row (fractional) of the horizon: the same in every frame, as the camera never rolls."""
    return H / 2 - F * math.tan(PITCH)


def road_rows(n: int):
    """Per art-grid row: road centre column and half width in columns (to the outer kerb edge), NaN where the row has no road (above the
    horizon or past FAR). Also the depth (metres along the view) of the road at that row, for placing the rival."""
    s0 = S * n / FRAMES
    ds = np.geomspace(1.5, FAR, 900)
    s = s0 + ds
    v = v_of_s(s)
    x, y = centre_x(v), v
    hd = np.arctan(slope(v))
    nx, ny = np.cos(hd), -np.sin(hd)                      # the road's right-hand normal
    c = np.stack([x, y, np.zeros_like(x)], -1)
    rr = np.stack([x + nx * EDGE, y + ny * EDGE, np.zeros_like(x)], -1)
    ll = np.stack([x - nx * EDGE, y - ny * EDGE, np.zeros_like(x)], -1)
    cc, rc, zc = project(c, n)
    cr, _, _ = project(rr, n)
    cl, _, _ = project(ll, n)
    ok = np.isfinite(rc)
    rc, cc, cr, cl, zc = rc[ok], cc[ok], cr[ok], cl[ok], zc[ok]
    rows = np.arange(H) + 0.5
    order = np.argsort(rc)                                 # row grows as the road comes nearer
    rc, cc, cr, cl, zc = rc[order], cc[order], cr[order], cl[order], zc[order]
    cx = np.interp(rows, rc, (cl + cr) / 2, left=np.nan, right=np.nan)
    hw = np.interp(rows, rc, np.abs(cr - cl) / 2, left=np.nan, right=np.nan)
    dz = np.interp(rows, rc, zc, left=np.nan, right=np.nan)
    below = rows > rc[-1]                                  # rows nearer than the nearest sample: extrapolate from the last two
    if below.any() and len(rc) > 1:
        k = (rows[below] - rc[-1]) / max(1e-6, rc[-1] - rc[-2])
        cx[below] = ((cl + cr) / 2)[-1] + k * (((cl + cr) / 2)[-1] - ((cl + cr) / 2)[-2])
        hw[below] = (np.abs(cr - cl) / 2)[-1] + k * ((np.abs(cr - cl) / 2)[-1] - (np.abs(cr - cl) / 2)[-2])
        dz[below] = zc[-1]
    return cx.astype(np.float32), hw.astype(np.float32), dz.astype(np.float32)


def bends():
    """How the road bends ahead in every frame, -1 (left) to 1 (right): the heading change over the next BEND_AHEAD metres, scaled by the
    loop's largest. The craft leans with it, smoothed by the theme."""
    s = S * np.arange(FRAMES) / FRAMES
    d = heading(s + BEND_AHEAD) - heading(s + LOOK)
    return (d / np.max(np.abs(d))).astype(np.float32)


# ---------------------------------------------------------------- depth code, fog, sky (numpy, used per frame by the scene script)
DEPTH_NEAR, DEPTH_SKY = 0.5, 255


def depth_code(d):
    """Depth in metres to uint8: log scale from DEPTH_NEAR to FAR over 0..254; 255 means sky (nothing there)."""
    d = np.asarray(d, dtype=np.float64)
    q = np.round(np.log(np.clip(d, DEPTH_NEAR, FAR) / DEPTH_NEAR) / math.log(FAR / DEPTH_NEAR) * 254)
    return np.where(np.isfinite(d) & (d < FAR), q, DEPTH_SKY).astype(np.uint8)


def depth_of_code(q):
    q = np.asarray(q, dtype=np.float64)
    return np.where(q >= DEPTH_SKY, np.inf, DEPTH_NEAR * np.exp(q / 254 * math.log(FAR / DEPTH_NEAR)))


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(np.asarray(x, dtype=np.float64), 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055) * 255.0


def sky_rows(h: int = H) -> np.ndarray:
    """The sky gradient as sRGB floats, one colour per row of an h-row image (art grid or render)."""
    k = h / H
    out = np.zeros((h, 3))
    ys = np.arange(h) / k
    pts = HAZE_ROWS
    for i in range(3):
        out[:, i] = np.interp(ys, [p[0] for p in pts], [p[1][i] for p in pts])
    return out


K_TONE = 1.0                      # tone map applied by bgloop: display = 1 - exp(-K_TONE * scene), per channel, linear light


def tone(x):
    return 1.0 - np.exp(-K_TONE * np.maximum(np.asarray(x, dtype=np.float64), 0.0))


def untone(y):
    """Inverse of tone(): the scene-linear value that tone-maps to display-linear y (y < 1)."""
    return -np.log(1.0 - np.clip(np.asarray(y, dtype=np.float64), 0.0, 0.999)) / K_TONE


def sky_scene_linear(h: int = H) -> np.ndarray:
    """The sky gradient in scene-linear light, so fogged geometry and the sky behind it tone-map to the same colour."""
    return untone(srgb_to_linear(sky_rows(h)))


def fog_amount(d):
    d = np.asarray(d, dtype=np.float64)
    f = 1.0 - np.exp(-d / FOG_D)
    edge = np.clip((d - FAR * 0.8) / (FAR * 0.2), 0.0, 1.0)  # forced to 1 by FAR, so nothing pops in at the far clip
    return np.where(np.isfinite(d), f + (1 - f) * edge * edge, 1.0)
