"""Flat illustrations for the /games/ tiles, one per game, drawn in two tints of the game's own colour.
Classes (set in site/games/games-ui.css): a1 deep tint, a2 light tint, a3 outline, a4 ink, a5 white, a6 thick stroke.
Parts that drift on hover carry .mv or .mv2. Each returns an <svg> string on a 200 x 140 canvas.
"""

OPEN = '<svg class="art" viewBox="0 0 200 140" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">'


def _r(x, y, w, h, c, rx=6, extra=""):
    return f'<rect class="{c}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"{extra}/>'


def linkle():
    rows = ["a1 a2 a3 a3 a3", "a2 a2 a1 a3 a3", "a1 a1 a1 a1 a1"]
    out = [OPEN]
    for r, row in enumerate(rows):
        for c, cls in enumerate(row.split()):
            cls_ = cls if cls != "a3" else "a3"
            x, y = 22 + c * 32, 22 + r * 32
            if cls_ == "a3":
                out.append(f'<rect class="a3" x="{x+1.5}" y="{y+1.5}" width="25" height="25" rx="6"/>')
            else:
                out.append(_r(x, y, 28, 28, cls_, 6))
    out.append('<g class="mv"><rect class="a5" x="22" y="118" width="28" height="8" rx="4"/><rect class="a5" x="56" y="118" width="12" height="8" rx="4" opacity=".6"/></g>')
    out.append("</svg>")
    return "".join(out)


