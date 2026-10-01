#!/usr/bin/env python3
"""Refreshed listing assets and copy for the ten "hero" Etsy print listings.

WHY THIS EXISTS
A buyer-persona review of the PurplelinkDesigns shop asked for four things the
etsy-build.py kits do not give: place-first searchable titles, 13 tags in the
phrases buyers actually type, explicit print sizes with pixel dimensions, and
three or four calm room mockups instead of one framed-on-a-wall shot. This
script layers that on top of the existing kits without touching them.

WHAT IT PRODUCES (photo-licensing-workspace/etsy/<slug>/v2/)
  photos/1-living-room.jpg   framed print over a sofa, procedurally drawn
  photos/2-office.jpg        lighter wall, wood shelf and desk
  photos/3-gallery-sizes.jpg the same photo at three print sizes, to scale
  photos/4-size-card.jpg     ratios, pixel dimensions, largest clean size
  photos/5-detail.jpg        the existing 100% detail crop, copied over
  listing.json               title, 13 tags, description, price
and photo-licensing-workspace/etsy/sets.json: "set of 3" bundles by country.

The print files themselves (<slug>/files/) are reused as built by
etsy-build.py; if a hero has no kit yet it is built first with that script's
own build() function. Pixel dimensions and "prints cleanly up to N in" come
from those files and etsy-build.py's PPI / fit_sizes, so the copy can never
promise a size the pixels do not support.

  python3 scripts/etsy-hero-assets.py            # write everything
  python3 scripts/etsy-hero-assets.py --check    # print the plan, write nothing
  python3 scripts/etsy-hero-assets.py DSC_1326   # one hero
"""
import argparse, csv, importlib.util, json, os, re, shutil, sys, time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

_spec = importlib.util.spec_from_file_location("etsy_build", HERE / "etsy-build.py")
eb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eb)

_WS = Path(os.environ.get("PL_WORKSPACE") or (ROOT / "photo-licensing-workspace"))
WS = _WS if _WS.exists() else Path("/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace")
OUT = WS / "etsy"
SRC = Path(os.environ.get("PL_PHOTOS") or eb.SRC)
HUB_DATA = ROOT / "site" / "photography" / "hub-data.json"
eb.WS, eb.OUT, eb.SRC = WS, OUT, SRC     # etsy-build.py's build() writes where we do

