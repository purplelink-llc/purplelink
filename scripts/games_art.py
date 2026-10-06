"""Flat illustrations for the /games/ tiles, one per game, drawn in two tints of the game's own colour.
Classes (set in site/games/games-ui.css): a1 deep tint, a2 light tint, a3 outline, a4 ink, a5 white, a6 thick stroke.
Parts that drift on hover carry .mv or .mv2. Each returns an <svg> string on a 200 x 140 canvas.
"""

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import games_logos as logos

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


def chess_puzzles():
    out = [OPEN]
    for r in range(5):
        for c in range(8):
            if (r + c) % 2 == 0:
                out.append(f'<rect class="a2" x="{c * 25}" y="{r * 28}" width="25" height="28" opacity=".45"/>')
    out.append('<g class="mv"><path class="a4" d="M52 118h46v-8H52zM56 108h38l-4-26H60zM50 82h50V66h-9v6h-8v-6H67v6h-8v-6h-9z"/></g>')
    out.append('<g class="mv2"><path class="a5" d="M146 112V52M126 74l20-22 20 22" fill="none" stroke="#fff" stroke-width="11" stroke-linecap="round" stroke-linejoin="round" style="stroke:var(--gc-ink)"/></g>'.replace(' style="stroke:var(--gc-ink)"', '').replace('stroke="#fff"', 'stroke="currentColor"').replace('class="a5"', 'class="a5 ar"'))
    out.append("</svg>")
    return "".join(out)


def sudoku_unlimited():
    out = [OPEN, '<rect class="a2" x="36" y="16" width="128" height="108" rx="10"/>']
    for i in range(1, 9):
        w = 3 if i % 3 == 0 else 1
        out.append(f'<rect class="a1" x="{36 + i * 14.22 - w / 2:.1f}" y="16" width="{w}" height="108"/>')
    for i in range(1, 9):
        w = 3 if i % 3 == 0 else 1
        out.append(f'<rect class="a1" x="36" y="{16 + i * 12 - w / 2:.1f}" width="128" height="{w}"/>')
    out.append('<g class="mv"><path class="a6" d="M70 70c0-9 6-14 13-14 13 0 17 28 30 28 7 0 13-5 13-14s-6-14-13-14c-13 0-17 28-30 28-7 0-13-5-13-14z" style="stroke-width:9"/></g>'.replace(' style="stroke-width:9"', ''))
    out.append("</svg>")
    return "".join(out)


def leaderboard():
    out = [OPEN]
    out.append(_r(70, 56, 30, 66, "a1", 5)); out.append(_r(104, 34, 32, 88, "a2", 5)); out.append(_r(140, 72, 30, 50, "a1", 5))
    for x, y, t in ((85, 80, "2"), (120, 62, "1"), (155, 94, "3")):
        out.append(f'<text class="a4" x="{x}" y="{y}" text-anchor="middle" font-size="20">{t}</text>')
    out.append('<g class="mv">' + _star(120, 18, 11, "a5") + "</g>")
    out.append('<g class="mv2"><circle class="a5" cx="44" cy="48" r="4"/><circle class="a5" cx="172" cy="40" r="3"/><circle class="a2" cx="30" cy="96" r="3"/></g>')
    out.append("</svg>")
    return "".join(out)


def landlink():
    out = [OPEN, '<circle class="a2" cx="100" cy="70" r="54"/>']
    out.append('<g class="mv"><path class="a1" d="M70 44c8-8 22-10 30-4 6 5 2 12-6 14-9 2-8 10-16 12-8 1-14-8-8-22zM108 74c8-4 18-2 22 6 4 8-2 16-10 18-9 2-8-8-14-12-5-4-3-9 2-12z"/></g>')
    out.append('<g class="mv2"><path class="a1" d="M128 40c6-3 14 0 14 6s-8 8-13 5-4-8-1-11z"/></g>')
    out.append('<path class="a3" d="M46 70h108M100 16c20 15 28 33 28 54s-8 39-28 54M100 16C80 31 72 49 72 70s8 39 28 54" fill="none"/>')
    out.append('<g class="mv"><path class="a4" d="M146 34c-8 0-14 6-14 14 0 11 14 24 14 24s14-13 14-24c0-8-6-14-14-14z"/><circle class="a5" cx="146" cy="48" r="5"/></g>')
    out.append("</svg>")
    return "".join(out)


