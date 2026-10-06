#!/usr/bin/env python3
"""TikTok Creator Rewards by month, rebuilt from TikTok's rolling 7-day account totals.

    python3 scripts/traffic-dashboard/test_tiktok_rewards.py

Why it exists: the Monetization page lists only the newest few posts, so summing per-post estimates under-counts
(2026-10-05: $17.72 from posts against TikTok's own 7-day total of $29.65). The account totals do not have that hole.
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


def window_totals(daily, start):
    """T(d) = sum of the 7 days ending d, for every day in daily (earnings before `start` are zero)."""
    out = {}
    for i in range(len(daily)):
        day = start + dt.timedelta(days=i)
        out[day] = sum(daily[j] for j in range(max(0, i - 6), i + 1))
    return out


class RebuiltFromAccountTotals(unittest.TestCase):
    def test_the_real_series_reaches_tiktoks_own_total(self):
        rows = [acct("2026-10-01", 0.0), acct("2026-10-02", 0.0), acct("2026-10-03", 7.86),
                acct("2026-10-04", 7.86, at="10:07:50"), acct("2026-10-04", 19.96, at="21:28:35"),
                acct("2026-10-05", 29.65)]
        daily = td.tiktok_daily_from_account_totals(rows)
        self.assertAlmostEqual(daily["2026-10-03"], 7.86, places=2)
        self.assertAlmostEqual(daily["2026-10-04"], 12.10, places=2)
        self.assertAlmostEqual(daily["2026-10-05"], 9.69, places=2)
        self.assertAlmostEqual(sum(daily.values()), 29.65, places=2)

    def test_a_week_later_the_window_rolls_and_daily_earnings_are_still_exact(self):
        rng = random.Random(7)
        start = dt.date(2026, 10, 1)
        true = [round(rng.uniform(0, 9), 2) for _ in range(21)]
        totals = window_totals(true, start)
        rows = [acct(d.isoformat(), round(t, 6)) for d, t in totals.items()]
        got = td.tiktok_daily_from_account_totals(rows)
        for i, e in enumerate(true):
            self.assertAlmostEqual(got[(start + dt.timedelta(days=i)).isoformat()], e, places=4, msg=f"day {i + 1}")

    def test_a_missing_snapshot_day_keeps_the_total_and_later_days_stay_exact(self):
        rng = random.Random(11)
        start = dt.date(2026, 10, 1)
        true = [round(rng.uniform(0, 9), 2) for _ in range(11)]
        totals = window_totals(true, start)
        skip = start + dt.timedelta(days=4)  # day 5 has no snapshot
        rows = [acct(d.isoformat(), t) for d, t in totals.items() if d != skip]
        got = td.tiktok_daily_from_account_totals(rows)
        self.assertAlmostEqual(got[skip.isoformat()] + got[(skip + dt.timedelta(days=1)).isoformat()],
                               true[4] + true[5], places=4)
        for i in (0, 1, 2, 3, 6, 7, 8, 9):  # untouched by the gap's even split
            self.assertAlmostEqual(got[(start + dt.timedelta(days=i)).isoformat()], true[i], places=4, msg=f"day {i + 1}")

    def test_other_windows_and_programs_are_ignored(self):
        rows = [acct("2026-10-01", 0.0), acct("2026-10-02", 5.0),
                acct("2026-10-02", 999, program="LIVE rewards"), acct("2026-10-02", 999, window="Last 28 days")]
        self.assertAlmostEqual(sum(td.tiktok_daily_from_account_totals(rows).values()), 5.0, places=2)

    def test_two_pipelines_add_up_and_never_mix(self):
        rows = [acct("2026-10-01", 0, pipe="nl"), acct("2026-10-02", 3.0, pipe="nl"),
                acct("2026-10-01", 0, pipe="aita"), acct("2026-10-02", 2.0, pipe="aita")]
        self.assertAlmostEqual(sum(td.tiktok_daily_from_account_totals(rows).values()), 5.0, places=2)

    def test_garbage_rows_are_skipped_not_fatal(self):
        rows = [acct("not-a-date", 1), acct("2026-10-01", "n/a"), acct("2026-10-02", 4.0)]
        self.assertAlmostEqual(sum(td.tiktok_daily_from_account_totals(rows).values()), 4.0, places=2)


class MonthTotals(unittest.TestCase):
    MONTHS = ["2026-09", "2026-10"]

    def test_rebuilt_total_beats_a_short_per_post_list(self):
        rows = [acct("2026-10-01", 0.0), acct("2026-10-03", 7.86), acct("2026-10-04", 19.96), acct("2026-10-05", 29.65),
                post("2026-10-05", "a", "2026-10-04T11:06", 4.18), post("2026-10-04", "b", "2026-10-03T09:00", 13.54)]
        got = td.tiktok_rewards_by_month(self.MONTHS, path=write_csv(rows))
        self.assertAlmostEqual(got["2026-10"], 29.65, places=2)
        self.assertEqual(got["2026-09"], 0.0)

    def test_per_post_total_wins_when_it_is_larger(self):
        rows = [acct("2026-10-01", 0.0), acct("2026-10-02", 2.0), post("2026-10-02", "a", "2026-10-01T11:06", 6.5)]
        self.assertAlmostEqual(td.tiktok_rewards_by_month(self.MONTHS, path=write_csv(rows))["2026-10"], 6.5, places=2)

    def test_earnings_land_in_the_month_of_their_snapshot_date(self):
        start = dt.date(2026, 9, 28)
        true = [1.0, 2.0, 3.0, 4.0, 5.0]  # Sep 28 29 30, Oct 1 2
        totals = window_totals(true, start)
        rows = [acct(d.isoformat(), t) for d, t in totals.items()]
        got = td.tiktok_rewards_by_month(self.MONTHS, path=write_csv(rows))
        self.assertAlmostEqual(got["2026-09"], 6.0, places=2)
        self.assertAlmostEqual(got["2026-10"], 9.0, places=2)

    def test_per_post_only_data_still_works_as_before(self):
        rows = [post("2026-10-02", "a", "2026-10-01T11:06", 1.25), post("2026-10-03", "a", "2026-10-01T11:06", 2.5)]
        self.assertAlmostEqual(td.tiktok_rewards_by_month(self.MONTHS, path=write_csv(rows))["2026-10"], 2.5, places=2)

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
