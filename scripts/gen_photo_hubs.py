#!/usr/bin/env python3
"""Generate the destination hub pages under purplelink.llc/photography/.

One page per country (/photography/iceland/) and one per place
(/photography/iceland/skogafoss/), built from the photo library's own
metadata. Each page carries 150-250 words of hand-written context from
scripts/data/photo-places.json, a grid of watermarked photographs, a
"License" link per photograph into /photography/license/, an ImageObject
JSON-LD block per photograph (creator, license, acquireLicensePage, so
Google Images can show the Licensable badge) and an entry in
site/sitemap-images.xml.

Why: the photographs are only discoverable where they are sold, and those
pages belong to the agencies. These pages are the one place that is ours,
that search engines can index by place name, and that every other channel
(pins, short videos, blogger credits, pitches) can point at.

Inputs
  photo-licensing-workspace/batch-001-metadata.csv   filename,title,description,keywords
  photo-licensing-workspace/alamy-locations.json     filename -> country (fallback)
  photo-licensing-workspace/etsy/listed.json         live Etsy listings (print links)
  scripts/data/photo-places.json                     taxonomy, intros, facts
  /Volumes/Extreme SSD/Nikon Photos/<stem>.jpeg      originals (never modified)

Outputs (all committed)
  site/photography/<country>/index.html, <country>/<place>/index.html
  site/assets/photography/hub/<stem>-1200.webp, -480.webp   (watermarked)
  site/photography/hub-data.json       what is on which page, for the other scripts
  site/sitemap-images.xml
  site/photography/index.html          the "Browse by place" section between the
                                       <!-- hubs:start --> / <!-- hubs:end --> markers

  python3 scripts/gen_photo_hubs.py            # build everything
  python3 scripts/gen_photo_hubs.py --check    # report what would change, write nothing
"""
import argparse, csv, datetime, html, json, os, re, sys, unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
_WS = Path(os.environ.get("PL_WORKSPACE") or (ROOT / "photo-licensing-workspace"))
WS = _WS if _WS.exists() else Path("/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace")
SRC = Path(os.environ.get("PL_PHOTOS") or "/Volumes/Extreme SSD/Nikon Photos")
PLACES = ROOT / "scripts" / "data" / "photo-places.json"
OUT_IMG = SITE / "assets" / "photography" / "hub"
OUT = SITE / "photography"
HUB_DATA = OUT / "hub-data.json"
IMG_SITEMAP = SITE / "sitemap-images.xml"
BASE = "https://purplelink.llc"
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
TILE_TEXT = "BENJAMIN AMPEL  ·  PURPLELINK.LLC"
MAX_PER_PLACE = 16
MAX_COUNTRY_EXTRA = 12
ETSY_SHOP = "https://www.etsy.com/shop/PurplelinkDesigns"
FAA = "https://fineartamerica.com/profiles/benjamin-ampel"

# The ten slideshow picks come first on their pages.
HEROES = ["DSC_1326", "DSC_4368", "DSC_8669", "DSC_6629-Edit", "DSC_1601", "DSC_7583",
          "DSC_8714", "DSC_4380", "DSC_3638", "DSC_7559-Pano-Edit"]

# A recognisable person in the frame: shown on the page (the caption says
# where it was taken) but not offered for a commercial license without a
# release, so the per-photo action reads "Editorial use: ask" instead.
PEOPLE = re.compile(r"\b(man|men|woman|women|people|person|crowd|crowds|portrait|wedding|bride|groom|friends|"
                    r"family|smiling|couple|boy|girl|child|children|kid|kids|fans|player|players|team|cheer|"
                    r"selfie|graduate|graduation|tattoo|runner|hiker|hikers|tourist|tourists|visitor|visitors|"
                    r"pedestrians|walker|cyclist|cyclists|spectators|audience)\b", re.I)
# Never on these pages: sport and event coverage, pets, product shots.
SKIP = re.compile(r"\b(basketball|baseball|football|soccer|derby|all-star|ncaa|mlb|wildcats|mckale|truist park|"
                  r"pirates|rays|mariners|great pyrenees|dog|dogs|puppy|cat\b|kitten|laptop|keyboard|screenshot)\b", re.I)

COUNTRY_BY_NAME = {"Iceland": "iceland", "Japan": "japan", "Switzerland": "switzerland",
                   "United Kingdom": "united-kingdom", "Denmark": "denmark", "Netherlands": "netherlands",
                   "Germany": "germany", "United States": "united-states", "Canada": "canada", "Panama": "panama"}


