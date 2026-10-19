"""Daily metrics, stored privately in ~/.purplelink/social/metrics.json (outside the repo).

  clicks      per source (bluesky, threads, linkedin, mastodon): the stats function's topUtm count and the
              first-touch pageviews per path (funnelByChannel). The function does not expose utm_campaign, so a post's
              clicks are the growth of its path under its platform's source since before it went out. Honest limit:
              two posts to one page share that count (the 21-day repeat rule keeps this rare).
  engagement  Bluesky likes, reposts, replies and quotes (public AppView), Mastodon favourites, reblogs and replies
              (public status API), Threads views, likes, replies, reposts and quotes only if the token has
              `threads_manage_insights`; otherwise views are recorded as null (unknown) with a note.
  followers   per account per day (Bluesky and Mastodon public profile; Threads needs `threads_manage_insights`;
              LinkedIn shows no public count here, so it is unknown).
Every network call goes through the injected `http`; tests mock it. Nothing here posts.
"""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import quote, urlsplit

from .. import items as itemsmod
from .. import paths, sysutil
from . import candidates as cand
from . import settings as st

APPVIEW = "https://public.api.bsky.app/xrpc"
THREADS = "https://graph.threads.net/v1.0"
SOURCES = ("bluesky", "threads", "linkedin", "mastodon")


def load() -> dict:
    d = st.read_json(paths.metrics_file(), {})
    d.setdefault("version", 1)
    for k in ("followers", "clicks", "posts", "notes"):
        d.setdefault(k, {} if k != "notes" else [])
    return d


def save(d: dict) -> None:
    st.write_json(paths.metrics_file(), d)


# ---------------------------------------------------------------- parsers (pure)
def bluesky_uri(result: dict) -> str | None:
    rid = str(result.get("id") or "")
    if rid.startswith("at://"):
        return rid
    m = re.match(r"https://bsky\.app/profile/([^/]+)/post/([A-Za-z0-9]+)", str(result.get("url") or ""))
    return f"at://{m.group(1)}/app.bsky.feed.post/{m.group(2)}" if m else None


def parse_bluesky_thread(j) -> dict | None:
    post = ((j or {}).get("thread") or {}).get("post") or {}
    if "likeCount" not in post and "repostCount" not in post:
        return None
    return {"likes": post.get("likeCount", 0), "reposts": post.get("repostCount", 0),
            "replies": post.get("replyCount", 0), "quotes": post.get("quoteCount", 0), "views": None}


def parse_mastodon_status(j) -> dict | None:
    if not isinstance(j, dict) or "favourites_count" not in j:
        return None
    return {"likes": j.get("favourites_count", 0), "reposts": j.get("reblogs_count", 0),
            "replies": j.get("replies_count", 0), "quotes": 0, "views": None}


def parse_threads_insights(j) -> dict | None:
    """{'data': [{'name': 'views', 'values': [{'value': 12}]}, ...]} -> counts; None when the call was refused."""
    if not isinstance(j, dict) or not isinstance(j.get("data"), list) or not j["data"]:
        return None
    vals = {}
    for m in j["data"]:
        v = m.get("values") or []
        vals[m.get("name")] = (v[0].get("value") if v else None) if "values" in m else m.get("total_value", {}).get("value")
    return {"likes": vals.get("likes"), "reposts": vals.get("reposts"), "replies": vals.get("replies"),
            "quotes": vals.get("quotes"), "views": vals.get("views")}


def parse_clicks(stats: dict) -> dict:
    """{source: {"total": topUtm count, "paths": {path: first-touch pageviews}}} for the posting sources."""
    top = {r["key"]: int(r["count"]) for r in (stats.get("topUtm") or []) if isinstance(r, dict)}
    fun = stats.get("funnelByChannel") or {}
    return {s: {"total": top.get(s, 0), "paths": dict((fun.get(s) or {}).get("pageviewsByPath") or {})}
            for s in SOURCES}


def parse_followers_bluesky(j) -> int | None:
    return j.get("followersCount") if isinstance(j, dict) else None


def parse_followers_mastodon(j) -> int | None:
    return j.get("followers_count") if isinstance(j, dict) else None


# ---------------------------------------------------------------- collection
def _get_json(http, url, headers=None):
    try:
        r = http.request("GET", url, headers=headers or {})
    except Exception:
        return None, 0
    return (r.json() if r.status == 200 else None), r.status


def posted_items(today: dt.date, days: int = 60):
    out = []
    for it in itemsmod.list_items():
        for plat, r in it.results.items():
            if r.get("status") != "posted":
                continue
            try:
                pdate = dt.datetime.fromisoformat(str(r.get("posted_at"))).date()
            except ValueError:
                continue
            if 0 <= (today - pdate).days <= days:
                out.append((it, plat, r, pdate))
    return out