PPI = eb.PPI
PRICE_SINGLE = 7.00
PRICE_SET = 15.00
W, H = 2400, 1800
PX_PER_IN = 20                     # every room mockup is drawn at this scale
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# stem: title lead (place first), one or two sentences, country for sets, 13 tags
HEROES = {
 "DSC_1326": dict(
    title="Skogafoss Waterfall Iceland Wall Art Print, Printable Travel Photography, Large Landscape Digital Download",
    about="Skogafoss waterfall on the south coast of Iceland, with a rainbow standing in the spray at the base of the falls.",
    country="Iceland",
    tags=["iceland wall art", "skogafoss print", "waterfall print", "large wall art", "living room art",
          "printable photo", "travel print", "landscape print", "nature wall decor", "digital download",
          "iceland print", "rainbow waterfall", "scandinavian decor"]),
 "DSC_4368": dict(
    title="Miyajima Torii Gate Japan Wall Art Print, Itsukushima Shrine at Dusk, Printable Travel Photography, Digital Download",
    about="The floating torii gate of Itsukushima Shrine on Miyajima island, Japan, seen between the shrine's red pavilions at dusk.",
    country="Japan",
    tags=["japan wall art", "miyajima print", "torii gate print", "itsukushima shrine", "japanese decor",
          "large wall art", "living room art", "printable photo", "travel print", "digital download",
          "japan print", "shrine at dusk", "zen wall decor"]),
 "DSC_8669": dict(
    title="Matterhorn Riffelsee Switzerland Wall Art Print, Zermatt Mountain Reflection, Printable Travel Photography, Digital Download",
    about="The Matterhorn reflected in Riffelsee, a small lake on the slopes above Zermatt, Switzerland, on a still morning.",
    country="Switzerland",
    tags=["switzerland print", "matterhorn print", "zermatt wall art", "mountain wall art", "swiss alps print",
          "lake reflection", "large wall art", "living room art", "printable photo", "travel print",
          "landscape print", "digital download", "alpine decor"]),
 "DSC_6629-Edit": dict(
    title="Big Ben London Wall Art Print, Westminster Sunset, Printable Travel Photography, Large Cityscape Digital Download",
    about="Big Ben and the Palace of Westminster in London at sunset, seen across the River Thames.",
    country="England",
    tags=["london wall art", "big ben print", "london print", "westminster print", "sunset cityscape",
          "city wall art", "large wall art", "living room art", "printable photo", "travel print",
          "digital download", "england print", "office wall art"]),
 "DSC_1601": dict(
    title="Jokulsarlon Glacier Lagoon Iceland Wall Art Print, Icebergs Panoramic, Printable Travel Photography, Digital Download",
    about="Icebergs drifting across Jokulsarlon glacier lagoon in southeast Iceland, with the peaks of Vatnajokull behind them.",
    country="Iceland",
    tags=["iceland wall art", "jokulsarlon print", "glacier lagoon", "iceberg print", "panoramic print",
          "nordic decor", "large wall art", "living room art", "printable photo", "travel print",
          "digital download", "iceland print", "blue wall art"]),
 "DSC_7583": dict(
    title="Sonoran Desert Sunset Arizona Wall Art Print, Saguaro Cactus Tucson, Printable Travel Photography, Digital Download",
    about="Sunset over the Sonoran Desert outside Tucson, Arizona, with saguaro cacti silhouetted against layered mountains.",
    country="Arizona",
    tags=["arizona wall art", "sonoran desert", "saguaro print", "desert sunset print", "tucson print",
          "southwest decor", "desert wall art", "large wall art", "living room art", "printable photo",
          "travel print", "digital download", "cactus wall art"]),
 "DSC_8714": dict(
    title="Gorner Glacier Zermatt Switzerland Wall Art Print, Swiss Alps Landscape, Printable Travel Photography, Digital Download",
    about="The Gorner Glacier winding between snow-covered peaks above Zermatt, Switzerland.",
    country="Switzerland",
    tags=["switzerland print", "gorner glacier", "zermatt wall art", "glacier print", "swiss alps print",
          "mountain wall art", "large wall art", "living room art", "printable photo", "travel print",
          "landscape print", "digital download", "alpine decor"]),
 "DSC_4380": dict(
    title="Waipio Valley Hawaii Wall Art Print, Big Island Black Sand Beach, Printable Travel Photography, Digital Download",
    about="Waipio Valley on the Big Island of Hawaii: green sea cliffs curving along a black sand beach, with surf breaking on the shore.",
    country="Hawaii",
    tags=["hawaii wall art", "waipio valley", "big island print", "black sand beach", "hawaii print",
          "ocean wall art", "coastal decor", "large wall art", "living room art", "printable photo",
          "travel print", "digital download", "beach wall art"]),
 "DSC_3638": dict(
    title="Arashiyama Kyoto Japan Wall Art Print, Misty Hozu River Gorge Panoramic, Printable Travel Photography, Digital Download",
    about="Low cloud drifting through the forested Hozu River gorge near Arashiyama, Kyoto, Japan, with a single house on the hillside.",
    country="Japan",
    tags=["japan wall art", "kyoto print", "arashiyama print", "misty mountains", "hozu river",
          "panoramic print", "japanese decor", "large wall art", "living room art", "printable photo",
          "travel print", "digital download", "zen wall decor"]),
 "DSC_7559-Pano-Edit": dict(
    title="Copenhagen Denmark Wall Art Print, Rooftops at Sunset Skyline, Printable Travel Photography, Digital Download",
    about="Copenhagen's red-tiled rooftops and a green copper spire under a sunset sky, Denmark.",
    country="Denmark",
    tags=["denmark wall art", "copenhagen print", "copenhagen skyline", "rooftops print", "scandinavian decor",
          "city wall art", "sunset print", "large wall art", "living room art", "printable photo",
          "travel print", "digital download", "nordic decor"]),
}

# Sets of three by country: the two heroes plus a third that adds variety.
# The third is a fallback; hub-data.json (if present) is consulted to confirm
# it is published on the site, and any hero country with only one hero is
# filled from etsy-build.py's SEL table.
SETS = {
 "Iceland": dict(heroes=["DSC_1326", "DSC_1601"], third="DSC_1362",
                 title="Iceland Wall Art Set of 3 Prints, Skogafoss Waterfall, Glacier Lagoon, Dyrholaey Sea Cliffs, Printable Digital Download"),
 "Switzerland": dict(heroes=["DSC_8669", "DSC_8714"], third="DSC_8511",
                     title="Switzerland Wall Art Set of 3 Prints, Matterhorn, Gorner Glacier, Lauterbrunnen, Printable Swiss Alps Digital Download"),
 "Japan": dict(heroes=["DSC_4368", "DSC_3638"], third="DSC_4038",
               title="Japan Wall Art Set of 3 Prints, Miyajima Torii, Arashiyama Mist, Kiyomizu-dera Kyoto, Printable Digital Download"),
}

