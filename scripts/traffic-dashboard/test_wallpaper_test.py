"""The free wallpaper pack's downloads and its 30-day stop rule (50 downloads, or no paid pack)."""
import sys
import os, tempfile
os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))   # never touch the real archive
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td
import datetime as dt

SITE = next(x for x in td.SITES if x["key"] == "purplelink")


def _days(start: str, counts: list[int]) -> dict:
    d0 = dt.date.fromisoformat(start)
    return {(d0 + dt.timedelta(days=i)).isoformat(): {"wallpaperDownloads": n, "pageviews": 5}
            for i, n in enumerate(counts)}


def test_counts_complete_days_only():
    by_day = _days("2026-10-31", [3, 4, 5])          # 10-31, 11-01 and today 11-02
    wt = td.wallpaper_test(by_day, dt.date(2026, 11, 2))
    assert wt == {"downloads": 7, "daysIn": 2, "start": "2026-10-31", "end": "2026-11-29", "done": False}


def test_window_stops_at_thirty_days():
    wt = td.wallpaper_test(_days("2026-10-31", [2] * 40), dt.date(2026, 12, 20))
    assert wt["daysIn"] == 30 and wt["downloads"] == 60 and wt["done"]


def test_observation_reports_progress_and_verdict():
    recent = (dt.date.today() - dt.timedelta(days=10)).isoformat()   # observations skip a site with no recent views
    s = td.summarise(SITE, {"byDay": _days(recent, [1] * 11)})
    for wt, expect in (
        ({"downloads": 7, "daysIn": 2, "start": "2026-10-31", "end": "2026-11-29", "done": False},
         "wallpaper test at 7 download(s) after 2 of 30 days"),
        ({"downloads": 12, "daysIn": 30, "start": "2026-10-31", "end": "2026-11-29", "done": True},
         "missed: no paid pack"),
        ({"downloads": 51, "daysIn": 30, "start": "2026-10-31", "end": "2026-11-29", "done": True},
         "passed: the paid 30-pack can be built"),
    ):
        lines = td.observations([dict(s, wallpaper_test=wt)])
        assert any(expect in line for line in lines), lines


def test_metric_is_a_purplelink_secondary_and_form():
    assert ("wallpaperDownloads", "wallpaper downloads") in SITE["secondaries"]
    assert SITE["signup_forms"]["wallpaper-news"] == "wallpaperSignups"
