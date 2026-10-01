#!/usr/bin/env python3
"""Emit PER-PLATFORM keyword sets instead of one embedded set for all agencies.

WHY THIS EXISTS
Until 2026-09-10 this project wrote one IPTC keyword set (median 30 keywords,
subject-first) and reused it everywhere. Platform research that day showed a
single set cannot be right for all four, because their ranking mechanics
actively disagree:

  Alamy       20-30 tightly relevant tags. Alamy's OWN endorsed keywording
              partner: "Do not be tempted to 'max out' on Keywords...
              over-keywording will only weaken your position in the search
              page results and lead to a declined Click Through Rate" -- and
              Alamy confirms CTR is itself a ranking input. At median 30 with
              276 images above 30, we sit at the top of the harmful range.
              Alamy does NOT stem ("cat" != "cats") but DOES index the
              constituent words of a multi-word tag ("Banff National Park"
              also matches banff / national park / park), so multi-word tags
              are strictly better value than the single-word generics.
  Adobe Stock 15-35 keywords, and "the first 10 keywords will have the most
              weight in search placement" -- order matters and ours was never
              ordered for Adobe. Adobe also only auto-suggests keywords when a
              file has NO embedded metadata, so our embed-once pipeline has
              been suppressing Adobe's own suggester.
  Shutterstock 7-50, no documented order weighting, but their guidance is to
              DIFFERENTIATE keywords between near-identical frames. We are
              under-keyworded here at 30, not over.
  Getty/iStock controlled vocabulary, and keywords are effectively locked once
              accepted. NOT emitted here -- the vocabulary could not be
              verified from Getty primary sources (contributor help is
              login-gated), and writing free-text guesses into a controlled
              vocabulary field does nothing. Confirm from inside the account
              before adding a Getty emitter.

HOW THE ALAMY TRIM WORKS
photo-metadata.sh wrote keywords subject-first, so position already encodes
subject prominence -- which is exactly what Alamy says to choose supertags by.
That order is preserved. The trim drops a short, evidence-backed list of terms
measured at ZERO buyer demand (ALAMY_ZERO_DEMAND) and then cuts to the budget,
so a real term inherits each slot a dead generic held. Ranking all keywords by
demand overlap was tried and rejected -- see the note on ALAMY_ZERO_DEMAND.

THE ADDED TERMS ARE FACTUAL, NOT GUESSED
Buyers search perspective/aesthetic/composition terms ("copy space", "shallow
depth of field", "panoramic"). Most of those need eyes on the image, and
inventing them would be inaccurate metadata -- a stated rejection reason on
Shutterstock. So this only adds terms it can *derive from EXIF*: orientation
and aspect from the pixel dimensions, depth of field from the aperture, low
light from the exposure/ISO, focal-length class from the 35mm-equivalent.
Nothing here is a guess about content. "copy space" and similar deliberately
stay out until something actually looks at the pixels.

USAGE
  scripts/platform-keywords.py                 # emit all three CSVs
  scripts/platform-keywords.py --platform alamy
  scripts/platform-keywords.py --stats         # show what would change
"""
import argparse, csv, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
MASTER = WS / "metadata-master.csv"

# Per-platform keyword budgets, from each platform's own contributor guidance.
ALAMY_TAGS = 25          # inside their 20-30 "relevant, not maxed" advice
ALAMY_SUPERTAGS = 10     # Alamy's cap; these carry extra ranking priority
ADOBE_MAX = 35           # their stated "15 to 35 is often plenty" ceiling
ADOBE_WEIGHTED = 10      # first N carry the most search weight
# A CEILING, NOT A QUOTA. An analysis of Shutterstock's most-popular images
# found high keyword counts correlate with ranking, which argues for ~45 -- but
# that analysis is vendor-authored and correlational, while Shutterstock's OWN
# rule that irrelevant or repeated keywords are a rejection reason
# ("keyword spamming") is primary and explicit. So we emit only keywords we can
# actually justify and land around 32. DO NOT pad toward 45 with filler to hit
# the number; that trades a documented rejection risk for a correlation.
SHUTTERSTOCK_TARGET = 45


