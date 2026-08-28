#!/usr/bin/env python3
"""
Daily traffic dashboard for purplelink.llc and getmuscleonglp.com.

Reads each site's own first-party analytics endpoint (the cookieless beacon +
Netlify Blobs store, not a third-party vendor), merges every daily figure into a
permanent local archive, and renders a self-contained HTML dashboard you can
open any time.

Why the local archive: the stats endpoints aggregate by listing one stored
record per event. That is fine at current volume, but the window is only as good
as what is still in the store, and a long window is slower and more failure
prone. Snapshotting each run into history.json means the record grows into a
durable daily series that outlives the endpoint's retention.

Usage:
    python3 traffic_dashboard.py            # fetch, archive, render, summarise
    python3 traffic_dashboard.py --open     # ...and open the dashboard
    python3 traffic_dashboard.py --no-fetch # re-render from the archive only

Config (never in this repo, which is public) at ~/.config/purplelink/traffic.env:
    PURPLELINK_STATS_TOKEN=...
    MUSCLEONGLP_STATS_TOKEN=...
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import http.client
import json
import os
import random
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "purplelink" / "traffic.env"
OUT_DIR = Path.home() / ".purplelink" / "traffic"
HISTORY_PATH = OUT_DIR / "history.json"
DASHBOARD_PATH = OUT_DIR / "dashboard.html"

FETCH_DAYS = 30          # comfortably covers any gap since the last run
TIMEOUT = 60
RETRIES = 3               # a daily job can afford to try again before giving up
RETRY_BACKOFF = 3.0       # seconds; doubles each attempt

# Metrics added after this archive already existed. The endpoints backfill a
# new counter with zeros for earlier days, so the data cannot tell "started
# today" apart from "nobody ever did it" — and reporting a day-old counter as
# a conversion failure would be wrong. Dated explicitly here because it is
# known, not inferable. Anything added later dates itself from first sight.
METRIC_START_OVERRIDES = {
    ("muscleonglp", "calcRuns"): "2026-07-25",
    ("purplelink", "checkoutClicks"): "2026-08-28",
}

SITES = [
    {
        "key": "purplelink",
        "label": "Purplelink LLC",
        "domain": "purplelink.llc",
        "url": "https://purplelink.llc/.netlify/functions/stats",
        "token_env": "PURPLELINK_STATS_TOKEN",
        # (json key in byDay, display label) — engagement metrics beyond a visit
        "secondaries": [("toolRuns", "tool runs"), ("signups", "waitlist signups"),
                        ("checkoutClicks", "checkout clicks")],
        # Paths that actually show a buy button. The useful denominator for a
        # checkout rate is "people who reached a page where buying was possible",
        # not all pageviews: /kits/clip-pipeline/ drew 24 views in a month and
        # produced no Stripe session at all, and against sitewide traffic that
        # signal disappears into the noise.
        "product_paths": ("/kits/", "/tools/paper-review/"),
        # Waitlists are Netlify Forms, so they never reach the analytics beacon.
        # Without this they read as zero while people are actually signing up.
        "netlify_site_id": "b264591f-fbbe-4048-9d9d-7051cf497823",
        # Search Console property id. Purplelink is a URL-prefix property, so
        # the trailing slash is part of the id; getmuscleonglp is a domain
        # property and takes the sc-domain: form. Using the wrong form returns
        # a 403 that looks exactly like a missing permission.
        "gsc_property": "https://purplelink.llc/",
    },
    {
        "key": "muscleonglp",
        "label": "MuscleOnGLP",
        "domain": "getmuscleonglp.com",
        "url": "https://getmuscleonglp.com/.netlify/functions/stats",
        "token_env": "MUSCLEONGLP_STATS_TOKEN",
        "secondaries": [("subscribes", "subscribes"), ("calcRuns", "calculator runs"),
                        ("checkoutClicks", "checkout clicks")],
        "product_paths": ("/guides/",),
        "gsc_property": "sc-domain:getmuscleonglp.com",
    },
]

# Service-account key for the Search Console API. Absent on a machine that has
# not been set up; the dashboard degrades to beacon-only rather than failing.
GSC_KEY_PATH = Path.home() / ".config" / "purplelink" / "gsc.json"
GSC_DAYS = 28            # GSC's own default reporting window
GSC_LAG_DAYS = 2         # Search Console data is ~48h behind; asking for
                         # yesterday returns zeros and reads as a traffic drop.


# ---------------------------------------------------------------- config/io

def load_config() -> dict[str, str]:
    """Environment wins; otherwise read the private key=value config file."""
    cfg: dict[str, str] = {}
    if CONFIG_PATH.exists():
        for line in CONFIG_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    for site in SITES:
        env = os.environ.get(site["token_env"])
        if env:
            cfg[site["token_env"]] = env
    return cfg


def _ssl_context() -> ssl.SSLContext:
    """python.org framework builds ship without CA roots, so verification fails
    unless we point at a bundle. Prefer certifi; fall back to the system store."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def fetch_site(site: dict, token: str) -> dict:
    """Fetch one site's stats, retrying transient failures.

    A single 502 used to drop the whole site to archived figures for the day,
    which is what happened on 2026-08-14: the stats function was timing out
    because it read one blob per event serially. That cause is fixed, but a
    cold start or a Netlify blip can still produce one bad response, and this
    job runs once a day, so there is no reason to give up on the first try.
    Only transient conditions are retried; a 401 means the token is wrong and
    retrying it would just be slower.
    """
    url = f"{site['url']}?token={urllib.parse.quote(token)}&days={FETCH_DAYS}"
    req = urllib.request.Request(url, headers={"User-Agent": "purplelink-traffic-dashboard"})
    last: Exception | None = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise
            last = exc
        except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
            # OSError covers URLError and TimeoutError (both subclasses) plus the
            # connection-level errors that are not URLErrors at all.
            # http.client.HTTPException covers a response that starts and then
            # breaks mid-stream. On 2026-08-23 a RemoteDisconnected -- which is
            # ConnectionResetError + BadStatusLine, so neither a URLError nor a
            # TimeoutError -- went straight past the old tuple, out of the retry
            # loop, out of main, and killed the process.
            last = exc
    raise last  # type: ignore[misc]