# Palette: warm neutrals, nothing saturated.
FRAME = (28, 26, 25)
MAT = (250, 249, 246)
INK = (36, 33, 31)
INK_SOFT = (104, 97, 91)
RULE = (214, 207, 198)


# --------------------------------------------------------------------------- data

def hero_dir(stem):
    name = eb.SEL[stem][0]
    return OUT / eb.slug(f"{name}-{stem}")


def ensure_kit(stem, meta, check):
    """Return the kit dir, building it with etsy-build.py if files/ is missing."""
    d = hero_dir(stem)
    if (d / "files").exists() and any((d / "files").glob("*.jpg")):
        return d, False
    if check:
        return d, True
    print(f"  building missing kit for {stem} with etsy-build.py")
    eb.build(stem, meta)
    return d, True


def ratio_rows(d):
    """[(label, (w, h), clean sizes string, max clean inches)] from files/."""
    rows = []
    for p in sorted((d / "files").glob("*.jpg")):
        lab = p.stem.rsplit("_", 1)[1]
        w, h = Image.open(p).size
        long_px = max(w, h)
        if lab == "native":
            sizes = "panoramic frames and custom sizes"
        elif lab in eb.PANO_SIZES:
            sizes = eb.fit_sizes(eb.PANO_SIZES[lab], long_px)
        else:
            sizes = next((eb.fit_sizes(s, long_px) for l, r, s in eb.RATIOS_STD if l == lab), "")
        rows.append((lab, (w, h), sizes, long_px // PPI))
    order = {"2x3": 0, "3x4": 1, "4x5": 2, "11x14": 3, "ISO": 4, "native": 5, "2x1": 6, "3x1": 7}
    return sorted(rows, key=lambda r: order.get(r[0], 9))


def clean_inch_sizes(rows):
    """(ratio value, [(short_in, long_in)...]) for the ratio used in mockups."""
    for lab, r, sizes in (("2x3", 1.5, None), ("2x1", 2.0, None), ("3x1", 3.0, None)):
        row = next((x for x in rows if x[0] == lab), None)
        if not row:
            continue
        table = eb.PANO_SIZES.get(lab) or next(s for l, _, s in eb.RATIOS_STD if l == lab)
        ok = [tuple(map(int, l.split("x"))) for l, L in table if L <= row[1][0] / PPI or L <= row[1][1] / PPI]
        if ok:
            return r, ok
    raise SystemExit("no 2x3 or panoramic file to size the mockups from")


def shot_date(stem):
    src = SRC / f"{stem}.jpeg"
    ex = Image.open(src).getexif()
    raw = ex.get_ifd(0x8769).get(36867) or ex.get(306)
    if not raw:
        return ""
    y, m = raw.split(" ")[0].split(":")[:2]
    return f"{MONTHS[int(m) - 1]} {y}"


def load_hub_data(wait_s):
    deadline = time.time() + wait_s
    while True:
        if HUB_DATA.exists():
            try:
                return json.loads(HUB_DATA.read_text())
            except json.JSONDecodeError:
                pass           # being written right now
        if time.time() > deadline:
            return None
        time.sleep(5)


# ------------------------------------------------------------------------ drawing

def wall(color_top, color_bottom):
    g = Image.linear_gradient("L").resize((W, H))
    bg = Image.composite(Image.new("RGB", (W, H), color_bottom), Image.new("RGB", (W, H), color_top), g)
    grain = Image.effect_noise((W, H), 6).filter(ImageFilter.GaussianBlur(0.6))
    return Image.composite(bg, bg.point(lambda v: max(0, v - 8)), grain.point(lambda v: 255 if v > 118 else 200))


def drop_shadow(bg, box, blur=26, dx=10, dy=22, strength=105, color=(70, 64, 58)):
    x0, y0, x1, y1 = box
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rectangle([x0 + dx, y0 + dy, x1 + dx, y1 + dy], fill=strength)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    return Image.composite(Image.new("RGB", (W, H), color), bg, sh)


def framed_print(bg, im, cx, cy, short_in, long_in, mat_in=2.5, frame_in=0.75, scale=PX_PER_IN):
    """Paste `im` as a short_in x long_in print, mat and thin black frame, centred at cx, cy.
    Returns (bg, outer box)."""
    land = im.width >= im.height
    pw, ph = (round(long_in * scale), round(short_in * scale)) if land else (round(short_in * scale), round(long_in * scale))
    mat, fr = round(mat_in * scale), max(6, round(frame_in * scale))
    ow, oh = pw + 2 * (mat + fr), ph + 2 * (mat + fr)
    x, y = round(cx - ow / 2), round(cy - oh / 2)
    bg = drop_shadow(bg, (x, y, x + ow, y + oh), blur=max(10, scale), dx=round(scale * .4), dy=round(scale * .9))
    d = ImageDraw.Draw(bg)
    d.rectangle([x, y, x + ow, y + oh], fill=FRAME)
    d.line([x, y, x + ow, y], fill=(58, 55, 53), width=2)                   # light catching the top rail
    d.rectangle([x + fr, y + fr, x + ow - fr, y + oh - fr], fill=MAT)
    px, py = x + fr + mat, y + fr + mat
    d.rectangle([px - 2, py - 2, px + pw + 1, py + ph + 1], fill=(222, 219, 214))  # mat bevel
    photo = ImageOps.fit(im, (pw, ph), Image.LANCZOS)                          # ratio already matches: no stretch
    bg.paste(photo, (px, py))
    return bg, (x, y, x + ow, y + oh)


def note(bg, text, xy, size=30, fill=INK_SOFT, anchor="la"):
    _, sans = eb.fonts()
    ImageDraw.Draw(bg).text(xy, text, font=sans(size, 2), fill=fill, anchor=anchor)


def mockup_living_room(im, sizes, path):
    """Sofa-height neutral wall, the largest clean size over an 84 in sofa."""
    short_in, long_in = sizes[-1]
    S = PX_PER_IN
    bg = wall((232, 226, 218), (219, 212, 203))
    d = ImageDraw.Draw(bg)
    floor_y = H - 5 * S
    d.rectangle([0, floor_y, W, H], fill=(184, 168, 148))                 # oak floor
    d.rectangle([0, floor_y - 5 * S, W, floor_y], fill=(241, 238, 233))  # baseboard
    d.line([0, floor_y - 5 * S, W, floor_y - 5 * S], fill=(205, 198, 190), width=3)
    # sofa: 84 in wide, 32 in back, 18 in seat, 25 in arms, 8 in arm width
    sw, back, seat, arm_h, arm_w = 84 * S, 32 * S, 18 * S, 25 * S, 8 * S
    x0 = (W - sw) // 2
    body, dark, light = (160, 152, 142), (140, 132, 123), (172, 164, 155)
    bg = drop_shadow(bg, (x0, floor_y - back, x0 + sw, floor_y - 2 * S), blur=30, dx=0, dy=14, strength=80)
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([x0 + arm_w, floor_y - back, x0 + sw - arm_w, floor_y - seat], 18, fill=body)
    third = (sw - 2 * arm_w) // 3
    for i in range(3):                                                    # back cushions
        cx0 = x0 + arm_w + i * third
        d.rounded_rectangle([cx0 + 10, floor_y - back + 14, cx0 + third - 10, floor_y - seat - 6], 22, fill=light)
    d.rounded_rectangle([x0 + arm_w, floor_y - seat, x0 + sw - arm_w, floor_y - 8 * S], 20, fill=dark)
    half = (sw - 2 * arm_w) // 2
    for i in range(2):                                                    # seat cushions
        cx0 = x0 + arm_w + i * half
        d.rounded_rectangle([cx0 + 10, floor_y - seat + 10, cx0 + half - 10, floor_y - 8 * S - 6], 22, fill=body)
    for ax in (x0, x0 + sw - arm_w):                                      # arms
        d.rounded_rectangle([ax, floor_y - arm_h, ax + arm_w, floor_y - 8 * S], 26, fill=dark)
    d.rectangle([x0, floor_y - 8 * S, x0 + sw, floor_y - 5 * S], fill=(128, 120, 112))   # base
    for lx in (x0 + 3 * S, x0 + sw - 4 * S):                              # legs
        d.rectangle([lx, floor_y - 5 * S, lx + S, floor_y], fill=(70, 62, 56))
    d.rounded_rectangle([x0 + arm_w + 2 * S, floor_y - back + 4 * S, x0 + arm_w + 18 * S, floor_y - seat],
                        18, fill=(205, 196, 184))                         # one throw pillow
    gap = 9 * S                                                            # frame bottom 9 in above the back
    ph_outer = short_in * S + 2 * (2.5 + .75) * S
    cy = floor_y - back - gap - ph_outer / 2
    bg, _ = framed_print(bg, im, W / 2, cy, short_in, long_in)
    note(bg, f"{short_in} x {long_in} in print over an 84 in sofa", (3 * S, H - 2.4 * S), fill=(96, 84, 72))
    bg.save(path, "JPEG", quality=88, optimize=True)


def mockup_office(im, sizes, path):
    """Lighter wall, a wood shelf line below the print and a desk at the bottom."""
    short_in, long_in = sizes[-2] if len(sizes) > 1 else sizes[-1]
    S = PX_PER_IN
    bg = wall((246, 243, 238), (236, 232, 226))
    d = ImageDraw.Draw(bg)
    floor_y = H - 3 * S
    d.rectangle([0, floor_y, W, H], fill=(206, 196, 182))
    # desk: 60 in wide, 30 in high, 1.5 in oak top
    dw, dh = 60 * S, 30 * S
    dx0 = (W - dw) // 2
    bg = drop_shadow(bg, (dx0, floor_y - dh, dx0 + dw, floor_y - dh + 2 * S), blur=18, dx=0, dy=10, strength=70)
    d = ImageDraw.Draw(bg)
    d.rectangle([dx0, floor_y - dh, dx0 + dw, floor_y - dh + round(1.5 * S)], fill=(176, 142, 104))
    d.line([dx0, floor_y - dh, dx0 + dw, floor_y - dh], fill=(196, 164, 126), width=3)
    for lx in (dx0 + S, dx0 + dw - 2 * S):
        d.rectangle([lx, floor_y - dh + round(1.5 * S), lx + S, floor_y], fill=(60, 56, 54))
    d.rectangle([dx0 + S, floor_y - dh + round(1.5 * S), dx0 + dw - S, floor_y - dh + 3 * S], fill=(60, 56, 54))
    # small things on the desk: a closed laptop and a mug
    d.rounded_rectangle([dx0 + 20 * S, floor_y - dh - round(.7 * S), dx0 + 34 * S, floor_y - dh], 6, fill=(120, 122, 126))
    d.rounded_rectangle([dx0 + 40 * S, floor_y - dh - 4 * S, dx0 + 43 * S, floor_y - dh], 8, fill=(226, 221, 214))
    # floating oak shelf, 36 in wide, 1.25 in thick, 10 in above the desk
    shelf_y = floor_y - dh - 10 * S
    sx0 = (W - 36 * S) // 2
    bg = drop_shadow(bg, (sx0, shelf_y, sx0 + 36 * S, shelf_y + round(1.25 * S)), blur=14, dx=0, dy=8, strength=70)
    d = ImageDraw.Draw(bg)
    d.rectangle([sx0, shelf_y, sx0 + 36 * S, shelf_y + round(1.25 * S)], fill=(176, 142, 104))
    d.line([sx0, shelf_y, sx0 + 36 * S, shelf_y], fill=(196, 164, 126), width=3)
    for i, (bw, bh, col) in enumerate(((1.2, 8, (118, 110, 104)), (1.6, 9, (196, 188, 176)), (1.0, 7.5, (90, 96, 92)))):
        bx = sx0 + 2 * S + sum(int(w * S) + 4 for w, _, _ in (((1.2, 8, 0), (1.6, 9, 0), (1.0, 7.5, 0))[:i]))
        d.rectangle([bx, shelf_y - bh * S, bx + bw * S, shelf_y], fill=col)
    pot_x = sx0 + 36 * S - 5 * S
    d.rounded_rectangle([pot_x, shelf_y - 3 * S, pot_x + 3 * S, shelf_y], 6, fill=(214, 206, 196))
    d.ellipse([pot_x - S, shelf_y - 7 * S, pot_x + 4 * S, shelf_y - 2 * S], fill=(128, 142, 118))
    gap = 11 * S                                                           # clears the 9 in books
    ph_outer = short_in * S + 2 * (2.5 + .75) * S
    cy = shelf_y - gap - ph_outer / 2
    bg, _ = framed_print(bg, im, W / 2, cy, short_in, long_in)
    note(bg, f"{short_in} x {long_in} in print above a 60 in desk", (3 * S, H - 2.4 * S), fill=(120, 108, 96))
    bg.save(path, "JPEG", quality=88, optimize=True)


def mockup_gallery(im, sizes, path):
    """The same photo at three clean sizes, side by side at one scale."""
    picks = [sizes[0], sizes[len(sizes) // 2], sizes[-1]] if len(sizes) >= 3 else sizes
    picks = sorted(set(picks))
    S = PX_PER_IN
    land = im.width >= im.height
    pad = (2.5 + .75) * 2
    widths = [((L if land else s) + pad) * S for s, L in picks]
    gap = 8 * S
    total = sum(widths) + gap * (len(picks) - 1)
    scale = S if total <= W - 12 * S else S * (W - 12 * S) / total
    widths = [w * scale / S for w in widths]
    bg = wall((238, 233, 226), (226, 220, 212))
    d = ImageDraw.Draw(bg)
    floor_y = H - 4 * S
    d.rectangle([0, floor_y, W, H], fill=(190, 174, 154))
    d.rectangle([0, floor_y - 4 * S, W, floor_y], fill=(243, 240, 235))
    x = (W - (sum(widths) + gap * (len(picks) - 1))) / 2
    cy = (floor_y - 10 * S) / 2
    for (s, L), w in zip(picks, widths):
        bg, box = framed_print(bg, im, x + w / 2, cy, s, L, scale=scale)
        note(bg, f"{s} x {L} in", (x + w / 2, box[3] + 1.6 * S), size=28, anchor="ma")
        x += w + gap
    note(bg, "Same file, three print sizes, drawn to one scale", (3 * S, H - 2.6 * S), fill=(96, 84, 72))
    bg.save(path, "JPEG", quality=88, optimize=True)


def size_card(name, rows, path):
    serif, sans = eb.fonts()
    bg = Image.new("RGB", (W, H), (247, 244, 239))
    d = ImageDraw.Draw(bg)
    d.text((160, 130), "Print sizes", font=serif(104), fill=INK)
    d.text((160, 270), name, font=sans(50), fill=INK_SOFT)
    y = 410
    cols = (160, 560, 1000, 1420)
    for x, head in zip(cols, ("Ratio", "Pixels", "Clean up to", "Sizes")):
        d.text((x, y), head, font=sans(36, 2), fill=INK_SOFT)
    y += 60
    d.line([160, y, W - 160, y], fill=RULE, width=3)
    y += 36
    for lab, (w, h), sizes, max_in in rows:
        label = "Native" if lab == "native" else ("A series" if lab == "ISO" else lab)
        d.text((cols[0], y), label, font=sans(50, 2), fill=INK)
        d.text((cols[1], y + 2), f"{w} x {h} px", font=sans(46), fill=INK)
        d.text((cols[2], y + 2), f"{max_in} in long side", font=sans(46), fill=INK)
        d.text((cols[3], y + 2), sizes, font=sans(42), fill=INK_SOFT)
        y += 96 if len(sizes) < 44 else 110
    y += 20
    d.line([160, y, W - 160, y], fill=RULE, width=3)
    y += 50
    for line in (f"{len(rows)} JPG files, one per ratio. Nothing is upscaled.",
                 f"Every listed size keeps at least {PPI} pixels per inch.",
                 "Print at home, at a local print shop, or through an online lab.",
                 "Digital files only. No physical print or frame is shipped."):
        d.text((160, y), line, font=sans(44), fill=INK_SOFT)
        y += 78
    bg.save(path, "JPEG", quality=88, optimize=True)


# --------------------------------------------------------------------------- copy

def describe(stem, cfg, rows, date):
    name = eb.SEL[stem][0]
    about = cfg["about"] + (f" Photographed in {date}." if date else "")
    lines = [about, "", "WHAT YOU GET",
             f"{len(rows)} high-resolution JPG files, one per print ratio, so you can match the frame you already have:"]
    for lab, (w, h), sizes, max_in in rows:
        if lab == "native":
            lines.append(f"- Native panoramic crop, {w} x {h} px: {sizes}. Prints cleanly up to {max_in} in on the long side.")
        else:
            label = "A-series (ISO)" if lab == "ISO" else f"{lab} ratio"
            lines.append(f"- {label}, {w} x {h} px: {sizes}. Prints cleanly up to {max_in} in on the long side.")
    lines += ["", f'"Prints cleanly" means at least {PPI} pixels per inch, the usual floor for wall art seen from a few feet away. Larger prints are possible but will look softer up close.',
              "", "HOW TO PRINT",
              "- At home: open the file that matches your frame and print on photo or matte paper at the largest size your printer allows.",
              "- Print shop: bring the file on a USB stick or email it; ask for the size listed above and a matte or lustre finish.",
              "- Online lab: upload the file to any photo lab and choose the matching size. Most labs also offer framing.",
              "", "FACTS",
              "Photographed by Benjamin Ampel on a Nikon. Every photo in the shop is my own. Files are delivered by Etsy instantly after purchase.",
              f"Shop: PurplelinkDesigns. More of the photography: purplelink.llc/photography/",
              "", "LICENSE",
              "Personal use only. You may print the files for your own home or as a gift. No resale, no sharing of the files, and no commercial use. Commercial licenses are available at purplelink.llc/photography/license/",
              "", "RETURNS",
              "Because this is a digital download, Etsy does not allow returns or exchanges once the files have been delivered. If a file will not open or you are unsure which one to print, message me through Etsy and I will help."]
    return "\n".join(lines)


def check_listing(l, single=True):
    assert len(l["title"]) <= 140, f"title too long ({len(l['title'])}): {l['title']}"
    for kw in (("Wall Art Print", "Printable", "Digital Download") if single else ("Wall Art", "Printable", "Digital Download")):
        assert kw in l["title"], f"title lacks {kw!r}"
    tags = l["tags"]
    assert len(tags) == 13, f"{len(tags)} tags"
    assert len(set(tags)) == 13, "duplicate tags"
    for t in tags:
        assert len(t) <= 20 and t == t.lower().strip(), f"bad tag {t!r}"
    assert not re.search(r"[\U0001F300-\U0001FAFF☀-➿]", l["description"]), "emoji in description"


# --------------------------------------------------------------------------- main

def build_hero(stem, meta, check):
    cfg = HEROES[stem]
    name = eb.SEL[stem][0]
    d, built = ensure_kit(stem, meta, check)
    v2 = d / "v2"
    plan = {"stem": stem, "dir": str(v2), "kit_built_now": built}
    if check and built:
        plan["note"] = "no kit yet; etsy-build.py's build() would run first"
        return plan
    rows = ratio_rows(d)
    ratio, sizes = clean_inch_sizes(rows)
    date = shot_date(stem)
    listing = {"stem": stem, "title": cfg["title"], "tags": cfg["tags"],
               "description": describe(stem, cfg, rows, date), "price": PRICE_SINGLE,
               "files": sorted(p.name for p in (d / "files").glob("*.jpg")),
               "photos": ["1-living-room.jpg", "2-office.jpg", "3-gallery-sizes.jpg", "4-size-card.jpg", "5-detail.jpg"],
               "photo_first": "../photos/0-photo.jpg" if (d / "photos" / "0-photo.jpg").exists() else None,
               "dir": str(v2)}
    check_listing(listing)
    plan.update(title=listing["title"], tags=listing["tags"], mockup_sizes=sizes,
                ratios=[(r[0], f"{r[1][0]}x{r[1][1]}", r[3]) for r in rows])
    if check:
        return plan
    (v2 / "photos").mkdir(parents=True, exist_ok=True)
    src = next(p for p in (SRC / f"{stem}.jpeg", SRC / f"{stem}.jpg") if p.exists())
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.thumbnail((2600, 2600), Image.LANCZOS)
    im = eb.crop_ratio(im, ratio)
    ph = v2 / "photos"
    mockup_living_room(im, sizes, ph / "1-living-room.jpg")
    mockup_office(im, sizes, ph / "2-office.jpg")
    mockup_gallery(im, sizes, ph / "3-gallery-sizes.jpg")
    size_card(name, rows, ph / "4-size-card.jpg")
    old = d / "photos" / "2-detail.jpg"
    if old.exists():
        shutil.copyfile(old, ph / "5-detail.jpg")
    else:
        eb.mockup_detail(ImageOps.exif_transpose(Image.open(src)).convert("RGB"), ph / "5-detail.jpg")
    (v2 / "listing.json").write_text(json.dumps(listing, indent=2, ensure_ascii=False) + "\n")
    mb = sum(p.stat().st_size for p in ph.glob("*.jpg")) / 1e6
    print(f"  OK  {stem:20} {v2.relative_to(OUT)}  photos {mb:.1f} MB  mockup sizes {sizes[0]}..{sizes[-1]} in")
    return plan


def build_sets(hub, check):
    """sets.json: one "set of 3" per country, 15.00, using the heroes plus a third."""
    on_site = set()
    if hub:
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("stem", "stems") or (isinstance(v, str) and v.startswith("DSC_")):
                        on_site.update(v if isinstance(v, list) else [v])
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(hub)
    out = []
    for country, s in SETS.items():
        third = s["third"]
        if hub and third not in on_site:
            alt = next((k for k, v in eb.SEL.items() if country in v[1] and k not in s["heroes"] and k in on_site), None)
            if alt:
                third = alt
        stems = s["heroes"] + [third]
        names = [eb.SEL[x][0] for x in stems]
        rows = {x: ratio_rows(hero_dir(x)) for x in stems if (hero_dir(x) / "files").exists()}
        missing = [x for x in stems if x not in rows]
        desc = [f"Three printable photographs of {country} by Benjamin Ampel, sold together at a lower price than buying them one by one:"]
        desc += [f"{i + 1}. {n}" for i, n in enumerate(names)]
        desc += ["", "Each photo comes as the same set of print-ratio JPG files as its single listing (2x3, 3x4, 4x5, 11x14 and A-series where the photo allows; panoramic crops for the wide ones), with the largest clean size listed per file.",
                 "", "Etsy allows five files per listing, so the three photos are delivered as three ZIP archives plus a PDF with the size table and printing notes.",
                 "", "FACTS",
                 "Photographed by Benjamin Ampel on a Nikon. Every photo in the shop is my own. Files are delivered by Etsy instantly after purchase.",
                 "", "LICENSE",
                 "Personal use only. No resale, no sharing of the files, and no commercial use. Commercial licenses are available at purplelink.llc/photography/license/",
                 "", "RETURNS",
                 "Because this is a digital download, Etsy does not allow returns or exchanges once the files have been delivered. If a file will not open or you are unsure which one to print, message me through Etsy and I will help."]
        tags = {
            "Iceland": ["iceland wall art", "iceland print set", "set of 3 prints", "gallery wall set", "waterfall print",
                        "glacier lagoon", "sea cliffs print", "nordic decor", "large wall art", "living room art",
                        "printable photo", "travel print", "digital download"],
            "Switzerland": ["switzerland print", "swiss alps print", "set of 3 prints", "gallery wall set", "matterhorn print",
                            "zermatt wall art", "lauterbrunnen", "mountain wall art", "alpine decor", "living room art",
                            "printable photo", "travel print", "digital download"],
            "Japan": ["japan wall art", "japan print set", "set of 3 prints", "gallery wall set", "kyoto print",
                      "miyajima print", "torii gate print", "japanese decor", "zen wall decor", "living room art",
                      "printable photo", "travel print", "digital download"],
        }[country]
        entry = {"country": country, "title": s["title"][:140], "stems": stems, "names": names, "price": PRICE_SET,
                 "tags": tags, "description": "\n".join(desc),
                 "kits": {x: str(hero_dir(x)) for x in stems}, "kits_missing": missing,
                 "third_confirmed_on_site": (third in on_site) if hub else None}
        check_listing(entry, single=False)
        out.append(entry)
    if not check:
        (OUT / "sets.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stems", nargs="*")
    ap.add_argument("--check", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--hub-wait", type=int, default=0, help="seconds to wait for site/photography/hub-data.json")
    a = ap.parse_args()
    stems = a.stems or list(HEROES)
    bad = [s for s in stems if s not in HEROES]
    if bad:
        raise SystemExit(f"not a hero: {bad}")
    meta = {r["filename"].rsplit(".", 1)[0]: r for r in csv.DictReader(open(WS / "metadata-master.csv"))}
    plans = [build_hero(s, meta.get(s, {}), a.check) for s in stems]
    hub = load_hub_data(a.hub_wait)
    sets = build_sets(hub, a.check)
    if a.check:
        for p in plans:
            print(f"\n{p['stem']}  ->  {p['dir']}" + ("  (kit missing)" if p["kit_built_now"] else ""))
            if "title" in p:
                print(f"  title ({len(p['title'])}): {p['title']}")
                print(f"  tags: {', '.join(p['tags'])}")
                print(f"  ratios: {p['ratios']}")
                print(f"  mockup sizes: {p['mockup_sizes']}")
        print("\nsets:")
        for s in sets:
            print(f"  {s['country']}: {s['stems']}  ${s['price']:.2f}  missing kits: {s['kits_missing']}  hub: {s['third_confirmed_on_site']}")
        print("\n--check: nothing written")
    else:
        print(f"{len(plans)} heroes written; sets -> {OUT / 'sets.json'}  (hub-data.json {'used' if hub else 'not found, SEL fallback'})")


if __name__ == "__main__":
    main()
