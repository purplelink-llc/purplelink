#!/usr/bin/env python3
"""Build the 2026 holiday Pinterest pins: 2027 calendars, gift prints, Atlanta.

A seasonal companion to scripts/pinterest-pins.py (same 1000x1500 layout,
watermark and CSV columns), written for the holiday window that closes on
January 15. Three groups, each a different board and link:

  calendar   35 pins, 5 per calendar, linking to /photography/calendars/#cal-<set>
             ("Iceland calendar 2027"); the photographs are the ones inside each
             calendar, from photo-calendars.py's own plan_sets()
  gift       25 pins of Fine Art America prints, linking to the artwork on the
             storefront benjamin-ampel.pixels.com ("gift for someone who went to Japan")
  atlanta    15 pins: Atlanta and North Georgia prints on the storefront, plus the
             /photography/united-states/atlanta/ page. Never the MLB All-Star photographs
             (team and league marks are not ours to put on products).

Every purplelink.llc link carries UTMs from scripts/hub/hub.py utm (one utm_content
per pin). Storefront links are another site's and get none.

Inputs
  site/photography/hub-data.json                         from gen_photo_hubs.py
  photo-licensing-workspace/faa-upload-state.json        filename -> FAA title
  photo-licensing-workspace/faa-title-renames.json       titles changed after upload
  photo-licensing-workspace/pinterest/faa-urls.json      storefront URL -> title, read from
                                                         the FAA profile (--refresh-faa rebuilds it)
Outputs
  site/assets/photography/pins/holiday/<group>-<slug>.jpg   committed, served by Netlify
  photo-licensing-workspace/pinterest/pins-holiday-2026.csv  upload this to Pinterest

  python3 scripts/pinterest-holiday-pins.py --check
  python3 scripts/pinterest-holiday-pins.py --start 2026-11-03
  python3 scripts/pinterest-holiday-pins.py --refresh-faa     # re-read storefront URLs first
"""
import argparse, csv, datetime, importlib.util, json, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_photo_hubs import FONT, HEROES, HUB_DATA, ROOT, SRC, WS, slug_of, watermark  # noqa: E402

_spec = importlib.util.spec_from_file_location("pinterest_pins", Path(__file__).resolve().parent / "pinterest-pins.py")
pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pins)

Image.MAX_IMAGE_PIXELS = None
OUT_DIR = pins.OUT_DIR / "holiday"
CSV_PATH = pins.PIN_DIR / "pins-holiday-2026.csv"
FAA_URLS = pins.PIN_DIR / "faa-urls.json"
STOREFRONT = "https://benjamin-ampel.pixels.com"
BASE = pins.BASE
CAMPAIGN = "holiday-2026"
PER_CALENDAR = 5

# Board per group. Ben creates these three boards before the upload (pinterest.md).
BOARDS = {"calendar": "2027 Photo Calendars", "gift": "Travel Photo Gifts", "atlanta": "Atlanta Photography"}

# Where each calendar's buyer has been, for "a gift for someone who went to ...".
CAL_TRIP = {"iceland": "Iceland", "japan": "Japan", "switzerland": "Switzerland", "european-cities": "Europe",
            "arizona-desert": "Arizona", "hawaii": "Hawaii", "best-of": None}
# Gift prints: how many per destination, in this order.
GIFT_QUOTA = [("Iceland", 5), ("Japan", 6), ("Switzerland", 4), ("London", 2), ("Copenhagen", 2),
              ("Amsterdam", 1), ("Hawaii", 3), ("Arizona", 3), ("San Francisco", 1)]
# Atlanta: storefront prints (no people, no event coverage) and the hub page.
ATLANTA_FAA = ["DSC_7629", "DSC_2751", "DSC_2731", "DSC_3554-Enhanced-NR", "DSC_5115", "DSC_5101",
               "DSC_5132", "DSC_5165", "DSC_5200"]
ATLANTA_PAGE = ["DSC_3566-Enhanced-NR", "DSC_3571-Enhanced-NR", "DSC_7629", "DSC_2751", "DSC_5115", "DSC_5200"]


# ── data ────────────────────────────────────────────────────────────────────

_cspec = importlib.util.spec_from_file_location("photo_calendars", Path(__file__).resolve().parent / "photo-calendars.py")
cals = importlib.util.module_from_spec(_cspec)
_cspec.loader.exec_module(cals)


