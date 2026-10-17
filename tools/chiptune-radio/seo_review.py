#!/usr/bin/env python3.12
"""Reads per-video YouTube stats for the ambient channel and says what to change in titles, tags and thumbnails, and which theme x sound videos to make next.

    python3.12 seo_review.py stats.csv                       # a report on screen
    python3.12 seo_review.py stats.csv --json report.json    # the same, as data
    python3.12 seo_review.py stats.json --min-impressions 500

Input: a CSV (or a JSON list of objects, or {"videos": [...]}) with one row per video. Column names are matched without regard to case and spaces.
    slug                   the video's folder name, for example campfire-brown-10h (theme and sound are read from it; or give columns theme and sound)
    title                  the title on YouTube now
    views, impressions     for the period you export (28 days is a good window)
    ctr                    impressions click-through rate, as 4.2 or 0.042 or "4.2%"
    avg_view_duration      seconds, or m:ss, or h:mm:ss
    watch_hours            watch time in hours
    top_search_terms       the YouTube search terms that led to the video, most views first, separated by semicolons
    tags                   optional, separated by semicolons
Until the channel's YouTube Analytics token exists (docs/products/ambient-channel-plan.md says what Ben must grant), export this by hand from YouTube
Studio: Analytics, Advanced mode, Content, pick the metrics above, Export current view; add top_search_terms from each video's Reach tab.

What it says, and the thresholds (all adjustable):
    - Fewer than `--min-impressions` (300) impressions: too little data to judge a click-through rate. Look at the title instead: does it lead with a phrase people search?
    - Click-through under 2 percent with enough impressions: change the thumbnail first (Test & Compare), then the title.
    - A search term that brought viewers but is missing from the title and tags: add it to the tags, and lead the title with it if it is a phrase that fits what the video is.
    - Average view duration under 10 minutes on a video of 2 hours or more with at least 50 views: people leave early; check the first 30 seconds.
    - Next videos: every theme x sound pair not yet made, scored by search demand (keywords.py) times how the theme and the sound have done so far, with
      the data shrunk toward the channel average so one lucky video does not decide. With fewer than 3 videos that have enough impressions, it says so
      and ranks by search demand alone.
It changes nothing on YouTube.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import keywords
import longform_pub as pub
import sounds
import themes

CTR_LOW, EARLY_LEAVE_SECONDS, EARLY_LEAVE_HOURS, EARLY_LEAVE_VIEWS = 2.0, 600.0, 2.0, 50
SHRINK = 2.0                    # a theme or sound with n videos counts as n real videos plus this many average ones


def _norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", k.lower())


ALIASES = {"slug": "slug", "video": "slug", "videoslug": "slug", "title": "title", "videotitle": "title", "views": "views", "impressions": "impressions",
           "ctr": "ctr", "impressionsclickthroughrate": "ctr", "impressionsclickthroughrate": "ctr", "avgviewduration": "avg_view_duration",
           "averageviewduration": "avg_view_duration", "watchhours": "watch_hours", "watchtimehours": "watch_hours", "topsearchterms": "top_search_terms",
           "searchterms": "top_search_terms", "tags": "tags", "theme": "theme", "sound": "sound", "hours": "hours"}


def parse_duration(v) -> float:
    if v in (None, ""):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    parts = str(v).strip().split(":")
    try:
        sec = 0.0
        for p in parts:
            sec = sec * 60 + float(p)
        return sec
    except ValueError:
        return 0.0


def parse_ctr(v) -> float:
    """Click-through as a percent. A value at or under 1 with no % sign is a fraction (0.042 is 4.2 percent); 1.0 exactly is read as 1 percent."""
    if v in (None, ""):
        return 0.0
    txt = str(v).strip()
    pct = txt.endswith("%")
    try:
        x = float(txt.rstrip("%"))
    except ValueError:
        return 0.0
    return x if pct or x > 1.0 else x * 100.0 if x < 1.0 else 1.0


def _num(v) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def parse_slug(slug: str) -> tuple[str | None, str, float]:
    """(theme, sound, hours) from a folder name such as campfire-brown-10h, winter-rain-3h or campfire-2h (sound chiptune)."""
    theme = next((t for t in themes.names() if slug == t or slug.startswith(t + "-")), None)
    rest = slug[len(theme) + 1:] if theme else slug
    sound = "chiptune"
    for n in sorted(sounds.NAMES, key=len, reverse=True):
        if re.search(rf"(^|-){re.escape(n)}(-|$)", rest):
            sound = n
            break
    m = re.search(r"(\d+(?:\.\d+)?)h(?:$|-)", rest)
    return theme, sound, float(m.group(1)) if m else 0.0


def load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        raw = data["videos"] if isinstance(data, dict) else data
    else:
        with path.open(newline="", encoding="utf-8-sig") as f:
            raw = list(csv.DictReader(f))
    rows = []
    for r in raw:
        d = {ALIASES[_norm_key(k)]: v for k, v in r.items() if _norm_key(k) in ALIASES}
        slug = str(d.get("slug") or "").strip()
        if not slug:
            continue
        th, sd, hrs = parse_slug(slug)
        terms = d.get("top_search_terms") or []
        tags = d.get("tags") or []
        split = lambda v: [x.strip() for x in v.split(";") if x.strip()] if isinstance(v, str) else list(v)
        rows.append({"slug": slug, "title": str(d.get("title") or ""), "theme": d.get("theme") or th, "sound": d.get("sound") or sd,
                     "hours": _num(d.get("hours")) or hrs, "views": _num(d.get("views")), "impressions": _num(d.get("impressions")),
                     "ctr": parse_ctr(d.get("ctr")), "avd": parse_duration(d.get("avg_view_duration")), "watch_hours": _num(d.get("watch_hours")),
                     "terms": split(terms), "tags": split(tags)})
    return rows


def key_words(row: dict) -> list[str]:
    """Words that make a search term relevant to this video: the sound's and the theme's key words from keywords.py."""
    out = []
    for table, name in ((keywords.SOUND_SEEDS, row["sound"]), (keywords.THEME_SEEDS, row["theme"])):
        out += table.get(name, ([], []))[1]
    return out


def title_suggestion(row: dict, term: str) -> str | None:
    """The video's title re-led with a search term it already gets, in the channel's usual shape."""
    lead = term.title()
    if row["theme"] in pub.TITLE_THEME and row["hours"]:
        dur = pub.hours_text(row["hours"] * 3600)
        screen = ", Dark Screen" if re.search(r"dark|black", row["title"], re.I) else ""
        t = f"{lead} with {pub.TITLE_THEME[row['theme']]}, {dur}{screen}"
        return t if len(t) <= 100 else f"{lead}, {dur}{screen}"[:100]
    return (f"{lead}, {row['title']}")[:100]


def review_video(row: dict, min_impr: float) -> dict:
    notes, actions = [], []
    title_l, tags_l = row["title"].lower(), " ".join(row["tags"]).lower()
    if row["impressions"] < min_impr:
        notes.append(f"{row['impressions']:g} impressions: too few to judge the click-through rate.")
        if row["theme"] in pub.TITLE_THEME and row["sound"] != "chiptune" and not any(s in title_l for s in (pub.LEADS.get(row["sound"], [""])[0].lower(),)):
            actions.append("The title does not lead with the sound's searched phrase; use the title from longform_pub.py.")
    elif row["ctr"] < CTR_LOW:
        actions.append(f"Click-through is {row['ctr']:.1f}% on {row['impressions']:g} impressions (under {CTR_LOW:g}%): change the thumbnail first, with Test & Compare; if it stays low, re-lead the title.")
    else:
        notes.append(f"Click-through {row['ctr']:.1f}% on {row['impressions']:g} impressions: leave the thumbnail alone.")
    kw = key_words(row)
    missing = [t for t in row["terms"] if t.lower() not in title_l and t.lower() not in tags_l and (not kw or any(k in t.lower() for k in kw))]
    if missing:
        actions.append("Add these searched terms to the tags: " + "; ".join(missing[:5]) + ".")
        new = title_suggestion(row, missing[0])
        if new and new.lower() != row["title"].lower():
            actions.append(f"Title to try, leading with the top missing term: {new!r}")
    if row["hours"] >= EARLY_LEAVE_HOURS and row["views"] >= EARLY_LEAVE_VIEWS and 0 < row["avd"] < EARLY_LEAVE_SECONDS:
        actions.append(f"Average view duration is {row['avd'] / 60:.0f} minutes on a {row['hours']:g} hour video: viewers leave early. Check the first 30 seconds.")
    return {"slug": row["slug"], "theme": row["theme"], "sound": row["sound"], "views": row["views"], "impressions": row["impressions"], "ctr": row["ctr"],
            "watch_hours": row["watch_hours"], "notes": notes, "actions": actions}


def _group(rows: list[dict], key: str) -> dict:
    g: dict = {}
    for r in rows:
        a = g.setdefault(r[key], {"videos": 0, "views": 0.0, "impressions": 0.0, "watch_hours": 0.0, "clicks": 0.0})
        a["videos"] += 1
        a["views"] += r["views"]
        a["impressions"] += r["impressions"]
        a["watch_hours"] += r["watch_hours"]
        a["clicks"] += r["impressions"] * r["ctr"] / 100
    for a in g.values():
        a["ctr"] = round(100 * a["clicks"] / a["impressions"], 2) if a["impressions"] else 0.0
        a["watch_hours_per_video"] = round(a["watch_hours"] / a["videos"], 2)
        del a["clicks"]
    return g


def demand(kw: dict | None, sound: str, theme: str) -> float:
    """Search demand for a pairing: the summed autocomplete score of the top five phrases for the sound plus half that of the theme."""
    s = sum(r["score"] for r in (kw or {}).get("kinds", {}).get(sound, [])[:5])
    t = sum(r["score"] for r in (kw or {}).get("kinds", {}).get(theme, [])[:5])
    return s + 0.5 * t


def next_videos(rows: list[dict], kw: dict | None, min_impr: float, top: int = 8) -> dict:
    judged = [r for r in rows if r["impressions"] >= min_impr]
    made = {(r["theme"], r["sound"]) for r in rows}
    all_sounds = [n for n in sounds.NAMES]
    cells = [(t, s) for t in themes.names() for s in all_sounds if (t, s) not in made]
    mean_wh = (sum(r["watch_hours"] for r in judged) / len(judged)) if judged else 0.0
    use_data = len(judged) >= 3 and mean_wh > 0
    by_sound, by_theme = _group(judged, "sound"), _group(judged, "theme")

    def factor(g: dict, name: str) -> float:
        if not use_data:
            return 1.0
        a = g.get(name, {"videos": 0, "watch_hours": 0.0})
        return (a["watch_hours"] + SHRINK * mean_wh) / ((a["videos"] + SHRINK) * mean_wh)
    dmax = max([demand(kw, s, t) for t, s in cells] + [1e-9])
    out = []
    for t, s in cells:
        d = demand(kw, s, t) / dmax if kw else 1.0
        score = (d ** 0.5) * factor(by_sound, s) * factor(by_theme, t)
        out.append({"theme": t, "sound": s, "score": round(score, 3), "demand": round(d, 3), "sound_factor": round(factor(by_sound, s), 2),
                    "theme_factor": round(factor(by_theme, t), 2)})
    out.sort(key=lambda r: (-r["score"], r["theme"], r["sound"]))
    return {"based_on": "search demand and results so far" if use_data else ("search demand only (fewer than 3 videos have enough impressions)" if kw else "nothing: no keyword research and too little data; follow the calendar"),
            "videos_with_enough_data": len(judged), "next": out[:top]}


def review(rows: list[dict], kw: dict | None = None, min_impr: float = 300.0) -> dict:
    return {"videos": [review_video(r, min_impr) for r in rows], "by_sound": _group(rows, "sound"), "by_theme": _group(rows, "theme"),
            "next": next_videos(rows, kw, min_impr), "keywords_date": (kw or {}).get("date")}


def render_text(rep: dict) -> str:
    L = ["Per video", ""]
    for v in rep["videos"]:
        L.append(f"{v['slug']}  ({v['theme']} + {v['sound']})  views {v['views']:g}, impressions {v['impressions']:g}, CTR {v['ctr']:.1f}%, watch hours {v['watch_hours']:g}")
        L += [f"  - {n}" for n in v["notes"]] + [f"  * {a}" for a in v["actions"]] + [""]
    for label, key in (("By sound", "by_sound"), ("By theme", "by_theme")):
        L.append(label)
        for name, a in sorted(rep[key].items(), key=lambda kv: -kv[1]["watch_hours"]):
            L.append(f"  {name:<16} {a['videos']} video(s), {a['views']:g} views, CTR {a['ctr']:.1f}%, {a['watch_hours']:g} watch hours ({a['watch_hours_per_video']:g} each)")
        L.append("")
    n = rep["next"]
    L.append(f"Make next (ranked by {n['based_on']}; {n['videos_with_enough_data']} video(s) with enough data)")
    for r in n["next"]:
        L.append(f"  {r['theme']} + {r['sound']}   score {r['score']}  (demand {r['demand']}, sound x{r['sound_factor']}, theme x{r['theme_factor']})")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stats", help="CSV or JSON of per-video stats")
    ap.add_argument("--json", help="also write the report here")
    ap.add_argument("--min-impressions", type=float, default=300.0)
    a = ap.parse_args(argv)
    rows = load_rows(Path(a.stats))
    if not rows:
        print("no rows with a slug column", file=sys.stderr)
        return 1
    rep = review(rows, keywords.load(), a.min_impressions)
    print(render_text(rep))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
