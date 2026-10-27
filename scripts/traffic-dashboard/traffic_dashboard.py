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
    STRIPE_EXTPAY_KEY=rk_live_...   # optional: restricted read-only key (Charges, Subscriptions) for the Stripe account ExtensionPay charges through
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import http.client
import json
import os
import random
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "purplelink" / "traffic.env"
OUT_DIR = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
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
    # The ModernTex 7-day trial shipped with 1.0.2; stats.mjs backfills the
    # counter with zeros for every earlier day.
    ("purplelink", "trialDownloads"): "2026-09-11",
    # Vitae moved behind the counted vitae-download function on this day; before
    # it the DMG was a static file and no download was ever recorded.
    ("purplelink", "vitaeDownloads"): "2026-09-22",
}

# Events we generated ourselves. The beacon cannot tell a verification click
# from a customer's, so they are subtracted here rather than left to be read as
# audience behaviour. history.json keeps the raw counts; only the analysis is
# adjusted, and the entry stops mattering once the day rolls out of the window.
#
# Add one when you exercise a paid path in production, and say why.
SYNTHETIC_EVENTS = {
    ("purplelink", "checkoutClicks", "2026-09-05"): {
        "count": 8,
        "why": "buy-button verification after the 2026-09-04 fix: one click on "
               "/moderntex/ plus the four kits, both paper-review pages and "
               "/tools/cover-letter/",
    },
    ("purplelink", "vitaeDownloads", "2026-09-22"): {
        "count": 1,
        "why": "verifying the counter right after Vitae moved behind vitae-download",
    },
    ("muscleonglp", "checkoutClicks", "2026-09-09"): {
        "count": 1,
        "why": "verifying the checkout+track pipeline still worked while "
               "investigating why weekly checkout clicks read zero",
    },
}


def without_synthetic(site_key: str, by_day: dict) -> tuple[dict, list[dict]]:
    """by_day with our own test events removed, plus what was removed.

    Applied once, here, so every downstream number — the 7-day counters, the
    checkout rate, the lifetime bound, the sparkline — is computed from the
    same corrected series. Patching each call site instead would eventually
    miss one and report two different figures for the same metric.
    """
    entries = [(k, v) for k, v in SYNTHETIC_EVENTS.items() if k[0] == site_key]
    if not entries:
        return by_day, []
    adjusted = {day: dict(metrics) for day, metrics in by_day.items()}
    applied = []
    for (_site, metric, day), entry in entries:
        if day not in adjusted:
            continue
        raw = int(adjusted[day].get(metric, 0) or 0)
        removed = min(raw, entry["count"])       # never subtract past zero
        if not removed:
            continue
        adjusted[day][metric] = raw - removed
        applied.append({"metric": metric, "day": day, "removed": removed,
                        "raw": raw, "why": entry["why"]})
    return adjusted, applied

SITES = [
    {
        "key": "purplelink",
        "label": "Purplelink LLC",
        "domain": "purplelink.llc",
        "url": "https://purplelink.llc/.netlify/functions/stats",
        "token_env": "PURPLELINK_STATS_TOKEN",
        # (json key in byDay, display label) — engagement metrics beyond a visit
        "secondaries": [("toolRuns", "tool runs"),
                        ("haeaSignups", "haea waitlist signups"),
                        ("moderntexReleaseSignups", "ModernTex release-notes signups"),
                        ("trialDownloads", "trial downloads"),
                        ("ovTrialDownloads", "Outbound Veil trial downloads"),
                        ("lgTrialDownloads", "Legroom trial downloads"),
                        ("kfTrialDownloads", "Keyfeel trial downloads"),
                        ("tfTrialDownloads", "Tapefolio trial downloads"),
                        ("pnTrialDownloads", "Panely trial downloads"),
                        ("smTrialDownloads", "Summonly trial downloads"),
                        ("vitaeDownloads", "Vitae downloads"),
                        ("checkoutClicks", "checkout clicks")],
        # Paths that actually show a buy button. The useful denominator for a
        # checkout rate is "people who reached a page where buying was possible",
        # not all pageviews: /kits/clip-pipeline/ drew 24 views in a month and
        # produced no Stripe session at all, and against sitewide traffic that
        # signal disappears into the noise.
        #
        # Exact paths, not prefixes. The first version used ("/kits/",
        # "/tools/paper-review/") and silently excluded the five adjacent paid
        # tools, which have buy buttons of their own. Prefixes are also unsafe
        # here in principle: muscleonglp sells from its homepage, and "/" as a
        # prefix matches the whole site.
        #
        # Derived from the markup, not from memory:
        #   grep -rl 'id="checkout-btn"\|pr-checkout-btn' site --include=index.html
        # Re-run that when a paid page is added or removed.
        "product_paths": (
            "/kits/", "/kits/clip-pipeline/", "/kits/faceless-content-pipeline/",
            "/kits/monetization-stack/",
            "/tools/paper-review/", "/tools/paper-review/packs/",
            "/tools/paper-review/revision/", "/tools/anonymity-check/",
            "/tools/citation-gap/", "/tools/cover-letter/",
            "/tools/response-review/", "/tools/resume-review/",
            # ModernTex was missing here even though its page has always carried
            # a checkout button (pr-checkout-btn, data-product="moderntex") —
            # found 2026-09-13 while checking the checkout wiring. Its ~250+
            # weekly pageviews were silently excluded from the denominator the
            # whole time, so the site-wide checkout rate was overstated.
            "/moderntex/",
            # Outbound Veil: buy button (pr-checkout-btn, data-product="outbound-veil"), added 2026-10-04.
            "/outbound-veil/",
            # Legroom: buy button (pr-checkout-btn, data-product="legroom").
            "/legroom/",
            # Keyfeel: buy button (pr-checkout-btn, data-product="keyfeel").
            "/keyfeel/",
            # Tapefolio: buy button (pr-checkout-btn, data-product="tapefolio").
            "/tapefolio/",
            # Panely and Summonly: buy buttons (pr-checkout-btn, data-product="panely" and "summonly").
            "/panely/",
            "/summonly/",
        ),
        # Waitlists are Netlify Forms, so they never reach the analytics beacon.
        # Without this they read as zero while people are actually signing up.
        "netlify_site_id": "b264591f-fbbe-4048-9d9d-7051cf497823",
        # Netlify form name -> byDay metric key, one entry per form that is
        # still a live funnel worth its own weekly line (see "secondaries"
        # above). A form Netlify keeps listing after its page drops the
        # <form> — e.g. waitlist-globepin, retired when the app shipped to
        # the App Store on 2026-09-03, or the original waitlist-moderntex,
        # retired when the real trial/buy flow replaced it around 2026-09-11
        # — is deliberately left out here: it would otherwise report a
        # permanent "zero signups" for a step that no longer exists instead
        # of just not being asked about. It still shows up, at its true
        # all-time count, in the "Signup forms" detail table.
        "signup_forms": {
            "waitlist-haea": "haeaSignups",
            "moderntex-releases": "moderntexReleaseSignups",
        },
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
        # Same derivation, via the [data-checkout] binding in checkout.js:
        #   grep -rl 'checkout\.js' muscleonglp-site --include=index.html
        # The homepage is on this list because it carries two buy buttons
        # (complete-pack and muscleonglp-guide). Leaving it out is what made the
        # first real sale, on 2026-09-01, divide by three unrelated views and
        # report a meaningless 33.3%.
        "product_paths": (
            "/", "/guides/", "/guides/creatine-glp1/", "/guides/no-gym-plan/",
            "/guides/off-ramp/", "/guides/protein-playbook/",
            "/guides/tracker/", "/guides/workbook/",
        ),
        "gsc_property": "sc-domain:getmuscleonglp.com",
    },
    {
        # RubbleFront (rubblefront.com, the Frontlink game's site). Its analytics.js beacons to Purplelink's collector with
        # h="rubblefront.com", so its records sit in the same store; stats.mjs keeps them out of Purplelink's own numbers
        # and returns them alone for ?host=rubblefront.com. Same stats token. No Search Console property is set here yet.
        "key": "rubblefront",
        "label": "RubbleFront",
        "domain": "rubblefront.com",
        "url": "https://purplelink.llc/.netlify/functions/stats",
        "stats_host": "rubblefront.com",
        "token_env": "PURPLELINK_STATS_TOKEN",
        "secondaries": [("steamClicks", "Steam clicks"), ("outboundClicks", "outbound clicks"),
                        ("downloads", "downloads"), ("newsletterSubmits", "newsletter signups")],
        # Domain property (verified 2026-10-12 by a DNS TXT record), so the sc-domain: form. Little data for the first days.
        # The service account must be a user on the property; a 403 here means it is not, and is non-fatal.
        "gsc_property": "sc-domain:rubblefront.com",
    },
]

# Service-account key for the Search Console API. Absent on a machine that has
# not been set up; the dashboard degrades to beacon-only rather than failing.
GSC_KEY_PATH = Path.home() / ".config" / "purplelink" / "gsc.json"
GSC_DAYS = 28            # GSC's own default reporting window
GSC_LAG_DAYS = 2         # Search Console data is ~48h behind; asking for
                         # yesterday returns zeros and reads as a traffic drop.

# AdMob (in-app ad revenue). Unlike Search Console, AdMob has no
# service-account path at all -- Google requires a real signed-in user's
# OAuth consent for AdMob account access, service accounts cannot be granted
# access to an AdMob account. The one-time setup (2026-09-25) authorized this
# script via a Desktop-app OAuth client in the same GCP project as the GSC
# service account (bampelvisitortrack), and the resulting refresh token
# (which does not expire, since that project's OAuth consent screen is
# "In production", not "Testing") lives at ADMOB_TOKEN_PATH. Absent on a
# machine that has not been set up; degrades to no card, same as GSC.
ADMOB_TOKEN_PATH = Path.home() / ".config" / "purplelink" / "admob-refresh-token.json"
ADMOB_APPS = {
    "globepin": {"label": "GlobePin", "publisherId": "pub-6407975157274256",
                 "appId": "ca-app-pub-6407975157274256~3074958691"},
}
ADMOB_DAYS = 7  # matches the Apple Search Ads manual reading, for a fair spend-vs-earnings comparison
PRODUCT_PAGE_PATHS = {"/moderntex", "/outbound-veil", "/legroom", "/keyfeel", "/tapefolio", "/panely", "/summonly", "/vitae", "/suite"}
AD_FUNNEL_DAYS = 7  # window for the first-touch channel funnel (adFunnel in history.json)


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


def fetch_site(site: dict, token: str, days: int | None = None) -> dict:
    """Fetch one site's stats, retrying transient failures.

    A single 502 used to drop the whole site to archived figures for the day,
    which is what happened on 2026-08-14: the stats function was timing out
    because it read one blob per event serially. That cause is fixed, but a
    cold start or a Netlify blip can still produce one bad response, and this
    job runs once a day, so there is no reason to give up on the first try.
    Only transient conditions are retried; a 401 means the token is wrong and
    retrying it would just be slower.
    """
    url = f"{site['url']}?token={urllib.parse.quote(token)}&days={days or FETCH_DAYS}"
    # A site that shares the collector with Purplelink asks for its own records (stats.mjs ?host=); without
    # this the shared endpoint answers with Purplelink's numbers only.
    if site.get("stats_host"):
        url += f"&host={urllib.parse.quote(site['stats_host'])}"
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


SALES_URL = "https://purplelink.llc/.netlify/functions/sales"
# Both sites sell through one Stripe account, so a single call covers them
# both; the endpoint splits by product. It reuses purplelink's stats token.
SALES_TOKEN_ENV = "PURPLELINK_STATS_TOKEN"


def fetch_sales(token: str) -> dict | None:
    """Revenue for both sites, or None when it cannot be read.

    Sales are the point of the whole exercise, but they are still only one
    panel: a Stripe outage must not cost us the traffic report, so every
    failure here degrades to None and the dashboard renders without it.
    """
    url = f"{SALES_URL}?token={urllib.parse.quote(token)}&days={FETCH_DAYS}"
    req = urllib.request.Request(url, headers={"User-Agent": "purplelink-traffic-dashboard"})
    last: Exception | None = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("error"):
                raise RuntimeError(payload.get("detail") or payload["error"])
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                print(f"  ! sales: HTTP {exc.code}", file=sys.stderr)
                return None
            last = exc
        except (OSError, http.client.HTTPException, json.JSONDecodeError, RuntimeError) as exc:
            last = exc
    print(f"  ! sales unavailable: {str(last)[:80]}", file=sys.stderr)
    return None


# --- ModernTex in-app updates (Sparkle) -------------------------------------
#
# Distinct from the site's own trial/purchase download beacon: this counts
# ModernTex's own auto-updater asking for a new version, i.e. existing users
# updating, not new customers arriving. The endpoint
# (netlify/functions/moderntex-download.mjs, ?stats=1) is a plain lifetime
# counter per DMG filename with no per-day breakdown, so a daily figure has
# to be derived here by diffing today's snapshot against the most recent one
# already archived — see merge_sparkle_updates below.
MODERNTEX_STATS_URL = "https://purplelink.llc/.netlify/functions/moderntex-download"
MODERNTEX_UPDATE_TOKEN_ENV = "MODERNTEX_UPDATE_TOKEN"


def fetch_sparkle_updates(token: str) -> dict | None:
    """Cumulative Sparkle update-download counts by DMG filename, or None.

    Same non-fatal-degrade contract as fetch_sales: an outage here must not
    cost us the rest of the daily run.
    """
    req = urllib.request.Request(
        MODERNTEX_STATS_URL + "?stats=1",
        headers={"User-Agent": "purplelink-traffic-dashboard", "X-ModernTex-Channel": token},
    )
    last: Exception | None = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("error"):
                raise RuntimeError(payload.get("detail") or payload["error"])
            return payload.get("downloads", {})
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                print(f"  ! sparkle updates: HTTP {exc.code}", file=sys.stderr)
                return None
            last = exc
        except (OSError, http.client.HTTPException, json.JSONDecodeError, RuntimeError) as exc:
            last = exc
    print(f"  ! sparkle updates unavailable: {str(last)[:80]}", file=sys.stderr)
    return None


# --- Vitae downloads -----------------------------------------------------------
#
# Vitae is free and served through netlify/functions/vitae-download.mjs, which
# counts every non-crawler GET both per file and per UTC day. Unlike the Sparkle
# counter above it has a real per-day series, so it is folded straight into the
# purplelink byDay archive as the "vitaeDownloads" metric.
VITAE_STATS_URL = "https://purplelink.llc/.netlify/functions/vitae-download"
VITAE_STATS_TOKEN_ENV = "VITAE_STATS_TOKEN"
PURPLELINK_SITE_ID = "b264591f-fbbe-4048-9d9d-7051cf497823"


def blobs_read(store: str, prefix: str) -> dict[str, int]:
    """{key minus prefix: integer value} for one prefix of a purplelink.llc site Blobs store,
    read with the Netlify CLI's own token. Raises OSError-family or ValueError on failure.
    Used where the matching *_TOKEN header is a write-only Netlify secret with no local
    copy: reading the store directly needs no secret and nothing to rotate."""
    token = _netlify_token()
    if not token:
        raise OSError("no Netlify CLI token")
    base = f"https://api.netlify.com/api/v1/blobs/{PURPLELINK_SITE_ID}/site:{store}"
    hdr = {"Authorization": f"Bearer {token}", "User-Agent": "purplelink-traffic-dashboard"}

    def get(url: str) -> bytes:
        with urllib.request.urlopen(urllib.request.Request(url, headers=hdr),
                                    timeout=TIMEOUT, context=_ssl_context()) as r:
            return r.read()

    out: dict[str, int] = {}
    listing = json.loads(get(f"{base}?prefix={urllib.parse.quote(prefix, safe=':')}").decode("utf-8"))
    for b in listing.get("blobs", []):
        raw = get(f"{base}/{urllib.parse.quote(b['key'], safe=':')}").decode("utf-8").strip()
        out[b["key"][len(prefix):]] = int(raw or 0)
    return out


def fetch_vitae_downloads_blobs() -> dict | None:
    """Same shape as fetch_vitae_downloads, read from the vitae-stats store (downloads: and day: keys)
    when VITAE_STATS_TOKEN is not set."""
    try:
        return {"downloads": blobs_read("vitae-stats", "downloads:"), "byDay": blobs_read("vitae-stats", "day:")}
    except (OSError, http.client.HTTPException, ValueError) as exc:
        print(f"  ! Vitae downloads (Blobs) unavailable: {str(exc)[:80]}", file=sys.stderr)
        return None


def fetch_sparkle_updates_blobs() -> dict | None:
    """Same shape as fetch_sparkle_updates, read from the moderntex-stats store when
    MODERNTEX_UPDATE_TOKEN is not set. That token is compiled into the shipped app, so it is read
    around, never rotated."""
    try:
        return blobs_read("moderntex-stats", "downloads:")
    except (OSError, http.client.HTTPException, ValueError) as exc:
        print(f"  ! ModernTex in-app updates (Blobs) unavailable: {str(exc)[:80]}", file=sys.stderr)
        return None


# --- Panely and Summonly: downloads served and in-app updates ---------------------
#
# The two download functions count every served download in their own stats store: "public:<file>"
# (the trial download), "buyer:<file>" (a purchase download), "day:<date>:<kind>" (per UTC day) and
# "downloads:<file>" (Sparkle updates, one counter per version). They are requests handed the file,
# not confirmed installs. Read straight from the Blobs store with the Netlify CLI's token, so no
# update-channel secret has to be kept locally.
APP_STATS_STORES = {"panely": "panely-stats", "summonly": "summonly-stats"}


def fetch_app_stats_blobs(app: str) -> dict | None:
    store = APP_STATS_STORES[app]
    try:
        by_day: dict[str, dict[str, int]] = {}
        for key, n in blobs_read(store, "day:").items():
            day, _, kind = key.partition(":")
            if kind in ("public", "buyer"):
                by_day.setdefault(day, {"public": 0, "buyer": 0})[kind] = n
        return {"updates": blobs_read(store, "downloads:"), "public": blobs_read(store, "public:"),
                "buyer": blobs_read(store, "buyer:"), "byDay": by_day,
                "fetchedAt": dt.datetime.now(dt.timezone.utc).isoformat()}
    except (OSError, http.client.HTTPException, ValueError) as exc:
        print(f"  ! {app} download counters (Blobs) unavailable: {str(exc)[:80]}", file=sys.stderr)
        return None


def app_stats_summary(entry: dict | None, today: dt.date | None = None) -> dict | None:
    """Totals from one app's stored counters: public and buyer downloads (all time, last 7 complete days,
    today) and in-app updates by version."""
    if not entry:
        return None
    today = today or dt.date.today()
    by_day = entry.get("byDay") or {}
    last7 = [(today - dt.timedelta(days=i)).isoformat() for i in range(1, 8)]
    pub7 = sum((by_day.get(d) or {}).get("public", 0) for d in last7)
    buy7 = sum((by_day.get(d) or {}).get("buyer", 0) for d in last7)
    t = by_day.get(today.isoformat()) or {}
    return {"publicAll": sum((entry.get("public") or {}).values()), "buyerAll": sum((entry.get("buyer") or {}).values()),
            "public7": pub7, "buyer7": buy7, "publicToday": t.get("public", 0), "buyerToday": t.get("buyer", 0),
            "updates": dict(sorted((entry.get("updates") or {}).items())), "updatesAll": sum((entry.get("updates") or {}).values()),
            "firstDay": min(by_day) if by_day else None}


def fetch_vitae_downloads(token: str) -> dict | None:
    """{"downloads": {file: lifetime}, "byDay": {date: n}} or None on failure."""
    req = urllib.request.Request(
        VITAE_STATS_URL + "?stats=1",
        headers={"User-Agent": "purplelink-traffic-dashboard", "X-Vitae-Stats": token},
    )
    last: Exception | None = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("error"):
                raise RuntimeError(payload.get("detail") or payload["error"])
            return {"downloads": payload.get("downloads", {}), "byDay": payload.get("byDay", {})}
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                print(f"  ! Vitae downloads: HTTP {exc.code}", file=sys.stderr)
                return None
            last = exc
        except (OSError, http.client.HTTPException, json.JSONDecodeError, RuntimeError) as exc:
            last = exc
    print(f"  ! Vitae downloads unavailable: {str(last)[:80]}", file=sys.stderr)
    return None


def merge_sparkle_updates(history: dict, by_file: dict) -> dict:
    """Snapshot today's cumulative counts and derive a day-over-day delta.

    The endpoint has no per-day breakdown, so "updates downloaded today"
    comes from diffing this snapshot against the most recently archived one
    — an odometer reading turned into a daily distance by subtracting
    yesterday's total. A total that goes backward (an old version's counter
    pruned from Blobs, or any other anomaly) is floored at 0 rather than
    reported as a negative count.
    """
    entry = history.setdefault("moderntexUpdates", {"snapshots": {}})
    snapshots = entry["snapshots"]
    today = _utc_today()
    total = sum(by_file.values())
    snapshots[today] = {"byFile": by_file, "total": total}
    entry["fetchedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()

    prior_days = sorted(d for d in snapshots if d < today)
    delta = max(0, total - snapshots[prior_days[-1]].get("total", 0)) if prior_days else None
    entry["today"] = {"total": total, "delta": delta}
    return entry


# --- MacUpdate -------------------------------------------------------------
#
# MacUpdate mirrors the DMG on its own servers, so its downloads never reach our download functions or the beacon;
# a buyer who found us there later shows up as "direct" or "from:trial". Buyer emails (2026-10-15 to 10-17) named it
# for 2 of 3 answers. The listing page states a running "Downloads" total in its server-rendered HTML; one reading a
# day is archived and the daily and weekly figures are differences between readings (an odometer, like Sparkle).
# Add an app here once its listing is live (the subdomain answers 200, not a redirect to the home page).
MACUPDATE_LISTINGS = {"moderntex": "https://moderntex.macupdate.com/"}
MACUPDATE_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"


def parse_macupdate_listing(page: str) -> dict | None:
    """{downloads, version, price} from a listing page, or None when the Downloads figure is missing."""
    def spec(title: str) -> str | None:
        m = re.search(r'specs_list_title[^"]*">\s*' + title + r'\s*</h3>\s*<p class="specs_list_description[^"]*">(.*?)</p>',
                      page, re.S)
        return re.sub(r"<[^>]+>|<!--.*?-->", "", m.group(1)).strip() if m else None
    dl = spec("Downloads")
    if dl is None or not re.fullmatch(r"[\d,]+", dl):
        return None
    ver = re.search(r"Version\s*(?:<!-- -->)?\s*([0-9][0-9A-Za-z.\-]*)", page)
    price = re.search(r'"offers":\{"@type":"Offer","price":"(\d+(?:\.\d+)?)"', page)
    return {"downloads": int(dl.replace(",", "")), "version": ver.group(1) if ver else None,
            "price": float(price.group(1)) if price else None}


def fetch_macupdate(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": MACUPDATE_UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            if r.geturl().rstrip("/") != url.rstrip("/"):
                return None  # redirected: the listing is gone or not live
            return parse_macupdate_listing(r.read().decode("utf-8", "replace"))
    except (OSError, http.client.HTTPException) as exc:
        print(f"  ! MacUpdate {url}: {str(exc)[:60]}", file=sys.stderr)
        return None


def merge_macupdate(history: dict, product: str, reading: dict, today: str | None = None) -> dict:
    entry = history.setdefault("macupdate", {}).setdefault(product, {"snapshots": {}})
    entry["snapshots"][today or _utc_today()] = reading
    entry["url"] = MACUPDATE_LISTINGS.get(product, entry.get("url"))
    return entry


def macupdate_summary(entry: dict | None, today: dt.date | None = None) -> dict | None:
    """Total, and downloads over the last 7 days from the reading 7 or more days back (None until one exists;
    then `since` says which reading the difference starts from). A total that goes down is floored at 0."""
    snaps = (entry or {}).get("snapshots") or {}
    if not snaps:
        return None
    today = today or dt.date.today()
    days = sorted(snaps)
    last = snaps[days[-1]]
    cutoff = (today - dt.timedelta(days=7)).isoformat()
    base_day = max((d for d in days if d <= cutoff), default=None)
    first_day = days[0]
    out = {"total": last["downloads"], "asOf": days[-1], "version": last.get("version"), "price": last.get("price"),
           "week": None, "sinceFirst": None, "firstDay": first_day}
    if base_day:
        out["week"] = max(0, last["downloads"] - snaps[base_day]["downloads"])
    if first_day != days[-1]:
        out["sinceFirst"] = max(0, last["downloads"] - snaps[first_day]["downloads"])
    return out


# Our own download counters per app (beacon trial clicks per day), for the all-sources view.
SITE_DOWNLOAD_METRICS = {"moderntex": "trialDownloads", "outbound-veil": "ovTrialDownloads", "legroom": "lgTrialDownloads",
                         "keyfeel": "kfTrialDownloads", "tapefolio": "tfTrialDownloads", "panely": "pnTrialDownloads",
                         "summonly": "smTrialDownloads", "vitae": "vitaeDownloads"}
APP_LABELS = {"moderntex": "ModernTex", "outbound-veil": "Outbound Veil", "legroom": "Legroom", "keyfeel": "Keyfeel",
              "tapefolio": "Tapefolio", "panely": "Panely", "summonly": "Summonly", "vitae": "Vitae"}


def downloads_all_sources(history: dict, today: dt.date | None = None) -> list[dict]:
    """One row per app: downloads from our site in the last 7 complete days, MacUpdate's over the last 7 days
    (when two readings that far apart exist) and MacUpdate's running total. GlobePin's App Store first-time
    downloads are added as their own row. Sources count different things (a click on our download link, a
    MacUpdate download, an App Store install), so they are shown side by side, never deduplicated."""
    today = today or dt.date.today()
    by_day = ((history.get("sites") or {}).get("purplelink") or {}).get("byDay") or {}
    last7 = [(today - dt.timedelta(days=i)).isoformat() for i in range(1, 8)]
    mu = history.get("macupdate") or {}
    rows = []
    for key, metric in SITE_DOWNLOAD_METRICS.items():
        site7 = sum(int((by_day.get(d) or {}).get(metric, 0) or 0) for d in last7)
        m = macupdate_summary(mu.get(key), today)
        rows.append({"app": APP_LABELS[key], "site7": site7, "mu": m})
    asd = (history.get("appstore") or {}).get("days") or {}
    if asd:
        rows.append({"app": "GlobePin (App Store)", "site7": None, "mu": None,
                     "store7": sum(int((asd.get(d) or {}).get("downloads", 0) or 0) for d in last7)})
    return rows


def print_downloads_all_sources(history: dict) -> None:
    rows = downloads_all_sources(history)
    if not rows:
        return
    print("\n  Downloads, all sources, last 7 complete days (our site = clicks on our download links, raw, link-checker clicks"
          " included; MacUpdate serves its own copy)")
    tot_site = tot_mu = 0
    for r in rows:
        if "store7" in r:
            print(f"   {r['app']:<22} App Store first-time downloads {r['store7']:>3}")
            continue
        m = r["mu"]
        tot_site += r["site7"]
        line = f"   {r['app']:<22} our site {r['site7']:>3}"
        if m:
            if m["week"] is not None:
                tot_mu += m["week"]
                line += f"   MacUpdate {m['week']:>3} ({m['total']} all time)"
            elif m["sinceFirst"] is not None:
                tot_mu += m["sinceFirst"]
                line += f"   MacUpdate {m['sinceFirst']:>3} since {m['firstDay']} ({m['total']} all time)"
            else:
                weekly_from = (dt.date.fromisoformat(m["firstDay"]) + dt.timedelta(days=7)).isoformat()
                line += f"   MacUpdate {m['total']} all time (first reading {m['asOf']}; weekly figure from {weekly_from})"
            if m.get("version"):
                line += f", listing shows {m['version']}" + (f" at ${m['price']:.2f}" if m.get("price") is not None else "")
        print(line)
    print(f"   Mac apps incl. Vitae: {tot_site} from our site, {tot_mu} from MacUpdate (where readings allow)")


def sparkle_observations(hist: dict | None) -> list[str]:
    """One bullet on ModernTex's in-app update volume — kept separate from
    the trial/purchase-download observations since it measures a different
    audience (existing owners, not prospects)."""
    if not hist or not hist.get("snapshots"):
        return []
    days = sorted(hist["snapshots"])
    latest = hist["snapshots"][days[-1]]
    total, by_file = latest.get("total", 0), latest.get("byFile", {})
    delta = hist.get("today", {}).get("delta")
    top = sorted(by_file.items(), key=lambda kv: -kv[1])[:1]
    top_note = f" (most on {top[0][0]}, {top[0][1]} lifetime)" if top and len(by_file) > 1 else ""
    if delta is None:
        return [f"ModernTex: {total} in-app update download(s) recorded so far{top_note}; "
                f"first snapshot today ({days[-1]}), no day-over-day figure yet."]
    return [f"ModernTex: {delta} in-app update download(s) in the last day, {total} lifetime{top_note}."]


# --- App Store Connect (GlobePin) ------------------------------------------
#
# Two Apple sources, archived under history["appstore"]:
#
#   Sales & Trends (daily SALES/SUMMARY report): downloads, redownloads,
#   updates, and Pro proceeds. Apple answers 404 for a day with no
#   transactions at all, so 404 is recorded as a zero day, not an error.
#   Reports for a day appear the next morning and can be revised for a few
#   days, so the last few days are always re-fetched.
#
#   Analytics Reports (the ONGOING request in ASC_ANALYTICS_REQUEST_ID):
#   impressions, product page views, sessions — what the App Store Connect
#   "Overview" page shows — and therefore conversion. Apple generates these
#   ~2-3 days behind and only from the day the request was created; there is
#   no backfill. Column names are recorded on first sight (see
#   history["appstore"]["analytics"]["headers"]) because Apple's schema is
#   only documented loosely; the panel reads whatever it recognises.
#
# Everything here degrades to "unavailable" rather than failing the run: an
# Apple outage must not cost us the traffic report.
ASC_API = "https://api.appstoreconnect.apple.com"
ASC_RELOOK_DAYS = 3        # re-fetch this many trailing days in case Apple revised them
ASC_ANALYTICS_REPORTS = (  # by name, not id: ids are per-request
    "App Downloads Standard",
    "App Store Discovery and Engagement Standard",
    "App Store Purchases Standard",
    "App Sessions Standard",
)


def _asc_token(cfg: dict[str, str]) -> str | None:
    try:
        import jwt  # PyJWT + cryptography; present on the launchd interpreter
    except ImportError:
        print("  ! appstore: PyJWT not installed for this interpreter", file=sys.stderr)
        return None
    key_path = Path(os.path.expanduser(cfg.get("ASC_KEY_PATH", "")))
    if not key_path.exists():
        print(f"  ! appstore: key not found at {key_path}", file=sys.stderr)
        return None
    now = int(time.time())
    return jwt.encode(
        {"iss": cfg["ASC_ISSUER_ID"], "iat": now, "exp": now + 1200, "aud": "appstoreconnect-v1"},
        key_path.read_text(), algorithm="ES256", headers={"kid": cfg["ASC_KEY_ID"]},
    )


def _asc_get(token: str, path: str, accept: str = "application/json") -> tuple[int, bytes]:
    # Analytics report segments are not Apple API calls: they are pre-signed S3
    # URLs (from a report instance's `segments` relationship) that already carry
    # their own auth as query parameters. S3 rejects a request that also carries
    # an Authorization header with 400 InvalidArgument ("Only one auth mechanism
    # allowed"), so the bearer token must only go on requests to Apple's own API.
    is_external = path.startswith("http") and not path.startswith(ASC_API)
    url = path if path.startswith("http") else ASC_API + path
    headers = {"Accept": accept, "User-Agent": "purplelink-traffic-dashboard"}
    if not is_external:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    last: Exception | None = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                return exc.code, exc.read()
            last = exc
        except (OSError, http.client.HTTPException) as exc:
            last = exc
    raise RuntimeError(f"appstore: {path[:60]} failed: {str(last)[:80]}")


def _asc_sales_day(token: str, cfg: dict[str, str], day: str) -> dict | None:
    """One day's SALES/SUMMARY report reduced to the app's numbers, or None if
    Apple could not be read (as opposed to a 404, which means a quiet day)."""
    import csv
    import gzip
    import io
    q = urllib.parse.urlencode({
        "filter[reportType]": "SALES", "filter[reportSubType]": "SUMMARY",
        "filter[frequency]": "DAILY", "filter[vendorNumber]": cfg["ASC_VENDOR_NUMBER"],
        "filter[reportDate]": day,
    })
    status, body = _asc_get(token, f"/v1/salesReports?{q}", accept="application/a-gzip")
    out = {"downloads": 0, "desktopDownloads": 0, "redownloads": 0, "updates": 0, "proUnits": 0,
           "proPromo": 0, "proRefunds": 0, "proceeds": {}, "countries": {}, "empty": False}
    if status == 404:
        out["empty"] = True
        return out
    if status != 200:
        print(f"  ! appstore: sales {day} HTTP {status}", file=sys.stderr)
        return None
    app_id, sku = cfg["ASC_APP_ID"], cfg.get("ASC_APP_SKU", "com.globepin.app")
    for row in csv.DictReader(io.StringIO(gzip.decompress(body).decode("utf-8")), delimiter="\t"):
        # App rows carry the app's own identifier; a Pro purchase row carries
        # the app's SKU as Parent Identifier instead. Keep both, drop the rest.
        if row.get("Apple Identifier", "") != app_id and row.get("Parent Identifier", "") != sku:
            continue
        ptype = row.get("Product Type Identifier", "")
        units = int(float(row.get("Units") or 0))
        country = (row.get("Country Code") or "").strip()
        # Apple's product type identifiers: 1x = first-time download, 3x =
        # redownload, 7x = update. Until 2026-10-01 the last two were swapped
        # here, which showed 19 "redownloads" where Apple showed 6.
        if ptype.startswith("1"):
            # Device "Desktop" is the iPhone app fetched on a Mac. App Store
            # Connect's Analytics tab (platform iOS) leaves those out of
            # First-Time Downloads, so count them on their own line and keep the
            # headline equal to Apple's (26 here against Apple's 18 was 8 of them).
            if (row.get("Device") or "").strip().lower() == "desktop":
                out["desktopDownloads"] += units
                continue
            out["downloads"] += units
            if country:
                out["countries"][country] = out["countries"].get(country, 0) + units
        elif ptype.startswith("3"):
            out["redownloads"] += units
        elif ptype.startswith("7"):
            out["updates"] += units
        elif ptype.startswith("IA") or ptype.startswith("FI"):
            # A promo-code redemption is a Pro unit with a code and no money;
            # counting it as a sale would overstate revenue exactly the way our
            # own test clicks once overstated checkout figures.
            if (row.get("Promo Code") or "").strip():
                out["proPromo"] += units
                continue
            # A refund arrives as negative units with negative proceeds. Count it
            # on its own line instead of letting it quietly shrink the sales count.
            if units < 0:
                out["proRefunds"] += -units
            else:
                out["proUnits"] += units
            cur = (row.get("Currency of Proceeds") or "").strip() or "?"
            out["proceeds"][cur] = round(out["proceeds"].get(cur, 0.0)
                                         + float(row.get("Developer Proceeds") or 0) * units, 2)
    return out


def _asc_analytics(token: str, cfg: dict[str, str], prior: dict) -> dict:
    """Latest daily instances of the reports we care about, reduced to
    per-date, per-dimension sums. Tolerant of not-yet-generated reports."""
    import csv
    import gzip
    import io
    rid = cfg.get("ASC_ANALYTICS_REQUEST_ID")
    result = {"reports": {}, "headers": dict(prior.get("headers", {})), "note": ""}
    if not rid:
        result["note"] = "no analytics request configured"
        return result
    status, body = _asc_get(token, f"/v1/analyticsReportRequests/{rid}/reports?limit=200")
    if status != 200:
        result["note"] = f"report list HTTP {status}"
        return result
    wanted = {r["attributes"]["name"]: r["id"]
              for r in json.loads(body).get("data", []) if r["attributes"]["name"] in ASC_ANALYTICS_REPORTS}
    got_any = False
    for name, report_id in wanted.items():
        status, body = _asc_get(token, f"/v1/analyticsReports/{report_id}/instances?filter[granularity]=DAILY&limit=50")
        if status != 200:
            continue
        instances = json.loads(body).get("data", [])
        if not instances:
            continue
        got_any = True
        by_date: dict[str, dict[str, int]] = dict(prior.get("reports", {}).get(name, {}).get("byDate", {}))
        ordered = sorted(instances, key=lambda i: i["attributes"].get("processingDate", ""))
        # With nothing archived, read every instance once; after that the newest few
        # are enough to pick up Apple's restatements.
        for inst in (ordered if not by_date else ordered[-ASC_RELOOK_DAYS - 1:]):
            st, sb = _asc_get(token, f"/v1/analyticsReportInstances/{inst['id']}/segments")
            if st != 200:
                continue
            # Counts from this instance alone. They replace, never add to, what is
            # archived for the same date: re-reading an instance on the next run
            # used to add its counts again, inflating downloads 20-30x.
            inst_dates: dict[str, dict[str, int]] = {}
            for seg in json.loads(sb).get("data", []):
                url = seg["attributes"].get("url")
                if not url:
                    continue
                s2, raw = _asc_get(token, url, accept="*/*")
                if s2 != 200:
                    continue
                try:
                    text = gzip.decompress(raw).decode("utf-8")
                except OSError:
                    text = raw.decode("utf-8", "replace")
                # Same TSV format as the sales report above, not CSV.
                reader = csv.DictReader(io.StringIO(text), delimiter="\t")
                if reader.fieldnames and name not in result["headers"]:
                    result["headers"][name] = list(reader.fieldnames)
                    print(f"  appstore: first '{name}' report; columns = {reader.fieldnames}", file=sys.stderr)
                for row in reader:
                    date = row.get("Date") or row.get("date") or ""
                    if not date:
                        continue
                    # the dimension that names what was counted, if the report has one
                    dim = row.get("Event") or row.get("Download Type") or row.get("Purchase Type") \
                        or row.get("Event Type") or "total"
                    count_key = next((k for k in ("Counts", "Count", "Total Downloads", "Downloads",
                                                  "Sessions", "Units") if k in row), None)
                    if not count_key:
                        continue
                    try:
                        n = int(float(row[count_key] or 0))
                    except ValueError:
                        continue
                    inst_dates.setdefault(date, {})
                    inst_dates[date][dim] = inst_dates[date].get(dim, 0) + n
            by_date.update(inst_dates)
        result["reports"][name] = {"byDate": by_date}
    if not got_any:
        result["note"] = "Apple has not generated the first report yet"
    return result


def fetch_appstore(cfg: dict[str, str], prior: dict | None) -> dict | None:
    """GlobePin's App Store figures, merged into whatever was archived before."""
    required = ("ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_KEY_PATH", "ASC_VENDOR_NUMBER", "ASC_APP_ID")
    if any(not cfg.get(k) for k in required):
        return None
    token = _asc_token(cfg)
    if not token:
        return None
    prior = prior or {}
    days: dict[str, dict] = dict(prior.get("days", {}))
    today = dt.date.today()
    launch = dt.date.fromisoformat(cfg.get("ASC_APP_LAUNCH", "2026-09-03"))
    # Days parsed before the 2026-10-01 fix lack desktopDownloads and are read
    # again once, so start from launch while any such day is on file.
    stale = any("desktopDownloads" not in v for v in days.values())
    start = launch if stale else max(launch, today - dt.timedelta(days=FETCH_DAYS))
    relook = today - dt.timedelta(days=ASC_RELOOK_DAYS)
    fetched = 0
    d = start
    while d < today:                       # today's report does not exist until tomorrow
        key = d.isoformat()
        if key not in days or d >= relook or "desktopDownloads" not in days[key]:
            try:
                rec = _asc_sales_day(token, cfg, key)
            except RuntimeError as exc:
                print(f"  ! {exc}", file=sys.stderr)
                rec = None
            if rec is not None:
                days[key] = rec
                fetched += 1
        d += dt.timedelta(days=1)
    try:
        analytics = _asc_analytics(token, cfg, prior.get("analytics", {}))
    except RuntimeError as exc:
        print(f"  ! {exc}", file=sys.stderr)
        analytics = prior.get("analytics", {"reports": {}, "headers": {}, "note": "unavailable this run"})
    return {
        "label": cfg.get("ASC_APP_LABEL", "App"),
        "appId": cfg["ASC_APP_ID"],
        "launch": launch.isoformat(),
        "days": days,
        "analytics": analytics,
        "fetchedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "fetchedDays": fetched,
    }


# --- Chrome Web Store (Scholar Utility Belt) --------------------------------
#
# The Chrome Web Store has no install-stats API: the current publish/package
# API (chromewebstore.googleapis.com) is management-only per Google's own
# docs, and the Developer Dashboard (chrome.google.com/webstore/devconsole)
# blocks automation outright. The public storefront listing page is a
# different host, needs no auth, and shows a rounded "X,XXX users" figure --
# not an exact daily count, but a real, zero-setup signal that beats having
# nothing.

CWS_EXTENSION_ID = "omcogfcgldfmihfogbffflbocdbjockn"
CWS_SLUG = "scholar-utility-belt"
CWS_LABEL = "Scholar Utility Belt"


def fetch_chrome_web_store(prior: dict | None) -> dict | None:
    """The storefront's rounded user count, or the prior reading on failure."""
    url = f"https://chromewebstore.google.com/detail/{CWS_SLUG}/{CWS_EXTENSION_ID}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (purplelink-traffic-dashboard)"})
    last: Exception | None = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            m = re.search(r">([\d,]+)\+?\s*users?<", body)
            if not m:
                raise RuntimeError("users count not found in listing page")
            return {"label": CWS_LABEL, "url": url, "users": m.group(1),
                     "asOf": dt.date.today().isoformat()}
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                print(f"  ! chrome web store: HTTP {exc.code}", file=sys.stderr)
                return prior
            last = exc
        except (OSError, http.client.HTTPException, RuntimeError) as exc:
            last = exc
    print(f"  ! chrome web store unavailable: {str(last)[:80]}", file=sys.stderr)
    return prior


