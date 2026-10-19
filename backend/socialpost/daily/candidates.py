"""Candidates: company items from the last week, plus an evergreen backlog so the list never runs empty.

Every candidate carries only what the page itself says (its own title, meta description, changelog entry). Pages are
read from the LIVE site, so something merged but still waiting for the next build is never a candidate. Facts are
loaded lazily (`load_facts`) because the evergreen list has dozens of entries and the day's pick needs a few.
"""
from __future__ import annotations

import datetime as dt
import html as html_lib
import json
import re
import subprocess
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from .. import paths
from . import lib219 as L

SITE = L.core.SITE
KINDS = ("release", "guide", "video", "blog", "tool", "evergreen")
PAGE_RE = re.compile(r"^/(guides|blog|tools)/([a-z0-9][a-z0-9-]*)/$")
KIND_OF_DIR = {"guides": "guide", "blog": "blog", "tools": "tool"}


@dataclass
class Candidate:
    id: str                 # stable key: guide:<slug>, release:<app>:<version>, video:<id>, ...
    kind: str               # release | guide | video | blog | tool | evergreen
    url: str                # the bare link to post (no UTM)
    published: dt.date | None = None
    title_hint: str = ""
    traffic: int = 0        # 90-day pageviews (evergreen only)
    page_kind: str = ""     # for evergreen: guide | blog | tool
    meta: dict = field(default_factory=dict)
    facts: dict | None = None

    def age_days(self, today: dt.date) -> int:
        return max(0, (today - self.published).days) if self.published else 0


# ---------------------------------------------------------------- pieces
def sitemap_urls(http) -> dict[str, dt.date | None]:
    """{path: lastmod} for the guide, blog and tool pages in the live sitemap."""
    xml = L.events.get_live(http, f"{SITE}/sitemap.xml")
    out: dict[str, dt.date | None] = {}
    for blk in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", blk)
        if not loc or not loc.group(1).startswith(SITE):
            continue
        path = loc.group(1)[len(SITE):]
        if not PAGE_RE.match(path):
            continue
        lm = re.search(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})", blk)
        out[path] = dt.date.fromisoformat(lm.group(1)) if lm else None
    return out


def git_added_dates(repo=None, run=subprocess.run) -> dict[str, dt.date]:
    """{path: date the page was first added to origin/main}: its real publish date, which a sitemap lastmod (bumped by
    any site-wide edit) is not. Returns {} when git or the checkout is unavailable."""
    repo = repo or paths.repo_root()
    try:
        r = run(["git", "-C", str(repo), "log", "origin/main", "--diff-filter=A", "--name-only", "--format=@@%aI",
                 "--", "site/guides", "site/blog", "site/tools"], capture_output=True, text=True, timeout=120)
    except Exception:
        return {}
    if r.returncode != 0:
        return {}
    out: dict[str, dt.date] = {}
    cur = None
    for line in r.stdout.splitlines():
        if line.startswith("@@"):
            cur = dt.date.fromisoformat(line[2:12])
        elif line.endswith("/index.html") and cur:
            out["/" + line[len("site/"):-len("index.html")]] = cur  # newest first, so the earliest add wins
    return out


def changelog_entries(http) -> list[dict]:
    """Entries of the live changelog: date, tag, title (h2) and text."""
    page = L.events.get_live(http, f"{SITE}/changelog/")
    out = []
    for blk in re.findall(r'<div class="changelog-entry">(.*?)\n      </div>\s*(?=<div class="changelog-entry">|</)', page, re.S):
        d = re.search(r'changelog-date">\s*([A-Za-z]+ \d{1,2}, \d{4})', blk)
        h = re.search(r"<h2[^>]*>(.*?)</h2>", blk, re.S)
        p = re.search(r"<p[^>]*>(.*?)</p>", blk, re.S)
        if not (d and h and p):
            continue
        try:
            date = dt.datetime.strptime(d.group(1), "%B %d, %Y").date()
        except ValueError:
            continue
        out.append({"date": date, "title": L.events.strip_tags(h.group(1)), "text": L.events.strip_tags(p.group(1))})
    return out


def ledger_videos(root=None) -> list[dict]:
    """Purplelink how-to videos recorded by the daily how-to pipeline (video/howto/ledger.json): the long cut only."""
    p = (root or paths.repo_root()) / "video" / "howto" / "ledger.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data if isinstance(e, dict) and e.get("long_id") and e.get("date")]


