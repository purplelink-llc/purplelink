#!/usr/bin/env python3
"""Build Dreamstime's bulk-metadata CSV for images already sitting in the FTP queue.

Dreamstime accepts a CSV over FTP that auto-populates title, description,
keywords and categories for files already uploaded. Without it every image sits
in "Uploads" marked `No Cat.` and cannot be submitted, which is where 771 images
were stranded.

Column order is fixed by Dreamstime's own template and must not be reordered:
  Filename, Image Name, Description, Category 1..3, keywords,
  Free, W-EL, P-EL, SR-EL, SR-Price, Editorial, MR doc Ids, Pr Docs

EDITORIAL RULE (Dreamstime enforces it): an editorial image's description must
open "Location - Month YYYY:". 218 of ours already did; the rest get the prefix
built from EXIF DateTimeOriginal plus a place name recovered from the title or
keywords. Anything still lacking a confident location is emitted as a plain
commercial row rather than a malformed editorial one -- a wrong editorial header
is a guaranteed rejection, and rejections cost approval ratio.

USAGE
  scripts/dreamstime-csv.py                 # writes the CSV + a coverage report
  scripts/dreamstime-csv.py --upload        # also FTPs it to Dreamstime
"""
import argparse, csv, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
MASTER = WS / "metadata-master.csv"
CLEAN = WS / "clean-upload-set.json"
OUT = WS / "dreamstime-metadata.csv"

COLUMNS = ["Filename", "Image Name", "Description", "Category 1", "Category 2",
           "Category 3", "keywords", "Free", "W-EL", "P-EL", "SR-EL", "SR-Price",
           "Editorial", "MR doc Ids", "Pr Docs"]

# --- Dreamstime category ids (from their Image Legend sheet) -----------------
C = {
    "waterfalls": 24, "mountains": 15, "deserts": 17, "landscapes": 146,
    "lakes_rivers": 16, "forests": 18, "sea": 19, "sunsets": 23, "skies": 22,
    "plants": 12, "flowers": 25, "geologic": 143, "water": 171, "tropical_n": 20,
    "seasons": 26, "vegetation": 11, "nature_details": 14,
    "birds": 31, "mammals": 32, "marine": 34, "pets": 30, "wildlife": 168,
    "insects": 36, "reptiles": 35,
    "landmarks": 70, "historic": 132, "architecture": 71, "modern_bldg": 131,
    "night_scenes": 130, "indoor": 73, "outdoor": 72, "ruins": 174,
    "arch_details": 124,
    "t_europe": 59, "t_asia": 57, "t_america": 58, "t_scenics": 61,
    "t_tropical": 66, "t_resorts": 64, "t_arts": 65,
    "ed_sports": 182, "ed_events": 179, "ed_people": 180, "ed_landmarks": 184,
    "ed_weather": 183,
    "p_men": 117, "p_women": 116, "p_portraits": 162, "p_active": 123,
    "military": 102, "transportation": 98, "planetarium": 165, "aerial": 211,
    "fruit_veg": 137, "food": 28, "still_life": 144, "obj_other": 145,
    "entertainment": 136, "ind_sports": 157, "food_bev": 127,
}