# Search Console rows that are not readers. A new site with a handful of
# real visitors gets most of its impressions from tools that run queries
# (citation checkers, research agents): quoted phrases, site: filters, bare
# PMC ids. They carry impressions and never clicks, so left in they drag the
# headline CTR to zero and the average position to a number that describes
# nobody. Classified here so the card can show them separately.
_OPERATOR_QUERY = re.compile(
    r'"|^[+%]|\bsite[.:]|pmc\d{5,}|fdcid|\b(?:intitle|inurl|filetype)\b', re.I)


def is_operator_query(q: str) -> bool:
    return bool(_OPERATOR_QUERY.search(q or ""))


def split_queries(rows: list[dict], total_impressions: int) -> dict:
    """Split Search Console query rows into operator-style and natural-language.

    Google hides rare queries, so the visible rows usually cover a minority of
    impressions; the remainder is reported as anonymized rather than guessed at.
    """
    op = {"queries": 0, "impressions": 0, "clicks": 0}
    nat = {"queries": 0, "impressions": 0, "clicks": 0, "top10_impressions": 0, "_pos": 0.0}
    natural_rows = []
    for r in rows:
        key = (r.get("keys") or [""])[0]
        imp = int(r.get("impressions", 0) or 0)
        clk = int(r.get("clicks", 0) or 0)
        pos = float(r.get("position", 0) or 0)
        if is_operator_query(key):
            bucket = op
        else:
            bucket = nat
            nat["_pos"] += pos * imp
            if pos <= 10:
                nat["top10_impressions"] += imp
            natural_rows.append({"key": key, "count": clk, "impressions": imp,
                                 "position": round(pos, 1)})
        bucket["queries"] += 1
        bucket["impressions"] += imp
        bucket["clicks"] += clk
    nat["position"] = round(nat.pop("_pos") / nat["impressions"], 1) if nat["impressions"] else 0.0
    visible = op["impressions"] + nat["impressions"]
    natural_rows.sort(key=lambda r: (-r["impressions"], r["key"]))
    return {"operator": op, "natural": nat, "natural_top": natural_rows[:10],
            "visible_impressions": visible,
            "anonymized_impressions": max(0, int(total_impressions) - visible)}


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
        query_rows = query(["query"], 1000).get("rows") or []
        pages = query(["page"], 10).get("rows") or []
        device_rows = query(["device"], 5).get("rows") or []
    except Exception as exc:                                # noqa: BLE001
        detail = getattr(exc, "reason", None) or str(exc)
        return {"error": detail[:200]}

    split = split_queries(query_rows, int(totals.get("impressions", 0) or 0))

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
        # Natural-language queries only; operator-style ones are counted in
        # "split" so the table is not ten rows of one PMC id.
        "queries": split["natural_top"],
        "split": split,
        "devices": {(r["keys"][0] or "").lower(): {
            "impressions": int(r.get("impressions", 0) or 0),
            "clicks": int(r.get("clicks", 0) or 0),
            "position": round(float(r.get("position", 0) or 0), 1)}
            for r in device_rows},
        "pages": [{"key": strip(r["keys"][0]), "count": int(r.get("clicks", 0) or 0),
                   "impressions": int(r.get("impressions", 0) or 0),
                   "position": round(float(r.get("position", 0) or 0), 1)}
                  for r in pages],
    }


def fetch_admob(app_key: str) -> dict | None:
    """AdMob in-app ad earnings for one app, over the trailing ADMOB_DAYS days.

    Returns None when ADMOB_TOKEN_PATH is missing (not set up on this
    machine) and {"error": ...} on any API failure -- same non-fatal contract
    as fetch_gsc(): an expired token or a Google outage must not cost us the
    rest of the run.
    """
    if not ADMOB_TOKEN_PATH.exists():
        return None
    app = ADMOB_APPS.get(app_key)
    if not app:
        return None

    try:
        cfg = json.loads(ADMOB_TOKEN_PATH.read_text())
        token_body = urllib.parse.urlencode({
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "refresh_token": cfg["refresh_token"],
            "grant_type": "refresh_token",
        }).encode()
        token_req = urllib.request.Request(cfg["token_uri"], data=token_body, method="POST")
        with urllib.request.urlopen(token_req, timeout=TIMEOUT, context=_ssl_context()) as resp:
            access_token = json.loads(resp.read().decode())["access_token"]

        end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
        start = end - dt.timedelta(days=ADMOB_DAYS - 1)
        report_body = json.dumps({
            "reportSpec": {
                "dateRange": {
                    "startDate": {"year": start.year, "month": start.month, "day": start.day},
                    "endDate": {"year": end.year, "month": end.month, "day": end.day},
                },
                "dimensions": ["APP"],
                "metrics": ["ESTIMATED_EARNINGS", "IMPRESSIONS", "CLICKS", "MATCHED_REQUESTS"],
                "dimensionFilters": [{"dimension": "APP", "matchesAny": {"values": [app["appId"]]}}],
            }
        }).encode()
        report_req = urllib.request.Request(
            f"https://admob.googleapis.com/v1/accounts/{app['publisherId']}/networkReport:generate",
            data=report_body, method="POST",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(report_req, timeout=TIMEOUT, context=_ssl_context()) as resp:
            rows = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:160]}"}
    except Exception as exc:  # noqa: BLE001 — never let an AdMob hiccup sink the run
        return {"error": str(exc)[:200]}

    # Estimated earnings by calendar month, this month included (through today), for the all-sources revenue view.
    # Best effort: a failure here leaves the 7-day figures intact.
    monthly: dict[str, float] = {}
    try:
        today = dt.datetime.now(dt.timezone.utc).date()
        y, m = today.year, today.month - 5
        while m < 1:
            m, y = m + 12, y - 1
        first = dt.date(y, m, 1)
        month_body = json.dumps({"reportSpec": {
            "dateRange": {"startDate": {"year": first.year, "month": first.month, "day": 1},
                          "endDate": {"year": today.year, "month": today.month, "day": today.day}},
            "dimensions": ["MONTH"], "metrics": ["ESTIMATED_EARNINGS"],
            "dimensionFilters": [{"dimension": "APP", "matchesAny": {"values": [app["appId"]]}}]}}).encode()
        month_req = urllib.request.Request(
            f"https://admob.googleapis.com/v1/accounts/{app['publisherId']}/networkReport:generate",
            data=month_body, method="POST",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(month_req, timeout=TIMEOUT, context=_ssl_context()) as resp:
            for item in json.loads(resp.read().decode()):
                r = item.get("row")
                if not r:
                    continue
                ym = str((r.get("dimensionValues") or {}).get("MONTH", {}).get("value", ""))
                if len(ym) == 6 and ym.isdigit():
                    micros = int((r.get("metricValues") or {}).get("ESTIMATED_EARNINGS", {}).get("microsValue", 0) or 0)
                    monthly[f"{ym[:4]}-{ym[4:]}"] = round(micros / 1_000_000, 4)
    except Exception:  # noqa: BLE001
        monthly = {}

    earnings_micros = impressions = clicks = matched = 0
    for item in rows:
        r = item.get("row")
        if not r:
            continue
        mv = r.get("metricValues", {})
        earnings_micros += int(mv.get("ESTIMATED_EARNINGS", {}).get("microsValue", 0) or 0)
        impressions += int(mv.get("IMPRESSIONS", {}).get("integerValue", 0) or 0)
        clicks += int(mv.get("CLICKS", {}).get("integerValue", 0) or 0)
        matched += int(mv.get("MATCHED_REQUESTS", {}).get("integerValue", 0) or 0)

    return {
        "label": app["label"],
        "days": ADMOB_DAYS,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "earnings": round(earnings_micros / 1_000_000, 4),
        "impressions": impressions,
        "clicks": clicks,
        "matchedRequests": matched,
        "monthly": monthly,
        "fetchedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------- cost sources
#
# What running the business costs, measured rather than estimated, for the
# profit view: Modal's billing API (every backend app's compute), the Paper
# Review usage ledger (real Claude API tokens and cost per paid job), and the
# Apple Search Ads API (spend per day, and which search terms spend it). Each
# degrades to None the same way AdMob does, so a missing key or an outage
# costs one line of the profit view, never the run.

MODAL_APP_LINES = {  # Modal app name -> product line the compute belongs to
    "purplelink-latextools": "Paper Review & tools",
    "muscleonglp-research": "MuscleOnGLP",
}
COST_DAYS = 28


def _modal_sdk():
    try:
        import modal  # present on the launchd interpreter (Python 3.12 framework)
        import modal.billing  # noqa: F401
        return modal
    except Exception:
        return None


def fetch_modal_costs(days: int = COST_DAYS) -> dict | None:
    """Modal compute cost per app per day, from Modal's own billing report."""
    modal = _modal_sdk()
    if modal is None:
        return None
    end = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        rows = modal.billing.workspace_billing_report(start=end - dt.timedelta(days=days), end=end,
                                                      resolution="d")
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:160]}
    by_app: dict[str, dict[str, float]] = {}
    for r in rows:
        day = r["interval_start"].date().isoformat()
        app = r.get("description") or r.get("object_id") or "unknown"
        by_app.setdefault(app, {})
        by_app[app][day] = by_app[app].get(day, 0.0) + float(r["cost"])
    return {"byAppDay": by_app, "through": (end - dt.timedelta(days=1)).date().isoformat()}


def fetch_api_usage() -> list[dict] | None:
    """Per-job Claude API cost from backend/app.py's paper-review-usage-ledger.
    Records with no model call (a job that failed before reaching Claude) are
    dropped: they cost nothing and would only pad the job counts."""
    modal = _modal_sdk()
    if modal is None:
        return None
    try:
        d = modal.Dict.from_name("paper-review-usage-ledger")
        rows = [v for _k, v in d.items()]
    except Exception as exc:  # noqa: BLE001
        print(f"  ! usage ledger unavailable: {str(exc)[:100]}", file=sys.stderr)
        return None
    return sorted(({k: r.get(k) for k in ("ts", "product_key", "status", "cost_usd",
                                          "input_tokens", "output_tokens", "price_charged_usd")}
                   for r in rows if r.get("models")), key=lambda r: r["ts"])


ASA_API = "https://api.searchads.apple.com/api/v5"
ASA_KEY_DEFAULT = "~/.config/purplelink/asa-private-key.pem"


def _asa_request(url: str, token: str, org: str | None, body: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if org:
        headers["X-AP-Context"] = f"orgId={org}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as r:
        return json.loads(r.read().decode())


def _asa_money(v) -> float:
    if isinstance(v, dict):
        v = v.get("amount")
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _asa_metrics(m: dict) -> dict:
    installs = m.get("totalInstalls", m.get("installs", m.get("tapInstalls", 0))) or 0
    return {"impressions": int(m.get("impressions") or 0), "taps": int(m.get("taps") or 0),
            "installs": int(installs), "spend": round(_asa_money(m.get("localSpend")), 2)}


def fetch_asa_api(cfg: dict[str, str]) -> dict | None:
    """Apple Search Ads through its API: an API user's EC key signs a client
    secret, exchanged for a one-hour token. No Apple ID sign-in and no 2FA, so
    it runs unattended like everything else here. Returns None when the
    ASA_* settings are absent (not set up), {"error": ...} on failure."""
    need = ("ASA_CLIENT_ID", "ASA_TEAM_ID", "ASA_KEY_ID")
    if not all(cfg.get(k) for k in need):
        return None
    try:
        import jwt
    except ImportError:
        return {"error": "PyJWT not installed for this interpreter"}
    key_path = Path(os.path.expanduser(cfg.get("ASA_KEY_PATH") or ASA_KEY_DEFAULT))
    if not key_path.exists():
        return {"error": f"private key not found at {key_path}"}
    try:
        now = int(time.time())
        secret = jwt.encode({"sub": cfg["ASA_CLIENT_ID"], "iss": cfg["ASA_TEAM_ID"], "iat": now,
                             "exp": now + 3600, "aud": "https://appleid.apple.com"},
                            key_path.read_text(), algorithm="ES256", headers={"kid": cfg["ASA_KEY_ID"]})
        body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": cfg["ASA_CLIENT_ID"],
                                       "client_secret": secret, "scope": "searchadsorg"}).encode()
        req = urllib.request.Request("https://appleid.apple.com/auth/oauth2/token", data=body, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as r:
            token = json.loads(r.read().decode())["access_token"]

        org = cfg.get("ASA_ORG_ID")
        if not org:
            acls = _asa_request(f"{ASA_API}/acls", token, None).get("data") or []
            if not acls:
                return {"error": "API user has no organization access"}
            org = str(acls[0]["orgId"])

        today = dt.date.today()
        start = (today - dt.timedelta(days=COST_DAYS - 1)).isoformat()
        selector = {"orderBy": [{"field": "localSpend", "sortOrder": "DESCENDING"}],
                    "pagination": {"offset": 0, "limit": 1000}}
        rep = _asa_request(f"{ASA_API}/reports/campaigns", token, org, {
            "startTime": start, "endTime": today.isoformat(), "granularity": "DAILY", "timeZone": "ORTZ",
            "selector": selector, "returnRecordsWithNoMetrics": True, "returnRowTotals": False,
            "returnGrandTotals": False})
        rows = ((rep.get("data") or {}).get("reportingDataResponse") or {}).get("row") or []

        wk_lo = (today - dt.timedelta(days=6)).isoformat()
        campaigns, daily = [], {}
        for row in rows:
            md = row.get("metadata") or {}
            days = row.get("granularity") or []
            last7 = {"impressions": 0, "taps": 0, "installs": 0, "spend": 0.0}
            for g in days:
                m = _asa_metrics(g)
                day = g.get("date", "")[:10]
                slot = daily.setdefault(day, {"spend": 0.0, "installs": 0, "taps": 0, "impressions": 0})
                for k in slot:
                    slot[k] += m[k]
                if day >= wk_lo:
                    for k in last7:
                        last7[k] += m[k]
            spend, inst, taps, imp = last7["spend"], last7["installs"], last7["taps"], last7["impressions"]
            campaigns.append({
                "id": md.get("campaignId"), "key": md.get("campaignName", "campaign"),
                "status": (md.get("displayStatus") or md.get("campaignStatus") or "").title(),
                "dailyBudget": _asa_money(md.get("dailyBudget")) or None,
                "spend": round(spend, 2), "impressions": imp, "taps": taps, "installs": inst,
                "avgCPT": round(spend / taps, 2) if taps else None,
                "avgCPA": round(spend / inst, 2) if inst else None,
                "ttr": f"{taps / imp * 100:.2f}%" if imp else "—",
                "conversionRate": f"{inst / taps * 100:.0f}%" if taps else "—",
            })

        terms = []
        for c in campaigns[:3]:
            if not c["id"]:
                continue
            try:
                t = _asa_request(f"{ASA_API}/reports/campaigns/{c['id']}/searchterms", token, org, {
                    "startTime": wk_lo, "endTime": today.isoformat(), "timeZone": "ORTZ",
                    "selector": selector, "returnRecordsWithNoMetrics": False, "returnRowTotals": True})
            except urllib.error.HTTPError:
                continue
            for row in ((t.get("data") or {}).get("reportingDataResponse") or {}).get("row") or []:
                md = row.get("metadata") or {}
                terms.append({"term": md.get("searchTermText") or "(low volume terms)",
                              "keyword": md.get("keyword") or "", **_asa_metrics(row.get("total") or {})})
        terms.sort(key=lambda t: (-t["spend"], -t["installs"]))
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:160]}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:200]}

    return {"asOf": today.isoformat(), "window": "Last 7 days", "source": "api",
            "campaigns": campaigns, "searchTerms": terms[:15],
            "daily": {d: {k: round(v, 2) if k == "spend" else v for k, v in m.items()}
                      for d, m in sorted(daily.items())}}


def record_asa_api(reading: dict) -> None:
    """Write an API reading into manual-ads.json under the same key the manual
    Chrome reading used, so every card and metric downstream reads it as-is."""
    data = load_manual_ads()
    prev = (data.get("appleSearchAds") or {}).get("campaigns") or []
    prev_inst = prev[0].get("installs") if prev else None
    c0 = reading["campaigns"][0] if reading["campaigns"] else {}
    note = (f"Last 7 days: {c0.get('impressions', 0):,} impressions, {c0.get('taps', 0)} taps and "
            f"{c0.get('installs', 0)} installs for ${c0.get('spend', 0):,.2f}"
            + (f", ${c0['avgCPA']:,.2f} per install" if c0.get("avgCPA") else "") + ".")
    if prev_inst is not None and prev_inst != c0.get("installs"):
        note += f" Installs {prev_inst} → {c0.get('installs')} since the last reading."
    data["appleSearchAds"] = {k: reading[k] for k in ("asOf", "window", "source", "campaigns", "searchTerms")}
    data["appleSearchAds"]["note"] = note
    MANUAL_ADS_PATH.write_text(json.dumps(data, indent=2))


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


def fetch_form_signups(site_id: str, token: str) -> tuple[dict[str, dict[str, int]], list]:
    """Daily submission counts per Netlify form (keyed by form name), plus an
    all-time per-form breakdown for the summary table.

    Kept per-form rather than blended into one total: a site can carry
    several signup forms for entirely different products (a pre-launch
    waitlist, a release-notes opt-in, ...), and summing them hid which one
    actually moved — a live form reading zero looked the same as a retired
    one that no longer even renders on the page.

    Only dates, counts and form names are read. Submissions carry email
    addresses; those are never extracted, stored, or displayed — the archive
    stays free of personal data.
    """
    def api(path):
        req = urllib.request.Request(
            f"https://api.netlify.com/api/v1/{path}",
            headers={"Authorization": f"Bearer {token}",
                     "User-Agent": "purplelink-traffic-dashboard"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as r:
            return json.loads(r.read().decode("utf-8"))

    by_form_day: dict[str, dict[str, int]] = {}
    per_form = []
    for form in api(f"sites/{site_id}/forms"):
        name = form.get("name", "form")
        subs = api(f"forms/{form['id']}/submissions")
        per_form.append({"key": name, "count": len(subs)})
        day_counts = by_form_day.setdefault(name, {})
        for s in subs:
            day = str(s.get("created_at", ""))[:10]
            if day:
                day_counts[day] = day_counts.get(day, 0) + 1
    per_form.sort(key=lambda f: -f["count"])
    return by_form_day, per_form


def load_history() -> dict:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text())
        except json.JSONDecodeError:
            backup = HISTORY_PATH.with_suffix(".corrupt.json")
            HISTORY_PATH.rename(backup)
            print(f"  ! history.json was unreadable; moved to {backup}", file=sys.stderr)
    return {"sites": {}}


AUDIENCE_MIN_VISITS = 20   # below this a percentage of visits says nothing; the line says so instead
AUDIENCE_SCROLL = ["0", "25", "50", "75", "100"]
AUDIENCE_ENGAGED = ["0-10s", "10-30s", "30-60s", "1-3m", "3m-plus"]
AUDIENCE_DEVICE = ["mobile", "tablet", "desktop"]


def audience_summary(payload: dict) -> dict | None:
    """Country, device, scroll-depth and engaged-time breakdowns from a ?host= stats response (stats.mjs).

    None when the response has none of them (an older collector, or a site fetched without a host filter), so a site
    that does not report them shows nothing. Visits are counted by the scroll_depth events, which the site sends once
    per visit; the plain-language line says so rather than guessing when the sample is small.
    """
    if not isinstance(payload, dict) or not any(k in payload for k in ("byCountry", "device", "scrollDepth", "engagedTime")):
        return None

    def num(v) -> int:
        return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else 0

    def rows(src, order) -> list[dict]:
        src = src if isinstance(src, dict) else {}
        return [{"key": k, "count": num(src.get(k))} for k in order]

    by_country = payload.get("byCountry") if isinstance(payload.get("byCountry"), dict) else {}
    countries = [{"key": str(c.get("key")), "count": num(c.get("count"))}
                 for c in (by_country.get("top") or []) if isinstance(c, dict) and c.get("key")]
    scroll = rows(payload.get("scrollDepth"), AUDIENCE_SCROLL)
    visits = sum(r["count"] for r in scroll)
    reach50 = sum(r["count"] for r in scroll if r["key"] in ("50", "75", "100"))
    if visits == 0:
        sentence = "No visit has reported a scroll depth yet."
        pct50 = None
    elif visits < AUDIENCE_MIN_VISITS:
        sentence = (f"Only {visits} visit{'s' if visits != 1 else ''} reported a scroll depth, too few for a percentage "
                    f"({reach50} reached 50 percent scroll).")
        pct50 = None
    else:
        pct50 = reach50 / visits * 100
        sentence = f"{pct50:.0f} percent of visits reached 50 percent scroll ({reach50} of {visits})."
    return {
        "countries": countries,
        "countryOther": num(by_country.get("other")),
        "countryUnknown": num(by_country.get("unknown")),
        "device": rows(payload.get("device"), AUDIENCE_DEVICE),
        "scroll": scroll,
        "engaged": rows(payload.get("engagedTime"), AUDIENCE_ENGAGED),
        "visits": visits,
        "reach50": reach50,
        "pct50": pct50,
        "sentence": sentence,
    }


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
    # Signup metrics arrive with real history from Netlify Forms, so date each
    # one from its first actual submission rather than from the day we started
    # reading the API — otherwise weeks of real data reads as "recorded since
    # today". signupMetricKeys lists which byDay keys came from forms this run
    # (one per SITES[*]["signup_forms"] entry); beacon-sourced metrics don't
    # need this, they're genuinely new the day polling for them starts.
    for metric_key in payload.get("signupMetricKeys", []):
        metric_days = sorted(d for d, m in (payload.get("byDay") or {}).items()
                             if isinstance(m, dict) and m.get(metric_key))
        if metric_days:
            seen = site_hist.setdefault("metricsFirstSeen", {})
            if metric_key not in seen or metric_days[0] < seen[metric_key]:
                seen[metric_key] = metric_days[0]

    site_hist["latest"] = {
        "formBreakdown": payload.get("formBreakdown", []),
        "generatedAt": payload.get("generatedAt"),
        "topPaths": payload.get("topPaths", []),
        "checkoutByProduct": payload.get("checkoutByProduct", []),
        "topReferrers": payload.get("topReferrers", []),
        "topUtm": payload.get("topUtm", []),
        "toolRuns": payload.get("toolRuns", []),
        "totals": payload.get("totals", {}),
        # "<type>: <meta>" counts over the stats window, e.g. "download: RubbleFront-Demo-1.0.0-mac.dmg" (which file).
        "otherEventDetail": payload.get("otherEventDetail", []),
    }
    audience = audience_summary(payload)
    if audience:
        site_hist["latest"]["audience"] = audience


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
    by_day, synthetic = without_synthetic(site["key"], site_hist.get("byDay", {}))
    today = dt.datetime.now(dt.timezone.utc).date()
    yesterday = today - dt.timedelta(days=1)

    def total(days: list[str], field: str) -> int:
        return sum(int(by_day.get(d, {}).get(field, 0) or 0) for d in days)

    last7_days = _daterange(yesterday, 7)      # complete days only
    prior7_days = _daterange(yesterday - dt.timedelta(days=7), 7)
    last14_days = _daterange(today, 14)        # for the sparkline, includes today
    last30_days = _daterange(yesterday, 30)
    trial_since = site_hist.get("metricsFirstSeen", {}).get("trialDownloads")
    trial_days = [d for d in last30_days if trial_since and d >= trial_since]

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
        "key": site["key"],
        "label": site["label"],
        "domain": site["domain"],
        "synthetic": synthetic,
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
                # Today is deliberately outside the 7-day window, which is right
                # for a week-over-week number and wrong for a claim about
                # whether anything is happening. On 2026-09-05 the first seven
                # checkout clicks the site ever recorded all landed today, and
                # the dashboard reported "zero, traffic is not reaching that
                # step" while four of them were paying.
                "today": total([today.isoformat()], k),
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
        # Checkout clicks day-by-day, not smoothed into a rate. The
        # moderntex buy button sat at a flat zero for 8 straight days
        # (2026-08-28 to 09-04) with normal traffic the whole time, and it
        # took a manual dig to notice -- this chart exists so a trailing
        # zero streak is visible on the next daily run instead.
        "checkout_spark": [
            {"day": d, "pv": int(by_day.get(d, {}).get("checkoutClicks", 0) or 0)}
            for d in last14_days
        ] if any(k == "checkoutClicks" for k, _ in site["secondaries"]) else None,
        "ai_trend": ai_referrer_trend(site_hist),
        "top_paths": latest.get("topPaths", [])[:6],
        "top_referrers": latest.get("topReferrers", [])[:6],
        "top_utm": latest.get("topUtm", [])[:5],
        "tool_runs": latest.get("toolRuns", [])[:5],
        "calc_runs": latest.get("calcByTool", [])[:5],
        "form_breakdown": latest.get("formBreakdown", [])[:6],
        "audience": latest.get("audience"),
        "gsc": site_hist.get("gsc"),
        "proj": project(by_day, today),
        "checkout": checkout_rate(
            latest.get("topPaths", []), site.get("product_paths"),
            int(total(last30_days, "checkoutClicks") or 0),
        ),
        # ModernTex trial funnel inputs, all over the same days: the last 30
        # complete days that fall on or after the day the trial shipped (see
        # METRIC_START_OVERRIDES). Clicks and orders from before the trial
        # existed are not trial conversions; counting them made the funnel read
        # "16 downloads -> 11 clicks -> 7 orders" when 6 of the 7 orders
        # predated the first trial download. The beacon keeps per-product
        # checkout clicks only as a 30-day total, so the per-day click count here
        # is every product's buy button (at this volume nearly all ModernTex).
        "trial_days": trial_days,
        "trial30": int(total(trial_days, "trialDownloads") or 0),
        "trial_clicks30": int(total(trial_days, "checkoutClicks") or 0),
        "bounds": [b for b in (
            conversion_bound(by_day, k, lbl) for k, lbl in site["secondaries"]
        ) if b],
        "error": site_hist.get("error"),
    }


AI_REFERRERS = ("chatgpt", "perplexity", "claude.ai", "copilot", "gemini")
SEARCH_REFERRERS = ("google", "bing", "duckduckgo", "brave", "ecosia", "yahoo")
SOCIAL_REFERRERS = ("reddit", "twitter", "t.co", "x.com", "facebook", "linkedin", "lnkd.in",
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


def ai_referrer_trend(site_hist: dict, min_points: int = 4) -> list[dict]:
    """AI-assistant share of referred traffic, one point per archived daily
    snapshot. Each snapshot's topReferrers is already a trailing FETCH_DAYS
    window, so this reads as a slow-moving trend line, not daily noise --
    which is the right resolution for a channel that moves by single-digit
    referrals a week. Found by comparing archived snapshots 2026-07-25
    through 2026-09-09: purplelink's share climbed from ~12% to a stable
    ~18-20%, while muscleonglp sat at a flat 0% the entire time.

    Skips snapshot days with no referred traffic at all (an undefined share,
    not a real 0%) rather than plotting a misleading floor.
    """
    snaps = site_hist.get("snapshots", {})
    points = []
    for day in sorted(snaps.keys()):
        refs = snaps[day].get("topReferrers", [])
        total = sum(int(r.get("count", 0) or 0) for r in refs)
        if not total:
            continue
        ai = sum(int(r.get("count", 0) or 0) for r in refs
                 if any(t in str(r.get("key", "")).lower() for t in AI_REFERRERS))
        points.append({"day": day, "pct": ai / total * 100, "ai": ai, "total": total})
    return points if len(points) >= min_points else []


def checkout_rate(top_paths: list, product_paths, clicks: int) -> dict | None:
    """Buy-button presses against views of pages that offer a buy button.

    topPaths is the live 30-day window, so `clicks` must be the 30-day count
    too, not the 7-day headline, or the ratio compares different periods. When
    no product page was viewed at all there is no rate to report -- that is a
    discovery problem, and saying "0%" would misattribute it to the button.
    """
    if not product_paths:
        return None
    wanted = set(product_paths)
    views = sum(
        r.get("count", 0) for r in (top_paths or [])
        if isinstance(r, dict) and str(r.get("key", "")) in wanted
    )
    if not views:
        return {"views": 0, "clicks": clicks, "pct": None}
    return {"views": views, "clicks": clicks, "pct": clicks / views * 100}


def observations(summaries: list[dict], sales: dict | None = None) -> list[str]:
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
            elif sec.get("today"):
                out.append(f"{s['label']}: {sec['today']} {sec['label']} today, the first in "
                           f"over a week. The 7-day window covers complete days only, "
                           f"so today is not in it yet.")
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

        # The ModernTex trial funnel: download -> buy click -> paid order. This is
        # the one number the trial was built to produce, so it gets its own line
        # rather than being read off three separate counters. Orders come from
        # Stripe (sales.byProduct), the other two from the beacon.
        tr = next((sec for sec in s["secondaries"] if sec["key"] == "trialDownloads"), None)
        if tr and tr["days_tracked"] is not None and s["key"] == "purplelink":
            # Orders from Stripe's recent list, dated, so only the ones placed on
            # the funnel's own days count. byProduct is all-time and would pull
            # in the launch-week orders that came before the trial.
            days = set(s.get("trial_days", []))
            recent = (sales or {}).get("recent", [])
            orders30 = sum(1 for r in recent
                           if r.get("product") == "moderntex" and (r.get("date") or "")[:10] in days)
            dl, clk = s.get("trial30", 0), s.get("trial_clicks30", 0)
            window = (f"since {tr['since']}" if tr["days_tracked"] < 30 else "last 30 days")
            caveat = (" Stripe's recent-order list was truncated, so orders may be undercounted."
                      if (sales or {}).get("truncated") else "")
            if dl == 0 and tr["days_tracked"] < 2:
                pass  # the generic "recorded since" line already covers a day-old counter
            elif dl == 0:
                out.append(f"{s['label']}: ModernTex trial funnel ({window}): no trial downloads yet, "
                           f"{clk} buy click(s), {orders30} order(s).{caveat}")
            else:
                conv = f", {orders30 / dl * 100:.0f}% of downloads became orders" if orders30 else ""
                out.append(f"{s['label']}: ModernTex trial funnel ({window}): {dl} trial download(s) "
                           f"→ {clk} buy click(s) → {orders30} paid order(s){conv}.{caveat}")

        # Say what was taken out, so the figures above can be reconciled against
        # the raw archive rather than looking like a discrepancy.
        for adj in s.get("synthetic", []):
            label = next((lbl for k, lbl in
                          (("checkoutClicks", "checkout clicks"), ("toolRuns", "tool runs"),
                           ("haeaSignups", "haea waitlist signups"),
                           ("moderntexReleaseSignups", "ModernTex release-notes signups"),
                           ("subscribes", "subscribes"),
                           ("calcRuns", "calculator runs"),
                           ("vitaeDownloads", "Vitae downloads"),
                           ("trialDownloads", "trial downloads")) if k == adj["metric"]), adj["metric"])
            out.append(f"{s['label']}: {adj['removed']} of the {adj['raw']} {label} on "
                       f"{adj['day']} were ours and are excluded above ({adj['why']}). "
                       f"The archive still holds the raw count.")

    # Cross-site
    ok = [s for s in summaries if not s.get("error")]
    if len(ok) == 2 and all(s["last7"] for s in ok):
        a, b = sorted(ok, key=lambda s: -s["last7"])
        if b["last7"]:
            out.append(f"Across the two sites, {a['label']} is carrying "
                       f"{round(a['last7'] / (a['last7'] + b['last7']) * 100)}% of the combined traffic.")
    return out


def appstore_observations(appstore: dict | None) -> list[str]:
    """Plain-language read of GlobePin's App Store Connect *Analytics Reports*
    (impressions, product page views, sessions, ...) -- separate from the
    Sales & Trends downloads/proceeds that appstore_summary() already covers.
    Apple only starts generating these a few days after the ongoing request
    was created and never backfills, so there is often nothing to say yet;
    that is reported honestly rather than as a zero."""
    if not appstore:
        return []
    label = appstore.get("label", "App")
    an = appstore.get("analytics") or {}
    reports = an.get("reports") or {}
    if not reports:
        note = an.get("note") or ""
        if note:
            return [f"{label}: App Store engagement analytics — {note}. "
                    f"Apple does not backfill, so this starts empty and fills in from here."]
        return []

    out: list[str] = []
    for name, rep in reports.items():
        by_date = rep.get("byDate") or {}
        if not by_date:
            continue
        totals: dict[str, int] = {}
        for day_counts in by_date.values():
            for dim, n in day_counts.items():
                totals[dim] = totals.get(dim, 0) + n
        if not totals:
            continue
        first_day = min(by_date.keys())
        days_covered = len(by_date)

        def _plural(word: str, n: int) -> str:
            return word if n == 1 or word.endswith("s") else word + "s"

        parts = ", ".join(f"{n} {_plural(dim.lower(), n)}"
                          for dim, n in sorted(totals.items(), key=lambda kv: -kv[1]))
        out.append(f"{label}: {parts} recorded by App Store Connect since {first_day} "
                   f"({days_covered} day(s) of data so far, from {name}). Too new for a rate yet.")
    return out


# ---------------------------------------------------------------- rendering

CSS = """
/* Dark by default, whatever the machine is set to (no prefers-color-scheme rules). Light is an opt-in from the
   Theme button, remembered in localStorage ("dash-theme"). color-scheme makes scrollbars and form controls match. */
:root{
  color-scheme:dark;
  --bg:oklch(16% 0.03 310); --panel:oklch(21% 0.035 310);
  --ink:oklch(96% 0.01 310); --muted:oklch(72% 0.03 300);
  --line:oklch(32% 0.05 310); --purple:oklch(78% 0.16 310);
  --purple-soft:oklch(28% 0.06 310); --good:oklch(78% 0.16 150);
  --bad:oklch(72% 0.16 25); --radius:14px;
  --on-purple:oklch(18% 0.06 310); --est:oklch(52% 0.11 310); --trend:oklch(80% 0.14 70);
  --chip:oklch(26% 0.04 310);
}
:root[data-theme="light"]{
  color-scheme:light;
  --bg:oklch(96.5% 0.008 310); --panel:oklch(99.5% 0.003 310);
  --ink:oklch(24% 0.03 310); --muted:oklch(45% 0.03 300);
  --line:oklch(88% 0.02 310); --purple:oklch(50% 0.19 310);
  --purple-soft:oklch(92% 0.035 310); --good:oklch(44% 0.13 150);
  --bad:oklch(50% 0.18 25);
  --on-purple:oklch(99% 0.01 310); --est:oklch(80% 0.09 310); --trend:oklch(52% 0.15 55);
  --chip:oklch(94% 0.02 310);
}
:root[data-theme="light"] .weekly-chart,:root[data-theme="light"] .rev-legend-item i{filter:brightness(.74) saturate(1.2)}
*{box-sizing:border-box}
body{
  margin:0; padding:clamp(20px,4vw,48px); background:var(--bg); color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1080px;margin:0 auto}
header{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px 24px;margin-bottom:14px}
header .head-title{min-width:0}
h1{font-size:clamp(24px,3vw,30px);letter-spacing:-.02em;margin:0;font-weight:640}
.stamp{color:var(--muted);font-size:13px;margin:4px 0 0}
h2{font-size:16px;margin:30px 0 12px;font-weight:650;color:var(--ink)}
:focus-visible{outline:2px solid var(--purple);outline-offset:2px}
body{font-variant-numeric:lining-nums}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px;align-items:start;margin-bottom:18px}
/* Sales sits above the traffic cards: it is the number the rest of the page
   exists to move, so it gets the top of the screen and the largest type. */
.sales{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:22px 24px;margin:0 0 22px}
.sales h2{margin:0 0 6px;font-size:1rem;color:var(--ink);font-weight:650}
.sales-figures{display:flex;flex-wrap:wrap;gap:12px 32px;align-items:baseline;margin:10px 0 4px}
.sales-big{font-size:1.6rem;font-weight:700;line-height:1.1;color:var(--ink);font-variant-numeric:tabular-nums}
.sales-sub{font-size:.9rem;color:var(--muted)}
.sales-figure-label{display:block;font-size:.78rem;color:var(--muted);margin-bottom:6px;
  text-transform:none;letter-spacing:.01em}
.sales-secondary{font-size:1.35rem;font-weight:650;line-height:1.1;font-variant-numeric:tabular-nums}
.sales-split{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 0}
.sales-chip{background:var(--chip);border-radius:8px;padding:4px 10px;font-size:.85rem;font-variant-numeric:tabular-nums}
.sales-chip b{color:var(--ink);font-weight:650}
.sales-chip span{color:var(--muted)}
.sales-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:22px;margin-top:18px}
.sales table{width:100%;border-collapse:collapse;font-size:.87rem}
.sales th.num,.sales-list th.num{text-align:right}
.sales th{text-align:left;font-weight:600;color:var(--muted);padding:4px 8px 6px 0;
  border-bottom:1px solid var(--line);font-size:.78rem}
.sales td{padding:5px 8px 5px 0;border-bottom:1px solid var(--line);color:var(--ink)}
.sales td.num{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink);white-space:nowrap}
.sales .who{color:var(--muted);font-size:.82rem}
.sales-none{color:var(--muted);margin:8px 0 0}
.rev-chart{width:100%;height:auto;margin-top:10px}
.sales h3{font-size:.9rem;font-weight:650;color:var(--ink);margin:24px 0 8px}
.metric-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px 24px;margin:12px 0 4px}
.tile{padding:2px 0 0}
.sales tr.total td{font-weight:600;border-top:2px solid var(--line)}
.tile b{display:block;font-size:1.3rem;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}
.tile span{display:block;color:var(--muted);font-size:.78rem;margin-top:3px}
.tile em{display:block;font-style:normal;font-size:.78rem;margin-top:3px}
.weekly-chart{width:100%;height:auto;display:block}
.cust-line{color:var(--ink);font-size:.88rem;margin:0}
.events{margin:0;padding-left:18px;font-size:.88rem;color:var(--ink)}
.events li{margin:3px 0}
.rev-legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:6px}
.rev-legend-item{display:flex;align-items:center;gap:6px;font-size:.82rem;color:var(--muted)}
.rev-legend-item i{display:inline-block;width:10px;height:10px;border-radius:3px}
.rev-legend-proj{background:none!important;border:1.5px dashed var(--muted)}
.sales-foot{color:var(--muted);font-size:.8rem;margin:14px 0 0;max-width:80ch}
.sales-foot a{color:var(--purple)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px}
.site-name{font-size:15px;font-weight:640;margin:0}
.site-dom{color:var(--muted);font-size:13px;margin:2px 0 16px}
.big{font-size:32px;font-weight:650;letter-spacing:-.02em;line-height:1.1;font-variant-numeric:tabular-nums}
.big-label{color:var(--muted);font-size:13px;margin-top:4px}
.delta{display:inline-block;margin-left:8px;font-size:14px;font-weight:600}
.up{color:var(--good)} .down{color:var(--bad)} .flat{color:var(--muted)}
.row{display:flex;gap:26px;margin-top:16px;flex-wrap:wrap}
.row div span{display:block}
.row .n{font-size:18px;font-weight:640;font-variant-numeric:tabular-nums}
.row .l{color:var(--muted);font-size:12px}
.dev-row{gap:10px 22px;margin-top:12px}
.dev-row .l{max-width:11em}
.spark{margin-top:18px}
.spark svg{width:100%;height:52px;display:block;overflow:visible}
.spark rect{fill:var(--purple)}
.spark rect.today{fill:var(--purple);opacity:.45}
.spark-x{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin-top:5px}
.checkout-spark{margin-top:16px;padding-top:14px;border-top:1px solid var(--line)}
.trend{margin-top:10px}
.trend svg{width:100%;height:40px;display:block;overflow:visible}
.trend .tline{fill:none;stroke:var(--purple);stroke-width:2;vector-effect:non-scaling-stroke}
.trend-x{display:flex;justify-content:space-between;align-items:baseline;color:var(--muted);font-size:11px;margin-top:6px}
.trend-x .delta{font-weight:650;font-size:12px}
ul.obs{list-style:none;padding:0;margin:0}
ul.obs li{background:var(--panel);border:1px solid var(--line);border-left:1px solid var(--line);
  border-radius:var(--radius);padding:13px 16px;margin-bottom:9px;font-size:15px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--muted);font-weight:600;font-size:12px;
  padding:0 0 8px;border-bottom:1px solid var(--line)}
td{padding:8px 0;border-bottom:1px solid var(--line);vertical-align:top}
th.num{text-align:right;white-space:nowrap;padding-left:12px}
td.num{text-align:right;font-variant-numeric:tabular-nums;width:64px;color:var(--muted);white-space:nowrap;padding-left:12px}
td.num.who{color:var(--muted)}
td.k{word-break:break-word}
.tables{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;align-items:start}
.funnel{display:flex;flex-direction:column;gap:10px}
.fstep{display:grid;grid-template-columns:5.2em minmax(0,1fr) auto;align-items:baseline;gap:8px;
  padding:9px 0;border-bottom:1px solid var(--line)}
.fstep:last-child{border-bottom:0}
.fstep .fn{font-size:18px;font-weight:640;font-variant-numeric:tabular-nums;white-space:nowrap}
.fstep .fn .delta{font-size:12px;margin-left:5px}
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
.cust-line b{font-variant-numeric:tabular-nums}
code{overflow-wrap:anywhere}
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
            parts.append(f"No {html.escape(b['label'])} yet in {b['views']} pageviews: the true rate is "
                         f"below <strong>{b['upper95']}%</strong> (95% confidence).")
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
      <p class="fan-note">In {n_p} days, 7-day pageviews should land between
        <strong>{last['p10']} and {last['p90']}</strong> (8 runs in 10), centred on {last['p50']}.
        No trend is assumed because none is detectable, so the centre drifts toward the
        {proj['window_days']}-day average of {proj['daily_mean']} a day. Read the band, not the line.</p>
    </div>"""


def sparkline(spark: list[dict], unit: str = "pageviews") -> str:
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
            f"<title>{d['day']}: {d['pv']} {unit}</title></rect>"
        )
    return (
        "<div class='spark'><svg viewBox='0 0 100 100' preserveAspectRatio='none'>"
        + "".join(bars)
        + f"</svg><div class='spark-x'><span>{spark[0]['day'][5:]}</span>"
        f"<span>{spark[-1]['day'][5:]} (today)</span></div></div>"
    )