def fetch_gsc(site: dict) -> dict | None:
    """Search Console clicks/impressions/position, plus top queries and pages.

    Returns None when the integration is not set up or the property is not
    readable. Every failure here is non-fatal: the beacon numbers are the
    dashboard's job, and a Google outage or an expired key must not cost us
    the daily run.
    """
    prop = site.get("gsc_property")
    if not prop or not GSC_KEY_PATH.exists():
        return None
    try:
        from google.oauth2 import service_account          # noqa: PLC0415
        from googleapiclient.discovery import build        # noqa: PLC0415
    except ImportError:
        return {"error": "google-api-python-client not installed"}

    end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=GSC_LAG_DAYS)
    start = end - dt.timedelta(days=GSC_DAYS - 1)

    def query(dimensions, limit):
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                "dimensions": dimensions, "rowLimit": limit}
        return svc.searchanalytics().query(siteUrl=prop, body=body).execute()

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(GSC_KEY_PATH),
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)

        # No dimensions => one row of site-wide totals for the window.
        totals = (query([], 1).get("rows") or [{}])[0]
        queries = query(["query"], 10).get("rows") or []
        pages = query(["page"], 10).get("rows") or []
    except Exception as exc:                                # noqa: BLE001
        detail = getattr(exc, "reason", None) or str(exc)
        return {"error": detail[:200]}

    def strip(u: str) -> str:
        for pre in ("https://", "http://"):
            if u.startswith(pre):
                u = u[len(pre):]
        return u

    return {
        "clicks": int(totals.get("clicks", 0) or 0),
        "impressions": int(totals.get("impressions", 0) or 0),
        "ctr": float(totals.get("ctr", 0) or 0) * 100,
        "position": float(totals.get("position", 0) or 0),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "queries": [{"key": r["keys"][0], "count": int(r.get("clicks", 0) or 0),
                     "impressions": int(r.get("impressions", 0) or 0),
                     "position": round(float(r.get("position", 0) or 0), 1)}
                    for r in queries],
        "pages": [{"key": strip(r["keys"][0]), "count": int(r.get("clicks", 0) or 0),
                   "impressions": int(r.get("impressions", 0) or 0),
                   "position": round(float(r.get("position", 0) or 0), 1)}
                  for r in pages],
    }


def _netlify_token() -> str | None:
    """Reuse the Netlify CLI's stored token rather than keeping a second copy."""
    if os.environ.get("NETLIFY_AUTH_TOKEN"):
        return os.environ["NETLIFY_AUTH_TOKEN"]
    for p in (Path.home() / "Library/Preferences/netlify/config.json",
              Path.home() / ".config/netlify/config.json"):
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        for user in (data.get("users") or {}).values():
            tok = (user.get("auth") or {}).get("token")
            if tok:
                return tok
    return None


