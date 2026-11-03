#!/usr/bin/env python3
"""TikTok Creator Rewards by month, from the per-post estimates in TikTok Studio.

    python3 scripts/traffic-dashboard/test_tiktok_rewards.py

Why it exists: posts were written with a local and a UTC posted_at and counted twice, and the account's 7-day totals,
rebuilt into days, overcounted. On 2026-10-20 TikTok's app said $42.38 for October; the old code said $51.08, this $41.73.
"""
import csv
import datetime as dt
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="traffic-test-")
os.environ["PURPLELINK_TRAFFIC_DIR"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent))

import traffic_dashboard as td  # noqa: E402
# Hide TikTok's real daily figures (TikTokPipeline/analytics/tiktok_daily_income.csv) when run directly, as conftest.py
# does under pytest; otherwise the live file overrides each test's own data (2026-10-20).
td.TIKTOK_DAILY_INCOME_CSV = Path(TMP) / "no-daily-income.csv"

FIELDS = ["snapshot_date", "snapshot_at", "pipeline", "platform", "level", "program", "window", "currency", "caption",
          "posted_at", "est_rewards", "qualified_views"]


def acct(day, total, at="21:00:00", pipe="nl", program="Total", window="Last 7 days"):
    return {"snapshot_date": day, "snapshot_at": f"{day}T{at}", "pipeline": pipe, "platform": "tiktok", "level": "account",
            "program": program, "window": window, "currency": "USD", "caption": "", "posted_at": "",
            "est_rewards": str(total), "qualified_views": ""}


def post(day, caption, posted, est, pipe="nl"):
    return {"snapshot_date": day, "snapshot_at": f"{day}T21:00:00", "pipeline": pipe, "platform": "tiktok", "level": "post",
            "program": "Creator Rewards Program", "window": "", "currency": "USD", "caption": caption,
            "posted_at": posted, "est_rewards": str(est), "qualified_views": "100"}


def write_csv(rows):
    path = Path(tempfile.mkdtemp(dir=TMP)) / "tiktok_rewards.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path


class PerPostReading(unittest.TestCase):
    MONTHS = ["2026-09", "2026-10"]

    def test_local_and_utc_spellings_of_one_post_count_once(self):
        # The real October file had 27 posts written both ways; counted twice they put October at $48.85, not $41.73.
        rows = [post("2026-10-05", "a", "2026-10-04T11:06", 4.18), post("2026-10-06", "a", "2026-10-04T15:06Z", 8.70),
                post("2026-10-06", "b", "2026-10-06T07:54", 1.54)]
        self.assertAlmostEqual(td.tiktok_rewards_by_month(self.MONTHS, path=write_csv(rows))["2026-10"], 10.24, places=2)

    def test_same_caption_days_apart_is_two_posts(self):
        rows = [post("2026-10-05", "a", "2026-10-01T11:00", 1.0), post("2026-10-05", "a", "2026-10-04T11:00", 2.0)]
        self.assertAlmostEqual(td.tiktok_rewards_by_month(self.MONTHS, path=write_csv(rows))["2026-10"], 3.0, places=2)

    def test_each_rise_lands_on_the_day_it_was_seen(self):
        rows = [post("2026-09-30", "a", "2026-09-29T10:00", 1.25), post("2026-10-01", "a", "2026-09-29T10:00", 2.5),
                post("2026-10-02", "a", "2026-09-29T10:00", 2.0)]  # a lower later figure is not a loss
        daily = td.tiktok_daily_from_posts([{**r} for r in csv.DictReader(open(write_csv(rows)))])
        self.assertEqual({d: round(v, 2) for d, v in daily["nl"].items()}, {"2026-09-30": 1.25, "2026-10-01": 1.25})
        got = td.tiktok_rewards_by_month(self.MONTHS, path=write_csv(rows))
        self.assertEqual(got, {"2026-09": 1.25, "2026-10": 1.25})

    def test_account_totals_are_not_counted(self):
        # Studio's rolling 7-day totals are revised down after the fact, so rebuilding days from them overcounted
        # ($51.08 for October 1-19 against TikTok's own $42.38). They stay in the CSV but do not count.
        rows = [acct("2026-10-01", 0.0), acct("2026-10-05", 29.65), post("2026-10-05", "a", "2026-10-04T11:06", 4.18)]
        self.assertAlmostEqual(td.tiktok_rewards_by_month(self.MONTHS, path=write_csv(rows))["2026-10"], 4.18, places=2)

    def test_missing_file_reads_as_zero(self):
        got = td.tiktok_rewards_by_month(self.MONTHS, path=Path(TMP) / "nope.csv")
        self.assertEqual(got, {"2026-09": 0.0, "2026-10": 0.0})


class Label(unittest.TestCase):
    def test_the_refresh_label_matches_the_7am_job(self):
        src = Path(td.__file__).read_text(encoding="utf-8")
        self.assertIn("refreshes daily from 7:00am", src)
        self.assertNotIn("refreshes daily at 9:00am", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)


def test_tiktoks_same_day_zero_is_not_a_zero_day(tmp_path):
    p = tmp_path / "income.csv"
    p.write_text(
        "snapshot_date,snapshot_at,pipeline,program,day,est_income,currency\n"
        "2026-10-27,2026-10-27T21:36:08,nl,Total,2026-10-26,0.51,USD\n"
        "2026-10-27,2026-10-27T21:36:08,nl,Total,2026-10-27,0.0,USD\n"
    )
    days = td.tiktok_api_daily(p)["nl"]
    assert days == {"2026-10-26": 0.51}
    p.write_text(p.read_text() + "2026-10-28,2026-10-28T13:44:30,nl,Total,2026-10-27,0.48,USD\n")
    assert td.tiktok_api_daily(p)["nl"] == {"2026-10-26": 0.51, "2026-10-27": 0.48}


def test_a_real_zero_for_an_earlier_day_still_counts(tmp_path):
    p = tmp_path / "income.csv"
    p.write_text(
        "snapshot_date,snapshot_at,pipeline,program,day,est_income,currency\n"
        "2026-10-28,2026-10-28T13:44:30,nl,Total,2026-10-20,0.0,USD\n"
    )
    assert td.tiktok_api_daily(p)["nl"] == {"2026-10-20": 0.0}