def load_rows():
    rows = [r for r in csv.DictReader(open(MASTER))
            if not r["dupe_of"].strip() and r["use"] in ("commercial", "editorial")
            # IMG_* are iPhone frames, not Nikon captures -- private wedding
            # photography that must never be licensed. Owner's rule, 2026-08-07.
            # Must match stock-ftp-upload.py's eligible() exactly; this filter
            # was missing here and let 14 IMG_* rows (incl. IMG_9209.jpeg, the
            # file that caused a 285-file mass rejection on Alamy) leak into
            # the v2 CSVs on 2026-09-10.
            and not r["filename"].upper().startswith("IMG_")
            # 11156_* are purchased race-event photos Ben doesn't hold copyright on.
            and not r["filename"].startswith("11156_")
            and r["filename"].upper().startswith("DSC")]
    return rows


def kws(row):
    return [k.strip() for k in row["keywords"].split(";") if k.strip()]


def exif_for(names):
    """One exiftool call for the whole set -- per-file calls cost minutes."""
    paths = [str(SRC / n) for n in names if (SRC / n).exists()]
    if not paths:
        return {}
    out = subprocess.run(
        ["exiftool", "-j", "-FileName", "-FocalLengthIn35mmFormat", "-FNumber",
         "-ExposureTime", "-ISO", "-ImageWidth", "-ImageHeight"] + paths,
        capture_output=True, text=True).stdout
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}
    return {Path(d.get("FileName", "")).name: d for d in data}


def _ratio(w, h):
    return (max(w, h) / min(w, h)) if (w and h) else None


def derived_terms(ex):
    """Buyer-search terms that follow from the EXIF as a matter of fact.

    Deliberately conservative: every term here is true by construction from a
    number in the file. Anything needing a look at the actual picture (copy
    space, candid, authentic) is out of scope -- see the module docstring.
    """
    t = []
    if not ex:
        return t
    w, h = ex.get("ImageWidth"), ex.get("ImageHeight")
    if w and h:
        t.append("horizontal" if w >= h else "vertical")
        r = _ratio(w, h)
        if r and r >= 2.0:
            t.append("panoramic")
        if r and abs(r - 1.0) < 0.02:
            t.append("square format")

    fl = ex.get("FocalLengthIn35mmFormat")
    if isinstance(fl, str):
        fl = fl.replace("mm", "").strip()
    try:
        fl = float(fl)
    except (TypeError, ValueError):
        fl = None
    if fl:
        if fl <= 24:
            t.append("wide angle")
        elif fl >= 135:
            t.append("telephoto")

    fn = ex.get("FNumber")
    try:
        fn = float(fn)
    except (TypeError, ValueError):
        fn = None
    if fn and fn <= 2.8:
        t += ["shallow depth of field", "bokeh"]

    # ExposureTime arrives as "1/160" or a float like 2.5
    et = ex.get("ExposureTime")
    secs = None
    if isinstance(et, str) and "/" in et:
        try:
            a, b = et.split("/")
            secs = float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            secs = None
    else:
        try:
            secs = float(et)
        except (TypeError, ValueError):
            secs = None
    if secs is not None and secs >= 1.0:
        t.append("long exposure")

    try:
        iso = float(ex.get("ISO"))
    except (TypeError, ValueError):
        iso = None
    if iso and iso >= 3200:
        t.append("low light")

    return t


def title_words(title):
    stop = {"a", "an", "the", "of", "at", "in", "on", "with", "and", "to",
            "from", "for", "by", "over", "under", "near", "into"}
    return [w for w in "".join(c.lower() if (c.isalnum() or c.isspace()) else " "
                               for c in title).split() if w and w not in stop]


def demand_vocab():
    """Words that REAL Alamy buyers typed, from alamy-search-terms.json.

    Captured 2026-09-10 from Alamy Measures: 238 queries over 30 days that
    surfaced our images, summing to exactly our 288 recorded views. Measured
    against those queries, our most-repeated keywords are worthless:

        travel      301x in our keywords ->   0 buyer queries
        tourism     266x                 ->   0
        nature      232x                 ->   0
        summer      149x                 ->   0
        outdoor     117x                 ->   0
        lifestyle   101x                 ->   0
        landmark     99x                 ->   0
        wilderness   98x                 ->   0

    Buyers type specific things instead -- "cologne germany", "rijksmuseum",
    "westminster abbey henry vii chapel", "ameyoko", "hyde park london". 93%
    of queries are multi-word. Both of the only two zooms we have ever had came
    from precise place names. Since Alamy weights CTR into AlamyRank and warns
    that over-keywording depresses CTR, a keyword with no demand is not neutral
    -- it is dilution.

    CAVEAT: 238 queries in one month is a small sample, so absence here is not
    proof of zero global demand. It is used only to ORDER keywords and to pick
    supertags, never to delete a term outright.
    """
    p = WS / "alamy-demand-vocab.json"
    if not p.exists():
        return set()
    return set(json.loads(p.read_text()))


