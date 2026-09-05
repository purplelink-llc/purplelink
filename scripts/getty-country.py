#!/usr/bin/env python3
"""Derive and embed "Country of shoot" for the Getty upload set.

Getty ESP requires Country of shoot on every file. It reads the rest of its
metadata straight out of our embedded IPTC -- title, description, keywords, and
Date Created from EXIF all arrive filled -- but none of our files carry a country
field, so that one box is the only thing standing between the batch and being
submittable.

Country is resolved in three passes, most reliable first:
  1. direct   -- a place name in the title/description/keywords
  2. same-day -- a photo shot the same calendar day as a resolved one
  3. trip     -- within +/-3 days of resolved photos (a single journey)

Anything still unresolved is LEFT ALONE and listed. A country on a stock photo
is a factual claim; guessing "United States" because a picture looks like desert
would put a wrong assertion on a published caption.

USAGE
  scripts/getty-country.py --dry-run     # show what would be written
  scripts/getty-country.py --embed       # write IPTC into the source files
"""
import argparse, collections, csv, datetime, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
SET = WS / "getty-upload-set.csv"
MAP = WS / "getty-country-map.json"
UNKNOWN = WS / "getty-country-unknown.txt"

PLACES = [
 (r"iceland|reykjav|jokulsarlon|jökulsárlón|snæfellsnes|skógafoss|seljalands|dyrhólaey|"
  r"vatnajokull|thingvellir|fjaðrárgljúfur|gljúfrabúi|bruarfoss|búðir|lóndrangar|bjarnarfoss",
  "Iceland", "ISL"),
 (r"\bkyoto|tokyo|hiroshima|miyajima|itsukushima|osaka|nara\b|japan|japanese|arashiyama|"
  r"kiyomizu|zojoji|meiji|fushimi|kabukicho", "Japan", "JPN"),
 (r"\blondon|westminster|greenwich|canary wharf|big ben|parliament|thames|england|"
  r"united kingdom", "United Kingdom", "GBR"),
 (r"\bcopenhagen|nyhavn|denmark|danish", "Denmark", "DNK"),
 (r"\bamsterdam|zuiderkerk|rijksmuseum|montelbaanstoren|netherlands|dutch", "Netherlands", "NLD"),
 (r"\bcologne|hohenzollern|heidelberg|germany|german|rhine|neckar|severins", "Germany", "DEU"),
 (r"\bzermatt|matterhorn|riffelsee|gorner|grindelwald|wetterhorn|lauterbrunnen|staubbach|"
  r"jungfrau|aletsch|interlaken|thun|brienz|\bbern\b|aare|switzerland|swiss|alpine|alps\b|chalet",
  "Switzerland", "CHE"),
 (r"\bpanama|casco viejo", "Panama", "PAN"),
 (r"\bvancouver|english bay|canada|canadian", "Canada", "CAN"),
 (r"\btucson|phoenix|scottsdale|sedona|arizona|saguaro|sonoran|honolulu|waikiki|diamond head|"
  r"oahu|hilo|kilauea|akaka|hawaii|maui|kauai|pearl harbor|atlanta|georgia|san francisco|"
  r"golden gate|california|redwood|yosemite|appalachian|blue ridge|smoky|united states|\busa\b",
  "United States", "USA"),
]
TRIP_DAYS = 3


def capture_days(files):
    out = subprocess.run(["exiftool", "-j", "-DateTimeOriginal", "-FileName"]
                         + [str(SRC / f) for f in files], capture_output=True, text=True).stdout
    days = {}
    for d in json.loads(out or "[]"):
        m = re.match(r"(\d{4}):(\d{2}):(\d{2})", d.get("DateTimeOriginal") or "")
        if m:
            days[Path(d["FileName"]).name] = datetime.date(int(m[1]), int(m[2]), int(m[3]))
    return days


def resolve():
    rows = list(csv.DictReader(open(SET)))
    files = [r["filename"] for r in rows]
    days = capture_days(files)

    final, how = {}, {}
    for r in rows:
        hay = f"{r['title']} {r['description']} {r['keywords']}"
        for pat, name, code in PLACES:
            if re.search(pat, hay, re.I):
                final[r["filename"]] = (name, code); how[r["filename"]] = "direct"
                break

    # pass 2: same calendar day as an already-resolved frame
    dayvote = collections.defaultdict(collections.Counter)
    for f, (n, c) in final.items():
        if f in days:
            dayvote[days[f]][(n, c)] += 1
    for r in rows:
        f = r["filename"]
        if f in final or f not in days:
            continue
        v = dayvote.get(days[f])
        if v:
            final[f] = v.most_common(1)[0][0]; how[f] = "same-day"

    # pass 3: within a single trip
    anchors = [(days[f], final[f]) for f in list(final) if f in days and how[f] == "direct"]
    for r in rows:
        f = r["filename"]
        if f in final or f not in days:
            continue
        near = collections.Counter(nc for dd, nc in anchors
                                   if abs((dd - days[f]).days) <= TRIP_DAYS)
        if near:
            final[f] = near.most_common(1)[0][0]; how[f] = f"trip±{TRIP_DAYS}d"

    unresolved = [r["filename"] for r in rows if r["filename"] not in final]
    return rows, final, how, unresolved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows, final, how, unresolved = resolve()
    print(f"{len(rows)} images in the Getty set")
    for k, v in collections.Counter(how.values()).most_common():
        print(f"  {v:>4}  resolved by {k}")
    print(f"  {len(unresolved):>4}  UNRESOLVED — left blank on purpose")
    print()
    for k, v in collections.Counter(n for n, c in final.values()).most_common():
        print(f"  {v:>4}  {k}")

    MAP.write_text(json.dumps({f: {"country": n, "code": c, "how": how[f]}
                               for f, (n, c) in final.items()}, indent=1))
    UNKNOWN.write_text("\n".join(sorted(unresolved)))
    print(f"\nwrote {MAP.name} ({len(final)}) and {UNKNOWN.name} ({len(unresolved)})")

    if not a.embed:
        print("\n(dry run — pass --embed to write IPTC into the source files)")
        return

    # group by country so exiftool runs once per country rather than per file
    bycountry = collections.defaultdict(list)
    for f, (n, c) in final.items():
        bycountry[(n, c)].append(str((SRC / f).resolve()))
    for (name, code), paths in bycountry.items():
        r = subprocess.run(
            ["exiftool", "-overwrite_original",
             f"-IPTC:Country-PrimaryLocationName={name}",
             f"-IPTC:Country-PrimaryLocationCode={code}",
             f"-XMP:Country={name}"] + paths,
            capture_output=True, text=True)
        ok = re.search(r"(\d+) image files updated", r.stdout)
        print(f"  {name:<16} {ok.group(1) if ok else '?'} files tagged")
    print("\ndone. Re-upload these files for ESP to pick the country up "
          "(it reads metadata at ingest, not retroactively).")


if __name__ == "__main__":
    main()
