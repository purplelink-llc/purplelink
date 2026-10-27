#!/usr/bin/env python3
"""Weekly read of the LaTeX video funnel, and the stop rule that decides whether to keep scaling it.

The funnel:  YouTube video (the "how to fix it" Shorts and the ModernTex promos)  ->  a purplelink.llc page
tagged utm_source=youtube-latex (scripts/yt-utm.py)  ->  ModernTex pages  ->  trial / purchase.
The site records utm_source as the first-touch channel, so everything this series sends is the channel
"youtube-latex" in the stats function's funnelByChannel. The live stream uses utm_source=youtube and is NOT counted.

  python3 scripts/latex_funnel_report.py                  # print the report
  python3 scripts/latex_funnel_report.py --record         # also append today's row to the history file
  history file: ~/.purplelink/latex-funnel/history.csv  (one row per date, re-running a day replaces its row)

STOP RULE (written 2026-10-14, before the series is scaled; do not edit it after seeing results):
  Checkpoint: the first report on or after 2026-12-09 (8 weeks after the tagged links went in) or with 45 or more
  "how to fix it" videos published, whichever comes first.
  CONTINUE only if the channel "youtube-latex" averaged at least 10 ESTIMATED HUMAN page views a week over the last
  4 weeks of history. Otherwise STOP scaling: keep what exists, publish nothing new in this series, and put the
  time elsewhere. Trials and purchases are reported but are not part of the rule: at this volume they are too rare
  to separate from noise (and see below). Early warning (not a stop): 4 weeks after the links went in with zero
  estimated human page views means the links are not being clicked or not being tagged; check yt-utm.py and test a
  link on a private Short before anything else.

  Why "estimated human": on 2026-10-14, within minutes of tagging 14 videos, the site recorded 28 page views and 4
  trial events for the channel: exactly 2 page views on each of 14 new tagged URLs and nothing else. Something
  that checks new links in a description arrives with an ordinary browser agent, which the site's bot filter
  (user-agent words only, netlify/functions/track.mjs) does not catch. Every new tagged URL therefore adds
  about 2 page views that no person produced, so a daily upload would add about 4 a day (28 a week) with no
  viewer at all and would clear a bar of 10 by itself. The estimate subtracts 2 views per tagged URL first
  published within the 28-day window (BOT_VIEWS_PER_URL); it is an estimate, and the history file keeps the raw
  numbers so it can be revised.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.util
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = Path.home() / ".purplelink" / "latex-funnel" / "history.csv"
CHANNEL = "youtube-latex"
LINKS_LIVE = dt.date(2026, 10, 14)
CHECKPOINT_DATE = dt.date(2026, 12, 9)
CHECKPOINT_VIDEOS = 45
MIN_VISITS_PER_WEEK = 10
BOT_VIEWS_PER_URL = 2
FIELDS = ["date", "videos", "tagged_urls", "views_7d", "views_28d", "search_share_28d", "ext_clicks_28d",
          "site_views_28d", "human_views_est_28d", "moderntex_views_28d", "trials_28d", "checkouts_28d",
          "errpage_views_7d", "errpage_views_28d", "band_trials_7d", "band_trials_14d", "band_trials_28d",
          "band_buys_7d", "band_buys_28d"]
BAND_CHANNEL = "from:latex-errors"   # first-touch label analytics.js gives a visit whose URL has ?from=latex-errors
ERRPAGE_PREFIX = "/latex-errors"     # the hub and the error pages
BAND_MIN_TRIALS_14D = 5


# ---------------------------------------------------------------- pure logic
def weekly_visits(rows: list[dict], today: dt.date, weeks: int = 4) -> float | None:
    """Average page views a week from the youtube-latex channel over the last `weeks` weeks.

    Each history row carries the trailing 28-day total, so the average is the latest row's 28-day figure scaled
    to weeks; with less than `weeks` weeks of history it is None (not enough data to judge)."""
    dated = sorted(((dt.date.fromisoformat(r["date"]), float(r.get("human_views_est_28d") or 0)) for r in rows
                    if r.get("date")), key=lambda x: x[0])
    if not dated or (today - dated[0][0]).days < weeks * 7 - 1:
        return None
    return dated[-1][1] / 4.0 if weeks == 4 else dated[-1][1] / (28 / 7)


def verdict(rows: list[dict], videos: int, today: dt.date) -> tuple[str, str]:
    """(status, one line). status is CONTINUE, STOP, WAIT or WARN."""
    due = today >= CHECKPOINT_DATE or videos >= CHECKPOINT_VIDEOS
    per_week = weekly_visits(rows, today)
    if not due:
        warn = (today - LINKS_LIVE).days >= 28 and rows and float(rows[-1].get("human_views_est_28d") or 0) == 0
        if warn:
            return "WARN", ("four weeks after the links went in there are no estimated human page views: the links are "
                            "not being clicked or not tagged. Check yt-utm.py and test a link on a private Short.")
        return "WAIT", (f"checkpoint at {CHECKPOINT_VIDEOS} videos or {CHECKPOINT_DATE.isoformat()} "
                        f"(now {videos} videos, {(CHECKPOINT_DATE - today).days} days to go)")
    if per_week is None:
        return "WAIT", "checkpoint reached but fewer than 4 weeks of history; keep recording and re-run"
    if per_week >= MIN_VISITS_PER_WEEK:
        return "CONTINUE", f"{per_week:.1f} estimated human page views a week from youtube-latex (rule: at least {MIN_VISITS_PER_WEEK})"
    return "STOP", (f"{per_week:.1f} estimated human page views a week from youtube-latex is under {MIN_VISITS_PER_WEEK}: "
                    "stop scaling the series")


def bot_allowance(history: list[dict], today: dt.date, tagged_now: int) -> int:
    """Page views to subtract as non-human: BOT_VIEWS_PER_URL for each tagged URL first published inside the
    28-day window. URLs known 28+ days ago are taken from the newest history row at least 28 days old."""
    old = [r for r in history if (today - dt.date.fromisoformat(r["date"])).days >= 28]
    base = int(float(old[-1].get("tagged_urls") or 0)) if old else 0
    return BOT_VIEWS_PER_URL * max(tagged_now - base, 0)


def human_estimate(site_views: int, allowance: int) -> int:
    return max(site_views - allowance, 0)


def append_history(row: dict, path: Path = HISTORY) -> None:
    """One row per date: a second run on the same day replaces that day's row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != row["date"]]
    rows.append({k: row.get(k, "") for k in FIELDS})
    rows.sort(key=lambda r: r["date"])
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def read_history(path: Path = HISTORY) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return sorted(csv.DictReader(f), key=lambda r: r["date"])


