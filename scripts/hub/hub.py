#!/usr/bin/env python3
"""Marketing hub, phase 0: where has each asset been marketed. See docs/growth-briefs/marketing-hub-2026-10-23.md.

Read-only over every source. `import` rebuilds one private SQLite file (~/.purplelink/hub/hub.sqlite) from scratch, so
it can be deleted at any time with nothing lost. Nothing here posts, sends or edits a source. Stdlib only.

  hub.py import                 rebuild the database from the sources below
  hub.py where ASSET            every placement of an asset (id like moderntex, guide:latexdiff-online, or a name)
  hub.py grid [--all]           assets by channel: placement counts (products only unless --all)
  hub.py gaps [--days 30]       live assets with no placement in the last N days
  hub.py unmatched              placements no asset could be matched to (fix by hand or ignore)
  hub.py status                 one line, for the daily update

Phase 1 (results):
  hub.py import --fetch         also read the first-touch funnel from the stats function (7 windows, one GET each)
  hub.py channels [PRODUCT]     product x channel over 45 days: placements, visits, trials, orders, verdict
  hub.py followups              outreach emails due a follow-up (day 4) and those past 28 days (no-response)
  hub.py check-listings [--if-older DAYS]   fetch live listing pages; record price and version seen (facts.json)
  hub.py export DIR             aggregate JSON arrays for the dashboard's Marketing tab (no contacts, no email targets)

Sources: approval queue items (pending, approved, done; outward kinds only), the social queue (posted and scheduled
company posts, one placement per platform), Outreach/OUTREACH-LOG.md tables, video/howto/ledger.json, and the MacUpdate
readings in the traffic dashboard history. Assets come from site/llms.txt and site/sitemap.xml.

Contacts are not copied: an outreach row keeps a `contact_ref` (file and line) and email addresses in notes are masked.

Results are honest about what they are. The stats function counts first-touch visits by source and page over a window,
not by link, so a placement's visits are every visit from its source to its page in the window since it went live
("path-shared" when another placement shares source, page and window). A channel is judged on visits, not on how many
placements it got: pause candidate only at 8+ placements, 150+ visits, 45 days and zero trials (design doc, section 3).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOME = Path.home()
SITE_HOST = "purplelink.llc"


def env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name) or default)


def paths() -> dict:
    # Sources default to this checkout's data; every one can be redirected (tests do).
    repo = env_path("PURPLELINK_REPO", REPO)
    return {
        "db": env_path("PURPLELINK_HUB", HOME / ".purplelink" / "hub") / "hub.sqlite",
        "queue": env_path("PURPLELINK_QUEUE", HOME / ".purplelink" / "queue"),
        "social": env_path("PURPLELINK_SOCIAL_QUEUE", HOME / ".purplelink" / "social" / "queue"),
        "traffic": env_path("PURPLELINK_TRAFFIC_HISTORY", HOME / ".purplelink" / "traffic" / "history.json"),
        "outreach": repo / "Outreach" / "OUTREACH-LOG.md",
        "llms": repo / "site" / "llms.txt",
        "sitemap": repo / "site" / "sitemap.xml",
        "videos": repo / "video" / "howto" / "ledger.json",
        "funnel": env_path("PURPLELINK_HUB", HOME / ".purplelink" / "hub") / "funnel.json",
        "facts": env_path("PURPLELINK_HUB", HOME / ".purplelink" / "hub") / "facts.json",
        "social_metrics": env_path("PURPLELINK_SOCIAL_METRICS", HOME / ".purplelink" / "social" / "metrics.json"),
        "traffic_env": env_path("PURPLELINK_TRAFFIC_ENV", HOME / ".config" / "purplelink" / "traffic.env"),
    }


SCHEMA = """
CREATE TABLE assets (id TEXT PRIMARY KEY, kind TEXT, name TEXT, product TEXT, url TEXT, version TEXT, price TEXT);
CREATE TABLE placements (
  id TEXT PRIMARY KEY, source TEXT, channel TEXT, kind TEXT, target TEXT, status TEXT, date TEXT,
  url TEXT, landing_url TEXT, utm TEXT, approval TEXT, contact_ref TEXT, notes TEXT,
  follow_up_due TEXT, facts_seen TEXT, check_state TEXT);
CREATE TABLE channel_stats (product TEXT, channel TEXT, placements INTEGER, visits INTEGER, trials INTEGER,
  orders INTEGER, heard INTEGER, rate_lo REAL, rate_hi REAL, verdict TEXT, why TEXT, PRIMARY KEY (product, channel));
CREATE TABLE heard (product TEXT, answer TEXT, channel TEXT, orders INTEGER, PRIMARY KEY (product, answer));
CREATE TABLE placement_assets (placement_id TEXT, asset_id TEXT, PRIMARY KEY (placement_id, asset_id));
CREATE TABLE results (placement_id TEXT, date TEXT, metric TEXT, value REAL, source TEXT, confidence TEXT);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
URL_RE = re.compile(r"https?://[^\s)|>\]\"'`,]+")
DATE_RE = re.compile(r"\d{4}-\d\d-\d\d")

# Keyword -> channel, first match wins. Used for queue targets and outreach section headings.
CHANNELS = [
    ("tex.stackexchange", "texse"), ("tex stackexchange", "texse"), ("tex.se", "texse"),
    ("reddit", "reddit"), ("r/", "reddit"), ("libguide", "libguide"), ("alternativeto", "alternativeto"),
    ("macupdate", "macupdate"), ("awesome-mac", "github"), ("github", "github"), ("product hunt", "producthunt"),
    ("hacker news", "hn"), ("linkedin", "linkedin"), ("bluesky", "bluesky"), ("threads", "threads"),
    ("mastodon", "mastodon"), ("youtube", "youtube"), ("tiktok", "tiktok"), ("newsletter", "newsletter"),
    ("syndication", "syndication"), ("press", "press"), ("photo", "photo-pitch"), ("directory", "directory"),
    ("directories", "directory"), ("listing", "directory"), ("setapp", "marketplace"), ("email", "email"),
    ("batch", "email"), ("outreach", "email"), ("pitch", "email"), ("customer note", "email"),
]
OUTWARD = {"post", "email", "listing", "submission", "spend"}
QUEUE_STATUS = {"pending": "queued", "approved": "approved", "done": "live"}
LOG_STATUS = {"sent": "live", "posted": "live", "replied": "replied", "included": "live", "listed": "live",
              "live": "live", "declined": "rejected-by-target", "rejected": "rejected-by-target",
              "no-response": "no-response", "skipped": "skipped", "submitted": "live", "merged": "live",
              "open": "live", "pending": "live", "removed": "removed"}


def channel_of(text: str, default: str = "other") -> str:
    low = text.lower()
    for key, ch in CHANNELS:
        if key in low:
            return ch
    return default


def mask(text: str) -> str:
    return EMAIL_RE.sub("[email]", text or "").strip()