def trend_line(points: list[dict], key: str, fmt=lambda v: f"{v:.0f}%") -> str:
    """A single line for `key` across `points`, scaled to its own range.

    Deliberately not a bar chart: this is meant to read as a slow drift
    (percentage-point share moving over weeks), and bars at this point
    density (one per archived snapshot, which can be irregular) read as
    noise where a line reads as a trend.
    """
    if len(points) < 2:
        return ""
    vals = [p[key] for p in points]
    peak, floor = max(vals + [0.0001]), min(vals + [0])
    n = len(points)
    x = lambda i: i / (n - 1) * 100
    y = lambda v: 100 - ((v - floor) / ((peak - floor) or 1)) * 100
    line = " ".join(f"{x(i):.2f},{y(v):.2f}" for i, v in enumerate(vals))
    first, last = points[0], points[-1]
    delta = last[key] - first[key]
    cls = "up" if delta > 0.5 else ("down" if delta < -0.5 else "flat")
    arrow = "&#9650;" if cls == "up" else ("&#9660;" if cls == "down" else "=")
    return f"""
    <div class="trend">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img"
           aria-label="Trend from {fmt(first[key])} on {first['day']} to {fmt(last[key])} on {last['day']}">
        <polyline class="tline" points="{line}"/>
      </svg>
      <div class="trend-x">
        <span>{first['day'][5:]}: {fmt(first[key])}</span>
        <span class="delta {cls}">{arrow} {fmt(abs(delta))}</span>
        <span>{last['day'][5:]}: {fmt(last[key])}</span>
      </div>
    </div>"""


def ai_trend_card(trend: list[dict]) -> str:
    if not trend:
        return ""
    first, last = trend[0], trend[-1]
    return (f"<div class='card'><h2 style='margin-top:0'>AI-assistant referral share</h2>"
            f"{trend_line(trend, 'pct')}"
            f"<p class='fnote'>Share of referred pageviews from ChatGPT, Perplexity, "
            f"Gemini and similar, read from each archived day's trailing "
            f"{FETCH_DAYS}-day referrer window ({first['day']} to {last['day']}, "
            f"{len(trend)} snapshot(s)). A slow structural drift, not a daily figure.</p></div>")


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

    # Checkout clicks, day by day rather than smoothed into a rate. A rate
    # can sit flat because a button is broken or because nobody's shopping;
    # a chart with a visible trailing zero streak tells the two apart at a
    # glance, which a single percentage can't.
    ck_spark = ""
    if s.get("checkout_spark"):
        pts = s["checkout_spark"]
        trailing_zero = 0
        for d in reversed(pts):
            if d["pv"]:
                break
            trailing_zero += 1
        flag = (f" <strong>Flat zero for the last {trailing_zero} days.</strong>"
                if trailing_zero >= 3 else "")
        ck_spark = (f"<div class='checkout-spark'>{sparkline(pts, 'checkout clicks')}"
                    f"<p class='fnote'>Checkout clicks, last 14 days.{flag}</p></div>")

    return (f"<div class='card'><h2 style='margin-top:0'>Conversion</h2>"
            f"<div class='funnel'>{cells}</div>"
            f"<p class='fnote'>Arrows compare with the previous 7 days. "
            f"Rates are share of pageviews, not unique visitors.</p>"
            f"{ck_spark}</div>")


def gsc_card(g: dict) -> str:
    """Headline Search Console figures, with the non-reader share broken out.

    Impressions and position are the useful pair here: position says whether
    Google ranks the site at all, impressions say whether anyone is searching
    for what it ranks for. Clicks alone can't separate those. Archived entries
    from before the device/query split carry neither key and render as before.
    """
    dev = g.get("devices") or {}
    split = g.get("split")

    def dcell(name: str) -> str:
        d = dev.get(name)
        if not d:
            return ""
        return (f"<div><span class='n'>{d['impressions']}</span>"
                f"<span class='l'>{name} impr. &middot; {d['clicks']} clicks "
                f"&middot; pos {d['position']:.1f}</span></div>")

    dev_row = ""
    if dev:
        dev_row = (f"<div class='row dev-row'>"
                   f"{dcell('mobile')}{dcell('desktop')}{dcell('tablet')}</div>")

    note = ""
    if split:
        tot = max(1, int(g["impressions"]))
        op, nat = split["operator"], split["natural"]
        note = (
            f"<p class='fnote'>Only {split['visible_impressions'] * 100 // tot}% of impressions "
            f"carry a visible query (Google hides rare ones). "
            f"Natural-language queries: {nat['impressions']} impressions, "
            f"{nat['top10_impressions']} of them at position 10 or better, "
            f"{nat['clicks']} clicks, average position {nat['position']:.1f}.")
        # Only warn when operator-style searches are a real share of what we
        # can see; a couple of stray ones are not worth a caveat.
        if op["impressions"] * 10 >= max(1, split["visible_impressions"]):
            note += (
                f" {op['impressions']} impressions are operator-style searches (quoted phrases, site:, paper ids), "
                f"probably citation checkers, which skew the headline position.")
        note += "</p>"

    return (
        f"<div class='card'><h2 style='margin-top:0'>Google Search</h2>"
        f"<div class='row'>"
        f"<div><span class='n'>{g['clicks']}</span><span class='l'>clicks</span></div>"
        f"<div><span class='n'>{g['impressions']}</span><span class='l'>impressions</span></div>"
        f"<div><span class='n'>{g['ctr']:.1f}%</span><span class='l'>CTR</span></div>"
        f"<div><span class='n'>{g['position']:.1f}</span><span class='l'>avg position</span></div>"
        f"</div>{dev_row}{note}"
        f"<p class='fnote'>{html.escape(g['start'])} to {html.escape(g['end'])} (Search Console lags two days).</p></div>")


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


def audience_card(a: dict | None) -> str:
    """Country, device, scroll depth and engaged time for a site whose beacon reports them (RubbleFront)."""
    if not a:
        return ""
    cc = list(a["countries"])
    if a["countryOther"]:
        cc.append({"key": "other countries", "count": a["countryOther"]})
    cc.append({"key": "unknown", "count": a["countryUnknown"]})
    out = (f"<div class='card'><h2 style='margin-top:0'>Reading depth</h2>"
           f"<p style='margin:0'>{html.escape(a['sentence'])}</p>"
           f"<p class='fnote'>A visit is counted when it sends its once-a-visit scroll event, so visits that leave "
           f"before it fires are missing from these three tables.</p></div>")
    out += table("Countries (page views)", cc, "No page views recorded in this window.")
    out += table("Devices (page views)", a["device"], "None recorded.")
    out += table("Scroll depth, percent of page (visits)", a["scroll"], "None recorded.")
    out += table("Time on page while visible (visits)", a["engaged"], "None recorded.")
    return out


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
        <div><span class="n">{s['last30']}</span><span class="l">last 30 days</span></div>
        <div><span class="n">{s['all_time']}</span><span class="l">tracked total</span></div>
      </div>
      {sparkline(s['spark'])}
      {fan_chart(s['spark'], s.get('proj'))}
      {bounds_note(s.get('bounds') or [])}
    </div>"""


PRODUCT_LABELS = {
    "scholar-belt": "Scholar Utility Belt Pro", "moderntex": "ModernTex", "outbound-veil": "Outbound Veil", "legroom": "Legroom", "keyfeel": "Keyfeel", "tapefolio": "Tapefolio", "panely": "Panely", "summonly": "Summonly", "freeboard": "Legroom", "app-suite": "Mac Suite", "bundle-2": "Mac Suite bundle (any 2)", "bundle-3": "Mac Suite bundle (any 3)", "cover-letter": "Cover letter", "anonymity-check": "Anonymity check",
    "citation-gap": "Citation gap", "revision-review": "Revision review",
    "response-review": "Response review", "resume-review": "Resume review",
    "kit-bundle": "Kit bundle", "kit-clip": "Clip pipeline kit",
    "kit-faceless": "Faceless pipeline kit", "kit-monetization": "Monetization kit",
    "paper-review-standard": "Paper review", "paper-review-journal": "Paper review (journal)",
    "paper-review-deep": "Paper review (deep)", "paper-review-pack-5": "Paper review 5-pack",
    "paper-review-pack-20": "Paper review 20-pack",
    "protein-playbook": "Protein playbook", "creatine-glp1": "Creatine guide",
    "muscleonglp-guide": "MuscleOnGLP guide", "complete-pack": "Complete pack",
    "no-gym-plan": "No-gym plan", "off-ramp": "Off-ramp guide",
    "tracker": "Tracker", "workbook": "Workbook",
    "vitae-plus-monthly": "Vitae Plus (monthly)", "vitae-plus-annual": "Vitae Plus (annual)",
    "digest-monthly": "Digest (monthly)", "digest-annual": "Digest (annual)",
    "sheet-submission": "Submission tracker (sheet)", "sheet-tenure": "Tenure tracker (sheet)",
    "sheet-jobmarket": "Job market tracker (sheet)",
    "sheet-grantpipeline": "Grant pipeline tracker (sheet)", "sheet-reviewmatrix": "Screening matrix (sheet)",
    "sheet-bundle": "Researcher sheet bundle", "sheet-other": "Spreadsheet (unmatched listing)",
    "photo-print": "Photo print (Etsy)", "live-scholar": "Live Citation Dashboard",
    "live-funding": "Live Funding Feed", "tracker-sheet": "GLP-1 tracker (sheet)",
}


def orders(n: int) -> str:
    return f"{n} order" if n == 1 else f"{n} orders"


CLUSTER_GAP_HOURS = 48   # orders closer together than this count as one burst


def _parse_sale_dt(s: str) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return None


def sales_clusters(recent: list[dict]) -> list[dict]:
    """Group orders that landed within CLUSTER_GAP_HOURS of each other.

    7 all-time orders is too few for a smoothed weekly rate to mean
    anything -- 5 of the first 6 ModernTex sales landed within a single
    20-hour window on 2026-09-05, which a "$X/week" figure would present as
    a steady rate rather than the one-day launch spike it actually was.
    Whether recent orders are one burst or spread out is the more honest
    question, and it's a cheap thing to compute from timestamps already on
    hand.
    """
    parsed = sorted(
        ((ts, r) for ts, r in ((_parse_sale_dt(r.get("date", "")), r) for r in recent) if ts),
        key=lambda t: t[0],
    )
    clusters: list[list[tuple]] = []
    for ts, r in parsed:
        if clusters and (ts - clusters[-1][-1][0]).total_seconds() <= CLUSTER_GAP_HOURS * 3600:
            clusters[-1].append((ts, r))
        else:
            clusters.append([(ts, r)])
    return [
        {"count": len(c), "span_hours": round((c[-1][0] - c[0][0]).total_seconds() / 3600, 1),
         "start": c[0][0], "end": c[-1][0]}
        for c in clusters
    ]


def sales_pattern_note(recent: list[dict]) -> str:
    """Plain-language read of whether sales are bursty or spread out."""
    clusters = sales_clusters(recent)
    total = sum(c["count"] for c in clusters)
    if total < 2:
        return ""
    biggest = max(clusters, key=lambda c: c["count"])
    if biggest["count"] < 2:
        return ""  # every order isolated -- a trickle, not a caveat worth raising
    when = biggest["start"].strftime("%b %-d")
    span = biggest["span_hours"]
    span_txt = f"{span:.0f}-hour" if span < 48 else f"{span / 24:.1f}-day"
    if len(clusters) == 1:
        return (f"All {total} order(s) landed within one {span_txt} window on {when} "
                f"— a launch burst so far, not yet a repeating rate.")
    share = round(biggest["count"] / total * 100)
    return (f"{biggest['count']} of {total} orders ({share}%) landed within a single "
            f"{span_txt} window on {when}; the rest were spread out.")


def days_since_last_order(recent: list[dict], generated_at: str | None) -> str:
    """'N days ago' rather than folding recency into a smoothed rate.

    A $X/30d figure reads the same whether the last sale was yesterday or
    three weeks ago. At 7 all-time orders that distinction is the more
    useful number.
    """
    dts = [t for t in (_parse_sale_dt(r.get("date", "")) for r in recent) if t]
    if not dts:
        return ""
    now = None
    if generated_at:
        try:
            now = dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            now = None
    now = now or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    days = max(0, int((now - max(dts)).total_seconds() // 86400))
    return "today" if days == 0 else ("1 day ago" if days == 1 else f"{days} days ago")


def money(cents: int) -> str:
    """Whole dollars stay whole: $40, not $40.00. Cents only when there are any."""
    return f"${cents / 100:,.2f}".replace(".00", "") if cents % 100 else f"${cents // 100:,}"


def sales_block(sales: dict | None) -> str:
    """The revenue panel that sits above everything else."""
    if not sales:
        return ("<section class='sales'><h2>Sales</h2>"
                "<p class='sales-none'>Stripe could not be reached on this run. "
                "Traffic figures below are unaffected.</p></section>")

    win, all_time = sales.get("window", {}), sales.get("allTime", {})
    days = win.get("days", FETCH_DAYS)
    bal = sales.get("balance") or {}

    chips = "".join(
        f"<span class='sales-chip'><b>{html.escape(s['label'])}</b> "
        f"<span>{money(s['windowGross'])} in {days}d · {money(s['gross'])} all time</span></span>"
        for s in sales.get("bySite", [])
    ) or "<span class='sales-chip'><span>No site has sold yet.</span></span>"

    prod_rows = "".join(
        f"<tr><td>{html.escape(PRODUCT_LABELS.get(r['key'], r['key']))}</td>"
        f"<td class='num'>{r['orders']}</td><td class='num'>{money(r['gross'])}</td>"
        f"<td class='who'>{html.escape(r['lastOrder'])}</td></tr>"
        for r in sales.get("byProduct", [])
    ) or "<tr><td colspan='4' class='who'>Nothing sold yet.</td></tr>"

    recent_rows = "".join(
        f"<tr><td class='who'>{html.escape(r['date'])}</td>"
        f"<td>{html.escape(PRODUCT_LABELS.get(r['product'], r['product']))}</td>"
        f"<td class='num'>{money(r['amount'])}</td>"
        f"<td class='who'>{html.escape(r['email'])}</td></tr>"
        for r in sales.get("recent", [])[:8]
    ) or "<tr><td colspan='4' class='who'>No orders yet.</td></tr>"

    recent = sales.get("recent", [])
    last_order = days_since_last_order(recent, sales.get("generatedAt"))
    notes = []
    pattern = sales_pattern_note(recent)
    if pattern:
        notes.append(pattern)
    if bal:
        notes.append(f"Stripe balance: {money(bal.get('available', 0))} available, "
                     f"{money(bal.get('pending', 0))} pending.")
    st = sales.get("selfTests") or {}
    if st.get("orders"):
        n = st["orders"]
        notes.append(f"{n} owner test purchase{'' if n == 1 else 's'} "
                     f"({money(st.get('gross', 0))}) excluded from every figure here.")
    lc = sales.get("lifecycle") or {}
    if lc:
        tr = lc.get("moderntex_trial") or {}
        notes.append(
            f"Follow-up emails: {tr.get('signups', 0)} ModernTex trial sign-up"
            f"{'' if tr.get('signups', 0) == 1 else 's'}, {tr.get('bought', 0)} later bought.")
    notes.append("Gross: refunds and Stripe fees are not deducted. The all-sales list above is net.")
    if sales.get("truncated"):
        notes.append("Older orders beyond the pagination cap are not counted.")

    return f"""<section class="sales">
  <h2>Card orders &middot; Stripe, gross</h2>
  <p class="cust-line">Last {days} days: <b>{money(win.get('gross', 0))}</b>, {orders(win.get('orders', 0))}.
    All time: <b>{money(all_time.get('gross', 0))}</b>, {orders(all_time.get('orders', 0))}.{
    f" Last order {html.escape(last_order)}." if last_order else ""}</p>
  <div class="sales-split">{chips}</div>
  <div class="sales-cols">
    <div>
      <table><thead><tr><th>Product</th><th class="num">Orders</th>
      <th class="num">Gross</th><th>Last</th></tr></thead>
      <tbody>{prod_rows}</tbody></table>
    </div>
    <div>
      <table><thead><tr><th>Recent</th><th>Product</th>
      <th class="num">Amount</th><th>Buyer</th></tr></thead>
      <tbody>{recent_rows}</tbody></table>
    </div>
  </div>
  <p class="sales-foot">{html.escape(" ".join(notes))}</p>
</section>"""



def appstore_summary(app: dict | None) -> dict | None:
    """The numbers the panel, the observations and the terminal line all share."""
    if not app:
        return None
    days = app.get("days", {})
    today = dt.date.today()
    def window(n: int) -> dict[str, int]:
        lo = (today - dt.timedelta(days=n)).isoformat()
        tot = {"downloads": 0, "redownloads": 0, "updates": 0, "proUnits": 0, "proPromo": 0}
        for k, v in days.items():
            if k >= lo:
                for m in tot:
                    tot[m] += v.get(m, 0)
        return tot
    countries: dict[str, int] = {}
    for k, v in days.items():
        if k >= (today - dt.timedelta(days=30)).isoformat():
            for c, n in v.get("countries", {}).items():
                countries[c] = countries.get(c, 0) + n
    proceeds: dict[str, float] = {}
    for v in days.values():
        for cur, amt in v.get("proceeds", {}).items():
            proceeds[cur] = round(proceeds.get(cur, 0.0) + amt, 2)
    spark = []
    for i in range(13, -1, -1):
        day = (today - dt.timedelta(days=i)).isoformat()
        spark.append({"day": day, "pv": days.get(day, {}).get("downloads", 0)})
    all_time = {"downloads": sum(v.get("downloads", 0) for v in days.values()),
                "redownloads": sum(v.get("redownloads", 0) for v in days.values()),
                "desktopDownloads": sum(v.get("desktopDownloads", 0) for v in days.values()),
                "proUnits": sum(v.get("proUnits", 0) for v in days.values()),
                "proPromo": sum(v.get("proPromo", 0) for v in days.values())}
    # analytics funnel, if Apple has delivered anything yet
    an = app.get("analytics", {}) or {}
    funnel = None
    eng = an.get("reports", {}).get("App Store Discovery and Engagement Standard", {}).get("byDate", {})
    if eng:
        recent = sorted(eng)[-7:]
        agg: dict[str, int] = {}
        for d_ in recent:
            for dim, n in eng[d_].items():
                agg[dim] = agg.get(dim, 0) + n
        def pick(*needles):
            return sum(v for k, v in agg.items() if any(nd in k.lower() for nd in needles))
        imps, views = pick("impression"), pick("page view", "product page")
        dl7 = window(7)["downloads"]
        funnel = {"days": len(recent), "impressions": imps, "pageViews": views, "downloads": dl7,
                  "conversion": (dl7 / views * 100) if views else None, "dims": agg}
    return {"label": app.get("label", "App"), "w7": window(7), "w30": window(30), "allTime": all_time,
            "proceeds": proceeds, "spark": spark, "funnel": funnel, "analyticsNote": an.get("note", ""),
            "countries": dict(sorted(countries.items(), key=lambda kv: -kv[1])[:5]),
            "latestDay": max(days) if days else None, "launch": app.get("launch")}


def appstore_block(app: dict | None) -> str:
    """App Store panel for GlobePin, styled like the Sales panel it sits under."""
    if app is None:
        return ""
    sm = appstore_summary(app)
    if not sm:
        return ("<section class='sales appstore'><h2>App Store · GlobePin</h2>"
                "<p class='sales-none'>App Store Connect could not be reached on this run.</p></section>")
    w7, w30, at = sm["w7"], sm["w30"], sm["allTime"]
    usd = sm["proceeds"].get("USD", 0.0)
    other = {k: v for k, v in sm["proceeds"].items() if k != "USD" and v}
    proceeds_txt = f"${usd:,.2f}" + (f" + {', '.join(f'{v:,.2f} {k}' for k, v in other.items())}" if other else "")
    if sm["funnel"]:
        f = sm["funnel"]
        conv = f"{f['conversion']:.1f}%" if f["conversion"] is not None else "–"
        funnel_html = (f"<div class='sales-split'>"
                       f"<span class='sales-chip'><b>{f['impressions']:,}</b> <span>impressions</span></span>"
                       f"<span class='sales-chip'><b>{f['pageViews']:,}</b> <span>product page views</span></span>"
                       f"<span class='sales-chip'><b>{conv}</b> <span>page view → download, last {f['days']}d</span></span>"
                       f"</div>")
    else:
        note = html.escape(sm["analyticsNote"] or "Apple has not generated the first report yet")
        funnel_html = (f"<p class='sales-none'>Impressions, page views and conversion: {note}. "
                       f"Analytics reports arrive 2–3 days behind and only from the day the request was created (2026-09-10).</p>")
    return f"""
<section class="sales appstore">
  <h2>App Store · {html.escape(sm['label'])}</h2>
  <div class="sales-figures">
    <div>
      <span class="sales-figure-label">Downloads, last 7 days</span>
      <span class="sales-big">{w7['downloads']:,}</span>
      <span class="sales-sub"> · {w30['downloads']:,} in 30d · {at['downloads']:,} first-time since launch{f" · {at['redownloads']:,} redownloads" if at.get('redownloads') else ''}{f" · {at['desktopDownloads']:,} on Mac (left out, as Apple's Analytics does)" if at.get('desktopDownloads') else ''}</span>
    </div>
    <div>
      <span class="sales-figure-label">Pro proceeds, since launch</span>
      <span class="sales-secondary">{html.escape(proceeds_txt)}</span>
      <span class="sales-sub"> · {at['proUnits']} paid Pro purchase{'' if at['proUnits'] == 1 else 's'}{f" · {at['proPromo']} promo-code redemption{'' if at['proPromo'] == 1 else 's'}" if at['proPromo'] else ''}</span>
    </div>
    <div>
      <span class="sales-figure-label">Last 30 days</span>
      <span class="sales-secondary">{w30['updates']:,} <span class="sales-sub">updates</span> &nbsp;{w30['redownloads']:,} <span class="sales-sub">redownloads</span></span>
    </div>
  </div>
  {sparkline(sm['spark'], 'downloads')}
  {("<div class='sales-split'>" + "".join(f"<span class='sales-chip'><b>{html.escape(c)}</b> <span>{n} download{'' if n == 1 else 's'}</span></span>" for c, n in sm['countries'].items()) + "</div>") if sm['countries'] else ''}
  {funnel_html}
  <p class="sales-foot">Sales &amp; Trends lag one day (latest: {html.escape(sm['latestDay'] or '—')}); a day with no report is shown as 0. Proceeds are after Apple's commission.</p>
</section>"""


def chrome_web_store_block(cws: dict | None) -> str:
    """Scholar Utility Belt's Chrome Web Store panel."""
    if not cws:
        return ""
    return f"""
<section class="sales appstore">
  <h2>Chrome Web Store · {html.escape(cws['label'])}</h2>
  <div class="sales-figures">
    <div>
      <span class="sales-figure-label">Installed users</span>
      <span class="sales-big">{html.escape(cws['users'])}</span>
    </div>
  </div>
  <p class="sales-foot">Rounded by Google to the nearest bucket, from the public
    <a href="{html.escape(cws['url'])}">store listing</a> (as of {html.escape(cws['asOf'])}).</p>
</section>"""


# ---------------------------------------------------------------- manual ad platforms
#
# Some ad platforms have no API path we're willing to automate — Apple Search
# Ads reporting sits behind an Apple ID sign-in (2FA, no service-account
# option), so there's no unattended way to pull it. Rather than leave those
# numbers out of the dashboard entirely, they're read by hand from the
# platform's own UI during a session and recorded to MANUAL_ADS_PATH; this
# section renders whatever was last recorded, same as any other card, so a
# manual pull from last week still shows (dated) instead of vanishing.

MANUAL_ADS_PATH = OUT_DIR / "manual-ads.json"


def load_manual_ads() -> dict:
    if not MANUAL_ADS_PATH.exists():
        return {}
    try:
        return json.loads(MANUAL_ADS_PATH.read_text())
    except Exception:
        return {}


def manual_ads_block(data: dict, admob: dict | None = None) -> str:
    asa = data.get("appleSearchAds")
    globepin_admob = (admob or {}).get("globepin")
    if not asa and not globepin_admob:
        return ""

    asa_html = ""
    spend_total = 0.0
    asa_stale = False
    if asa:
        try:
            asa_stale = (dt.date.today() - dt.date.fromisoformat(str(asa.get("asOf"))[:10])).days > 14
        except ValueError:
            asa_stale = False
    if asa and asa_stale:
        cs = asa.get("campaigns", [])
        asa_html = (f"<p class='cust-line'>Apple Search Ads: no reading since {html.escape(str(asa.get('asOf')))}. "
                    f"That reading ({html.escape(asa.get('window', '').lower())}) was ${sum(c.get('spend', 0) for c in cs):,.2f} spent, "
                    f"{sum(c.get('installs', 0) for c in cs):,} installs.</p>")
        asa = None
    if asa:
        chips = "".join(
            f"<span class='sales-chip'><b>${c.get('spend', 0):,.2f}</b> <span>spend</span></span>"
            f"<span class='sales-chip'><b>{c.get('impressions', 0):,}</b> <span>impressions</span></span>"
            f"<span class='sales-chip'><b>{c.get('taps', 0):,}</b> <span>taps</span></span>"
            f"<span class='sales-chip'><b>{c.get('installs', 0):,}</b> <span>installs</span></span>"
            for c in asa.get("campaigns", [])
        )
        spend_total = sum(c.get("spend", 0) for c in asa.get("campaigns", []))
        campaign_names = ", ".join(c.get("key", "campaign") for c in asa.get("campaigns", []))
        note = (f"<p class='sales-foot'>{html.escape(asa['note'])}</p>" if asa.get("note") else "")
        source = ("pulled from the Apple Search Ads API" if asa.get("source") == "api" else
                  "read by hand from app-ads.apple.com; set up the API user (ASA_* in traffic.env) "
                  "to make this automatic")
        terms = asa.get("searchTerms") or []
        terms_html = ""
        if terms:
            trows = "".join(
                f"<tr><td>{html.escape(t['term'])}</td><td>{html.escape(t.get('keyword', ''))}</td>"
                f"<td class='num'>{t['impressions']:,}</td><td class='num'>{t['taps']}</td>"
                f"<td class='num'>{t['installs']}</td><td class='num'>${t['spend']:,.2f}</td>"
                f"<td class='num'>{'—' if not t['installs'] else '$' + format(t['spend'] / t['installs'], ',.2f')}</td></tr>"
                for t in terms[:10])
            terms_html = f"""
  <h3>Search terms · last 7 days</h3>
  <table><thead><tr><th>Search term</th><th>Keyword</th><th class='num'>Impr.</th><th class='num'>Taps</th>
    <th class='num'>Installs</th><th class='num'>Spend</th><th class='num'>Per install</th></tr></thead>
    <tbody>{trows}</tbody></table>"""
        asa_html = f"""
  <h3>Apple Search Ads · spend</h3>
  <p class="sales-foot">{html.escape(campaign_names)} — {source}
    ({html.escape(asa.get('window', ''))}, as of {html.escape(asa.get('asOf', '?'))}).</p>
  <div class="sales-split">{chips}</div>
  {note}{terms_html}"""

    admob_html = ""
    earnings_total = None
    if globepin_admob and not globepin_admob.get("error"):
        earnings_total = globepin_admob["earnings"]
        admob_chips = (
            f"<span class='sales-chip'><b>${globepin_admob['earnings']:,.2f}</b> <span>earned</span></span>"
            f"<span class='sales-chip'><b>{globepin_admob['impressions']:,}</b> <span>ad impressions</span></span>"
            f"<span class='sales-chip'><b>{globepin_admob['clicks']:,}</b> <span>ad clicks</span></span>"
            f"<span class='sales-chip'><b>{globepin_admob['matchedRequests']:,}</b> <span>matched requests</span></span>"
        )
        admob_html = f"""
  <h3>AdMob · in-app ad earnings</h3>
  <p class="sales-foot">{html.escape(globepin_admob['label'])}, {globepin_admob['start']} to
    {globepin_admob['end']} ({globepin_admob['days']}d) — automated pull via the AdMob API.</p>
  <div class="sales-split">{admob_chips}</div>"""
    elif globepin_admob and globepin_admob.get("error"):
        admob_html = (f"<p class='sales-foot'>AdMob (GlobePin): unavailable this run "
                       f"({html.escape(globepin_admob['error'][:120])}).</p>")

    compare_html = ""
    if asa and earnings_total is not None and not asa_stale:
        net = earnings_total - spend_total
        verdict = ("still well behind" if net < -spend_total * 0.5 else
                   "behind" if net < 0 else "ahead")
        compare_html = (f"<p class='sales-foot'><b>GlobePin ads, same window:</b> "
                         f"${spend_total:,.2f} spent on Apple Search Ads vs "
                         f"${earnings_total:,.2f} earned from AdMob — {verdict} "
                         f"(net {'-' if net < 0 else '+'}${abs(net):,.2f}). Early days; "
                         f"this compares paid-install spend against ad revenue from the whole "
                         f"install base, not just paid installs, so it is not a strict ROAS.</p>")

    return f"""
<section class="sales appstore">
  <h2>Ads · GlobePin</h2>
  {asa_html}
  {admob_html}
  {compare_html}
</section>"""


# ---------------------------------------------------------------- revenue metrics
#
# The in-house version of what an app-revenue service (RevenueCat and the like)
# reports: a transaction ledger kept across runs, the last 28 days against the
# 28 before, conversion from install or trial to paid per product, customer
# counts and lifetime value, acquisition cost against revenue per customer, and
# a feed of what changed since the previous run. All of it is derived from
# sources this script already reads: Stripe (through sales.mjs, whose ledger
# carries fees, refunds and hashed customer ids, never emails), App Store
# Connect sales reports, the site beacons and the two manual ad readings. No
# app ships a new SDK and no new party receives customer data.

METRICS_DAYS = 28
PRODUCT_GROUPS = [
    ("ModernTex", "var(--purple)"),
    ("Outbound Veil", "oklch(66% 0.2 300)"),
    ("Scholar Utility Belt Pro", "oklch(72% 0.13 150)"),
    ("Legroom", "oklch(72% 0.14 215)"),
    ("Keyfeel", "oklch(74% 0.13 190)"),
    ("Tapefolio", "oklch(70% 0.14 255)"),
    ("Panely", "oklch(72% 0.13 165)"),
    ("Summonly", "oklch(70% 0.15 25)"),
    ("Mac Suite", "oklch(70% 0.18 330)"),
    ("Paper Review & tools", "oklch(75% 0.14 230)"),
    ("Kits", "oklch(80% 0.13 85)"),
    ("Spreadsheets", "oklch(70% 0.12 280)"),
    ("Subscriptions", "oklch(76% 0.13 165)"),
    ("Photo prints (Etsy)", "oklch(74% 0.10 20)"),
    ("MuscleOnGLP", "oklch(72% 0.15 35)"),
    ("GlobePin Pro", "var(--good)"),
]


def product_group(row: dict) -> str:
    product, site = row.get("product", ""), row.get("site", "")
    if product == "photo-print":
        return "Photo prints (Etsy)"
    if site == "muscleonglp":
        return "MuscleOnGLP"
    if product == "moderntex":
        return "ModernTex"
    if product == "outbound-veil":
        return "Outbound Veil"
    if product == "scholar-belt":
        return "Scholar Utility Belt Pro"
    if product in ("legroom", "freeboard"):  # Freeboard was its working name; Stripe still says so
        return "Legroom"
    if product == "keyfeel":
        return "Keyfeel"
    if product == "tapefolio":
        return "Tapefolio"
    if product == "panely":
        return "Panely"
    if product == "summonly":
        return "Summonly"
    if product in ("app-suite", "bundle-2", "bundle-3"):  # the Suite and its pick-2 / pick-3 bundles; revenue is not split per app
        return "Mac Suite"
    if product.startswith("kit-"):
        return "Kits"
    if product.startswith("sheet-"):
        return "Spreadsheets"
    if product.startswith(("vitae-plus", "digest-", "live-")):
        return "Subscriptions"
    return "Paper Review & tools"


def _row_net(r: dict) -> int:
    """Cents kept from one order: Stripe's net where known, gross otherwise,
    minus anything refunded."""
    base = r["net"] if r.get("net") is not None else r["gross"]
    return base - (r.get("refunded") or 0)


def merge_ledger(history: dict, sales: dict) -> list[dict] | None:
    """Fold this run's Stripe ledger into the archive, keyed by Stripe id, and
    return what is new since the last run. None when sales.mjs sent no ledger
    (older deploy). The first run returns [] so ten old orders are not
    announced as news."""
    rows = sales.get("ledger")
    if rows is None:
        return None
    archive = history.setdefault("ledger", {})
    first_time = not archive
    if first_time:
        history["ledgerSince"] = dt.date.today().isoformat()
    events = []
    for r in rows:
        old = archive.get(r["id"])
        if old is None and not first_time:
            events.append({"kind": r["kind"], "product": r["product"], "gross": r["gross"],
                           "net": r.get("net"), "ts": r["ts"]})
        elif old is not None and (r.get("refunded") or 0) > (old.get("refunded") or 0):
            events.append({"kind": "refund", "product": r["product"],
                           "gross": (r.get("refunded") or 0) - (old.get("refunded") or 0), "ts": r["ts"]})
        archive[r["id"]] = r
    # Free copies (a 100%-off code, $0) are no longer sent as orders since 2026-10-11;
    # drop the ones archived before that so they stop counting as customers.
    for k in [k for k, r in archive.items() if not r.get("market") and r.get("kind") == "purchase" and r.get("gross") == 0]:
        del archive[k]
    return events


