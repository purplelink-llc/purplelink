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

Sources: approval queue items (pending, approved, done; outward kinds only), the social queue (posted and scheduled
company posts, one placement per platform), Outreach/OUTREACH-LOG.md tables, video/howto/ledger.json, and the MacUpdate
readings in the traffic dashboard history. Assets come from site/llms.txt and site/sitemap.xml.

Contacts are not copied: an outreach row keeps a `contact_ref` (file and line) and email addresses in notes are masked.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
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
    }


SCHEMA = """
CREATE TABLE assets (id TEXT PRIMARY KEY, kind TEXT, name TEXT, product TEXT, url TEXT);
CREATE TABLE placements (
  id TEXT PRIMARY KEY, source TEXT, channel TEXT, kind TEXT, target TEXT, status TEXT, date TEXT,
  url TEXT, landing_url TEXT, utm TEXT, approval TEXT, contact_ref TEXT, notes TEXT);
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
    section, product = "", None
    for line in text.splitlines():
        if line.startswith("## "):
            section, product = line[3:].lower(), None
            continue
        if section.startswith("products") and "development" not in section and line.startswith("### "):
            product = re.sub(r"\s*\(.*$", "", line[4:]).strip()
            continue
        if product:
            for u in URL_RE.findall(line):
                path = site_path(u)
                if path and path.count("/") == 2 and path not in ("/tools/", "/guides/", "/blog/"):
                    aid = path.strip("/")
                    assets.setdefault(aid, {"kind": "product", "name": product, "product": aid,
                                            "url": f"https://{SITE_HOST}{path}"})
                    product = None
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
        })
        for day, s in sorted(snaps.items()):
            if "downloads" in s:
                results.append((pid, day, "downloads-total", s["downloads"], "macupdate", "exact"))
    return out, results


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
    p["db"].parent.mkdir(parents=True, exist_ok=True)
    tmp = p["db"].with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO assets VALUES (?,?,?,?,?)",
                    [(k, a["kind"], a["name"], a["product"], a["url"]) for k, a in assets.items()])
    cols = ["id", "source", "channel", "kind", "target", "status", "date", "url", "landing_url", "utm", "approval",
            "contact_ref", "notes"]
    seen, unmatched = set(), 0
    for pl in placements:
        if pl["id"] in seen:
            continue
        seen.add(pl["id"])
        con.execute(f"INSERT INTO placements VALUES ({','.join('?' * len(cols))})", [pl.get(c) or "" for c in cols])
        ids = [a for a in pl.get("_assets", []) if a in assets] or match_assets(pl["_text"] + " " + pl["landing_url"], assets)
        if not ids:
            unmatched += 1
        con.executemany("INSERT OR IGNORE INTO placement_assets VALUES (?,?)", [(pl["id"], a) for a in ids])
    con.executemany("INSERT INTO results VALUES (?,?,?,?,?,?)", results)
    now = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    con.executemany("INSERT INTO meta VALUES (?,?)", [("built", now), ("unmatched", str(unmatched))])
    con.commit()
    con.close()
    os.replace(tmp, p["db"])
    by_source: dict = {}
    for pl in placements:
        by_source[pl["source"]] = by_source.get(pl["source"], 0) + 1
    return {"assets": len(assets), "placements": len(seen), "unmatched": unmatched, "by_source": by_source}


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import")
    w = sub.add_parser("where"); w.add_argument("asset"); w.add_argument("--all", action="store_true")
    g = sub.add_parser("grid"); g.add_argument("--all", action="store_true")
    gp = sub.add_parser("gaps"); gp.add_argument("--days", type=int, default=30); gp.add_argument("--all", action="store_true")
    sub.add_parser("unmatched")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    {"import": cmd_import, "where": cmd_where, "grid": cmd_grid, "gaps": cmd_gaps,
     "unmatched": cmd_unmatched, "status": cmd_status}[a.cmd](a, paths())
    return 0


if __name__ == "__main__":
    sys.exit(main())