# Terms measured at ZERO buyer demand while being the most-repeated keywords in
# the portfolio. Each appears 98-301 times across our images and in 0 of the 238
# real Alamy queries captured 2026-09-10 (see demand_vocab). Alamy weights CTR
# into AlamyRank and warns that over-keywording depresses CTR, so these are not
# harmless padding -- they dilute 25 finite tag slots.
#
# Kept as an explicit, short, auditable list rather than a demand-ranking
# heuristic. Ranking every keyword by word-overlap against 238 queries was tried
# first and made things WORSE: it promoted "blue sky" above "botanical garden" as
# a supertag, because generic words like sky/blue happen to occur in the sample
# while "lily pad" does not. That is overfitting a one-month sample. Dropping
# eight proven-dead terms is the part the evidence actually supports.
ALAMY_ZERO_DEMAND = {
    "travel", "tourism", "nature", "summer", "outdoor", "outdoors",
    "lifestyle", "landmark", "wilderness",
}


def alamy_set(row, demand=None):
    """Subject-first order preserved; proven-dead generics removed.

    photo-metadata.sh wrote keywords subject-first, so position already encodes
    subject prominence -- which is what Alamy says to pick supertags by. That
    ordering is left alone. The only change is dropping ALAMY_ZERO_DEMAND, then
    trimming to the tag budget, which lets a real term move up into each slot a
    dead generic was occupying.
    """
    ks = [k for k in kws(row) if k.strip().lower() not in ALAMY_ZERO_DEMAND]
    head = ks[:ALAMY_TAGS]
    supertags = head[:ALAMY_SUPERTAGS]
    return head, supertags


def adobe_set(row):
    """Same terms, reordered so the weighted first 10 mirror the title."""
    ks = kws(row)
    tw = set(title_words(row["title"]))
    hoisted = [k for k in ks if any(w in tw for w in k.lower().split())]
    rest = [k for k in ks if k not in hoisted]
    ordered = hoisted + rest
    return ordered[:ADOBE_MAX]


def shutterstock_set(row, derived):
    """Full set plus the EXIF-derived terms, toward the top of their range."""
    ks = kws(row)
    have = {k.lower() for k in ks}
    add = [d for d in derived if d.lower() not in have]
    return (ks + add)[:SHUTTERSTOCK_TARGET]


# Shutterstock requires 1-2 categories from ITS OWN fixed 26-name list before
# a submission can leave "Needs attention" -- confirmed 2026-09-11 via their
# support docs after a CSV push landed description/keywords on 387 images but
# left every one stuck, because shutterstock-metadata-v2.csv's Categories
# column had been written as "" for every row (never implemented).
# https://submit.shutterstock.com/help/en/articles/10617427
SHUTTERSTOCK_CATEGORIES = [
    "Abstract", "Animals/Wildlife", "Arts", "Backgrounds/Textures",
    "Beauty/Fashion", "Buildings/Landmarks", "Business/Finance",
    "Celebrities", "Education", "Food and Drink", "Healthcare/Medical",
    "Holidays", "Industrial", "Interiors", "Miscellaneous", "Nature",
    "Objects", "Parks/Outdoor", "People", "Religion", "Science",
    "Signs/Symbols", "Sports/Recreation", "Technology", "Transportation",
    "Vintage",
]

