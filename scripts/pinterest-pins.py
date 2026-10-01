#!/usr/bin/env python3
"""Build Pinterest pins for the photography hub pages.

Reads site/photography/hub-data.json (written by scripts/gen_photo_hubs.py),
picks a capped set of photographs, renders each as a 1000x1500 pin (the
original photograph fitted to 2:3, the usual diagonal watermark, a purple
band at the bottom with the place name) and writes a CSV in the column
layout Pinterest's bulk-create upload expects.

Selection: every photograph whose stem is in gen_photo_hubs.HEROES, plus the
first four photographs of every place page. Photographs with a recognisable
person are never pinned. Roughly 120 pins.

Outputs
  site/assets/photography/pins/<slug>.jpg               committed, served by Netlify
  photo-licensing-workspace/pinterest/pins.csv          upload this to Pinterest
  photo-licensing-workspace/pinterest/exported.json     slugs already put in a CSV

  python3 scripts/pinterest-pins.py                 build pins + CSV for the whole set
  python3 scripts/pinterest-pins.py --check         counts only, write nothing
  python3 scripts/pinterest-pins.py --limit 10      first 10 pins only
  python3 scripts/pinterest-pins.py --new-only --mark-exported
                                                    weekly: CSV of pins not yet exported,
                                                    then remember them as exported
"""
import argparse, csv, datetime, json, re, sys, unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_photo_hubs import HEROES, FONT, SRC, HUB_DATA, ROOT, SITE, WS, slug_of, watermark  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
OUT_DIR = SITE / "assets" / "photography" / "pins"
PIN_DIR = WS / "pinterest"
CSV_PATH = PIN_DIR / "pins.csv"
EXPORTED = PIN_DIR / "exported.json"
BASE = "https://purplelink.llc"

PIN_W, PIN_H = 1000, 1500
BAND_H = 120
PURPLE = (91, 42, 134)            # sRGB stand-in for the site's oklch hue-310 purple
PANORAMA_ASPECT = 1.9             # wider than this gets a blurred fill instead of a crop
PER_PLACE = 4
JPEG_QUALITY = 72
MIN_QUALITY = 56                  # busy frames (cityscapes) step down to here, no further
MAX_BYTES = 180_000
FOLDER_CAP = 25 * 1024 * 1024
PER_DAY = 5
SLOTS = ["09:17", "11:43", "14:08", "16:31", "18:52"]   # local time, never on the hour
COLUMNS = ["Title", "Media URL", "Pinterest board", "Thumbnail", "Description", "Link", "Publish date", "Keywords"]
SUFFIX = ". Travel photography print"
TAIL = "Prints and licenses at purplelink.llc"


def norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


# ── selection ───────────────────────────────────────────────────────────────

def select(data):
    """Yield (image, place_name, link, country_name) in page order, no duplicates."""
    seen, out = set(), []
    data.setdefault("_misfiled", [])

    def add(img, place, link, country):
        if img["people"] or img["stem"] in seen:
            return
        seen.add(img["stem"])
        other = foreign_country(img, country)
        if other:
            data["_misfiled"].append(f"{img['stem']} filed under {country} / {place} but names {other}: {img['title']}")
            return
        out.append((img, place, link, country))

    heroes = set(HEROES)
    for c in data["countries"]:
        for p in c["places"]:
            kept = 0
            for img in p["images"]:
                if img["people"]:
                    continue
                if img["stem"] in heroes or kept < PER_PLACE:
                    add(img, p["name"], p["url"], c["name"])
                    kept += 1
        for img in c.get("extra", []):
            if img["stem"] in heroes:
                add(img, c["name"], c["url"], c["name"])
    return out


# ── pin image ───────────────────────────────────────────────────────────────

def fit_photo(im, w, h):
    """Return the photograph as a w x h canvas: centre crop, or blurred fill for panoramas."""
    iw, ih = im.size
    if iw / ih <= PANORAMA_ASPECT:
        return ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(0.5, 0.5))
    bg = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    bg = Image.eval(bg, lambda v: int(v * 0.55))
    fg = im.copy()
    fg.thumbnail((w - 60, h), Image.LANCZOS)
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return bg


def fitted_font(text, max_w, start_px, min_px=22):
    px = start_px
    while px > min_px:
        f = ImageFont.truetype(FONT, px)
        if ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=f) <= max_w:
            return f
        px -= 2
    return ImageFont.truetype(FONT, min_px)