def ratings():
    """stem -> Ben's 1-5 rating from metadata-master.csv (0 when unrated)."""
    with open(WS / "metadata-master.csv", newline="", encoding="utf-8") as fh:
        return {r["filename"].rsplit(".", 1)[0]: int(r["rating"]) if r["rating"].isdigit() else 0 for r in csv.DictReader(fh)}


def hub_index():
    data = json.loads(HUB_DATA.read_text(encoding="utf-8"))
    out = {}
    for c in data["countries"]:
        for p in c["places"]:
            for i in p["images"]:
                out.setdefault(i["stem"], {**i, "place": p["name"], "place_slug": p["slug"], "country": c["name"]})
        for i in c.get("extra", []):
            out.setdefault(i["stem"], {**i, "place": c["name"], "place_slug": "", "country": c["name"]})
    return out


def destination(img):
    """The trip a buyer would name: the city for European cities and US places, else the country."""
    p, c = img["place"], img["country"]
    for city in ("London", "Copenhagen", "Amsterdam", "San Francisco", "Hawaii", "Atlanta"):
        if p.startswith(city):
            return city
    if p.startswith("Sonoran Desert"):
        return "Arizona"
    return c


def refresh_faa_urls():
    """Read storefront URL -> title for every artwork on Ben's FAA profile (public pages, read only)."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9340")
        pg = b.contexts[0].new_page()
        for n in range(1, 40):
            pg.goto(f"https://fineartamerica.com/profiles/benjamin-ampel?tab=artwork&page={n}", wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(3500)
            got = pg.evaluate("""()=>{const o={};document.querySelectorAll('a[href*="/featured/"]').forEach(a=>{
                const img=a.querySelector('img');const t=(img&&(img.getAttribute('alt')||img.getAttribute('title')))||'';
                const h=a.href.split('?')[0]; if(t&&h.includes('benjamin-ampel')&&!o[h])o[h]=t});return o}""")
            new = {h: t for h, t in got.items() if h not in out}
            if not new:
                break
            out.update(new)
        pg.close()
    FAA_URLS.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out


def faa_links():
    """stem -> storefront artwork URL, matched on the title each photograph was uploaded with."""
    if not FAA_URLS.exists():
        sys.exit(f"missing {FAA_URLS}; run with --refresh-faa (needs the photo automation Chrome on port 9340)")
    def key(t):
        return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()

    by_title = {}
    for url, title in json.loads(FAA_URLS.read_text()).items():
        by_title[key(re.sub(r"\s+by Benjamin Ampel$", "", title))] = STOREFRONT + "/featured/" + url.rsplit("/featured/", 1)[1]
    renames = {}
    rp = WS / "faa-title-renames.json"
    if rp.exists():
        renames = {key(v["old"]): key(v["new"]) for v in json.loads(rp.read_text()).values()}
    out = {}
    for fn, v in json.loads((WS / "faa-upload-state.json").read_text())["uploaded"].items():
        t = key(v.get("title", ""))
        t = renames.get(t, t)
        if t not in by_title:
            # FAA cuts long titles; accept one listing whose title is a long enough prefix of ours.
            hits = [k for k in by_title if len(k) >= 30 and t.startswith(k)]
            t = hits[0] if len(hits) == 1 else t
        if t in by_title:
            out[fn.rsplit(".", 1)[0]] = by_title[t]
    return out


def utm(url, asset, content):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "hub" / "hub.py"), "utm", url, "--asset", asset,
                           "--channel", "pinterest", "--campaign", CAMPAIGN, "--content", content],
                          check=True, capture_output=True, text=True).stdout.strip()


# ── picking ─────────────────────────────────────────────────────────────────

def pick():
    hub = hub_index()
    faa = faa_links()
    out, used = [], set()

    for plan in cals.plan_sets():
        n = 0
        for img in plan["unique"]:
            if n == PER_CALENDAR:
                break
            if img["stem"] not in hub or (img["stem"] in used and plan["slug"] != "best-of"):
                continue
            used.add(img["stem"])
            n += 1
            out.append({"group": "calendar", "stem": img["stem"], "img": hub[img["stem"]], "set": plan["slug"], "set_name": plan["name"]})

    # Gift prints: wall subjects only (the calendar script's own filters), best rated first.
    stars = ratings()
    ranked = sorted((i for i in hub.values() if not i["people"] and not i.get("event")
                     and not cals.AVOID.search(i["title"] + " " + i["caption"]) and cals.SCENIC.search(i["title"])),
                    key=lambda i: (i["stem"] not in HEROES, -stars.get(i["stem"], 0), -len(cals.SCENIC.findall(i["title"]))))
    for dest, quota in GIFT_QUOTA:
        n = 0
        for i in ranked:
            if n == quota:
                break
            if destination(i) == dest and i["stem"] in faa and i["stem"] not in used:
                used.add(i["stem"])
                n += 1
                out.append({"group": "gift", "stem": i["stem"], "img": i, "dest": dest, "link": faa[i["stem"]]})

    for stem in ATLANTA_FAA:
        if stem in faa and stem in hub:
            out.append({"group": "atlanta", "stem": stem, "img": hub[stem], "kind": "print", "link": faa[stem]})
    for stem in ATLANTA_PAGE:
        if stem in hub:
            out.append({"group": "atlanta", "stem": stem, "img": hub[stem], "kind": "page"})
    return out


# ── pin image ───────────────────────────────────────────────────────────────

def band(w, h, big_text, small_text):
    im = Image.new("RGB", (w, h), pins.PURPLE)
    d = ImageDraw.Draw(im)
    big = pins.fitted_font(big_text, w - 80, 52)
    small = ImageFont.truetype(FONT, 22)
    d.text(((w - d.textlength(big_text, font=big)) / 2, 20), big_text, font=big, fill=(255, 255, 255))
    d.text(((w - d.textlength(small_text, font=small)) / 2, h - 46), small_text, font=small, fill=(225, 210, 240))
    return im


def build(stem, big_text, small_text, dest):
    src = SRC / f"{stem}.jpeg"
    if not src.exists():
        return None
    if dest.exists() and dest.stat().st_mtime >= max(src.stat().st_mtime, Path(__file__).stat().st_mtime):
        return dest.stat().st_size
    with Image.open(src) as im:
        im.draft("RGB", (pins.PIN_W * 2, pins.PIN_H * 2))
        im = ImageOps.exif_transpose(im).convert("RGB")
        photo = pins.fit_photo(im, pins.PIN_W, pins.PIN_H - pins.BAND_H)
    photo = watermark(photo, 0.9)
    canvas = Image.new("RGB", (pins.PIN_W, pins.PIN_H), pins.PURPLE)
    canvas.paste(photo, (0, 0))
    canvas.paste(band(pins.PIN_W, pins.BAND_H, big_text, small_text), (0, pins.PIN_H - pins.BAND_H))
    dest.parent.mkdir(parents=True, exist_ok=True)
    q = pins.JPEG_QUALITY
    while True:
        canvas.save(dest, "JPEG", quality=q, optimize=True, progressive=True, subsampling=2)
        if dest.stat().st_size <= pins.MAX_BYTES or q <= pins.MIN_QUALITY:
            return dest.stat().st_size
        q -= 4


# ── text ────────────────────────────────────────────────────────────────────

def subject(img):
    t = pins.DATELINE.sub("", img["title"].strip().rstrip("."))
    return t[:1].upper() + t[1:]


def caption(img):
    c = img["caption"].strip()
    return c if c.endswith(".") else c + "."


def texts(x):
    """(band headline, band subline, pin title, description, keywords)."""
    img, g = x["img"], x["group"]
    if g == "calendar":
        name, trip = x["set_name"], CAL_TRIP.get(x["set"])
        big = f"{name} calendar 2027" if x["set"] != "best-of" else "Travel photo calendar 2027"
        gift = (f"A small gift for someone who went to {trip}." if trip
                else "A small gift for someone who travels: Iceland, Japan, Switzerland, London, Arizona and Hawaii in one year.")
        which = "Best of calendar, twelve places in one year" if x["set"] == "best-of" else f"{name} wall calendar"
        desc = (f"{caption(img)} This photograph is one of the months in the printable 2027 {which}: "
                f"thirteen pages, US Letter and A4, $7, or all seven calendars for $19. {gift} Print it at home or at any print shop.")
        return (big, "Printable PDF, $7  |  purplelink.llc", f"{big}: {subject(img)}", desc,
                f"calendar 2027, {name.lower()} calendar 2027, printable calendar, wall calendar, travel gift")
    if g == "gift":
        dest = x["dest"]
        desc = (f"{caption(img)} A gift for someone who went to {dest}: framed prints, canvas, metal and posters of this "
                f"photograph by Benjamin Ampel, printed and shipped by Fine Art America.")
        return (f"{dest} wall art", "Prints and gifts  |  benjamin-ampel.pixels.com",
                f"{dest} gift print: {subject(img)}", desc,
                f"{dest.lower()} wall art, {dest.lower()} gift, travel gift, photography print, wall decor")
    north = "north georgia" in (img["caption"] + " " + img["title"]).lower() or "appalachian" in img["title"].lower()
    if x["kind"] == "print":
        where = "North Georgia" if north else "Atlanta"
        desc = (f"{caption(img)} A gift for someone who calls Atlanta home: framed prints, canvas and metal prints of this "
                f"photograph by Benjamin Ampel, an Atlanta photographer, printed and shipped by Fine Art America.")
        return (f"{where} wall art", "Prints and gifts  |  benjamin-ampel.pixels.com", f"{where} wall art print: {subject(img)}",
                desc, "atlanta wall art, atlanta gift, georgia wall art, atlanta skyline, photography print")
    desc = (f"{caption(img)} One of about 30 photographs of Atlanta and North Georgia by Benjamin Ampel: the Midtown skyline, "
            f"the city in snow, the Botanical Garden. Prints and licenses at purplelink.llc.")
    return ("Atlanta and North Georgia", "Photographs  |  purplelink.llc/photography",
            f"Atlanta photographs: {subject(img)}", desc,
            "atlanta, atlanta skyline, atlanta photography, north georgia, midtown atlanta")


def clip(s, n):
    return s if len(s) <= n else s[:n - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "."


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--start", help="first publish date, YYYY-MM-DD (default: tomorrow)")
    ap.add_argument("--refresh-faa", action="store_true", help="re-read storefront URLs from the FAA profile first")
    a = ap.parse_args()
    if a.refresh_faa:
        print(f"{len(refresh_faa_urls())} storefront URLs read")
    chosen = pick()
    counts = {g: sum(1 for x in chosen if x["group"] == g) for g in BOARDS}
    print(", ".join(f"{g} {n}" for g, n in counts.items()) + f": {len(chosen)} pins")
    if a.check:
        for x in chosen:
            print(f"  {x['group']:8} {x['stem']:28} {texts(x)[0]}")
        return 0

    start = datetime.date.fromisoformat(a.start) if a.start else datetime.date.today() + datetime.timedelta(days=1)
    # Interleave the groups so each day carries calendars, gifts and Atlanta, not one group per week.
    groups = {g: [x for x in chosen if x["group"] == g] for g in BOARDS}
    order = []
    while any(groups.values()):
        for g in ("calendar", "gift", "calendar", "atlanta", "gift"):
            if groups[g]:
                order.append(groups[g].pop(0))
    rows, keep = [], set()
    for x, when in zip(order, pins.publish_dates(len(order), start)):
        big, small, title, desc, kw = texts(x)
        name = (f"calendar-{x['set']}-{slug_of(x['stem'])}" if x["group"] == "calendar" else
                f"{x['group']}-{slug_of(x['stem'])}" + ("-page" if x.get("kind") == "page" else ""))
        if build(x["stem"], big, small, OUT_DIR / f"{name}.jpg") is None:
            print(f"  skip {x['stem']}: original not found")
            continue
        keep.add(name)
        if x["group"] == "calendar":
            link = utm(f"{BASE}/photography/calendars/#cal-{x['set']}", "photo-calendars", f"pin-cal-{x['set']}-{slug_of(x['stem'])}")
        elif x.get("kind") == "page":
            link = utm(f"{BASE}/photography/united-states/atlanta/", "photo-atlanta", f"pin-atl-{slug_of(x['stem'])}")
        else:
            link = x["link"]
        rows.append({"Title": pins.shorten(title, 100), "Media URL": f"{BASE}/assets/photography/pins/holiday/{name}.jpg",
                     "Pinterest board": BOARDS[x["group"]], "Thumbnail": "", "Description": clip(desc, 500),
                     "Link": link, "Publish date": when, "Keywords": kw})
    for stale in OUT_DIR.glob("*.jpg"):
        if stale.stem not in keep:
            stale.unlink()
            print(f"  removed stale {stale.name}")
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=pins.COLUMNS)
        w.writeheader()
        w.writerows(rows)
    size = sum(p.stat().st_size for p in OUT_DIR.glob("*.jpg"))
    print(f"{len(rows)} rows in {CSV_PATH}; pins folder {size / 1024 / 1024:.1f} MB")
    if rows:
        print(f"publish dates {rows[0]['Publish date']} to {rows[-1]['Publish date']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