# Trigger words drawn from the portfolio's OWN keyword vocabulary (the
# top-400 most-used terms across metadata-master.csv, 2026-09-11), not
# invented -- this maps what a caption/keyword set ALREADY says onto
# Shutterstock's fixed category names, the same kind of derivation
# adobe_set()/alamy_set() already do from real data rather than guessing
# new content about the image.
CATEGORY_TRIGGERS = {
    "Sports/Recreation": {
        "basketball", "sport", "sports", "athlete", "athletes", "athletic",
        "competition", "arena", "stadium", "ncaa", "mlb", "pac-12", "jersey",
        "college basketball", "college sports", "womens basketball",
        "sports action", "sports photography", "game day", "game action",
        "team sport", "indoor sports", "indoor arena", "courtside",
        "baseball", "professional baseball", "ballpark", "home plate",
        "spectator sport", "spectators", "fans", "university sports",
        "athletics", "player", "uniform", "team", "rivalry", "action shot",
        "hiking", "hiking trail", "outdoor recreation", "fitness",
    },
    "Animals/Wildlife": {
        "animal", "animals", "wildlife", "wildlife photography", "dog",
        "canine", "pet", "pet portrait", "pet photography", "domestic animal",
        "companion animal", "family pet", "bird", "feathers", "zoo",
        "marine life", "species", "mixed breed", "animal portrait",
        "conservation",
    },
    "Buildings/Landmarks": {
        "architecture", "landmark", "famous landmark", "iconic landmark",
        "cityscape", "skyline", "city skyline", "downtown", "urban",
        "urban landscape", "heritage", "heritage site", "cultural heritage",
        "historic building", "historic site", "historic district", "historic",
        "monument", "statue", "old town", "european city", "metropolis",
        "metropolitan", "skyscrapers", "facade", "gothic architecture",
        "japanese architecture", "capital city", "unesco", "tourist attraction",
        "famous", "harbor", "canal", "billboards", "stone wall", "naval history",
        "military history", "pearl harbor", "downtown tokyo", "busy street",
        "city street", "city life",
    },
    "Nature": {
        "nature", "nature photography", "wilderness", "forest", "trees",
        "greenery", "green trees", "foliage", "woodland", "canopy", "moss",
        "mountains", "mountain", "mountain range", "geology", "rock formation",
        "boulders", "rocks", "volcanic rock", "volcanic landscape", "canyon",
        "waterfall", "cascade", "glacier", "river", "lake", "coastline",
        "coastal", "shoreline", "seascape", "ocean", "pacific ocean",
        "underwater", "natural beauty", "natural wonder", "natural phenomenon",
        "natural light", "desert", "desert landscape", "sonoran desert",
        "southwest", "jungle", "tropical", "island", "big island", "valley",
        "valley view", "hillside", "countryside", "rugged terrain", "storm clouds",
        "dramatic sky", "night sky", "dark sky", "clear sky", "cloudy sky",
        "grey sky", "sky", "horizon", "vista", "panoramic view", "wide view",
        "landscape", "landscape photography", "scenic", "scenic view",
        "scenic overlook", "remote", "ecosystem", "weather", "snow", "winter",
        "spring", "autumn", "fall", "mist", "swiss alps",
    },
    "Parks/Outdoor": {
        "park", "garden", "outdoor", "outdoors", "outdoor portrait",
        "outdoor adventure", "backyard", "backyard party", "patio",
        "campus", "trail", "grass", "green grass", "botanical", "waterfront",
        "beach", "overlook",
    },
    "People": {
        "portrait", "candid", "candid portrait", "candid moment", "man",
        "men", "woman", "young man", "young adult", "young adults", "male",
        "two men", "group photo", "group portrait", "friends", "friendship",
        "togetherness", "bonding", "camaraderie", "smiling", "laughing",
        "joy", "joyful", "happy", "humor", "casual", "casual portrait",
        "casual style", "posing", "sitting", "standing", "profile",
        "confident", "relaxed", "romantic", "portrait photography",
        "travel portrait", "sunglasses", "beard", "elegant", "dressed up",
        "formal wear", "cap and gown", "graduation", "commencement",
        "achievement", "milestone", "success", "energetic", "teamwork",
        "party", "house party", "indoor party", "social event", "social gathering",
        "gathering", "celebration", "festive", "excitement", "nightlife",
        "tattoo",
    },
    "Religion": {
        "religious site", "sacred site", "spiritual", "buddhist temple",
    },
    "Vintage": {"vintage", "americana"},
    "Industrial": {"engineering", "craftsmanship", "traffic", "signage"},
    "Interiors": {"indoor",},
    "Beauty/Fashion": {"fashion",},
    "Education": {"education",},
}