# ---------------------------------------------------------------- marketplaces
#
# Etsy (PurplelinkDesigns), Gumroad (purplelink.gumroad.com) and Payhip sell the
# spreadsheet products and, on Etsy, photo prints. None of it passes through
# this Stripe account, so it needs its own readers:
#   * Gumroad: fetch_gumroad() below, unattended, personal access token.
#   * Etsy, Payhip (and Gumroad without a token): record_marketplaces.py reads the
#     signed-in automation Chrome and writes MARKETPLACES_PATH; run.sh's copy of
#     this script only merges that file.
# Every order becomes a ledger row: id "<marketplace>:<id>", kind "order".
#
# Fee schedules, checked 2026-09-29 (used only when the page/API gives no fee):
#   Etsy    6.5% transaction + 3% + $0.25 payment processing (US), $0.20 per listing
#           https://www.etsy.com/legal/fees/  (Etsy returns 403 to scripts, so the
#           figures are Etsy's published US schedule, not re-fetched today)
#   Gumroad 10% + $0.50 on direct sales, 30% on Discover; processing is included
#           https://gumroad.com/pricing  (the API's gumroad_fee is used when present)
#   Payhip  Free plan 5% transaction fee; PayPal/Stripe charge their standard rates on top
#           https://payhip.com/pricing  (processor assumed Stripe 2.9% + $0.30)
# Listing fees are per listing, not per order, so they are shown as a shop-level
# note and never spread over orders.
#
# Double counting: sales.mjs reads only this account's Checkout Sessions and
# subscription invoices (product metadata set by checkout.mjs). Gumroad is merchant
# of record and Payhip/Etsy settle in their own systems, so their sales never
# appear in that ledger. As a guard anyway, a marketplace row is dropped when a
# Stripe ledger row has the same product, the same gross and a timestamp within
# MARKETPLACE_DEDUPE_SECS.

MARKETPLACES_PATH = OUT_DIR / "marketplaces.json"
GUMROAD_TOKEN_ENV = "GUMROAD_TOKEN"
GUMROAD_API = "https://api.gumroad.com/v2/sales"
MARKETPLACE_LABELS = {"etsy": "Etsy", "gumroad": "Gumroad", "payhip": "Payhip", "extensionpay": "ExtensionPay"}
# ExtensionPay charges Scholar Utility Belt Pro through its own Stripe account (separate from the one sales.mjs reads),
# so it is read here with a restricted read-only key for that account. No key means no line, never an error.
EXTPAY_KEY_ENV = "STRIPE_EXTPAY_KEY"
STRIPE_API_BASE = "https://api.stripe.com/v1"
MARKETPLACE_STALE_DAYS = 2
MARKETPLACE_DEDUPE_SECS = 900
MARKETPLACE_EVENT_HOURS = 48
ETSY_SHEET_LISTING_FEES = 1.40   # 7 spreadsheet listings x $0.20, one time (2026-09-29)

# Order matters: the bundle title also names its parts.
SHEET_KEYWORDS = [
    ("bundle", "sheet-bundle", "purplelink"),
    ("glp-1", "tracker-sheet", "muscleonglp"), ("glp1", "tracker-sheet", "muscleonglp"),
    ("grant pipeline", "sheet-grantpipeline", "purplelink"),
    ("job market", "sheet-jobmarket", "purplelink"),
    ("screening matrix", "sheet-reviewmatrix", "purplelink"),
    ("systematic review", "sheet-reviewmatrix", "purplelink"),
    ("submission tracker", "sheet-submission", "purplelink"),
    ("tenure", "sheet-tenure", "purplelink"),
]


def marketplace_product(market: str, title: str) -> tuple[str, str]:
    """Listing title -> (product key, site). An unmatched Etsy title is taken to be
    a photo print (the shop's other stock); on Gumroad and Payhip everything for
    sale is a sheet, so an unmatched title stays in Spreadsheets."""
    if market == "extensionpay":
        return "scholar-belt", "purplelink"
    t = (title or "").lower()
    for kw, product, site in SHEET_KEYWORDS:
        if kw in t:
            return product, site
    if market == "etsy":
        return "photo-print", "purplelink"
    return "sheet-other", "purplelink"


def estimate_fee(market: str, gross: int) -> int:
    """Cents of fees from the published schedule (see the comment above)."""
    if market == "etsy":
        return round(gross * 0.065 + gross * 0.03 + 25)
    if market == "gumroad":
        return round(gross * 0.10 + 50)
    if market == "extensionpay":
        return round(gross * 0.029 + 30)     # Stripe's card rate; the real fee (incl. ExtensionPay's cut) comes from the charge
    return round(gross * 0.05 + gross * 0.029 + 30)


def marketplace_row(market: str, o: dict) -> dict | None:
    """One stored/API order -> a ledger row, or None when it is not a usable sale."""
    try:
        gross, ts = int(o["gross"]), float(o["ts"])
    except (KeyError, TypeError, ValueError):
        return None
    if gross <= 0:
        return None
    product, site = marketplace_product(market, o.get("title", ""))
    fee = o.get("fee")
    estimated = fee is None
    if estimated:
        fee = estimate_fee(market, gross)
    return {"id": f"{market}:{o['id']}", "kind": "order", "product": product, "site": site,
            "gross": gross, "fee": int(fee), "net": gross - int(fee), "feeEstimated": estimated,
            "refunded": int(o.get("refunded") or 0), "ts": ts, "market": market,
            "attr": {"first": {"s": market}}}


def load_marketplaces() -> dict:
    try:
        d = json.loads(MARKETPLACES_PATH.read_text())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def parse_gumroad_sale(s: dict) -> dict | None:
    """API sale -> the stored order shape (no buyer fields). None for a free or
    non-USD sale, which cannot be summed with the rest."""
    price = s.get("price")
    if not isinstance(price, (int, float)) or price <= 0 or (s.get("currency") or "usd").lower() != "usd":
        return None
    try:
        ts = dt.datetime.fromisoformat(str(s["created_at"]).replace("Z", "+00:00")).timestamp()
    except (KeyError, ValueError):
        return None
    refunded = int(s.get("amount_refunded_cents") or 0)
    if (s.get("refunded") or s.get("chargedback")) and not refunded:
        refunded = int(price)
    fee = s.get("gumroad_fee")
    return {"id": str(s["id"]), "ts": ts, "title": s.get("product_name", ""), "gross": int(price),
            "fee": int(fee) if isinstance(fee, (int, float)) else None, "refunded": refunded}


def fetch_gumroad(cfg: dict[str, str], since_days: int | None = None) -> dict | None:
    """Sales from the Gumroad API (GET /v2/sales, scope view_sales).

    Docs: https://gumroad.com/api . Each sale carries id, created_at, product_name,
    price (cents), gumroad_fee (cents, processing included), refunded,
    partially_refunded, amount_refunded_cents, chargedback, currency. Pages come
    back with next_page_key, passed on as page_key. Buyer emails are never read
    into the result. None when there is no token, {"error": ...} on failure.
    """
    token = cfg.get(GUMROAD_TOKEN_ENV)
    if not token:
        return None
    params = {"access_token": token}
    if since_days:
        params["after"] = (dt.date.today() - dt.timedelta(days=since_days)).isoformat()
    orders: list[dict] = []
    skipped = 0
    try:
        for _page in range(60):
            url = GUMROAD_API + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "purplelink-traffic-dashboard"})
            payload = None
            for attempt in range(RETRIES):
                if attempt:
                    time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
                try:
                    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as resp:
                        payload = json.loads(resp.read().decode("utf-8"))
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code < 500 and exc.code != 429:
                        return {"error": f"HTTP {exc.code}" + (" (token rejected)" if exc.code in (401, 403) else "")}
                except (OSError, http.client.HTTPException, json.JSONDecodeError):
                    pass
            if payload is None:
                return {"error": "unreachable"}
            if not payload.get("success", True):
                return {"error": str(payload.get("message") or "API refused")[:80]}
            for s in payload.get("sales", []):
                parsed = parse_gumroad_sale(s)
                if parsed:
                    orders.append(parsed)
                else:
                    skipped += 1
            key = payload.get("next_page_key")
            if not key:
                break
            params["page_key"] = key
    except Exception as exc:  # noqa: BLE001 -- never let this sink the run
        return {"error": str(exc)[:80]}
    return {"orders": orders, "skipped": skipped, "asOf": dt.datetime.now(dt.timezone.utc).isoformat()}


def _stripe_get(key: str, path: str, params: dict) -> dict:
    """GET one Stripe list page with a restricted key. Raises RuntimeError with a short reason."""
    import base64
    url = f"{STRIPE_API_BASE}/{path}?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={
        "Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode(),
        "User-Agent": "purplelink-traffic-dashboard", "Stripe-Version": "2024-06-20"})
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"HTTP {exc.code}" + (" (key rejected or missing a permission)" if exc.code in (401, 403) else ""))
        except (OSError, http.client.HTTPException, json.JSONDecodeError):
            pass
    raise RuntimeError("unreachable")


def parse_stripe_charge(c: dict) -> dict | None:
    """One Stripe charge -> the stored order shape, or None for a charge that is not a paid USD sale.
    The fee is the balance transaction's, which for a Connect charge includes ExtensionPay's cut."""
    try:
        gross = int(c["amount"])
        if not c.get("paid") or c.get("status") != "succeeded" or gross <= 0 or str(c.get("currency", "usd")).lower() != "usd":
            return None
        bt = c.get("balance_transaction")
        fee = bt.get("fee") if isinstance(bt, dict) else None
        refunded = int(c.get("amount_refunded") or 0)
        if c.get("refunded") and not refunded:
            refunded = gross
        return {"id": str(c["id"]), "ts": float(c["created"]), "gross": gross,
                "fee": int(fee) if isinstance(fee, (int, float)) else None, "refunded": refunded,
                "title": str(c.get("description") or "ExtensionPay")[:80]}
    except (KeyError, TypeError, ValueError):
        return None


def _monthly_cents(sub: dict) -> float:
    total = 0.0
    for it in ((sub.get("items") or {}).get("data") or []):
        price = it.get("price") or {}
        rec = price.get("recurring") or {}
        unit = price.get("unit_amount")
        if unit is None or not rec:
            continue
        n = max(1, int(rec.get("interval_count") or 1))
        per = {"month": 1 / n, "year": 1 / (12 * n), "week": 52 / 12 / n, "day": 30 / n}.get(rec.get("interval"), 0)
        total += unit * int(it.get("quantity") or 1) * per
    return total


def fetch_extpay(cfg: dict[str, str]) -> dict | None:
    """Scholar Utility Belt Pro sales from the Stripe account ExtensionPay charges through.

    Needs STRIPE_EXTPAY_KEY, a restricted key with read access to Charges and Subscriptions (a customer
    list is not needed). None when there is no key, {"error": ...} on failure. Buyer fields are never read.
    Subscriptions are best effort: a key without that permission still yields the charges.
    """
    key = cfg.get(EXTPAY_KEY_ENV)
    if not key:
        return None
    orders, skipped = [], 0
    try:
        params: dict = {"limit": 100, "expand[]": "data.balance_transaction"}
        for _page in range(20):
            payload = _stripe_get(key, "charges", params)
            data = payload.get("data") or []
            for c in data:
                row = parse_stripe_charge(c)
                if row:
                    orders.append(row)
                else:
                    skipped += 1
            if not payload.get("has_more") or not data:
                break
            params["starting_after"] = data[-1]["id"]
    except Exception as exc:  # noqa: BLE001 -- never let this sink the run
        return {"error": str(exc)[:80]}
    subs = None
    try:
        active = trialing = 0
        mrr = 0.0
        for status in ("active", "trialing"):
            sp = {"limit": 100, "status": status}
            for _page in range(10):
                payload = _stripe_get(key, "subscriptions", sp)
                data = payload.get("data") or []
                for sub in data:
                    if status == "active":
                        active += 1
                        mrr += _monthly_cents(sub)
                    else:
                        trialing += 1
                if not payload.get("has_more") or not data:
                    break
                sp["starting_after"] = data[-1]["id"]
        subs = {"active": active, "trialing": trialing, "mrr": round(mrr)}      # cents, like every other money figure here
    except Exception:  # noqa: BLE001
        subs = None
    return {"orders": orders, "skipped": skipped, "subs": subs, "asOf": dt.datetime.now(dt.timezone.utc).isoformat()}


def marketplace_step(history: dict, cfg: dict[str, str], fetch: bool) -> tuple[list[dict], bool]:
    """Fold marketplaces.json and (when fetching) the Gumroad API into the ledger.
    Returns (feed events, whether the ledger or meta changed)."""
    archive = history.setdefault("ledger", {})
    prior = history.get("marketplaceMeta") or {}
    data = load_marketplaces()
    incoming: dict[str, list[dict]] = {m: [] for m in MARKETPLACE_LABELS}
    for o in (data.get("orders") or {}).values():
        if o.get("site") in incoming:
            incoming[o["site"]].append(o)
    meta: dict[str, dict] = {}
    for m in MARKETPLACE_LABELS:
        meta[m] = {"asOf": (data.get("asOf") or {}).get(m), "status": (data.get("status") or {}).get(m)}
        if not meta[m]["asOf"] and (prior.get(m) or {}).get("asOf"):
            meta[m] = {"asOf": prior[m]["asOf"], "status": prior[m].get("status")}
        if (prior.get(m) or {}).get("api"):
            meta[m]["api"] = prior[m]["api"]
            # A --no-fetch re-render must not roll an API reading back to an older browser
            # reading left in marketplaces.json (Gumroad's froze there on 2026-10-09).
            if prior[m]["api"] == "ok" and (prior[m].get("asOf") or "") > (meta[m]["asOf"] or ""):
                meta[m] = {**prior[m]}

    if fetch:
        try:
            g = fetch_gumroad(cfg, 90 if any(k.startswith("gumroad:") for k in archive) else None)
        except Exception as exc:  # noqa: BLE001
            g = {"error": str(exc)[:80]}
        if g is None:
            print(f"  ! Gumroad: no token ({GUMROAD_TOKEN_ENV} not set in {CONFIG_PATH})", file=sys.stderr)
            meta["gumroad"]["api"] = "no token"
        elif g.get("error"):
            print(f"  ! Gumroad API: {g['error']}", file=sys.stderr)
            meta["gumroad"]["api"] = g["error"]
        else:
            # The API is authoritative for Gumroad and supersedes a browser reading.
            incoming["gumroad"] = g["orders"]
            meta["gumroad"] = {"asOf": g["asOf"], "status": "ok", "api": "ok"}
            print(f"  ok Gumroad API: {len(g['orders'])} paid sale(s) read")

    if fetch:
        try:
            x = fetch_extpay(cfg)
        except Exception as exc:  # noqa: BLE001
            x = {"error": str(exc)[:80]}
        if x is None:
            meta["extensionpay"]["api"] = "no key"                       # optional source: quiet when not set up
        elif x.get("error"):
            print(f"  ! ExtensionPay (Stripe): {x['error']}", file=sys.stderr)
            meta["extensionpay"]["api"] = x["error"]
        else:
            incoming["extensionpay"] = x["orders"]
            meta["extensionpay"] = {"asOf": x["asOf"], "status": "ok", "api": "ok", "subs": x["subs"]}
            print(f"  ok ExtensionPay (Stripe): {len(x['orders'])} paid charge(s) read")

    stripe_rows = [r for r in archive.values() if not r.get("market")]
    now = dt.datetime.now().timestamp()
    events, changed = [], False
    for m, orders in incoming.items():
        for o in orders:
            row = marketplace_row(m, o)
            if not row:
                continue
            if any(sr["product"] == row["product"] and sr["gross"] == row["gross"]
                   and abs(sr["ts"] - row["ts"]) <= MARKETPLACE_DEDUPE_SECS for sr in stripe_rows):
                continue
            old = archive.get(row["id"])
            if old == row:
                continue
            if old is None and row["ts"] >= now - MARKETPLACE_EVENT_HOURS * 3600:
                events.append({"kind": "purchase", "product": row["product"], "gross": row["gross"],
                               "net": row["net"], "ts": row["ts"], "via": MARKETPLACE_LABELS[m]})
            elif old is not None and row["refunded"] > (old.get("refunded") or 0):
                events.append({"kind": "refund", "product": row["product"], "via": MARKETPLACE_LABELS[m],
                               "gross": row["refunded"] - (old.get("refunded") or 0), "ts": row["ts"]})
            archive[row["id"]] = row
            changed = True
    if meta != prior:
        history["marketplaceMeta"] = meta
        changed = True
    return events, changed


def marketplace_summary(history: dict, days: int = 30) -> dict:
    """Per-marketplace figures for the sales panel, the terminal and the report."""
    rows = [r for r in (history.get("ledger") or {}).values() if r.get("market")]
    meta = history.get("marketplaceMeta") or {}
    now = dt.datetime.now().timestamp()
    today = dt.date.today()
    out = {}
    for m, label in MARKETPLACE_LABELS.items():
        mine = [r for r in rows if r["market"] == m]
        win = [r for r in mine if r["ts"] >= now - days * 86400]
        info = meta.get(m) or {}
        if m == "extensionpay" and not mine and info.get("api") != "ok":
            continue                                                   # optional source that is not set up: no row, no gap
        as_of = (info.get("asOf") or "")[:10]
        age = _days_since(as_of, today) if as_of else None
        status = info.get("status")
        issues = []
        if not as_of:
            issues.append("never read")
        elif age is not None and age > MARKETPLACE_STALE_DAYS:
            issues.append(f"last read {as_of}, {age} days ago")
        if status and status != "ok":
            issues.append(status)
        if m == "gumroad" and info.get("api") == "no token":
            issues.append("no API token")
        if m == "extensionpay" and info.get("api") not in (None, "ok", "no key"):
            issues.append(f"Stripe: {info['api']}")
        out[m] = {"label": label, "orders": len(mine), "windowOrders": len(win),
                  "gross": sum(r["gross"] for r in mine), "windowGross": sum(r["gross"] for r in win),
                  "windowNet": sum(_row_net(r) for r in win), "windowRefunded": sum(r["refunded"] for r in win),
                  "estimated": sum(1 for r in win if r.get("feeEstimated")),
                  "last": max((r["ts"] for r in mine), default=None), "asOf": as_of or None,
                  "issues": issues, "days": days}
    return out


def marketplaces_block(summary: dict | None) -> str:
    if not summary:
        return ""
    body, quiet = "", []
    for s in summary.values():
        if not s["orders"] and not s["windowOrders"]:
            quiet.append(s["label"])
            continue
        last = (dt.datetime.fromtimestamp(s["last"]).strftime("%Y-%m-%d") if s["last"] else "none yet")
        reading = html.escape(s["asOf"] or "never") + (
            f" <span class='who'>({html.escape('; '.join(s['issues']))})</span>" if s["issues"] else "")
        body += (f"<tr><td>{html.escape(s['label'])}</td><td class='num'>{s['windowOrders']}</td>"
                 f"<td class='num'>{money(s['windowGross'])}</td><td class='num'>{money(s['windowNet'])}</td>"
                 f"<td class='num'>{s['orders']} / {money(s['gross'])}</td><td class='who'>{last}</td>"
                 f"<td class='who'>{reading}</td></tr>")
    est = sum(s["estimated"] for s in summary.values())
    notes = [f"Net is after the marketplace's fees ({est} order(s) in the window use the published fee schedule). "
             f"Etsy listing fees for the 7 spreadsheet listings (${ETSY_SHEET_LISTING_FEES:.2f}, one time) are not in these figures."]
    quiet_html = (f"<p class='cust-line'>{html.escape(', '.join(quiet))}: no orders yet.</p>" if quiet else "")
    table_html = (f"""<table><thead><tr><th>Marketplace</th><th class="num">Orders, {summary['etsy']['days']}d</th>
    <th class="num">Gross</th><th class="num">Net</th><th class="num">All time</th><th>Last order</th>
    <th>Last read</th></tr></thead><tbody>{body}</tbody></table>""" if body else "")
    return f"""<section class="sales">
  <h2>Sales · marketplaces</h2>
  {table_html}{quiet_html}
  <p class="sales-foot">{html.escape(' '.join(notes))}</p>
</section>"""


QUEUE_INDEX = Path(os.environ.get("PURPLELINK_QUEUE") or Path.home() / ".purplelink" / "queue") / "queue.json"


def queue_summary() -> dict | None:
    """Approval-queue counts, read from the index approval_queue.py maintains. None when unset."""
    try:
        idx = json.loads(QUEUE_INDEX.read_text())
    except Exception:
        return None
    c, st = idx.get("counts", {}), idx.get("stats30", {})
    soon = 0
    for p in idx.get("pending", []):
        try:
            if (dt.date.fromisoformat(str(p["expires"])[:10]) - dt.date.today()).days <= 2:
                soon += 1
        except Exception:
            pass
    return {"pending": c.get("pending", 0), "needsWork": c.get("needs-work", 0), "approved": c.get("approved", 0),
            "soon": soon, "acceptance": st.get("acceptance_pct", 0), "decided": st.get("decided", 0),
            "expiredPct": st.get("expired_pct", 0), "updated": idx.get("updated", "")}


def print_queue(q: dict | None) -> None:
    if not q:
        return
    print(f"\n  Approval queue: {q['pending']} pending ({q['soon']} expiring within 2 days), {q['needsWork']} in needs-work, "
          f"{q['approved']} approved awaiting action; acceptance {q['acceptance']}% over {q['decided']} decisions, "
          f"expired unread {q['expiredPct']}%")


def queue_block() -> str:
    q = queue_summary()
    if not q:
        return ""
    watch = []
    if q["soon"]:
        watch.append(f"{q['soon']} expiring within 2 days")
    if q["needsWork"]:
        watch.append(f"{q['needsWork']} in needs-work")
    extra = f" ({', '.join(watch)})" if watch else ""
    return (f"<section class=\"sales\"><h2>Approval queue</h2><p class=\"cust-line\">"
            f"<b>{q['pending']}</b> pending{extra}, <b>{q['approved']}</b> approved and awaiting action.</p></section>")


AD_FUNNEL_SINCE = "2026-10-07"  # first day analytics.js sends the first-touch channel (ft) on funnel events


# Link checkers. Publishing a tagged link (a YouTube description, a Short) brings an automated visitor within minutes:
# exactly 2 page views per new URL, often with trial-download clicks, never a buy click (seen 2026-10-14 and again
# 2026-10-15 to 10-17; ~/.purplelink/latex-funnel/latex_funnel_report.py makes the same allowance). The site's bot
# filter matches user-agent words only and cannot see it, so the funnel subtracts an allowance per tagged URL
# published inside its window. tagged_links.json records hand-tagged batches; the how-to ledger adds its own videos.
LINK_CHECK_VIEWS_PER_URL = 2
LINK_CHECK_TRIALS_PER_URL = 2
# launchd runs a copy of this file from ~/.purplelink/traffic (see the photo-dashboard note below), so each file is
# looked up next to the script first and then at its place in the repo.
_REPO = Path("/Volumes/Extreme SSD/Purplelink LLC")


def _repo_file(rel: str) -> Path:
    here = Path(__file__).resolve()
    for cand in (here.parents[2] / rel if len(here.parents) > 2 else None, _REPO / rel):
        if cand is not None and cand.exists():
            return cand
    return _REPO / rel


TAGGED_LINKS_PATH = _repo_file("scripts/traffic-dashboard/tagged_links.json")
HOWTO_LEDGER_PATH = _repo_file("video/howto/ledger.json")
HOWTO_URLS_PER_VIDEO = 2  # the tutorial and its Short each carry one tagged link (scripts/howto-publish.py)


def tagged_link_batches() -> list[dict]:
    """[{date, channel, urls}] for every known publication of tagged links, newest last."""
    out: list[dict] = []
    try:
        out += [b for b in json.loads(TAGGED_LINKS_PATH.read_text()).get("batches", [])
                if b.get("date") and b.get("channel") and int(b.get("urls", 0)) > 0]
    except (OSError, ValueError):
        pass
    try:
        for v in json.loads(HOWTO_LEDGER_PATH.read_text()):
            if v.get("date"):
                out.append({"date": v["date"], "channel": "youtube-howto", "urls": HOWTO_URLS_PER_VIDEO,
                            "note": v.get("slug", "")})
    except (OSError, ValueError):
        pass
    return sorted(out, key=lambda b: b["date"])


def link_check_allowance(as_of: str, days: int, batches: list[dict] | None = None) -> dict:
    """{channel: urls published in the window ending as_of} (inclusive, `days` long)."""
    end = dt.date.fromisoformat(as_of)
    start = (end - dt.timedelta(days=days - 1)).isoformat()
    per: dict[str, int] = {}
    for b in tagged_link_batches() if batches is None else batches:
        if start <= b["date"] <= end.isoformat():
            per[b["channel"]] = per.get(b["channel"], 0) + int(b["urls"])
    return per


def human_estimate(pageviews: int, trials: int, urls: int) -> tuple[int, int]:
    """Page views and trials left after the link-check allowance for `urls` new tagged URLs (never below 0)."""
    return (max(0, pageviews - LINK_CHECK_VIEWS_PER_URL * urls),
            max(0, trials - LINK_CHECK_TRIALS_PER_URL * urls))


def looks_like_scanner(v: dict) -> bool:
    """A campaign tag with one or two page views in all and nothing else: what a mail security scanner leaves when
    it opens each link in an email before the reader does. Cannot be told from one real reader; marked, not removed."""
    return (0 < v.get("pageviews", 0) <= 2 and not sum((v.get("trial") or {}).values())
            and not sum((v.get("checkout") or {}).values()))


def print_ad_funnel(history: dict) -> None:
    """Channels through the funnel, from the site's own first-touch labels. Google Ads for ModernTex was turned
    off on 2026-10-19 and is no longer read or compared here. Nothing is printed until the site has recorded
    any channel labels."""
    af = history.get("adFunnel") or {}
    ch = af.get("channels") or {}
    if not ch:
        return
    days = af.get("days", AD_FUNNEL_DAYS)
    print(f"\n  Funnel by first-touch channel, last {days} days (tracking began {AD_FUNNEL_SINCE}; each visitor counted under how they first arrived)")
    allow = link_check_allowance(af.get("asOf") or dt.date.today().isoformat(), days)
    rows, scanners = [], []
    raw_trials = est_trials = 0
    for name, v in ch.items():
        paths = v.get("pageviewsByPath") or {}
        prod_views = sum(c for p, c in paths.items() if p.rstrip("/") in PRODUCT_PAGE_PATHS)
        trials = sum((v.get("trial") or {}).values())
        buys = sum((v.get("checkout") or {}).values())
        urls = allow.get(name, 0)
        hpv, htr = human_estimate(v.get("pageviews", 0), trials, urls)
        raw_trials, est_trials = raw_trials + trials, est_trials + htr
        if not urls and "." not in name and ":" not in name and name != "direct" and looks_like_scanner(v):
            scanners.append(name)
            continue
        rows.append((name, v.get("pageviews", 0), prod_views, trials, buys, urls, hpv, htr))
    rows.sort(key=lambda r: (-r[7], -r[4], -r[3], -r[1]))
    for name, pv, ppv, tr, bu, urls, hpv, htr in rows[:8]:
        line = f"   {name:<22} {pv:>4} page views ({ppv} on product pages)  {tr:>3} trial downloads  {bu:>3} buy clicks"
        if urls:
            line += f"  [est. human: {hpv} views, {htr} trials; {urls} tagged URL(s) published in the window]"
        print(line)
    if est_trials != raw_trials:
        print(f"   Trials, all channels: {raw_trials} counted, about {est_trials} after the link-check allowance "
              f"({LINK_CHECK_VIEWS_PER_URL} views and up to {LINK_CHECK_TRIALS_PER_URL} trials per new tagged URL; "
              "an estimate, a real early visitor is subtracted too)")
    if scanners:
        print(f"   Tags with only 1 or 2 views and nothing else (on an email tag this is often a mail scanner opening the "
              f"link; judge those emails by replies): {', '.join(sorted(scanners))}")
    heard = {}
    for r in (history.get("ledger") or {}).values():
        if r.get("heard"):
            heard[r["heard"]] = heard.get(r["heard"], 0) + 1
    if heard:
        print("   Buyers' own answer, 'How did you first hear about us?' (asked at checkout since 2026-10-11): "
              + ", ".join(f"{k} {v}" for k, v in sorted(heard.items(), key=lambda kv: -kv[1])))



def print_extensionpay(history: dict) -> None:
    """Scholar Utility Belt Pro in one line group; nothing at all until STRIPE_EXTPAY_KEY is set and has read once."""
    meta = (history.get("marketplaceMeta") or {}).get("extensionpay") or {}
    if meta.get("api") != "ok":
        return
    rows = [r for r in (history.get("ledger") or {}).values() if r.get("market") == "extensionpay"]
    now = dt.datetime.now().timestamp()
    win = [r for r in rows if r["ts"] >= now - 30 * 86400]
    users = ((history.get("chromeWebStore") or {}).get("users") or "").replace(",", "")
    installs = int(users) if users.isdigit() else None
    paid_customers = len(rows)
    conv = f" ({paid_customers / installs * 100:.1f}% of installs)" if installs and paid_customers else ""
    print("\n  Scholar Utility Belt Pro (ExtensionPay)")
    print(f"   Web Store users {installs:,} (rounded) -> {paid_customers} paid charge(s) all time{conv}" if installs
          else f"   {paid_customers} paid charge(s) all time (Web Store count unavailable)")
    print(f"   Last 30d: {len(win)} charge(s), {money(sum(r['gross'] for r in win))} gross, "
          f"{money(sum(_row_net(r) for r in win))} net, {money(sum(r['refunded'] for r in win))} refunded")
    subs = meta.get("subs")
    if subs:
        print(f"   Subscriptions: {subs['active']} active, {subs['trialing']} trialing, MRR {money(subs['mrr'])}")
    else:
        print("   Subscriptions: not read (the key may lack Subscriptions read access)")


def print_marketplaces(summary: dict | None) -> None:
    if not summary:
        return
    print(f"\n  Marketplace sales (last {summary['etsy']['days']}d, net after fees)")
    for s in summary.values():
        gap = f"  [{'; '.join(s['issues'])}]" if s["issues"] else ""
        print(f"   {s['label']:<10} {s['windowOrders']:>3} orders  {money(s['windowGross']):>8} gross  "
              f"{money(s['windowNet']):>8} net   all time {s['orders']} / {money(s['gross'])}{gap}")


def appstore_events(before: dict, after: dict) -> list[dict]:
    """GlobePin Pro sales, promo redemptions and refunds that appeared since
    the last run, found by diffing each day's counts."""
    events = []
    for day, v in sorted((after or {}).items()):
        old = (before or {}).get(day, {})
        for field, kind in (("proUnits", "globepin-pro"), ("proPromo", "globepin-promo"),
                            ("proRefunds", "globepin-refund")):
            n = v.get(field, 0) - old.get(field, 0)
            if n > 0:
                events.append({"kind": kind, "count": n, "day": day,
                               "proceeds": (v.get("proceeds") or {}).get("USD", 0.0)
                               - (old.get("proceeds") or {}).get("USD", 0.0)})
    return events


def subscription_events(before: dict | None, after: dict | None) -> list[dict]:
    if not before or not after:
        return []
    events = []
    for field in ("active", "trialing", "mrr"):
        a, b = before.get(field, 0), after.get(field, 0)
        if a != b:
            events.append({"kind": "subs", "field": field, "from": a, "to": b})
    return events


def _event_text(e: dict) -> str:
    label = PRODUCT_LABELS.get(e.get("product", ""), e.get("product", ""))
    if e["kind"] == "purchase":
        net = f" (net {money(e['net'])})" if e.get("net") is not None else ""
        via = f" on {e['via']}" if e.get("via") else ""
        return f"New order{via}: {label} {money(e['gross'])}{net}"
    if e["kind"] == "renewal":
        return f"Renewal: {label} {money(e['gross'])}"
    if e["kind"] == "refund":
        via = f" {e['via']}" if e.get("via") else ""
        return f"Refund: {money(e['gross'])} on a{via} {label} order"
    if e["kind"] == "globepin-pro":
        return f"GlobePin Pro sold ×{e['count']} ({e['day']}, ${e['proceeds']:,.2f} proceeds)"
    if e["kind"] == "globepin-promo":
        return f"GlobePin Pro promo code redeemed ×{e['count']} ({e['day']})"
    if e["kind"] == "globepin-refund":
        return f"GlobePin Pro refunded ×{e['count']} ({e['day']})"
    if e["kind"] == "subs":
        if e["field"] == "mrr":
            return f"MRR {money(e['from'])} → {money(e['to'])}"
        return f"{e['field'].capitalize()} subscriptions {e['from']} → {e['to']}"
    return str(e)


def revenue_metrics(history: dict, summaries: list[dict], manual_ads: dict) -> dict | None:
    sales = history.get("sales") or {}
    ledger = sorted((history.get("ledger") or {}).values(), key=lambda r: r["ts"])
    app_days = (history.get("appstore") or {}).get("days", {})
    if not ledger and not app_days:
        return None

    today = dt.date.today()
    now = dt.datetime.now().timestamp()
    win = METRICS_DAYS * 86400
    lo = (today - dt.timedelta(days=METRICS_DAYS)).isoformat()
    lo2 = (today - dt.timedelta(days=2 * METRICS_DAYS)).isoformat()
    cur = [r for r in ledger if r["ts"] >= now - win]
    prev = [r for r in ledger if now - 2 * win <= r["ts"] < now - win]

    def app_sum(field: str, a: str, b: str = "9999") -> float:
        if field == "proceeds":
            return sum((v.get("proceeds") or {}).get("USD", 0.0) for d, v in app_days.items() if a <= d < b)
        return sum(v.get(field, 0) for d, v in app_days.items() if a <= d < b)

    # --- overview: last 28 days vs the 28 before -------------------------------
    app_cur, app_prev = app_sum("proceeds", lo), app_sum("proceeds", lo2, lo)
    gross_cur = sum(r["gross"] for r in cur) / 100 + app_cur
    gross_prev = sum(r["gross"] for r in prev) / 100 + app_prev
    net_cur = sum(_row_net(r) for r in cur) / 100 + app_cur
    change = None if not gross_prev else (gross_cur - gross_prev) / gross_prev * 100

    # --- customers and lifetime value ----------------------------------------
    first_seen: dict[str, float] = {}
    orders_by: dict[str, int] = {}
    net_by: dict[str, int] = {}
    for r in ledger:
        c = r.get("cust") or r["id"]
        first_seen.setdefault(c, r["ts"])
        orders_by[c] = orders_by.get(c, 0) + 1
        net_by[c] = net_by.get(c, 0) + _row_net(r)
    buyers_cur = {r.get("cust") or r["id"] for r in cur}
    new_cur = sum(1 for c in buyers_cur if first_seen[c] >= now - win)
    customers = len(first_seen)
    repeat = sum(1 for n in orders_by.values() if n > 1)

    refunded = [r for r in ledger if (r.get("refunded") or 0) > 0]
    gross_all = sum(r["gross"] for r in ledger)

    # --- weekly revenue by product group, last 12 weeks ------------------------
    monday = today - dt.timedelta(days=today.weekday())
    weeks = [(monday - dt.timedelta(weeks=i)).isoformat() for i in range(11, -1, -1)]
    weekly = {w: {g: 0.0 for g, _c in PRODUCT_GROUPS} for w in weeks}
    for r in ledger:
        d = dt.date.fromtimestamp(r["ts"])
        wk = (d - dt.timedelta(days=d.weekday())).isoformat()
        if wk in weekly:
            weekly[wk][product_group(r)] += r["gross"] / 100
    for d, v in app_days.items():
        dd = dt.date.fromisoformat(d)
        wk = (dd - dt.timedelta(days=dd.weekday())).isoformat()
        if wk in weekly:
            weekly[wk]["GlobePin Pro"] += (v.get("proceeds") or {}).get("USD", 0.0)

    # --- conversion ------------------------------------------------------------
    site_hist = history.get("sites", {}).get("purplelink", {})
    clean, _adj = without_synthetic("purplelink", site_hist.get("byDay", {}))
    trial_since = site_hist.get("metricsFirstSeen", {}).get("trialDownloads") or "2026-09-11"
    since_ts = dt.datetime.fromisoformat(trial_since).timestamp()
    wk_ago = (today - dt.timedelta(days=7)).isoformat()

    def trials(a: str) -> int:
        return int(sum(v.get("trialDownloads", 0) or 0 for d, v in clean.items() if d >= a))

    mt_all = [r for r in ledger if r["product"] == "moderntex" and r["ts"] >= since_ts]
    # Same start as the trial counts: launch-week sales before the trial existed
    # would otherwise inflate trial→paid.
    mt_cur = [r for r in mt_all if r["ts"] >= now - win]
    lifecycle = (sales.get("lifecycle") or {}).get("moderntex_trial") or {}
    moderntex = {
        "since": trial_since,
        "trials": trials(trial_since), "orders": len(mt_all),
        "trials28": trials(max(lo, trial_since)), "orders28": len(mt_cur),
        "trialsInProgress": trials(wk_ago),
        "netPerTrial": (sum(_row_net(r) for r in mt_all) / 100 / trials(trial_since)) if trials(trial_since) else None,
        "linkedSignups": lifecycle.get("signups"), "linkedBought": lifecycle.get("bought"),
    }

    installs_all, installs_28 = app_sum("downloads", "0000"), app_sum("downloads", lo)
    pro_all, pro_28 = app_sum("proUnits", "0000"), app_sum("proUnits", lo)
    proceeds_all = app_sum("proceeds", "0000")
    globepin = {
        "installs": int(installs_all), "pro": int(pro_all), "installs28": int(installs_28), "pro28": int(pro_28),
        "promo": int(app_sum("proPromo", "0000")), "refunds": int(app_sum("proRefunds", "0000")),
        "revenuePerInstall": (proceeds_all / installs_all) if installs_all else None,
        "admob7": ((history.get("admob") or {}).get("globepin") or {}).get("earnings"),
    }

    pl_summary = next((s for s in summaries if s.get("key") == "purplelink"), {}) or {}
    ck = pl_summary.get("checkout") or {}
    month_ago = now - 30 * 86400
    web = {"views": ck.get("views"), "clicks": ck.get("clicks"),
           "orders": sum(1 for r in ledger if r.get("site") == "purplelink" and not r.get("market")
                         and r["ts"] >= month_ago)}

    # --- acquisition: what a customer costs vs. what one is worth ---------------
    acq = []
    asa = (manual_ads or {}).get("appleSearchAds") or {}
    if asa.get("campaigns"):
        c0 = asa["campaigns"][0]
        spend, inst = c0.get("spend", 0.0), c0.get("installs", 0)
        acq.append({"channel": "Apple Search Ads → GlobePin", "asOf": asa.get("asOf"),
                    "spend": spend, "unit": "install", "units": inst,
                    "cost": (spend / inst) if inst else None,
                    "worth": globepin["revenuePerInstall"]})

    # Event feed: everything detected in the last 24 hours. A rolling window, not
    # "since the previous run", because the 7am launchd run would otherwise use
    # up the news before the daily update is read.
    cutoff_at = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)).isoformat()
    log = history.get("eventLog") or []
    started = history.get("ledgerSince")
    events = {"items": [e for e in log if e.get("at", "") >= cutoff_at],
              "firstRun": bool(started) and started >= (today - dt.timedelta(days=1)).isoformat()}

    subs = sales.get("subscriptions") or {}
    return {
        "days": METRICS_DAYS,
        "grossCur": gross_cur, "grossPrev": gross_prev, "netCur": net_cur, "change": change,
        "appCur": app_cur, "ordersCur": len(cur),
        "unknownFees": sum(1 for r in cur if r.get("net") is None),
        "newCur": new_cur, "returningCur": len(buyers_cur) - new_cur,
        "customers": customers, "repeat": repeat,
        "ltv": (sum(net_by.values()) / customers / 100) if customers else None,
        "refundOrders": len(refunded), "refundAmount": sum(r["refunded"] for r in refunded),
        "refundRate": (sum(r["refunded"] for r in refunded) / gross_all * 100) if gross_all else None,
        "mrr": subs.get("mrr", 0), "subsActive": subs.get("active", 0), "subsTrialing": subs.get("trialing", 0),
        "subsWindow": subs.get("window") or {},
        "weeks": weeks, "weekly": weekly,
        "moderntex": moderntex, "globepin": globepin, "web": web, "acquisition": acq,
        "events": events,
    }