def band(w, h, place, country):
    im = Image.new("RGB", (w, h), PURPLE)
    d = ImageDraw.Draw(im)
    big = fitted_font(place, w - 80, 52)
    small = ImageFont.truetype(FONT, 22)
    sub = f"{country}  |  purplelink.llc/photography"
    tw = d.textlength(place, font=big)
    sw = d.textlength(sub, font=small)
    d.text(((w - tw) / 2, 20), place, font=big, fill=(255, 255, 255))
    d.text(((w - sw) / 2, h - 22 - 24), sub, font=small, fill=(225, 210, 240))
    return im


def build_pin(stem, place, country, dest):
    src = SRC / f"{stem}.jpeg"
    if not src.exists():
        return None
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return dest.stat().st_size
    with Image.open(src) as im:
        im.draft("RGB", (PIN_W * 2, PIN_H * 2))   # JPEG DCT-scaled decode: 20 MP originals open about 4x faster
        im = ImageOps.exif_transpose(im).convert("RGB")
        photo = fit_photo(im, PIN_W, PIN_H - BAND_H)
    photo = watermark(photo, 0.9)
    canvas = Image.new("RGB", (PIN_W, PIN_H), PURPLE)
    canvas.paste(photo, (0, 0))
    canvas.paste(band(PIN_W, BAND_H, place, country), (0, PIN_H - BAND_H))
    dest.parent.mkdir(parents=True, exist_ok=True)
    q = JPEG_QUALITY
    while True:
        canvas.save(dest, "JPEG", quality=q, optimize=True, progressive=True, subsampling=2)
        size = dest.stat().st_size
        if size <= MAX_BYTES or q <= MIN_QUALITY:
            return size
        q -= 4


# ── csv rows ────────────────────────────────────────────────────────────────

JOINERS = r"with|from|near|above|beside|against|under|over|across|beneath|through|between|toward|towards|in|at|on|of|and|as"
DANGLING = re.compile(r"(\s+(a|an|the|or|into|by|to|for|its|their|" + JOINERS + r")\b)+$", re.I)
PHRASE_START = re.compile(r"\s+(" + JOINERS + r")\s", re.I)
DATELINE = re.compile(r"^[^:]{3,60}\s-\s(January|February|March|April|May|June|July|August|September|October|November|December)\s\d{4}:\s*", re.I)

# A photograph filed under one country whose own title or keywords name another is a
# taxonomy slip upstream (scripts/data/photo-places.json); it is not pinned, and the run reports it.
COUNTRY_WORDS = {"iceland": "Iceland", "japan": "Japan", "switzerland": "Switzerland", "united kingdom": "United Kingdom",
                 "england": "United Kingdom", "denmark": "Denmark", "netherlands": "Netherlands", "germany": "Germany",
                 "united states": "United States", "usa": "United States", "arizona": "United States", "hawaii": "United States",
                 "california": "United States", "pennsylvania": "United States", "canada": "Canada", "panama": "Panama"}


def foreign_country(img, country):
    blob = " " + norm(img["title"]) + " " + " ".join(norm(k) for k in img["keywords"]) + " "
    hits = {c for w, c in COUNTRY_WORDS.items() if re.search(r"\b" + re.escape(w) + r"\b", blob)}
    hits.discard(country)
    return ", ".join(sorted(hits))


def shorten(t, room):
    """Cut t to at most room chars, preferably at the start of a prepositional phrase."""
    if len(t) <= room:
        return t
    head = t[:room + 1]
    starts = [m.start() for m in PHRASE_START.finditer(head)]
    if starts and starts[-1] >= room * 0.5:
        return t[:starts[-1]].rstrip(",;:")
    return DANGLING.sub("", head.rsplit(" ", 1)[0]).rstrip(",;:")


def pin_title(img, place, country):
    t = img["title"].strip().rstrip(".")
    t = DATELINE.sub("", t)                                         # "Tokyo, Japan - June 2025: Neon ..." -> "Neon ..."
    t = re.sub(r",\s*" + re.escape(country) + r"$", "", t, flags=re.I)
    t = t[:1].upper() + t[1:]
    place_short = re.split(r"\s+and\s+|,", place)[0].strip()      # "Panama City and the canal" -> "Panama City"
    if norm(place_short).split()[0] not in norm(t):
        t = f"{place_short}: {t}"
    tail = f", {country}{SUFFIX}"
    return shorten(t, 100 - len(tail)) + tail


