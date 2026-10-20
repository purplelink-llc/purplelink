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

    def test_account_windows_are_not_counted_and_months_follow_the_snapshot_day(self):
        # Account 7-day totals are ignored. The August post's estimate was first seen in an October snapshot, so it counts
        # in October: there is no earlier reading to place it.
        f = self.csv("2026-10-03,2026-10-03T21:00:00,nl,tiktok,account,Total,Last 7 days,USD,,,7.86,\n"
                     + post("2026-08-31", "old", "2026-08-30T10:00", 1.0) + post("2026-10-04", "old", "2026-08-30T10:00", 3.0)
                     + post("2026-10-04", "new", f"{THIS}-01T10:00", 4.0))
        out = td.tiktok_rewards_by_month(["2026-08", THIS], f)
        self.assertEqual(out, {"2026-08": 1.0, THIS: 6.0})

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
        # Same for the Getty estimate, which reads the live download ledger.
        getty = mock.patch.object(td, "getty_estimate_by_month", lambda months: {m: 0.0 for m in months})
        getty.start()
        self.addCleanup(getty.stop)

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


class GettyEstimate(unittest.TestCase):
    DL = [
        # premium x2 and one subscription, one premium already on a statement
        {"asset_id": "A", "last_download": "2026-10-11", "gi_premium": "2", "is_subscriptions": "1"},
        {"asset_id": "B", "last_download": "2026-10-05", "gi_premium": "0", "is_subscriptions": "1"},
        {"asset_id": "C", "last_download": "2026-08-20", "gi_premium": "1", "is_subscriptions": "0"},
    ]
    SALES = [
        {"asset_id": "C", "product_type": "Premium Access Time Limited", "gross_royalty": "1.00"},
        {"asset_id": "A", "product_type": "Premium Access Time Limited", "gross_royalty": "2.00"},
        {"asset_id": "B", "product_type": "iStock Subscription", "gross_royalty": "0.10"},
    ]

    def test_only_unstatemented_downloads_are_priced_at_the_average_rate(self):
        rows, rates = td.getty_unpriced_downloads(self.DL, self.SALES)
        self.assertAlmostEqual(rates["gi_premium"], 1.5)
        self.assertAlmostEqual(rates["is_subscriptions"], 0.10)
        got = {(r["asset_id"], r["column"]): (r["n"], r["est_cents"]) for r in rows}
        # A: 2 premium - 1 on a statement = 1 at $1.50; 1 subscription at $0.10. B's one subscription is on a statement.
        # C's premium is on a statement.
        self.assertEqual(got, {("A", "gi_premium"): (1, 150), ("A", "is_subscriptions"): (1, 10)})

    def test_a_type_with_no_statement_row_is_not_guessed(self):
        rows, rates = td.getty_unpriced_downloads(self.DL, [self.SALES[0]])
        self.assertEqual(set(rates), {"gi_premium"})
        self.assertTrue(all(r["column"] == "gi_premium" for r in rows))

    def test_by_month_and_sales_rows_and_total(self):
        with mock.patch.object(td, "_read_photo_csv", lambda name: self.DL if "downloads" in name else self.SALES):
            self.assertEqual(td.getty_estimate_by_month(["2026-09", "2026-10"]), {"2026-09": 0.0, "2026-10": 1.6})
        with mock.patch.object(td, "PHOTO_AN", Path(TMP) / "none"):
            self.assertEqual(td.photo_sale_rows(), [])
        # grouped into Photo licensing, not a source of its own, but still named as an estimate
        self.assertNotIn("getty_est", [k for k, _l, _c in td.REVENUE_SOURCES])
        with mock.patch.object(td, "photo_revenue_by_month", lambda months: {m: 5.0 for m in months}), \
             mock.patch.object(td, "getty_estimate_by_month", lambda months: {m: 1.6 for m in months}):
            s = td.revenue_series(None, None, [], None, [THIS])
        self.assertAlmostEqual(s["photo"][THIS], 6.6)
        self.assertAlmostEqual(s["getty_est"][THIS], 1.6)