def site_numbers(stats: dict) -> dict:
    """From the stats function's response (28 days): the series' own channel only."""
    ch = (stats.get("funnelByChannel") or {}).get(CHANNEL) or {}
    by_path = ch.get("pageviewsByPath") or {}
    return {"site_views_28d": int(ch.get("pageviews", 0)),
            "moderntex_views_28d": sum(n for p, n in by_path.items() if p.startswith("/moderntex")),
            "trials_28d": sum(int(v) for v in (ch.get("trial") or {}).values() if str(v).isdigit() or isinstance(v, int)),
            "checkouts_28d": sum(int(v) for v in (ch.get("checkout") or {}).values() if str(v).isdigit() or isinstance(v, int))}


def band_numbers(stats: dict | None) -> dict | None:
    """From one stats response (any window): page views on /latex-errors/* and the ModernTex band's tagged trials and
    buy clicks. None when the response is missing (not measured).

    Tagged = the site's first-touch channel is "from:latex-errors" (analytics.js labels a visit by utm_source, else
    ?from=). The stats function records the first-touch label on trial downloads and buy clicks, not the landing
    URL, so a visitor who first arrived some other way (search, a YouTube tag) and later clicked the band is not
    counted: the tagged figure is a floor."""
    if stats is None:
        return None
    views = sum(int(x.get("count", 0)) for x in (stats.get("topPaths") or [])
                if str(x.get("key", "")).startswith(ERRPAGE_PREFIX))
    ch = (stats.get("funnelByChannel") or {}).get(BAND_CHANNEL) or {}
    num = lambda d: sum(int(v) for v in (d or {}).values() if isinstance(v, (int, float)) or str(v).isdigit())
    return {"views": views, "trials": num(ch.get("trial")), "buys": num(ch.get("checkout"))}