def site_path(url: str) -> str | None:
    m = re.match(r"https?://(?:www\.)?purplelink\.llc(/[^?#]*)?", url or "")
    if not m:
        return None
    p = m.group(1) or "/"
    return p if p.endswith("/") else p + "/"


def vtuple(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


# --- assets -------------------------------------------------------------------------------------------------------

def asset_id_for_path(path: str) -> tuple[str, str] | None:
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return None
    if parts[0] in ("guides", "tools", "blog") and len(parts) >= 2:
        return f"{parts[0].rstrip('s')}:{parts[1]}", parts[0].rstrip("s")
    if parts[0] in ("guides", "tools", "blog"):
        return None
    return parts[0], "page"


def load_assets(p: dict) -> dict:
    """id -> {kind, name, product, url, names}. Products come from llms.txt headings; pages from llms.txt and sitemap."""
    assets: dict = {}
    text = p["llms"].read_text() if p["llms"].exists() else ""
    # A product's version and price lines can come before its first link, so they wait in `pending` until it is known.
    section, product, cur, pending = "", None, None, {}
    for line in text.splitlines():
        if line.startswith("## "):
            section, product, cur, pending = line[3:].lower(), None, None, {}
            continue
        if section.startswith("products") and "development" not in section and line.startswith("### "):
            product, cur, pending = re.sub(r"\s*\(.*$", "", line[4:]).strip(), None, {}
            continue
        if product or (cur and cur in assets):
            tgt = assets[cur] if cur and cur in assets and not product else pending
            if line.startswith("- **Status:**"):
                # The newest version the status line names (BatteryMeter's reads "Version 1.2.0 added ...; 1.2.1 is ...").
                vs = re.findall(r"(?<![\d.])(\d+\.\d+(?:\.\d+)?)(?![\d.]*\d)", line.split("http")[0])
                if vs:
                    tgt["version"] = max(vs, key=vtuple)
            pr = re.search(r"\*\*Pricing:\*\*.*?\$(\d+(?:\.\d\d)?)", line)
            # "Free. Optional Vitae Plus $2.99" is a free app with a paid add-on: there is no app price to check.
            if pr and re.match(r"- \*\*Pricing:\*\* Free[.,]? (?!\d+-day)", line):
                pr = None
            if pr and not tgt.get("price"):
                tgt["price"] = pr.group(1)
        if product:
            for u in URL_RE.findall(line):
                path = site_path(u)
                if path and path.count("/") == 2 and path not in ("/tools/", "/guides/", "/blog/"):
                    aid = path.strip("/")
                    assets.setdefault(aid, {"kind": "product", "name": product, "product": aid,
                                            "url": f"https://{SITE_HOST}{path}"})
                    for k, v in pending.items():
                        assets[aid].setdefault(k, v)
                    product, cur, pending = None, aid, {}
                    break
            continue
        m = re.match(r"- (.+?): (https://purplelink\.llc/\S+)", line)
        if m and section.split(" ")[0] in ("tools", "guides", "blog"):
            path = site_path(m.group(2))
            got = asset_id_for_path(path) if path else None
            if got and got[0] not in assets:
                assets[got[0]] = {"kind": got[1], "name": m.group(1).strip(), "product": None, "url": m.group(2).rstrip("/") + "/"}
    if p["sitemap"].exists():
        for u in re.findall(r"<loc>([^<]+)</loc>", p["sitemap"].read_text()):
            path = site_path(u)
            got = asset_id_for_path(path) if path else None
            if got and got[1] in ("guide", "tool", "blog") and got[0] not in assets:
                assets[got[0]] = {"kind": got[1], "name": got[0].split(":", 1)[1].replace("-", " "), "product": None, "url": u}
    # Photo licensing pitches market the stock photography line, which has no page of its own.
    assets["photo-licensing"] = {"kind": "line", "name": "Photo licensing", "product": None, "url": ""}
    for a in assets.values():
        a["names"] = [a["name"].lower()] if a["kind"] in ("product", "tool") else []
    return assets


def add_linked_assets(text: str, assets: dict) -> None:
    """A placement can link a guide, tool or blog post newer than the local sitemap; add it rather than lose the match."""
    for u in URL_RE.findall(text or ""):
        path = site_path(u)
        got = asset_id_for_path(path) if path else None
        if got and got[1] in ("guide", "tool", "blog") and got[0] not in assets:
            assets[got[0]] = {"kind": got[1], "name": got[0].split(":", 1)[1].replace("-", " "), "product": None,
                              "url": f"https://{SITE_HOST}{path}", "names": []}


def match_assets(text: str, assets: dict) -> list:
    found = []
    for u in URL_RE.findall(text or ""):
        path = site_path(u)
        if not path:
            continue
        got = asset_id_for_path(path)
        if got and got[0] in assets:
            found.append(got[0])
    low = (text or "").lower()
    for aid, a in assets.items():
        for n in a["names"]:
            if len(n) >= (4 if a["kind"] == "product" else 8) and re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", low):
                found.append(aid)
    return list(dict.fromkeys(found))


# --- sources ------------------------------------------------------------------------------------------------------

def parse_front(text: str) -> tuple[dict, str]:
    """Front matter where each value is JSON (social queue) or the approval queue's simple scalars."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm = {}
    for line in text[3:end].strip("\n").splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        try:
            fm[k.strip()] = json.loads(v)
        except ValueError:
            fm[k.strip()] = v.strip("\"'")
    return fm, text[end + 4:]


def section(body: str, name: str) -> str:
    m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    return m.group(1).strip() if m else ""


def from_queue(p: dict) -> list:
    out = []
    for folder, status in QUEUE_STATUS.items():
        d = p["queue"] / folder
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            fm, body = parse_front(f.read_text(errors="replace"))
            if fm.get("kind") not in OUTWARD:
                continue
            target = str(fm.get("target", ""))
            result = section(body, "Result")
            res_urls = [u for u in URL_RE.findall(result) if not site_path(u)]
            date = (DATE_RE.findall(result) or [str(fm.get("decided") or fm.get("created") or "")[:10]])[-1]
            out.append({
                "id": f"queue:{fm.get('id', f.stem)}", "source": "approval-queue",
                "channel": channel_of(target + " " + str(fm.get("kind")), "email" if fm.get("kind") == "email" else "other"),
                "kind": fm.get("kind"), "target": mask(target)[:200], "status": status, "date": date[:10],
                "url": res_urls[0] if res_urls else "", "landing_url": "", "utm": "",
                "approval": fm.get("id", ""), "contact_ref": "", "notes": mask(result)[:300],
                "_text": " ".join([target, section(body, "Ask"), section(body, "Draft")]),
            })
    return out


def from_social(p: dict) -> list:
    out = []
    d = p["social"]
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.md")):
        fm, body = parse_front(f.read_text(errors="replace"))
        iid = str(fm.get("id") or f.stem)
        if re.search(r"dryrun|dry-run", iid):
            continue
        results = fm.get("results") if isinstance(fm.get("results"), dict) else {}
        approval = str(fm.get("approved_by") or "")
        link = str(fm.get("link") or "")
        for plat in fm.get("platforms") or []:
            r = results.get(plat) or {}
            # Only a platform's own result says it went out; the item's status covers all its platforms.
            if r.get("status"):
                status = {"posted": "live", "failed": "failed", "refused": "failed"}.get(r["status"], r["status"])
            elif fm.get("status") in ("cancelled", "canceled"):
                status = "cancelled"
            else:
                status = "approved" if approval else "drafted"
            when = str(r.get("posted_at") or fm.get("scheduled_at") or fm.get("created") or "")[:10]
            campaign = str(fm.get("campaign") or "")
            out.append({
                "id": f"social:{iid}:{plat}", "source": "social-queue", "channel": plat, "kind": "post",
                "target": f"Purplelink {plat}", "status": status, "date": when, "url": r.get("url") or "",
                "landing_url": link, "utm": f"utm_source={plat}&utm_medium=social&utm_campaign={campaign}" if campaign else "",
                "approval": "standing:2026-10-18" if "standing" in approval else approval, "contact_ref": "",
                "notes": (r.get("error") or r.get("detail") or "")[:200], "_text": link + " " + body,
            })
    return out


def from_outreach(p: dict) -> list:
    out = []
    f = p["outreach"]
    if not f.exists():
        return out
    heading, header = "", None
    for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
        if line.startswith("#"):
            heading, header = line.lstrip("#").strip(), None
            continue
        if not line.startswith("|"):
            header = None if not line.strip() else header
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        row = dict(zip(header, cells))
        joined = " | ".join(cells)
        date_cell = next((row[k] for k in header if "date" in k), "")
        date = (DATE_RE.findall(date_cell) or [""])[0] or (DATE_RE.findall(heading) or [""])[0]
        status_cell = next((row[k] for k in header if k.startswith("status")), "")
        status = LOG_STATUS.get(status_cell.lower().split(" ")[0].strip("*`,."), "") if status_cell else ""
        if not status:
            status = "live" if date else "planned"
        target_key = next((k for k in header if k in ("target", "subreddit", "question url", "directory", "site",
                                                       "outlet", "organization", "venue", "where")), header[1] if len(header) > 1 else header[0])
        urls = URL_RE.findall(joined)
        ext = [u for u in urls if not site_path(u)]
        landing = next((u for u in urls if site_path(u)), "")
        out.append({
            "id": f"outreach:{n}", "source": "outreach-log", "channel": channel_of(heading + " " + row.get(target_key, ""), "other"),
            "kind": "reply" if "stackexchange" in heading.lower() else "", "target": mask(row.get(target_key, ""))[:200],
            "status": status, "date": date, "url": ext[0] if ext else "", "landing_url": landing, "utm": "",
            "approval": (re.findall(r"q-\d{8}-[\w-]+", joined) or [""])[0], "contact_ref": f"OUTREACH-LOG.md:{n}",
            "notes": mask(row.get("notes", ""))[:300], "_text": heading + " " + joined,
            "_social": (re.findall(r"^(?:linkedin|bluesky|threads|mastodon|x): (\S+)$", row.get(target_key, "")) or [""])[0],
            "_assets": ["photo-licensing"] if channel_of(heading, "") == "photo-pitch" else [],
        })
    return out


def from_videos(p: dict) -> list:
    out = []
    if not p["videos"].exists():
        return out
    for v in json.loads(p["videos"].read_text()):
        for fld, label in (("long_id", "youtube"), ("short_id", "youtube-short")):
            vid = v.get(fld)
            if not vid:
                continue
            out.append({
                "id": f"video:{vid}", "source": "video-ledger", "channel": "youtube", "kind": "video",
                "target": f"Purplelink YouTube ({label})", "status": "live", "date": v.get("date", ""),
                "url": f"https://www.youtube.com/watch?v={vid}" if fld == "long_id" else f"https://www.youtube.com/shorts/{vid}",
                "landing_url": "", "utm": f"utm_content={v.get('link_utm_content', '')}" if v.get("link_utm_content") else "",
                "approval": "standing:daily-howto", "contact_ref": "", "notes": v.get("title", "")[:200],
                "_text": str(v.get("app", "")), "_assets": [str(v.get("app", ""))],
            })
    return out


def from_macupdate(p: dict) -> tuple[list, list]:
    out, results = [], []
    if not p["traffic"].exists():
        return out, results
    mu = json.loads(p["traffic"].read_text()).get("macupdate") or {}
    for product, entry in mu.items():
        snaps = entry.get("snapshots") or {}
        pid = f"macupdate:{product}"
        last = snaps[max(snaps)] if snaps else {}
        out.append({
            "id": pid, "source": "traffic-history", "channel": "macupdate", "kind": "listing",
            "target": "MacUpdate", "status": "live", "date": min(snaps) if snaps else "", "url": entry.get("url", ""),
            "landing_url": "", "utm": "", "approval": "", "contact_ref": "",
            "notes": f"listing shows version {last.get('version')} at ${last.get('price')}" if last else "",
            "_text": product, "_assets": [product],
            "_facts": {"versions": [str(last["version"])] if last.get("version") else [],
                       "prices": [f"{float(last['price']):.2f}"] if last.get("price") is not None else [],
                       "checked": max(snaps)} if last else None,
        })
        for day, s in sorted(snaps.items()):
            if "downloads" in s:
                results.append((pid, day, "downloads-total", s["downloads"], "macupdate", "exact"))
    return out, results


# --- results (phase 1) --------------------------------------------------------------------------------------------

FUNNEL_WINDOWS = (7, 14, 30, 45, 60, 90, 120)  # the stats function caps a window at 120 days
STATS_URL = f"https://{SITE_HOST}/.netlify/functions/stats"
STOP_PLACEMENTS, STOP_VISITS, STOP_DAYS, EARLY = 8, 150, 45, 5
FOLLOW_UP_DAY, FOLLOW_UP_LAST, NO_RESPONSE_DAY = 4, 14, 28
# Photo pitches are left out: Ben paused them on 2026-10-19, so the hub must not prompt a follow-up.
OUTREACH_CHANNELS = {"email", "libguide", "press", "newsletter"}
LISTING_CHANNELS = {"directory", "macupdate", "alternativeto", "marketplace", "producthunt"}
# Where a placement's URL and target may appear in the export: public posts and listings only, never a person.
PUBLIC_CHANNELS = {"directory", "macupdate", "alternativeto", "marketplace", "producthunt", "github", "texse",
                   "reddit", "youtube", "linkedin", "bluesky", "threads", "mastodon", "x", "syndication", "hn"}
# First-touch source keys (analytics.js `ft`, folded by stats.mjs) that belong to each channel. A key also matches its
# own "-suffix" family (youtube matches youtube-latex). Placement URL hosts and utm_source values are added per placement.
CHANNEL_KEYS = {
    "youtube": ("youtube",), "reddit": ("reddit", "www.reddit.com", "old.reddit.com"), "github": ("github", "github.com"),
    "texse": ("texse", "tex.stackexchange.com"), "linkedin": ("linkedin", "www.linkedin.com", "lnkd.in"),
    "bluesky": ("bluesky", "bsky.app"), "threads": ("threads", "www.threads.com", "www.threads.net"),
    "mastodon": ("mastodon", "mastodon.social"), "macupdate": ("macupdate", "www.macupdate.com"),
    "email": ("email",), "libguide": ("libguide",), "alternativeto": ("alternativeto", "alternativeto.net"),
    "producthunt": ("producthunt", "www.producthunt.com"), "newsletter": ("newsletter",), "x": ("x", "t.co"),
    "hn": ("news.ycombinator.com", "hn"), "press": ("press",),
}
# "How did you first hear about us?" codes (netlify/functions/checkout.mjs HEARD_OPTIONS) -> channel, where one fits.
HEARD_CHANNEL = {"reddit": "reddit", "directory": "directory", "email": "email", "library": "libguide"}


def stats_token(p: dict) -> str:
    f = p["traffic_env"]
    if f.exists():
        for line in f.read_text().splitlines():
            if line.startswith("PURPLELINK_STATS_TOKEN="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def fetch_funnel(p: dict, get=None) -> dict:
    """One GET per window; the token goes in a header, never the URL. Writes funnel.json; returns what it wrote."""
    tok = stats_token(p)
    if not tok:
        raise SystemExit(f"no PURPLELINK_STATS_TOKEN in {p['traffic_env']}")
    if get is None:
        import urllib.request

        def get(url, headers):
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
    out = {"asOf": dt.date.today().isoformat(), "windows": {}}
    for w in FUNNEL_WINDOWS:
        data = get(f"{STATS_URL}?days={w}", {"x-stats-token": tok, "User-Agent": "purplelink-marketing-hub"})
        out["windows"][str(w)] = data.get("funnelByChannel") or {}
    p["funnel"].parent.mkdir(parents=True, exist_ok=True)
    p["funnel"].write_text(json.dumps(out, indent=1))
    return out


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def host_key(url: str) -> list:
    m = re.match(r"https?://([^/?#]+)", url or "")
    if not m or site_path(url):
        return []
    h = m.group(1).lower()
    return [h, h.removeprefix("www."), h.removeprefix("www.").split(".")[0]]


def source_keys(pl: dict) -> set:
    keys = set(CHANNEL_KEYS.get(pl["channel"], (pl["channel"],)))
    keys.update(host_key(pl.get("url", "")))
    for u in (pl.get("landing_url", ""), pl.get("utm", "")):
        m = re.search(r"utm_source=([\w.\-]+)", u or "")
        if m:
            keys.add(m.group(1).lower())
    return keys


def key_matches(funnel_key: str, keys: set) -> bool:
    k = funnel_key.lower()
    return k in keys or any(k.startswith(x + "-") for x in keys)


def window_for(date: str, today: dt.date) -> int | None:
    try:
        age = (today - dt.date.fromisoformat(date)).days + 1
    except ValueError:
        return None
    return next((w for w in FUNNEL_WINDOWS if w >= age), None)


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple:
    """Exact binomial interval for k successes in n, by bisection on the binomial tail (stdlib only)."""
    if n <= 0:
        return (0.0, 1.0)

    def tail_ge(p, k):  # P(X >= k)
        if k <= 0:
            return 1.0
        if p <= 0:
            return 0.0
        if p >= 1:
            return 1.0
        lp, lq = math.log(p), math.log1p(-p)
        return min(1.0, sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
                            for i in range(k, n + 1)))

    def solve(f, target):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda q: tail_ge(q, k), alpha / 2)
    # Upper bound: P(X <= k) = alpha/2, i.e. P(X >= k+1) = 1 - alpha/2 (an increasing function of q, as solve needs).
    upper = 1.0 if k == n else solve(lambda q: tail_ge(q, k + 1), 1 - alpha / 2)
    return (lower, upper)


def paths_for(pl: dict, ids: list, assets: dict) -> list:
    out = []
    if pl.get("landing_url"):
        out.append(site_path(pl["landing_url"]))
    for a in ids:
        u = assets.get(a, {}).get("url")
        if u and site_path(u):
            out.append(site_path(u))
    return [x for x in dict.fromkeys(out) if x]


def orders_from_ledger(p: dict) -> list:
    led = (load_json(p["traffic"], {}) or {}).get("ledger") or {}
    out = []
    for o in led.values():
        if o.get("kind") != "order" or o.get("refunded") or o.get("disputed"):
            continue
        first = ((o.get("attr") or {}).get("first") or {}).get("s") or ""
        day = dt.datetime.fromtimestamp(float(o.get("ts") or 0), dt.timezone.utc).date().isoformat()
        out.append({"product": o.get("product") or "", "first": first, "heard": o.get("heard") or "", "date": day})
    return out


def placement_results(pls: list, links: dict, assets: dict, funnel: dict, orders: list, metrics: dict,
                      today: dt.date) -> list:
    """Rows for the results table. Visits and trials come from the funnel window that covers the time since the
    placement went live; orders from the ledger's first-touch source after that day; engagement from social metrics."""
    rows = []
    wins = funnel.get("windows") or {}
    asof = funnel.get("asOf") or today.isoformat()
    live = [pl for pl in pls if pl["status"] in ("live", "replied") and pl.get("date")]
    shared: dict = {}
    plan = []
    for pl in live:
        w = window_for(pl["date"], today)
        ids = links.get(pl["id"], [])
        products = [a for a in ids if assets.get(a, {}).get("kind") == "product"]
        keys = source_keys(pl)
        paths = paths_for(pl, ids, assets)
        plan.append((pl, w, keys, paths, products))
        if w:
            for k in keys:
                for path in paths:
                    shared[(w, k, path)] = shared.get((w, k, path), 0) + 1
    for pl, w, keys, paths, products in plan:
        if w and str(w) in wins:
            fun = wins[str(w)]
            visits = trials = checkouts = 0
            n_share = 1
            for fk, v in fun.items():
                if not key_matches(fk, keys):
                    continue
                pbp = v.get("pageviewsByPath") or {}
                visits += sum(pbp.get(path, 0) for path in paths)
                trials += sum((v.get("trial") or {}).get(prod, 0) for prod in products)
                checkouts += sum((v.get("checkout") or {}).get(prod, 0) for prod in products)
            n_share = max([shared.get((w, k, path), 1) for k in keys for path in paths] or [1])
            conf = f"path-shared:{n_share}" if n_share > 1 else "path"
            for metric, val in (("first-touch-visits", visits), ("trials", trials), ("checkout-clicks", checkouts)):
                if metric != "first-touch-visits" and not products:
                    continue
                rows.append((pl["id"], asof, metric, val, f"funnel:{w}d", conf))
        if products:
            n = sum(1 for o in orders if o["product"] in products and o["date"] >= pl["date"]
                    and o["first"] and key_matches(o["first"], keys))
            rows.append((pl["id"], asof, "orders", n, "ledger", "first-touch"))
    for item, post in (metrics.get("posts") or {}).items():
        for plat, v in (post.get("platforms") or {}).items():
            snaps = v.get("snapshots") or {}
            if not snaps:
                continue
            day = max(snaps)
            for metric, val in snaps[day].items():
                if val is not None:
                    rows.append((f"social:{item}:{plat}", day, metric, val, "social-metrics", "exact"))
    return rows


def follow_up(pl: dict, today: dt.date) -> tuple:
    """(status, follow_up_due) for one-to-one outreach: one follow-up from day 4 to day 14, no-response after day 28.
    Past day 14 the follow-up window has closed, so nothing is listed as due."""
    if (pl["channel"] not in OUTREACH_CHANNELS or pl["status"] != "live" or not pl.get("date")
            or "photo-licensing" in pl.get("_assets", [])):
        return pl["status"], ""
    try:
        age = (today - dt.date.fromisoformat(pl["date"])).days
    except ValueError:
        return pl["status"], ""
    if re.search(r"follow-?up sent|followed up|replied|reply", (pl.get("notes") or "").lower()):
        return pl["status"], ""
    if age > NO_RESPONSE_DAY:
        return "no-response", ""
    if age > FOLLOW_UP_LAST:
        return pl["status"], ""
    return pl["status"], (dt.date.fromisoformat(pl["date"]) + dt.timedelta(days=FOLLOW_UP_DAY)).isoformat()


def listing_check(seen: dict, asset: dict) -> str:
    """ok, stale (price or version differs from site/llms.txt) or manual (nothing readable). Never stale on a failure."""
    if not seen or seen.get("error") or not (seen.get("versions") or seen.get("prices")):
        return "manual"
    cur_v, cur_p = asset.get("version"), asset.get("price")
    if cur_v and seen.get("versions") and cur_v not in seen["versions"]:
        return "stale"
    if cur_p and seen.get("prices") and not any(abs(float(x) - float(cur_p)) < 0.005 for x in seen["prices"]):
        return "stale"
    return "ok"


def page_text(html: str) -> str:
    """Visible text of a page, without script and style contents (the stdlib parser handles every end-tag form)."""
    from html.parser import HTMLParser

    class Text(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts, self.skip = [], 0

        def handle_starttag(self, tag, attrs):
            self.skip += tag in ("script", "style")

        def handle_endtag(self, tag):
            if tag in ("script", "style") and self.skip:
                self.skip -= 1

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)
    t = Text()
    t.feed(html)
    t.close()
    return re.sub(r"\s+", " ", " ".join(t.parts))


def read_facts(html: str, asset_name: str) -> dict:
    text = page_text(html)
    # Directory pages list many apps, so only the text just around our app's name counts.
    low, name = text.lower(), (asset_name or "").lower()
    near = " ".join(text[max(0, m.start() - 150):m.start() + 500] for m in re.finditer(re.escape(name), low)) if name else ""
    versions = sorted(set(re.findall(r"[Vv]ersion:?\s*v?(\d+\.\d+(?:\.\d+)?)", near)), key=vtuple)
    prices = sorted(set(re.findall(r"\$\s?(\d{1,3}\.\d\d)\b", near)))
    import hashlib
    return {"versions": versions, "prices": prices, "hash": hashlib.sha256(text.encode()).hexdigest()[:16],
            "mentions": bool(near)}


def check_listings(p: dict, if_older: int = 0, get=None) -> dict:
    """Fetch each live listing once, sequentially, and record what it shows in facts.json (keyed by URL)."""
    con = connect(p)
    facts = load_json(p["facts"], {})
    rows = con.execute(
        "SELECT p.id, p.url, p.channel, a.name FROM placements p JOIN placement_assets x ON x.placement_id = p.id "
        "JOIN assets a ON a.id = x.asset_id WHERE a.kind = 'product' AND p.status IN ('live','replied') AND p.url != '' "
        f"AND p.channel IN ({','.join('?' * len(LISTING_CHANNELS))})", tuple(LISTING_CHANNELS)).fetchall()
    if get is None:
        import urllib.request

        def get(url):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                                                       "AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read(2_000_000).decode("utf-8", "replace")
    today = dt.date.today()
    done = skipped = 0
    for r in rows:
        url = r["url"]
        if not url.startswith("http") or r["channel"] == "macupdate":  # MacUpdate is read daily by the traffic job
            continue
        prev = facts.get(url) or {}
        if if_older and prev.get("checked") and (today - dt.date.fromisoformat(prev["checked"][:10])).days < if_older:
            skipped += 1
            continue
        try:
            seen = read_facts(get(url), r["name"])
        except Exception as exc:  # a blocked or broken page is a manual check, never "stale"
            seen = {"error": str(exc)[:120]}
        seen["checked"] = dt.datetime.now().astimezone().isoformat(timespec="minutes")
        facts[url] = seen
        done += 1
    p["facts"].parent.mkdir(parents=True, exist_ok=True)
    p["facts"].write_text(json.dumps(facts, indent=1))
    return {"checked": done, "skipped": skipped}


def channel_stats(pls: list, links: dict, assets: dict, funnel: dict, orders: list, today: dt.date) -> list:
    """Product x channel over the last 45 days, judged by the stop rule on visits, not on placement count."""
    since = (today - dt.timedelta(days=STOP_DAYS)).isoformat()
    fun = (funnel.get("windows") or {}).get(str(STOP_DAYS))
    groups: dict = {}
    for pl in pls:
        if pl["status"] not in ("live", "replied", "no-response") or not pl.get("date") or pl["date"] < since:
            continue
        for a in links.get(pl["id"], []):
            if assets.get(a, {}).get("kind") == "product":
                g = groups.setdefault((a, pl["channel"]), {"n": 0, "keys": set(CHANNEL_KEYS.get(pl["channel"], (pl["channel"],))), "first": pl["date"]})
                g["n"] += 1
                g["keys"] |= source_keys(pl)
                g["first"] = min(g["first"], pl["date"])
    rows = []
    for (prod, ch), g in sorted(groups.items()):
        path = site_path(assets[prod]["url"]) or f"/{prod}/"
        visits = trials = None
        if fun is not None:
            visits = trials = 0
            for fk, v in fun.items():
                if key_matches(fk, g["keys"]):
                    visits += sum(c for pth, c in (v.get("pageviewsByPath") or {}).items() if pth.startswith(path))
                    trials += (v.get("trial") or {}).get(prod, 0)
        n_orders = sum(1 for o in orders if o["product"] == prod and o["date"] >= since and o["first"] and key_matches(o["first"], g["keys"]))
        n_heard = sum(1 for o in orders if o["product"] == prod and o["date"] >= since and HEARD_CHANNEL.get(o["heard"]) == ch)
        # Trials start on guide pages too, while visits count the product's own pages only. Where trials outnumber
        # visits there is no honest per-visit rate, so none is given.
        lo, hi = clopper_pearson(trials or 0, visits or 0) if visits and (trials or 0) < visits else (None, None)
        age = (today - dt.date.fromisoformat(g["first"])).days
        if visits is None:
            verdict, why = "no-data", "funnel not fetched (run import --fetch)"
        elif g["n"] < STOP_PLACEMENTS:
            verdict, why = "building", f"{g['n']} of {STOP_PLACEMENTS} placements"
        elif visits < STOP_VISITS:
            verdict, why = "unmeasured", f"{visits} of {STOP_VISITS} first-touch visits"
        elif trials == 0 and age >= STOP_DAYS - 1:
            verdict, why = "pause-candidate", f"0 trials in {visits} visits (rate under {hi:.1%}); needs Ben's yes"
        elif trials < EARLY:
            verdict, why = "early", f"{trials} trials, fewer than {EARLY}"
        else:
            verdict, why = "working", f"{trials} trials in {visits} visits"
        if visits and (trials or 0) >= visits > 0 and trials:
            why += f"; {trials} trials against {visits} product-page visits: trials also start on guides, and link checkers can trigger them, so no rate is given"
        rows.append((prod, ch, g["n"], visits, trials, n_orders, n_heard, lo, hi, verdict, why))
    return rows


# --- build --------------------------------------------------------------------------------------------------------

def build(p: dict) -> dict:
    assets = load_assets(p)
    mu, results = from_macupdate(p)
    social = from_social(p)
    social_ids = {pl["id"].split(":")[1] for pl in social}
    # The social engine also appends a row per platform to the outreach log; the social queue is the record.
    outreach = [pl for pl in from_outreach(p) if pl["_social"] not in social_ids or not pl["_social"]]
    # A send logged by hand with its queue id is the same placement as the queue item: keep one, with both references.
    queue = from_queue(p)
    by_qid = {pl["approval"]: pl for pl in queue if pl["approval"]}
    kept = []
    for pl in outreach:
        q = by_qid.get(pl["approval"])
        if q is None or q.get("_merged"):
            kept.append(pl)
            continue
        q["_merged"] = True
        q["url"] = q["url"] or pl["url"]
        q["contact_ref"] = pl["contact_ref"]
        q["date"] = pl["date"] or q["date"]
        q["_text"] += " " + pl["_text"]
    placements = queue + social + kept + from_videos(p) + mu
    for pl in placements:
        add_linked_assets(pl["_text"] + " " + pl["landing_url"], assets)
    today = dt.date.today()
    uniq, links, unmatched = [], {}, 0
    for pl in placements:
        if pl["id"] in links:
            continue
        ids = [a for a in pl.get("_assets", []) if a in assets] or match_assets(pl["_text"] + " " + pl["landing_url"], assets)
        links[pl["id"]] = ids
        unmatched += not ids
        uniq.append(pl)
    facts = load_json(p["facts"], {})
    for pl in uniq:
        pl["status"], pl["follow_up_due"] = follow_up(pl, today)
        seen = pl.get("_facts") or (facts.get(pl["url"]) if pl["channel"] in LISTING_CHANNELS else None)
        prods = [a for a in links[pl["id"]] if assets.get(a, {}).get("kind") == "product"]
        if seen and prods:
            pl["facts_seen"] = json.dumps(seen, sort_keys=True)
            pl["check_state"] = listing_check(seen, assets[prods[0]])
        elif pl["channel"] in LISTING_CHANNELS and pl["status"] in ("live", "replied") and prods:
            pl["check_state"] = "unchecked" if pl["url"].startswith("http") else "no-link"
    funnel = load_json(p["funnel"], {})
    orders = orders_from_ledger(p)
    results += placement_results(uniq, links, assets, funnel, orders, load_json(p["social_metrics"], {}), today)
    chan = channel_stats(uniq, links, assets, funnel, orders, today)
    heard: dict = {}
    for o in orders:
        if o["heard"]:
            k = (o["product"], o["heard"])
            heard[k] = heard.get(k, 0) + 1

    p["db"].parent.mkdir(parents=True, exist_ok=True)
    tmp = p["db"].with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO assets VALUES (?,?,?,?,?,?,?)",
                    [(k, a["kind"], a["name"], a["product"], a["url"], a.get("version"), a.get("price")) for k, a in assets.items()])
    cols = ["id", "source", "channel", "kind", "target", "status", "date", "url", "landing_url", "utm", "approval",
            "contact_ref", "notes", "follow_up_due", "facts_seen", "check_state"]
    for pl in uniq:
        con.execute(f"INSERT INTO placements VALUES ({','.join('?' * len(cols))})", [pl.get(c) or "" for c in cols])
        con.executemany("INSERT OR IGNORE INTO placement_assets VALUES (?,?)", [(pl["id"], a) for a in links[pl["id"]]])
    con.executemany("INSERT INTO results VALUES (?,?,?,?,?,?)", results)
    con.executemany(f"INSERT INTO channel_stats VALUES ({','.join('?' * 11)})", chan)
    con.executemany("INSERT INTO heard VALUES (?,?,?,?)", [(k[0], k[1], HEARD_CHANNEL.get(k[1], ""), n) for k, n in heard.items()])
    now = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    con.executemany("INSERT INTO meta VALUES (?,?)", [("built", now), ("unmatched", str(unmatched)),
                                                     ("funnel_asof", funnel.get("asOf", ""))])
    con.commit()
    con.close()
    os.replace(tmp, p["db"])
    by_source: dict = {}
    for pl in placements:
        by_source[pl["source"]] = by_source.get(pl["source"], 0) + 1
    return {"assets": len(assets), "placements": len(links), "unmatched": unmatched, "by_source": by_source}


