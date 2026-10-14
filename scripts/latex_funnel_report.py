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
  CONTINUE only if the channel "youtube-latex" averaged at least 10 page views a week over the last 4 weeks of
  history. Otherwise STOP scaling: keep what exists, publish nothing new in this series, and put the time elsewhere.
  Trials and purchases are reported but are not part of the rule: at this volume they are too rare to separate
  from noise. Early warning (not a stop): 4 weeks after the links went in with zero attributed page views means
  the links are not being clicked or not being tagged; check yt-utm.py and a private Short before anything else.
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
FIELDS = ["date", "videos", "views_7d", "views_28d", "search_share_28d", "ext_clicks_28d",
          "site_views_28d", "moderntex_views_28d", "trials_28d", "checkouts_28d"]


# ---------------------------------------------------------------- pure logic
def weekly_visits(rows: list[dict], today: dt.date, weeks: int = 4) -> float | None:
    """Average page views a week from the youtube-latex channel over the last `weeks` weeks.

    Each history row carries the trailing 28-day total, so the average is the latest row's 28-day figure scaled
    to weeks; with less than `weeks` weeks of history it is None (not enough data to judge)."""
    dated = sorted(((dt.date.fromisoformat(r["date"]), float(r["site_views_28d"] or 0)) for r in rows
                    if r.get("date")), key=lambda x: x[0])
    if not dated or (today - dated[0][0]).days < weeks * 7 - 1:
        return None
    return dated[-1][1] / 4.0 if weeks == 4 else dated[-1][1] / (28 / 7)


def verdict(rows: list[dict], videos: int, today: dt.date) -> tuple[str, str]:
    """(status, one line). status is CONTINUE, STOP, WAIT or WARN."""
    due = today >= CHECKPOINT_DATE or videos >= CHECKPOINT_VIDEOS
    per_week = weekly_visits(rows, today)
    if not due:
        warn = (today - LINKS_LIVE).days >= 28 and rows and float(rows[-1]["site_views_28d"] or 0) == 0
        if warn:
            return "WARN", ("four weeks after the links went in there are no attributed page views: the links are "
                            "not being clicked or not tagged. Check yt-utm.py and test a link on a private Short.")
        return "WAIT", (f"checkpoint at {CHECKPOINT_VIDEOS} videos or {CHECKPOINT_DATE.isoformat()} "
                        f"(now {videos} videos, {(CHECKPOINT_DATE - today).days} days to go)")
    if per_week is None:
        return "WAIT", "checkpoint reached but fewer than 4 weeks of history; keep recording and re-run"
    if per_week >= MIN_VISITS_PER_WEEK:
        return "CONTINUE", f"{per_week:.1f} page views a week from youtube-latex (rule: at least {MIN_VISITS_PER_WEEK})"
    return "STOP", (f"{per_week:.1f} page views a week from youtube-latex is under {MIN_VISITS_PER_WEEK}: "
                    "stop scaling the series")


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


# ---------------------------------------------------------------- data sources
def fetch_site_stats() -> dict:
    spec = importlib.util.spec_from_file_location("td", ROOT / "scripts" / "traffic-dashboard" / "traffic_dashboard.py")
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
    today = dt.date.today()
    out = {"videos": len(series)}
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


def report(today: dt.date, yt: dict, site: dict, history: list[dict]) -> str:
    rows = [r for r in history if r["date"] != today.isoformat()] + [{**site, "date": today.isoformat()}]
    status, why = verdict(sorted(rows, key=lambda r: r["date"]), yt["videos"], today)
    pv = site["site_views_28d"]
    return "\n".join([
        f"LaTeX video funnel, {today.isoformat()}",
        f"  videos in the series: {yt['videos']}   views 7d {yt['views_7d']}, 28d {yt['views_28d']}   "
        f"from YouTube search {yt['search_share_28d']:.0%}   external-link views 28d {yt['ext_clicks_28d']}",
        f"  site, channel '{CHANNEL}', 28d: {pv} page views, {site['moderntex_views_28d']} on ModernTex pages, "
        f"{site['trials_28d']} trial(s), {site['checkouts_28d']} checkout click(s)",
        f"  views to site visits: {pv / yt['views_28d']:.1%}" if yt["views_28d"] else "  views to site visits: n/a",
        f"  stop rule: {status} - {why}"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", action="store_true", help="append today's row to the history file")
    a = ap.parse_args()
    today = dt.date.today()
    yt, site = fetch_youtube(), site_numbers(fetch_site_stats())
    hist = read_history()
    print(report(today, yt, site, hist))
    if a.record:
        append_history({"date": today.isoformat(), **{k: yt[k] for k in ("videos", "views_7d", "views_28d",
                         "search_share_28d", "ext_clicks_28d")}, **site})
    return 0


if __name__ == "__main__":
    sys.exit(main())
