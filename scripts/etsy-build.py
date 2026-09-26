#!/usr/bin/env python3
"""Build Etsy printable-wall-art listings: print files, listing photos, copy.

WHY THIS EXISTS
Etsy buyers searching "Iceland print" or "Matterhorn wall art" are a demand
pool none of the stock agencies or Fine Art America reach. A digital download
has no fulfilment cost, so each listing is $0.20 plus fees against a $5-12
sale. Etsy allows five files of up to 20MB per digital listing, which is why
each listing ships at most five print ratios.

WHAT IT PRODUCES (photo-licensing-workspace/etsy/<slug>/)
  files/     up to five JPEGs, one per print ratio (centre crop, no upscaling)
  photos/    three 2400x1800 listing photos: framed on a wall, a 100% detail
             crop, and a "what you get" card with honest size limits
  listing.json   title (<=140), 13 tags (<=20 chars each), description, price
and photo-licensing-workspace/etsy/listings.csv summarising all of them.

SIZE HONESTY
"Prints well up to N in" is the file's long edge at 150 ppi, and the size
list on each ratio drops any size whose long side exceeds that. Nothing is
upscaled, so no listed size exceeds what the pixels support.

  python3 scripts/etsy-build.py            # build everything
  python3 scripts/etsy-build.py DSC_1326   # rebuild one
"""
import csv, json, os, re, sys, unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
OUT = WS / "etsy"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
MAX_BYTES = 19_500_000
PPI = 150   # common floor for wall art seen from a few feet away
PRICE_SINGLE = 7.00