def connect(p: dict) -> sqlite3.Connection:
    if not p["db"].exists():
        sys.exit("no hub database yet: run hub.py import")
    con = sqlite3.connect(p["db"])
    con.row_factory = sqlite3.Row
    return con


def resolve_asset(con, q: str) -> list:
    rows = con.execute("SELECT id FROM assets WHERE id = ?", (q,)).fetchall()
    if rows:
        return [rows[0]["id"]]
    like = f"%{q.lower()}%"
    return [r["id"] for r in con.execute(
        "SELECT id FROM assets WHERE lower(id) LIKE ? OR lower(name) LIKE ? ORDER BY kind != 'product', id", (like, like))]


# --- commands -----------------------------------------------------------------------------------------------------

def cmd_import(a, p):
    if a.fetch:
        f = fetch_funnel(p)
        print(f"funnel: {len(f['windows'])} windows as of {f['asOf']}")
    s = build(p)
    parts = ", ".join(f"{k} {v}" for k, v in sorted(s["by_source"].items()))
    print(f"hub: {s['assets']} assets, {s['placements']} placements ({parts}); {s['unmatched']} unmatched -> {p['db']}")


def cmd_where(a, p):
    con = connect(p)
    ids = resolve_asset(con, a.asset)
    if not ids:
        sys.exit(f"no asset matches {a.asset!r}")
    if len(ids) > 1 and not a.all:
        print(f"{len(ids)} assets match; showing {ids[0]} (others: {', '.join(ids[1:8])}{' ...' if len(ids) > 8 else ''})")
        ids = ids[:1]
    for aid in ids:
        rows = con.execute(
            "SELECT p.* FROM placements p JOIN placement_assets x ON x.placement_id = p.id WHERE x.asset_id = ? "
            "ORDER BY p.date DESC, p.channel", (aid,)).fetchall()
        print(f"\n{aid}: {len(rows)} placements")
        for r in rows:
            link = r["url"] or r["contact_ref"] or r["approval"]
            print(f"  {r['date'] or '----------':10}  {r['channel']:13} {r['status']:11} {r['target'][:44]:44}  {link}")