def atomlink():
    out = [OPEN]
    for rot in (0, 60, 120):
        out.append(f'<ellipse class="a3" cx="100" cy="70" rx="64" ry="24" transform="rotate({rot} 100 70)"/>')
    out.append('<g class="mv"><circle class="a5" cx="100" cy="70" r="13"/><circle class="a1" cx="100" cy="70" r="7"/></g>')
    for (x, y) in ((164, 70), (68, 14), (68, 126)):
        out.append(f'<circle class="a4" cx="{x}" cy="{y}" r="7"/>')
    out.append('<g class="mv2"><circle class="a2" cx="36" cy="70" r="5"/><circle class="a2" cx="132" cy="14" r="5"/><circle class="a2" cx="132" cy="126" r="5"/></g>')
    out.append("</svg>")
    return "".join(out)


def prizelink():
    out = [OPEN]
    out.append('<path class="a1" d="M70 86l-14 44 44-20 44 20-14-44z"/>')
    out.append('<g class="mv"><circle class="a5" cx="100" cy="58" r="42"/><circle class="a2" cx="100" cy="58" r="33"/>' + _star(100, 58, 22, "a1") + "</g>")
    out.append('<g class="mv2"><circle class="a5" cx="40" cy="30" r="4"/><circle class="a5" cx="162" cy="24" r="3"/><circle class="a2" cx="170" cy="86" r="4"/></g>')
    out.append("</svg>")
    return "".join(out)