def quadlink():
    out = [OPEN]
    pat = ["a1 a2 a3 a1 a3 a3 a3 a3 a3", "a3 a3 a3 a2 a1 a2 a3 a3 a3", "a3 a1 a3 a3 a2 a3 a1 a1 a1", "a2 a2 a2 a3 a3 a3 a1 a2 a3"]
    for b in range(4):
        ox, oy = 20 + (b % 2) * 84, 14 + (b // 2) * 62
        for i, cls in enumerate(pat[b].split()):
            x, y = ox + (i % 3) * 19, oy + (i // 3) * 19
            if cls == "a3":
                out.append(f'<rect class="a3" x="{x+1}" y="{y+1}" width="15" height="15" rx="3.5"/>')
            else:
                out.append(_r(x, y, 17, 17, cls, 3.5))
    out.append("</svg>")
    return "".join(out)


def daily_five():
    out = [OPEN, '<circle class="a2" cx="100" cy="58" r="40"/>']
    out.append('<g class="mv"><path class="a6" d="M85 50c0-9 7-15 16-15 9 0 16 6 16 14 0 12-16 12-16 25"/></g>')
    out.append('<circle class="a1" cx="101" cy="86" r="5.5"/>')
    for i in range(5):
        out.append(f'<circle class="{"a1" if i < 3 else "a5"}" cx="{60 + i * 20}" cy="121" r="6"{"" if i < 3 else " opacity=\".55\""}/>')
    out.append("</svg>")
    return "".join(out)


def daily_photo():
    out = [OPEN, '<rect class="a2" x="24" y="18" width="152" height="104" rx="12"/>']
    out.append('<circle class="a5" cx="140" cy="48" r="13"/>')
    out.append('<path class="a1" d="M24 112l42-46 30 30 22-22 58 50v10a12 12 0 0 1-12 12H36a12 12 0 0 1-12-12z"/>')
    out.append('<path class="a4" opacity=".28" d="M96 96l22-22 58 50v-4L118 74z"/>')
    out.append('<g class="mv"><path class="a4" d="M158 74c-9 0-16 7-16 16 0 12 16 26 16 26s16-14 16-26c0-9-7-16-16-16z"/><circle class="a5" cx="158" cy="90" r="6"/></g>')
    out.append("</svg>")
    return "".join(out)


def daily_chess():
    out = [OPEN]
    for r in range(5):
        for c in range(8):
            if (r + c) % 2 == 0:
                out.append(f'<rect class="a2" x="{c * 25}" y="{r * 28}" width="25" height="28" opacity=".5"/>')
    out.append('<g class="mv">'
               '<path class="a4" d="M70 112h60v-10H70zM76 100h48l-5-34h-38zM68 66h64V48h-12v8h-10v-8h-16v8H80v-8H68z"/>'
               '<rect class="a1" x="62" y="112" width="76" height="12" rx="4"/>'
               '</g>')
    out.append('<circle class="a5" cx="158" cy="40" r="7" opacity=".9"/>')
    out.append("</svg>")
    return "".join(out)


def sudoku():
    out = [OPEN, '<rect class="a2" x="42" y="14" width="116" height="116" rx="10"/>']
    for i in range(1, 9):
        w = 3 if i % 3 == 0 else 1
        out.append(f'<rect class="a1" x="{42 + i * 12.89 - w / 2:.1f}" y="14" width="{w}" height="116"/>')
        out.append(f'<rect class="a1" x="42" y="{14 + i * 12.89 - w / 2:.1f}" width="116" height="{w}"/>')
    digs = {(0, 0): 5, (0, 4): 7, (1, 2): 3, (2, 6): 8, (3, 1): 4, (4, 4): 1, (4, 7): 6, (5, 5): 9, (6, 2): 2, (7, 6): 5, (8, 3): 7, (8, 8): 3, (2, 1): 6, (6, 7): 4}
    for (r, c), d in digs.items():
        out.append(f'<text class="a4" x="{42 + c * 12.89 + 6.4:.1f}" y="{14 + r * 12.89 + 9.6:.1f}" text-anchor="middle" font-size="10">{d}</text>')
    out.append('<g class="mv"><rect class="a3" x="42" y="14" width="116" height="116" rx="10"/></g>')
    out.append("</svg>")
    return "".join(out)


def crossword():
    out = [OPEN]
    mask = ["0001000", "0110100", "1000011", "0010000", "0000101"]
    for r, row in enumerate(mask):
        for c, ch in enumerate(row):
            x, y = 16 + c * 25.5, 22 + r * 20.5
            out.append(_r(f"{x:.1f}", f"{y:.1f}", 24, 19.5, "a1" if ch == "1" else "a2", 3))
    for (r, c, n) in [(0, 0, 1), (1, 3, 3), (2, 1, 4), (3, 3, 5), (4, 0, 6)]:
        out.append(f'<text class="a4" x="{18 + c * 25.5:.1f}" y="{31 + r * 20.5:.1f}" font-size="7">{n}</text>')
    out.append('<g class="mv"><rect class="a5" x="41.5" y="22" width="22" height="19" rx="3" opacity=".9"/><text class="a4" x="52.5" y="37" font-size="14" text-anchor="middle">A</text></g>')
    out.append("</svg>")
    return "".join(out)


def daily_stars():
    out = [OPEN, '<circle class="a2" cx="70" cy="68" r="38"/>', '<circle class="a1" cx="86" cy="56" r="34"/>']
    out.append('<g class="mv">' + _star(150, 38, 17, "a5") + "</g>")
    out.append('<g class="mv2">' + _star(142, 98, 10, "a2") + _star(36, 28, 7, "a5") + "</g>")
    out.append('<circle class="a5" cx="108" cy="116" r="2.8"/><circle class="a5" cx="174" cy="72" r="2.6"/><circle class="a5" cx="24" cy="104" r="2.4"/>')
    out.append("</svg>")
    return "".join(out)


def _star(cx, cy, r, cls):
    k = r * 0.28
    return (f'<path class="{cls}" d="M{cx} {cy - r}L{cx + k} {cy - k}L{cx + r} {cy}L{cx + k} {cy + k}L{cx} {cy + r}'
            f'L{cx - k} {cy + k}L{cx - r} {cy}L{cx - k} {cy - k}Z"/>')


ART = {"linkle": linkle, "quadlink": quadlink, "daily-five": daily_five, "daily-photo": daily_photo,
       "daily-chess": daily_chess, "sudoku": sudoku, "crossword": crossword, "daily-stars": daily_stars}


def art(slug):
    return ART[slug]()
