#!/usr/bin/env python3
"""Build the printable 2027 wall calendars sold at purplelink.llc/photography/calendars/.

Seven sets (Iceland, Japan, Switzerland, European cities, Arizona desert,
Hawaii, Best of), each a 13-page PDF (cover + twelve months) in two editions:
US Letter landscape with a Sunday-first week, and A4 landscape with a
Monday-first week. The photographs come from the hub data that
scripts/gen_photo_hubs.py writes (one list per place, best picture first);
the clean originals are read from the Nikon Photos volume, never from the
watermarked web files.

Inputs
  site/photography/hub-data.json                     from gen_photo_hubs.py
  /Volumes/Extreme SSD/Nikon Photos/<stem>.jpeg      clean originals

Outputs
  photo-licensing-workspace/calendars/calendar-2027-<set>-letter.pdf   clean, sold
  photo-licensing-workspace/calendars/calendar-2027-<set>-a4.pdf       clean, sold
  site/assets/photography/calendars/<set>-p1.jpg .. -p3.jpg            watermarked previews (1200 px)
  site/assets/photography/calendars/<set>-cover.jpg                    watermarked cover (800 px)

  python3 scripts/photo-calendars.py              # build everything
  python3 scripts/photo-calendars.py --check      # print the plan, write nothing
  python3 scripts/photo-calendars.py --sets iceland,hawaii
"""
import argparse, calendar, datetime, json, os, re, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_photo_hubs import HEROES, HUB_DATA, SITE, SRC, WS, watermark  # noqa: E402

from reportlab.lib.pagesizes import A4, landscape, letter  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
YEAR = 2027
OUT_PDF = WS / "calendars"
OUT_PREV = SITE / "assets" / "photography" / "calendars"
SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
SERIF_BOLD = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
MARGIN = 30.0               # pt, the thin white border around the photo
PHOTO_BAND = 0.62           # share of the page height given to the photo on month pages
COVER_BAND = 0.66
PHOTO_PX = (3300, 1750)     # longest printed photo is ~10.9 x 5.8 in: this is 300 dpi for that
JPEG_QUALITY = 80
PREVIEW_W, COVER_W = 1200, 800
INK, MUTED, LINE = (0.10, 0.09, 0.12), (0.40, 0.38, 0.44), (0.82, 0.80, 0.85)
PURPLE = (0.49, 0.23, 0.93)   # the site's theme colour, #7c3aed
NOTICE = "© Benjamin Ampel. Personal printing only; not for resale.  purplelink.llc/photography"

# (slug, display name, how to gather the candidates)
SETS = [
    ("iceland", "Iceland", {"countries": ["iceland"]}),
    ("japan", "Japan", {"countries": ["japan"]}),
    ("switzerland", "Switzerland", {"countries": ["switzerland"]}),
    ("european-cities", "European cities",
     {"places": ["london", "copenhagen", "amsterdam", "cologne", "heidelberg", "bern"]}),
    ("arizona-desert", "Arizona desert", {"places": ["sonoran-desert"]}),
    ("hawaii", "Hawaii", {"places": ["hawaii"]}),
    ("best-of", "Best of", {"heroes": True}),
]
EDITIONS = [("letter", landscape(letter), calendar.SUNDAY), ("a4", landscape(A4), calendar.MONDAY)]


# ── calendar grids ───────────────────────────────────────────────────────────

def month_weeks(month, firstweekday):
    """Rows of seven day numbers (0 = outside the month), checked against datetime."""
    weeks = calendar.Calendar(firstweekday).monthdayscalendar(YEAR, month)
    days_in_month = calendar.monthrange(YEAR, month)[1]
    first_col = (datetime.date(YEAR, month, 1).weekday() - firstweekday) % 7
    flat = [d for w in weeks for d in w if d]
    assert flat == list(range(1, days_in_month + 1)), (month, firstweekday)
    assert weeks[0][first_col] == 1 and all(d == 0 for d in weeks[0][:first_col]), (month, firstweekday)
    for w in weeks:
        for col, d in enumerate(w):
            if d:
                assert datetime.date(YEAR, month, d).weekday() == (firstweekday + col) % 7
    return weeks


def verify_all_grids():
    for _, _, fw in EDITIONS:
        for m in range(1, 13):
            month_weeks(m, fw)


# ── picking the photographs ─────────────────────────────────────────────────