def slug_of(stem):
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")


def esc(s):
    return html.escape(str(s), quote=True)


def norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


# ── watermark (same look as photo-site-images.py) ───────────────────────────

def tile_layer(size, font_px, rot=-24):
    w, h = size
    diag = int((w * w + h * h) ** 0.5) + 200
    font = ImageFont.truetype(FONT, font_px)
    txt = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    tw = d.textlength(TILE_TEXT, font=font)
    stepx, stepy = int(tw + font_px * 3.2), int(font_px * 8.8)
    row = 0
    for y in range(-stepy, diag + stepy, stepy):
        off = (stepx // 2) if row % 2 else 0
        for x in range(-stepx + off, diag + stepx, stepx):
            d.text((x + 2, y + 2), TILE_TEXT, font=font, fill=(0, 0, 0, 120))
            d.text((x, y), TILE_TEXT, font=font, fill=(255, 255, 255, 140))
        row += 1
    txt = txt.rotate(rot, resample=Image.BICUBIC)
    left, top = (diag - w) // 2, (diag - h) // 2
    return txt.crop((left, top, left + w, top + h))


def watermark(im, strength=1.0):
    im = im.convert("RGBA")
    w, h = im.size
    font_px = max(14, int(w / 46 * strength))
    im.alpha_composite(tile_layer(im.size, font_px))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, max(11, int(w / 90)))
    plate = "© Benjamin Ampel / purplelink.llc/photography"
    tw = d.textlength(plate, font=f)
    pad = max(6, w // 160)
    d.rectangle((w - tw - 3 * pad, h - f.size - 3 * pad, w, h), fill=(0, 0, 0, 150))
    d.text((w - tw - 1.5 * pad, h - f.size - 1.5 * pad), plate, font=f, fill=(255, 255, 255, 230))
    return im.convert("RGB")


def build_images(stem, check=False):
    """Write <slug>-1200.webp and <slug>-480.webp; returns (w, h) of the 1200."""
    src = SRC / f"{stem}.jpeg"
    if not src.exists():
        return None
    s = slug_of(stem)
    big, small = OUT_IMG / f"{s}-1200.webp", OUT_IMG / f"{s}-480.webp"
    if big.exists() and small.exists() and big.stat().st_mtime >= src.stat().st_mtime:
        with Image.open(big) as im:
            return im.size
    if check:
        return (1200, 800)
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        b = im.copy(); b.thumbnail((1200, 1200), Image.LANCZOS)
        watermark(b).save(big, "WEBP", quality=72, method=6)
        t = im.copy(); t.thumbnail((480, 480), Image.LANCZOS)
        watermark(t, 1.1).save(small, "WEBP", quality=70, method=6)
        return b.size


# ── data ────────────────────────────────────────────────────────────────────

def load_rows():
    rows = []
    with open(WS / "batch-001-metadata.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            fn = r["filename"]
            if not fn.startswith("DSC") or not fn.lower().endswith(".jpeg") or "IMG_" in fn:
                continue
            stem = fn[:-5]
            blob = " ".join([r["title"], r["description"], r["keywords"].replace(";", " ")])
            if SKIP.search(blob):
                continue
            rows.append({"stem": stem, "title": r["title"].strip(), "caption": r["description"].strip(),
                         "keywords": [k.strip() for k in r["keywords"].split(";") if k.strip()],
                         "people": bool(PEOPLE.search(r["title"])), "_blob": norm(blob)})
    return rows


def load_countries():
    p = WS / "alamy-locations.json"
    return json.loads(p.read_text()) if p.exists() else {}


def load_etsy():
    p = WS / "etsy" / "listed.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text())
    return {k: f"{ETSY_SHOP}/search?search_query={html.escape(v['title'].split(',')[0])}".replace(" ", "+")
            for k, v in d.items()}


def assign(rows, taxonomy, countries):
    """Return {country_slug: {place_slug: [rows], "_extra": [rows]}}."""
    out = {c["slug"]: {"_extra": []} for c in taxonomy["countries"]}
    matchers = []
    for c in taxonomy["countries"]:
        for p in c["places"]:
            out[c["slug"]][p["slug"]] = []
            matchers.append((c["slug"], p["slug"], [re.compile(norm(m), re.I) for m in p["match"]]))
    for r in rows:
        hit = next(((cs, ps) for cs, ps, res in matchers if any(x.search(r["_blob"]) for x in res)), None)
        if hit:
            out[hit[0]][hit[1]].append(r)
            continue
        cs = COUNTRY_BY_NAME.get(countries.get(r["stem"] + ".jpeg", ""))
        if cs:
            out[cs]["_extra"].append(r)
    rank = {s: i for i, s in enumerate(HEROES)}

    def order(lst, cap):
        lst.sort(key=lambda r: (rank.get(r["stem"], 99), r["people"], r["stem"]))
        return lst[:cap]
    for cs in out:
        for ps in list(out[cs]):
            out[cs][ps] = order(out[cs][ps], MAX_COUNTRY_EXTRA if ps == "_extra" else MAX_PER_PLACE)
    return out


# ── html ────────────────────────────────────────────────────────────────────

HEAD = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>{title} | Purplelink</title>
    <meta name="description" content="{desc}">
    <link rel="canonical" href="{url}">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{og_title}">
    <meta property="og:description" content="{desc}">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:image:width" content="{og_w}">
    <meta property="og:image:height" content="{og_h}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{og_title}">
    <meta name="twitter:description" content="{desc}">
    <meta name="twitter:image" content="{og_image}">
    <meta name="twitter:image:alt" content="{og_alt}">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preload" href="/assets/fonts/fraunces-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
    <script src="/theme.js"></script>
    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/photography/hubs.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
{jsonld}
    </script>
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-mark.svg" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/products/">Products</a>
        <a href="/tools/">Tools</a>
        <a href="/guides/">Guides</a>
        <a href="/blog/">Blog</a>
        <a href="/about/">About</a>
      </nav>
    </header>

    <main id="main-content" class="hub-page">
"""

TAIL = """    </main>
    <footer class="footer"></footer>
  </body>
</html>
"""


def image_object(img):
    return {"@type": "ImageObject", "contentUrl": BASE + img["src"], "thumbnailUrl": BASE + img["thumb"],
            "name": img["title"], "description": img["caption"], "width": img["w"], "height": img["h"],
            "creator": {"@type": "Person", "name": "Benjamin Ampel"},
            "creditText": "Benjamin Ampel / purplelink.llc", "copyrightNotice": "© Benjamin Ampel",
            "license": f"{BASE}/photography/license/",
            "acquireLicensePage": f"{BASE}/photography/license/?photo={img['stem']}"}


def crumbs(items):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}


def figure(img, etsy):
    if img["people"]:
        act = f'<a href="mailto:ben@purplelink.llc?subject={esc("Editorial license: " + img["stem"])}">Editorial use: ask</a>'
    else:
        act = f'<a href="/photography/license/?photo={esc(img["stem"])}">License</a>'
    if img["stem"] in etsy:
        act += f'<a href="{esc(etsy[img["stem"]])}" rel="noopener noreferrer" target="_blank">Print</a>'
    return (f'          <figure class="hub-item" data-reveal>\n'
            f'            <a class="hub-img" href="{esc(img["src"])}"><img src="{esc(img["thumb"])}" '
            f'srcset="{esc(img["thumb"])} 480w, {esc(img["src"])} 1200w" sizes="(min-width: 900px) 30vw, (min-width: 600px) 45vw, 92vw" '
            f'width="{img["tw"]}" height="{img["th"]}" alt="{esc(img["caption"])}" loading="lazy" decoding="async"></a>\n'
            f'            <figcaption><span class="hub-title">{esc(img["title"])}</span><span class="hub-actions">{act}</span></figcaption>\n'
            f'          </figure>\n')


def grid(images, etsy):
    return '        <div class="hub-grid">\n' + "".join(figure(i, etsy) for i in images) + "        </div>\n"


def page(title, desc, url, images, body, crumb_items, og_title=None):
    og = images[0] if images else None
    jl = {"@context": "https://schema.org", "@graph": [crumbs(crumb_items)] + ([{
        "@type": "ImageGallery", "name": title, "url": url,
        "associatedMedia": [image_object(i) for i in images]}] if images else [])}
    return (HEAD.format(title=esc(title), desc=esc(desc), url=url, og_title=esc(og_title or title),
                        og_image=BASE + (og["src"] if og else "/assets/photography/matterhorn-2200.webp"),
                        og_w=og["w"] if og else 2200, og_h=og["h"] if og else 1464,
                        og_alt=esc(og["caption"] if og else title),
                        jsonld=json.dumps(jl, indent=2, ensure_ascii=False)) + body + TAIL)


def shop_strip():
    return ('        <aside class="hub-shops" data-reveal>\n'
            '          <p>Prints: <a href="' + FAA + '" rel="noopener noreferrer" target="_blank">Fine Art America</a> ships finished prints; '
            '<a href="' + ETSY_SHOP + '" rel="noopener noreferrer" target="_blank">Etsy</a> sells the files to print yourself. '
            'Licenses: <a href="/photography/license/">three fixed tiers</a>, delivered as a clean full-resolution file.</p>\n'
            '        </aside>\n')


def write(path, text, check, changed):
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    changed.append(str(path.relative_to(ROOT)))
    if not check:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    taxonomy = json.loads(PLACES.read_text(encoding="utf-8"))
    rows = load_rows()
    assigned = assign(rows, taxonomy, load_countries())
    etsy = load_etsy()
    changed, data = [], {"generated": datetime.date.today().isoformat(), "countries": []}
    sitemap = []

    def prep(r):
        size = build_images(r["stem"], a.check)
        if not size:
            return None
        s = slug_of(r["stem"])
        w, h = size
        tw = 480 if w >= h else round(480 * w / h)
        th = round(480 * h / w) if w >= h else 480
        return {"stem": r["stem"], "title": r["title"], "caption": r["caption"], "keywords": r["keywords"],
                "people": r["people"], "w": w, "h": h, "tw": tw, "th": th,
                "src": f"/assets/photography/hub/{s}-1200.webp", "thumb": f"/assets/photography/hub/{s}-480.webp"}

    index_cards = []
    for c in taxonomy["countries"]:
        cs = c["slug"]
        curl = f"{BASE}/photography/{cs}/"
        cdata = {"slug": cs, "name": c["name"], "intro": c["intro"], "url": curl, "places": [], "extra": []}
        place_cards = []
        for p in c["places"]:
            imgs = [x for x in (prep(r) for r in assigned[cs][p["slug"]]) if x]
            if not imgs:
                continue
            purl = f"{curl}{p['slug']}/"
            pdata = {"slug": p["slug"], "name": p["name"], "intro": p["intro"], "fact": p["fact"], "url": purl, "images": imgs}
            cdata["places"].append(pdata)
            body = (f'      <nav class="hub-crumbs" aria-label="Breadcrumb"><a href="/photography/">Photography</a> <span aria-hidden="true">/</span> '
                    f'<a href="/photography/{cs}/">{esc(c["name"])}</a> <span aria-hidden="true">/</span> <span aria-current="page">{esc(p["name"])}</span></nav>\n'
                    f'      <section class="hub-head">\n        <h1>{esc(p["name"])}</h1>\n        <p class="hub-intro">{esc(p["intro"])}</p>\n'
                    f'        <p class="hub-fact">{esc(p["fact"])}</p>\n      </section>\n'
                    f'      <section class="hub-photos" aria-label="Photographs of {esc(p["name"])}">\n' + grid(imgs, etsy) + shop_strip() + '      </section>\n')
            title = f"{p['name']} photographs"
            desc = f"{len(imgs)} photographs of {p['name']} by Benjamin Ampel, available as prints and to license. {p['fact']}"
            write(OUT / cs / p["slug"] / "index.html",
                  page(title, desc[:300], purl, imgs, body, [("Home", BASE + "/"), ("Photography", BASE + "/photography/"), (c["name"], curl), (p["name"], purl)]),
                  a.check, changed)
            sitemap.append((purl, imgs))
            place_cards.append(f'          <a class="hub-card" href="/photography/{cs}/{p["slug"]}/" data-reveal>\n'
                               f'            <img src="{esc(imgs[0]["thumb"])}" alt="" width="{imgs[0]["tw"]}" height="{imgs[0]["th"]}" loading="lazy" decoding="async">\n'
                               f'            <span class="hub-card-body"><span class="hub-card-name">{esc(p["name"])}</span>'
                               f'<span class="hub-card-count">{len(imgs)} photographs</span></span>\n          </a>\n')
        extra = [x for x in (prep(r) for r in assigned[cs]["_extra"]) if x]
        cdata["extra"] = extra
        all_imgs = [i for p in cdata["places"] for i in p["images"]] + extra
        if not all_imgs:
            continue
        body = (f'      <nav class="hub-crumbs" aria-label="Breadcrumb"><a href="/photography/">Photography</a> <span aria-hidden="true">/</span> <span aria-current="page">{esc(c["name"])}</span></nav>\n'
                f'      <section class="hub-head">\n        <h1>{esc(c["name"])}</h1>\n        <p class="hub-intro">{esc(c["intro"])}</p>\n      </section>\n')
        if place_cards:
            body += '      <section class="hub-places" aria-label="Places">\n        <div class="hub-cards">\n' + "".join(place_cards) + '        </div>\n      </section>\n'
        if extra:
            body += (f'      <section class="hub-photos" aria-labelledby="hub-more">\n        <h2 id="hub-more">Elsewhere in {esc(c["name"])}</h2>\n'
                     + grid(extra, etsy) + '      </section>\n')
        body += '      <section class="hub-photos">\n' + shop_strip() + '      </section>\n'
        n = len(all_imgs)
        title = f"{c['name']} photographs"
        desc = f"{n} travel photographs from {c['name']} by Benjamin Ampel: " + ", ".join(p["name"] for p in cdata["places"])[:160] + ". Prints and licenses."
        write(OUT / cs / "index.html",
              page(title, desc[:300], curl, all_imgs, body,
                   [("Home", BASE + "/"), ("Photography", BASE + "/photography/"), (c["name"], curl)]),
              a.check, changed)
        sitemap.append((curl, extra))
        data["countries"].append(cdata)
        cover = cdata["places"][0]["images"][0] if cdata["places"] else extra[0]
        index_cards.append(f'          <a class="hub-card" href="/photography/{cs}/" data-reveal>\n'
                           f'            <img src="{esc(cover["thumb"])}" alt="" width="{cover["tw"]}" height="{cover["th"]}" loading="lazy" decoding="async">\n'
                           f'            <span class="hub-card-body"><span class="hub-card-name">{esc(c["name"])}</span>'
                           f'<span class="hub-card-count">{n} photographs</span></span>\n          </a>\n')

    # the index page's "Browse by place" section
    idx = OUT / "index.html"
    if idx.exists():
        txt = idx.read_text(encoding="utf-8")
        section = ('<!-- hubs:start -->\n      <section class="hub-browse" aria-labelledby="photo-places">\n'
                   '        <div class="hub-browse-head" data-reveal>\n          <h2 id="photo-places">Browse by place</h2>\n'
                   '          <p>Every photograph on these pages can be bought as a print or licensed as a clean file.</p>\n        </div>\n'
                   '        <div class="hub-cards hub-cards-index">\n' + "".join(index_cards) + '        </div>\n      </section>\n      <!-- hubs:end -->')
        if "<!-- hubs:start -->" in txt:
            new = re.sub(r"<!-- hubs:start -->.*?<!-- hubs:end -->", lambda m: section, txt, flags=re.S)
            if '/photography/hubs.css' not in new:
                new = new.replace('<link rel="stylesheet" href="/photography/photography.css',
                                  '<link rel="stylesheet" href="/photography/hubs.css">\n    <link rel="stylesheet" href="/photography/photography.css', 1)
            write(idx, new, a.check, changed)
        else:
            print("NOTE: site/photography/index.html has no <!-- hubs:start --> marker; index section not written")

    write(HUB_DATA, json.dumps(data, indent=1, ensure_ascii=False) + "\n", a.check, changed)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for url, imgs in sitemap:
        xml.append(f"  <url>\n    <loc>{esc(url)}</loc>")
        for i in imgs:
            xml.append(f"    <image:image>\n      <image:loc>{esc(BASE + i['src'])}</image:loc>\n      <image:title>{esc(i['title'])}</image:title>\n"
                       f"      <image:caption>{esc(i['caption'])}</image:caption>\n      <image:license>{BASE}/photography/license/</image:license>\n    </image:image>")
        xml.append("  </url>")
    xml.append("</urlset>\n")
    write(IMG_SITEMAP, "\n".join(xml), a.check, changed)

    total = sum(len(p["images"]) for c in data["countries"] for p in c["places"]) + sum(len(c["extra"]) for c in data["countries"])
    print(f"{len(data['countries'])} countries, {sum(len(c['places']) for c in data['countries'])} place pages, {total} photographs")
    if changed:
        print(("would change" if a.check else "wrote") + f" {len(changed)} file(s)")
        for f in changed[:40]:
            print("  " + f)
    return 1 if (a.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