# stem: (name for title, place, theme, specific tags)
SEL = {
 "DSC_1326": ("Skogafoss Waterfall with Rainbow", "Iceland", "waterfall", ["skogafoss", "iceland waterfall", "rainbow print"]),
 "DSC_1362": ("Dyrholaey Sea Arch and Cliffs", "Iceland", "coast", ["dyrholaey", "sea arch print", "iceland coast"]),
 "DSC_1601": ("Icebergs in Jokulsarlon Glacier Lagoon", "Iceland", "glacier", ["jokulsarlon", "iceberg print", "glacier lagoon"]),
 "DSC_1615": ("Jokulsarlon Glacier Lagoon Panorama", "Iceland", "glacier", ["jokulsarlon", "glacier print", "panoramic print"]),
 "DSC_1152": ("Basalt Column Waterfall, Snaefellsnes", "Iceland", "waterfall", ["snaefellsnes", "basalt columns", "iceland waterfall"]),
 "DSC_1584": ("Fjadrargljufur Canyon from Above", "Iceland", "canyon", ["fjadrargljufur", "canyon print", "aerial landscape"]),
 "DSC_1570": ("Slot Canyon Waterfall", "Iceland", "waterfall", ["canyon waterfall", "iceland waterfall", "moss green art"]),
 "DSC_8669": ("Matterhorn Reflected in Riffelsee", "Zermatt, Switzerland", "mountain", ["matterhorn print", "riffelsee", "zermatt"]),
 "DSC_8610": ("Matterhorn Above the Clouds", "Zermatt, Switzerland", "mountain", ["matterhorn print", "zermatt", "alpine print"]),
 "DSC_8199": ("Bern Old Town Rooftops", "Switzerland", "city", ["bern print", "bern old town", "red rooftops"]),
 "DSC_8190": ("Bridge over the Aare River, Bern", "Switzerland", "city", ["bern print", "aare river", "bridge print"]),
 "DSC_8244-Pano": ("Interlaken Between Two Lakes Panorama", "Switzerland", "lake", ["interlaken", "lake thun", "lake brienz"]),
 "DSC_8496": ("Snowy Alpine Summit", "Switzerland", "mountain", ["alpine print", "snowy mountain", "mountain summit"]),
 "DSC_8511": ("Staubbach Falls, Lauterbrunnen", "Switzerland", "waterfall", ["lauterbrunnen", "staubbach falls", "swiss village"]),
 "DSC_8714": ("Gorner Glacier Panorama", "Zermatt, Switzerland", "glacier", ["gorner glacier", "zermatt", "glacier print"]),
 "DSC_8450": ("Green Alpine Valley from Jungfraujoch", "Switzerland", "mountain", ["jungfraujoch", "alpine valley", "green mountains"]),
 "DSC_8395": ("Snow-Dusted Swiss Alps", "Switzerland", "mountain", ["alpine print", "snowy mountains", "mountain range"]),
 "DSC_4094-Pano": ("Kyoto Temple Gate", "Japan", "temple", ["kyoto print", "temple gate", "japanese temple"]),
 "DSC_4038": ("Kiyomizu-dera Gate and Pagoda", "Kyoto, Japan", "temple", ["kiyomizu dera", "kyoto print", "pagoda print"]),
 "DSC_3638": ("Misty Hozu Gorge, Arashiyama", "Kyoto, Japan", "forest", ["arashiyama", "misty mountains", "kyoto print"]),
 "DSC_4368": ("Itsukushima Shrine Torii at Dusk", "Miyajima, Japan", "temple", ["miyajima", "torii gate", "itsukushima"]),
 "DSC_5058": ("Pink Cherry Blossoms", "Japan", "flower", ["cherry blossom", "sakura print", "pink flower art"]),
 "DSC_3977-Pano": ("Kyoto Cityscape Panorama", "Japan", "city", ["kyoto print", "kyoto skyline", "panoramic print"]),
 "DSC_7909-Pano": ("Cologne Skyline and Hohenzollern Bridge Panorama", "Germany", "city", ["cologne print", "cologne cathedral", "rhine river"]),
 "DSC_7933": ("Cologne Cathedral and Hohenzollern Bridge", "Germany", "city", ["cologne print", "cologne cathedral", "kolner dom"]),
 "DSC_7888": ("Cologne Cathedral at Dusk", "Germany", "city", ["cologne print", "cologne cathedral", "kolner dom"]),
 "DSC_7979": ("Heidelberg Old Town and Neckar River", "Germany", "city", ["heidelberg print", "neckar river", "german old town"]),
 "DSC_7559-Pano-Edit": ("Copenhagen Rooftops Panorama", "Denmark", "city", ["copenhagen print", "denmark print", "scandinavian art"]),
 "DSC_7220-Edit": ("Rowers on a Copenhagen Canal", "Denmark", "city", ["copenhagen print", "denmark print", "rowing print"]),
 "DSC_7750": ("Zuiderkerk Tower over an Amsterdam Canal", "Netherlands", "city", ["amsterdam print", "amsterdam canal", "zuiderkerk"]),
 "DSC_7761-Pano": ("Amstel River Panorama, Amsterdam", "Netherlands", "city", ["amsterdam print", "amstel river", "houseboats"]),
 "DSC_6629-Edit": ("Big Ben at Sunset", "London", "city", ["london print", "big ben print", "westminster"]),
 "DSC_6691": ("Tower Bridge Under Storm Clouds", "London", "city", ["london print", "tower bridge", "river thames"]),
 "DSC_4380": ("Waipio Valley Black Sand Beach", "Hawaii", "coast", ["waipio valley", "hawaii print", "big island"]),
 "DSC_4188-Pano": ("Kilauea Caldera Panorama", "Hawaii", "volcano", ["kilauea", "hawaii print", "volcano print"]),
 "DSC_7583": ("Saguaro Sunset, Tucson", "Arizona", "desert", ["saguaro print", "tucson print", "desert sunset"]),
 "DSC_3490": ("Saguaro Silhouette at Sunset", "Arizona", "desert", ["saguaro print", "cactus print", "desert sunset"]),
 "DSC_0027": ("Shooting Star over a Desert Mountain", "Arizona", "night", ["shooting star", "night sky print", "astrophotography"]),
 "DSC_7629": ("Atlanta Skyline at Golden Hour", "Georgia", "city", ["atlanta print", "atlanta skyline", "georgia wall art"]),
 "DSC_4821-Pano": ("Sunburst Through Redwood Trees", "California", "forest", ["redwood print", "forest print", "sun rays"]),
 "DSC_2163-Enhanced-NR": ("Autumn Forest Canopy", "", "forest", ["autumn print", "fall foliage", "forest print"]),
 "DSC_5165": ("Mossy Forest Waterfall, North Georgia", "Georgia", "waterfall", ["waterfall print", "north georgia", "forest waterfall"]),
 "DSC_5033-Pano": ("Vancouver and English Bay Panorama", "British Columbia", "city", ["vancouver print", "english bay", "canada print"]),
}