# Subjects that read well on a wall, and subjects that do not (signs, interiors,
# museum cases, close-ups, people the hub's title check did not catch).
SCENIC = re.compile(r"waterfall|falls|mountain|lake|sunset|sunrise|dusk|skyline|cathedral|castle|beach|glacier|"
                    r"valley|canyon|river|bridge|aerial|panoram|shrine|temple|torii|cliff|coast|harbou?r|lagoon|"
                    r"iceberg|peak|alpine|church|tower|crater|caldera|volcan|lava|\bsea\b|ocean|rainbow|night sky|"
                    r"rooftops|old town|lightning|geyser|island|minster|palace|canal", re.I)
AVOID = re.compile(r"close-up|closeup|close view|interior|submarine|dancer|dance|golf|\bstore\b|billboard|\bwindow\b|"
                   r"carved|barrel|gauge|torpedo|cabin|hatch|display|museum|\bmodel\b|rally|crane|helicopter|caged|"
                   r"macaque|leash|arcade|shopping|market|stalls|traffic|parrot|swan|penguin|\bkoi\b|tulip|advertising|"
                   r"screens|\bbus\b|waste-to-energy|texture|burned|stump|portrait|busy|crowd|\bsign\b|signpost|"
                   r"signage|\btent\b|crate|fruit|gecko|warning|memorial|turret|inscription|newspaper|tools|motor|"
                   r"machinery|belongings|uniform|wreck|sunken|armor|niche|preening|pavilion tent|guardian statue|bell hanging|"
                   r"lawn|feeding|fireworks", re.I)
# Pictures the hub filed under a country they are not from (its matchers are by title words).
MISFILED = {"japan": re.compile(r"desert|arizona|tropical|palm|resort|pond garden|alpine|alps|swiss", re.I),
            "switzerland": re.compile(r"iceland|golf|log cabin|chough", re.I),
            "european-cities": re.compile(r"\bbears?\b|golf", re.I),
            "iceland": re.compile(r"tulip", re.I)}
SEASONAL = [(12, re.compile(r"christmas|holiday", re.I)), (4, re.compile(r"cherry blossom", re.I))]


def load_hub():
    data = json.loads(HUB_DATA.read_text(encoding="utf-8"))
    by_country = {c["slug"]: c for c in data["countries"]}
    by_place = {p["slug"]: (p, c) for c in data["countries"] for p in c["places"]}
    return by_country, by_place


def beyond_hub_cap():
    """The hub keeps 16 pictures per place, alphabetically after the heroes, which
    hides most of Hawaii and the Sonoran storms. Re-run the hub's own assignment
    with no cap so those are candidates too. Returns {country: {place: [rows]}}."""
    import gen_photo_hubs as g
    g.MAX_PER_PLACE = g.MAX_COUNTRY_EXTRA = 10 ** 6
    taxonomy = json.loads(g.PLACES.read_text(encoding="utf-8"))
    return g.assign(g.load_rows(), taxonomy, g.load_countries())


def usable(img, set_slug):
    if img["people"] or AVOID.search(img["title"]) or not (SRC / f"{img['stem']}.jpeg").exists():
        return False
    mis = MISFILED.get(set_slug)
    return not (mis and mis.search(img["title"] + " " + img.get("caption", "")))


def labelled(img, place):
    img = {**img, "place": place}
    if "w" not in img:
        with Image.open(SRC / f"{img['stem']}.jpeg") as im:
            img["w"], img["h"] = im.size
    return img


def score(img):
    """Heroes (the slideshow picks) lead, then landscape pictures, then scenic subjects."""
    hero = (len(HEROES) - HEROES.index(img["stem"])) * 10 if img["stem"] in HEROES else 0
    return hero + (3 if img["w"] >= img["h"] else 0) + min(2, len(SCENIC.findall(img["title"])))


def ranked(images, place, set_slug):
    out = [labelled(i, place) for i in images if usable(i, set_slug)]
    out.sort(key=lambda i: -score(i))     # stable: hub order (heroes first) breaks ties
    return out