# Checked in this order when scores tie, so the more specific/likely category
# for THIS portfolio (landscape and sports photography, no studio/product
# work) wins over a generic catch-all.
CATEGORY_PRIORITY = ["Sports/Recreation", "Animals/Wildlife", "Buildings/Landmarks",
                     "Nature", "Parks/Outdoor", "People", "Religion", "Vintage",
                     "Industrial", "Interiors", "Beauty/Fashion", "Education"]


# Word-boundary, not substring: a naive `"pet" in text` matched inside
# "com-PET-itive" and "athletic com-PET-ition" and tagged basketball-coach
# photos Animals/Wildlife. \b anchors so "pet" only hits the standalone word
# (and "team"/"man"/"dog"/etc. get the same protection), while multi-word
# phrases like "college basketball" still match as a unit.
_CATEGORY_PATTERNS = {
    cat: [re.compile(rf"\b{re.escape(trig)}\b") for trig in trigs]
    for cat, trigs in CATEGORY_TRIGGERS.items()
}


def shutterstock_categories(row):
    """1-2 categories from Shutterstock's fixed list, scored from the row's
    OWN title/description/keywords -- never from image content we haven't
    looked at. Falls back to Miscellaneous (itself one of the 26 valid
    names) rather than leaving the required field empty when nothing in the
    existing text matches a trigger.
    """
    text = f"{row['title']} {row['description']} {row['keywords']}".lower()
    scores = {}
    for cat in CATEGORY_PRIORITY:
        hits = sum(1 for pat in _CATEGORY_PATTERNS[cat] if pat.search(text))
        if hits:
            scores[cat] = hits
    if not scores:
        return "Miscellaneous"
    ranked = sorted(scores, key=lambda c: (-scores[c], CATEGORY_PRIORITY.index(c)))
    return ",".join(ranked[:2])


# Alamy's own fixed Primary Category list, read straight from its live
# dropdown (ul.dropdown-menu li[custom-li-attribute=changeprimarycategory],
# 2026-09-11) -- a DIFFERENT set of 25 names from Shutterstock's 26, so it
# gets its own trigger table rather than reusing CATEGORY_TRIGGERS. Found
# because 3 of 10 sampled live images had Primary category still at the
# unset "Select" placeholder -- nothing in this pipeline had ever set it,
# since alamy-metadata-v2.csv has no Category column and Alamy has no bulk
# CSV import for it (this can only be set one image at a time, live).
ALAMY_CATEGORIES = [
    "Abstracts and backgrounds", "Animals and wildlife",
    "Architecture and interiors", "Archive or historical", "Art and artwork",
    "Business", "Celebrations and life events", "Concepts", "Education",
    "Entertainment and celebrities", "Food and drink", "Healthcare and medical",
    "Industry and agriculture", "Landscapes", "Lifestyle", "News and reportage",
    "Objects and still life", "Occupations", "Plants and gardens", "Science",
    "Sport", "Technology", "Transport", "Travel", "Weather and seasons",
]