def band_verdict(trials_14d: int | None) -> str:
    if trials_14d is None:
        return "band test: not measured (tagged trials in 14 days unavailable)"
    if trials_14d >= BAND_MIN_TRIALS_14D:
        return "band test: readable"
    return f"band test: not readable yet ({trials_14d} tagged trials in 14 days, need {BAND_MIN_TRIALS_14D})"


def band_fields(w7: dict | None, w14: dict | None, w28: dict | None) -> dict:
    g = lambda w, k: "" if w is None else w[k]
    return {"errpage_views_7d": g(w7, "views"), "errpage_views_28d": g(w28, "views"),
            "band_trials_7d": g(w7, "trials"), "band_trials_14d": g(w14, "trials"), "band_trials_28d": g(w28, "trials"),
            "band_buys_7d": g(w7, "buys"), "band_buys_28d": g(w28, "buys")}


def band_line(f: dict) -> str:
    m = lambda k: "not measured" if f.get(k, "") == "" else str(f[k])
    return (f"  ModernTex band on /latex-errors/*: page views 7d {m('errpage_views_7d')}, 28d {m('errpage_views_28d')}; "
            f"tagged trials (from=latex-errors) 7d {m('band_trials_7d')}, 14d {m('band_trials_14d')}, 28d {m('band_trials_28d')}; "
            f"tagged buy clicks 7d {m('band_buys_7d')}, 28d {m('band_buys_28d')}")


def fetch_band_stats() -> tuple[dict | None, dict | None, dict | None]:
    """Stats windows of 7, 14 and 28 days; a window that cannot be read is None, never zero."""
    spec = importlib.util.spec_from_file_location("td", _dashboard_path())
    td = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(td)
    site = next(s for s in td.SITES if s["key"] == "purplelink")
    token = td.load_config()["PURPLELINK_STATS_TOKEN"]
    out = []
    for d in (7, 14, 28):
        try:
            out.append(band_numbers(td.fetch_site(site, token, d)))
        except Exception as e:  # noqa: BLE001 - report as not measured
            print(f"  (band stats {d}d unavailable: {e})", file=sys.stderr)
            out.append(None)
    return tuple(out)  # type: ignore[return-value]


# ---------------------------------------------------------------- data sources
def _dashboard_path() -> Path:
    """The traffic dashboard module: the local copy the daily job keeps in ~/.purplelink/traffic (it exists when the
    repo checkout is behind or the SSD is not mounted), else the one in this repo."""
    local = Path.home() / ".purplelink" / "traffic" / "traffic_dashboard.py"
    return local if local.exists() else ROOT / "scripts" / "traffic-dashboard" / "traffic_dashboard.py"


def fetch_site_stats() -> dict:
    spec = importlib.util.spec_from_file_location("td", _dashboard_path())
    td = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(td)
    site = next(s for s in td.SITES if s["key"] == "purplelink")
    return td.fetch_site(site, td.load_config()["PURPLELINK_STATS_TOKEN"], 28)


