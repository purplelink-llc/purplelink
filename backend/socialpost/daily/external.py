"""Posts that did not come from the daily pipeline but still count for the repeat rule.

The 21-day repeat window (and the fatigue count) must see everything the company accounts posted, whoever posted it:
  1. Outreach/OUTREACH-LOG.md rows whose status is "posted" (linkedin_post.py launches, Chrome posts, queue items);
  2. every posted result in the social queue (Ben's own campaign items such as the Buddy test, and the daily ones);
  3. ~/.purplelink/social/history-extra.json, a small private file for a post nobody logged:
       [{"date": "2026-10-18", "platforms": ["linkedin", "bluesky"], "text": "vitae 1.4.0 launch", "note": "..."}]

Each source becomes rows {"date", "platforms", "text", "external": True}. A candidate is blocked on a platform when a
row for that platform inside the window names it (see `names_candidate`). Matching is on words in the row, so it is
a general mechanism: the product and version for a release, the slug or URL path for a page, the video id.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .. import items as itemsmod
from .. import paths
from . import settings as st

PLATFORM_WORDS = {"linkedin": ("linkedin",), "bluesky": ("bluesky", "bsky.app", "bsky.social"),
                  "threads": ("threads.com", "threads.net", "threads @", "threads:", " threads"),
                  "mastodon": ("mastodon",)}


def extra_file() -> Path:
    return paths.home() / "history-extra.json"


def platforms_in(text: str) -> list[str]:
    low = " " + text.lower()
    return [p for p, words in PLATFORM_WORDS.items() if any(w in low for w in words)]


def outreach_rows(today: dt.date, days: int) -> list[dict]:
    p = paths.outreach_log()
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]):
            continue
        if not cells[3].lower().startswith("posted"):
            continue
        d = dt.date.fromisoformat(cells[0])
        if not 0 <= (today - d).days < days:
            continue
        text = " | ".join(cells[1:])
        plats = platforms_in(" ".join(cells[1:3]))
        if plats:
            out.append({"date": cells[0], "platforms": plats, "text": text.lower(), "external": True, "src": "outreach-log"})
    return out


def queue_rows(today: dt.date, days: int) -> list[dict]:
    out = []
    for it in itemsmod.list_items():
        body = " ".join(it.sections.values())
        for plat, r in it.results.items():
            if r.get("status") != "posted":
                continue
            try:
                d = dt.datetime.fromisoformat(str(r.get("posted_at"))).date()
            except ValueError:
                continue
            if 0 <= (today - d).days < days:
                text = f"{it.id} {it.campaign} {it.link} {body}".lower()
                out.append({"date": d.isoformat(), "platforms": [plat], "text": text, "external": True, "src": "queue"})
    return out


def manual_rows(today: dt.date, days: int) -> list[dict]:
    data = st.read_json(extra_file(), [])
    out = []
    for e in data if isinstance(data, list) else []:
        try:
            d = dt.date.fromisoformat(str(e["date"])[:10])
        except (KeyError, ValueError):
            continue
        if 0 <= (today - d).days < days:
            plats = [p for p in e.get("platforms", list(PLATFORM_WORDS)) if p in PLATFORM_WORDS]
            out.append({"date": d.isoformat(), "platforms": plats, "text": str(e.get("text", "")).lower(),
                        "external": True, "src": "history-extra"})
    return out


def load(today: dt.date, days: int) -> list[dict]:
    return outreach_rows(today, days) + queue_rows(today, days) + manual_rows(today, days)


# ---------------------------------------------------------------- matching
def row_versions(text: str) -> set[str]:
    """Dotted versions in the row, plus campaign digits such as 'vitae-140' read as 1.4.0."""
    v = set(re.findall(r"\b\d+\.\d+(?:\.\d+)?\b", text))
    for digits in re.findall(r"[a-z]-(\d{2,3})\b", text):
        v.add(".".join(digits))
    return v


def names_candidate(c, row_text: str) -> bool:
    """True when a row's text is about this candidate."""
    t = row_text.lower()
    parts = c.id.split(":")
    if c.kind == "release":
        app, version = parts[1], parts[2]
        names = {app, app.replace("-", " ")}
        if not any(re.search(rf"\b{re.escape(n)}\b", t) for n in names):
            return False
        seen = row_versions(t)
        return version in seen or not seen
    if c.kind == "video":
        return parts[1].lower() in t
    path = c.url.split("purplelink.llc", 1)[-1].strip("/").lower()   # guides/slug
    slug = path.split("/")[-1]
    if not slug:
        return False
    if re.search(rf"(?<![a-z0-9-]){re.escape(path)}(?![a-z0-9-])", t):      # .../guides/slug in a URL
        return True
    # the bare slug only when it is specific enough not to be a common word ("mac", "latex")
    return len(slug) >= 15 and "-" in slug and re.search(rf"(?<![a-z0-9-]){re.escape(slug)}(?![a-z0-9-])", t) is not None
