#!/usr/bin/env python3
"""Every source's revenue per day, archived in history.json, exported as CSV and drawn on the Overview.

    python3 scripts/traffic-dashboard/test_revenue_daily.py
"""
import csv
import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="traffic-test-")
os.environ["PURPLELINK_TRAFFIC_DIR"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent))

import traffic_dashboard as td  # noqa: E402


def row(date, source, net, estimate=False):
    return {"date": date, "source": source, "detail": "", "item": "", "gross": None, "net": net, "estimate": estimate}


class Archive(unittest.TestCase):
    def test_days_and_sources_split_received_from_estimated(self):
        h = {}
        a = td.archive_revenue_daily(h, [row("2026-10-19", "Photo licensing", 200), row("2026-10-19", "Photo licensing", 50),
                                         row("2026-10-19", td.SRC_TIKTOK, 298, True), row("bad", "x", 9)])
        self.assertEqual(a, {"2026-10-19": {"Photo licensing": {"received": 250, "estimated": 0},
                                            td.SRC_TIKTOK: {"received": 0, "estimated": 298}}})
        self.assertIs(h["revenueDaily"], a)

    def test_a_source_missing_from_a_later_run_keeps_its_past_days(self):
        h = {}
        td.archive_revenue_daily(h, [row("2026-10-18", td.SRC_TIKTOK, 396, True), row("2026-10-18", "App Store", 100)])
        # TikTok's file is gone this run; App Store's figure for the day was revised.
        td.archive_revenue_daily(h, [row("2026-10-18", "App Store", 120)])
        self.assertEqual(h["revenueDaily"]["2026-10-18"], {td.SRC_TIKTOK: {"received": 0, "estimated": 396},
                                                          "App Store": {"received": 120, "estimated": 0}})

    def test_csv(self):
        a = {"2026-10-19": {"Photo licensing": {"received": 200, "estimated": 0}, td.SRC_TIKTOK: {"received": 0, "estimated": 298}}}
        f = Path(TMP) / "revenue_daily.csv"
        td.write_revenue_daily_csv(a, f)
        got = list(csv.DictReader(f.open()))
        self.assertEqual([(r["date"], r["source"], r["received"], r["estimated"], r["total"]) for r in got],
                         [("2026-10-19", "Photo licensing", "2.00", "0.00", "2.00"),
                          ("2026-10-19", td.SRC_TIKTOK, "0.00", "2.98", "2.98")])


class Block(unittest.TestCase):
    TODAY = dt.date(2026, 10, 20)

    def test_chart_and_figures(self):
        a = {"2026-10-20": {"App Store": {"received": 500, "estimated": 0}},
             "2026-10-18": {td.SRC_TIKTOK: {"received": 0, "estimated": 298}},
             "2026-09-01": {"App Store": {"received": 99999, "estimated": 0}}}  # outside the 30 days
        out = td.daily_revenue_block(a, self.TODAY)
        self.assertIn("$5</b> <span>today", out)
        self.assertIn("$7.98</b> <span>last 7 days", out)
        self.assertIn("last 30 days ($2.98 estimated)", out)
        self.assertEqual(out.count("<title>"), 30)
        self.assertIn("2026-10-18: $0 sold or received, $2.98 estimated", out)

    def test_nothing_to_show_is_empty(self):
        self.assertEqual(td.daily_revenue_block({}, self.TODAY), "")
        self.assertEqual(td.daily_revenue_block(None, self.TODAY), "")


if __name__ == "__main__":
    unittest.main()