# Place -> (match tokens, "City, Country", travel category)
PLACES = [
    (r"\biceland|reykjav|jokulsarlon|jkulsrln|vik\b|snfellsnes|skgafoss|seljalands|dyrhlaey|vatnajokull",
     "Iceland", "t_europe"),
    (r"\bkyoto\b", "Kyoto, Japan", "t_asia"),
    (r"\btokyo\b", "Tokyo, Japan", "t_asia"),
    (r"\bhiroshima\b", "Hiroshima, Japan", "t_asia"),
    (r"\bmiyajima|itsukushima", "Miyajima, Japan", "t_asia"),
    (r"\bosaka|nara\b", "Osaka, Japan", "t_asia"),
    (r"\bjapan|japanese\b", "Japan", "t_asia"),
    (r"\blondon|westminster|greenwich|canary wharf|big ben", "London, United Kingdom", "t_europe"),
    (r"\bcopenhagen|nyhavn", "Copenhagen, Denmark", "t_europe"),
    (r"\bamsterdam|zuiderkerk|rijksmuseum|montelbaanstoren", "Amsterdam, Netherlands", "t_europe"),
    (r"\bcologne|hohenzollern", "Cologne, Germany", "t_europe"),
    (r"\bheidelberg\b", "Heidelberg, Germany", "t_europe"),
    (r"\bzermatt|matterhorn|riffelsee|gorner", "Zermatt, Switzerland", "t_europe"),
    (r"\bgrindelwald|wetterhorn", "Grindelwald, Switzerland", "t_europe"),
    (r"\blauterbrunnen|staubbach", "Lauterbrunnen, Switzerland", "t_europe"),
    (r"\bjungfrau|aletsch", "Jungfraujoch, Switzerland", "t_europe"),
    (r"\binterlaken|thun|brienz", "Interlaken, Switzerland", "t_europe"),
    (r"\bbern\b|aare", "Bern, Switzerland", "t_europe"),
    (r"\bswitzerland|swiss|alpine|alps\b", "Switzerland", "t_europe"),
    (r"\btucson\b", "Tucson, Arizona", "t_america"),
    (r"\bphoenix|scottsdale|sedona", "Phoenix, Arizona", "t_america"),
    (r"\bsaguaro|sonoran|arizona\b", "Arizona, United States", "t_america"),
    (r"\bhonolulu|waikiki|diamond head|oahu|pearl harbor", "Honolulu, Hawaii", "t_america"),
    (r"\bhilo|kilauea|akaka|rainbow falls|volcanoes national", "Hilo, Hawaii", "t_america"),
    (r"\bhawaii|hawaiian|maui|kauai", "Hawaii, United States", "t_america"),
    (r"\batlanta\b", "Atlanta, Georgia", "t_america"),
    (r"\bvancouver\b", "Vancouver, Canada", "t_america"),
    (r"\bsan francisco|golden gate", "San Francisco, California", "t_america"),
    (r"\bpanama\b", "Panama", "t_america"),
    (r"\bredwood|yosemite|california\b", "California, United States", "t_america"),
    (r"\bappalachian|blue ridge|smoky", "Appalachian Mountains, United States", "t_america"),
]

# Ordered, most specific first. First match wins for Category 1.
RULES = [
    # Sports/editorial first: these are unambiguous and must never fall through
    # to a scenery rule.
    (r"basketball|slam dunk|free throw|jump shot|referee|arena crowd|head coach", ["ed_sports", "p_active", "ed_events"]),
    (r"baseball|dodgers|pitcher|the mound|ballpark|dugout|outfield|all-star game|stadium", ["ed_sports", "ed_events", "p_active"]),
    (r"football|soccer|hockey|tennis|marathon|race\b|runner", ["ed_sports", "p_active", "ed_events"]),
    # Objects and food, before any scenery rule can grab a stray landscape word.
    (r"fruit\b|vegetable|papaya|avocado|produce market|farmers market|fruit stand", ["fruit_veg", "food", "food_bev"]),
    (r"\bfood\b|meal|dish\b|cuisine|restaurant plate|dessert|pastry", ["food", "food_bev", "still_life"]),
    (r"tattoo|easel|book\b|painting|artwork|sculpture|mural|craft booth|art booth", ["still_life", "entertainment", "obj_other"]),
    # Built subjects outrank light/weather: "Big Ben at sunset" is a landmark
    # photo, not a sunset photo. These must precede every sky rule below.
    (r"temple|shrine|torii|pagoda|cathedral|church|abbey|castle|minster|mosque|"
     r"big ben|parliament|palace|monument|statue\b", ["landmarks", "historic", "t_arts"]),
    (r"ruins|colonial|ancient|archaeolog|fortress|citadel", ["ruins", "historic", "landmarks"]),
    (r"skyline|downtown|cityscape|city view|neon sign|street scene", ["architecture", "modern_bldg", "t_scenics"]),
    (r"bridge\b", ["architecture", "landmarks", "t_scenics"]),
    (r"canal|harbour|harbor|waterfront", ["architecture", "t_scenics", "water"]),
    (r"waterfall|falls\b|foss\b|cascad", ["waterfalls", "landscapes", "t_scenics"]),
    (r"glacier|iceberg|ice cave|lagoon ice", ["geologic", "landscapes", "t_scenics"]),
    (r"volcan|caldera|lava|crater", ["geologic", "landscapes", "t_scenics"]),
    (r"saguaro|cactus|cacti|desert", ["deserts", "landscapes", "t_america"]),
    # Night sky needs a real night-sky phrase. A bare "star" once dragged a
    # baseball photo into Planetarium via a "star pitcher" keyword.
    (r"milky way|night sky|starry|star-filled|shooting star|meteor|eclipse|aurora|constellation|blood moon", ["planetarium", "skies", "landscapes"]),
    (r"monsoon|storm cloud|thunderhead|lightning", ["skies", "ed_weather", "landscapes"]),
    (r"sunset|sunrise|golden hour|dusk sky", ["sunsets", "landscapes", "skies"]),
    (r"submarine|torpedo|battleship|warship|gun turret|wwii|aircraft wreck", ["military", "historic", "ed_landmarks"]),
    (r"shipwreck|sunken|underwater|scuba|coral|reef", ["marine", "sea", "t_tropical"]),
    (r"whale shark|jellyfish|koi\b|fish\b|turtle|trevally", ["marine", "wildlife", "sea"]),
    (r"penguin|hawk|chough|swan|goose|geese|bird|heron|eagle|owl", ["birds", "wildlife", "nature_details"]),
    (r"\bdog\b|puppy|retriever", ["pets", "mammals", "p_active"]),
    (r"frog|lizard|gecko|snake|iguana", ["reptiles", "wildlife", "tropical_n"]),
    (r"beetle|butterfly|dragonfly|bee\b|spider", ["insects", "wildlife", "nature_details"]),
    # Coast before forest: "rocky coastline with a forested island" is a coast shot.
    (r"coastline|coastal|shoreline|beach|ocean|sea\b|surf\b|wave|bay\b", ["sea", "landscapes", "t_scenics"]),
    (r"mountain|peak\b|summit|matterhorn|ridge|alpine", ["mountains", "landscapes", "t_scenics"]),
    (r"canyon|gorge|cliff|sea stack|basalt", ["geologic", "landscapes", "t_scenics"]),
    (r"lake|river|pond|reservoir|stream", ["lakes_rivers", "landscapes", "water"]),
    (r"forest|redwood|bamboo|conifer|woodland|tree canopy", ["forests", "plants", "landscapes"]),
    (r"cherry blossom|flower|bloom|garden|lily", ["flowers", "plants", "nature_details"]),
    (r"autumn|fall color|snow|winter|spring\b", ["seasons", "landscapes", "nature_details"]),
    # "aerial" alone matched circus "aerial performers"; require a viewpoint.
    (r"aerial view|aerial panorama|from above|drone|bird's-eye|panoramic view", ["aerial", "landscapes", "t_scenics"]),
    (r"portrait|smiling|man\b|woman\b|friends|posing|performer", ["p_portraits", "p_men", "p_active"]),
    (r"train|tram|van\b|car\b|bus\b|airplane|aircraft", ["transportation", "t_scenics", "architecture"]),
]
DEFAULT = ["landscapes", "t_scenics", "nature_details"]