def cmd_grid(a, p):
    con = connect(p)
    where = "" if a.all else "WHERE a.kind = 'product'"
    rows = con.execute(
        f"SELECT a.id, p.channel, count(*) n FROM assets a "
        f"JOIN placement_assets x ON x.asset_id = a.id JOIN placements p ON p.id = x.placement_id {where} "
        f"GROUP BY a.id, p.channel").fetchall()
    grid: dict = {}
    for r in rows:
        grid.setdefault(r["id"], {})[r["channel"]] = r["n"]
    if not grid:
        print("no placements matched to assets")
        return
    chans = sorted({c for g in grid.values() for c in g}, key=lambda c: -sum(g.get(c, 0) for g in grid.values()))
    w = max(len(k) for k in grid) + 1
    print(" " * w + " ".join(f"{c[:8]:>8}" for c in chans) + "    total")
    for aid in sorted(grid, key=lambda k: -sum(grid[k].values())):
        print(f"{aid:{w}}" + " ".join(f"{grid[aid].get(c, '') or '.':>8}" for c in chans) + f"{sum(grid[aid].values()):>9}")


def cmd_gaps(a, p):
    con = connect(p)
    since = (dt.date.today() - dt.timedelta(days=a.days)).isoformat()
    kinds = ("product",) if not a.all else ("product", "guide", "tool", "blog")
    rows = con.execute(
        f"SELECT a.id, a.kind, max(p.date) last, count(p.id) n FROM assets a "
        f"LEFT JOIN placement_assets x ON x.asset_id = a.id LEFT JOIN placements p ON p.id = x.placement_id "
        f"AND p.status IN ('live','replied') WHERE a.kind IN ({','.join('?' * len(kinds))}) "
        f"GROUP BY a.id HAVING last IS NULL OR last < ? ORDER BY last", (*kinds, since)).fetchall()
    print(f"{len(rows)} assets with no live placement since {since}:")
    for r in rows:
        print(f"  {r['id']:44} {r['kind']:8} last {r['last'] or 'never'}  ({r['n']} ever)")