def place_lists(set_slug, spec, by_country, by_place, full):
    """One ranked candidate list per place: the hub's pictures, then the ones past its cap."""
    lists = []

    def add(hub_imgs, more_rows, place):
        seen = {i["stem"] for i in hub_imgs}
        lst = ranked(list(hub_imgs) + [r for r in more_rows if r["stem"] not in seen], place, set_slug)
        if lst:
            lists.append(lst)

    for cs in spec.get("countries", []):
        c = by_country[cs]
        for p in c["places"]:
            add(p["images"], full.get(cs, {}).get(p["slug"], []), f"{p['name']}, {c['name']}")
        add(c["extra"], full.get(cs, {}).get("_extra", []), c["name"])
    for ps in spec.get("places", []):
        if ps in by_place:
            p, c = by_place[ps]
            add(p["images"], full.get(c["slug"], {}).get(ps, []), f"{p['name']}, {c['name']}")
    return lists


def round_robin(lists, n):
    """Best of each place first, landscape pictures before portrait ones."""
    picks, seen = [], set()
    for landscape in (True, False):
        cols = [[i for i in lst if (i["w"] >= i["h"]) == landscape] for lst in lists]
        k = 0
        while len(picks) < n and any(len(col) > k for col in cols):
            for col in cols:
                if k < len(col) and col[k]["stem"] not in seen and len(picks) < n:
                    picks.append(col[k]); seen.add(col[k]["stem"])
            k += 1
    return picks


def seasonal(months):
    """Put a Christmas picture in December and cherry blossom in April, if the set has one."""
    for month, rx in SEASONAL:
        j = next((i for i, img in enumerate(months) if rx.search(img["title"])), None)
        if j is not None and j != month - 1:
            months[j], months[month - 1] = months[month - 1], months[j]
    return months


def plan_sets(only=None):
    by_country, by_place = load_hub()
    full = beyond_hub_cap()
    index = {i["stem"]: labelled(i, f"{p['name']}, {c['name']}")
             for c in by_country.values() for p in c["places"] for i in p["images"]}
    plans = []
    for slug, name, spec in SETS:
        if spec.get("heroes"):
            uniq = [index[s] for s in HEROES if s in index and usable(index[s], slug)]
            k = 0                                    # then the strongest of every other set
            while len(uniq) < 13 and any(len(o["unique"]) > k for o in plans):
                for other in plans:
                    if k < len(other["unique"]) and other["unique"][k]["stem"] not in {u["stem"] for u in uniq} and len(uniq) < 13:
                        uniq.append(other["unique"][k])
                k += 1
        else:
            uniq = round_robin(place_lists(slug, spec, by_country, by_place, full), 13)
        if not uniq:
            print(f"NOTE: {slug}: no usable photographs, skipped")
            continue
        cover = uniq[0]
        months = uniq[1:13] if len(uniq) >= 13 else [uniq[i % len(uniq)] for i in range(12)]
        plans.append({"slug": slug, "name": name, "unique": uniq, "cover": cover, "months": seasonal(months)})
    if only:
        plans = [p for p in plans if p["slug"] in only]
    return plans


# ── photographs at print size ───────────────────────────────────────────────

class PhotoCache:
    def __init__(self, folder):
        self.folder, self.sizes = Path(folder), {}

    def get(self, stem):
        """Path of a clean JPEG scaled to fit PHOTO_PX, plus its pixel size."""
        if stem in self.sizes:
            return self.folder / f"{stem}.jpg", self.sizes[stem]
        out = self.folder / f"{stem}.jpg"
        with Image.open(SRC / f"{stem}.jpeg") as im:
            im.draft("RGB", (PHOTO_PX[0] * 2, PHOTO_PX[1] * 2))
            im = im.convert("RGB")
            im.thumbnail(PHOTO_PX, Image.LANCZOS)
            im.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=False, subsampling=1)
            self.sizes[stem] = im.size
        return out, im.size


# ── drawing ─────────────────────────────────────────────────────────────────

def fonts():
    pdfmetrics.registerFont(TTFont("Serif", SERIF))
    pdfmetrics.registerFont(TTFont("Serif-Bold", SERIF_BOLD))


def fit(w, h, bw, bh):
    s = min(bw / w, bh / h)
    return w * s, h * s


def ellipsize(c, text, font, size, max_w):
    if pdfmetrics.stringWidth(text, font, size) <= max_w:
        return text
    while text and pdfmetrics.stringWidth(text + "…", font, size) > max_w:
        text = text[:-1].rstrip()
    return text + "…"