THEME_TAGS = {
 "waterfall": ["waterfall wall art", "nature photography"],
 "coast": ["ocean wall art", "coastal decor"],
 "glacier": ["nordic decor", "blue wall art"],
 "canyon": ["nature photography", "landscape print"],
 "mountain": ["mountain wall art", "swiss alps print"],
 "lake": ["mountain wall art", "swiss alps print"],
 "temple": ["japan wall art", "japanese decor"],
 "forest": ["forest wall art", "nature photography"],
 "flower": ["floral wall art", "spring decor"],
 "city": ["city print", "travel wall art"],
 "volcano": ["nature photography", "landscape print"],
 "desert": ["desert wall art", "southwest decor"],
 "night": ["night sky wall art", "southwest decor"],
}
COUNTRY_TAG = {"Iceland": "iceland wall art", "Switzerland": "switzerland print",
               "Japan": "japan print", "Germany": "germany print", "Denmark": "denmark print",
               "Netherlands": "netherlands print", "London": "england print",
               "Hawaii": "hawaii wall art", "Arizona": "arizona print", "Georgia": "georgia print",
               "California": "california print", "British Columbia": "canada wall art"}
GENERIC = ["printable wall art", "digital download", "photography print",
           "travel photography", "large wall art", "gift for traveler", "landscape print"]

# (label, long/short ratio, [(size label, long side in inches)])
RATIOS_STD = [("2x3", 3/2, [("4x6", 6), ("8x12", 12), ("12x18", 18), ("16x24", 24), ("20x30", 30), ("24x36", 36)]),
              ("3x4", 4/3, [("6x8", 8), ("9x12", 12), ("12x16", 16), ("18x24", 24)]),
              ("4x5", 5/4, [("8x10", 10), ("16x20", 20)]),
              ("11x14", 14/11, [("11x14", 14)]),
              ("ISO", 2**0.5, [("A5", 8.3), ("A4", 11.7), ("A3", 16.5), ("A2", 23.4), ("A1", 33.1)])]
PANO_SIZES = {"2x1": [("10x20", 20), ("12x24", 24), ("18x36", 36), ("24x48", 48)],
              "3x1": [("8x24", 24), ("12x36", 36), ("20x60", 60)]}


def fit_sizes(sizes, long_px):
    ok = [lab for lab, L in sizes if L <= long_px / PPI]
    unit = "" if ok and ok[0].startswith("A") else " in"
    return ", ".join(ok) + unit if ok else ""


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def crop_ratio(im, r):
    """Centre-crop to long/short ratio r, keeping the image's orientation."""
    w, h = im.size
    land = w >= h
    L, S = (w, h) if land else (h, w)
    if L / S > r:            # too long: trim the long edge
        nL, nS = round(S * r), S
    else:                    # too square: trim the short edge
        nL, nS = L, round(L / r)
    nw, nh = (nL, nS) if land else (nS, nL)
    x, y = (w - nw) // 2, (h - nh) // 2
    return im.crop((x, y, x + nw, y + nh))


def save_under(im, path, cap_long=None):
    if cap_long and max(im.size) > cap_long:
        f = cap_long / max(im.size)
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    for q in (92, 88, 84, 80, 76):
        im.save(path, "JPEG", quality=q, optimize=True, dpi=(300, 300))
        if path.stat().st_size <= MAX_BYTES:
            return im.size
    im = im.resize((round(im.width * .85), round(im.height * .85)), Image.LANCZOS)
    return save_under(im, path)


def fonts():
    av = "/System/Library/Fonts/Avenir Next.ttc"
    ge = "/System/Library/Fonts/Supplemental/Georgia.ttf"
    return (lambda s: ImageFont.truetype(ge, s)), (lambda s, i=7: ImageFont.truetype(av, s, index=i))