def cmd_unmatched(a, p):
    con = connect(p)
    rows = con.execute("SELECT * FROM placements WHERE id NOT IN (SELECT placement_id FROM placement_assets) "
                       "ORDER BY source, date").fetchall()
    for r in rows:
        print(f"  {r['source']:14} {r['date'] or '----------':10} {r['channel']:12} {r['target'][:60]}  [{r['id']}]")
    print(f"{len(rows)} unmatched")


def cmd_status(a, p):
    if not p["db"].exists():
        print("hub: not built")
        return
    con = connect(p)
    n = con.execute("SELECT count(*) FROM placements").fetchone()[0]
    live = con.execute("SELECT count(*) FROM placements WHERE status IN ('live','replied')").fetchone()[0]
    since = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    week = con.execute("SELECT count(*) FROM placements WHERE status IN ('live','replied') AND date >= ?", (since,)).fetchone()[0]
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    print(f"hub: {n} placements, {live} live, {week} live in 7 days, {meta.get('unmatched')} unmatched (built {meta.get('built')})")


def cmd_channels(a, p):
    con = connect(p)
    q = "SELECT * FROM channel_stats" + (" WHERE product = ?" if a.product else "") + " ORDER BY product, placements DESC"
    rows = con.execute(q, (a.product,) if a.product else ()).fetchall()
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    print(f"last {STOP_DAYS} days; funnel as of {meta.get('funnel_asof') or 'never (run import --fetch)'}")
    print(f"  {'product':15} {'channel':13} {'placed':>6} {'visits':>6} {'trials':>6} {'orders':>6} {'heard':>5}  verdict")
    for r in rows:
        v = "-" if r["visits"] is None else r["visits"]
        t = "-" if r["trials"] is None else r["trials"]
        print(f"  {r['product']:15} {r['channel']:13} {r['placements']:>6} {v:>6} {t:>6} {r['orders']:>6} {r['heard']:>5}  {r['verdict']}: {r['why']}")
    heard = con.execute("SELECT * FROM heard ORDER BY orders DESC").fetchall()
    if heard:
        print("how buyers say they heard (Checkout answers, all time): " + ", ".join(f"{h['product']} {h['answer']} {h['orders']}" for h in heard))