def _pct(n: float | None, d: float | None) -> str:
    return f"{n / d * 100:.0f}%" if d else "—"


def weekly_chart(weeks: list[str], weekly: dict[str, dict[str, float]]) -> str:
    first = next((i for i, w in enumerate(weeks) if sum(weekly[w].values()) > 0), 0)
    weeks = weeks[first:]
    totals = [sum(weekly[w].values()) for w in weeks]
    peak = max(totals + [1.0])
    n = len(weeks)
    w_, h, pad_top, pad_bottom = max(n, 4) * 64, 170, 22, 22
    bar_w, gap = (w_ / n) * 0.62, (w_ / n) * 0.38
    parts = []
    for i, wk in enumerate(weeks):
        x = i * (bar_w + gap) + gap / 2
        y = h - pad_bottom
        for group, color in PRODUCT_GROUPS:
            v = weekly[wk].get(group, 0.0)
            if v <= 0:
                continue
            seg = v / peak * (h - pad_top - pad_bottom)
            y -= seg
            parts.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{seg:.1f}' "
                         f"fill='{color}' rx='2'><title>{html.escape(group)}: ${v:,.2f}</title></rect>")
        if totals[i] > 0:
            parts.append(f"<text x='{x + bar_w / 2:.1f}' y='{y - 5:.1f}' font-size='12' "
                         f"fill='var(--ink)' text-anchor='middle'>${totals[i]:,.0f}</text>")
        if i % 2 == 0 or i == n - 1:
            label = dt.date.fromisoformat(wk).strftime("%b %-d")
            parts.append(f"<text x='{x + bar_w / 2:.1f}' y='{h - 5}' font-size='12' "
                         f"fill='var(--muted)' text-anchor='middle'>{label}</text>")
    legend = "".join(
        f"<span class='rev-legend-item'><i style='background:{c}'></i>{html.escape(g)}</span>"
        for g, c in PRODUCT_GROUPS if any(weekly[w].get(g, 0) > 0 for w in weeks))
    return (f"<svg viewBox='0 0 {w_} {h}' class='weekly-chart' role='img' style='max-width:{int(w_ * 1.4)}px' "
            f"aria-label='Revenue per week, stacked by product'>{''.join(parts)}</svg>"
            f"<div class='rev-legend'>{legend}</div>")


def metrics_block(m: dict | None) -> str:
    if not m:
        return ""
    ch = ("" if m["change"] is None else
          f"<em class='{'up' if m['change'] >= 0 else 'down'}'>{m['change']:+.0f}% vs prior {m['days']}d</em>")
    fee_note = (f" · {m['unknownFees']} order(s) without a Stripe fee on record, counted at gross"
                if m["unknownFees"] else "")
    sw = m["subsWindow"]
    tiles = [
        (f"${m['netCur']:,.2f}", f"net, last {m['days']}d (gross ${m['grossCur']:,.2f})", ch),
        (str(m["newCur"]), f"new customers ({m['returningCur']} returning)", ""),
    ]
    if m["mrr"] or m["subsActive"]:
        tiles.append((money(m["mrr"]), f"MRR, {m['subsActive']} active, {m['subsTrialing']} trialing", ""))
    tiles += [
        (str(m["moderntex"]["trialsInProgress"] + m["subsTrialing"]),
         "ModernTex trials, last 7d", ""),
        (str(m["refundOrders"]), f"refunds, {money(m['refundAmount'])} all time", ""),
    ]
    tiles_html = "".join(f"<div class='tile'><b>{v}</b><span>{html.escape(lbl)}</span>{extra}</div>"
                         for v, lbl, extra in tiles)

    mt, gp, web = m["moderntex"], m["globepin"], m["web"]
    linked = ""
    if mt["linkedSignups"] is not None:
        linked = (f"<br><span class='who'>Email-linked: {mt['linkedSignups']} trial sign-up(s) → "
                  f"{mt['linkedBought']} bought ({_pct(mt['linkedBought'], mt['linkedSignups'])})</span>")
    npt = f"${mt['netPerTrial']:,.2f}" if mt["netPerTrial"] is not None else "—"
    rpi = f"${gp['revenuePerInstall']:,.2f}" if gp["revenuePerInstall"] is not None else "—"
    admob = f"; AdMob ${gp['admob7']:,.2f} in 7d" if gp.get("admob7") is not None else ""
    web_line = ("—" if web["views"] is None else
                f"{web['views']} product-page views → {web['clicks']} buy clicks ({_pct(web['clicks'], web['views'])}) "
                f"→ {web['orders']} orders ({_pct(web['orders'], web['clicks'])} of clicks)")
    conv_rows = f"""
      <tr><td>ModernTex · trial → paid</td>
        <td>{mt['trials']} trials → {mt['orders']} paid since {mt['since']} ({_pct(mt['orders'], mt['trials'])}){linked}</td>
        <td class='num'>{mt['trials28']} → {mt['orders28']}</td><td class='num'>{npt} / trial</td></tr>
      <tr><td>GlobePin · install → Pro</td>
        <td>{gp['installs']} installs → {gp['pro']} paid Pro ({_pct(gp['pro'], gp['installs'])}),
          {gp['promo']} promo, {gp['refunds']} refunded{admob}</td>
        <td class='num'>{gp['installs28']} → {gp['pro28']}</td><td class='num'>{rpi} / install</td></tr>
      <tr><td>purplelink.llc · page → order</td><td colspan='3'>{web_line} (30d)</td></tr>"""

    acq_rows = "".join(
        f"<tr><td>{html.escape(a['channel'])}</td><td class='num'>${a['spend']:,.2f}</td>"
        f"<td class='num'>{a['units']} {a['unit']}{'' if a['units'] == 1 else 's'}</td>"
        f"<td class='num'>{'—' if a['cost'] is None else '$' + format(a['cost'], ',.2f')}</td>"
        f"<td class='num'>{'—' if a['worth'] is None else '$' + format(a['worth'], ',.2f')}</td>"
        f"<td class='num'>{'—' if not a['cost'] or a['worth'] is None else format(a['worth'] / a['cost'], '.2f') + '×'}</td></tr>"
        for a in m["acquisition"])
    acq_html = (f"""
  <h3>Acquisition · last 7 days</h3>
  <table><thead><tr><th>Channel</th><th class='num'>Spend</th><th class='num'>Got</th>
    <th class='num'>Cost each</th><th class='num'>Worth each</th><th class='num'>Payback</th></tr></thead>
    <tbody>{acq_rows}</tbody></table>""" if acq_rows else "")

    ev = m["events"]
    items = ev.get("items") or []
    if items:
        ev_html = ("<h3>Last 24 hours</h3><ul class='events'>"
                   + "".join(f"<li>{html.escape(_event_text(e))}</li>" for e in items) + "</ul>")
    elif ev.get("firstRun"):
        ev_html = ("<p class='sales-foot'>Event feed: today's ledger is the baseline, so new orders, "
                   "refunds and subscription changes show here from the next run.</p>")
    else:
        ev_html = "<p class='sales-foot'>Last 24 hours: no new orders, refunds or subscription changes.</p>"

    ltv = f"${m['ltv']:,.2f}" if m["ltv"] is not None else "—"
    return f"""
<section class="sales metrics">
  <h2>Card sales and GlobePin Pro &middot; last {m['days']} days</h2>
  <div class="metric-tiles">{tiles_html}</div>
  <h3>Revenue per week</h3>
  {weekly_chart(m['weeks'], m['weekly'])}
  <h3>Conversion</h3>
  <table><thead><tr><th>Funnel</th><th>All time</th><th class='num'>Last {m['days']}d</th>
    <th class='num'>Worth</th></tr></thead><tbody>{conv_rows}</tbody></table>
  {acq_html}
  <h3>Customers</h3>
  <p class="cust-line">{m['customers']} paying customers all time · {m['repeat']} bought more than once
    ({_pct(m['repeat'], m['customers'])}) · average {ltv} net each · refund rate
    {'—' if m['refundRate'] is None else format(m['refundRate'], '.1f') + '%'}</p>
  {ev_html}
  <p class="sales-foot">Stripe sales plus GlobePin Pro proceeds (already net of Apple's cut); net is after
    Stripe's fee and refunds{fee_note}. Trial→paid compares downloads with orders over the same days, not
    the same people. "Payback" is worth ÷ cost; 1.00× is break-even.</p>
</section>"""


def app_funnel_report(history: dict, *, page: str, metric: str, since: str, checkout_keys: tuple,
                      ledger_match) -> dict | None:
    """One app's funnel in one place: page views, downloads, buy clicks, orders.

    Page views and buy clicks come from the beacon's 30-day window (topPaths, checkoutByProduct);
    downloads are per day under `metric` (counted since `since`); orders come from the Stripe
    ledger rows `ledger_match` accepts. Search Console figures are the page's own row when it is
    in the top pages list. Downloads and orders are not linked to each other, so the rate is
    orders over downloads across the same days, never a per-person conversion.
    """
    site = (history.get("sites") or {}).get("purplelink") or {}
    latest = site.get("latest") or {}
    if not latest:
        return None
    by_day = site.get("byDay") or {}
    today = dt.date.today()
    day_keys = sorted(by_day)

    def dl(d: str) -> int:
        return int((by_day.get(d) or {}).get(metric, 0) or 0)

    last7 = [(today - dt.timedelta(days=i)).isoformat() for i in range(1, 8)]
    views = {r["key"]: r.get("count", 0) for r in latest.get("topPaths", []) if str(r.get("key", "")).startswith(page)}
    clicks = sum(r.get("count", 0) for r in latest.get("checkoutByProduct", []) if r.get("key") in checkout_keys)
    now = dt.datetime.now().timestamp()
    rows = [r for r in (history.get("ledger") or {}).values() if ledger_match(r) and r.get("kind") != "refund"]
    rows30 = [r for r in rows if r.get("ts", 0) >= now - 30 * 86400]
    since_days = [d for d in day_keys if d >= since]
    orders_since = [r for r in rows if r.get("ts", 0) >= dt.datetime.fromisoformat(since).timestamp()]
    gsc = next((r for r in (site.get("gsc") or {}).get("pages", [])
                if f"purplelink.llc{page}" in str(r.get("key", "")) and "start" not in r["key"] and "success" not in r["key"]), None)
    return {
        "views": views, "viewsTotal": sum(views.values()),
        "dl7": sum(dl(d) for d in last7), "dlToday": dl(today.isoformat()),
        "dlAll": sum(dl(d) for d in day_keys if d >= since), "dlSince": since,
        "dlDays": len(since_days),
        "clicks": clicks,
        "orders30": len(rows30), "gross30": sum(r.get("gross", 0) for r in rows30) / 100, "net30": sum(r.get("net", 0) for r in rows30) / 100,
        "ordersAll": len(rows), "grossAll": sum(r.get("gross", 0) for r in rows) / 100,
        "ordersSince": len(orders_since),
        "gsc": gsc,
    }


def outbound_veil_report(history: dict) -> dict | None:
    """Outbound Veil: counted since 2026-10-04. In-app update downloads have no counter yet."""
    return app_funnel_report(history, page="/outbound-veil", metric="ovTrialDownloads", since="2026-10-04",
                             checkout_keys=("outbound-veil",),
                             ledger_match=lambda r: r.get("product") == "outbound-veil" and r.get("kind") == "purchase")


def legroom_report(history: dict) -> dict | None:
    """Legroom ($9.99, 7-day trial), live 2026-10-05. Its own orders only: Mac Suite orders include
    Legroom but are counted on the Suite line, so they are reported apart as `suiteOrders`."""
    r = app_funnel_report(history, page="/legroom", metric="lgTrialDownloads", since="2026-10-05",
                          checkout_keys=("legroom", "freeboard"),
                          ledger_match=lambda x: x.get("product") in ("legroom", "freeboard") and x.get("kind") == "purchase")
    if r is not None:
        r["suiteOrders"] = sum(1 for x in (history.get("ledger") or {}).values()
                               if x.get("product") == "app-suite" and x.get("kind") == "purchase")
    return r


def _suite_orders(history: dict) -> int:
    return sum(1 for x in (history.get("ledger") or {}).values() if x.get("product") == "app-suite" and x.get("kind") == "purchase")


def panely_report(history: dict) -> dict | None:
    """Panely ($9.99, 7-day trial), live 2026-10-12. Its own orders only: Mac Suite orders include it and are
    reported apart as `suiteOrders`. `server` holds the download counters kept by the download function."""
    r = app_funnel_report(history, page="/panely", metric="pnTrialDownloads", since="2026-10-12",
                          checkout_keys=("panely",),
                          ledger_match=lambda x: x.get("product") == "panely" and x.get("kind") == "purchase")
    if r is not None:
        r["suiteOrders"] = _suite_orders(history)
        r["server"] = app_stats_summary((history.get("appStats") or {}).get("panely"))
    return r


def summonly_report(history: dict) -> dict | None:
    """Summonly ($9.99, 7-day trial), live 2026-10-12. Same shape as panely_report."""
    r = app_funnel_report(history, page="/summonly", metric="smTrialDownloads", since="2026-10-12",
                          checkout_keys=("summonly",),
                          ledger_match=lambda x: x.get("product") == "summonly" and x.get("kind") == "purchase")
    if r is not None:
        r["suiteOrders"] = _suite_orders(history)
        r["server"] = app_stats_summary((history.get("appStats") or {}).get("summonly"))
    return r


def vitae_report(history: dict) -> dict | None:
    """Vitae is free: the first step is a download, the conversion is a Vitae Plus subscription
    ($2.99 a month or $23.99 a year, 7-day trial). Downloads are counted since 2026-09-22."""
    return app_funnel_report(history, page="/vitae", metric="vitaeDownloads", since="2026-09-22",
                             checkout_keys=("vitae-plus-monthly", "vitae-plus-annual"),
                             ledger_match=lambda r: str(r.get("product", "")).startswith("vitae-plus"))


def _dl_rate(o: dict, what: str) -> str:
    n = o["dlAll"]
    if not n:
        return "no downloads yet"
    return f"{o['ordersSince']} {what} against {n} download(s) since {o['dlSince']} ({_pct(o['ordersSince'], n)})"


def print_app_funnel(o: dict | None, title: str, page: str, *, start_note: str = "", free_step: bool = False,
                     conv_word: str = "order") -> None:
    if not o:
        return
    v = o["views"]
    print(f"\n  {title}")
    extra = f", {v.get(page + 'start/', 0)} start page (after download), {v.get(page + 'success/', 0)} success page" if start_note else ""
    print(f"   Page views, 30d: {v.get(page, 0)} product page{extra}")
    print(f"   {'Downloads' if free_step else 'Trial downloads'}: {o['dl7']} in the last 7 complete days, {o['dlToday']} today, "
          f"{o['dlAll']} total (counted since {o['dlSince']}, {o['dlDays']} day(s))")
    print(f"   Buy clicks, 30d: {o['clicks']}; {conv_word}s, 30d: {o['orders30']} (${o['gross30']:,.2f} gross, ${o['net30']:,.2f} net); "
          f"all time {o['ordersAll']} (${o['grossAll']:,.2f} gross)")
    print(f"   Download to {conv_word}: {_dl_rate(o, conv_word + '(s)')}"
          + ("; too few to read as a rate" if o["ordersSince"] < 5 else ""))
    if o.get("suiteOrders"):
        print(f"   Mac Suite orders, all time: {o['suiteOrders']} (they include this app; counted on the Suite line)")
    g = o["gsc"]
    if g:
        print(f"   Search: {g.get('count', 0)} click(s), {g.get('impressions', 0)} impression(s), position {g.get('position', 0):.1f} on the product page")
    else:
        print("   Search: the product page is not in Search Console's top pages yet")


def print_outbound_veil(o: dict | None) -> None:
    print_app_funnel(o, "Outbound Veil (Mac app, $29.99, 7-day trial)", "/outbound-veil/", start_note="start")
    if o:
        print("   Not measured: in-app update downloads (no counter for this app yet), trial-to-paid by email")


def print_legroom(o: dict | None) -> None:
    print_app_funnel(o, "Legroom (Mac app, $9.99, 7-day trial)", "/legroom/")
    if o:
        print("   Not measured: in-app update downloads and trial-to-paid by email (the trial has no sign-up step)")


def print_app_server_counts(o: dict | None) -> None:
    sv = (o or {}).get("server")
    if not sv:
        print("   Downloads served (server count): not available this run")
        return
    print(f"   Downloads served by the site (all browsers, not only those the beacon sees): {sv['publicAll']} public (trial), "
          f"{sv['buyerAll']} to buyers; last 7 complete days {sv['public7']} public, {sv['buyer7']} buyer; today {sv['publicToday']} + {sv['buyerToday']}")
    if sv["updates"]:
        print("   In-app updates installed, by version: " + ", ".join(f"{k.replace('.dmg', '')} x{n}" for k, n in sv["updates"].items()))
    else:
        print("   In-app updates installed: none yet (counted when the app's updater asks for a version)")


def print_panely(o: dict | None) -> None:
    print_app_funnel(o, "Panely (Mac app, $9.99, 7-day trial)", "/panely/")
    print_app_server_counts(o)
    if o:
        print("   Not measured: trials started (the app sends nothing), trial-to-paid by email")


def print_summonly(o: dict | None) -> None:
    print_app_funnel(o, "Summonly (Mac app, $9.99, 7-day trial)", "/summonly/")
    print_app_server_counts(o)
    if o:
        print("   Not measured: trials started (the app sends nothing), trial-to-paid by email")


def print_vitae(o: dict | None) -> None:
    print_app_funnel(o, "Vitae (Mac app, free; Vitae Plus $2.99/month or $23.99/year, 7-day trial)", "/vitae/",
                     free_step=True, conv_word="Plus subscription")
    if o:
        print("   Not measured: Plus trials that have not converted yet, and in-app update downloads")


def print_metrics(m: dict | None) -> None:
    if not m:
        return
    ch = "" if m["change"] is None else f", {m['change']:+.0f}% vs prior {m['days']}d"
    print(f"\n  Revenue metrics — ${m['grossCur']:,.2f} gross / ${m['netCur']:,.2f} net in {m['days']}d{ch}; "
          f"{m['newCur']} new, {m['returningCur']} returning customer(s); MRR {money(m['mrr'])} "
          f"({m['subsActive']} active, {m['subsTrialing']} trialing); refunds {m['refundOrders']} all time")
    mt, gp = m["moderntex"], m["globepin"]
    print(f"   ModernTex: {mt['trials']} trials → {mt['orders']} paid since {mt['since']} "
          f"({_pct(mt['orders'], mt['trials'])}); {mt['trialsInProgress']} trial(s) in progress"
          + (f"; email-linked {mt['linkedSignups']} → {mt['linkedBought']} bought" if mt["linkedSignups"] is not None else ""))
    print(f"   GlobePin: {gp['installs']} installs → {gp['pro']} paid Pro ({_pct(gp['pro'], gp['installs'])}), "
          f"{gp['promo']} promo, {gp['refunds']} refunded")
    for a in m["acquisition"]:
        cost = "—" if a["cost"] is None else f"${a['cost']:,.2f}"
        worth = "—" if a["worth"] is None else f"${a['worth']:,.2f}"
        print(f"   {a['channel']}: ${a['spend']:,.2f} for {a['units']} {a['unit']}(s), {cost} each vs {worth} worth each")
    ltv = "—" if m["ltv"] is None else f"${m['ltv']:,.2f}"
    print(f"   Customers: {m['customers']} all time, {m['repeat']} repeat, {ltv} average net each")
    ev = m["events"]
    items = ev.get("items") or []
    if items:
        print("   Last 24h: " + "; ".join(_event_text(e) for e in items))
    elif ev.get("firstRun"):
        print("   Last 24h: feed starts next run (today's ledger is the baseline)")
    else:
        print("   Last 24h: no new orders, refunds or subscription changes")


# ---------------------------------------------------------------- profit view
#
# Revenue minus what it cost to earn, per product line, over the last 7 days
# (the window every ad reading covers). Net revenue is already after Stripe's
# fee, refunds and Apple's cut; from it come ad spend, Claude API cost per paid
# job, Modal compute, and fixed costs from COSTS_PATH, spread evenly per day
# (usdPerMonth, usdPerYear), or counted once in the window holding its date (usdOnce + date).
# Only measured or entered costs appear; what is not measured is listed.

PROFIT_DAYS = 7
COSTS_PATH = Path.home() / ".config" / "purplelink" / "costs.json"
PROFIT_LINES = ["ModernTex", "Outbound Veil", "Scholar Utility Belt Pro", "Legroom", "Keyfeel", "Tapefolio", "Panely", "Summonly", "Mac Suite", "Paper Review & tools", "Kits", "Spreadsheets", "Photo prints (Etsy)", "Subscriptions", "MuscleOnGLP",
                "GlobePin", "Company"]


def load_costs() -> list[dict]:
    try:
        return json.loads(COSTS_PATH.read_text()).get("items") or []
    except Exception:
        return []


def profit_view(history: dict, manual_ads: dict, days: int = PROFIT_DAYS) -> dict | None:
    ledger = list((history.get("ledger") or {}).values())
    app_days = (history.get("appstore") or {}).get("days", {})
    if not ledger and not app_days:
        return None
    today = dt.date.today()
    now = dt.datetime.now().timestamp()
    lo_ts, lo = now - days * 86400, (today - dt.timedelta(days=days)).isoformat()
    lines = {k: {"revenue": 0.0, "ads": 0.0, "api": 0.0, "hosting": 0.0, "fixed": 0.0, "orders": 0}
             for k in PROFIT_LINES}
    gaps: list[str] = []

    for r in ledger:
        if r["ts"] >= lo_ts:
            g = product_group(r)
            g = "GlobePin" if g == "GlobePin Pro" else g
            lines[g]["revenue"] += _row_net(r) / 100
            lines[g]["orders"] += 1
    gp = lines["GlobePin"]
    gp["revenue"] += sum((v.get("proceeds") or {}).get("USD", 0.0) for d, v in app_days.items() if d >= lo)
    gp["orders"] += int(sum(v.get("proUnits", 0) for d, v in app_days.items() if d >= lo))
    admob = (history.get("admob") or {}).get("globepin") or {}
    if admob.get("earnings") is not None and not admob.get("error"):
        gp["revenue"] += admob["earnings"] * days / (admob.get("days") or days)
    else:
        gaps.append("AdMob earnings (no reading)")

    stale_before = (today - dt.timedelta(days=2)).isoformat()
    # A reading taken before this window began describes spend outside it (Apple Search Ads stopped 2026-10-06, and
    # its last reading kept charging GlobePin $40 a week). Such a reading is left out and named as a gap instead.
    window_start = (today - dt.timedelta(days=days)).isoformat()
    asa = (manual_ads or {}).get("appleSearchAds") or {}
    if asa.get("campaigns"):
        if (asa.get("asOf") or "") < window_start:
            gaps.append(f"Apple Search Ads (last reading {asa.get('asOf')}, before this window; not counted)")
        else:
            gp["ads"] += sum(c.get("spend", 0.0) for c in asa["campaigns"]) * days / 7
            if (asa.get("asOf") or "") < stale_before:
                gaps.append(f"Apple Search Ads reading is from {asa.get('asOf')}")
    for m, ms in marketplace_summary(history).items():
        for issue in ms["issues"]:
            gaps.append(f"{ms['label']} sales ({issue})")
    if any(r.get("feeEstimated") and r["ts"] >= lo_ts for r in ledger):
        gaps.append("marketplace fees estimated from the published schedule where the page showed none")
    if not any(it.get("usdOnce") for it in load_costs()):
        gaps.append(f"shop-level Etsy costs (listing fees for the 7 new sheets, ${ETSY_SHEET_LISTING_FEES:.2f} one time)")

    usage = history.get("apiUsage")
    if usage is None:
        gaps.append("Claude API cost per paid job (usage ledger unreachable)")
    jobs = 0
    for u in usage or []:
        if u["ts"] >= lo_ts:
            g = product_group({"product": u.get("product_key", ""), "site": "purplelink"})
            lines[g]["api"] += u.get("cost_usd") or 0.0
            jobs += 1

    mc = history.get("modalCosts") or {}
    if not mc.get("byAppDay"):
        gaps.append("Modal compute (billing report unreachable)")
    for app, by_day in (mc.get("byAppDay") or {}).items():
        lines[MODAL_APP_LINES.get(app, "Company")]["hosting"] += sum(v for d, v in by_day.items() if d >= lo)

    items = load_costs()
    for it in items:
        if it.get("pending"):  # known cost, amount not yet entered: listed, never counted
            gaps.append(f"{it.get('name', 'a fixed cost')} (amount not entered)")
            continue
        per_day = (it.get("usdPerMonth", 0) * 12 + it.get("usdPerYear", 0)) / 365
        line = it.get("line") if it.get("line") in lines else "Company"
        lines[line]["fixed"] += per_day * days
        # One-time cost: counted in full in the window that contains its date.
        if it.get("usdOnce") and lo < (it.get("date") or "") <= today.isoformat():
            lines[line]["fixed"] += it["usdOnce"]
    gaps.append("Claude API calls outside paid jobs (the daily digest's curation)" +
                (", entered as an estimate" if any("digest" in (it.get("name") or "").lower() for it in items) else ""))
    if not [it for it in items if not it.get("pending")]:
        gaps.append(f"fixed costs (none entered in {COSTS_PATH})")

    rows = []
    for k in PROFIT_LINES:
        v = lines[k]
        cost = v["ads"] + v["api"] + v["hosting"] + v["fixed"]
        if abs(v["revenue"]) < 0.005 and cost < 0.005:
            continue
        rows.append({"line": k, **v, "cost": cost, "profit": v["revenue"] - cost,
                     "margin": ((v["revenue"] - cost) / v["revenue"] * 100) if v["revenue"] else None})
    tot = {f: sum(r[f] for r in rows) for f in ("revenue", "ads", "api", "hosting", "fixed", "cost", "profit")}
    return {"days": days, "rows": rows, "total": tot, "jobs": jobs, "gaps": gaps,
            "fixedItems": [it.get("name", "?") for it in items if not it.get("pending")]}


def classify_touch(t: dict | None) -> str:
    """One arrival (from analytics.js via Stripe metadata) -> a channel name."""
    if not t:
        return "Direct / no record"
    s, m, r = (t.get("s") or "").lower(), (t.get("m") or "").lower(), (t.get("r") or "").lower()
    if s in MARKETPLACE_LABELS:
        return MARKETPLACE_LABELS[s]
    if t.get("g") or (s in ("google", "adwords") and m in ("cpc", "ppc", "paid")):
        return "Google Ads"
    if s.startswith("from:") or s.startswith("ref:") or s in ("vitae", "moderntex"):
        return "Own apps & links"
    if re.fullmatch(r"tool-[a-z0-9][a-z0-9-]{0,39}", s):
        # The offer card on a free tool page (utm_source=tool-<slug>); the slug is in the funnel table as tool:<slug>.
        return "Tool offers"
    if s in ("email", "newsletter", "rss"):
        return "Email & RSS"
    probe = r or s
    if any(a in probe for a in AI_REFERRERS) or "chatgpt" in s:
        return "AI assistants"
    if "reddit" in probe:
        return "Reddit"
    if any(x in probe for x in SOCIAL_REFERRERS):
        return "Social"
    if any(x in probe for x in SEARCH_REFERRERS):
        return "Search"
    return "Other sites" if r else f"Campaign: {s}"


def channel_revenue(history: dict) -> dict | None:
    ledger = sorted((history.get("ledger") or {}).values(), key=lambda r: r["ts"])
    tagged = [r for r in ledger if r.get("attr")]
    if not ledger:
        return None
    # Site tracking starts with the first Stripe order that carries a record;
    # marketplace orders always know their channel, so they are always in.
    own = [r for r in tagged if not r.get("market")] or tagged
    since = dt.date.fromtimestamp(own[0]["ts"]).isoformat() if own else None
    window = [r for r in ledger if tagged and (r.get("market") or r["ts"] >= own[0]["ts"])]
    table: dict[str, dict] = {}
    for r in window:
        a = r.get("attr") or {}
        for which in ("first", "last"):
            ch = classify_touch(a.get(which) or (a.get("first") if which == "last" else None))
            row = table.setdefault(ch, {"first": 0, "firstNet": 0.0, "last": 0, "lastNet": 0.0})
            row[which] += 1
            row[which + "Net"] += _row_net(r) / 100
    rows = sorted(({"channel": k, **v} for k, v in table.items()), key=lambda x: (-x["lastNet"], -x["firstNet"]))
    return {"since": since, "orders": len(window), "tagged": len(tagged),
            "untaggedBefore": len(ledger) - len(window), "rows": rows}


def _usd(v: float) -> str:
    v = round(v, 2) + 0.0  # no "-$0.00" for a fraction of a cent
    return f"-${-v:,.2f}" if v < 0 else f"${v:,.2f}"


# ---------------------------------------------------------------- tax estimate
#
# Purplelink LLC is a Georgia single-member LLC taxed as a disregarded entity
# (docs/photo-licensing/legal-ops.md), so business profit lands on Ben's
# Schedule C: self-employment tax on 92.35% of it, then federal income tax
# (after half the SE tax and the 20% QBI deduction) and Georgia's flat tax at
# the margin on top of his other income. A loss pays no SE tax and offsets
# other income instead, which is a saving at the same marginal rates. The
# marginal federal rate and filing status live in TAX_PROFILE_PATH because
# they depend on income outside the business. An estimate, not a return.

TAX_PROFILE_PATH = Path.home() / ".config" / "purplelink" / "tax-profile.json"
TAX_DEFAULTS = {
    "taxYear": 2026,
    "filingStatus": "single",
    "federalMarginal": 0.22,       # bracket the last dollar of other income falls in
    "stateRate": 0.0499,           # Georgia flat rate for 2026 (HB 463, signed 2026-05-11)
    "wagesAboveSSBase": False,     # W-2 wages over $184,500 (2026) remove the 12.4% SS part of SE tax
}
ESTIMATED_TAX_DUE = {2026: ["2026-04-15", "2026-06-15", "2026-09-15", "2027-01-15"]}
# 2026 federal brackets (IRS Rev. Proc. 2025-32, after the One Big Beautiful Bill):
# (lower bound of taxable income, rate), plus the Additional Medicare threshold.
FEDERAL_BRACKETS = {2026: {"single": [(0, .10), (12_400, .12), (50_400, .22), (105_700, .24),
                                      (201_775, .32), (256_225, .35), (640_600, .37)]}}
STANDARD_DEDUCTION = {2026: {"single": 16_100}}
SS_WAGE_BASE = {2026: 184_500}
ADDL_MEDICARE_AT = {"single": 200_000}
# QBI: above this taxable income the 20% deduction phases out over the range for a
# business that pays no W-2 wages and owns little property (Purplelink: none).
QBI_THRESHOLD = {2026: {"single": 201_750}}  # Rev. Proc. 2025-32: single/HoH 201,750 (201,775 is the MFS figure)
QBI_PHASE_IN = {"single": 75_000}
SALES_TAX_GROSS = 100_000          # lowest common economic-nexus threshold, per state
SALES_TAX_ORDERS = 200             # the transaction-count alternative some states still use
SE_MIN_PROFIT = 400                # no SE tax below $400 of net SE earnings


def load_tax_profile() -> tuple[dict, bool]:
    try:
        return {**TAX_DEFAULTS, **json.loads(TAX_PROFILE_PATH.read_text())}, True
    except Exception:
        return dict(TAX_DEFAULTS), False


def _bracket_tax(taxable: float, brackets: list[tuple[float, float]]) -> float:
    tax = 0.0
    for i, (lower, rate) in enumerate(brackets):
        upper = brackets[i + 1][0] if i + 1 < len(brackets) else float("inf")
        if taxable > lower:
            tax += (min(taxable, upper) - lower) * rate
    return tax


def schedule_c_tax(profit: float, prof: dict) -> dict:
    """Extra tax (negative: saving) from `profit` of annual Schedule C profit.

    With w2Wages in the profile this is exact against the bracket table: the
    federal change is tax(other + change) - tax(other), so a loss that crosses
    a bracket line is priced at both rates. SE tax counts the Social Security
    room left under the wage base and the 0.9% Additional Medicare over $200k.
    Without it, one flat federalMarginal rate stands in."""
    brackets = FEDERAL_BRACKETS.get(prof["taxYear"], {}).get(prof["filingStatus"])
    wages = prof.get("w2Wages")
    if wages is not None and brackets:
        base = max(0.0, wages - STANDARD_DEDUCTION[prof["taxYear"]][prof["filingStatus"]])
        se_base = profit * 0.9235 if profit * 0.9235 >= SE_MIN_PROFIT else 0.0
        ss = 0.124 * min(se_base, max(0.0, SS_WAGE_BASE[prof["taxYear"]] - wages))
        medicare = 0.029 * se_base
        addl = 0.009 * max(0.0, se_base - max(0.0, ADDL_MEDICARE_AT[prof["filingStatus"]] - wages))
        half_se = (ss + medicare) / 2          # Additional Medicare is not deductible
        qbi = 0.2 * (profit - half_se) if profit > 0 else 0.0
        over = base + profit - half_se - QBI_THRESHOLD[prof["taxYear"]][prof["filingStatus"]]
        qbi *= 1 - min(1.0, max(0.0, over / QBI_PHASE_IN[prof["filingStatus"]]))
        change = profit - half_se - qbi
        federal = _bracket_tax(max(0.0, base + change), brackets) - _bracket_tax(base, brackets)
        state = prof["stateRate"] * (profit - half_se)
        se = ss + medicare + addl
        return {"se": se, "federal": federal, "state": state, "total": se + federal + state}

    fed, st = prof["federalMarginal"], prof["stateRate"]
    if profit <= 0:
        return {"se": 0.0, "federal": profit * fed, "state": profit * st, "total": profit * (fed + st)}
    se_rate = 0.029 if prof.get("wagesAboveSSBase") else 0.153
    se = profit * 0.9235 * se_rate if profit * 0.9235 >= SE_MIN_PROFIT else 0.0
    agi = profit - se / 2
    federal = agi * 0.8 * fed          # QBI: 20% of profit after half SE, well under the phase-in
    state = agi * st                   # Georgia starts from federal AGI; no QBI
    return {"se": se, "federal": federal, "state": state, "total": se + federal + state}


def tax_view(p: dict | None, history: dict) -> dict | None:
    if not p:
        return None
    prof, from_file = load_tax_profile()
    days = p["days"]
    week_profit = p["total"]["profit"]
    annual_profit = week_profit * 365 / days
    annual = schedule_c_tax(annual_profit, prof)
    week_tax = annual["total"] * days / 365
    at_1k = schedule_c_tax(1000, prof)["total"] / 1000
    loss_rate = -schedule_c_tax(-1000, prof)["total"] / 1000

    today = dt.date.today().isoformat()
    dues = ESTIMATED_TAX_DUE.get(prof["taxYear"], [])
    next_due = next((d for d in dues if d >= today), None)

    year_ago = dt.datetime.now().timestamp() - 365 * 86400
    recent = [r for r in (history.get("ledger") or {}).values() if r["ts"] >= year_ago]
    gross_12m = sum(r["gross"] for r in recent) / 100
    return {
        "profile": prof, "profileFile": from_file,
        "rateProfit": at_1k, "rateLoss": loss_rate,
        "weekProfit": week_profit, "weekTax": week_tax, "weekAfterTax": week_profit - week_tax,
        "annualProfit": annual_profit, "annual": annual,
        "nextDue": next_due, "estimatesNeeded": annual["total"] >= 1000,
        "gross12m": gross_12m, "orders12m": len(recent),
        "nexusPct": max(gross_12m / SALES_TAX_GROSS, len(recent) / SALES_TAX_ORDERS) * 100,
    }


def tax_block(t: dict | None) -> str:
    if not t:
        return ""
    pr, a = t["profile"], t["annual"]
    saving = t["weekTax"] < 0
    week_line = (f"{'saves' if saving else 'costs'} about {_usd(abs(t['weekTax']))} in tax "
                 f"({'loss offsets other income' if saving else 'set this aside'}), "
                 f"{_usd(t['weekAfterTax'])} after tax")
    est = ("At this rate the business owes no tax; its loss lowers the tax on other income."
           if a["total"] < 0 else
           "Projected tax is under $1,000, so no estimated payments are needed at this rate."
           if not t["estimatesNeeded"] else
           f"Projected tax is over $1,000: pay estimates (next due {t['nextDue']}) or raise W-2 withholding.")
    basis = (f"W-2 wages ${pr['w2Wages']:,.0f} with the standard deduction, priced against the "
             f"{pr['taxYear']} bracket table" if pr.get("w2Wages") is not None else
             f"federal bracket {pr['federalMarginal'] * 100:.0f}% set by other income")
    assumed = ("" if t["profileFile"] else
               f" These are defaults; put your real bracket in {html.escape(str(TAX_PROFILE_PATH))}.")
    rows = f"""
      <tr><td>This week's profit {_usd(t['weekProfit'])}</td><td colspan='2'>{week_line}</td></tr>
      <tr><td>Full year at this week's rate</td><td class='num'>{_usd(t['annualProfit'])}</td>
        <td>SE tax {_usd(a['se'])} · federal {_usd(a['federal'])} · Georgia {_usd(a['state'])} ·
          total {_usd(a['total'])}</td></tr>
      <tr><td>Rate on each extra dollar</td><td class='num'>{t['rateProfit'] * 100:.1f}%</td>
        <td>on the first $1,000 of profit (self-employment tax, federal after QBI, Georgia
          {pr['stateRate'] * 100:.2f}%); the first $1,000 of loss saves {t['rateLoss'] * 100:.1f}%</td></tr>
      <tr><td>Sales tax thresholds</td><td class='num'>{t['nexusPct']:.1f}%</td>
        <td>{_usd(t['gross12m'])} and {t['orders12m']} orders in 12 months, all states combined, against a
          single state's lowest threshold ($100,000 or 200 orders)</td></tr>"""
    return f"""
  <h3>Taxes · estimate for {pr['taxYear']}</h3>
  <table><tbody>{rows}</tbody></table>
  <p class="sales-foot">{est} Schedule C, {html.escape(pr['filingStatus'])} filer, {basis}.{assumed} An estimate for planning, not a return.</p>"""


