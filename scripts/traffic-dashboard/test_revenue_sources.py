#!/usr/bin/env python3
"""The all-sources revenue view: ExtensionPay as its own source, AdMob and TikTok shown as estimates.

    python3 scripts/traffic-dashboard/test_revenue_sources.py
"""
import contextlib
import datetime as dt
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="traffic-test-")
os.environ["PURPLELINK_TRAFFIC_DIR"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent))

import traffic_dashboard as td  # noqa: E402

THIS = dt.date.today().strftime("%Y-%m")
NOW = dt.datetime.now().timestamp()
HEADER = "snapshot_date,snapshot_at,pipeline,platform,level,program,window,currency,caption,posted_at,est_rewards,qualified_views\n"


def post(snap, caption, posted, est):
    return f"{snap},{snap}T21:00:00,nl,tiktok,post,Creator Rewards Program,,USD,{caption},{posted},{est},100\n"


def ext_row(gross=300, fee=58):
    return {"id": "extensionpay:ch_1", "kind": "order", "product": "scholar-belt", "site": "purplelink", "gross": gross, "fee": fee,
            "net": gross - fee, "refunded": 0, "ts": NOW, "market": "extensionpay"}


def etsy_row():
    return {"id": "etsy:1", "kind": "order", "product": "photo-print", "site": "purplelink", "gross": 2400, "fee": 300,
            "net": 2100, "refunded": 0, "ts": NOW, "market": "etsy"}


class TikTok(unittest.TestCase):
    def csv(self, text):
        f = Path(TMP) / "rewards.csv"
        f.write_text(HEADER + text)
        return f

    def test_a_post_counts_once_at_its_best_estimate(self):
        f = self.csv(post("2026-10-02", "a", f"{THIS}-02T10:00", 1.0) + post("2026-10-03", "a", f"{THIS}-02T10:00", 5.5)
                     + post("2026-10-04", "a", f"{THIS}-02T10:00", 5.5) + post("2026-10-04", "b", f"{THIS}-03T10:00", 2.25))
        self.assertEqual(td.tiktok_rewards_by_month([THIS], f), {THIS: 7.75})

    def test_account_windows_are_never_summed_and_other_months_stay_apart(self):
        # Two snapshots of the same rolling 7-day total are one 7.86, not 15.72. The account total (7.86) is larger than
        # the per-post sum (4.0) because the Monetization page lists only the newest posts, so it wins for this month.
        # August has no account rows, so its per-post figure stands and the months never mix.
        f = self.csv("2026-10-03,2026-10-03T21:00:00,nl,tiktok,account,Total,Last 7 days,USD,,,7.86,\n"
                     "2026-10-04,2026-10-04T21:00:00,nl,tiktok,account,Total,Last 7 days,USD,,,7.86,\n"
                     + post("2026-10-04", "old", "2026-08-30T10:00", 3.0) + post("2026-10-04", "new", f"{THIS}-01T10:00", 4.0))
        out = td.tiktok_rewards_by_month(["2026-08", THIS], f)
        self.assertEqual(out, {"2026-08": 3.0, THIS: 7.86})

    def test_missing_or_garbled_file_reads_zero(self):
        self.assertEqual(td.tiktok_rewards_by_month([THIS], Path(TMP) / "nope.csv"), {THIS: 0.0})
        f = self.csv("garbage\n" + post("2026-10-04", "x", f"{THIS}-01T10:00", "n/a"))
        self.assertEqual(td.tiktok_rewards_by_month([THIS], f), {THIS: 0.0})


class Sources(unittest.TestCase):
    def setUp(self):
        # revenue_series reads one thing that is not passed in: real photo-licensing revenue, from the live
        # photo-licensing-workspace snapshots. Pin it so every figure below comes from what the test supplies and the
        # test cannot drift as that data changes. (TikTok is pointed at a temp CSV inside the test that needs it.)
        patcher = mock.patch.object(td, "photo_revenue_by_month", lambda months: {m: 0.0 for m in months})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_extensionpay_is_its_own_source_not_a_marketplace(self):
        rows = [etsy_row(), ext_row()]
        s = td.revenue_series(None, None, rows, None, [THIS])
        self.assertEqual(s["marketplaces"][THIS], 24.0)
        self.assertEqual(s["extpay"][THIS], 3.0)
        sales = td.all_sales_rows(rows, None)
        by_detail = {r["detail"]: r for r in sales}
        self.assertEqual(by_detail["Scholar Utility Belt Pro"]["source"], "Chrome extension (ExtensionPay)")
        self.assertEqual(by_detail["Scholar Utility Belt Pro"]["item"], "Scholar Utility Belt Pro")
        self.assertEqual(by_detail["Etsy"]["source"], "Etsy, Gumroad, Payhip")
        self.assertIn("Chrome extension (ExtensionPay)", td.all_sales_block(rows, None))

    def test_admob_months(self):
        admob = {"globepin": {"monthly": {THIS: 0.2, "2026-08": 1.5}}}
        self.assertEqual(td.admob_revenue_by_month(admob, ["2026-08", "2026-09", THIS]), {"2026-08": 1.5, "2026-09": 0.0, THIS: 0.2})
        self.assertEqual(td.admob_revenue_by_month(None, [THIS]), {THIS: 0.0})

    def test_block_and_report_line_name_the_estimates(self):
        admob = {"globepin": {"monthly": {THIS: 0.2}}}
        real = td.TIKTOK_REWARDS_CSV
        f = Path(TMP) / "r2.csv"
        f.write_text(HEADER + post("2026-10-04", "a", f"{THIS}-01T10:00", 5.0))
        td.TIKTOK_REWARDS_CSV = f
        try:
            html_out = td.revenue_block(None, None, market_rows=[ext_row()], admob=admob)
            self.assertIn("Ad revenue (est.)", html_out)
            self.assertIn("TikTok Creator Rewards (est.)", html_out)
            self.assertIn("includes $5.20 of estimates", html_out)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                td.print_revenue_sources(None, None, [ext_row()], admob)
            text = out.getvalue()
            self.assertIn("$8.20 (", text)
            self.assertIn("$3.00 received or sold, $5.20 estimated", text)
            self.assertIn("Chrome extension (ExtensionPay) $3.00", text)
            self.assertIn("Ad revenue (est.) $0.20", text)
            self.assertIn("TikTok Creator Rewards (est.) $5.00", text)
        finally:
            td.TIKTOK_REWARDS_CSV = real


if __name__ == "__main__":
    unittest.main()
