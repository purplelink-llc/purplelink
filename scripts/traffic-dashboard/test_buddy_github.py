"""Buddy (GitHub): release asset download_count is a running total; the dashboard row is the 7-day difference
per day, n/a until a reading 7 days old exists, and says the count includes Sparkle update downloads."""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import traffic_dashboard as td  # noqa: E402

TODAY = dt.date(2026, 11, 27)


def _hist(readings):
    h = {}
    for day, total in readings.items():
        td.merge_buddy_github(h, total, day)
    return h


def test_fetch_sums_pages_from_gh(monkeypatch):
    seen = []

    def fake_run(cmd, **kw):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="60\n36\n")

    monkeypatch.setattr(td.subprocess, "run", fake_run)
    assert td.fetch_buddy_github_total() == 96
    assert seen[0][:4] == ["gh", "api", "--paginate", "repos/purplelink-llc/buddy/releases"]


def test_fetch_falls_back_to_rest_and_counts_only_buddy_zip(monkeypatch):
    def no_gh(cmd, **kw):
        raise FileNotFoundError("gh")

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps([{"assets": [{"name": "Buddy.zip", "download_count": 5},
                                           {"name": "notes.txt", "download_count": 99}]},
                               {"assets": [{"name": "Buddy.zip", "download_count": 11}]}]).encode()

    monkeypatch.setattr(td.subprocess, "run", no_gh)
    monkeypatch.setattr(td.urllib.request, "urlopen", lambda req, timeout=20: R())
    assert td.fetch_buddy_github_total() == 16


def test_fetch_none_when_everything_fails(monkeypatch):
    def boom(*a, **k):
        raise OSError("offline")

    monkeypatch.setattr(td.subprocess, "run", boom)
    monkeypatch.setattr(td.urllib.request, "urlopen", boom)
    assert td.fetch_buddy_github_total() is None


def test_seven_day_difference_per_day():
    h = _hist({"2026-11-20": 89, "2026-11-27": 96})
    s = td.buddy_github_summary(h["buddyGithub"], TODAY)
    assert s["total"] == 96 and s["since"] == "2026-11-20" and s["perDay"] == 1.0


def test_uses_latest_reading_at_least_seven_days_old():
    h = _hist({"2026-11-15": 50, "2026-11-19": 80, "2026-11-27": 96})
    s = td.buddy_github_summary(h["buddyGithub"], TODAY)
    assert s["since"] == "2026-11-19" and s["perDay"] == 2.0  # 16 downloads over 8 days


def test_na_until_seven_days_of_readings():
    s = td.buddy_github_summary(_hist({"2026-11-27": 96})["buddyGithub"], TODAY)
    assert s["perDay"] is None and s["weeklyFrom"] == "2026-12-04"
    s = td.buddy_github_summary(_hist({"2026-11-24": 90, "2026-11-27": 96})["buddyGithub"], TODAY)
    assert s["perDay"] is None
    assert td.buddy_github_summary(None, TODAY) is None


def test_total_going_down_is_floored_at_zero():
    s = td.buddy_github_summary(_hist({"2026-11-20": 100, "2026-11-27": 90})["buddyGithub"], TODAY)
    assert s["perDay"] == 0


def test_row_and_printed_note(capsys):
    h = _hist({"2026-11-20": 89, "2026-11-27": 96})
    h["sites"] = {"purplelink": {"byDay": {}}}
    rows = {r["app"]: r for r in td.downloads_all_sources(h, TODAY)}
    assert rows["Buddy (GitHub)"]["gh"]["perDay"] == 1.0
    td.print_downloads_all_sources(h)
    out = capsys.readouterr().out
    assert "Buddy (GitHub)" in out and "1.0 a day" in out and "Sparkle auto-update downloads" in out
    assert "Mac apps incl. Vitae" in out
    out_na = td.downloads_all_sources({"sites": {}}, TODAY)[-1]
    assert out_na["gh"] is None