def print_tax(t: dict | None) -> None:
    if not t:
        return
    a = t["annual"]
    word = "saves" if t["weekTax"] < 0 else "owes"
    print(f"   Tax: this week {word} ~{_usd(abs(t['weekTax']))} ({_usd(t['weekAfterTax'])} after tax); "
          f"full year at this rate {_usd(t['annualProfit'])} profit → {_usd(a['total'])} tax "
          f"({t['rateProfit'] * 100:.1f}% on the first $1k of profit, {t['rateLoss'] * 100:.1f}% saved on the first $1k of loss); "
          f"sales-tax threshold {t['nexusPct']:.1f}% of the way"
          + ("" if t["profileFile"] else "; default bracket, set tax-profile.json"))


def profit_block(p: dict | None, ch: dict | None, tax: dict | None = None) -> str:
    if not p:
        return ""
    def cell(v: float) -> str:
        return "<td class='num'>—</td>" if abs(v) < 0.005 else f"<td class='num'>{_usd(v)}</td>"
    body = "".join(
        f"<tr><td>{html.escape(r['line'])}</td><td class='num'>{_usd(r['revenue'])}</td>"
        f"{cell(r['ads'])}{cell(r['api'])}{cell(r['hosting'])}{cell(r['fixed'])}"
        f"<td class='num {'down' if r['profit'] < 0 else 'up'}'>{_usd(r['profit'])}</td>"
        f"<td class='num'>{'—' if r['margin'] is None else format(r['margin'], '.0f') + '%'}</td></tr>"
        for r in p["rows"])
    t = p["total"]
    body += (f"<tr class='total'><td>All lines</td><td class='num'>{_usd(t['revenue'])}</td>"
             f"{cell(t['ads'])}{cell(t['api'])}{cell(t['hosting'])}{cell(t['fixed'])}"
             f"<td class='num {'down' if t['profit'] < 0 else 'up'}'>{_usd(t['profit'])}</td><td></td></tr>")
    gaps = "; ".join(html.escape(g) for g in p["gaps"])
    fixed = (f" Fixed costs: {len(p['fixedItems'])} entered items." if p["fixedItems"] else "")

    ch_html = ""
    if ch:
        if ch["rows"]:
            ch_rows = "".join(
                f"<tr><td>{html.escape(r['channel'])}</td><td class='num'>{r['first']}</td>"
                f"<td class='num'>{_usd(r['firstNet'])}</td><td class='num'>{r['last']}</td>"
                f"<td class='num'>{_usd(r['lastNet'])}</td></tr>" for r in ch["rows"])
            ch_html = f"""
  <h3>Revenue by channel · since {ch['since']}</h3>
  <table><thead><tr><th>Channel</th><th class='num'>Orders, first touch</th><th class='num'>Net</th>
    <th class='num'>Orders, last touch</th><th class='num'>Net</th></tr></thead><tbody>{ch_rows}</tbody></table>
  <p class="sales-foot">First touch is how the buyer first found the site; last touch is the most
    recent arrival from somewhere else before buying. {ch['tagged']} of {ch['orders']} orders since
    {ch['since']} carry a record; the rest came from browsers with Do Not Track or blocked storage.
    {ch['untaggedBefore']} earlier orders predate channel tracking.</p>"""
        else:
            ch_html = ("<h3>Revenue by channel</h3><p class='sales-foot'>Channel tracking started "
                       "2026-09-28. The first order placed after that shows here with where the buyer came from.</p>")
    return f"""
<section class="sales metrics">
  <h2>Profit by product · last {p['days']} days</h2>
  <table><thead><tr><th>Line</th><th class='num'>Net revenue</th><th class='num'>Ads</th>
    <th class='num'>Claude API</th><th class='num'>Hosting</th><th class='num'>Fixed</th>
    <th class='num'>Profit</th><th class='num'>Margin</th></tr></thead><tbody>{body}</tbody></table>
  <p class="sales-foot">Net revenue is after Stripe's fee, refunds and Apple's cut; GlobePin adds
    AdMob earnings. Claude API is the metered cost of {p['jobs']} paid job(s); hosting is Modal's
    billing report per app; fixed costs are spread evenly per day.{fixed} Not measured: {gaps}.</p>
  {tax_block(tax)}
  {ch_html}
</section>"""


def print_profit(p: dict | None, ch: dict | None, tax: dict | None = None) -> None:
    if not p:
        return
    t = p["total"]
    print(f"\n  Profit, last {p['days']}d — {_usd(t['revenue'])} net revenue − {_usd(t['cost'])} costs "
          f"(ads {_usd(t['ads'])}, Claude API {_usd(t['api'])}, hosting {_usd(t['hosting'])}, "
          f"fixed {_usd(t['fixed'])}) = {_usd(t['profit'])}")
    for r in p["rows"]:
        print(f"   {r['line']:<22} {_usd(r['revenue']):>9} − {_usd(r['cost']):>8} = {_usd(r['profit']):>9}")
    print(f"   Not measured: {'; '.join(p['gaps'])}")
    print_tax(tax)
    if ch and ch["rows"]:
        print(f"   By channel since {ch['since']} (last touch): "
              + ", ".join(f"{r['channel']} {r['last']} ({_usd(r['lastNet'])})" for r in ch["rows"] if r["last"]))


# ---------------------------------------------------------------- combined revenue
#
# Pulls together every revenue source into one monthly view: Sales (Stripe,
# both sites), App Store (GlobePin Pro proceeds), and photo licensing
# (scraped/parsed stock-platform balances). Ad revenue (AdSense) has no
# reporting integration at all as of 2026-09 -- both sites are still in
# AdSense's "Needs attention: Low value content" review state, so it is
# rendered as an explicit, honestly-labeled $0/not-yet-earning column rather
# than omitted, so the chart's shape doesn't quietly change once it exists.
#
# This is deliberately NOT called "MRR": almost none of this is recurring
# subscription revenue (ModernTex and the guides are one-time purchases,
# photo licensing is per-download). "Combined monthly revenue" is the
# honest name for what this actually measures.

# The daily launchd job (run.sh) copies this script to a local cache
# (~/.purplelink/traffic/traffic_dashboard.py) and always executes THAT copy
# -- even when the repo's external SSD is mounted -- so Path(__file__) never
# actually points into the repo in production, only when this file is run
# directly from its real location (manual testing, etc.). Found 2026-09-19
# when the first scheduled run after this feature shipped logged "No such
# file or directory: /Users/benampel/.purplelink/photo-dashboard.py" --
# .parent.parent of the LOCAL COPY's path, not the repo's scripts/ dir.
# Try the sibling-relative path first (correct when run from the repo), then
# fall back to the canonical absolute repo path (correct when run from the
# local cache with the SSD mounted). If neither exists -- SSD truly
# unmounted -- _load_photo_dashboard_module's caller already degrades to
# $0 for photo revenue that day, the same honest fallback every other
# source here already has for its own outages.
_PHOTO_DASHBOARD_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "photo-dashboard.py",
    Path("/Volumes/Extreme SSD/Purplelink LLC/scripts/photo-dashboard.py"),
]


def _load_photo_dashboard_module():
    """Import scripts/photo-dashboard.py despite its hyphenated filename
    (which `import photo-dashboard` cannot express) rather than duplicating
    its carry-forward/alamy-dedup logic here -- see platform_money_asof()'s
    own docstring for why that logic has to stay in one place."""
    import importlib.util
    path = next((p for p in _PHOTO_DASHBOARD_CANDIDATES if p.exists()), None)
    if path is None:
        raise FileNotFoundError(
            f"photo-dashboard.py not found at any of: {[str(p) for p in _PHOTO_DASHBOARD_CANDIDATES]}")
    spec = importlib.util.spec_from_file_location("photo_dashboard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recent_months(n: int, today: dt.date | None = None) -> list[str]:
    """The last n calendar months as YYYY-MM, oldest first, ending with the
    current (in-progress) month."""
    today = today or dt.date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(months))


def _month_bounds(month: str) -> tuple[str, str]:
    """(first day, last day) of a YYYY-MM month, both YYYY-MM-DD, inclusive."""
    y, m = (int(x) for x in month.split("-"))
    first = dt.date(y, m, 1)
    last = (dt.date(y + 1, 1, 1) if m == 12 else dt.date(y, m + 1, 1)) - dt.timedelta(days=1)
    return first.isoformat(), last.isoformat()


def sales_revenue_by_month(sales: dict | None, months: list[str]) -> dict[str, float]:
    by_day = (sales or {}).get("byDay") or {}
    # sales["byDay"] (from sales.mjs) isn't the same shape as a site's
    # traffic byDay -- confirm the actual keys it uses before trusting this
    # blindly ever changes; today it's {date: {"gross": cents, "orders": n}}.
    out = {}
    for month in months:
        lo, hi = _month_bounds(month)
        out[month] = sum(v.get("gross", 0) for d, v in by_day.items() if lo <= d <= hi) / 100.0
    return out


def appstore_revenue_by_month(appstore: dict | None, months: list[str]) -> dict[str, float]:
    days = (appstore or {}).get("days") or {}
    out = {}
    for month in months:
        lo, hi = _month_bounds(month)
        total = 0.0
        for d, v in days.items():
            if lo <= d <= hi:
                total += (v.get("proceeds") or {}).get("USD", 0.0)
        out[month] = total
    return out


def marketplace_revenue_by_month(rows: list[dict], months: list[str]) -> dict[str, float]:
    out = {}
    for month in months:
        lo, hi = _month_bounds(month)
        out[month] = sum(r["gross"] for r in rows
                         if lo <= dt.date.fromtimestamp(r["ts"]).isoformat() <= hi) / 100.0
    return out


def photo_revenue_by_month(months: list[str]) -> dict[str, float]:
    """This month's real photo-licensing revenue, derived by diffing
    per-platform balances at each month's start and end (via the shared
    platform_money_asof helper) rather than reporting the running balance
    itself, which is cumulative and would make every month after the first
    look identical to "all time". Each platform's diff is floored at 0
    before summing: a platform whose balance drops mid-period because a
    payout cleared it is 0 new revenue that period, not negative revenue.
    A platform with a per-sale ledger (photo_ledger_by_month) counts the
    larger of its balance diff and its ledger total for the month.
    """
    ledgers = photo_ledger_by_month(months)
    ledger_only = {m: round(sum(v.get(m, 0.0) for v in ledgers.values()), 2) for m in months}
    try:
        pd = _load_photo_dashboard_module()
    except Exception as exc:
        print(f"  ! photo revenue unavailable: {str(exc)[:100]}", file=sys.stderr)
        return ledger_only
    try:
        data = pd.load()
    except SystemExit:
        # pd.load() itself sys.exit()s if snapshots.csv doesn't exist yet --
        # a real, expected state (photo tracking not set up at all), not an
        # error worth a stack trace.
        return ledger_only
    dates = sorted(data)

    def balances_asof(asof: str) -> dict[str, float]:
        _total_money, _total_sales, rows = pd.platform_money_asof(data, dates, asof)
        return {label: (bal or 0.0) for label, bal, *_rest in rows}

    out = {}
    for month in months:
        lo, hi = _month_bounds(month)
        day_before = (dt.date.fromisoformat(lo) - dt.timedelta(days=1)).isoformat()
        start = balances_asof(day_before)
        end = balances_asof(hi if hi <= dates[-1] else dates[-1])
        platforms = set(start) | set(end) | set(ledgers)
        out[month] = round(sum(max(max(0.0, end.get(p, 0.0) - start.get(p, 0.0)), ledgers.get(p, {}).get(month, 0.0))
                               for p in platforms), 2)
    return out


def photo_ledger_by_month(months: list[str]) -> dict[str, dict[str, float]]:
    """Per-sale photo ledgers summed by month, keyed by the balance label they belong to: {label: {month: dollars}}.
    Only Fine Art America so far. Its balance is read once a day by a sweep that sometimes fails, and a payout resets
    it, so the balance diff can miss a sale that the order list has. The two readings are of the same money, so
    photo_revenue_by_month takes the larger one per platform per month and never adds them (as with TikTok's two)."""
    faa = {m: 0.0 for m in months}
    for r in faa_sale_rows(_read_photo_csv("faa-sales.csv")):
        if r["date"][:7] in faa:
            faa[r["date"][:7]] += r["net"] / 100.0
    return {FAA_LABEL: faa}


SRC_EXTENSION = "Chrome extension (ExtensionPay)"
SRC_ADS = "Ad revenue (est.)"
SRC_TIKTOK = "TikTok Creator Rewards (est.)"
REVENUE_SOURCES = [
    ("sales", "Sales", "var(--purple)"),
    ("appstore", "App Store", "var(--good)"),
    ("photo", "Photo licensing", "oklch(75% 0.14 230)"),
    ("marketplaces", "Etsy, Gumroad, Payhip", "oklch(70% 0.12 280)"),
    ("extpay", SRC_EXTENSION, "oklch(72% 0.13 150)"),
    ("ads", SRC_ADS, "oklch(80% 0.12 110)"),
    ("tiktok", SRC_TIKTOK, "oklch(70% 0.16 10)"),
]
# Money that is TikTok's or AdMob's own estimate and has not been paid out. Our estimate of Getty downloads not yet on a
# royalty statement is folded into "photo" and reported separately as series["getty_est"], which is not a source of its own. Shown in the totals, never hidden inside them.
ESTIMATED_SOURCES = ("ads", "tiktok")
TIKTOK_REWARDS_CSV = Path("/Volumes/Extreme SSD/TikTokPipeline/analytics/tiktok_rewards.csv")
# TikTok's own day-by-day estimate (growth_export.py, from the JSON behind Studio's Monetization page). It matches the
# figure in TikTok's app to the cent, so wherever it has a day it is the figure used.
TIKTOK_DAILY_INCOME_CSV = Path("/Volumes/Extreme SSD/TikTokPipeline/analytics/tiktok_daily_income.csv")


def _tiktok_posted(value: str):
    """posted_at as a naive datetime. The collector wrote some posts in local time and later snapshots of the same post
    in UTC with a trailing Z, so the two spellings of one post can sit hours apart; callers match within a window."""
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat((value or "").strip().rstrip("Z")[:19])
    except ValueError:
        return None


def tiktok_posts(rows: list[dict]) -> list[dict]:
    """The per-post rows grouped into one record per real post: {pipeline, caption, video_id, snaps: [(snapshot_at,
    snapshot_date, est)]}.

    Rows are the same post when the pipeline and caption match, the posted_at times are within 12 hours of each other
    (local versus UTC spelling of one time), and their video ids do not disagree. Keying on the raw posted_at string, as
    this code did until 2026-10-20, counted 27 October posts twice and put October at $48.85 against $41.73."""
    import datetime as _dt
    posts: list[dict] = []
    for r in sorted((r for r in rows if r.get("level") == "post"), key=lambda r: r.get("snapshot_at") or ""):
        posted = _tiktok_posted(r.get("posted_at") or "")
        try:
            est = float(r.get("est_rewards") or 0)
        except ValueError:
            continue
        if posted is None:
            continue
        vid = (r.get("video_id") or "").strip()
        for p in posts:
            if (p["pipeline"] == (r.get("pipeline") or "") and p["caption"] == (r.get("caption") or "")
                    and abs(p["posted"] - posted) <= _dt.timedelta(hours=12)
                    and not (vid and p["video_id"] and vid != p["video_id"])):
                break
        else:
            p = {"pipeline": r.get("pipeline") or "", "caption": r.get("caption") or "", "posted": posted,
                 "video_id": vid, "snaps": []}
            posts.append(p)
        p["video_id"] = p["video_id"] or vid
        p["snaps"].append((r.get("snapshot_at") or "", (r.get("snapshot_date") or "")[:10], est))
    return posts


def tiktok_daily_from_posts(rows: list[dict]) -> dict[str, dict[str, float]]:
    """{pipeline: {ISO date: rewards}}: what each post's estimate rose by, counted on the day of the snapshot that saw
    the rise. A post's first snapshot counts in full on its day. A post's estimate only accrues, so a lower later
    figure is ignored rather than counted as a loss (the running high stands). Summed over a month this is every
    post's latest figure, so the days add up to the month exactly."""
    out: dict[str, dict[str, float]] = {}
    for p in tiktok_posts(rows):
        high = 0.0
        for _at, day, est in sorted(p["snaps"]):
            if est > high and day:
                days = out.setdefault(p["pipeline"], {})
                days[day] = days.get(day, 0.0) + est - high
                high = est
    return out


def tiktok_api_daily(path: Path | None = None) -> dict[str, dict[str, float]]:
    """{pipeline: {ISO day: TikTok's estimate for that day}} from tiktok_daily_income.csv, account "Total" series.
    Every collector run appends TikTok's whole 60-day window and TikTok revises recent days, so each day takes its value
    from the latest snapshot that has it. A missing file reads as empty."""
    import csv
    latest: dict[tuple, tuple] = {}
    try:
        with open(path or TIKTOK_DAILY_INCOME_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("program") != "Total" or not re.match(r"^\d{4}-\d\d-\d\d$", r.get("day") or ""):
                    continue
                try:
                    val = float(r.get("est_income") or 0)
                except ValueError:
                    continue
                key = (r.get("pipeline") or "", r["day"])
                at = r.get("snapshot_at") or ""
                if key not in latest or at >= latest[key][0]:
                    latest[key] = (at, val)
    except OSError:
        return {}
    out: dict[str, dict[str, float]] = {}
    for (pipe, day), (_at, val) in latest.items():
        out.setdefault(pipe, {})[day] = val
    return out


def tiktok_daily(path: Path | None = None, api_path: Path | None = None) -> tuple[dict[str, dict[str, tuple[float, bool]]], list[dict]]:
    """{pipeline: {ISO day: (dollars, from_tiktok)}} plus the raw per-post rows.

    For a pipeline with TikTok's own daily figures, every day from its first such day on is TikTok's figure. Days
    before that (and pipelines without it) use the per-post rises (tiktok_daily_from_posts). The two never cover the
    same day, so nothing is counted twice."""
    import csv
    try:
        with open(path or TIKTOK_REWARDS_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        rows = []
    api = tiktok_api_daily(api_path)
    out: dict[str, dict[str, tuple[float, bool]]] = {}
    for pipe, days in tiktok_daily_from_posts(rows).items():
        first_api = min(api.get(pipe) or {"9999-12-31": 0})
        out[pipe] = {d: (v, False) for d, v in days.items() if d < first_api}
    for pipe, days in api.items():
        out.setdefault(pipe, {}).update({d: (v, True) for d, v in days.items()})
    return out, rows


def tiktok_readings(months: list[str], path: Path | None = None, api_path: Path | None = None) -> tuple[dict[str, float], list[dict]]:
    """TikTok Creator Rewards by month (tiktok_daily), plus the raw per-post rows. Missing files read as zeros."""
    by_month = {m: 0.0 for m in months}
    daily, rows = tiktok_daily(path, api_path)
    for days in daily.values():
        for day, (est, _api) in days.items():
            if day[:7] in by_month:
                by_month[day[:7]] += est
    return by_month, rows


def tiktok_rewards_by_month(months: list[str], path: Path | None = None, api_path: Path | None = None) -> dict[str, float]:
    """TikTok Creator Rewards estimates by month: TikTok's own daily figures where the collector has them
    (tiktok_daily_income.csv, since 2026-10-20; they match TikTok's app to the cent), otherwise the rise in each post's
    estimate, counted on the day it was seen.

    Until 2026-10-20 this took the larger of that and the account's rolling 7-day totals rebuilt into days
    (tiktok_daily_by_pipeline). The rebuild assumes each window is a plain sum of fixed days, but Studio revises earlier
    days down, so it came out with negative days and overcounted: $51.08 for October 1-19 against $42.38 in TikTok's
    own app. The per-post reading gave $41.73. It can run a little low, because Studio lists only the newest posts and a
    post that scrolls off stops being updated here. These are TikTok's estimates from Studio, not payouts. A missing
    file reads as zero, quietly."""
    by_month, _rows = tiktok_readings(months, path, api_path)
    return {m: round(v, 2) for m, v in by_month.items()}



def admob_revenue_by_month(admob: dict | None, months: list[str]) -> dict[str, float]:
    """AdMob's estimated earnings by month, from the monthly report stored with the 7-day one."""
    monthly = (((admob or {}).get("globepin") or {}).get("monthly")) or {}
    return {m: float(monthly.get(m, 0.0) or 0.0) for m in months}


def extension_revenue_by_month(rows: list[dict], months: list[str]) -> dict[str, float]:
    return marketplace_revenue_by_month([r for r in rows if r.get("market") == "extensionpay"], months)


def revenue_series(sales, appstore, market_rows, admob, months: list[str]) -> dict[str, dict[str, float]]:
    rows = market_rows or []
    getty_est = getty_estimate_by_month(months)
    photo = photo_revenue_by_month(months)
    return {
        "sales": sales_revenue_by_month(sales, months),
        "appstore": appstore_revenue_by_month(appstore, months),
        "photo": {m: photo.get(m, 0.0) + getty_est.get(m, 0.0) for m in months},
        "marketplaces": marketplace_revenue_by_month([r for r in rows if r.get("market") != "extensionpay"], months),
        "extpay": extension_revenue_by_month(rows, months),
        "ads": admob_revenue_by_month(admob, months),
        "tiktok": tiktok_rewards_by_month(months),
        "getty_est": getty_est,
    }


def print_revenue_sources(sales, appstore, market_rows, admob) -> None:
    """This month's revenue across every source, with the estimated part named, for the daily report."""
    months = recent_months(2)
    series = revenue_series(sales, appstore, market_rows, admob, months)
    now_m, prev = months[-1], months[0]
    def total(m, only=None):
        return sum(series[k].get(m, 0.0) for k, _l, _c in REVENUE_SOURCES if only is None or (k in ESTIMATED_SOURCES) == only)
    getty_est = series["getty_est"].get(now_m, 0.0)
    est = total(now_m, True) + getty_est
    print(f"\n  Revenue, all sources, {dt.datetime.strptime(now_m, '%Y-%m').strftime('%B')} so far: ${total(now_m):,.2f} "
          f"(${total(now_m, False) - getty_est:,.2f} received or sold, ${est:,.2f} estimated); last month ${total(prev):,.2f}")
    bits = [f"{label} ${series[k].get(now_m, 0.0):,.2f}" for k, label, _c in REVENUE_SOURCES if series[k].get(now_m, 0.0) > 0]
    print("   " + ("; ".join(bits) if bits else "nothing yet"))


def revenue_block(sales: dict | None, appstore: dict | None, n_months: int = 6,
                  market_rows: list[dict] | None = None, admob: dict | None = None) -> str:
    months = recent_months(n_months)
    series = revenue_series(sales, appstore, market_rows, admob, months)
    this_month = months[-1]
    this_month_total = sum(series[k].get(this_month, 0.0) for k, _l, _c in REVENUE_SOURCES)
    chips = "".join(
        f"<span class='sales-chip'><b>${series[key].get(this_month, 0.0):,.2f}</b> <span>{html.escape(label)}</span></span>"
        for key, label, _c in REVENUE_SOURCES
    )
    monthly_totals = {m: sum(series[k].get(m, 0.0) for k, _l, _c in REVENUE_SOURCES) for m in months}
    last_month_fig = ""
    if len(months) >= 2:
        prev = months[-2]
        last_month_fig = (f"<div><span class=\"sales-figure-label\">Last month ({dt.datetime.strptime(prev, '%Y-%m').strftime('%B')})</span>"
                          f"<span class=\"sales-secondary\">${monthly_totals[prev]:,.2f}</span></div>")
    est_now = sum(series[k].get(this_month, 0.0) for k in ESTIMATED_SOURCES) + series["getty_est"].get(this_month, 0.0)
    est_note = (f"This month includes ${est_now:,.2f} of estimates that have not been paid out (TikTok Creator Rewards, "
                f"AdMob, Getty downloads not yet on a royalty statement). The rest is money received or sold.")
    return f"""
<section class="sales revenue">
  <h2>Revenue by month &middot; all sources</h2>
  <div class="sales-figures">
    <div>
      <span class="sales-figure-label">This month so far</span>
      <span class="sales-secondary">${this_month_total:,.2f}</span>
    </div>
    {last_month_fig}
  </div>
  <div class="sales-split">{chips}</div>
  <p class="sales-foot">{html.escape(est_note)}</p>
</section>"""




# ---------------------------------------------------------------- every sale, every source
#
# One list for the Money tab: card sales (Stripe, both sites), Etsy/Gumroad/Payhip, App Store
# proceeds and photo-licensing sales, newest first. The photo platforms that publish a
# per-sale report (Getty, Adobe Stock, Dreamstime, Fine Art America, Shutterstock's daily totals) are read from the
# photo arm's CSVs; the rest report totals only, and a line under the table says so.

REFUNDED_TAG = ' <span class="who">(refunded)</span>'
PHOTO_AN = Path("/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace/analytics")


def _cents(v) -> int:
    try:
        return int(round(float(v) * 100))
    except (TypeError, ValueError):
        return 0


FAA_LABEL = "Fine Art America"   # photo-dashboard.py's label for the fineartamerica balance


def faa_sale_rows(ledger: list[dict]) -> list[dict]:
    """Fine Art America orders from faa-sales.csv (scripts/sales-ledgers.py). `total` is our profit on the order (FAA
    pays the markup, not the retail price). Owner purchases have no total and earn nothing, so they are left out."""
    out = []
    for r in ledger:
        if not (r.get("total") or "").strip():
            continue
        out.append({"date": r.get("sale_date", ""), "source": "Photo licensing", "detail": FAA_LABEL,
                    "item": r.get("product", ""), "gross": None, "net": _cents(r.get("total"))})
    return out


def photo_sale_rows() -> list[dict]:
    import csv
    rows: list[dict] = []

    def read(name):
        try:
            with open(PHOTO_AN / name, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except OSError:
            return []

    for r in read("getty-sales.csv"):
        try:
            d = dt.datetime.strptime(r["sale_date"], "%d-%b-%Y").date().isoformat()
        except (KeyError, ValueError):
            continue
        rows.append({"date": d, "source": "Photo licensing", "detail": "Getty / iStock",
                     "item": (r.get("description") or "")[11:] or r.get("asset_id", ""), "gross": None,
                     "net": _cents(r.get("gross_royalty"))})
    for r in read("adobe-sales.csv"):
        rows.append({"date": r.get("sale_date", ""), "source": "Photo licensing", "detail": "Adobe Stock",
                     "item": r.get("title") or r.get("filename", ""), "gross": None, "net": _cents(r.get("amount"))})
    for r in read("dreamstime-sales.csv"):
        rows.append({"date": r.get("sale_date", ""), "source": "Photo licensing", "detail": "Dreamstime",
                     "item": r.get("title") or r.get("filename", ""), "gross": None, "net": _cents(r.get("amount"))})
    for r in faa_sale_rows(read("faa-sales.csv")):
        rows.append(r)
    for r in read("shutterstock-days.csv"):
        n = int(float(r.get("downloads") or 0))
        rows.append({"date": r.get("date", ""), "source": "Photo licensing", "detail": "Shutterstock",
                     "item": f"{n} download{'s' if n != 1 else ''} (daily total)", "gross": None,
                     "net": _cents(r.get("earnings"))})
    unpriced, _rates = getty_unpriced_downloads(read("getty-downloads.csv"), read("getty-sales.csv"))
    for u in unpriced:
        kind = "Premium Access" if u["column"] == "gi_premium" else "subscription"
        rows.append({"date": u["date"], "source": "Photo licensing", "detail": "Getty / iStock (estimate)",
                     "item": f"{u['n']} {kind} download{'s' if u['n'] != 1 else ''}, royalty not on a statement yet "
                             f"(asset {u['asset_id']})", "gross": None, "net": u["est_cents"], "estimate": True})
    return [r for r in rows if re.match(r"^\d{4}-\d\d-\d\d$", r["date"])]


# Getty pays per download, a month or more late: the royalty statement is the only place a download turns into dollars.
# The download ledger (getty-downloads.csv) is current, so downloads that no statement row covers yet are priced at the
# average royalty the statements have paid for the same product type. Product columns of the download ledger that map
# to a statement product_type; anything else is left unpriced rather than guessed.
GETTY_TYPE_COLUMNS = {"Premium Access Time Limited": "gi_premium", "iStock Subscription": "is_subscriptions"}


def getty_unpriced_downloads(downloads: list[dict], sales: list[dict]) -> tuple[list[dict], dict[str, float]]:
    """Getty downloads with no statement row yet, each with an estimated royalty in cents.

    Per asset and product type, downloads minus statement sales is what is still unpaid (never below zero). The
    rate is the mean gross_royalty of the statement rows of that product type, so it follows what Getty really pays and
    updates itself as statements arrive; a type with no statement row yet gets no estimate. The ledger only keeps each
    asset's latest download date, so an asset downloaded in two months puts all its unpaid downloads in the later one.
    Returns (rows, rates) where rows are {asset_id, date, column, n, est_cents} and rates is {column: dollars}."""
    paid: dict[tuple[str, str], int] = {}
    totals: dict[str, list[float]] = {}
    for r in sales:
        col = GETTY_TYPE_COLUMNS.get((r.get("product_type") or "").strip())
        try:
            royalty = float(r.get("gross_royalty"))
        except (TypeError, ValueError):
            continue
        if not col:
            continue
        paid[(r.get("asset_id", ""), col)] = paid.get((r.get("asset_id", ""), col), 0) + 1
        totals.setdefault(col, []).append(royalty)
    rates = {col: sum(v) / len(v) for col, v in totals.items()}
    out = []
    for d in downloads:
        date = (d.get("last_download") or "")[:10]
        for col, rate in rates.items():
            try:
                have = int(float(d.get(col) or 0))
            except ValueError:
                continue
            n = max(0, have - paid.get((d.get("asset_id", ""), col), 0))
            if n:
                out.append({"asset_id": d.get("asset_id", ""), "date": date, "column": col, "n": n,
                            "est_cents": _cents(n * rate)})
    return out, rates


def _read_photo_csv(name: str) -> list[dict]:
    import csv
    try:
        with open(PHOTO_AN / name, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def getty_estimate_by_month(months: list[str]) -> dict[str, float]:
    """Estimated Getty royalty for downloads not on a statement yet, by the month of the asset's latest download."""
    out = {m: 0.0 for m in months}
    rows, _rates = getty_unpriced_downloads(_read_photo_csv("getty-downloads.csv"), _read_photo_csv("getty-sales.csv"))
    for r in rows:
        if r["date"][:7] in out:
            out[r["date"][:7]] += r["est_cents"] / 100.0
    return {m: round(v, 2) for m, v in out.items()}


def tiktok_sale_rows(path: Path | None = None, api_path: Path | None = None) -> list[dict]:
    """One estimate row per day per pipeline from tiktok_daily: TikTok's own figure for the day where the collector has
    it, otherwise what that day's snapshot added to the posts' estimates. These rows are what tiktok_rewards_by_month
    sums. TikTok's estimates, not payouts: every row is marked estimate and kept out of the received total."""
    daily, _rows = tiktok_daily(path, api_path)
    out = []
    for pipe, days in sorted(daily.items()):
        for day, (est, from_tiktok) in sorted(days.items()):
            if _cents(est) == 0:
                continue
            out.append({"date": day, "source": SRC_TIKTOK, "detail": pipe or "tiktok",
                        "item": "TikTok's estimate for the day" if from_tiktok
                        else "Creator Rewards estimate added that day (per-post)",
                        "gross": None, "net": _cents(est), "estimate": True, "from_tiktok": from_tiktok})
    return out


def tiktok_month_note(rows: list[dict], path: Path | None = None) -> str:
    """Says how the TikTok rows are counted, and flags any rows that still come from the per-post reading."""
    tik = [r for r in rows if r["source"] == SRC_TIKTOK]
    if not tik:
        return ""
    per_post = [r for r in tik if not r.get("from_tiktok", False)]
    if not per_post:
        return "TikTok rows are TikTok's own daily estimates, the same figures as TikTok's app."
    return ("TikTok rows marked per-post are the rise in each post's estimate on the day a snapshot saw it, used where "
            "TikTok's own daily figure was not recorded; they can run slightly below TikTok's app.")


def admob_month_rows(admob: dict | None, today: dt.date | None = None) -> list[dict]:
    """AdMob only gives us monthly earnings (fetch_admob stores {YYYY-MM: dollars} next to the 7-day report, whose own
    days are not kept), so each month with earnings is one estimate row, dated its last day with data: the month's
    end, or today for the month still running."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    out = []
    monthly = (((admob or {}).get("globepin") or {}).get("monthly")) or {}
    for ym, usd in sorted(monthly.items()):
        try:
            first = dt.date.fromisoformat(ym + "-01")
            cents = _cents(usd)
        except ValueError:
            continue
        if cents <= 0 or first > today:
            continue
        end = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
        out.append({"date": min(end, today).isoformat(), "source": SRC_ADS, "detail": "GlobePin (AdMob)",
                    "item": f"AdMob estimate, month total for {first.strftime('%B %Y')}", "gross": None,
                    "net": cents, "estimate": True})
    return out


def _photo_platform_has_ledger(label: str, listed: list[dict]) -> bool:
    """Same label match photo_totals_only_note has always used: a balance row belongs to a platform that already lists
    per-sale rows when the first word of one of those rows' detail starts its label."""
    details = {r["detail"] for r in listed if r["source"] == "Photo licensing"}
    return any(label.lower().startswith(d.lower().split(" ")[0]) for d in details)


def photo_balance_rows(listed: list[dict]) -> list[dict]:
    """Sales of photo platforms that only report a balance, as the day-to-day rises of that balance.

    Walks every snapshot day with photo-dashboard's platform_money_asof (the carry-forward helper, so a failed
    collector run never reads as a payout). A rise is revenue, dated the day it showed up. A drop is a payout clearing
    the balance, not negative revenue: the next rise is measured from the new, lower level. Platforms that already have
    a per-sale ledger in `listed` are skipped. The monthly photo figure instead takes the net balance change over the
    month, so across a month with a payout these rows can add up to more than it; they never add up to less."""
    try:
        pd = _load_photo_dashboard_module()
        data = pd.load()
        dates = sorted(data)
        out: list[dict] = []
        prev: dict[str, float] = {}
        for day in dates:
            _t, _s, money_rows = pd.platform_money_asof(data, dates, day)
            for label, bal, *_rest in money_rows:
                bal = bal or 0.0
                rise = _cents(bal - prev.get(label, 0.0))
                prev[label] = bal
                if rise > 0 and not _photo_platform_has_ledger(label, listed):
                    out.append({"date": day, "source": "Photo licensing", "detail": label,
                                "item": "balance rose (sale not itemised by the platform)", "gross": None,
                                "net": rise})
        return out
    except (Exception, SystemExit):  # noqa: BLE001 - photo tracking may be absent; the rest of the list must still render
        return []


def all_sales_rows(ledger_rows: list[dict], appstore: dict | None, admob: dict | None = None,
                   today: dt.date | None = None) -> list[dict]:
    rows: list[dict] = []
    for r in ledger_rows:
        # Marketplace and ExtensionPay rows are kind "order"; leaving that out hid every one of them from this list.
        if r.get("kind") not in (None, "purchase", "renewal", "order"):
            continue
        market = r.get("market")
        if market == "extensionpay":
            source, detail = SRC_EXTENSION, "Scholar Utility Belt Pro"
        elif market:
            source, detail = "Etsy, Gumroad, Payhip", MARKETPLACE_LABELS.get(market, market)
        else:
            source = "Card sales (Stripe)"
            detail = "MuscleOnGLP" if r.get("site") == "muscleonglp" else "purplelink.llc"
        rows.append({"date": dt.date.fromtimestamp(r["ts"]).isoformat(), "source": source, "detail": detail,
                     "item": PRODUCT_LABELS.get(r.get("product", ""), r.get("product", "")),
                     "gross": r.get("gross", 0), "net": _row_net(r),
                     "refunded": bool(r.get("refunded"))})
    for d, v in ((appstore or {}).get("days") or {}).items():
        usd = (v.get("proceeds") or {}).get("USD", 0.0)
        if usd:
            rows.append({"date": d, "source": "App Store", "detail": "GlobePin",
                         "item": f"Pro ({v.get('proUnits', 0)} unit(s))", "gross": None, "net": _cents(usd)})
    photo = photo_sale_rows()
    rows += photo
    rows += photo_balance_rows(photo)
    rows += tiktok_sale_rows()
    rows += admob_month_rows(admob, today)
    rows.sort(key=lambda r: (r["date"], r["source"]), reverse=True)
    return rows


def all_sales_by_day(rows: list[dict], today: dt.date | None = None, days: int = 60) -> list[dict]:
    """The same rows as the big table, added up per calendar day for the last `days` days, newest first. Every day is
    listed, empty ones too, so a quiet day reads as quiet. `received` is the non-estimate rows (what was sold or paid),
    `estimated` the rows marked estimate, `total` both, all in cents. Rows dated after today are not shown."""
    today = today or dt.date.today()
    window = [(today - dt.timedelta(days=k)).isoformat() for k in range(days)]
    got = {d: [0, 0] for d in window}
    for r in rows:
        if r["date"] in got:
            got[r["date"]][1 if r.get("estimate") else 0] += r["net"]
    return [{"date": d, "received": got[d][0], "estimated": got[d][1], "total": got[d][0] + got[d][1]} for d in window]


REVENUE_DAILY_CSV = OUT_DIR / "revenue_daily.csv"


def archive_revenue_daily(history: dict, rows: list[dict]) -> dict:
    """Keep every day's revenue, per source, in history["revenueDaily"]: {date: {source: {"received": cents,
    "estimated": cents}}}, built from the all-sales rows (all_sales_rows) so it is the same money as the table.

    Each run replaces the (date, source) pairs it has rows for and keeps the rest. A source whose own file goes
    missing (TikTok's daily figures, a photo CSV) therefore keeps its past days here, so the series behind the
    Overview chart and the causal tests (insights/experiments) does not lose history. Returns the archive."""
    fresh: dict[str, dict[str, dict[str, int]]] = {}
    for r in rows:
        if not re.match(r"^\d{4}-\d\d-\d\d$", r.get("date") or ""):
            continue
        cell = fresh.setdefault(r["date"], {}).setdefault(r["source"], {"received": 0, "estimated": 0})
        cell["estimated" if r.get("estimate") else "received"] += int(r.get("net") or 0)
    archive = history.setdefault("revenueDaily", {})
    for day, by_src in fresh.items():
        archive.setdefault(day, {}).update(by_src)
    return archive


def write_revenue_daily_csv(archive: dict, path: Path | None = None) -> None:
    """The archive as a long CSV (date, source, received, estimated, total; dollars) for pandas and the insights
    scripts. Rewritten whole each run; the archive in history.json is the record."""
    import csv
    path = path or REVENUE_DAILY_CSV
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "source", "received", "estimated", "total"])
        for day in sorted(archive):
            for src in sorted(archive[day]):
                c = archive[day][src]
                rec, est = int(c.get("received", 0)), int(c.get("estimated", 0))
                w.writerow([day, src, f"{rec / 100:.2f}", f"{est / 100:.2f}", f"{(rec + est) / 100:.2f}"])
    tmp.replace(path)


# ---- revenue forecast. Plain Python so it runs wherever the dashboard does; ARIMA candidates join only when
# statsmodels imports. Mirrors ~/.purplelink/insights/revenue_forecast/forecast.py: candidates are scored by a
# rolling-origin backtest (last 28 days, refit at each origin, score the 7-day total), the winner is refit on all days.
FC_HORIZON = 60          # days forecast (the page slices 14 / 30 / 60)
FC_WINDOW = 90           # most recent complete days the models see
FC_BACKTEST, FC_STEP = 28, 7
FC_PATHS = 2000          # bootstrap paths for the 80% range
FC_ARIMA = True          # tests switch this off; the real run still needs statsmodels to import
FC_ARIMA_BUDGET = 25.0   # seconds of ARIMA fitting allowed before the candidate is dropped


def _fc_mean_all(y: list[float], h: int):
    m = sum(y) / len(y)
    return [m] * h, [v - m for v in y]


def _fc_mean_28(y: list[float], h: int):
    w = y[-28:]
    m = sum(w) / len(w)
    return [m] * h, [v - m for v in w]


def _fc_ses(y: list[float], h: int):
    """Simple exponential smoothing; alpha by least squares on a grid."""
    best = None
    for alpha in (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9):
        level, errs = y[0], []
        for v in y[1:]:
            e = v - level
            errs.append(e)
            level += alpha * e
        sse = sum(e * e for e in errs)
        if best is None or sse < best[0]:
            best = (sse, level, errs)
    return [best[1]] * h, best[2]


def _fc_damped(y: list[float], h: int):
    """Holt's linear trend with damping; alpha, beta, phi by least squares on a coarse grid."""
    best = None
    for alpha in (0.05, 0.1, 0.2, 0.35, 0.5, 0.7):
        for beta in (0.05, 0.15, 0.3):
            for phi in (0.8, 0.9, 0.95, 0.98):
                level, trend, errs = y[0], 0.0, []
                for v in y[1:]:
                    pred = level + phi * trend
                    e = v - pred
                    errs.append(e)
                    level = pred + alpha * e
                    trend = phi * trend + alpha * beta * e
                sse = sum(e * e for e in errs)
                if best is None or sse < best[0]:
                    best = (sse, level, trend, phi, errs)
    _, level, trend, phi, errs = best
    out, damp = [], 0.0
    for i in range(1, h + 1):
        damp += phi ** i
        out.append(level + damp * trend)
    return out, errs


def _fc_arima_candidates(deadline: float) -> dict:
    """ARIMA by AIC and ARIMA with weekly seasonality, only when statsmodels is importable. {} otherwise."""
    if not FC_ARIMA:
        return {}
    try:
        import warnings
        from statsmodels.tsa.arima.model import ARIMA
    except Exception:
        return {}

    def check():
        if time.monotonic() > deadline:
            raise TimeoutError("arima budget")

    def fit(*a, **k):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return ARIMA(*a, **k).fit()

    def arima_best(y, h):
        best = None
        for order in ((0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1)):
            check()
            try:
                f = fit(y, order=order, trend="c" if order[1] == 0 else "n")
            except Exception:
                continue
            if best is None or f.aic < best.aic:
                best = f
        if best is None:
            raise ValueError("no ARIMA order fit")
        return [float(v) for v in best.forecast(h)], [float(v) for v in best.resid]

    def arima_weekly(y, h):
        check()
        f = fit(y, order=(1, 0, 0), seasonal_order=(1, 0, 0, 7), trend="c")
        return [float(v) for v in f.forecast(h)], [float(v) for v in f.resid]

    return {"ARIMA (order by AIC)": arima_best, "ARIMA with weekly seasonality": arima_weekly}


def fc_candidates(deadline: float | None = None) -> dict:
    c = {"Mean of all days": _fc_mean_all, "Mean of last 28 days": _fc_mean_28,
         "Simple exponential smoothing": _fc_ses, "Damped-trend smoothing": _fc_damped}
    c.update(_fc_arima_candidates(deadline if deadline is not None else time.monotonic() + FC_ARIMA_BUDGET))
    return c


def fc_backtest(y: list[float], candidates: dict | None = None) -> dict[str, float]:
    """Mean absolute error of the 7-day total, rolling origin over the last 28 days. A candidate that raises is dropped."""
    candidates = candidates if candidates is not None else fc_candidates()
    n = len(y)
    origins = range(max(14, n - FC_BACKTEST), n - FC_STEP + 1)
    scores: dict[str, float] = {}
    for name, fn in candidates.items():
        errs = []
        try:
            for o in origins:
                fc, _ = fn(y[:o], FC_STEP)
                errs.append(abs(sum(max(0.0, v) for v in fc) - sum(y[o:o + FC_STEP])))
        except Exception:
            continue
        if errs:
            scores[name] = sum(errs) / len(errs)
    return scores


def forecast_series(y: list[float], horizon: int = FC_HORIZON, candidates: dict | None = None) -> dict | None:
    """Forecast the next `horizon` days of a daily series (cents, complete days only). None when under 21 days.

    Returns {model, mae, scores, fc, lo, hi, total30, total30_lo, total30_hi} with fc/lo/hi per day, never below 0.
    The band is the 80% range of the 7-day average, from bootstrapped centred residuals of the chosen model clipped
    at 0 (six lead-in days drawn from the same process give the first forecast days a full week); it is widened to
    hold the point forecast, which is the planning figure."""
    if len(y) < 21:
        return None
    candidates = candidates if candidates is not None else fc_candidates()
    scores = fc_backtest(y, candidates)
    if not scores:
        return None
    best = min(scores, key=lambda k: (scores[k], k))
    fc_raw, resid = candidates[best](y, horizon)
    fc = [max(0.0, float(v)) for v in fc_raw]
    resid = [r for r in resid if r == r]
    mu = sum(resid) / len(resid) if resid else 0.0
    resid = [r - mu for r in resid]
    rng = random.Random(7)
    cols: list[list[float]] = [[] for _ in range(horizon)]
    month: list[float] = []
    for _ in range(FC_PATHS):
        # Six lead-in days drawn from the same process, so the 7-day average has a full week from the first
        # forecast day on (a band that starts as a single day's spread would flare open at "today").
        lead = [max(0.0, fc[0] + (rng.choice(resid) if resid else 0.0)) for _ in range(6)]
        path = [max(0.0, f + (rng.choice(resid) if resid else 0.0)) for f in fc]
        full = lead + path
        for j in range(horizon):
            cols[j].append(sum(full[j:j + 7]) / 7)
        month.append(sum(path[:30]))

    def pct(vals: list[float], q: float) -> float:
        s = sorted(vals)
        return s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))]

    lo = [min(pct(c, 0.10), f) for c, f in zip(cols, fc)]
    hi = [max(pct(c, 0.90), f) for c, f in zip(cols, fc)]
    return {"model": best, "mae": round(scores[best]), "scores": {k: round(v) for k, v in sorted(scores.items(), key=lambda kv: kv[1])},
            "fc": [round(v) for v in fc], "lo": [round(v) for v in lo], "hi": [round(v) for v in hi],
            "total30": round(sum(fc[:30])), "total30_lo": round(pct(month, 0.10)), "total30_hi": round(pct(month, 0.90))}