def cmd_followups(a, p):
    con = connect(p)
    today = dt.date.today().isoformat()
    due = con.execute("SELECT * FROM placements WHERE follow_up_due != '' ORDER BY follow_up_due").fetchall()
    print(f"{sum(1 for r in due if r['follow_up_due'] <= today)} follow-ups due (one each, days {FOLLOW_UP_DAY} to {FOLLOW_UP_LAST}), {len(due)} open:")
    for r in due:
        mark = "due" if r["follow_up_due"] <= today else "wait"
        print(f"  {mark:4} {r['follow_up_due']}  sent {r['date']}  {r['channel']:11} {r['target'][:50]:50} {r['contact_ref'] or r['approval']}")
    n = con.execute("SELECT count(*) FROM placements WHERE status = 'no-response'").fetchone()[0]
    print(f"{n} marked no-response (no reply logged after {NO_RESPONSE_DAY} days)")


def cmd_check_listings(a, p):
    r = check_listings(p, a.if_older)
    s = build(p)
    con = connect(p)
    states = dict(con.execute("SELECT check_state, count(*) FROM placements WHERE check_state != '' GROUP BY check_state").fetchall())
    print(f"checked {r['checked']} listings ({r['skipped']} checked recently); now {states}; {s['placements']} placements")
    for row in con.execute("SELECT p.*, a.version, a.price FROM placements p JOIN placement_assets x ON x.placement_id = p.id "
                           "JOIN assets a ON a.id = x.asset_id WHERE p.check_state = 'stale' AND a.kind = 'product'"):
        f = json.loads(row["facts_seen"] or "{}")
        print(f"  stale: {row['target'][:40]:40} shows {f.get('versions')} {f.get('prices')}, site says {row['version']} ${row['price']}  {row['url']}")