def pin_description(img, fact):
    cap = img["caption"].strip()
    if cap and not cap.endswith("."):
        cap += "."
    fact = (fact or "").strip()
    if fact and not fact.endswith("."):
        fact += "."
    parts = [cap, fact, TAIL]
    desc = " ".join(p for p in parts if p)
    if len(desc) > 500:
        room = 500 - len(f" {TAIL}") - 1
        body = " ".join(p for p in (cap, fact) if p)[:room].rsplit(" ", 1)[0].rstrip(",;:") + "."
        desc = f"{body} {TAIL}"
    return desc


def pin_keywords(img):
    seen, out = set(), []
    for k in img["keywords"]:
        k = k.replace(",", " ").strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
        if len(out) == 10:
            break
    return ", ".join(out)


def publish_dates(n, start):
    for i in range(n):
        day = start + datetime.timedelta(days=i // PER_DAY)
        yield f"{day.isoformat()} {SLOTS[i % PER_DAY]}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="print counts, write nothing")
    ap.add_argument("--limit", type=int, help="only the first N pins")
    ap.add_argument("--new-only", action="store_true", help="CSV only for slugs not in exported.json")
    ap.add_argument("--mark-exported", action="store_true", help="after writing the CSV, record its slugs in exported.json")
    a = ap.parse_args()

    if not HUB_DATA.exists():
        sys.exit(f"missing {HUB_DATA}; run scripts/gen_photo_hubs.py first")
    data = json.loads(HUB_DATA.read_text(encoding="utf-8"))
    facts = {p["url"]: p.get("fact", "") for c in data["countries"] for p in c["places"]}
    picked = select(data)
    if a.limit:
        picked = picked[:a.limit]
    exported = json.loads(EXPORTED.read_text()) if EXPORTED.exists() else {}
    rows_src = [x for x in picked if not (a.new_only and slug_of(x[0]["stem"]) in exported)]

    for line in data["_misfiled"]:
        print("  not pinned, check photo-places.json: " + line)
    if a.check:
        boards = sorted({c for _, _, _, c in picked})
        print(f"{len(picked)} pins across {len(boards)} boards: {', '.join(boards)}")
        print(f"{len(rows_src)} would go in the CSV" + (" (new only)" if a.new_only else ""))
        missing = [i["stem"] for i, *_ in picked if not (SRC / f"{i['stem']}.jpeg").exists()]
        if missing:
            print(f"{len(missing)} original(s) missing: {', '.join(missing[:10])}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PIN_DIR.mkdir(parents=True, exist_ok=True)
    built, total = 0, 0
    sizes = {}
    for img, place, link, country in picked:
        slug = slug_of(img["stem"])
        size = build_pin(img["stem"], place, country, OUT_DIR / f"{slug}.jpg")
        if size is None:
            print(f"  skip {img['stem']}: original not found")
            continue
        sizes[slug] = size
        built += 1
        total += size
    if not a.limit:
        for stale in OUT_DIR.glob("*.jpg"):          # pins for photographs no longer selected
            if stale.stem not in sizes:
                stale.unlink()
                print(f"  removed stale {stale.name}")

    start = datetime.date.today() + datetime.timedelta(days=1)
    rows = []
    for (img, place, link, country), when in zip(rows_src, publish_dates(len(rows_src), start)):
        slug = slug_of(img["stem"])
        if slug not in sizes:
            continue
        rows.append({
            "Title": pin_title(img, place, country),
            "Media URL": f"{BASE}/assets/photography/pins/{slug}.jpg",
            "Pinterest board": country,
            "Thumbnail": "",
            "Description": pin_description(img, facts.get(link, "")),
            "Link": link,
            "Publish date": when,
            "Keywords": pin_keywords(img),
        })
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    if a.mark_exported:
        today = datetime.date.today().isoformat()
        for r in rows:
            exported.setdefault(r["Media URL"].rsplit("/", 1)[1][:-4], today)
        EXPORTED.write_text(json.dumps(exported, indent=1, sort_keys=True) + "\n")

    folder = sum(p.stat().st_size for p in OUT_DIR.glob("*.jpg"))
    print(f"{built} pins in {OUT_DIR.relative_to(ROOT)} ({folder / 1024 / 1024:.1f} MB, largest {max(sizes.values()) // 1024} KB)")
    print(f"{len(rows)} rows in {CSV_PATH}" + (f", exported.json now lists {len(exported)}" if a.mark_exported else ""))
    if rows:
        print(f"publish dates {rows[0]['Publish date']} to {rows[-1]['Publish date']}")
    if folder > FOLDER_CAP:
        print(f"WARNING: pins folder is over {FOLDER_CAP // 1024 // 1024} MB; lower JPEG_QUALITY or PER_PLACE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