def collect(http, main_cfg: dict, today: dt.date, token_for=None, stats=None) -> dict:
    """One daily pass. Returns the updated metrics dict (also saved). Failures are recorded as notes, never raised."""
    d = load()
    day = today.isoformat()
    notes: list[str] = []
    token_for = token_for or (lambda plat: sysutil.keychain_get(plat, "access_token"))

    # clicks
    stats = stats if stats is not None else cand.fetch_stats(http, 30)
    if stats:
        d["clicks"][day] = parse_clicks(stats)
    else:
        notes.append("stats function unavailable: no click counts today")

    # followers
    f: dict = {}
    j, _ = _get_json(http, f"{APPVIEW}/app.bsky.actor.getProfile?actor={quote(main_cfg['platforms']['bluesky']['expected'].get('handle', ''))}")
    f["bluesky"] = parse_followers_bluesky(j)
    mc = main_cfg["platforms"].get("mastodon", {})
    acct = str((mc.get("expected") or {}).get("acct", "")).split("@")[0]
    if mc.get("instance") and acct:
        j, _ = _get_json(http, f"{mc['instance'].rstrip('/')}/api/v1/accounts/lookup?acct={quote(acct)}")
        f["mastodon"] = parse_followers_mastodon(j)
    tok = token_for("threads")
    f["threads"] = None
    if tok:
        j, status = _get_json(http, f"{THREADS}/me/threads_insights?metric=followers_count",
                              {"Authorization": f"Bearer {tok}"})
        if status == 200 and isinstance(j, dict) and j.get("data"):
            m = j["data"][0]
            f["threads"] = (m.get("total_value") or {}).get("value")
        else:
            notes.append("threads followers and views unknown: the token lacks threads_manage_insights "
                         "(Ben would need to add that permission to the Meta app)")
    f["linkedin"] = None  # no public follower count is readable here
    d["followers"][day] = f

    # per-post engagement
    for it, plat, r, pdate in posted_items(today):
        row = d["posts"].setdefault(it.id, {"kind": (it.meta.get("daily") or {}).get("kind"),
                                           "format": (it.meta.get("daily") or {}).get("format"),
                                           "campaign": it.campaign, "path": urlsplit(it.link).path,
                                           "platforms": {}})
        pr = row["platforms"].setdefault(plat, {"url": r.get("url"), "posted": pdate.isoformat(), "snapshots": {}})
        eng = None
        if plat == "bluesky":
            uri = bluesky_uri(r)
            if uri:
                j, _ = _get_json(http, f"{APPVIEW}/app.bsky.feed.getPostThread?uri={quote(uri, safe='')}&depth=0&parentHeight=0")
                eng = parse_bluesky_thread(j)
        elif plat == "mastodon":
            inst = (mc.get("instance") or "").rstrip("/")
            if inst and r.get("id"):
                j, _ = _get_json(http, f"{inst}/api/v1/statuses/{quote(str(r['id']))}")
                eng = parse_mastodon_status(j)
        elif plat == "threads" and tok and r.get("id"):
            j, status = _get_json(http, f"{THREADS}/{quote(str(r['id']))}/insights?metric=views,likes,replies,reposts,quotes",
                                  {"Authorization": f"Bearer {tok}"})
            eng = parse_threads_insights(j) if status == 200 else None
            if eng is None:
                eng = {"likes": None, "reposts": None, "replies": None, "quotes": None, "views": None}
        else:
            eng = {"likes": None, "reposts": None, "replies": None, "quotes": None, "views": None}
        if eng is not None:
            pr["snapshots"][day] = eng
    d["notes"] = (d["notes"] + [f"{day}: {n}" for n in notes])[-60:]
    save(d)
    return d


# ---------------------------------------------------------------- per-post outcomes (used by learn.py)
def baseline_clicks(d: dict, source: str, path: str, posted: str) -> int:
    """Pageviews for the path under this source on the last snapshot dated before the post (0 if none)."""
    prior = sorted(k for k in d["clicks"] if k < posted)
    return int(((d["clicks"][prior[-1]].get(source) or {}).get("paths") or {}).get(path, 0)) if prior else 0


def post_outcomes(d: dict, today: dt.date, min_age_days: int = 2) -> list[dict]:
    """One row per (post, platform): kind, format, platform, engagement and click growth, and a single outcome number
    (clicks + likes + 2 x reposts + 2 x replies). Views are left out: they are unknown on most platforms."""
    out = []
    latest_click_day = max(d["clicks"], default=None)
    for item_id, row in d["posts"].items():
        for plat, pr in row["platforms"].items():
            if (today - dt.date.fromisoformat(pr["posted"])).days < min_age_days:
                continue
            snap = pr["snapshots"][max(pr["snapshots"])] if pr["snapshots"] else {}
            clicks = 0
            if latest_click_day and plat in SOURCES:
                now_c = int(((d["clicks"][latest_click_day].get(plat) or {}).get("paths") or {}).get(row["path"], 0))
                clicks = max(0, now_c - baseline_clicks(d, plat, row["path"], pr["posted"]))
            eng = sum(int(snap.get(k) or 0) * w for k, w in (("likes", 1), ("reposts", 2), ("replies", 2)))
            out.append({"item": item_id, "kind": row.get("kind"), "format": row.get("format"), "platform": plat,
                        "posted": pr["posted"], "clicks": clicks, "engagement": eng, "views": snap.get("views"),
                        "outcome": clicks + eng})
    return [o for o in out if o["kind"] and o["format"]]