def export_rows(p: dict) -> dict:
    """Every dataset is an array of plain rows. Only allow-listed fields leave the Mac: no contact reference, no notes,
    and no target or URL for one-to-one outreach (emails, library and press pitches)."""
    con = connect(p)
    today = dt.date.today()
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    links: dict = {}
    for r in con.execute("SELECT placement_id, asset_id FROM placement_assets"):
        links.setdefault(r[0], []).append(r[1])
    res: dict = {}
    for r in con.execute("SELECT * FROM results"):
        res.setdefault(r["placement_id"], {})[r["metric"]] = (r["value"], r["confidence"])
    pls = [dict(r) for r in con.execute("SELECT * FROM placements")]
    kinds = {r["id"]: r["kind"] for r in con.execute("SELECT id, kind FROM assets")}
    names = {r["id"]: r["name"] for r in con.execute("SELECT id, name FROM assets")}
    products = [r["id"] for r in con.execute("SELECT id FROM assets WHERE kind = 'product' ORDER BY id")]
    live = [x for x in pls if x["status"] in ("live", "replied", "no-response")]
    wk = (today - dt.timedelta(days=7)).isoformat()

    grid, chans = [], {}
    for prod in products:
        mine = [x for x in live if prod in links.get(x["id"], [])]
        c: dict = {}
        for x in mine:
            c[x["channel"]] = c.get(x["channel"], 0) + 1
            chans[x["channel"]] = chans.get(x["channel"], 0) + 1
        grid.append({"product": prod, "name": names.get(prod, prod), "total": len(mine),
                     "last": max((x["date"] for x in mine), default=None), "channels": c,
                     "last7": sum(1 for x in mine if x["date"] >= wk)})
    grid.sort(key=lambda g: (-g["total"], g["product"]))

    def public(x):
        return x["channel"] in PUBLIC_CHANNELS

    def label(x):  # "MacMenuBar (Luuk)" -> "MacMenuBar": a person's name in brackets stays on the Mac
        return re.sub(r"\s*\([^)]*\)", "", x["target"]).strip() if public(x) else None

    def n(v):
        return None if v is None else (int(v) if float(v).is_integer() else v)

    placements = []
    for x in sorted(live + [y for y in pls if y["status"] in ("approved", "queued")], key=lambda y: y["date"] or "", reverse=True)[:80]:
        r = res.get(x["id"], {})
        placements.append({
            "date": x["date"] or None, "assets": [a for a in links.get(x["id"], []) if kinds.get(a) != "line"],
            "channel": x["channel"], "kind": x["kind"] or None, "status": x["status"],
            "target": label(x), "url": x["url"] if public(x) and x["url"].startswith("http") else None,
            "visits": n(r.get("first-touch-visits", (None,))[0]), "trials": n(r.get("trials", (None,))[0]),
            "orders": n(r.get("orders", (None,))[0]), "confidence": r.get("first-touch-visits", (None, None))[1],
            "approval": "standing" if (x["approval"] or "").startswith("standing") else ("queue" if x["approval"] else None),
        })
    followups = [{"due": x["follow_up_due"], "sent": x["date"], "channel": x["channel"],
                  "assets": links.get(x["id"], []), "isDue": x["follow_up_due"] <= today.isoformat()}
                 for x in sorted(pls, key=lambda y: y["follow_up_due"]) if x["follow_up_due"]]
    listings = []
    for x in pls:
        if not x["check_state"]:
            continue
        prods = [a for a in links.get(x["id"], []) if kinds.get(a) == "product"]
        a = con.execute("SELECT version, price FROM assets WHERE id = ?", (prods[0],)).fetchone() if prods else None
        f = json.loads(x["facts_seen"] or "{}")
        listings.append({"product": prods[0] if prods else None, "channel": x["channel"], "target": label(x),
                         "url": x["url"] if public(x) else None, "state": x["check_state"],
                         "seenVersions": f.get("versions") or [], "seenPrices": f.get("prices") or [],
                         "siteVersion": a["version"] if a else None, "sitePrice": a["price"] if a else None,
                         "checked": (f.get("checked") or "")[:10] or None})
    order = {"stale": 0, "manual": 1, "unchecked": 2, "no-link": 3, "ok": 4}
    listings.sort(key=lambda r: (order.get(r["state"], 4), r["product"] or ""))
    channels = [{"product": r["product"], "channel": r["channel"], "placements": r["placements"], "visits": r["visits"],
                 "trials": r["trials"], "orders": r["orders"], "heard": r["heard"], "rateLo": r["rate_lo"],
                 "rateHi": r["rate_hi"], "verdict": r["verdict"], "why": r["why"]}
                for r in con.execute("SELECT * FROM channel_stats ORDER BY product, placements DESC")]
    heard = [dict(r) for r in con.execute("SELECT product, answer, channel, orders FROM heard ORDER BY orders DESC")]
    summary = [{
        "asOf": today.isoformat(), "built": meta.get("built"), "funnelAsOf": meta.get("funnel_asof") or None,
        "placements": len(pls), "live": len(live), "live7": sum(1 for x in live if x["date"] >= wk),
        "queued": sum(1 for x in pls if x["status"] in ("queued", "approved")), "unmatched": int(meta.get("unmatched") or 0),
        "followupsDue": sum(1 for f in followups if f["isDue"]), "noResponse": sum(1 for x in pls if x["status"] == "no-response"),
        "stale": sum(1 for r in listings if r["state"] == "stale"), "manual": sum(1 for r in listings if r["state"] in ("manual", "unchecked")),
        "pauseCandidates": sum(1 for r in channels if r["verdict"] == "pause-candidate"),
        "untouched": [g["product"] for g in grid if not g["total"]],
        "channelOrder": sorted(chans, key=lambda c: -chans[c]),
        "rule": f"Pause only at {STOP_PLACEMENTS}+ placements, {STOP_VISITS}+ first-touch visits, {STOP_DAYS} days, zero trials.",
    }]
    return {"marketing_summary": summary, "marketing_grid": grid, "marketing_channels": channels,
            "marketing_placements": placements, "marketing_followups": followups, "marketing_listings": listings,
            "marketing_heard": heard}