def citylink():
    out = [OPEN]
    heights = [(18, 70), (42, 96), (66, 58), (90, 112), (114, 82), (138, 100), (160, 64)]
    for x, h in heights:
        out.append(_r(x, 124 - h, 20, h, "a1" if (x // 24) % 2 else "a2", 3))
    for x, h in heights:
        for y in range(124 - h + 10, 118, 16):
            out.append(f'<rect class="a5" x="{x + 5}" y="{y}" width="4" height="6" rx="1" opacity=".75"/><rect class="a5" x="{x + 12}" y="{y}" width="4" height="6" rx="1" opacity=".75"/>')
    out.append('<rect class="a4" x="8" y="124" width="184" height="6" rx="3"/>')
    out.append('<g class="mv"><circle class="a5" cx="168" cy="26" r="13"/></g>')
    out.append("</svg>")
    return "".join(out)


def peaklink():
    out = [OPEN, '<g class="mv2"><circle class="a5" cx="158" cy="30" r="13"/></g>']
    out.append('<path class="a2" d="M0 124L52 52l26 34 30-48 62 86z"/>')
    out.append('<g class="mv"><path class="a1" d="M40 124L96 36l60 88z"/><path class="a5" d="M96 36l-15 23 9-5 6 8 7-8 9 5z"/></g>')
    out.append('<path class="a4" opacity=".28" d="M96 36l60 88H96z"/>')
    out.append("</svg>")
    return "".join(out)


def codelink():
    out = [OPEN, _r(22, 18, 156, 104, "a1", 12), '<rect class="a4" x="22" y="18" width="156" height="22" rx="12"/><rect class="a4" x="22" y="30" width="156" height="10"/>']
    for x in (36, 48, 60):
        out.append(f'<circle class="a5" cx="{x}" cy="29" r="3.2"/>')
    lines = [(38, 54, 36, "a2"), (58, 54, 70, "a5"), (38, 70, 58, "a2"), (50, 86, 46, "a5"), (38, 102, 30, "a2"), (74, 102, 40, "a5")]
    for x, y, w, c in lines:
        out.append(f'<rect class="{c}" x="{x}" y="{y}" width="{w}" height="8" rx="4"/>')
    out.append('<g class="mv"><rect class="a5" x="130" y="98" width="8" height="16" rx="2"/></g>')
    out.append("</svg>")
    return "".join(out)


def thinkerlink():
    out = [OPEN]
    out.append('<g class="mv"><path class="a2" d="M82 18h36v34l34 62a8 8 0 0 1-7 12H55a8 8 0 0 1-7-12l34-62z"/><path class="a1" d="M64 92h72l16 30a8 8 0 0 1-7 12H55a8 8 0 0 1-7-12z" opacity=".95"/><rect class="a5" x="78" y="12" width="44" height="10" rx="5"/></g>')
    out.append('<g class="mv2"><circle class="a5" cx="96" cy="110" r="6"/><circle class="a5" cx="116" cy="100" r="4.5"/><circle class="a5" cx="108" cy="122" r="3.5"/></g>')
    out.append('<g class="mv2"><circle class="a5" cx="150" cy="30" r="5" opacity=".8"/><circle class="a5" cx="168" cy="52" r="3.5" opacity=".7"/><circle class="a2" cx="34" cy="40" r="4"/></g>')
    out.append("</svg>")
    return "".join(out)


def riverlink():
    out = [OPEN, '<path class="a2" d="M0 120c30-20 50-6 74-24s30-40 60-48 50 6 66-6V140H0z"/>']
    out.append('<path class="a6" d="M16 20c28 6 24 28 50 34s40-8 62 6 24 40 62 46" style="stroke-width:12"/>'.replace(' style="stroke-width:12"', ''))
    out.append('<g class="mv"><path class="a5" d="M146 30l10 14-10 14-10-14z" opacity=".95"/></g>')
    out.append('<g class="mv2"><circle class="a5" cx="44" cy="96" r="5" opacity=".8"/><circle class="a5" cx="168" cy="104" r="4" opacity=".7"/></g>')
    out.append("</svg>")
    return "".join(out)


def wildlink():
    out = [OPEN]
    out.append('<g class="mv"><ellipse class="a1" cx="100" cy="92" rx="40" ry="32"/><ellipse class="a1" cx="44" cy="62" rx="16" ry="21" transform="rotate(-20 44 62)"/><ellipse class="a1" cx="80" cy="28" rx="16" ry="23"/><ellipse class="a1" cx="122" cy="28" rx="16" ry="23"/><ellipse class="a1" cx="158" cy="62" rx="16" ry="21" transform="rotate(20 158 62)"/></g>')
    out.append('<g class="mv2"><circle class="a5" cx="30" cy="112" r="5"/><circle class="a5" cx="176" cy="108" r="4"/><circle class="a2" cx="170" cy="22" r="5"/></g>')
    out.append("</svg>")
    return "".join(out)





def _logo_art(slug, extra=""):
    return OPEN + logos.art_mark(slug, 100, 70, 1.2) + extra + "</svg>"


def lockerlink():
    return _logo_art("lockerlink", '<g class="mv2"><circle class="a5" cx="26" cy="30" r="4"/><circle class="a2" cx="176" cy="112" r="5"/></g>')


def gridlink():
    return _logo_art("gridlink", '<g class="mv2"><circle class="a5" cx="24" cy="112" r="4"/><circle class="a2" cx="178" cy="28" r="5"/></g>')


def under_the_cap():
    return _logo_art("under-the-cap", '<g class="mv2"><circle class="a5" cx="28" cy="26" r="4"/><circle class="a2" cx="174" cy="114" r="5"/></g>')


def tanklink():
    return _logo_art("tanklink", '<g class="mv2"><circle class="a5" cx="26" cy="28" r="4"/><circle class="a2" cx="176" cy="112" r="5"/></g>')


def frontlink():
    return _logo_art("frontlink", '<g class="mv2"><circle class="a5" cx="28" cy="112" r="4"/><circle class="a2" cx="174" cy="30" r="5"/></g>')


ART = {"tanklink": tanklink, "frontlink": frontlink, "lockerlink": lockerlink, "gridlink": gridlink, "under-the-cap": under_the_cap, "thinkerlink": thinkerlink, "riverlink": riverlink, "wildlink": wildlink, "citylink": citylink, "peaklink": peaklink, "codelink": codelink, "landlink": landlink, "atomlink": atomlink, "prizelink": prizelink, "chess-puzzles": chess_puzzles, "sudoku-unlimited": sudoku_unlimited, "leaderboard": leaderboard, "linkle": linkle, "quadlink": quadlink, "daily-five": daily_five, "daily-photo": daily_photo,
       "daily-chess": daily_chess, "sudoku": sudoku, "crossword": crossword, "daily-stars": daily_stars}


def art(slug):
    return ART[slug]()