def draw_photo(c, photos, img, top, band_h, page_w):
    """Draw the photograph at its own aspect ratio, centred in the band under `top`.
    Returns (band bottom, photo bottom): panoramas sit higher than the band's floor."""
    path, (pw, ph) = photos.get(img["stem"])
    bw, bh = page_w - 2 * MARGIN, band_h
    w, h = fit(pw, ph, bw, bh)
    x, y = (page_w - w) / 2, top - bh + (bh - h) / 2
    c.drawImage(ImageReader(str(path)), x, y, w, h, preserveAspectRatio=False)
    c.setStrokeColorRGB(*LINE); c.setLineWidth(0.4)
    c.rect(x, y, w, h, stroke=1, fill=0)
    return top - bh, y


def draw_notice(c, page_w):
    c.setFont("Helvetica", 6.5); c.setFillColorRGB(*MUTED)
    c.drawCentredString(page_w / 2, MARGIN - 14, NOTICE)


def draw_cover(c, photos, plan, page_w, page_h):
    bottom, _ = draw_photo(c, photos, plan["cover"], page_h - MARGIN, COVER_BAND * page_h, page_w)
    y = bottom - 60
    c.setFillColorRGB(*INK); c.setFont("Serif", 60)
    c.drawString(MARGIN, y, str(YEAR))
    c.setFont("Serif", 28)
    c.drawRightString(page_w - MARGIN, y, plan["name"])
    y -= 24
    c.setFont("Helvetica", 10); c.setFillColorRGB(*MUTED)
    c.drawString(MARGIN + 3, y, "Photographs by Benjamin Ampel")
    c.setFillColorRGB(*PURPLE)
    c.drawRightString(page_w - MARGIN, y, "purplelink.llc/photography")
    draw_notice(c, page_w)


def draw_month(c, photos, img, month, firstweekday, page_w, page_h):
    bottom, photo_bottom = draw_photo(c, photos, img, page_h - MARGIN, PHOTO_BAND * page_h - MARGIN, page_w)
    width = page_w - 2 * MARGIN
    # caption: the photograph's title and where it was taken, just under the picture
    c.setFont("Helvetica", 8); c.setFillColorRGB(*MUTED)
    c.drawString(MARGIN, photo_bottom - 11, ellipsize(c, f"{img['title']}  ·  {img['place']}", "Helvetica", 8, width))
    # month name and year
    y = bottom - 40
    c.setFillColorRGB(*INK); c.setFont("Serif", 24)
    c.drawString(MARGIN, y, calendar.month_name[month])
    c.setFillColorRGB(*PURPLE)
    c.drawRightString(page_w - MARGIN, y, str(YEAR))
    c.setStrokeColorRGB(*PURPLE); c.setLineWidth(0.7)
    c.line(MARGIN, y - 8, page_w - MARGIN, y - 8)
    # grid
    weeks = month_weeks(month, firstweekday)
    top, floor = y - 12, MARGIN + 4
    rows = len(weeks) + 1
    row_h, col_w = (top - floor) / rows, width / 7
    c.setFont("Helvetica-Bold", 7.5); c.setFillColorRGB(*MUTED)
    for col in range(7):
        name = calendar.day_abbr[(firstweekday + col) % 7].upper()
        c.drawCentredString(MARGIN + col_w * (col + 0.5), top - row_h + 6, name)
    c.setStrokeColorRGB(*LINE); c.setLineWidth(0.35)
    for r in range(1, rows + 1):
        c.line(MARGIN, top - row_h * r, page_w - MARGIN, top - row_h * r)
    for col in range(1, 7):
        c.line(MARGIN + col_w * col, top - row_h, MARGIN + col_w * col, floor)
    c.setFont("Helvetica", 10); c.setFillColorRGB(*INK)
    for r, week in enumerate(weeks):
        cell_top = top - row_h * (r + 1)
        for col, d in enumerate(week):
            if d:
                c.drawString(MARGIN + col_w * col + 5, cell_top - 12, str(d))
    draw_notice(c, page_w)


def build_pdf(plan, edition, photos, out):
    _, (page_w, page_h), firstweekday = edition
    c = canvas.Canvas(str(out), pagesize=(page_w, page_h), pageCompression=1)
    c.setTitle(f"{YEAR} {plan['name']} wall calendar")
    c.setAuthor("Benjamin Ampel")
    c.setSubject(f"Photographs by Benjamin Ampel, purplelink.llc/photography. Personal printing only; not for resale.")
    draw_cover(c, photos, plan, page_w, page_h)
    c.showPage()
    for m, img in enumerate(plan["months"], 1):
        draw_month(c, photos, img, m, firstweekday, page_w, page_h)
        c.showPage()
    c.save()