class FaaLedgerTest(unittest.TestCase):
    LEDGER = [
        {"sale_date": "2026-10-19", "order_id": "7180079", "product": "Topiary T-Shirt", "buyer": "", "price": "2.0",
         "qty": "1", "total": "2.0"},
        {"sale_date": "2026-10-03", "order_id": "1-2", "product": "Flyover Print", "buyer": "Marietta, GA",
         "price": "44.0", "qty": "1", "total": "44.0"},
        {"sale_date": "2026-09-25", "order_id": "3-4", "product": "Card", "buyer": "Owner Purchase", "price": "",
         "qty": "1", "total": ""},
    ]

    def test_rows_skip_owner_purchases(self):
        rows = td.faa_sale_rows(self.LEDGER)
        self.assertEqual([(r["date"], r["detail"], r["net"]) for r in rows],
                         [("2026-10-19", "Fine Art America", 200), ("2026-10-03", "Fine Art America", 4400)])

    def test_monthly_total_takes_the_larger_reading_per_platform(self):
        class FakePD:
            # FAA balance rose only $1.60 in October (the sweep missed the $44 sale); Adobe rose $3.
            SNAP = {"2026-09-30": {"Fine Art America": 10.0, "Adobe Stock": 1.0},
                    "2026-10-20": {"Fine Art America": 11.6, "Adobe Stock": 4.0}}

            def load(self):
                return {d: {} for d in self.SNAP}

            def platform_money_asof(self, data, dates, asof):
                day = max(d for d in self.SNAP if d <= asof)
                return 0, 0, [(k, v) for k, v in self.SNAP[day].items()]

        with mock.patch.object(td, "_read_photo_csv", lambda name: self.LEDGER if name == "faa-sales.csv" else []), \
             mock.patch.object(td, "_load_photo_dashboard_module", lambda: FakePD()):
            got = td.photo_revenue_by_month(["2026-10"])
        # FAA: max(1.60 balance, 46.00 ledger) = 46.00, plus Adobe's 3.00; never 1.60 + 46.00
        self.assertAlmostEqual(got["2026-10"], 49.0)

    def test_faa_row_counts_paid_orders_and_takes_the_larger_total(self):
        # The control panel gives FAA a balance but no order count, so its row said 0 sales (2026-10-20).
        import importlib.util
        spec = importlib.util.spec_from_file_location("photo_dashboard_t", Path(__file__).resolve().parents[1] / "photo-dashboard.py")
        pd = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "argv", ["photo-dashboard.py"]):
            spec.loader.exec_module(pd)
        data = {"2026-09-30": {("fineartamerica", "balance"): 1.6}, "2026-10-19": {("fineartamerica", "balance"): 45.6}}
        dates = sorted(data)
        orders = [("2026-09-29", 1.6), ("2026-10-03", 44.0), ("2026-10-19", 2.0)]   # owner purchases are already left out
        with mock.patch.object(pd, "faa_orders", lambda: orders):
            faa = lambda asof: [r[:3] for r in pd.platform_money_asof(data, dates, asof)[2] if r[0] == "Fine Art America"][0]
            self.assertEqual(faa("2026-09-30"), ("Fine Art America", 1.6, 1))
            # balance $45.60 was read before the $2.00 order: the order list's $47.60 wins, and the count is 3
            self.assertEqual(faa("2026-10-19"), ("Fine Art America", 47.6, 3))
        with mock.patch.object(pd, "faa_orders", lambda: []):
            self.assertEqual(faa("2026-10-19"), ("Fine Art America", 45.6, None))   # no ledger: balance alone, as before

    def test_ledger_alone_when_photo_tracking_is_unavailable(self):
        def boom():
            raise FileNotFoundError("no photo-dashboard.py")
        with mock.patch.object(td, "_read_photo_csv", lambda name: self.LEDGER if name == "faa-sales.csv" else []), \
             mock.patch.object(td, "_load_photo_dashboard_module", boom):
            self.assertEqual(td.photo_revenue_by_month(["2026-09", "2026-10"]), {"2026-09": 0.0, "2026-10": 46.0})