def revenue_chart_data(archive: dict | None, today: dt.date | None = None) -> dict | None:
    """What the Overview chart draws: every day from the archive's first day through today, per source in cents
    ({source: {"r": [received...], "e": [estimated...]}}), plus the forecast for all sources with estimates and for
    received money alone. None when the archive holds no money. The forecast never breaks the page: a failure leaves
    "forecast" empty and prints one line."""
    today = today or dt.date.today()
    days_with = sorted(d for d in (archive or {}) if re.match(r"^\d{4}-\d\d-\d\d$", d) and d <= today.isoformat())
    if not days_with:
        return None
    start = dt.date.fromisoformat(days_with[0])
    n = (today - start).days + 1
    days = [(start + dt.timedelta(days=i)).isoformat() for i in range(n)]
    srcs: dict[str, dict[str, list[int]]] = {}
    for i, d in enumerate(days):
        for src, c in (archive.get(d) or {}).items():
            s = srcs.setdefault(src, {"r": [0] * n, "e": [0] * n})
            s["r"][i] += int(c.get("received", 0) or 0)
            s["e"][i] += int(c.get("estimated", 0) or 0)
    if not any(sum(s["r"]) + sum(s["e"]) for s in srcs.values()):
        return None
    order = sorted(srcs, key=lambda k: -(sum(srcs[k]["r"]) + sum(srcs[k]["e"])))
    forecast: dict = {}
    try:
        complete = slice(max(0, n - 1 - FC_WINDOW), n - 1)       # today is still running: leave it out of the fit
        allv = [float(sum(srcs[k]["r"][i] + srcs[k]["e"][i] for k in srcs)) for i in range(n)][complete]
        recv = [float(sum(srcs[k]["r"][i] for k in srcs)) for i in range(n)][complete]
        for key, series in (("all", allv), ("received", recv)):
            f = forecast_series(series)
            if f:
                forecast[key] = f
    except Exception as e:  # noqa: BLE001 - a forecast failure must not take the dashboard down
        print(f"  (revenue forecast skipped: {type(e).__name__}: {e})")
        forecast = {}
    return {"today": today.isoformat(), "start": days[0], "n": n, "order": order,
            "sources": {k: srcs[k] for k in order}, "forecast": forecast, "horizon": FC_HORIZON}