ALAMY_CATEGORY_TRIGGERS = {
    "Sport": {
        "basketball", "sport", "sports", "athlete", "athletes", "athletic",
        "competition", "arena", "stadium", "ncaa", "mlb", "pac-12", "jersey",
        "college basketball", "college sports", "womens basketball",
        "sports action", "sports photography", "game day", "game action",
        "team sport", "indoor sports", "indoor arena", "courtside",
        "baseball", "professional baseball", "ballpark", "home plate",
        "spectator sport", "spectators", "fans", "university sports",
        "athletics", "player", "uniform", "team", "rivalry", "action shot",
    },
    "Animals and wildlife": {
        "animal", "animals", "wildlife", "wildlife photography", "dog",
        "canine", "pet", "pet portrait", "pet photography", "domestic animal",
        "companion animal", "family pet", "bird", "feathers", "zoo",
        "marine life", "species", "mixed breed", "animal portrait",
        "conservation",
    },
    "Architecture and interiors": {
        "architecture", "landmark", "famous landmark", "iconic landmark",
        "cityscape", "skyline", "city skyline", "downtown", "urban",
        "urban landscape", "historic building", "monument", "statue",
        "old town", "european city", "metropolis", "metropolitan",
        "skyscrapers", "facade", "gothic architecture", "japanese architecture",
        "capital city", "indoor", "interior", "interiors", "stone wall",
        "busy street", "city street",
    },
    "Landscapes": {
        "nature", "nature photography", "wilderness", "forest", "trees",
        "greenery", "green trees", "mountains", "mountain", "mountain range",
        "geology", "rock formation", "boulders", "rocks", "volcanic rock",
        "volcanic landscape", "canyon", "waterfall", "cascade", "glacier",
        "river", "lake", "coastline", "coastal", "shoreline", "seascape",
        "ocean", "pacific ocean", "desert", "desert landscape",
        "sonoran desert", "southwest", "jungle", "tropical", "island",
        "big island", "valley", "valley view", "hillside", "countryside",
        "rugged terrain", "horizon", "vista", "panoramic view", "wide view",
        "landscape", "landscape photography", "scenic", "scenic view",
        "scenic overlook", "remote", "natural beauty", "natural wonder",
        "swiss alps",
    },
    "Plants and gardens": {
        "garden", "botanical", "plants", "flowers", "foliage", "woodland",
        "canopy", "moss", "green grass", "grass",
    },
    "Travel": {
        "travel", "tourism", "tourist", "tourists", "destination",
        "wanderlust", "sightseeing", "vacation", "heritage site", "unesco",
        "bucket list", "tourist attraction", "travel photography",
        "travel destination", "iconic", "heritage", "cultural heritage",
        "historic site", "historic district",
    },
    "Weather and seasons": {
        "storm clouds", "dramatic sky", "night sky", "dark sky", "clear sky",
        "cloudy sky", "grey sky", "snow", "winter", "spring", "autumn",
        "fall", "mist", "sunset", "dusk", "twilight", "golden hour",
        "evening light", "overcast", "overcast sky",
    },
    "Celebrations and life events": {
        "celebration", "party", "house party", "indoor party", "graduation",
        "commencement", "cap and gown", "milestone", "achievement",
        "holiday season", "festive", "social event", "gathering",
        "backyard party",
    },
    "Lifestyle": {
        "candid", "candid portrait", "candid moment", "casual",
        "casual portrait", "casual style", "relaxed", "friends",
        "friendship", "togetherness", "bonding", "camaraderie", "smiling",
        "laughing", "joy", "joyful", "happy", "lifestyle", "active lifestyle",
        "leisure", "posing", "group photo", "group portrait",
    },
    "Archive or historical": {
        "historic", "vintage", "americana", "naval history",
        "military history", "pearl harbor",
    },
    "Food and drink": {"food", "drink", "restaurant", "meal"},
    "Transport": {"boats", "car", "train", "airplane"},
}

ALAMY_CATEGORY_PRIORITY = ["Sport", "Animals and wildlife",
                          "Architecture and interiors", "Landscapes",
                          "Plants and gardens", "Travel", "Weather and seasons",
                          "Celebrations and life events", "Lifestyle",
                          "Archive or historical", "Food and drink", "Transport"]

_ALAMY_CATEGORY_PATTERNS = {
    cat: [re.compile(rf"\b{re.escape(trig)}\b") for trig in trigs]
    for cat, trigs in ALAMY_CATEGORY_TRIGGERS.items()
}


def alamy_category(row):
    """Single best-match Primary category from Alamy's fixed 25-name list,
    scored from the row's own title/description/keywords. Unlike
    shutterstock_categories() this returns None on no signal rather than a
    catch-all guess -- Alamy has no "Miscellaneous"-equivalent honest
    fallback, and this sets a LIVE field on an already-selling image, so an
    unconfident category is worse than leaving it for manual review.
    """
    text = f"{row['title']} {row['description']} {row['keywords']}".lower()
    scores = {}
    for cat in ALAMY_CATEGORY_PRIORITY:
        hits = sum(1 for pat in _ALAMY_CATEGORY_PATTERNS[cat] if pat.search(text))
        if hits:
            scores[cat] = hits
    if not scores:
        return None
    return sorted(scores, key=lambda c: (-scores[c], ALAMY_CATEGORY_PRIORITY.index(c)))[0]