# ---------------------------------------------------------------- gather
def gather(http, today: dt.date, cfg: dict, stats: dict | None = None, added: dict | None = None,
           ledger: list | None = None, notes: list | None = None) -> list[Candidate]:
    """All candidates for `today`. Failures of one source are noted and do not stop the others."""
    notes = notes if notes is not None else []
    days = cfg["recent_days"]
    cands: list[Candidate] = []

    # releases: apps whose live version has a changelog entry dated within the window
    try:
        entries = changelog_entries(http)
    except L.Skip as e:
        entries = []
        notes.append(f"changelog: {e}")
    for app in L.events.PRODUCTS:
        try:
            facts = L.events.release_facts(http, app)
        except L.Skip as e:
            notes.append(f"{app}: {e}")
            continue
        want = f"{facts['name']} {facts['version']}"
        ent = next((e for e in entries if e["title"] == want), None)
        if not ent or not 0 <= (today - ent["date"]).days <= days:
            continue
        cands.append(Candidate(id=f"release:{app}:{facts['version']}", kind="release", url=facts["url"],
                               published=ent["date"], title_hint=want, facts=_release(facts)))

    # guides, blog posts, tools: first added within the window (publish date), checked against the live sitemap
    try:
        live = sitemap_urls(http)
    except L.Skip as e:
        live = {}
        notes.append(f"sitemap: {e}")
    added = added if added is not None else git_added_dates()
    for path, lastmod in sorted(live.items()):
        m = PAGE_RE.match(path)
        pub = added.get(path)
        if pub is None:
            continue
        if 0 <= (today - pub).days <= days and path not in cfg["exclude_paths"]:
            kind = KIND_OF_DIR[m.group(1)]
            cands.append(Candidate(id=f"{kind}:{m.group(2)}", kind=kind, url=SITE + path, published=pub,
                                   title_hint=m.group(2).replace("-", " ")))

    # videos from the how-to ledger (and the public feed when it answers; it often does not)
    for e in (ledger if ledger is not None else ledger_videos()):
        try:
            d = dt.date.fromisoformat(e["date"])
        except ValueError:
            continue
        if 0 <= (today - d).days <= days:
            cands.append(Candidate(id=f"video:{e['long_id']}", kind="video",
                                   url=f"https://www.youtube.com/watch?v={e['long_id']}", published=d,
                                   title_hint=e.get("title", ""), meta={"video_id": e["long_id"]}))

    # evergreen: the most-visited guides, tools and blog posts over 90 days, else the sitemap in a fixed order
    fresh_ids = {c.id for c in cands}
    for c in evergreen(live, stats, cfg, notes):
        if c.id not in fresh_ids:
            cands.append(c)
    return cands


def evergreen(live: dict, stats: dict | None, cfg: dict, notes: list) -> list[Candidate]:
    out: list[Candidate] = []
    ranked: list[tuple[str, int]] = []
    if stats and stats.get("topPaths"):
        ranked = [(r["key"], int(r["count"])) for r in stats["topPaths"] if isinstance(r, dict) and "key" in r]
    else:
        notes.append("no traffic stats: evergreen list falls back to the sitemap order")
        ranked = [(p, 0) for p in sorted(live)]
    for path, n in ranked:
        m = PAGE_RE.match(path)
        if not m or path in cfg["exclude_paths"] or (live and path not in live):
            continue
        kind = KIND_OF_DIR[m.group(1)]
        out.append(Candidate(id=f"evergreen:{kind}:{m.group(2)}", kind="evergreen", url=SITE + path, traffic=n,
                             page_kind=kind, title_hint=m.group(2).replace("-", " ")))
        if len(out) >= cfg["evergreen_top_n"]:
            break
    return out


def fetch_stats(http, days: int = 90) -> dict | None:
    """Owner stats, sent as a header only (never in a URL, never printed). None when unavailable."""
    tok = None
    try:
        for line in paths.traffic_env().read_text(encoding="utf-8").splitlines():
            if line.startswith("PURPLELINK_STATS_TOKEN="):
                tok = line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        return None
    if not tok:
        return None
    r = http.request("GET", f"{SITE}/.netlify/functions/stats?days={days}", headers={"x-stats-token": tok})
    data = r.json() if r.status == 200 else None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------- facts
def _release(f: dict) -> dict:
    return {"title": f["title"], "description": "", "notes": f["notes"], "name": f["name"], "version": f["version"],
            "price": f.get("price", ""), "url": f["url"], "og_image": f.get("og_image", ""), "image_alt": ""}


def page_facts(http, url: str) -> dict:
    """Title, meta description and card image of a live page. Raises Skip when it is not a 200 page with a title."""
    page = L.events.get_live(http, url)
    title = L.plain(L.events.meta(page, "og:title") or L.events.h1(page))
    title = re.sub(r"\s*[|–-]\s*Purplelink( LLC)?\s*$", "", title).strip()
    if not title:
        raise L.Skip(f"{url} has no title")
    return {"title": title, "description": L.plain(L.events.meta(page, "description") or L.events.meta(page, "og:description")),
            "notes": "", "url": url, "og_image": L.events.meta(page, "og:image"),
            "image_alt": L.plain(L.events.meta(page, "og:image:alt") or L.events.meta(page, "twitter:image:alt"))}


def video_page_facts(http, video_id: str) -> dict:
    """Title from YouTube's public oEmbed (it answers only for a public video)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    f = L.events.video_facts(http, video_id, entry={})
    return {"title": f["title"], "description": "", "notes": "", "url": url, "og_image": "", "image_alt": ""}


def load_facts(http, c: Candidate) -> dict:
    """Fill c.facts from the live source (idempotent)."""
    if c.facts is None:
        c.facts = video_page_facts(http, c.meta["video_id"]) if c.kind == "video" else page_facts(http, c.url)
    return c.facts


def source_text(facts: dict) -> str:
    """Everything the post may draw on. The vetting gate compares the post against this."""
    return " ".join(str(facts.get(k) or "") for k in ("title", "description", "notes", "name", "version", "price"))