def exif_dates(files):
    """filename -> 'Month YYYY' from DateTimeOriginal."""
    if not files:
        return {}
    out = subprocess.run(
        ["exiftool", "-j", "-DateTimeOriginal", "-FileName"] + [str(SRC / f) for f in files],
        capture_output=True, text=True).stdout
    MON = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]
    res = {}
    for d in json.loads(out or "[]"):
        raw = d.get("DateTimeOriginal") or ""
        m = re.match(r"(\d{4}):(\d{2}):(\d{2})", raw)
        if m:
            res[os.path.basename(d["FileName"])] = f"{MON[int(m.group(2)) - 1]} {m.group(1)}"
    return res


def place_for(text):
    for pat, label, travel in PLACES:
        if re.search(pat, text, re.I):
            return label, travel
    return None, None


# An editorial caption asserts where a thing happened. Dreamstime wants a real
# "City, Country"; 43 of our descriptions open with things like "Riverside
# boardwalk - July 2022", which names no place at all. Same-day EXIF didn't
# pin any of them, so rather than invent a location (a factual claim on a
# published caption) those rows are held back for the owner to label.
NAMED_PLACE = re.compile(
    r"\b(Iceland|Japan|Kyoto|Tokyo|Hiroshima|Miyajima|Osaka|London|England|"
    r"Copenhagen|Denmark|Amsterdam|Netherlands|Cologne|Heidelberg|Germany|"
    r"Zermatt|Grindelwald|Lauterbrunnen|Jungfraujoch|Interlaken|Bern|Switzerland|"
    r"Tucson|Phoenix|Scottsdale|Sedona|Arizona|Honolulu|Hilo|Oahu|Maui|Hawaii|"
    r"Pearl Harbor|Atlanta|Georgia|Vancouver|Canada|San Francisco|California|"
    r"Panama|Appalachian|United States|United Kingdom)\b")