# ── previews ────────────────────────────────────────────────────────────────

def render_pages(pdf, pages, width_px):
    """Rasterise PDF pages to PIL images: CoreGraphics on macOS, ghostscript elsewhere."""
    try:
        import Quartz
    except ImportError:
        Quartz = None
    if Quartz:
        p = str(pdf).encode()
        doc = Quartz.CGPDFDocumentCreateWithURL(Quartz.CFURLCreateFromFileSystemRepresentation(None, p, len(p), False))
        out = []
        for n in pages:
            page = Quartz.CGPDFDocumentGetPage(doc, n)
            rect = Quartz.CGPDFPageGetBoxRect(page, Quartz.kCGPDFMediaBox)
            scale = width_px / rect.size.width
            w, h = width_px, int(round(rect.size.height * scale))
            ctx = Quartz.CGBitmapContextCreate(None, w, h, 8, w * 4, Quartz.CGColorSpaceCreateDeviceRGB(),
                                               Quartz.kCGImageAlphaPremultipliedLast)
            Quartz.CGContextSetRGBFillColor(ctx, 1, 1, 1, 1)
            Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, w, h))
            Quartz.CGContextScaleCTM(ctx, scale, scale)
            Quartz.CGContextDrawPDFPage(ctx, page)
            img = Quartz.CGBitmapContextCreateImage(ctx)
            data = bytes(Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img)))
            out.append(Image.frombuffer("RGBA", (w, h), data, "raw", "RGBA", Quartz.CGImageGetBytesPerRow(img), 1).convert("RGB"))
        return out
    with tempfile.TemporaryDirectory() as td:
        out = []
        for n in pages:
            png = Path(td) / f"p{n}.png"
            subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=png16m", f"-dFirstPage={n}", f"-dLastPage={n}",
                            "-r150", f"-sOutputFile={png}", str(pdf)], check=True)
            with Image.open(png) as im:
                im = im.convert("RGB")
                im.thumbnail((width_px, width_px * 2), Image.LANCZOS)
                out.append(im.copy())
        return out


def write_previews(plan, pdf):
    OUT_PREV.mkdir(parents=True, exist_ok=True)
    for n, im in enumerate(render_pages(pdf, [1, 2, 3], PREVIEW_W), 1):
        watermark(im, 0.9).save(OUT_PREV / f"{plan['slug']}-p{n}.jpg", "JPEG", quality=70, optimize=True)
    cover = render_pages(pdf, [1], COVER_W)[0]
    watermark(cover, 0.9).save(OUT_PREV / f"{plan['slug']}-cover.jpg", "JPEG", quality=70, optimize=True)


# ── main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--sets", help="comma-separated set slugs to build (default: all)")
    a = ap.parse_args()
    verify_all_grids()
    if not HUB_DATA.exists():
        sys.exit(f"missing {HUB_DATA}; run scripts/gen_photo_hubs.py first")
    plans = plan_sets(set(a.sets.split(",")) if a.sets else None)
    short = []
    for p in plans:
        n = len(p["unique"])
        note = "" if n >= 13 else f"  ({n} unique photographs: {13 - n} month(s) reuse a photograph)"
        if n < 13:
            short.append((p["slug"], n))
        print(f"{p['slug']}: cover {p['cover']['stem']}{note}")
        for m, img in enumerate(p["months"], 1):
            print(f"  {calendar.month_abbr[m]}  {img['stem']:<22} {img['w']}x{img['h']}  {img['title'][:60]}  [{img['place']}]")
    if a.check:
        return 0
    fonts()
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="calendars-") as td:
        photos = PhotoCache(td)
        for p in plans:
            for edition in EDITIONS:
                out = OUT_PDF / f"calendar-{YEAR}-{p['slug']}-{edition[0]}.pdf"
                build_pdf(p, edition, photos, out)
                mb = out.stat().st_size / 1e6
                print(f"wrote {out}  {mb:.1f} MB" + ("  (over 25 MB)" if mb > 25 else ""))
                if edition[0] == "letter":
                    write_previews(p, out)
    print(f"previews in {OUT_PREV}")
    if short:
        print("sets with fewer than 13 unique photographs (cover + 12): " + ", ".join(f"{s} ({n})" for s, n in short))
    return 0


if __name__ == "__main__":
    sys.exit(main())