# Fine Art America / Pixels.com sells PRINTS of an image, not licensing usage
# rights -- a fundamentally different buyer intent from Alamy/Adobe/
# Shutterstock, and faa-upload.py had been sending it the exact same
# stock-licensing keyword set as everyone else. Confirmed live 2026-09-19:
# median keyword field already uses 328 of FAA's 500-character tag limit,
# so the fix isn't "add more words," it's "the words are for the wrong
# buyer." A stock buyer searches what an image DEPICTS ("candid moment",
# "horseplay", "antics"); a print buyer searches what they're DECORATING
# ("living room wall art", "housewarming gift"). Confirmed against FAA's own
# published seller advice: tags are internal-search-only pathways (so this
# doesn't need to be Google-readable prose), title should front-load the
# strongest phrase (existing subject-first titles already do this, untouched
# here), and descriptions should read as a short story, not a keyword dump.
#
# Existing subject keywords are KEPT, not replaced -- a print buyer still
# searches "mountain wall art" using the real subject word "mountain", not
# just the product word. This only ADDS decor/gift-intent phrasing on top,
# and only phrasing tied to a real signal already in the row's own text
# (same discipline as ALAMY_CATEGORY_TRIGGERS/CATEGORY_TRIGGERS above) --
# never a gift-occasion or room-type claim invented from nothing.
FAA_UNIVERSAL_TERMS = ["wall art", "canvas print", "framed print",
                       "home decor", "photography print", "fine art print"]

FAA_DECOR_TRIGGERS = {
    "nature wall art,landscape photography,living room wall art,nature lover gift": {
        "mountain", "mountains", "lake", "forest", "waterfall", "desert",
        "canyon", "valley", "wilderness", "landscape", "glacier", "volcanic",
        "sunset", "sunrise", "scenic", "nature", "trees", "river", "cliff",
    },
    "beach house decor,coastal wall art,ocean photography": {
        "ocean", "beach", "coastal", "coastline", "seascape", "island",
        "shoreline", "waves", "tropical", "harbor",
    },
    "cityscape wall art,architectural photography,office wall art,modern wall decor": {
        "skyline", "cityscape", "architecture", "downtown", "skyscraper",
        "urban", "city street", "bridge", "tower", "historic building",
    },
    "travel photography wall art,wanderlust gift,traveler gift": {
        "travel", "tourist", "tourism", "destination", "heritage site",
        "unesco", "temple", "shrine", "castle", "cathedral", "landmark",
    },
    "animal wall art,wildlife photography,animal lover gift": {
        "animal", "wildlife", "bird", "dog", "canine", "pet", "zoo",
        "marine life", "wild animal",
    },
    "sports wall art,sports fan gift,man cave decor": {
        "basketball", "baseball", "athlete", "stadium", "arena", "team",
        "sports action", "college sports",
    },
    "black and white photography,fine art photography print": {
        "silhouette", "monochrome", "night photography", "dramatic lighting",
    },
}
_FAA_TRIGGER_PATTERNS = [
    (phrases, [re.compile(rf"\b{re.escape(w)}\b") for w in words])
    for phrases, words in FAA_DECOR_TRIGGERS.items()
]

FAA_TAG_LIMIT = 500


def faa_keywords(row):
    """Existing subject keywords, reordered so the strongest real-content
    term still leads (tags are FAA's own internal search index, not a
    public-facing field, so keyword-dense phrasing here is expected, not
    spammy) plus decor/gift-intent phrasing for whichever FAA_DECOR_TRIGGERS
    actually matched this row's own text, plus the universal product terms
    every print listing can honestly carry. Trimmed to FAA_TAG_LIMIT so nothing
    silently gets truncated server-side the way some rows already were.
    """
    text = f"{row['title']} {row['description']} {row['keywords']}".lower()
    existing = kws(row)
    have = {k.lower() for k in existing}
    added = []
    for phrases, patterns in _FAA_TRIGGER_PATTERNS:
        if any(p.search(text) for p in patterns):
            for phrase in phrases.split(","):
                if phrase not in have:
                    added.append(phrase)
                    have.add(phrase)
    for term in FAA_UNIVERSAL_TERMS:
        if term not in have:
            added.append(term)
            have.add(term)

    ordered = existing + added
    out, total = [], 0
    for k in ordered:
        extra = len(k) + (1 if out else 0)   # +1 for the joining comma
        if total + extra > FAA_TAG_LIMIT:
            break
        out.append(k)
        total += extra
    return ",".join(out)