def names_a_place(description):
    head = description.split(":")[0]
    return bool(NAMED_PLACE.search(head))


def categories_for(title, keywords, travel_hint):
    """Title first. Scanning keywords too once mislabeled 100 Adobe images
    'Animals' because a stray keyword matched, so keywords only break ties."""
    picked = None
    for pat, cats in RULES:
        if re.search(pat, title, re.I):
            picked = list(cats)
            break
    if picked is None:
        for pat, cats in RULES:
            if re.search(pat, keywords, re.I):
                picked = list(cats)
                break
    if picked is None:
        picked = list(DEFAULT)
    if travel_hint and travel_hint not in picked:
        picked[2] = travel_hint          # geography beats a third generic tag
    ids, seen = [], set()
    for k in picked:
        v = C[k]
        if v not in seen:
            seen.add(v); ids.append(v)
    while len(ids) < 3:
        ids.append(0)
    return ids[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true", help="FTP the CSV to Dreamstime")
    a = ap.parse_args()

    clean = set(json.loads(CLEAN.read_text()))
    rows = {r["filename"]: r for r in csv.DictReader(open(MASTER))}
    sel = [rows[f] for f in sorted(clean) if f in rows]

    ed_fmt = re.compile(r"^[^:]{5,70}\d{4}\s*:")
    need_prefix = [r["filename"] for r in sel
                   if r["use"] == "editorial" and not ed_fmt.match(r["description"])]
    dates = exif_dates(need_prefix)

    out, held = [], []
    stats = {"editorial": 0, "commercial": 0, "downgraded": 0, "prefix_built": 0}
    for r in sel:
        title, desc = r["title"].strip(), r["description"].strip()
        kw = ", ".join(k.strip() for k in r["keywords"].split(";") if k.strip())
        hay = f"{title} {r['keywords']}"
        place, travel = place_for(hay)
        editorial = 0

        if r["use"] == "editorial":
            if ed_fmt.match(desc):
                if not names_a_place(desc):
                    held.append((r["filename"], desc.split(":")[0].strip()))
                    continue          # keep it out of the queue entirely
                editorial = 1
                stats["editorial"] += 1
            elif place and r["filename"] in dates:
                body = desc[0].lower() + desc[1:] if desc else desc
                desc = f"{place} - {dates[r['filename']]}: {body}"
                editorial = 1
                stats["editorial"] += 1; stats["prefix_built"] += 1
            else:
                # No confident location -> ship as commercial rather than as a
                # malformed editorial header Dreamstime will reject.
                stats["downgraded"] += 1; stats["commercial"] += 1
        else:
            stats["commercial"] += 1

        c1, c2, c3 = categories_for(title, r["keywords"], travel)
        out.append({
            "Filename": r["filename"], "Image Name": title[:100], "Description": desc,
            "Category 1": c1, "Category 2": c2, "Category 3": c3, "keywords": kw,
            "Free": 0, "W-EL": 0, "P-EL": 0, "SR-EL": 0, "SR-Price": 0,
            "Editorial": editorial, "MR doc Ids": "", "Pr Docs": "",
        })

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader(); w.writerows(out)

    print(f"wrote {OUT}  ({len(out)} rows)")
    print(f"  editorial {stats['editorial']} (prefix built for {stats['prefix_built']})")
    print(f"  commercial {stats['commercial']} (incl. {stats['downgraded']} editorial "
          f"downgraded for want of a location)")
    uncat = sum(1 for r in out if r["Category 1"] == 0)
    print(f"  rows with no Category 1: {uncat}")

    if held:
        p = WS / "dreamstime-held-no-location.csv"
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["filename", "vague_prefix"]); w.writerows(held)
        print(f"  HELD BACK {len(held)} editorial rows whose caption names no real place "
              f"-> {p.name} (label the location, then re-run)")

    if a.upload:
        import ftplib
        user = os.environ.get("DREAMSTIME_USER")
        if not user:
            sys.exit("set DREAMSTIME_USER first")
        pw = subprocess.run(["security", "find-generic-password", "-a", user,
                             "-s", "dreamstime-ftp", "-w"],
                            capture_output=True, text=True, check=True).stdout.strip()
        ftp = ftplib.FTP("upload.dreamstime.com", timeout=60)
        ftp.login(user, pw)
        with open(OUT, "rb") as fh:
            ftp.storbinary(f"STOR {OUT.name}", fh)
        ftp.quit()
        print(f"uploaded {OUT.name} to Dreamstime FTP")


if __name__ == "__main__":
    main()