def fetch_form_signups(site_id: str, token: str) -> tuple[dict, list]:
    """Waitlist signups per day, plus a per-form breakdown.

    Only dates and counts are read. Submissions carry email addresses; those
    are never extracted, stored, or displayed — the archive stays free of
    personal data.
    """
    def api(path):
        req = urllib.request.Request(
            f"https://api.netlify.com/api/v1/{path}",
            headers={"Authorization": f"Bearer {token}",
                     "User-Agent": "purplelink-traffic-dashboard"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as r:
            return json.loads(r.read().decode("utf-8"))

    by_day: dict[str, int] = {}
    per_form = []
    for form in api(f"sites/{site_id}/forms"):
        name = form.get("name", "form")
        subs = api(f"forms/{form['id']}/submissions")
        per_form.append({"key": name, "count": len(subs)})
        for s in subs:
            day = str(s.get("created_at", ""))[:10]
            if day:
                by_day[day] = by_day.get(day, 0) + 1
    per_form.sort(key=lambda f: -f["count"])
    return by_day, per_form


def load_history() -> dict:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text())
        except json.JSONDecodeError:
            backup = HISTORY_PATH.with_suffix(".corrupt.json")
            HISTORY_PATH.rename(backup)
            print(f"  ! history.json was unreadable; moved to {backup}", file=sys.stderr)
    return {"sites": {}}


def merge_history(history: dict, key: str, payload: dict) -> None:
    """Merge a fetch into the durable archive.

    Daily counts are authoritative from the source (a day can still be
    accumulating), so later reads overwrite earlier ones for the same date.
    Days the source no longer returns are preserved.
    """
    site_hist = history["sites"].setdefault(key, {"byDay": {}, "snapshots": {}})
    for day, metrics in (payload.get("byDay") or {}).items():
        prev = site_hist["byDay"].get(day, {})
        # Never let a transient partial read shrink a day we already recorded.
        merged = dict(prev)
        for k, v in metrics.items():
            if not isinstance(v, (int, float)):
                continue
            merged[k] = max(v, prev.get(k, 0)) if isinstance(prev.get(k), (int, float)) else v
        site_hist["byDay"][day] = merged
    site_hist["snapshots"][payload.get("generatedAt", "")[:10] or _utc_today()] = {
        "topPaths": payload.get("topPaths", [])[:12],
        "topReferrers": payload.get("topReferrers", [])[:12],
        "topUtm": payload.get("topUtm", [])[:8],
        "toolRuns": payload.get("toolRuns", [])[:8],
    }
    _record_metric_starts(site_hist, key, payload)
    # Signups arrive with real history from Netlify, so date the metric from the
    # first actual signup rather than from the day we started reading the API.
    # Otherwise a counter with weeks of data reads as "recorded since today".
    signup_days = sorted(d for d, m in (payload.get("byDay") or {}).items()
                         if isinstance(m, dict) and m.get("signups"))
    if signup_days:
        seen = site_hist.setdefault("metricsFirstSeen", {})
        if "signups" not in seen or signup_days[0] < seen["signups"]:
            seen["signups"] = signup_days[0]

    site_hist["latest"] = {
        "formBreakdown": payload.get("formBreakdown", []),
        "generatedAt": payload.get("generatedAt"),
        "topPaths": payload.get("topPaths", []),
        "topReferrers": payload.get("topReferrers", []),
        "topUtm": payload.get("topUtm", []),
        "toolRuns": payload.get("toolRuns", []),
        "totals": payload.get("totals", {}),
    }


def _record_metric_starts(site_hist: dict, key: str, payload: dict) -> None:
    """Note the date each metric first appeared, so a brand-new counter is not
    read as a failed one.

    On the first pass every metric already in the archive is dated to the
    earliest day with traffic: those counters were being collected for as long
    as there is data. After that, a key we have never seen before is genuinely
    new and dated from today.
    """
    seen = site_hist.setdefault("metricsFirstSeen", {})
    by_day = site_hist.get("byDay", {})
    active = sorted(d for d, m in by_day.items() if (m.get("pageviews") or 0) > 0)
    first_seeding = not seen
    default = (active[0] if active else _utc_today()) if first_seeding else _utc_today()

    for metrics in (payload.get("byDay") or {}).values():
        for k, v in metrics.items():
            if isinstance(v, (int, float)) and k not in seen:
                seen[k] = default

    for (site_key, metric), date in METRIC_START_OVERRIDES.items():
        if site_key == key:
            seen[metric] = date


# ---------------------------------------------------------------- analysis

def _utc_today() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def _daterange(end: dt.date, n: int) -> list[str]:
    return [(end - dt.timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _describe_age(iso_date: str | None) -> str:
    """Plain-language age of a date relative to today: 'today', 'yesterday',
    or 'N days ago'. Measured from the date itself, so a counter that began
    yesterday is never described as having begun today."""
    if not iso_date:
        return "start date unknown"
    try:
        start = dt.date.fromisoformat(iso_date)
    except ValueError:
        return "start date unknown"
    delta = (dt.datetime.now(dt.timezone.utc).date() - start).days
    if delta <= 0:
        return "today"
    if delta == 1:
        return "yesterday"
    return f"{delta} days ago"


def _days_since(iso_date: str | None, until: dt.date) -> int | None:
    """Complete days between a start date and `until`, inclusive. None if unknown."""
    if not iso_date:
        return None
    try:
        start = dt.date.fromisoformat(iso_date)
    except ValueError:
        return None
    return max(0, (until - start).days + 1)


def summarise(site: dict, site_hist: dict) -> dict:
    """Compute the numbers the dashboard actually shows."""
    by_day = site_hist.get("byDay", {})
    today = dt.datetime.now(dt.timezone.utc).date()
    yesterday = today - dt.timedelta(days=1)

    def total(days: list[str], field: str) -> int:
        return sum(int(by_day.get(d, {}).get(field, 0) or 0) for d in days)

    last7_days = _daterange(yesterday, 7)      # complete days only
    prior7_days = _daterange(yesterday - dt.timedelta(days=7), 7)
    last14_days = _daterange(today, 14)        # for the sparkline, includes today
    last30_days = _daterange(yesterday, 30)

    last7 = total(last7_days, "pageviews")
    prior7 = total(prior7_days, "pageviews")

    active = sorted(d for d, m in by_day.items() if (m.get("pageviews") or 0) > 0)
    first_day = active[0] if active else None

    # A baseline that reaches back before tracking began is not a real
    # comparison — those days are zero because nothing was recorded, not
    # because nobody visited. Suppress the delta rather than report growth
    # that is an artifact of when the beacon was installed.
    baseline_complete = bool(first_day) and prior7_days[0] >= first_day
    if prior7 > 0 and baseline_complete:
        delta_pct = round((last7 - prior7) / prior7 * 100)
    else:
        delta_pct = None
    latest = site_hist.get("latest", {})

    return {
        "label": site["label"],
        "domain": site["domain"],
        "today": total([today.isoformat()], "pageviews"),
        "last7": last7,
        "prior7": prior7,
        "delta_pct": delta_pct,
        "baseline_complete": baseline_complete,
        "uniques7": total(last7_days, "uniques"),
        "secondaries": [
            {
                "key": k,
                "label": lbl,
                "value": total(last7_days, k),
                # Prior week for the same counter, so the card can show whether
                # a number is moving rather than just its level. Only comparable
                # when the counter already existed across the whole prior week.
                "prior": total(prior7_days, k),
                "comparable": bool(
                    site_hist.get("metricsFirstSeen", {}).get(k)
                    and prior7_days[0] >= site_hist["metricsFirstSeen"][k]
                ),
                "since": site_hist.get("metricsFirstSeen", {}).get(k),
                # Complete days this counter has actually existed for. A zero
                # over a window the counter did not span is not a finding.
                "days_tracked": _days_since(site_hist.get("metricsFirstSeen", {}).get(k), yesterday),
            }
            for k, lbl in site["secondaries"]
        ],
        "last30": total(last30_days, "pageviews"),
        # topReferrers comes from the live payload, which is a FETCH_DAYS (30)
        # window — not the 7-day one the headline uses. Pair it with the
        # matching 30-day pageview total or the "unreferred remainder" is
        # nonsense (it went negative and got silently suppressed once already).
        "channels": channel_mix(latest.get("topReferrers", []), total(last30_days, "pageviews")),
        "all_time": total(sorted(by_day), "pageviews"),
        "first_day": first_day,
        "days_tracked": len(active),
        "spark": [
            {"day": d, "pv": int(by_day.get(d, {}).get("pageviews", 0) or 0)}
            for d in last14_days
        ],
        "top_paths": latest.get("topPaths", [])[:6],
        "top_referrers": latest.get("topReferrers", [])[:6],
        "top_utm": latest.get("topUtm", [])[:5],
        "tool_runs": latest.get("toolRuns", [])[:5],
        "calc_runs": latest.get("calcByTool", [])[:5],
        "form_breakdown": latest.get("formBreakdown", [])[:6],
        "gsc": site_hist.get("gsc"),
        "proj": project(by_day, today),
        "checkout": checkout_rate(
            latest.get("topPaths", []), site.get("product_paths"),
            int(total(last30_days, "checkoutClicks") or 0),
        ),
        "bounds": [b for b in (
            conversion_bound(by_day, k, lbl) for k, lbl in site["secondaries"]
        ) if b],
        "error": site_hist.get("error"),
    }


AI_REFERRERS = ("chatgpt", "perplexity", "claude.ai", "copilot", "gemini")
SEARCH_REFERRERS = ("google", "bing", "duckduckgo", "brave", "ecosia", "yahoo")
SOCIAL_REFERRERS = ("reddit", "twitter", "t.co", "x.com", "facebook", "linkedin",
                    "instagram", "youtube", "news.ycombinator", "bsky", "mastodon")


def channel_mix(referrers: list[dict], pageviews: int) -> list[dict]:
    """Group referrers into channels, and infer the unreferred remainder.

    Only referred visits appear in topReferrers, so "Direct / untagged" is
    pageviews minus everything attributed. That bucket is not purely
    bookmark-and-type traffic: Reddit and most link shorteners send
    rel=noreferrer, and apps strip referrers entirely, so real referrals land
    here too. Labelled accordingly rather than called "direct".
    """
    buckets = {"Search engines": 0, "AI assistants": 0, "Social & forums": 0, "Other referrers": 0}
    for r in referrers:
        host = str(r.get("key", "")).lower()
        n = int(r.get("count", 0) or 0)
        if any(t in host for t in SEARCH_REFERRERS):
            buckets["Search engines"] += n
        elif any(t in host for t in AI_REFERRERS):
            buckets["AI assistants"] += n
        elif any(t in host for t in SOCIAL_REFERRERS):
            buckets["Social & forums"] += n
        else:
            buckets["Other referrers"] += n

    referred = sum(buckets.values())
    rows = [{"key": k, "count": v} for k, v in buckets.items() if v]
    # Never render a negative remainder: the referrer list and the pageview
    # window can disagree at the edges (the API's top-N truncates, and the
    # windows are not guaranteed identical).
    if pageviews > referred:
        rows.append({"key": "Direct / untagged", "count": pageviews - referred})
    return rows


def checkout_rate(top_paths: list, product_prefixes, clicks: int) -> dict | None:
    """Buy-button presses against views of pages that offer a buy button.

    topPaths is the live 30-day window, so `clicks` must be the 30-day count
    too, not the 7-day headline, or the ratio compares different periods. When
    no product page was viewed at all there is no rate to report -- that is a
    discovery problem, and saying "0%" would misattribute it to the button.
    """
    if not product_prefixes:
        return None
    views = sum(
        r.get("count", 0) for r in (top_paths or [])
        if isinstance(r, dict) and str(r.get("key", "")).startswith(tuple(product_prefixes))
    )
    if not views:
        return {"views": 0, "clicks": clicks, "pct": None}
    return {"views": views, "clicks": clicks, "pct": clicks / views * 100}


def observations(summaries: list[dict]) -> list[str]:
    """Plain-language read of what the numbers mean. No spin."""
    out: list[str] = []
    for s in summaries:
        if s.get("error"):
            out.append(f"{s['label']}: could not read analytics this run ({s['error']}). "
                       f"Figures below are the last good archive.")
            continue
        if s["last7"] == 0:
            out.append(f"{s['label']}: no pageviews in the last 7 complete days.")
            continue

        # Trend
        if s["delta_pct"] is None:
            why = (f" Tracking only began {s['first_day']}, so there is no complete "
                   f"prior week to compare against yet — a week-over-week number here "
                   f"would just be measuring when the beacon was installed."
                   if s["first_day"] and not s["baseline_complete"]
                   else " No prior week to compare against yet.")
            out.append(f"{s['label']}: {s['last7']} pageviews in the last 7 days.{why}")
        else:
            direction = "up" if s["delta_pct"] > 0 else ("down" if s["delta_pct"] < 0 else "flat")
            out.append(f"{s['label']}: {s['last7']} pageviews in the last 7 days, "
                       f"{direction} {abs(s['delta_pct'])}% vs the prior 7 ({s['prior7']}).")

        # Traffic concentration
        paths = s["top_paths"]
        if paths:
            tot = sum(p["count"] for p in paths) or 1
            top = paths[0]
            share = round(top["count"] / tot * 100)
            if share >= 45:
                out.append(f"{s['label']}: {share}% of tracked pageviews land on a single page "
                           f"({top['key']}). Concentrated traffic is fragile; one ranking change moves everything.")

        # Where it comes from
        refs = s["top_referrers"]
        if refs:
            rtot = sum(r["count"] for r in refs) or 1
            search = sum(r["count"] for r in refs
                         if any(t in r["key"].lower() for t in SEARCH_REFERRERS))
            ai = sum(r["count"] for r in refs
                     if any(t in r["key"].lower() for t in AI_REFERRERS))
            if search:
                out.append(f"{s['label']}: {round(search / rtot * 100)}% of referred visits come from "
                           f"search engines. Organic search is the main channel.")
            if ai:
                out.append(f"{s['label']}: {ai} referred visit(s) came from AI assistants "
                           f"(ChatGPT/Perplexity and similar) — worth watching as a channel.")
        else:
            out.append(f"{s['label']}: no external referrers recorded — visits are direct "
                       f"or the referrer was stripped.")

        # Engagement / conversion honesty, per metric. A zero only means
        # something once the counter has covered the window being reported.
        for sec in s["secondaries"]:
            days = sec["days_tracked"]
            if sec["value"] > 0:
                out.append(f"{s['label']}: {sec['value']} {sec['label']} in the last 7 days.")
            elif days is not None and days < 7:
                # Phrase the age from the start date itself, not from the count of
                # complete days: a counter started yesterday has one full day of
                # data, which is not the same as having started today.
                started = _describe_age(sec["since"])
                out.append(f"{s['label']}: {sec['label']} have only been recorded since "
                           f"{sec['since']} ({started}), so the 7-day window is not covered yet. "
                           f"Zero here measures the counter's age, not the audience.")
            else:
                out.append(f"{s['label']}: zero {sec['label']} in the last 7 days. "
                           f"Traffic is arriving but not reaching that step.")

        # Checkout funnel. Reported separately from the generic secondaries
        # because the interesting number is the ratio, and because zero clicks
        # on zero product-page views is a completely different problem from
        # zero clicks on real product-page traffic.
        ck = s.get("checkout")
        # A rate is only honest once the counter has been running for the window
        # it is quoted over. Without this the first 30 days after shipping the
        # counter would read "people are not pressing buy" when the truth is
        # that nothing was recording the presses yet.
        ck_age = next((sec["days_tracked"] for sec in s["secondaries"]
                       if sec["key"] == "checkoutClicks"), None)
        if ck and ck_age is not None and ck_age < 30 and ck["clicks"] == 0:
            out.append(f"{s['label']}: {ck['views']} view(s) of pages with a buy button in 30 days, "
                       f"but checkout clicks have only been counted for {ck_age} day(s), so no rate "
                       f"is available yet.")
        elif ck:
            if ck["views"] == 0:
                out.append(f"{s['label']}: nobody reached a page with a buy button in the last 30 "
                           f"days, so there is no checkout rate to report. The gap is discovery, "
                           f"not the button.")
            elif ck["clicks"] == 0:
                out.append(f"{s['label']}: {ck['views']} view(s) of pages with a buy button and 0 "
                           f"checkout clicks in 30 days. People are finding the products and not "
                           f"pressing buy.")
            else:
                out.append(f"{s['label']}: {ck['clicks']} checkout click(s) from {ck['views']} "
                           f"product-page view(s) in 30 days — a {ck['pct']:.1f}% checkout rate.")

    # Cross-site
    ok = [s for s in summaries if not s.get("error")]
    if len(ok) == 2 and all(s["last7"] for s in ok):
        a, b = sorted(ok, key=lambda s: -s["last7"])
        if b["last7"]:
            out.append(f"Across the two sites, {a['label']} is carrying "
                       f"{round(a['last7'] / (a['last7'] + b['last7']) * 100)}% of the combined traffic.")
    return out


# ---------------------------------------------------------------- rendering

CSS = """
/* Dark only, by request. The palette below is what used to sit inside a
   prefers-color-scheme: dark block; it is now unconditional, so the dashboard
   looks the same on a machine set to light. color-scheme tells the browser to
   render scrollbars and any form controls dark to match, rather than leaving a
   bright scrollbar down the side of a dark page. */
:root{
  color-scheme:dark;
  --bg:oklch(16% 0.03 310); --panel:oklch(21% 0.035 310);
  --ink:oklch(96% 0.01 310); --muted:oklch(72% 0.03 300);
  --line:oklch(32% 0.05 310); --purple:oklch(78% 0.16 310);
  --purple-soft:oklch(28% 0.06 310); --good:oklch(78% 0.16 150);
  --bad:oklch(72% 0.16 25); --radius:14px;
}
*{box-sizing:border-box}
body{
  margin:0; padding:clamp(20px,4vw,48px); background:var(--bg); color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1080px;margin:0 auto}
header{margin-bottom:28px}
h1{font-size:clamp(26px,3.6vw,38px);letter-spacing:-.02em;margin:0 0 6px;font-weight:640}
.stamp{color:var(--muted);font-size:14px}
h2{font-size:15px;letter-spacing:.02em;margin:34px 0 12px;font-weight:640;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px}
.site-name{font-size:15px;font-weight:640;margin:0}
.site-dom{color:var(--muted);font-size:13px;margin:2px 0 16px}
.big{font-size:44px;font-weight:660;letter-spacing:-.03em;line-height:1}
.big-label{color:var(--muted);font-size:13px;margin-top:4px}
.delta{display:inline-block;margin-left:10px;font-size:14px;font-weight:600;vertical-align:super}
.up{color:var(--good)} .down{color:var(--bad)} .flat{color:var(--muted)}
.row{display:flex;gap:26px;margin-top:16px;flex-wrap:wrap}
.row div span{display:block}
.row .n{font-size:20px;font-weight:640}
.row .l{color:var(--muted);font-size:12px}
.spark{margin-top:18px}
.spark svg{width:100%;height:52px;display:block;overflow:visible}
.spark rect{fill:var(--purple)}
.spark rect.today{fill:var(--purple);opacity:.45}
.spark-x{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin-top:5px}
ul.obs{list-style:none;padding:0;margin:0}
ul.obs li{background:var(--panel);border:1px solid var(--line);border-left:1px solid var(--line);
  border-radius:var(--radius);padding:13px 16px;margin-bottom:9px;font-size:15px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--muted);font-weight:600;font-size:12px;
  padding:0 0 8px;border-bottom:1px solid var(--line)}
td{padding:8px 0;border-bottom:1px solid var(--line);vertical-align:top}
td.num{text-align:right;font-variant-numeric:tabular-nums;width:64px;color:var(--muted)}
td.k{word-break:break-word}
.tables{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}
.funnel{display:flex;flex-direction:column;gap:10px}
.fstep{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;
  padding:9px 0;border-bottom:1px solid var(--line)}
.fstep:last-child{border-bottom:0}
.fstep .fn{font-size:20px;font-weight:640;font-variant-numeric:tabular-nums;min-width:56px}
.fstep .fl{color:var(--ink);font-size:14px;flex:1;min-width:0}
.fstep .fr{color:var(--muted);font-size:12px;white-space:nowrap}
.fnote{color:var(--muted);font-size:12px;margin:12px 0 0}
.win{font-weight:500;text-transform:none;letter-spacing:0}
.fan{margin-top:16px}
.fan svg{width:100%;height:120px;display:block;overflow:visible}
.fan .band90 polygon{fill:var(--purple);opacity:.14}
.fan .band50 polygon{fill:var(--purple);opacity:.26}
.fan .hist{fill:none;stroke:var(--ink);stroke-width:1.6;vector-effect:non-scaling-stroke}
.fan .med{fill:none;stroke:var(--purple);stroke-width:1.6;stroke-dasharray:3 3;vector-effect:non-scaling-stroke}
.fan .now{stroke:var(--line);stroke-width:1;vector-effect:non-scaling-stroke}
.fan-x{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin-top:5px}
.fan-note{color:var(--muted);font-size:12px;margin:10px 0 0;line-height:1.5}
.bound{color:var(--muted);font-size:12px;margin:8px 0 0;line-height:1.5}
.err{border-color:var(--bad);color:var(--bad)}
footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--line);
  color:var(--muted);font-size:13px}
code{background:var(--purple-soft);padding:1px 5px;border-radius:5px;font-size:12px}
"""


PROJ_WINDOW = 21         # days of history the projection is drawn from
PROJ_HORIZON = 14        # days projected forward
PROJ_PATHS = 4000        # bootstrap resamples


def project(by_day: dict, today: dt.date) -> dict | None:
    """Bootstrap a range for the next PROJ_HORIZON days of 7-day pageview totals.

    Deliberately does NOT fit a trend. On this data a least-squares slope is
    statistically indistinguishable from flat (t = -0.03 and -1.34 for the two
    sites, with residual noise 67-91% of the level), so drawing a rising or
    falling line would be inventing confidence the data does not support. The
    projection therefore assumes the current daily rate continues, and the
    bands show how wide the outcome still is under that assumption.

    Bands come from resampling observed daily values rather than assuming a
    distribution: counts this small and this overdispersed are badly served by
    a normal interval, which would go negative at the low end.
    """
    days = sorted(d for d, m in by_day.items() if isinstance(m, dict))
    active = [d for d in days if (by_day[d].get("pageviews") or 0) > 0]
    if len(active) < 10:
        return None                      # not enough signal to say anything

    # Complete days only: today is still accumulating and would drag the level down.
    hist_days = [d for d in days if d < today.isoformat()][-PROJ_WINDOW:]
    obs = [int(by_day[d].get("pageviews", 0) or 0) for d in hist_days]
    if len(obs) < 10:
        return None

    rnd = random.Random(20260810)         # fixed seed: same data -> same picture
    tail = obs[-6:]                       # observed days still inside the first 7-day window
    pct = (10, 25, 50, 75, 90)
    bands: list[dict] = []
    for h in range(1, PROJ_HORIZON + 1):
        totals = []
        for _ in range(PROJ_PATHS):
            drawn = [rnd.choice(obs) for _ in range(min(h, 7))]
            keep = tail[-(7 - len(drawn)):] if len(drawn) < 7 else []
            totals.append(sum(drawn) + sum(keep))
        totals.sort()
        q = {p: totals[int(p / 100 * (len(totals) - 1))] for p in pct}
        bands.append({"day": (today + dt.timedelta(days=h)).isoformat(), **{f"p{p}": q[p] for p in pct}})

    mean = sum(obs) / len(obs)
    return {
        "bands": bands,
        "window_days": len(obs),
        "daily_mean": round(mean, 1),
        "last7": sum(obs[-7:]),
        "flat": True,
    }


def conversion_bound(by_day: dict, field: str, label: str) -> dict | None:
    """Honest statement about a metric that has never fired.

    With zero events in n trials there is no rate to project, but there is a
    real upper bound: the rule of three puts the 95% limit at 3/n. Reporting
    that is defensible; extrapolating a sales figure from no sales is not.
    """
    days = [d for d, m in by_day.items() if isinstance(m, dict)]
    events = sum(int(by_day[d].get(field, 0) or 0) for d in days)
    views = sum(int(by_day[d].get("pageviews", 0) or 0) for d in days)
    if views < 30:
        return None
    return {
        "label": label, "events": events, "views": views,
        "upper95": round(3.0 / views * 100, 2) if events == 0 else None,
        "rate": round(events / views * 100, 2) if events else None,
    }


def bounds_note(bounds: list[dict]) -> str:
    """State what a never-fired metric can and cannot support.

    A conversion that has never happened has no rate to forecast. The rule of
    three still gives a real 95% ceiling from the pageviews observed, which is
    a defensible statement; a projected sales figure would not be.
    """
    parts = []
    for b in bounds:
        if b["events"] == 0:
            parts.append(
                f"No {html.escape(b['label'])} yet in {b['views']} pageviews, so there is no rate to "
                f"project. That sample does put the true rate below "
                f"<strong>{b['upper95']}%</strong> (95% confidence); it cannot narrow it further "
                f"until one happens.")
        else:
            parts.append(
                f"{b['events']} {html.escape(b['label'])} in {b['views']} pageviews "
                f"({b['rate']}%).")
    return f"<p class='bound'>{' '.join(parts)}</p>" if parts else ""


def fan_chart(spark: list[dict], proj: dict | None) -> str:
    """Observed 7-day totals, then the projected range. One shared scale."""
    if not proj:
        return ""
    hist = []
    pv = [d["pv"] for d in spark]
    for i in range(len(pv)):
        window = pv[max(0, i - 6):i + 1]
        hist.append(sum(window))
    hist = hist[:-1] or hist              # drop today (partial)
    bands = proj["bands"]

    n_h, n_p = len(hist), len(bands)
    total = n_h + n_p
    peak = max(hist + [b["p90"] for b in bands] + [1])
    X = lambda i: i / (total - 1) * 100
    Y = lambda v: 100 - (v / peak) * 100

    def area(lo_key, hi_key):
        top = " ".join(f"{X(n_h - 1 + 1 + i):.2f},{Y(b[hi_key]):.2f}" for i, b in enumerate(bands))
        bot = " ".join(f"{X(n_h - 1 + 1 + i):.2f},{Y(b[lo_key]):.2f}" for i, b in reversed(list(enumerate(bands))))
        join = f"{X(n_h - 1):.2f},{Y(hist[-1]):.2f} " if hist else ""
        return f"<polygon points='{join}{top} {bot}'/>"

    hist_line = " ".join(f"{X(i):.2f},{Y(v):.2f}" for i, v in enumerate(hist))
    med_line = (f"{X(n_h - 1):.2f},{Y(hist[-1]):.2f} " if hist else "") + \
               " ".join(f"{X(n_h + i):.2f},{Y(b['p50']):.2f}" for i, b in enumerate(bands))
    last = bands[-1]
    return f"""
    <div class="fan">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img"
           aria-label="Observed 7-day pageview totals followed by a projected range for the next {n_p} days">
        <g class="band90">{area('p10','p90')}</g>
        <g class="band50">{area('p25','p75')}</g>
        <polyline class="hist" points="{hist_line}"/>
        <polyline class="med" points="{med_line}"/>
        <line class="now" x1="{X(n_h - 1):.2f}" y1="0" x2="{X(n_h - 1):.2f}" y2="100"/>
      </svg>
      <div class="fan-x"><span>observed</span><span>projected &rarr; {last['day'][5:]}</span></div>
      <p class="fan-note">In {n_p} days, 7-day pageviews land between
        <strong>{last['p10']} and {last['p90']}</strong> in 8 runs out of 10,
        centred on {last['p50']}. Drawn by resampling the last
        {proj['window_days']} complete days ({proj['daily_mean']}/day average).
        <strong>No trend is assumed</strong>, because none is statistically
        detectable here. So the centre line drifts toward that average rather
        than continuing the current week: it reads
        {"down" if last['p50'] < proj['last7'] else "up"} from {proj['last7']}
        only because this week sits
        {"above" if last['p50'] < proj['last7'] else "below"} the 21-day
        average, not because a {"decline" if last['p50'] < proj['last7'] else "rise"}
        has been measured. Treat the band, not the line, as the finding.</p>
    </div>"""


def sparkline(spark: list[dict]) -> str:
    peak = max((d["pv"] for d in spark), default=0) or 1
    n = len(spark)
    gap, w = 3, 100 / n
    bars = []
    for i, d in enumerate(spark):
        h = (d["pv"] / peak) * 100
        h = max(h, 1.5) if d["pv"] else 0.8
        cls = " class='today'" if i == n - 1 else ""
        bars.append(
            f"<rect{cls} x='{i * w + gap / 2:.2f}' y='{100 - h:.2f}' "
            f"width='{w - gap:.2f}' height='{h:.2f}' rx='1.2'>"
            f"<title>{d['day']}: {d['pv']} pageviews</title></rect>"
        )
    return (
        "<div class='spark'><svg viewBox='0 0 100 100' preserveAspectRatio='none'>"
        + "".join(bars)
        + f"</svg><div class='spark-x'><span>{spark[0]['day'][5:]}</span>"
        f"<span>{spark[-1]['day'][5:]} (today)</span></div></div>"
    )


def funnel(s: dict) -> str:
    """Pageviews to the action that matters, as a rate rather than a count.

    A raw count of tool runs says nothing about whether the traffic is
    converting. Two runs off five visits and two off five hundred are
    different problems.
    """
    steps = [{"label": "pageviews (7d)", "value": s["last7"], "rate": None}]
    for sec in s["secondaries"]:
        rate = (sec["value"] / s["last7"] * 100) if s["last7"] else None
        steps.append({"label": sec["label"], "value": sec["value"], "rate": rate,
                      "delta": sec["value"] - sec["prior"] if sec["comparable"] else None})

    cells = ""
    for st in steps:
        rate = f"<span class='fr'>{st['rate']:.1f}% of visits</span>" if st.get("rate") is not None else ""
        d = st.get("delta")
        if d is None:
            trend = ""
        elif d > 0:
            trend = f"<span class='delta up'>&#9650; {d}</span>"
        elif d < 0:
            trend = f"<span class='delta down'>&#9660; {abs(d)}</span>"
        else:
            trend = "<span class='delta flat'>=</span>"
        cells += (f"<div class='fstep'><span class='fn'>{st['value']}{trend}</span>"
                  f"<span class='fl'>{html.escape(st['label'])}</span>{rate}</div>")
    return (f"<div class='card'><h2 style='margin-top:0'>Conversion</h2>"
            f"<div class='funnel'>{cells}</div>"
            f"<p class='fnote'>Arrows compare with the previous 7 days. "
            f"Rates are share of pageviews, not unique visitors.</p></div>")


def gsc_card(g: dict) -> str:
    """Headline Search Console figures.

    Impressions and position are the useful pair here: position says whether
    Google ranks the site at all, impressions say whether anyone is searching
    for what it ranks for. Clicks alone can't separate those.
    """
    return (
        f"<div class='card'><h2 style='margin-top:0'>Google Search</h2>"
        f"<div class='row'>"
        f"<div><span class='n'>{g['clicks']}</span><span class='l'>clicks</span></div>"
        f"<div><span class='n'>{g['impressions']}</span><span class='l'>impressions</span></div>"
        f"<div><span class='n'>{g['ctr']:.1f}%</span><span class='l'>CTR</span></div>"
        f"<div><span class='n'>{g['position']:.1f}</span><span class='l'>avg position</span></div>"
        f"</div>"
        f"<p class='fnote'>{html.escape(g['start'])} to {html.escape(g['end'])}. "
        f"Search Console lags about two days, so this window ends before the "
        f"beacon figures above.</p></div>")


def gsc_table(title: str, rows: list[dict], empty: str) -> str:
    """Query/page table carrying impressions and position, not just clicks.

    At this traffic level clicks are mostly zero, so a clicks-only table would
    render as a column of noughts and say nothing.
    """
    if not rows:
        return (f"<div class='card'><h2 style='margin-top:0'>{html.escape(title)}</h2>"
                f"<p style='color:var(--muted);font-size:14px;margin:0'>{html.escape(empty)}</p></div>")
    body = "".join(
        f"<tr><td class='k'>{html.escape(str(r['key']))}</td>"
        f"<td class='num'>{r['count']}</td>"
        f"<td class='num'>{r['impressions']}</td>"
        f"<td class='num'>{r['position']}</td></tr>"
        for r in rows
    )
    return (f"<div class='card'><h2 style='margin-top:0'>{html.escape(title)}</h2>"
            f"<table><thead><tr><th></th><th class='num'>clicks</th>"
            f"<th class='num'>impr.</th><th class='num'>pos.</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


def table(title: str, rows: list[dict], empty: str) -> str:
    if not rows:
        return (f"<div class='card'><h2 style='margin-top:0'>{html.escape(title)}</h2>"
                f"<p style='color:var(--muted);font-size:14px;margin:0'>{html.escape(empty)}</p></div>")
    body = "".join(
        f"<tr><td class='k'>{html.escape(str(r['key']))}</td>"
        f"<td class='num'>{r['count']}</td></tr>"
        for r in rows
    )
    return (f"<div class='card'><h2 style='margin-top:0'>{html.escape(title)}</h2>"
            f"<table><tbody>{body}</tbody></table></div>")


def site_card(s: dict) -> str:
    if s["delta_pct"] is None:
        delta = ""  # no honest comparison available; don't imply one
    elif s["delta_pct"] > 0:
        delta = f"<span class='delta up'>&#9650; {s['delta_pct']}%</span>"
    elif s["delta_pct"] < 0:
        delta = f"<span class='delta down'>&#9660; {abs(s['delta_pct'])}%</span>"
    else:
        delta = "<span class='delta flat'>flat</span>"

    err = (f"<p style='color:var(--bad);font-size:13px;margin:0 0 12px'>"
           f"Live fetch failed this run — showing archived data.</p>") if s.get("error") else ""

    return f"""
    <div class="card">
      {err}
      <p class="site-name">{html.escape(s['label'])}</p>
      <p class="site-dom">{html.escape(s['domain'])}</p>
      <div><span class="big">{s['last7']}</span>{delta}</div>
      <div class="big-label">pageviews, last 7 complete days</div>
      <div class="row">
        <div><span class="n">{s['today']}</span><span class="l">today so far</span></div>
        <div><span class="n">{s['uniques7']}</span><span class="l">visitors (7d)</span></div>
        {"".join(f'<div><span class="n">{sec["value"]}</span>'
                 f'<span class="l">{html.escape(sec["label"])} (7d)</span></div>'
                 for sec in s['secondaries'])}
        <div><span class="n">{s['last30']}</span><span class="l">last 30 days</span></div>
        <div><span class="n">{s['all_time']}</span><span class="l">tracked total</span></div>
      </div>
      {sparkline(s['spark'])}
      {fan_chart(s['spark'], s.get('proj'))}
      {bounds_note(s.get('bounds') or [])}
    </div>"""


def render(summaries: list[dict], obs: list[str], generated: str, first_day: str | None) -> str:
    cards = "".join(site_card(s) for s in summaries)
    obs_html = "".join(f"<li>{html.escape(o)}</li>" for o in obs) or "<li>No data yet.</li>"

    tables = ""
    for s in summaries:
        # Everything below the Conversion card comes from the live payload,
        # which is a 30-day window — say so, rather than letting it sit next to
        # 7-day headline numbers looking like the same period.
        tables += (f"<h2>{html.escape(s['label'])} — detail "
                   f"<span class='win'>· last {FETCH_DAYS} days</span></h2><div class='tables'>")
        tables += funnel(s)
        tables += table("Channels", s["channels"], "No traffic recorded in this window.")
        if s.get("gsc"):
            tables += gsc_card(s["gsc"])
            tables += gsc_table("Search queries", s["gsc"]["queries"],
                                "No queries returned for this window.")
            tables += gsc_table("Search landing pages", s["gsc"]["pages"],
                                "No pages returned for this window.")
        tables += table("Top pages", s["top_paths"], "No pages recorded in this window.")
        tables += table("Top referrers", s["top_referrers"], "No external referrers recorded.")
        # Render these even when empty. "No tool runs at all this week" is a
        # finding; a silently absent table reads as "not measured".
        sec_keys = {sec["key"] for sec in s["secondaries"]}
        if "toolRuns" in sec_keys:
            tables += table("Tool runs, by tool", s["tool_runs"],
                            "No tool was run this week.")
        if "calcRuns" in sec_keys:
            tables += table("Calculator runs, by tool", s["calc_runs"],
                            "No calculator was run this week.")
        if "signups" in sec_keys or s["form_breakdown"]:
            tables += table("Waitlist signups", s["form_breakdown"], "None this week.")
        if s["top_utm"] and not (s["tool_runs"] or s["calc_runs"]):
            tables += table("Campaign sources", s["top_utm"], "None recorded.")
        tables += "</div>"

    since = f" Tracking since {first_day}." if first_day else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Traffic — Purplelink &amp; MuscleOnGLP</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>Traffic</h1>
  <p class="stamp">Updated {html.escape(generated)} · refreshes daily at 9:00am</p>
</header>
<div class="grid">{cards}</div>
<h2>What this says</h2>
<ul class="obs">{obs_html}</ul>
{tables}
<footer>
  First-party, cookieless analytics from each site's own beacon — no third-party
  vendor, Do Not Track honoured, so these counts are conservative and exclude
  visitors who opt out.{html.escape(since)}
  Daily figures are archived to <code>~/.purplelink/traffic/history.json</code>,
  which keeps growing even if the source window rolls off.
</footer>
</div></body></html>"""


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--open", action="store_true", help="open the dashboard when done")
    ap.add_argument("--no-fetch", action="store_true", help="re-render from the archive only")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    history = load_history()

    if not args.no_fetch:
        for site in SITES:
            token = cfg.get(site["token_env"])
            entry = history["sites"].setdefault(site["key"], {"byDay": {}, "snapshots": {}})
            if not token:
                entry["error"] = f"{site['token_env']} not set"
                print(f"  ! {site['label']}: {site['token_env']} not set in {CONFIG_PATH}",
                      file=sys.stderr)
                continue
            try:
                payload = fetch_site(site, token)
                if payload.get("error"):
                    raise RuntimeError(payload.get("detail") or payload["error"])

                # Fold Netlify Forms signups into the same per-day shape the
                # stats endpoint returns, so every downstream metric, table and
                # observation treats them like any other counter.
                forms_note = ""
                if site.get("netlify_site_id"):
                    nt = _netlify_token()
                    if nt:
                        try:
                            by_day, per_form = fetch_form_signups(site["netlify_site_id"], nt)
                            payload.setdefault("byDay", {})
                            for day, n in by_day.items():
                                payload["byDay"].setdefault(day, {})["signups"] = n
                            payload["formBreakdown"] = per_form
                            total = sum(by_day.values())
                            forms_note = f", {total} waitlist signup(s)"
                        except Exception as exc:
                            print(f"  ! {site['label']}: form fetch failed ({str(exc)[:60]})",
                                  file=sys.stderr)
                    else:
                        print(f"  ! {site['label']}: no Netlify token; skipping waitlists",
                              file=sys.stderr)

                merge_history(history, site["key"], payload)
                entry.pop("error", None)
                print(f"  ok {site['label']}: {payload.get('totals', {}).get('pageviews', 0)} "
                      f"pageviews in last {FETCH_DAYS}d{forms_note}")

                # Search Console is a separate, optional source. Stored on the
                # archive entry so a later --no-fetch re-render still shows the
                # last known search numbers instead of dropping the section.
                gsc = fetch_gsc(site)
                if gsc and not gsc.get("error"):
                    entry["gsc"] = gsc
                    print(f"     search: {gsc['clicks']} clicks, "
                          f"{gsc['impressions']} impressions, pos {gsc['position']:.1f}")
                elif gsc:
                    print(f"  ! {site['label']}: Search Console unavailable "
                          f"({gsc['error'][:80]})", file=sys.stderr)
            except (OSError, http.client.HTTPException, RuntimeError, ValueError) as exc:
                entry["error"] = str(exc)[:120]
                print(f"  ! {site['label']} fetch failed: {exc}", file=sys.stderr)

        history["lastRun"] = dt.datetime.now(dt.timezone.utc).isoformat()
        HISTORY_PATH.write_text(json.dumps(history, indent=1, sort_keys=True))

    summaries = [summarise(s, history["sites"].get(s["key"], {})) for s in SITES]
    obs = observations(summaries)
    firsts = [s["first_day"] for s in summaries if s["first_day"]]
    generated = dt.datetime.now().strftime("%a %d %b %Y, %-I:%M%p").replace("AM", "am").replace("PM", "pm")

    DASHBOARD_PATH.write_text(render(summaries, obs, generated, min(firsts) if firsts else None))

    # Terminal summary, so a manual run is useful without opening a browser.
    print(f"\n  Traffic — {generated}")
    for s in summaries:
        d = "" if s["delta_pct"] is None else f"  ({s['delta_pct']:+d}% WoW)"
        print(f"   {s['label']:<16} {s['last7']:>4} pv/7d{d}   today {s['today']}")
    print()
    for o in obs:
        print(f"   - {o}")
    print(f"\n  {DASHBOARD_PATH}")

    if args.open:
        subprocess.run(["open", str(DASHBOARD_PATH)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
