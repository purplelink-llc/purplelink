"""Logos for the three sports games, drawn once as shapes in a 100 x 100 box and used three ways:
  * standalone files (site/assets/games/<slug>.svg) with fixed colours, for the page header and the share cards;
  * inline tile art, using the page's per-game colour classes;
  * the 24 px nav glyphs are hand-drawn in site/games/glyphs.svg to match.
Each mark has one idea: Lockerlink is a locker door whose handle is two chain links, Gridlink is a clue grid with a link in its
corner, Under the Cap is a shield with a zero and a star. Tanklink is a tank with a shell in flight, Frontlink is a small map with your unit and the enemy flag. Colours follow site/games/games-ui.css (--gc and friends)."""
import math

HUE = {"lockerlink": 118, "gridlink": 150, "under-the-cap": 20, "tanklink": 75, "frontlink": 255}


def oklch_hex(l, c, h):
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    bl = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    f = lambda x: round(255 * min(1, max(0, 12.92 * x if x <= 0.0031308 else 1.055 * (x ** (1 / 2.4)) - 0.055)))
    return "#%02x%02x%02x" % (f(r), f(g), f(bl))


def palette(slug):
    h = HUE[slug]
    return {"bg": oklch_hex(.72, .15, h), "deep": oklch_hex(.46, .14, h), "light": oklch_hex(.90, .07, h), "white": oklch_hex(.99, .01, h), "ink": oklch_hex(.21, .05, h)}


class Hex:
    """Fixed colours, for standalone files."""
    def __init__(self, slug): self.p = palette(slug)
    def fill(self, role): return f'fill="{self.p[role]}"'
    def stroke(self, role, w): return f'fill="none" stroke="{self.p[role]}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'


class Cls:
    """Classes from games-ui.css, for inline art inside a tile."""
    C = {"deep": "lg-d", "light": "lg-l", "white": "lg-w", "ink": "lg-i", "bg": "lg-b"}
    def fill(self, role): return f'class="{self.C[role]}"'
    def stroke(self, role, w): return f'class="{self.C[role]}s" stroke-width="{w}"'


def star(cx, cy, r, k=0.45):
    pts = []
    for i in range(10):
        a = math.radians(-90 + 36 * i); rr = r if i % 2 == 0 else r * k
        pts.append(f"{cx + rr * math.cos(a):.2f} {cy + rr * math.sin(a):.2f}")
    return "M" + " L".join(pts) + "Z"


def lockerlink(P):
    out = []
    for x in (13, 53):                                   # a bank of two lockers
        out.append(f'<rect x="{x}" y="12" width="34" height="76" rx="7.5" {P.fill("white")}/>')
        for y in (20, 26.5, 33):
            out.append(f'<rect x="{x + 7}" y="{y}" width="20" height="3.2" rx="1.6" {P.fill("deep")}/>')
        for y in (73, 79.5):
            out.append(f'<rect x="{x + 7}" y="{y}" width="20" height="3.2" rx="1.6" {P.fill("deep")}/>')
    # two chain links hold them together across the gap
    out.append(f'<rect x="28" y="47.5" width="27" height="14" rx="7" {P.stroke("deep", 4.6)}/>')
    out.append(f'<rect x="45" y="47.5" width="27" height="14" rx="7" {P.stroke("deep", 4.6)}/>')
    out.append(f'<path d="M48.6 47.5 A7 7 0 0 1 55 54.5" {P.stroke("deep", 4.6)}/>')
    return "".join(out)


def gridlink(P):
    s, g, o = 17, 3.8, 14.2
    out = []
    for r in range(4):
        for c in range(4):
            x, y = o + c * (s + g), o + r * (s + g)
            role = "deep" if (r == 0 or c == 0) else "white"
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{s}" height="{s}" rx="5" {P.fill(role)}/>')
    # a link in the corner
    out.append(f'<rect x="{o + 1.6:.1f}" y="{o + 5.6:.1f}" width="9.6" height="5.8" rx="2.9" {P.stroke("white", 2.2)}/>')
    out.append(f'<rect x="{o + 5.8:.1f}" y="{o + 5.6:.1f}" width="9.6" height="5.8" rx="2.9" {P.stroke("white", 2.2)}/>')
    # two answers in the grid
    for r, c in ((1, 2), (3, 1)):
        x, y = o + c * (s + g) + s / 2, o + r * (s + g) + s / 2
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" {P.fill("deep")}/>')
    return "".join(out)