def fetch_youtube() -> dict:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    c = Credentials.from_authorized_user_file(str(Path.home() / ".tiktok_pipeline" / "youtube_analytics_purplelink.json"))
    if not c.valid:
        c.refresh(Request())
    yt = build("youtube", "v3", credentials=c, cache_discovery=False)
    ya = build("youtubeAnalytics", "v2", credentials=c, cache_discovery=False)
    up = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    vids = []
    for i in range(0, len(ids), 50):
        vids += yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute()["items"]
    series = [v["id"] for v in vids if "/latex-errors/" in v["snippet"].get("description", "")]
    tagged = {u for v in vids for u in re.findall(r"https://purplelink\.llc/\S*utm_source=youtube-latex\S*", v["snippet"].get("description", ""))}
    today = dt.date.today()
    out = {"videos": len(series), "tagged_urls": len(tagged)}
    if not series:
        return {**out, "views_7d": 0, "views_28d": 0, "search_share_28d": 0.0, "ext_clicks_28d": 0}
    flt = "video==" + ",".join(series)

    def q(days, dims=None):
        kw = dict(ids="channel==MINE", startDate=(today - dt.timedelta(days=days)).isoformat(),
                  endDate=today.isoformat(), metrics="views", filters=flt)
        if dims:
            kw["dimensions"] = dims
        return ya.reports().query(**kw).execute().get("rows") or []
    v7, v28 = q(7), q(28)
    src = {r[0]: r[1] for r in q(28, "insightTrafficSourceType")}
    total = sum(src.values()) or 1
    out.update(views_7d=int(v7[0][0]) if v7 else 0, views_28d=int(v28[0][0]) if v28 else 0,
               search_share_28d=round(src.get("YT_SEARCH", 0) / total, 3), ext_clicks_28d=int(src.get("EXT_URL", 0)))
    return out


def report(today: dt.date, yt: dict, site: dict, history: list[dict], band: dict | None = None) -> str:
    allowance = bot_allowance(history, today, yt["tagged_urls"])
    human = human_estimate(site["site_views_28d"], allowance)
    rows = [r for r in history if r["date"] != today.isoformat()] + [{**site, "date": today.isoformat(), "human_views_est_28d": human}]
    status, why = verdict(sorted(rows, key=lambda r: r["date"]), yt["videos"], today)
    pv = site["site_views_28d"]
    return "\n".join([
        f"LaTeX video funnel, {today.isoformat()}",
        f"  videos in the series: {yt['videos']}   views 7d {yt['views_7d']}, 28d {yt['views_28d']}   "
        f"from YouTube search {yt['search_share_28d']:.0%}   external-link views 28d {yt['ext_clicks_28d']}",
        f"  site, channel '{CHANNEL}', 28d: {pv} page views of which about {allowance} are link checks on "
        f"{yt['tagged_urls']} tagged URLs, so {human} estimated human; {site['moderntex_views_28d']} on ModernTex pages, "
        f"{site['trials_28d']} trial(s), {site['checkouts_28d']} checkout click(s)",
        f"  views to estimated human site visits: {human / yt['views_28d']:.1%}" if yt["views_28d"] else "  views to site visits: n/a",
        f"  stop rule: {status} - {why}",
        band_line(band or band_fields(None, None, None)),
        "  " + band_verdict(None if not band or band.get("band_trials_14d", "") == "" else int(band["band_trials_14d"]))])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", action="store_true", help="append today's row to the history file")
    a = ap.parse_args()
    today = dt.date.today()
    yt, site = fetch_youtube(), site_numbers(fetch_site_stats())
    hist = read_history()
    band = band_fields(*fetch_band_stats())
    print(report(today, yt, site, hist, band))
    if a.record:
        human = human_estimate(site["site_views_28d"], bot_allowance(hist, today, yt["tagged_urls"]))
        append_history({"date": today.isoformat(), **{k: yt[k] for k in ("videos", "tagged_urls", "views_7d", "views_28d",
                         "search_share_28d", "ext_clicks_28d")}, **site, **band, "human_views_est_28d": human})
    return 0


if __name__ == "__main__":
    sys.exit(main())