def cmd_export(a, p):
    out = Path(a.dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in export_rows(p).items():
        tmp = out / f".{name}.json.tmp"
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        os.replace(tmp, out / f"{name}.json")
    print(f"exported marketing datasets to {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    im = sub.add_parser("import"); im.add_argument("--fetch", action="store_true")
    w = sub.add_parser("where"); w.add_argument("asset"); w.add_argument("--all", action="store_true")
    g = sub.add_parser("grid"); g.add_argument("--all", action="store_true")
    gp = sub.add_parser("gaps"); gp.add_argument("--days", type=int, default=30); gp.add_argument("--all", action="store_true")
    sub.add_parser("unmatched")
    sub.add_parser("status")
    ch = sub.add_parser("channels"); ch.add_argument("product", nargs="?")
    sub.add_parser("followups")
    cl = sub.add_parser("check-listings"); cl.add_argument("--if-older", type=int, default=0)
    ex = sub.add_parser("export"); ex.add_argument("dir")
    a = ap.parse_args(argv)
    {"import": cmd_import, "where": cmd_where, "grid": cmd_grid, "gaps": cmd_gaps, "unmatched": cmd_unmatched,
     "status": cmd_status, "channels": cmd_channels, "followups": cmd_followups, "check-listings": cmd_check_listings,
     "export": cmd_export}[a.cmd](a, paths())
    return 0


if __name__ == "__main__":
    sys.exit(main())