def under_the_cap(P):
    out = [f'<rect x="14" y="16" width="72" height="8.5" rx="4.2" {P.fill("deep")}/>']             # the cap
    heights = (30, 41, 54, 44, 34)                                                                    # five players, the tallest just under the cap
    for i, h in enumerate(heights):
        x = 14.5 + i * 14.8
        out.append(f'<rect x="{x:.1f}" y="{88 - h:.1f}" width="11.6" height="{h}" rx="4.2" {P.fill("white")}/>')
    out.append(f'<path d="{star(14.5 + 2 * 14.8 + 5.8, 88 - 54 + 11, 4.8)}" {P.fill("deep")}/>')    # the star player
    return "".join(out)


def tanklink(P):
    out = [f'<rect x="10" y="78" width="80" height="9" rx="4.5" {P.fill("deep")}/>']                    # the ground
    out.append(f'<rect x="20" y="62" width="46" height="13" rx="6.5" {P.fill("white")}/>')              # hull
    out.append(f'<rect x="30" y="50" width="26" height="14" rx="6.5" {P.fill("white")}/>')              # turret
    out.append(f'<path d="M50 54 L74 38" {P.stroke("white", 5.4)}/>')                                  # barrel
    for cx in (28, 43, 58):
        out.append(f'<circle cx="{cx}" cy="73" r="4" {P.fill("deep")}/>')                              # wheels
    out.append(f'<path d="M80 33 Q88 24 92 36" {P.stroke("light", 3)} stroke-dasharray="1 6.5"/>')       # the shell in flight
    out.append(f'<circle cx="82" cy="30" r="3.6" {P.fill("white")}/>')
    return "".join(out)


def frontlink(P):
    s, g, o = 20, 4, 11
    out = []
    for r in range(3):
        for c in range(3):
            x, y = o + c * (s + g), o + r * (s + g)
            out.append(f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="5.5" {P.fill("white")} opacity="{0.36 if (r + c) % 2 else 0.2}"/>')
    out.append(f'<rect x="{o}" y="{o + 2 * (s + g)}" width="{s}" height="{s}" rx="5.5" {P.fill("deep")}/>')       # your HQ
    out.append(f'<circle cx="{o + s / 2}" cy="{o + 2 * (s + g) + s / 2}" r="5.2" {P.fill("white")}/>')           # your unit
    x, y = o + 2 * (s + g), o
    out.append(f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="5.5" {P.fill("white")}/>')                   # the enemy HQ
    out.append(f'<path d="M{x + 7} {y + 15} V{y + 5} L{x + 15} {y + 8.5} L{x + 7} {y + 12}" {P.stroke("deep", 2.4)}/>')  # a flag
    out.append(f'<path d="M{o + 10} {o + 2 * (s + g) - 2.5} V{o + s + g + 12} H{o + 2 * (s + g) - 5}" {P.stroke("white", 3.2)} stroke-dasharray="1 6"/>')  # the advance
    return "".join(out)


MARKS = {"lockerlink": lockerlink, "gridlink": gridlink, "under-the-cap": under_the_cap, "tanklink": tanklink, "frontlink": frontlink}


def logo_svg(slug):
    P = Hex(slug); bg = palette(slug)["bg"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="{slug.capitalize()} logo">'
            f'<rect width="100" height="100" rx="22" fill="{bg}"/>{MARKS[slug](P)}</svg>\n')


def art_mark(slug, cx=100, cy=70, scale=1.28):
    """The mark for the 200 x 140 tile art, centred on (cx, cy)."""
    return f'<g transform="translate({cx - 50 * scale:.1f} {cy - 50 * scale:.1f}) scale({scale})">{MARKS[slug](Cls())}</g>'