def mockup_wall(im, path):
    W, H = 2400, 1800
    bg = Image.new("RGB", (W, H), (236, 231, 224))
    g = Image.linear_gradient("L").resize((W, H)).point(lambda v: 255 - v // 10)
    bg = Image.composite(bg, Image.new("RGB", (W, H), (214, 208, 200)), g)
    ImageDraw.Draw(bg).rectangle([0, H - 150, W, H], fill=(196, 184, 168))
    ImageDraw.Draw(bg).rectangle([0, H - 156, W, H - 150], fill=(250, 248, 244))
    maxw, maxh = (1500, 1050) if im.width >= im.height else (820, 1180)
    if im.width / im.height > 2:
        maxw, maxh = 2150, 1000
    f = min(maxw / im.width, maxh / im.height)
    pw, ph = round(im.width * f), round(im.height * f)
    mat, fr = round(min(pw, ph) * .09), 22
    ow, oh = pw + 2 * (mat + fr), ph + 2 * (mat + fr)
    x, y = (W - ow) // 2, max(90, (H - 150 - oh) // 2 - 20)
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rectangle([x + 18, y + 30, x + ow + 18, y + oh + 30], fill=120)
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    bg = Image.composite(Image.new("RGB", (W, H), (120, 112, 104)), bg, sh)
    d = ImageDraw.Draw(bg)
    d.rectangle([x, y, x + ow, y + oh], fill=(33, 30, 28))
    d.rectangle([x + fr, y + fr, x + ow - fr, y + oh - fr], fill=(248, 247, 244))
    bg.paste(im.resize((pw, ph), Image.LANCZOS), (x + fr + mat, y + fr + mat))
    bg.save(path, "JPEG", quality=90)


def mockup_detail(im, path):
    W, H = 2400, 1800
    cx, cy = im.width // 2, im.height // 2
    tw, th = min(im.width, W), min(im.height, H)
    crop = im.crop((cx - tw // 2, cy - th // 2, cx - tw // 2 + tw, cy - th // 2 + th))
    if crop.size != (W, H):
        crop = ImageOps.fit(crop, (W, H), Image.LANCZOS)
    serif, sans = fonts()
    d = ImageDraw.Draw(crop)
    label = "Full-resolution detail"
    fnt = sans(40, 2)
    bw = d.textlength(label, font=fnt) + 60
    d.rounded_rectangle([40, H - 120, 40 + bw, H - 40], 40, fill=(20, 20, 20))
    d.text((70, H - 104), label, font=fnt, fill=(245, 245, 245))
    crop.save(path, "JPEG", quality=90)


def mockup_card(name, files, max_in, path):
    W, H = 2400, 1800
    bg = Image.new("RGB", (W, H), (247, 244, 239))
    d = ImageDraw.Draw(bg)
    serif, sans = fonts()
    d.text((160, 150), "What you get", font=serif(110), fill=(34, 30, 28))
    d.text((160, 300), name, font=sans(52), fill=(95, 88, 82))
    y = 450
    for label, sizes in files:
        d.text((160, y), label, font=sans(54, 2), fill=(34, 30, 28))
        d.text((640, y + 4), sizes, font=sans(50), fill=(70, 64, 60))
        y += 120
    y += 40
    d.line([160, y, W - 160, y], fill=(210, 202, 194), width=3)
    y += 60
    for line in (f"{len(files)} high-resolution JPG files, instant download",
                 f"Prints well up to about {max_in} inches on the long side",
                 "Print at home, at a local print shop, or online",
                 "Digital file only. No physical item is shipped."):
        d.text((160, y), line, font=sans(48), fill=(70, 64, 60))
        y += 84
    bg.save(path, "JPEG", quality=90)


def tags_for(place, theme, specific):
    out = []
    country = next((v for k, v in COUNTRY_TAG.items() if k in place), None)
    for t in specific + ([country] if country else []) + THEME_TAGS[theme] + GENERIC:
        t = t.lower().strip()
        if t and len(t) <= 20 and t not in out:
            out.append(t)
    return out[:13]


def description(name, place, meta_desc, files, max_in):
    where = f" ({place})" if place else ""
    lines = [f"{name}{where}. A printable photograph by Benjamin Ampel, taken on a Nikon.",
             "", meta_desc, "",
             "WHAT YOU GET",
             f"{len(files)} high-resolution JPG files, so you can print the size that fits your frame:"]
    lines += [f"- {lab} ratio: {sz}" for lab, sz in files]
    lines += ["", f"The files print well up to about {max_in} inches on the long side. Larger prints are possible but will be softer.",
              "", "HOW IT WORKS",
              "1. Buy the listing. Etsy emails you a download link, and the files are also under Purchases and Reviews.",
              "2. Download the file that matches your frame.",
              "3. Print at home on photo paper, or send it to a print shop or an online lab.",
              "", "PLEASE NOTE",
              "- This is a digital download. No physical print or frame is shipped.",
              "- Colors vary a little between screens and printers.",
              "- Personal use only. The files may not be resold, shared, or used commercially.",
              "- Frame and room shown in the photos are for illustration only."]
    return "\n".join(lines)


def build(stem, meta):
    name, place, theme, specific = SEL[stem]
    src = next((p for p in (SRC / f"{stem}.jpeg", SRC / f"{stem}.jpg") if p.exists()), None)
    if not src:
        print(f"  MISSING {stem}"); return None
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    d = OUT / slug(f"{name}-{stem}")
    (d / "files").mkdir(parents=True, exist_ok=True)
    (d / "photos").mkdir(exist_ok=True)
    for old in (d / "files").glob("*.jpg"):
        old.unlink()
    aspect = max(im.size) / min(im.size)
    base = slug(name)
    files = []
    if aspect > 1.8:        # panorama: native plus the two standard pano ratios
        sizes = [(f"{aspect:.1f}:1 native", None), ("2x1", 2.0)]
        if aspect >= 3:
            sizes.append(("3x1", 3.0))
        for lab, r in sizes:
            c = im if r is None else crop_ratio(im, r)
            fn = "native" if r is None else lab
            wl = max(save_under(c, d / "files" / f"{base}_{fn}.jpg", cap_long=14000))
            sz = "Panoramic frames and custom sizes" if r is None else fit_sizes(PANO_SIZES[lab], wl)
            if sz:
                files.append((lab, sz))
            else:
                (d / "files" / f"{base}_{fn}.jpg").unlink()
    else:
        for lab, r, sizes in RATIOS_STD:
            wl = max(save_under(crop_ratio(im, r), d / "files" / f"{base}_{lab}.jpg"))
            sz = fit_sizes(sizes, wl)
            if sz:
                files.append((lab, sz))
            else:
                (d / "files" / f"{base}_{lab}.jpg").unlink()
    long_px = max(Image.open(p).size[0] if Image.open(p).size[0] > Image.open(p).size[1] else Image.open(p).size[1]
                  for p in (d / "files").glob("*.jpg"))
    max_in = long_px // PPI
    mockup_wall(im, d / "photos" / "1-wall.jpg")
    mockup_detail(im, d / "photos" / "2-detail.jpg")
    mockup_card(name, files, max_in, d / "photos" / "3-what-you-get.jpg")
    tail = f" Print, {place} Wall Art, Printable Photography, Digital Download" if place else " Print, Printable Nature Photography, Digital Download"
    title = (name + tail)[:140]
    listing = {"stem": stem, "title": title, "tags": tags_for(place, theme, specific),
               "description": description(name, place, meta.get("description", ""), files, max_in),
               "price": PRICE_SINGLE, "files": sorted(p.name for p in (d / "files").glob("*.jpg")),
               "photos": sorted(p.name for p in (d / "photos").glob("*.jpg")), "dir": str(d)}
    (d / "listing.json").write_text(json.dumps(listing, indent=2, ensure_ascii=False))
    sizes_mb = [round((d / "files" / f).stat().st_size / 1e6, 1) for f in listing["files"]]
    print(f"  OK  {stem:22} {len(files)} files {sizes_mb} MB  max {max_in}in  tags={len(listing['tags'])}")
    return listing


def main():
    meta = {r["filename"].rsplit(".", 1)[0]: r for r in csv.DictReader(open(WS / "metadata-master.csv"))}
    stems = sys.argv[1:] or list(SEL)
    OUT.mkdir(exist_ok=True)
    built = [x for s in stems if (x := build(s, meta.get(s, {})))]
    idx = OUT / "listings.csv"
    rows = {}
    if idx.exists() and sys.argv[1:]:
        rows = {r["stem"]: r for r in csv.DictReader(open(idx))}
    for l in built:
        rows[l["stem"]] = {"stem": l["stem"], "title": l["title"], "tags": ",".join(l["tags"]),
                           "price": l["price"], "dir": l["dir"]}
    with open(idx, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stem", "title", "tags", "price", "dir"])
        w.writeheader(); w.writerows(rows.values())
    print(f"{len(built)} built -> {idx}")


if __name__ == "__main__":
    main()