def faa_description(row):
    """The existing factual description, plus one short, honest decor-intent
    closing line -- never an invented backstory or first-person narrative
    (nothing in this pipeline knows what Ben was actually thinking when he
    took the shot, and claiming otherwise under his name would be exactly
    the kind of fabricated content this project avoids everywhere else). One
    real, generic, always-true sentence about the physical product on offer
    is honest; a manufactured "inspiration" is not.
    """
    desc = row["description"].strip()
    closer = ("A striking addition to any wall, printed as a canvas, framed "
             "print, or fine art print to your specification.")
    if not desc:
        return closer
    if desc.endswith((".", "!", "?")):
        return f"{desc} {closer}"
    return f"{desc}. {closer}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["alamy", "adobe", "shutterstock", "faa"])
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()

    rows = load_rows()
    demand = demand_vocab()
    print(f"{len(rows)} licensable images | buyer-demand vocab: {len(demand)} words", flush=True)
    print("reading EXIF (one pass)...", flush=True)
    ex = exif_for([r["filename"] for r in rows])
    print(f"  EXIF for {len(ex)} of {len(rows)}", flush=True)

    if a.stats:
        import statistics
        before = [len(kws(r)) for r in rows]
        al = [len(alamy_set(r, demand)[0]) for r in rows]
        ad = [len(adobe_set(r)) for r in rows]
        ss = [len(shutterstock_set(r, derived_terms(ex.get(r["filename"], {})))) for r in rows]
        nd = [len(derived_terms(ex.get(r["filename"], {}))) for r in rows]
        moved = sum(1 for r in rows if adobe_set(r)[:ADOBE_WEIGHTED] != kws(r)[:ADOBE_WEIGHTED])
        print(f"\n  current   median {statistics.median(before):.0f}  max {max(before)}")
        print(f"  alamy     median {statistics.median(al):.0f}  (was {statistics.median(before):.0f}) "
              f"-- {sum(1 for b,x in zip(before,al) if x<b)} images trimmed")
        print(f"  adobe     median {statistics.median(ad):.0f}  "
              f"-- weighted top-10 reordered on {moved} images")
        print(f"  shutterstk median {statistics.median(ss):.0f}  (was {statistics.median(before):.0f})")
        print(f"  EXIF-derived terms added: median {statistics.median(nd):.0f}, max {max(nd)}")
        return

    want = [a.platform] if a.platform else ["alamy", "adobe", "shutterstock", "faa"]

    if "alamy" in want:
        p = WS / "alamy-metadata-v2.csv"
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Filename", "Caption", "Tags", "Supertags", "License", "Editorial", "Title"])
            for r in rows:
                tags, supers = alamy_set(r, demand)
                w.writerow([r["filename"], r["description"], ";".join(tags),
                            ";".join(supers), "RM" if r["use"] == "editorial" else "RF",
                            "true" if r["use"] == "editorial" else "false", r["title"]])
        print(f"wrote {p}")

    if "adobe" in want:
        p = WS / "adobe-stock-metadata-v2.csv"
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
            for r in rows:
                w.writerow([r["filename"], r["title"], ",".join(adobe_set(r)), "", ""])
        print(f"wrote {p}")

    if "shutterstock" in want:
        p = WS / "shutterstock-metadata-v2.csv"
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Filename", "Description", "Keywords", "Categories",
                        "Illustration", "Mature Content", "Editorial"])
            for r in rows:
                ks = shutterstock_set(r, derived_terms(ex.get(r["filename"], {})))
                w.writerow([r["filename"], r["description"], ",".join(ks),
                            shutterstock_categories(r),
                            "no", "no", "yes" if r["use"] == "editorial" else "no"])
        print(f"wrote {p}")

    if "faa" in want:
        p = WS / "faa-metadata-v2.csv"
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Filename", "Title", "Keywords", "Description"])
            for r in rows:
                w.writerow([r["filename"], r["title"], faa_keywords(r), faa_description(r)])
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
