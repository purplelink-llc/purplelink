"""A 5x7 pixel font for the stream's text, drawn in code (nothing to license) and scaled by whole numbers so every letter stays
crisp at 1080p. The scene's old text used PIL's built-in 6x11 bitmap font on the 320x180 canvas, which is blurry once the frame is
enlarged six times; this draws each letter at the size it will actually be seen.

    im = text_image("FOCUS 24:13", scale=8, fill=(244, 236, 250))      # an RGBA image, cached
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image

GLYPH_W, GLYPH_H, GAP = 5, 7, 1

_RAW = """
A 01110 10001 10001 11111 10001 10001 10001
B 11110 10001 10001 11110 10001 10001 11110
C 01110 10001 10000 10000 10000 10001 01110
D 11110 10001 10001 10001 10001 10001 11110
E 11111 10000 10000 11110 10000 10000 11111
F 11111 10000 10000 11110 10000 10000 10000
G 01110 10001 10000 10111 10001 10001 01111
H 10001 10001 10001 11111 10001 10001 10001
I 01110 00100 00100 00100 00100 00100 01110
J 00111 00010 00010 00010 00010 10010 01100
K 10001 10010 10100 11000 10100 10010 10001
L 10000 10000 10000 10000 10000 10000 11111
M 10001 11011 10101 10101 10001 10001 10001
N 10001 11001 10101 10011 10001 10001 10001
O 01110 10001 10001 10001 10001 10001 01110
P 11110 10001 10001 11110 10000 10000 10000
Q 01110 10001 10001 10001 10101 10010 01101
R 11110 10001 10001 11110 10100 10010 10001
S 01111 10000 10000 01110 00001 00001 11110
T 11111 00100 00100 00100 00100 00100 00100
U 10001 10001 10001 10001 10001 10001 01110
V 10001 10001 10001 10001 10001 01010 00100
W 10001 10001 10001 10101 10101 11011 10001
X 10001 10001 01010 00100 01010 10001 10001
Y 10001 10001 01010 00100 00100 00100 00100
Z 11111 00001 00010 00100 01000 10000 11111
0 01110 10001 10011 10101 11001 10001 01110
1 00100 01100 00100 00100 00100 00100 01110
2 01110 10001 00001 00010 00100 01000 11111
3 11110 00001 00001 01110 00001 00001 11110
4 00010 00110 01010 10010 11111 00010 00010
5 11111 10000 11110 00001 00001 10001 01110
6 00110 01000 10000 11110 10001 10001 01110
7 11111 00001 00010 00100 01000 01000 01000
8 01110 10001 10001 01110 10001 10001 01110
9 01110 10001 10001 01111 00001 00010 01100
: 00000 00100 00100 00000 00100 00100 00000
. 00000 00000 00000 00000 00000 01100 01100
, 00000 00000 00000 00000 00100 00100 01000
- 00000 00000 00000 11111 00000 00000 00000
+ 00000 00100 00100 11111 00100 00100 00000
! 00100 00100 00100 00100 00100 00000 00100
/ 00001 00010 00010 00100 01000 01000 10000
' 00100 00100 01000 00000 00000 00000 00000
? 01110 10001 00001 00110 00100 00000 00100
# 01010 01010 11111 01010 11111 01010 01010
( 00010 00100 01000 01000 01000 00100 00010
) 01000 00100 00010 00010 00010 00100 01000
& 01100 10010 10100 01000 10101 10010 01101
% 11001 11010 00010 00100 01000 01011 10011
"""

GLYPHS: dict[str, np.ndarray] = {" ": np.zeros((GLYPH_H, GLYPH_W), bool)}
for _line in _RAW.strip().splitlines():
    _ch, *_rows = _line.split()
    GLYPHS[_ch] = np.array([[c == "1" for c in row] for row in _rows], bool)


def width(text: str, scale: int) -> int:
    """Pixels wide: every letter is 5 columns and a 1-column gap, scaled."""
    return max(0, (GLYPH_W + GAP) * len(text) - GAP) * scale


def height(scale: int) -> int:
    return GLYPH_H * scale


@lru_cache(maxsize=512)
def text_image(text: str, scale: int, fill: tuple, shadow: tuple | None = (14, 10, 22)) -> Image.Image:
    """The text as an RGBA image (transparent background). Upper case only; a letter this font lacks is drawn as '?'.
    A one-pixel-at-this-scale shadow, down and to the right, keeps it readable over any part of the scene."""
    text = text.upper()
    cols = (GLYPH_W + GAP) * len(text) - GAP if text else 0
    bits = np.zeros((GLYPH_H, max(cols, 1)), bool)
    for n, ch in enumerate(text):
        bits[:, n * (GLYPH_W + GAP): n * (GLYPH_W + GAP) + GLYPH_W] = GLYPHS.get(ch, GLYPHS["?"])
    big = np.kron(bits, np.ones((scale, scale), bool))
    pad = scale if shadow else 0
    out = np.zeros((big.shape[0] + pad, big.shape[1] + pad, 4), np.uint8)
    if shadow:
        out[pad:, pad:][big] = (*shadow, 255)
    out[: big.shape[0], : big.shape[1]][big] = (*fill, 255)
    return Image.fromarray(out, "RGBA")


def draw(im: Image.Image, x: int, y: int, text: str, scale: int, fill: tuple, shadow: tuple | None = (14, 10, 22)) -> int:
    """Paste `text` onto `im` at (x, y); returns the x just past it."""
    t = text_image(text, scale, tuple(fill), tuple(shadow) if shadow else None)
    im.paste(t, (x, y), t)
    return x + width(text, scale)