def _json_for_script(obj) -> str:
    return json.dumps(obj, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def daily_revenue_block(archive: dict | None, today: dt.date | None = None) -> str:
    """Overview: money per day as an interactive chart (REV_JS draws it from the embedded JSON). Bars stack what was
    sold or received (solid) under estimates (TikTok, AdMob, Getty downloads not on a statement; lighter), so an
    estimate is never read as cash. Controls: range, weekly and 30-day lines, estimates, sources, forecast."""
    data = revenue_chart_data(archive, today)
    if not data:
        return ""
    return f"""
<section class="sales daily-revenue" id="rev">
  <h2>Revenue by day</h2>
  <div class="rev-fig" id="rev-fig" role="group" aria-label="Totals for the selection"></div>
  <div class="rev-controls" id="rev-controls" role="group" aria-label="Chart controls"></div>
  <div class="rev-plot" id="rev-plot"><div class="rev-tip" id="rev-tip" hidden></div></div>
  <p class="rev-caption" id="rev-caption"></p>
  <div class="sr-only" id="rev-live" aria-live="polite"></div>
  <noscript><p class="sales-foot">The chart needs JavaScript. The same figures are in the Money tab.</p></noscript>
  <script type="application/json" id="rev-data">{_json_for_script(data)}</script>
</section>"""


def photo_totals_only_note(listed: list[dict]) -> str:
    """Platforms that report a sales count and balance but no per-sale rows. Their balance rises are listed
    as photo rows (photo_balance_rows), so this names them and says how many sales the platform counts."""
    try:
        pd = _load_photo_dashboard_module()
        data = pd.load()
        dates = sorted(data)
        _t, _s, money_rows = pd.platform_money_asof(data, dates, dates[-1])
    except (Exception, SystemExit):  # noqa: BLE001 - this note is a convenience; pd.load() exits when photo tracking has no snapshots yet
        return ""
    ledger_labels = [r for r in listed if r["source"] == "Photo licensing" and not r["item"].startswith("balance rose")]
    bits = []
    for label, bal, sales_n, *_rest in money_rows:
        if (sales_n or 0) > 0 and not _photo_platform_has_ledger(label, ledger_labels):
            bits.append(f"{label} ({int(sales_n)} sale{'s' if int(sales_n) != 1 else ''}, ${bal or 0:,.2f})")
    return ("Photo platforms that report totals only, so their sales are shown as balance rises, not itemised: "
            + "; ".join(bits) + ". A payout lowers the balance and counts as nothing; the next rise starts from the new level. "
            "Monthly photo revenue uses each month's net balance change, so across a payout these rows can add up to more."
            if bits else "")


# Chip order for the all-sales list: sold or received sources first, estimates last.
ALL_SALES_SOURCES = ["Card sales (Stripe)", "Etsy, Gumroad, Payhip", SRC_EXTENSION, "App Store", "Photo licensing", SRC_TIKTOK, SRC_ADS]


def all_sales_block(ledger_rows: list[dict], appstore: dict | None, admob: dict | None = None,
                    today: dt.date | None = None) -> str:
    rows = all_sales_rows(ledger_rows, appstore, admob, today)
    sources = ALL_SALES_SOURCES
    chips = "".join(
        f"<button type='button' class='src-chip' data-src=\"{html.escape(src)}\">{html.escape(src)} "
        f"<b>{sum(1 for r in rows if r['source'] == src)}</b></button>" for src in sources)
    body = "".join(
        f"<tr data-src=\"{html.escape(r['source'])}\"><td class='who'>{r['date']}</td>"
        f"<td>{html.escape(r['source'])}<span class='who'> &middot; {html.escape(r['detail'])}</span></td>"
        f"<td title=\"{html.escape(r['item'])}\">{html.escape(r['item'][:80])}{REFUNDED_TAG if r.get('refunded') else ''}</td>"
        f"<td class='num'>{'' if r['gross'] is None else money(r['gross'])}</td>"
        f"<td class='num'>{'~' if r.get('estimate') else ''}{money(r['net'])}</td></tr>"
        for r in rows) or "<tr><td colspan='5' class='who'>No sales on record yet.</td></tr>"
    real_rows = [r for r in rows if not r.get("estimate")]
    total_net = sum(r["net"] for r in real_rows)
    est_rows = [r for r in rows if r.get("estimate")]
    est_net = sum(r["net"] for r in est_rows)
    getty_rows = [r for r in est_rows if r["detail"].startswith("Getty")]
    tiktok_rows = [r for r in est_rows if r["source"] == SRC_TIKTOK]
    ad_rows = [r for r in est_rows if r["source"] == SRC_ADS]
    est_bits = []
    if getty_rows:
        n = sum(int(re.match(r"\d+", r["item"]).group()) for r in getty_rows)
        est_bits.append(f"{n} Getty download(s) not on a royalty statement yet, about {money(sum(r['net'] for r in getty_rows))} "
                        f"at the average royalty Getty has paid per download")
    if tiktok_rows:
        est_bits.append(f"{money(sum(r['net'] for r in tiktok_rows))} of TikTok Creator Rewards estimated by TikTok Studio, not yet paid")
    if ad_rows:
        est_bits.append(f"{money(sum(r['net'] for r in ad_rows))} of AdMob earnings estimated by AdMob, as one row per month")
    est_sentence = (" Rows marked ~ are estimates, not in the received or sold total: " + "; ".join(est_bits) + "."
                    if est_rows else "")
    notes = [n for n in (photo_totals_only_note(rows), tiktok_month_note(rows)) if n]
    return f"""
<section class="sales all-sales">
  <h2>All sales &middot; every source</h2>
  <p class="sales-sub">{len(real_rows)} sale(s) on record: {money(total_net)} received or sold after fees or royalty split,
  plus {money(est_net)} estimated, {money(total_net + est_net)} combined. Newest first.{est_sentence}</p>
  <div class="src-chips"><button type="button" class="src-chip on" data-src="">All <b>{len(rows)}</b></button>{chips}</div>
  <div class="sales-scroll"><table class="sales-list">
    <thead><tr><th>Date</th><th>Source</th><th>Item</th><th class="num">Gross</th><th class="num">Kept</th></tr></thead>
    <tbody>{body}</tbody>
    <tfoot><tr><td colspan="4">Received or sold</td><td class="num">{money(total_net)}</td></tr>
    <tr><td colspan="4">Estimated (~, not received)</td><td class="num">~{money(est_net)}</td></tr>
    <tr><td colspan="4">Combined</td><td class="num">{money(total_net + est_net)}</td></tr></tfoot>
  </table></div>
  {''.join(f'<p class="sales-foot">{html.escape(n)}</p>' for n in notes)}
</section>"""


# ---------------------------------------------------------------- navigation
#
# The page grew into one long scroll. render() now files each block under a tab
# (Overview, Money, Ads, Apps, one per site) and a small script adds: tab
# switching with the choice remembered, click-to-collapse headings, a filter box
# that searches every tab, and expand/collapse all. With JavaScript off the
# blocks all show, in the old order, so nothing is hidden by the script's absence.

NAV_CSS = """
.topnav{position:sticky;top:0;z-index:5;margin:0 -4px 20px;padding:8px 4px;background:var(--bg);border-bottom:1px solid var(--line)}
.topnav .tabs{display:flex;flex-wrap:wrap;gap:6px}
.topnav a.tab{padding:6px 14px;border-radius:999px;border:1px solid var(--line);color:var(--muted);
  text-decoration:none;font-size:14px;white-space:nowrap;min-height:34px;display:inline-flex;align-items:center}
.topnav a.tab:hover{border-color:var(--purple);color:var(--ink)}
.topnav a.tab.on{background:var(--purple);border-color:var(--purple);color:var(--on-purple);font-weight:640}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;max-width:100%}
.tools input[type=search]{font:inherit;font-size:14px;padding:6px 12px;border-radius:999px;border:1px solid var(--line);
  background:var(--panel);color:var(--ink);width:min(220px,46vw);min-height:34px}
.tools input[type=search]::placeholder{color:var(--muted);opacity:1}
.tools button{font:inherit;font-size:13px;padding:6px 12px;white-space:nowrap;border-radius:999px;border:1px solid var(--line);
  background:transparent;color:var(--muted);cursor:pointer;min-height:34px}
.tools button:hover{border-color:var(--purple);color:var(--ink)}
.tools .count{font-size:13px;color:var(--muted)}
.tools .count:empty{display:none}
@media (max-width:640px){
  .sales table,.tables table,table.glance{display:block;max-width:100%;overflow-x:auto}
  .sales-list{display:table}
  .sales{padding:18px 16px}
  .card{padding:18px 16px}
  body{padding:16px}
}
@media (max-width:640px){
  .topnav .tabs{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
  .topnav .tabs::-webkit-scrollbar{display:none}
  .topnav a.tab{min-height:40px;flex:none}
  .tools{width:100%}
  .tools input[type=search]{flex:1 1 100%;width:auto}
  .tools button{flex:1 1 auto;min-height:40px}
}
.js [data-panel]:not(.active){display:none}
[data-panel] > h2.panel-title{display:none}
.js.all [data-panel]{display:block}
.js.all [data-panel] > h2.panel-title{display:block;margin:30px 0 14px;font-size:18px;color:var(--ink);
  padding-bottom:6px;border-bottom:1px solid var(--line)}
.js h2.fold,.js .sales > h2{cursor:pointer;display:flex;align-items:center;gap:8px;user-select:none}
.js h2.fold::before,.js .sales > h2::before{content:"";width:0;height:0;flex:none;border-left:6px solid var(--muted);
  border-top:4px solid transparent;border-bottom:4px solid transparent;transition:transform .15s}
.js .fold-block:not(.collapsed) > h2.fold::before,.js .sales:not(.collapsed) > h2::before,.js .tables > .card:not(.collapsed) > h2.fold::before{transform:rotate(90deg)}
.js .collapsed > :not(h2){display:none}
.js .collapsed > h2{margin-bottom:0}
.hidden-by-filter{display:none!important}
.src-chips{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.src-chip{font:inherit;font-size:13px;padding:5px 12px;min-height:32px;border-radius:999px;border:1px solid var(--line);background:transparent;color:var(--muted);cursor:pointer}
.src-chip[disabled]{opacity:.5;cursor:default}
.src-chip b{color:var(--ink);font-weight:640;margin-left:4px}
.src-chip:hover{border-color:var(--purple)}
.src-chip.on{background:var(--purple);border-color:var(--purple);color:var(--on-purple)}
.src-chip.on b{color:inherit}
.sales-scroll{max-height:560px;overflow:auto;border-top:1px solid var(--line)}
.sales-list{width:100%;border-collapse:collapse;font-size:.88rem}
.sales-list th{position:sticky;top:0;background:var(--panel);text-align:left;font-size:.75rem;color:var(--muted);padding:8px 10px;border-bottom:1px solid var(--line)}
.sales-list td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
.sales-list tfoot td{font-weight:640;border-bottom:0;position:sticky;bottom:0;background:var(--panel)}
.sales-list td.num.who,.sales-list td.who.num{color:var(--muted)}
.sales-list .num,.sales-list th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.sales-list .who{color:var(--muted)}
.sales-list td,.sales-list th{white-space:nowrap}
.sales-list td:first-child,.sales-list th:first-child{min-width:7.5em}
.all-sales .sales-list:not(.by-day) td:nth-child(3){max-width:26em;overflow:hidden;text-overflow:ellipsis}
.by-day-title{margin:14px 0 6px;font-size:.95rem;color:var(--muted);font-weight:600}
.embed{width:100%;border:1px solid var(--line);border-radius:var(--radius);background:var(--bg);min-height:480px;display:block}
.embed-meta{color:var(--muted);font-size:.85rem;margin:0 0 12px}
.embed-meta code{font-size:.8rem}
.embed-meta a{color:var(--purple)}
.glance{width:100%;border-collapse:collapse;font-size:.92rem}
.glance th{text-align:left;font-weight:600;color:var(--muted);font-size:.78rem;padding:6px 10px 6px 0;
  border-bottom:1px solid var(--line)}
.glance td{padding:8px 10px 8px 0;border-bottom:1px solid var(--line)}
.glance td.num,.glance th.num{text-align:right;font-variant-numeric:tabular-nums}
.site-notes{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:16px 22px;margin:0 0 22px}
.site-notes h2{margin:0 0 6px}
.site-notes ul{margin:6px 0 0;padding-left:1.1em}
.site-notes li{margin:4px 0}
.site-notes details{margin-top:10px;color:var(--muted);font-size:.9rem}
.site-notes summary{cursor:pointer}
@media (prefers-reduced-motion:reduce){.js h2.fold::before,.js .sales > h2::before{transition:none}}
"""

NAV_JS = """
(function(){
  var root=document.documentElement; root.classList.add('js');
  var tabs=[].slice.call(document.querySelectorAll('a.tab')), panels=[].slice.call(document.querySelectorAll('[data-panel]'));
  var KEY='dash-tab', filterEl=document.getElementById('dash-filter'), countEl=document.getElementById('dash-count');
  function store(v){try{localStorage.setItem(KEY,v)}catch(e){}}
  function recall(){try{return localStorage.getItem(KEY)}catch(e){return null}}
  function show(name){
    var all=name==='all';
    root.classList.toggle('all',all);
    panels.forEach(function(p){p.classList.toggle('active',all||p.dataset.panel===name)});
    tabs.forEach(function(t){t.classList.toggle('on',t.dataset.tab===name)});
    if(history.replaceState)history.replaceState(null,'','#'+name);
    if(typeof fitSoon==='function')fitSoon();
  }
  tabs.forEach(function(t){t.addEventListener('click',function(e){e.preventDefault();clearFilter();show(t.dataset.tab);store(t.dataset.tab);window.scrollTo(0,0)})});
  var start=(location.hash||'').slice(1)||recall()||'overview';
  if(!tabs.some(function(t){return t.dataset.tab===start}))start='overview';
  // Source chips on the all-sales list: show one source's rows, or all.
  [].slice.call(document.querySelectorAll('.src-chips')).forEach(function(bar){
    var table=bar.parentElement.querySelector('table.sales-list:not(.by-day)');
    bar.addEventListener('click',function(e){
      var b=e.target.closest('.src-chip'); if(!b)return;
      [].slice.call(bar.children).forEach(function(c){c.classList.toggle('on',c===b)});
      var src=b.dataset.src;
      [].slice.call(table.tBodies[0].rows).forEach(function(r){r.style.display=(!src||r.dataset.src===src)?'':'none'});
    });
  });
  // Embedded dashboards (iframes): size each to its content whenever it is shown or resized.
  function fitFrames(){
    [].slice.call(document.querySelectorAll('iframe.embed')).forEach(function(f){
      if(f.offsetParent===null)return;
      try{var d=f.contentDocument; if(d&&d.documentElement){f.style.height=Math.max(480,d.documentElement.scrollHeight+4)+'px'}}catch(e){}
    });
  }
  [].slice.call(document.querySelectorAll('iframe.embed')).forEach(function(f){f.addEventListener('load',function(){fitFrames();setTimeout(fitFrames,400);setTimeout(fitFrames,1500)})});
  window.addEventListener('resize',fitFrames);
  function fitSoon(){fitFrames();setTimeout(fitFrames,150);setTimeout(fitFrames,700);setTimeout(fitFrames,2000)}
  show(start);
  window.addEventListener('hashchange',function(){var h=(location.hash||'').slice(1);if(tabs.some(function(t){return t.dataset.tab===h}))show(h)});

  // Collapsible blocks: a section.sales, or a card inside .tables, folds under its heading.
  function blocks(){return [].slice.call(document.querySelectorAll('section.sales, .tables > .card, .fold-block'))}
  blocks().forEach(function(b){
    var h=b.querySelector(':scope > h2'); if(!h)return;
    h.classList.add('fold'); h.tabIndex=0; h.setAttribute('role','button');
    var title=(h.textContent||'').trim().toLowerCase();
    if(/top referrers|signup forms|campaign sources|search landing pages|ai-assistant|lifetime/.test(title))b.classList.add('collapsed');
    function toggle(){b.classList.toggle('collapsed');h.setAttribute('aria-expanded',String(!b.classList.contains('collapsed')))}
    h.setAttribute('aria-expanded',String(!b.classList.contains('collapsed')));
    h.addEventListener('click',toggle);
    h.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();toggle()}});
  });
  document.getElementById('dash-expand').addEventListener('click',function(){blocks().forEach(function(b){b.classList.remove('collapsed')})});
  document.getElementById('dash-collapse').addEventListener('click',function(){blocks().forEach(function(b){if(b.querySelector(':scope > h2'))b.classList.add('collapsed')})});

  // Filter: searches every tab. Rows, tiles, notes and whole blocks that do not match are hidden.
  var wasTab=null;
  function items(){return [].slice.call(document.querySelectorAll('tr, .tile, .site-notes li, .obs li, .sales-chip'))}
  function clearFilter(){
    if(!filterEl)return; filterEl.value=''; apply();
  }
  function apply(){
    var q=(filterEl.value||'').trim().toLowerCase();
    document.querySelectorAll('.hidden-by-filter').forEach(function(e){e.classList.remove('hidden-by-filter')});
    [].slice.call(document.querySelectorAll('iframe.embed')).forEach(function(f){try{[].slice.call(f.contentDocument.querySelectorAll('tr, li')).forEach(function(it){it.style.display=''})}catch(e){}});
    if(!q){countEl.textContent=''; if(wasTab){show(wasTab);wasTab=null} return}
    if(!wasTab){wasTab=(tabs.filter(function(t){return t.classList.contains('on')})[0]||{dataset:{}}).dataset.tab||'overview'}
    show('all'); tabs.forEach(function(t){t.classList.remove('on')});
    var n=0;
    items().forEach(function(it){ if((it.textContent||'').toLowerCase().indexOf(q)<0)it.classList.add('hidden-by-filter'); else n++ });
    [].slice.call(document.querySelectorAll('iframe.embed')).forEach(function(f){
      f._hits=0;
      try{
        var d=f.contentDocument; if(!d)return;
        [].slice.call(d.querySelectorAll('tr, li')).forEach(function(it){
          if((it.textContent||'').toLowerCase().indexOf(q)<0)it.style.display='none'; else {it.style.display=''; n++; f._hits++}
        });
      }catch(e){}
    });
    blocks().concat([].slice.call(document.querySelectorAll('[data-panel]'))).forEach(function(b){
      var hit=[].slice.call(b.querySelectorAll('tr, .tile, .site-notes li, .obs li, .sales-chip')).some(function(x){return !x.classList.contains('hidden-by-filter')});
      if(!hit&&[].slice.call(b.querySelectorAll('iframe.embed')).some(function(f){return f._hits>0}))hit=true;
      var titleHit=((b.querySelector(':scope > h2')||{}).textContent||'').toLowerCase().indexOf(q)>=0;
      if(!hit&&!titleHit)b.classList.add('hidden-by-filter'); else b.classList.remove('collapsed');
    });
    fitSoon();
    countEl.textContent=n+(n===1?' match':' matches');
  }
  if(filterEl){filterEl.addEventListener('input',apply);
    filterEl.addEventListener('keydown',function(e){if(e.key==='Escape')clearFilter()});
    document.addEventListener('keydown',function(e){if(e.key==='/'&&document.activeElement!==filterEl&&!/INPUT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();filterEl.focus()}})}
})();
"""

THEME_JS = """
(function(){
  var b=document.getElementById('dash-theme'), root=document.documentElement; if(!b)return;
  function sync(){var light=root.getAttribute('data-theme')==='light';b.textContent=light?'Dark theme':'Light theme';b.setAttribute('aria-pressed',String(light))}
  b.addEventListener('click',function(){
    var light=root.getAttribute('data-theme')!=='light';
    if(light)root.setAttribute('data-theme','light');else root.removeAttribute('data-theme');
    try{localStorage.setItem('dash-theme',light?'light':'dark')}catch(e){}
    sync();
  });
  sync();
})();
"""

REV_CSS = """
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.rev-fig{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px 24px;margin:12px 0 4px}
.rev-stat b{display:block;font-size:1.3rem;font-weight:650;line-height:1.15;font-variant-numeric:tabular-nums}
.rev-stat span{display:block;font-size:.82rem;color:var(--muted);margin-top:2px}
.rev-stat em{display:block;font-style:normal;font-size:.78rem;color:var(--muted);margin-top:1px;font-variant-numeric:tabular-nums}
.rev-controls{display:flex;flex-direction:column;gap:8px;margin:14px 0 6px}
.rev-row{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center}
.rev-group{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.rev-lab{font-size:.78rem;color:var(--muted);margin-right:2px}
.rev-slider{display:flex;align-items:center;gap:8px;font-size:.78rem;color:var(--muted)}
.rev-slider input{width:96px;accent-color:var(--purple);margin:0;height:24px}
.rev-slider output{min-width:2.2em;color:var(--ink);font-variant-numeric:tabular-nums}
.rev-slider.off{opacity:.5}
.rev-plot{position:relative;margin-top:8px}
.rev-svg{display:block;width:100%;height:auto;overflow:visible;touch-action:pan-y}
.rev-svg:focus-visible{outline:2px solid var(--purple);outline-offset:4px;border-radius:6px}
.rv-grid{stroke:var(--line);stroke-width:1;opacity:.7}
.rv-axis{stroke:var(--muted);stroke-width:1;opacity:.6}
.rv-tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.rv-bar{fill:var(--purple)}
.rv-hatch-bg{fill:var(--est)}
.rv-hatch-ln{stroke:var(--purple);stroke-width:2.2}
.rv-today{stroke:var(--muted);stroke-width:1;stroke-dasharray:2 3}
.rv-guide{stroke:var(--ink);stroke-width:1;opacity:.35}
.rv-wk,.rv-mo,.rv-fc{fill:none;stroke-linejoin:round;stroke-linecap:round}
.rv-wk{stroke:var(--trend);stroke-width:2.25}
.rv-mo{stroke:var(--good);stroke-width:2}
.rv-fc{stroke:var(--ink);stroke-width:2;stroke-dasharray:6 4}
.rv-band{fill:var(--ink);opacity:.13}
.rev-legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin:8px 0 0}
.rev-legend-item i{width:12px;height:12px;border-radius:3px;display:inline-block}
.rev-legend-item i.rv-sw-bar{background:var(--purple)}
.rev-legend-item i.rv-sw-est{background:repeating-linear-gradient(45deg,var(--purple) 0 2px,var(--est) 2px 4px)}
.rev-legend-item i.rv-sw-wk{background:var(--trend);height:3px;border-radius:2px}
.rev-legend-item i.rv-sw-mo{background:var(--good);height:3px;border-radius:2px}
.rev-legend-item i.rv-sw-fc{background:none;border-top:2px dashed var(--ink);height:0;border-radius:0}
.rev-legend-item i.rv-sw-band{background:color-mix(in oklab,var(--ink) 18%,transparent)}
.rev-caption{margin:10px 0 0;font-size:.84rem;color:var(--muted);max-width:75ch}
.rev-tip{position:absolute;z-index:3;pointer-events:none;min-width:190px;max-width:260px;padding:10px 12px;
  background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:10px;font-size:.8rem;
  box-shadow:0 6px 24px oklch(0% 0 0 / .28)}
.rev-tip[hidden]{display:none}
.rev-tip strong{display:block;margin-bottom:4px;font-weight:650}
.rt-row{display:flex;justify-content:space-between;gap:14px;font-variant-numeric:tabular-nums}
.rt-row span{color:var(--muted)}
.rt-row b{font-weight:600;text-align:right}
.rt-total{border-top:1px solid var(--line);margin-top:3px;padding-top:3px}
.rt-total span{color:var(--ink)}
.rt-src{font-size:.76rem}
.rt-fc{border-top:1px solid var(--line);margin-top:6px;padding-top:6px}
.rt-note{color:var(--muted);font-size:.76rem;margin-top:2px}
@media (max-width:640px){
  .daily-revenue{display:flex;flex-direction:column}
  .daily-revenue > h2{order:0} .rev-fig{order:1} .rev-plot{order:2} .rev-legend{order:3} .rev-caption{order:4} .rev-controls{order:5;margin-top:16px}
  .rev-fig{grid-template-columns:repeat(2,minmax(0,1fr))}
  .rev-slider input{width:80px}
  .rev-sources .rev-group{flex-wrap:wrap;row-gap:8px;max-width:100%}
  .rev-sources .rev-lab{flex-basis:100%}
  .rev-sources .src-chip{flex:none}
}
"""

REV_JS = r"""
(function(){
  var dataEl=document.getElementById('rev-data'); if(!dataEl)return;
  var D=JSON.parse(dataEl.textContent), N=D.n, KEY='dash-rev', NS='http://www.w3.org/2000/svg';
  var plot=document.getElementById('rev-plot'), figEl=document.getElementById('rev-fig'),
      ctlEl=document.getElementById('rev-controls'), capEl=document.getElementById('rev-caption'),
      tip=document.getElementById('rev-tip'), live=document.getElementById('rev-live');
  var S={range:60,weekly:true,monthly:true,sigma:3,est:true,fc:true,hz:30,src:[]};
  try{var o=JSON.parse(localStorage.getItem(KEY)||'null'); if(o)for(var k in S)if(k in o)S[k]=o[k]}catch(e){}
  if([0,30,60,90].indexOf(S.range)<0)S.range=60;
  S.sigma=Math.min(7,Math.max(1,Math.round(+S.sigma)||3));
  if([14,30,60].indexOf(S.hz)<0)S.hz=30;
  S.src=(Array.isArray(S.src)?S.src:[]).filter(function(s){return D.sources[s]});
  function save(){try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}}

  var active=-1, geo=null, cache=null;
  function money(c,whole){var v=c/100,s=(whole?Math.round(v):v).toFixed(whole?0:2).replace(/\B(?=(\d{3})+(?!\d))/g,',');return '$'+s}
  function dayDate(i){var p=D.start.split('-');return new Date(+p[0],+p[1]-1,+p[2]+i)}
  var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], DOW=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  function lab(i){var d=dayDate(i);return MON[d.getMonth()]+' '+d.getDate()}
  function longLab(i){var d=dayDate(i);return DOW[d.getDay()]+' '+MON[d.getMonth()]+' '+d.getDate()}

  // ---- series for the current selection (all in cents)
  function series(){
    var names=S.src.length?S.src:D.order, r=new Array(N).fill(0), e=new Array(N).fill(0), i;
    names.forEach(function(k){var s=D.sources[k];for(i=0;i<N;i++){r[i]+=s.r[i];e[i]+=s.e[i]}});
    var t=r.map(function(v,j){return v+(S.est?e[j]:0)});
    return {r:r,e:S.est?e:new Array(N).fill(0),t:t};
  }
  // Gaussian-weighted centred mean over complete days (today is still running). Edges average what exists, 4 days minimum.
  function gauss(t,sigma){
    var half=Math.max(2,Math.round(7/3*sigma)), w=[], k, i, M=N-1, out=new Array(N).fill(null);
    for(k=-half;k<=half;k++)w.push(Math.exp(-0.5*k*k/(sigma*sigma)));
    for(i=0;i<M;i++){
      var sw=0,sv=0,c=0;
      for(k=-half;k<=half;k++){var j=i+k;if(j<0||j>=M)continue;sw+=w[k+half];sv+=w[k+half]*t[j];c++}
      if(c>=4)out[i]=sv/sw;
    }
    return out;
  }
  function trailing(t,n){
    var out=new Array(N).fill(null),M=N-1,i,s=0;
    for(i=0;i<M;i++){s+=t[i];if(i>=n)s-=t[i-n];if(i>=n-1)out[i]=s/n}
    return out;
  }
  function fcActive(){return S.fc&&!S.src.length&&D.forecast&&D.forecast[S.est?'all':'received']}

  // ---- controls
  function btn(text,pressed,fn,extra){
    var b=document.createElement('button');b.type='button';b.className='src-chip'+(extra?' '+extra:'');
    b.textContent=text;b.setAttribute('aria-pressed',String(!!pressed));if(pressed)b.classList.add('on');
    b.addEventListener('click',fn);return b;
  }
  function group(label,nodes){
    var g=document.createElement('div');g.className='rev-group';g.setAttribute('role','group');g.setAttribute('aria-label',label);
    var l=document.createElement('span');l.className='rev-lab';l.textContent=label;g.appendChild(l);
    nodes.forEach(function(n){g.appendChild(n)});return g;
  }
  var sigmaOut=null,sigmaIn=null;
  function buildControls(){
    ctlEl.textContent='';
    var row=document.createElement('div');row.className='rev-row';
    var maxDays=N;
    row.appendChild(group('Range',[[30,'30 days'],[60,'60 days'],[90,'90 days'],[0,'All ('+maxDays+')']].map(function(p){
      return btn(p[1],S.range===p[0],function(){S.range=p[0];refresh()});})));
    row.appendChild(group('Include',[btn('Estimates',S.est,function(){S.est=!S.est;refresh()})]));
    var lines=[btn('Weekly trend',S.weekly,function(){S.weekly=!S.weekly;refresh()}),
               btn('30-day average',S.monthly,function(){S.monthly=!S.monthly;refresh()})];
    row.appendChild(group('Lines',lines));
    var sg=document.createElement('label');sg.className='rev-slider';
    var st=document.createElement('span');st.textContent='Smoothing';sg.appendChild(st);
    sigmaIn=document.createElement('input');sigmaIn.type='range';sigmaIn.min='1';sigmaIn.max='7';sigmaIn.step='1';sigmaIn.value=S.sigma;
    sigmaIn.setAttribute('aria-label','Weekly trend smoothing, standard deviation in days');
    sigmaOut=document.createElement('output');sigmaOut.textContent=S.sigma+' d';
    sigmaIn.addEventListener('input',function(){S.sigma=+sigmaIn.value;refresh()});
    sg.appendChild(sigmaIn);sg.appendChild(sigmaOut);row.appendChild(sg);
    var fcs=[btn('Forecast',S.fc,function(){S.fc=!S.fc;refresh()})];
    [14,30,60].forEach(function(h){fcs.push(btn(h+' d',S.hz===h,function(){S.hz=h;S.fc=true;refresh()},'hz'))});
    row.appendChild(group('Forecast',fcs));
    ctlEl.appendChild(row);
    var chips=document.createElement('div');chips.className='rev-row rev-sources';
    var sgp=document.createElement('div');sgp.className='rev-group';sgp.setAttribute('role','group');sgp.setAttribute('aria-label','Sources');
    var sl=document.createElement('span');sl.className='rev-lab';sl.textContent='Sources';sgp.appendChild(sl);
    sgp.appendChild(btn('All',!S.src.length,function(){S.src=[];refresh()},'src-all'));
    D.order.forEach(function(name){
      sgp.appendChild(btn(name,S.src.indexOf(name)>=0,function(){
        var i=S.src.indexOf(name);if(i>=0)S.src.splice(i,1);else S.src.push(name);
        if(S.src.length===D.order.length)S.src=[];refresh()},'src'));
    });
    chips.appendChild(sgp);ctlEl.appendChild(chips);
  }
  function syncControls(){
    var bs=ctlEl.querySelectorAll('button'),idx=0;
    // order: 4 range, estimates, 2 lines, forecast, 3 horizons, then All + sources
    var ranges=[30,60,90,0],on=[];
    ranges.forEach(function(r){on.push(S.range===r)});
    on.push(S.est,S.weekly,S.monthly,S.fc,S.hz===14,S.hz===30,S.hz===60,!S.src.length);
    D.order.forEach(function(n){on.push(S.src.indexOf(n)>=0)});
    for(idx=0;idx<bs.length;idx++){bs[idx].classList.toggle('on',!!on[idx]);bs[idx].setAttribute('aria-pressed',String(!!on[idx]))}
    sigmaIn.value=S.sigma;sigmaOut.textContent=S.sigma+' d';sigmaIn.disabled=!S.weekly;
    sigmaIn.parentNode.classList.toggle('off',!S.weekly);
    [].forEach.call(ctlEl.querySelectorAll('.hz'),function(b){b.disabled=false});
  }

  // ---- figures
  function figures(se){
    var i0=S.range?Math.max(0,N-S.range):0, n=N-i0, tot=0,est=0,i;
    for(i=i0;i<N;i++){tot+=se.t[i];est+=se.e[i]}
    var wk=0;for(i=Math.max(0,N-7);i<N;i++)wk+=se.t[i];
    var share=tot>0&&est>0?' &middot; '+money(est)+' estimated ('+Math.round(100*est/tot)+'%)':'';
    var label=S.range?'Last '+n+' days':'All '+n+' days';
    var items=[[money(se.t[N-1]),'Today so far',''],[money(wk),'Last 7 days',''],[money(tot),label,share],[money(Math.round(tot/n)),'Per day, '+(S.range?'last '+n:'all')+' days','']];
    figEl.innerHTML=items.map(function(x){return '<div class="rev-stat"><b>'+x[0]+'</b><span>'+x[1]+'</span>'+(x[2]?'<em>'+x[2].replace(/^ &middot; /,'')+'</em>':'')+'</div>'}).join('');
  }

  // ---- chart
  function nice(max){
    if(max<=0)return {top:100,step:25};
    var raw=max/4,mag=Math.pow(10,Math.floor(Math.log10(raw))),f=raw/mag,s=f<=1?1:f<=2?2:f<=2.5?2.5:f<=5?5:10;
    var step=s*mag;return {top:Math.ceil(max/step)*step,step:step};
  }
  function el(tag,attrs,parent){
    var e=document.createElementNS(NS,tag);for(var k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e;
  }
  function draw(){
    var W=plot.clientWidth; if(W<40)return;
    var se=series(), F=fcActive(), hz=F?S.hz:0, i0=S.range?Math.max(0,N-S.range):0;
    var cols=N-i0+(hz?hz-1:0), H=W<520?230:290, ml=W<520?38:46, mr=8, mt=18, mb=24;
    var pw=W-ml-mr, ph=H-mt-mb, cw=pw/cols, i, j;
    var wk=S.weekly?gauss(se.t,S.sigma):null, mo=S.monthly?trailing(se.t,30):null;
    var max=0;
    for(i=i0;i<N;i++){max=Math.max(max,se.t[i]);if(wk&&wk[i]!=null)max=Math.max(max,wk[i]);if(mo&&mo[i]!=null)max=Math.max(max,mo[i])}
    if(hz)for(j=0;j<hz;j++)max=Math.max(max,F.hi[j]);
    var ax=nice(max*1.04);
    function X(idx){return ml+(idx-i0+0.5)*cw}
    function Y(v){return mt+ph*(1-v/ax.top)}
    plot.querySelectorAll('svg').forEach(function(s){s.remove()});
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H,width:W,height:H,class:'rev-svg',tabindex:'0',role:'img',
      'aria-label':'Revenue per day chart. Use the left and right arrow keys to read each day.'},null);
    // grid + y labels
    for(var v=0;v<=ax.top+1e-6;v+=ax.step){
      var y=Y(v);el('line',{x1:ml,x2:W-mr,y1:y,y2:y,class:v===0?'rv-axis':'rv-grid'},svg);
      var t=el('text',{x:ml-6,y:y+4,class:'rv-tick','text-anchor':'end'},svg);t.textContent=money(v,ax.step%100===0);
    }
    // x labels on Mondays, spaced at least ~64px
    var step=Math.max(1,Math.ceil(64/(7*cw))),mcount=0;
    for(i=i0;i<i0+cols;i++){
      if(dayDate(i).getDay()!==1)continue;
      if((mcount++)%step)continue;
      var tx=el('text',{x:X(i),y:H-7,class:'rv-tick','text-anchor':'middle'},svg);tx.textContent=lab(i);
    }
    // bars; estimates are hatched so they never read as cash
    var defs=el('defs',{},svg),pt=el('pattern',{id:'rv-hatch',width:4,height:4,patternUnits:'userSpaceOnUse',patternTransform:'rotate(45)'},defs);
    el('rect',{width:4,height:4,class:'rv-hatch-bg'},pt);el('line',{x1:0,y1:0,x2:0,y2:4,class:'rv-hatch-ln'},pt);
    var bw=Math.max(1,cw-(cw>5?1.5:0.5)), bg=el('g',{},svg);
    for(i=i0;i<N;i++){
      var r=se.r[i],e=se.e[i];if(!r&&!e)continue;
      var yr=Y(r),ye=Y(r+e);
      if(r)el('rect',{x:X(i)-bw/2,y:yr,width:bw,height:Math.max(0.5,Y(0)-yr),class:'rv-bar'},bg);
      if(e)el('rect',{x:X(i)-bw/2,y:ye,width:bw,height:Math.max(0.5,yr-ye),class:'rv-est',fill:'url(#rv-hatch)'},bg);
    }
    // today divider
    var tdx=ml+(N-1-i0)*cw;
    el('line',{x1:tdx,x2:tdx,y1:mt-4,y2:mt+ph,class:'rv-today'},svg);
    var tt=el('text',{x:tdx+(hz?4:-4),y:mt-6,class:'rv-tick','text-anchor':hz?'start':'end'},svg);tt.textContent='today';
    // forecast band + line
    if(hz){
      var up=[],dn=[];
      for(j=0;j<hz;j++){var xx=X(N-1+j);up.push(xx.toFixed(1)+','+Y(F.hi[j]).toFixed(1));dn.unshift(xx.toFixed(1)+','+Y(F.lo[j]).toFixed(1))}
      el('polygon',{points:up.concat(dn).join(' '),class:'rv-band'},svg);
      var pts=[];for(j=0;j<hz;j++)pts.push(X(N-1+j).toFixed(1)+','+Y(F.fc[j]).toFixed(1));
      el('polyline',{points:pts.join(' '),class:'rv-fc'},svg);
    }
    function line(arr,cls){
      var seg=[],all=[];
      for(i=i0;i<N;i++){if(arr[i]==null){if(seg.length)all.push(seg);seg=[];continue}seg.push(X(i).toFixed(1)+','+Y(arr[i]).toFixed(1))}
      if(seg.length)all.push(seg);
      all.forEach(function(s){if(s.length>1)el('polyline',{points:s.join(' '),class:cls},svg)});
    }
    if(mo)line(mo,'rv-mo');
    if(wk)line(wk,'rv-wk');
    var guide=el('line',{x1:0,x2:0,y1:mt,y2:mt+ph,class:'rv-guide',visibility:'hidden'},svg);
    plot.insertBefore(svg,tip);
    geo={W:W,H:H,ml:ml,cw:cw,mt:mt,ph:ph,i0:i0,cols:cols,hz:hz,F:F,se:se,guide:guide,svg:svg,X:X,wk:wk,mo:mo};
    bindSvg(svg);
    if(active>=i0&&active<i0+cols)showDay(active,false);else hideTip();
    legend(F);
  }
  function legend(F){
    var items=[['rv-sw-bar','Sold or received']];
    if(S.est)items.push(['rv-sw-est','Estimated']);
    if(S.weekly)items.push(['rv-sw-wk','Weekly trend']);
    if(S.monthly)items.push(['rv-sw-mo','30-day average']);
    if(F)items.push(['rv-sw-fc','Forecast'],['rv-sw-band','80% range of the 7-day average']);
    var lg=document.getElementById('rev-legend');
    if(!lg){lg=document.createElement('div');lg.id='rev-legend';lg.className='rev-legend';capEl.parentNode.insertBefore(lg,capEl)}
    lg.innerHTML=items.map(function(x){return '<span class="rev-legend-item"><i class="'+x[0]+'"></i>'+x[1]+'</span>'}).join('');
  }
  function caption(){
    var F=D.forecast&&D.forecast[S.est?'all':'received'], msg='';
    if(!S.fc)msg='';
    else if(S.src.length)msg='The forecast covers all sources. Select All sources to see it.';
    else if(!F)msg='The forecast needs at least 21 days of history.';
    else msg='Forecast: '+F.model+', the best of the backtest (its 7-day total was off by '+money(F.mae,true)+' on average over the last 28 days). '+
      'Next 30 days: '+money(F.total30,true)+', 80% range '+money(F.total30_lo,true)+' to '+money(F.total30_hi,true)+'.';
    capEl.textContent=msg;capEl.hidden=!msg;
  }

  // ---- tooltip / keyboard
  function dayText(i){
    var names=S.src.length?S.src:D.order,parts=[],se=geo.se,lines=[];
    names.forEach(function(k){var s=D.sources[k],r=s.r[i],e=S.est?s.e[i]:0;if(r||e)parts.push([k,r,e])});
    parts.sort(function(a,b){return (b[1]+b[2])-(a[1]+a[2])});
    return {title:longLab(i),r:se.r[i],e:se.e[i],t:se.t[i],parts:parts};
  }
  function showDay(i,fromKey){
    if(!geo)return; active=i;
    var x=geo.X(i),h='',txt;
    if(i<N){
      var d=dayText(i);
      h='<strong>'+d.title+(i===N-1?' (today so far)':'')+'</strong><div class="rt-row"><span>Sold or received</span><b>'+money(d.r)+'</b></div>'+
        (S.est?'<div class="rt-row"><span>Estimated</span><b>'+money(d.e)+'</b></div>':'')+
        '<div class="rt-row rt-total"><span>Day total</span><b>'+money(d.t)+'</b></div>'+
        d.parts.map(function(p){return '<div class="rt-row rt-src"><span>'+esc(p[0])+'</span><b>'+(p[2]&&!p[1]?'~':'')+money(p[1]+p[2])+'</b></div>'}).join('');
      txt=d.title+': '+money(d.t)+' total, '+money(d.r)+' sold or received'+(S.est?', '+money(d.e)+' estimated':'')+'.';
    }
    if(geo.hz&&i>=N-1){
      var j=i-(N-1),F=geo.F;
      h+=(i<N?'<div class="rt-fc">':'<strong>'+longLab(i)+'</strong><div class="rt-fc">')+'<div class="rt-row"><span>Forecast</span><b>'+money(F.fc[j])+'</b></div>'+
         '<div class="rt-note">7-day average, 80% range: '+money(F.lo[j])+' to '+money(F.hi[j])+'</div></div>';
      txt=(txt?txt+' ':longLab(i)+': ')+'Forecast '+money(F.fc[j])+' a day, range '+money(F.lo[j])+' to '+money(F.hi[j])+'.';
    }
    tip.innerHTML=h;tip.hidden=false;
    geo.guide.setAttribute('x1',x);geo.guide.setAttribute('x2',x);geo.guide.setAttribute('visibility','visible');
    var tw=tip.offsetWidth,th=tip.offsetHeight,left=x+12;
    if(left+tw>geo.W)left=x-tw-12; if(left<0)left=0;
    tip.style.left=left+'px'; tip.style.top=Math.max(0,Math.min(geo.mt+4,geo.H-th))+'px';
    if(fromKey)live.textContent=txt;
  }
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function hideTip(){active=-1;tip.hidden=true;if(geo)geo.guide.setAttribute('visibility','hidden')}
  function bindSvg(svg){
    function idxAt(ev){
      var r=svg.getBoundingClientRect(),x=ev.clientX-r.left-geo.ml,i=geo.i0+Math.floor(x/geo.cw);
      return (x<0||i>=geo.i0+geo.cols)?-1:i;
    }
    svg.addEventListener('pointermove',function(ev){var i=idxAt(ev);if(i<0)hideTip();else showDay(i,false)});
    svg.addEventListener('pointerdown',function(ev){var i=idxAt(ev);if(i>=0)showDay(i,false)});
    svg.addEventListener('pointerleave',function(ev){if(ev.pointerType!=='touch'&&document.activeElement!==svg)hideTip()});
    svg.addEventListener('blur',hideTip);
    svg.addEventListener('keydown',function(ev){
      var last=geo.i0+geo.cols-1,cur=active<0?N-1:active,n=cur;
      if(ev.key==='ArrowLeft')n=cur-1;else if(ev.key==='ArrowRight')n=cur+1;
      else if(ev.key==='Home')n=geo.i0;else if(ev.key==='End')n=last;
      else if(ev.key==='Escape'){hideTip();return}else return;
      ev.preventDefault();n=Math.max(geo.i0,Math.min(last,n));showDay(n,true);
    });
    svg.addEventListener('focus',function(){if(active<0)showDay(N-1,true)});
  }

  function refresh(){save();syncControls();var se=series();figures(se);caption();draw()}
  buildControls();refresh();
  if(window.ResizeObserver){var ro=new ResizeObserver(function(){draw()});ro.observe(plot)}else window.addEventListener('resize',draw);
})();
"""

_RESTATES_CARD = re.compile(
    r"^(?:[\d,]+|zero) [^.]*? in the last 7 days\.$|^[\d,]+ checkout click\(s\) from |^ModernTex trial funnel \(last |"
    r"^[\d,]+ (?:pageviews in the last 7 days|tool runs in the last 7 days|calculator runs in the last 7 days|"
    r"Vitae downloads in the last 7 days|checkout clicks in the last 7 days|trial downloads in the last 7 days|"
    r"ModernTex release-notes signups in the last 7 days|subscribes in the last 7 days|"
    r"[A-Za-z ]+ signups in the last 7 days)", re.I)


def split_notes(summaries: list[dict], obs: list[str]) -> tuple[dict, list[str]]:
    """Group the observation lines by site, drop the ones that only repeat a number the
    site card already shows, and set aside the "excluded our own test clicks" footnotes.
    Returns ({label: {"notes": [...], "footnotes": [...]}}, [lines about no single site])."""
    labels = [s["label"] for s in summaries]
    per = {l: {"notes": [], "footnotes": []} for l in labels}
    general: list[str] = []
    for o in obs:
        site, _, rest = o.partition(": ")
        if site in per and rest:
            if "excluded above" in rest or "were ours and are excluded" in rest:
                per[site]["footnotes"].append(rest)
            elif _RESTATES_CARD.match(rest):
                continue
            else:
                per[site]["notes"].append(rest)
        else:
            general.append(o)
    return per, general


def glance_table(summaries: list[dict]) -> str:
    rows = ""
    for s in summaries:
        d = s["delta_pct"]
        delta = "" if d is None else (f"+{d}%" if d > 0 else f"{d}%")
        rows += (f"<tr><td>{html.escape(s['label'])}</td><td class='num'>{s['last7']}</td>"
                 f"<td class='num'>{delta}</td><td class='num'>{s['today']}</td>"
                 f"<td class='num'>{s['uniques7']}</td><td class='num'>{s['last30']}</td></tr>")
    return ("<section class='sales'><h2>Traffic at a glance</h2><table class='glance'><thead><tr><th>Site</th>"
            "<th class='num'>Pageviews 7d</th><th class='num'>vs prior 7d</th><th class='num'>Today</th>"
            "<th class='num'>Visitors 7d</th><th class='num'>Pageviews 30d</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></section>")


def notes_block(label: str, notes: list[str], footnotes: list[str]) -> str:
    if not notes and not footnotes:
        return ""
    li = "".join(f"<li>{html.escape(n)}</li>" for n in notes) or "<li>Nothing beyond the numbers above.</li>"
    foot = ""
    if footnotes:
        foot = ("<details><summary>Data notes (test traffic excluded)</summary><ul>"
                + "".join(f"<li>{html.escape(n)}</li>" for n in footnotes) + "</ul></details>")
    return f"<section class='site-notes'><h2>What this says</h2><ul>{li}</ul>{foot}</section>"



# The photography and TikTok arms keep their own dashboards (written by their own jobs). They
# are folded in as tabs here, each inside an iframe built from the file's current contents, so
# their CSS and scripts cannot touch this page and no web server is needed to view them.
EMBEDS = [
    ("photography", "Photography",
     Path("/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace/analytics/dashboard.html")),
    ("tiktok", "TikTok",
     Path("/Volumes/Extreme SSD/TikTokPipeline/analytics/dashboard.html")),
]


def embed_panel(label: str, path: Path) -> str:
    try:
        doc = path.read_text(encoding="utf-8", errors="replace")
        stamp = dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%a %d %b %Y, %-I:%M%p").replace("AM", "am").replace("PM", "pm")
    except OSError:
        return (f"<section class='site-notes'><h2>{html.escape(label)}</h2><p>Dashboard file not found: "
                f"<code>{html.escape(str(path))}</code>. It is written by that arm's own job.</p></section>")
    link = html.escape("file://" + str(path).replace(" ", "%20"))
    return (f"<p class='embed-meta'>Snapshot of <code>{html.escape(str(path))}</code>, written {html.escape(stamp)}. "
            f"That job refreshes it on its own schedule; this tab picks up the newest copy each time this page is built. "
            f"<a href=\"{link}\">Open on its own</a></p>"
            f"<iframe class='embed' title=\"{html.escape(label)} dashboard\" loading='eager' "
            f"sandbox='allow-scripts allow-same-origin allow-popups' srcdoc=\"{html.escape(doc, quote=True)}\"></iframe>")


def render(summaries: list[dict], obs: list[str], generated: str, first_day: str | None,
           sales: dict | None = None, appstore: dict | None = None,
           manual_ads: dict | None = None, chrome_web_store: dict | None = None,
           admob: dict | None = None, metrics: dict | None = None,
           profit: dict | None = None, channels: dict | None = None, tax: dict | None = None,
           marketplaces: dict | None = None, market_rows: list[dict] | None = None,
           ledger_rows: list[dict] | None = None, revenue_daily: dict | None = None) -> str:
    cards = "".join(site_card(s) for s in summaries)
    obs_html = "".join(f"<li>{html.escape(o)}</li>" for o in obs) or "<li>No data yet.</li>"

    site_tables: dict[str, str] = {}
    for s in summaries:
        tables = ""
        # Everything below the Conversion card comes from the live payload,
        # which is a 30-day window — say so, rather than letting it sit next to
        # 7-day headline numbers looking like the same period.
        tables += (f"<h2>{html.escape(s['label'])} — detail "
                   f"<span class='win'>· last {FETCH_DAYS} days</span></h2><div class='tables'>")
        tables += funnel(s)
        tables += table("Channels", s["channels"], "No traffic recorded in this window.")
        tables += ai_trend_card(s.get("ai_trend") or [])
        if s.get("gsc"):
            tables += gsc_card(s["gsc"])
            tables += gsc_table("Search queries (natural language)" if s["gsc"].get("split") else "Search queries",
                                s["gsc"]["queries"],
                                "No queries returned for this window.")
            tables += gsc_table("Search landing pages", s["gsc"]["pages"],
                                "No pages returned for this window.")
        tables += audience_card(s.get("audience"))
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
        if any(k.endswith("Signups") for k in sec_keys) or s["form_breakdown"]:
            tables += table("Signup forms (all-time)", s["form_breakdown"], "None yet.")
        if s["top_utm"] and not (s["tool_runs"] or s["calc_runs"]):
            tables += table("Campaign sources", s["top_utm"], "None recorded.")
        tables += "</div>"
        site_tables[s["label"]] = tables

    since = f" Tracking since {first_day}." if first_day else ""
    per_site, general = split_notes(summaries, obs)
    general = [g for g in general if "Too new for a rate yet" not in g]
    general_html = ("<section class='site-notes'><h2>Other notes</h2><ul>"
                    + "".join(f"<li>{html.escape(g)}</li>" for g in general) + "</ul></section>") if general else ""
    overview = (f"{daily_revenue_block(revenue_daily)}\n"
                f"{revenue_block(sales, appstore, market_rows=market_rows, admob=admob)}\n{metrics_block(metrics)}\n"
                f"{profit_block(profit, channels, tax)}\n{glance_table(summaries)}\n"
                f"{queue_block()}\n{general_html}")
    money = f"{all_sales_block(ledger_rows or [], appstore, admob)}\n{sales_block(sales)}\n{marketplaces_block(marketplaces)}"
    ads = manual_ads_block(manual_ads or {}, admob)
    apps = f"{appstore_block(appstore)}\n{chrome_web_store_block(chrome_web_store)}"
    panels = [("overview", "Overview", overview), ("money", "Money", money), ("ads", "Ads", ads), ("apps", "Apps", apps)]
    for s_ in summaries:
        key = "site-" + re.sub(r"[^a-z0-9]+", "-", s_["label"].lower()).strip("-")
        n = per_site.get(s_["label"], {"notes": [], "footnotes": []})
        body = (f"<div class='grid'>{site_card(s_)}</div>"
                f"{notes_block(s_['label'], n['notes'], n['footnotes'])}"
                f"{site_tables[s_['label']]}")
        panels.append((key, s_["label"], body))
    for k_, t_, path_ in EMBEDS:
        panels.append((k_, t_, embed_panel(t_, path_)))
    tabs_html = "".join(f"<a class='tab' href='#{k}' data-tab='{k}'>{html.escape(t)}</a>" for k, t, _ in panels)
    tabs_html += "<a class='tab' href='#all' data-tab='all'>Everything</a>"
    panels_html = "".join(
        f"<div data-panel='{k}'><h2 class='panel-title'>{html.escape(t)}</h2>{body}</div>" for k, t, body in panels)

    since = f" Tracking since {first_day}." if first_day else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Purplelink dashboard</title>
<script>try{{if(localStorage.getItem('dash-theme')==='light')document.documentElement.setAttribute('data-theme','light')}}catch(e){{}}</script>
<style>{CSS}{NAV_CSS}{REV_CSS}</style></head>
<body><div class="wrap">
<header>
  <div class="head-title">
    <h1>Dashboard</h1>
    <p class="stamp">Updated {html.escape(generated)} · refreshes daily from 7:00am</p>
  </div>
  <div class="tools">
    <input id="dash-filter" type="search" placeholder="Filter (press /)" aria-label="Filter the dashboard" autocomplete="off">
    <span id="dash-count" class="count" role="status" aria-live="polite"></span>
    <button type="button" id="dash-expand">Expand all</button>
    <button type="button" id="dash-collapse">Collapse all</button>
    <button type="button" id="dash-theme" aria-pressed="false">Light theme</button>
  </div>
</header>
<nav class="topnav" aria-label="Dashboard sections">
  <div class="tabs">{tabs_html}</div>
</nav>
{panels_html}
<footer>
  First-party, cookieless analytics from each site's own beacon — no third-party
  vendor, Do Not Track honoured, so these counts are conservative and exclude
  visitors who opt out.{html.escape(since)}
  Daily figures are archived to <code>~/.purplelink/traffic/history.json</code>,
  which keeps growing even if the source window rolls off.
</footer>
</div><script>{NAV_JS}{THEME_JS}{REV_JS}</script></body></html>"""


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
        # State before this run, for the event feed (what changed since last time).
        prev_app_days = json.loads(json.dumps((history.get("appstore") or {}).get("days", {})))
        prev_subs = (history.get("sales") or {}).get("subscriptions")
        new_events: list[dict] = []

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

                # Fold each live Netlify Forms signup funnel into the same
                # per-day shape the stats endpoint returns, one metric per
                # product (SITES[*]["signup_forms"]) rather than one blended
                # total — so a product's own secondary line picks it up like
                # any beacon-sourced counter, and a retired form reading zero
                # doesn't hide a live one that's actually converting.
                forms_note = ""
                signup_forms = site.get("signup_forms", {})
                if site.get("netlify_site_id"):
                    nt = _netlify_token()
                    if nt:
                        try:
                            by_form_day, per_form = fetch_form_signups(site["netlify_site_id"], nt)
                            payload.setdefault("byDay", {})
                            noted = []
                            for form_name, metric_key in signup_forms.items():
                                form_days = by_form_day.get(form_name, {})
                                for day, n in form_days.items():
                                    payload["byDay"].setdefault(day, {})[metric_key] = n
                                if form_days:
                                    noted.append(f"{sum(form_days.values())} {form_name}")
                            payload["formBreakdown"] = per_form
                            payload["signupMetricKeys"] = list(signup_forms.values())
                            if noted:
                                forms_note = ", " + ", ".join(noted) + " signup(s)"
                        except Exception as exc:
                            print(f"  ! {site['label']}: form fetch failed ({str(exc)[:60]})",
                                  file=sys.stderr)
                    else:
                        print(f"  ! {site['label']}: no Netlify token; skipping waitlists",
                              file=sys.stderr)

                if site["key"] == "purplelink":
                    try:
                        week = fetch_site(site, token, AD_FUNNEL_DAYS)
                        if week.get("funnelByChannel") is not None:
                            history["adFunnel"] = {"asOf": dt.date.today().isoformat(), "days": AD_FUNNEL_DAYS,
                                                   "channels": week["funnelByChannel"]}
                    except Exception as exc:
                        print(f"  ! {site['label']}: channel funnel fetch failed ({str(exc)[:60]})", file=sys.stderr)
                    vt = cfg.get(VITAE_STATS_TOKEN_ENV)
                    vd = fetch_vitae_downloads(vt) if vt else fetch_vitae_downloads_blobs()
                    if vd is not None:
                        payload.setdefault("byDay", {})
                        for day, n in vd["byDay"].items():
                            payload["byDay"].setdefault(day, {})["vitaeDownloads"] = n
                        ours = sum(e["count"] for (sk, m, _d), e in SYNTHETIC_EVENTS.items()
                                   if sk == "purplelink" and m == "vitaeDownloads")
                        lifetime = max(0, sum(vd["downloads"].values()) - ours)
                        forms_note += f", {lifetime} Vitae download(s) lifetime"

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
                    mob = (gsc.get("devices") or {}).get("mobile", {})
                    sp = gsc.get("split") or {}
                    print(f"     search: {gsc['clicks']} clicks, "
                          f"{gsc['impressions']} impressions, pos {gsc['position']:.1f}")
                    if sp:
                        print(f"     search (readers): mobile {mob.get('impressions', 0)} impr / "
                              f"{mob.get('clicks', 0)} clicks; natural queries "
                              f"{sp['natural']['impressions']} impr, "
                              f"{sp['natural']['top10_impressions']} at pos<=10; "
                              f"operator-style {sp['operator']['impressions']} impr")
                elif gsc:
                    print(f"  ! {site['label']}: Search Console unavailable "
                          f"({gsc['error'][:80]})", file=sys.stderr)
            except (OSError, http.client.HTTPException, RuntimeError, ValueError) as exc:
                entry["error"] = str(exc)[:120]
                print(f"  ! {site['label']} fetch failed: {exc}", file=sys.stderr)

        # Sales come from Stripe, not from either site's beacon, so they are
        # fetched once for both. Archived like the rest so a --no-fetch
        # re-render still shows the last known revenue instead of a blank panel.
        sales_token = cfg.get(SALES_TOKEN_ENV)
        if sales_token:
            sales = fetch_sales(sales_token)
            if sales:
                new_events += merge_ledger(history, sales) or []
                new_events += subscription_events(prev_subs, sales.get("subscriptions"))
                if sales.get("subscriptions") is not None:
                    s_ = sales["subscriptions"]
                    history.setdefault("subsDaily", {})[dt.date.today().isoformat()] = {
                        "mrr": s_.get("mrr", 0), "active": s_.get("active", 0),
                        "trialing": s_.get("trialing", 0)}
                history["sales"] = sales
                w, a = sales.get("window", {}), sales.get("allTime", {})
                print(f"  ok Sales: {money(w.get('gross', 0))} in {w.get('days', FETCH_DAYS)}d "
                      f"({orders(w.get('orders', 0))}), {money(a.get('gross', 0))} all time")
        else:
            print(f"  ! sales: {SALES_TOKEN_ENV} not set in {CONFIG_PATH}", file=sys.stderr)

        # ModernTex in-app updates (Sparkle): existing owners updating, not new
        # customers — kept separate from the sales/trial numbers above.
        sparkle_token = cfg.get(MODERNTEX_UPDATE_TOKEN_ENV)
        by_file = fetch_sparkle_updates(sparkle_token) if sparkle_token else fetch_sparkle_updates_blobs()
        if by_file is not None:
            sparkle_hist = merge_sparkle_updates(history, by_file)
            today = sparkle_hist["today"]
            delta_note = f", {today['delta']} today" if today["delta"] is not None else " (first snapshot)"
            print(f"  ok ModernTex in-app updates: {today['total']} lifetime{delta_note}")

        # MacUpdate listings: their own download counter (they serve a mirrored copy we never see).
        for mu_key, mu_url in MACUPDATE_LISTINGS.items():
            reading = fetch_macupdate(mu_url)
            if reading is not None:
                merge_macupdate(history, mu_key, reading)
                print(f"  ok MacUpdate {mu_key}: {reading['downloads']} downloads all time, listing shows {reading['version']}")

        # Panely and Summonly: downloads served (public and buyer) and in-app updates by version.
        for app_key in APP_STATS_STORES:
            app_entry = fetch_app_stats_blobs(app_key)
            if app_entry is not None:
                history.setdefault("appStats", {})[app_key] = app_entry
                sm_ = app_stats_summary(app_entry)
                print(f"  ok {app_key.title()} downloads: {sm_['publicAll']} public, {sm_['buyerAll']} buyer, "
                      f"{sm_['updatesAll']} in-app update(s)")

        # App Store Connect (GlobePin): archived per day like everything else.
        if cfg.get("ASC_VENDOR_NUMBER"):
            try:
                app = fetch_appstore(cfg, history.get("appstore"))
            except Exception as exc:  # noqa: BLE001 — never let Apple sink the run
                print(f"  ! appstore unavailable: {str(exc)[:100]}", file=sys.stderr)
                app = None
            if app:
                new_events += appstore_events(prev_app_days, app.get("days", {}))
                history["appstore"] = app
                sm = appstore_summary(app)
                print(f"  ok App Store ({app['label']}): {sm['w7']['downloads']} downloads in 7d, "
                      f"{sm['allTime']['downloads']} since launch, {sm['allTime']['proUnits']} paid Pro"
                      f"{' (' + str(app['fetchedDays']) + ' day(s) fetched)' if app.get('fetchedDays') else ''}")

        # AdMob (GlobePin in-app ad earnings): no auth setup means no card,
        # same degrade-quietly contract as everything else here.
        try:
            admob = fetch_admob("globepin")
        except Exception as exc:  # noqa: BLE001 — never let this sink the run
            print(f"  ! admob unavailable: {str(exc)[:100]}", file=sys.stderr)
            admob = None
        if admob:
            history.setdefault("admob", {})["globepin"] = admob
            if admob.get("error"):
                print(f"  ! AdMob (GlobePin): {admob['error']}", file=sys.stderr)
            else:
                print(f"  ok AdMob (GlobePin): ${admob['earnings']:.2f} earned in {admob['days']}d, "
                      f"{admob['impressions']:,} impressions")

        # Costs for the profit view: Modal compute per app, and the Claude API
        # cost of each paid job from the backend's usage ledger.
        mc = fetch_modal_costs()
        if mc and not mc.get("error"):
            history["modalCosts"] = mc
            wk = (dt.date.today() - dt.timedelta(days=PROFIT_DAYS)).isoformat()
            print(f"  ok Modal compute: ${sum(v for a in mc['byAppDay'].values() for d, v in a.items() if d >= wk):,.2f} in 7d")
        elif mc:
            print(f"  ! Modal billing: {mc['error']}", file=sys.stderr)
        usage = fetch_api_usage()
        if usage is not None:
            history["apiUsage"] = usage
            print(f"  ok Claude API usage ledger: {len(usage)} paid job(s), "
                  f"${sum(u.get('cost_usd') or 0 for u in usage):,.2f} all time")

        # Apple Search Ads API. When configured it replaces the manual Chrome
        # reading: same manual-ads.json key, so every card reads it unchanged.
        try:
            asa = fetch_asa_api(cfg)
        except Exception as exc:  # noqa: BLE001
            asa = {"error": str(exc)[:160]}
        if asa and asa.get("error"):
            print(f"  ! Apple Search Ads API: {asa['error']}", file=sys.stderr)
        elif asa and asa.get("campaigns"):
            record_asa_api(asa)
            history["asaDaily"] = {**(history.get("asaDaily") or {}), **asa["daily"]}
            c0 = asa["campaigns"][0]
            print(f"  ok Apple Search Ads API: ${c0['spend']:,.2f} spend, {c0['installs']} installs in 7d")

        # Chrome Web Store (Scholar Utility Belt): no auth, so always attempted.
        try:
            cws = fetch_chrome_web_store(history.get("chromeWebStore"))
        except Exception as exc:  # noqa: BLE001 — never let this sink the run
            print(f"  ! chrome web store unavailable: {str(exc)[:100]}", file=sys.stderr)
            cws = history.get("chromeWebStore")
        if cws:
            history["chromeWebStore"] = cws
            print(f"  ok Chrome Web Store ({cws['label']}): {cws['users']} installed users")

        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        month_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
        # Etsy, Gumroad, Payhip: after Stripe so merge_ledger's first-run logic is untouched.
        try:
            mk_events, _mk_changed = marketplace_step(history, cfg, fetch=True)
            new_events += mk_events
        except Exception as exc:  # noqa: BLE001 -- never let this sink the run
            print(f"  ! marketplaces unavailable: {str(exc)[:100]}", file=sys.stderr)
        history["eventLog"] = ([e for e in history.get("eventLog", []) if e.get("at", "") >= month_ago]
                               + [{**e, "at": stamp} for e in new_events])
        history["lastRun"] = stamp
        HISTORY_PATH.write_text(json.dumps(history, indent=1, sort_keys=True))
    else:
        # Re-render only, but pick up a fresh marketplaces.json (the daily update
        # records it, then re-renders with --no-fetch).
        try:
            mk_events, mk_changed = marketplace_step(history, cfg, fetch=False)
        except Exception as exc:  # noqa: BLE001
            mk_events, mk_changed = [], False
            print(f"  ! marketplaces unavailable: {str(exc)[:100]}", file=sys.stderr)
        if mk_changed and HISTORY_PATH.exists():
            stamp = dt.datetime.now(dt.timezone.utc).isoformat()
            history["eventLog"] = history.get("eventLog", []) + [{**e, "at": stamp} for e in mk_events]
            HISTORY_PATH.write_text(json.dumps(history, indent=1, sort_keys=True))

    summaries = [summarise(s, history["sites"].get(s["key"], {})) for s in SITES]
    obs = (observations(summaries, history.get("sales"))
           + appstore_observations(history.get("appstore"))
           + sparkle_observations(history.get("moderntexUpdates")))
    firsts = [s["first_day"] for s in summaries if s["first_day"]]
    generated = dt.datetime.now().strftime("%a %d %b %Y, %-I:%M%p").replace("AM", "am").replace("PM", "pm")

    sales = history.get("sales")
    appstore = history.get("appstore")
    chrome_web_store = history.get("chromeWebStore")
    manual_ads = load_manual_ads()
    metrics = revenue_metrics(history, summaries, manual_ads)
    profit = profit_view(history, manual_ads)
    channels = channel_revenue(history)
    tax = tax_view(profit, history)
    marketplaces = marketplace_summary(history)
    market_rows = [r for r in (history.get("ledger") or {}).values() if r.get("market")]
    # Every source's money per day, kept in the archive so the series outlives any one source file.
    try:
        revenue_daily = archive_revenue_daily(
            history, all_sales_rows(list((history.get("ledger") or {}).values()), appstore, history.get("admob")))
        if HISTORY_PATH.exists():
            HISTORY_PATH.write_text(json.dumps(history, indent=1, sort_keys=True))
        write_revenue_daily_csv(revenue_daily)
    except Exception as exc:  # noqa: BLE001 -- never let this sink the run
        revenue_daily = history.get("revenueDaily")
        print(f"  ! daily revenue not archived: {str(exc)[:100]}", file=sys.stderr)
    DASHBOARD_PATH.write_text(
        render(summaries, obs, generated, min(firsts) if firsts else None,
               sales, appstore, manual_ads, chrome_web_store, history.get("admob"), metrics,
               profit, channels, tax, marketplaces, market_rows,
               list((history.get("ledger") or {}).values()), revenue_daily))

    # Terminal summary, so a manual run is useful without opening a browser.
    print_metrics(metrics)
    print_revenue_sources(sales, appstore, market_rows, history.get("admob"))
    print_outbound_veil(outbound_veil_report(history))
    print_legroom(legroom_report(history))
    print_panely(panely_report(history))
    print_summonly(summonly_report(history))
    print_vitae(vitae_report(history))
    print_downloads_all_sources(history)
    print_extensionpay(history)
    print_profit(profit, channels, tax)
    print_ad_funnel(history)
    print_marketplaces(marketplaces)
    print_queue(queue_summary())
    if sales:
        w, a = sales.get("window", {}), sales.get("allTime", {})
        print(f"\n  Sales — {money(w.get('gross', 0))} in the last "
              f"{w.get('days', FETCH_DAYS)} days ({orders(w.get('orders', 0))}); "
              f"{money(a.get('gross', 0))} all time ({orders(a.get('orders', 0))})")
        for site_row in sales.get("bySite", []):
            print(f"   {site_row['label']:<22} {money(site_row['windowGross']):>8} "
                  f"({site_row['windowOrders']})   all time {money(site_row['gross'])}")

    if appstore:
        sm = appstore_summary(appstore)
        usd = sm["proceeds"].get("USD", 0.0)
        print(f"\n  App Store — {sm['label']}: {sm['w7']['downloads']} downloads/7d, "
              f"{sm['w30']['downloads']}/30d, {sm['allTime']['downloads']} since launch; "
              f"{sm['allTime']['proUnits']} paid Pro, {sm['allTime']['proPromo']} promo, ${usd:,.2f} proceeds")

    if chrome_web_store:
        print(f"\n  Chrome Web Store — {chrome_web_store['label']}: "
              f"{chrome_web_store['users']} installed users (rounded, as of {chrome_web_store['asOf']})")

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
