#!/usr/bin/env python3
"""The all-sales list itemises every revenue source: TikTok and AdMob estimates, balance-only photo platforms, and a
per-day table built from the same rows.

    python3 scripts/traffic-dashboard/test_all_sales_daily.py
"""
import datetime as dt
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="traffic-test-")
os.environ["PURPLELINK_TRAFFIC_DIR"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent))

import traffic_dashboard as td  # noqa: E402

HEADER = "snapshot_date,snapshot_at,pipeline,platform,level,program,window,currency,caption,posted_at,est_rewards,qualified_views\n"


def acct(day, total, pipe="nl"):
    return f"{day},{day}T21:00:00,{pipe},tiktok,account,Total,Last 7 days,USD,,,{total},\n"


def post(snap, caption, posted, est, pipe="nl"):
    return f"{snap},{snap}T21:00:00,{pipe},tiktok,post,Creator Rewards Program,,USD,{caption},{posted},{est},100\n"


_REAL_PHOTO_MODULE = td._load_photo_dashboard_module()


def fake_photo_module(data):
    """photo-dashboard's real carry-forward helper over invented snapshots."""
    real = _REAL_PHOTO_MODULE
    return types.SimpleNamespace(load=lambda: data, platform_money_asof=real.platform_money_asof)


class TikTokRows(unittest.TestCase):
    def csv(self, text):
        f = Path(TMP) / "rewards.csv"
        f.write_text(HEADER + text)
        return f

    def test_one_estimate_row_per_day_per_pipeline_and_zero_days_skipped(self):
        # nl: 7-day totals 7, 7, 7 -> day 1 gets 7, then each new day replaces the day leaving the window (none yet), so
        # 0 and 0. A second pipeline has its own rows.
        f = self.csv(acct("2026-10-01", 7.0) + acct("2026-10-02", 7.0) + acct("2026-10-03", 9.0)
                     + acct("2026-10-02", 3.0, pipe="aita"))
        rows = td.tiktok_sale_rows(f)
        self.assertTrue(all(r["estimate"] and r["source"] == td.SRC_TIKTOK for r in rows))
        self.assertEqual({(r["date"], r["detail"]): r["net"] for r in rows},
                         {("2026-10-01", "nl"): 700, ("2026-10-03", "nl"): 200, ("2026-10-02", "aita"): 300})
        self.assertEqual(rows[0]["item"], "Creator Rewards estimate for the day")
        self.assertFalse(any(r["date"] < "2026-10-01" for r in rows))

    def test_a_negative_day_is_kept_so_rows_add_up_to_the_month(self):
        # Studio lowered the second total: that day comes out negative. Dropping it would make the rows exceed
        # tiktok_rewards_by_month, so it stays, labelled.
        f = self.csv(acct("2026-10-01", 5.0) + acct("2026-10-02", 3.0))
        rows = td.tiktok_sale_rows(f)
        self.assertEqual(sorted(r["net"] for r in rows), [-200, 500])
        self.assertIn("negative", [r for r in rows if r["net"] < 0][0]["item"])
        self.assertAlmostEqual(sum(r["net"] for r in rows) / 100, td.tiktok_rewards_by_month(["2026-10"], f)["2026-10"], places=2)

    def test_rows_match_the_monthly_figure_when_the_account_reading_wins(self):
        f = self.csv(acct("2026-10-01", 4.0) + acct("2026-10-02", 6.5) + acct("2026-10-03", 6.5)
                     + post("2026-10-03", "a", "2026-10-01T10:00", 1.0))
        rows = td.tiktok_sale_rows(f)
        self.assertEqual(sum(r["net"] for r in rows), 650)
        self.assertEqual(td.tiktok_rewards_by_month(["2026-10"], f), {"2026-10": 6.5})
        self.assertIn("the two agree", td.tiktok_month_note(rows, f))

    def test_note_names_a_month_where_the_per_post_reading_is_higher(self):
        f = self.csv(acct("2026-10-01", 2.0) + post("2026-10-03", "a", "2026-10-01T10:00", 5.0))
        rows = td.tiktok_sale_rows(f)
        self.assertEqual(sum(r["net"] for r in rows), 200)
        self.assertEqual(td.tiktok_rewards_by_month(["2026-10"], f), {"2026-10": 5.0})
        note = td.tiktok_month_note(rows, f)
        self.assertIn("higher than the rows for October 2026", note)
        self.assertIn("$5 counted", note)
        self.assertIn("$2 in the rows", note)

    def test_missing_file_gives_no_rows(self):
        self.assertEqual(td.tiktok_sale_rows(Path(TMP) / "nope.csv"), [])
        self.assertEqual(td.tiktok_month_note([]), "")


class AdMobRows(unittest.TestCase):
    TODAY = dt.date(2026, 10, 20)

    def test_one_row_per_month_dated_its_last_day_with_data(self):
        admob = {"globepin": {"monthly": {"2026-08": 1.5, "2026-09": 0.0, "2026-10": 0.2, "2026-11": 9.0}}}
        rows = td.admob_month_rows(admob, self.TODAY)
        self.assertEqual([(r["date"], r["net"]) for r in rows], [("2026-08-31", 150), ("2026-10-20", 20)])
        self.assertTrue(all(r["estimate"] and r["source"] == td.SRC_ADS for r in rows))
        self.assertIn("month total for August 2026", rows[0]["item"])

    def test_nothing_without_data_or_after_an_api_error(self):
        self.assertEqual(td.admob_month_rows(None, self.TODAY), [])
        self.assertEqual(td.admob_month_rows({"globepin": {"error": "HTTP 401"}}, self.TODAY), [])

    def test_rows_equal_the_monthly_series(self):
        admob = {"globepin": {"monthly": {"2026-09": 1.234, "2026-10": 0.2}}}
        series = td.admob_revenue_by_month(admob, ["2026-09", "2026-10"])
        rows = td.admob_month_rows(admob, self.TODAY)
        for r in rows:
            self.assertAlmostEqual(r["net"] / 100, series[r["date"][:7]], places=2)


class BalanceRows(unittest.TestCase):
    def data(self):
        # Alamy: 5 -> 7 (rise 2) -> 1 (payout) -> 4 (rise 3, measured from 1). Vecteezy only steps up once.
        # Getty has a per-sale ledger, so its balance is not turned into rows.
        return {
            "2026-09-30": {("alamy", "balance"): 5.0, ("vecteezy", "balance"): 1.0, ("getty", "balance"): 10.0},
            "2026-10-05": {("alamy", "balance"): 7.0},
            "2026-10-10": {("alamy", "balance"): 1.0},
            "2026-10-12": {("alamy", "balance"): 4.0, ("vecteezy", "balance"): 1.5, ("getty", "balance"): 12.0},
        }

    def rows(self):
        listed = [{"source": "Photo licensing", "detail": "Getty / iStock", "item": "x", "net": 1, "date": "2026-10-01", "gross": None}]
        with mock.patch.object(td, "_load_photo_dashboard_module", lambda: fake_photo_module(self.data())):
            return td.photo_balance_rows(listed)

    def test_a_rise_is_a_row_and_a_payout_is_not_negative_revenue(self):
        got = [(r["date"], r["detail"], r["net"]) for r in self.rows() if r["detail"] == "Alamy"]
        # The first snapshot reads as a rise from nothing, matching how the monthly figure starts from zero.
        self.assertEqual(sorted(got), [("2026-09-30", "Alamy", 500), ("2026-10-05", "Alamy", 200), ("2026-10-12", "Alamy", 300)])

    def test_row_shape(self):
        r = [r for r in self.rows() if r["date"] == "2026-10-05"][0]
        self.assertEqual((r["source"], r["item"], r["gross"]), ("Photo licensing", "balance rose (sale not itemised by the platform)", None))
        self.assertFalse(r.get("estimate"))

    def test_platform_with_a_ledger_is_skipped(self):
        self.assertFalse([r for r in self.rows() if r["detail"].startswith("Getty")])

    def test_october_rows_versus_the_monthly_photo_figure(self):
        # Documented relationship: rows add the rises (2 + 3 + 0.5 = 5.5); the monthly figure is the net balance change
        # per platform, floored at 0 (Alamy 4 - 5 -> 0, Vecteezy 0.5), so the rows are never below it.
        data = self.data()
        with mock.patch.object(td, "_load_photo_dashboard_module", lambda: fake_photo_module(data)), \
                mock.patch.object(td, "_read_photo_csv", lambda name: []):
            monthly = td.photo_revenue_by_month(["2026-10"])["2026-10"]
            oct_rows = [r for r in td.photo_balance_rows([]) if r["date"].startswith("2026-10") and r["detail"] != "Getty / iStock"]
        by_platform = {}
        for r in oct_rows:
            by_platform[r["detail"]] = by_platform.get(r["detail"], 0) + r["net"] / 100
        self.assertEqual(by_platform["Alamy"], 5.0)
        self.assertEqual(by_platform["Vecteezy"], 0.5)
        self.assertGreaterEqual(sum(by_platform.values()) + 2.0, monthly)  # + Getty's 2.0 rise, which has no rows here
        self.assertEqual(monthly, 2.5)

    def test_without_photo_tracking_there_are_no_rows(self):
        with mock.patch.object(td, "_load_photo_dashboard_module", side_effect=FileNotFoundError("none")):
            self.assertEqual(td.photo_balance_rows([]), [])


class ByDay(unittest.TestCase):
    TODAY = dt.date(2026, 10, 20)

    def rows(self):
        return [
            {"date": "2026-10-20", "source": "App Store", "detail": "x", "item": "i", "gross": None, "net": 250},
            {"date": "2026-10-20", "source": td.SRC_TIKTOK, "detail": "nl", "item": "i", "gross": None, "net": 100, "estimate": True},
            {"date": "2026-10-18", "source": "Photo licensing", "detail": "Alamy", "item": "i", "gross": None, "net": 40},
            {"date": "2026-08-01", "source": "Photo licensing", "detail": "Alamy", "item": "i", "gross": None, "net": 999},
            {"date": "2026-10-25", "source": "Photo licensing", "detail": "Alamy", "item": "i", "gross": None, "net": 777},
        ]

    def test_days_are_newest_first_and_split_received_from_estimated(self):
        days = td.all_sales_by_day(self.rows(), self.TODAY)
        self.assertEqual(len(days), 60)
        self.assertEqual(days[0], {"date": "2026-10-20", "received": 250, "estimated": 100, "total": 350})
        self.assertEqual(days[1], {"date": "2026-10-19", "received": 0, "estimated": 0, "total": 0})
        self.assertEqual(days[2]["received"], 40)

    def test_window_totals_equal_the_rows_inside_it(self):
        days = td.all_sales_by_day(self.rows(), self.TODAY)
        self.assertEqual(sum(d["received"] for d in days), 290)
        self.assertEqual(sum(d["estimated"] for d in days), 100)
        self.assertEqual(sum(d["total"] for d in days), 390)


class Block(unittest.TestCase):
    def setUp(self):
        for name, repl in (("photo_sale_rows", lambda: []), ("photo_balance_rows", lambda listed: []),
                           ("photo_totals_only_note", lambda listed: "")):
            p = mock.patch.object(td, name, repl)
            p.start()
            self.addCleanup(p.stop)
        self.csv = Path(TMP) / "block-rewards.csv"
        self.csv.write_text(HEADER + acct("2026-10-19", 4.0) + acct("2026-10-20", 6.0))
        p = mock.patch.object(td, "TIKTOK_REWARDS_CSV", self.csv)
        p.start()
        self.addCleanup(p.stop)

    def ledger(self):
        ts = dt.datetime(2026, 10, 20, 12).timestamp()
        return [{"id": "s1", "kind": "purchase", "product": "x", "site": "purplelink", "gross": 2000, "fee": 100,
                 "net": 1900, "refunded": 0, "ts": ts}]

    def test_every_source_is_a_chip_and_the_three_totals_are_separate(self):
        admob = {"globepin": {"monthly": {"2026-10": 0.5}}}
        out = td.all_sales_block(self.ledger(), None, admob, dt.date(2026, 10, 20))
        for src in (td.SRC_TIKTOK, td.SRC_ADS):
            self.assertIn(f'data-src="{src}"', out)
        # Received 19.00; estimated 4.00 + 2.00 (TikTok) + 0.50 (AdMob) = 6.50; combined 25.50.
        self.assertIn("$19 received or sold", out)
        self.assertIn("$6.50 estimated", out)
        self.assertIn("$25.50 combined", out)
        self.assertIn("Estimated (~, not received)", out)
        self.assertIn("~$6.50", out)

    def test_by_day_table_uses_the_same_rows(self):
        admob = {"globepin": {"monthly": {"2026-10": 0.5}}}
        today = dt.date(2026, 10, 20)
        rows = td.all_sales_rows(self.ledger(), None, admob, today)
        days = td.all_sales_by_day(rows, today)
        self.assertEqual(sum(d["total"] for d in days), sum(r["net"] for r in rows))
        out = td.all_sales_block(self.ledger(), None, admob, today)
        self.assertIn("By day", out)
        self.assertIn("<td class='who'>2026-10-20</td>", out)

    def test_old_call_shape_still_works(self):
        self.assertIn("All sales", td.all_sales_block(self.ledger(), None))


class Reconciliation(unittest.TestCase):
    """One month, every source, rows against revenue_series (the monthly all-sources figure)."""
    M = "2026-10"

    def test_rows_add_up_to_the_series_per_source(self):
        csv_path = Path(TMP) / "recon-rewards.csv"
        csv_path.write_text(HEADER + acct("2026-10-01", 4.0) + acct("2026-10-02", 6.5) + acct("2026-10-03", 6.5, pipe="aita"))
        ts = dt.datetime(2026, 10, 5, 12).timestamp()
        ledger = [
            {"id": "s1", "kind": "purchase", "product": "x", "site": "purplelink", "gross": 2000, "fee": 100, "net": 1900, "refunded": 0, "ts": ts},
            {"id": "e1", "kind": "order", "product": "scholar-belt", "gross": 300, "fee": 58, "net": 242, "refunded": 0, "ts": ts, "market": "extensionpay"},
            {"id": "m1", "kind": "order", "product": "photo-print", "gross": 2400, "fee": 300, "net": 2100, "refunded": 0, "ts": ts, "market": "etsy"},
        ]
        appstore = {"days": {"2026-10-06": {"proceeds": {"USD": 3.5}, "proUnits": 1}}}
        admob = {"globepin": {"monthly": {self.M: 0.75}}}
        data = {"2026-09-30": {("alamy", "balance"): 1.0}, "2026-10-04": {("alamy", "balance"): 3.0}}
        with mock.patch.object(td, "TIKTOK_REWARDS_CSV", csv_path), \
                mock.patch.object(td, "_load_photo_dashboard_module", lambda: fake_photo_module(data)), \
                mock.patch.object(td, "_read_photo_csv", lambda name: []), \
                mock.patch.object(td, "photo_sale_rows", lambda: []), \
                mock.patch.object(td, "getty_estimate_by_month", lambda months: {m: 0.0 for m in months}):
            rows = td.all_sales_rows(ledger, appstore, admob, dt.date(2026, 10, 20))
            series = td.revenue_series(None, appstore, ledger[1:], admob, [self.M])  # market_rows are marketplace orders only
        by, gross = {}, {}
        for r in rows:
            if r["date"].startswith(self.M):
                by[r["source"]] = by.get(r["source"], 0) + r["net"] / 100
                gross[r["source"]] = gross.get(r["source"], 0) + (r["gross"] or 0) / 100
        self.assertAlmostEqual(by["App Store"], series["appstore"][self.M], places=2)
        # Marketplace and ExtensionPay months count the gross sale; the list's Kept column is net of fees, its Gross
        # column is what the series adds up. That difference predates these rows.
        self.assertAlmostEqual(gross["Chrome extension (ExtensionPay)"], series["extpay"][self.M], places=2)
        self.assertAlmostEqual(gross["Etsy, Gumroad, Payhip"], series["marketplaces"][self.M], places=2)
        self.assertAlmostEqual(by["Chrome extension (ExtensionPay)"], 2.42, places=2)
        self.assertAlmostEqual(by[td.SRC_ADS], series["ads"][self.M], places=2)
        # Photo: a single rise with no payout, so the rows equal the month's balance change (3.0 - 1.0).
        self.assertAlmostEqual(by["Photo licensing"], series["photo"][self.M], places=2)
        # TikTok: the rebuilt daily rows are what the series counts here (the account reading is the larger).
        self.assertAlmostEqual(by[td.SRC_TIKTOK], series["tiktok"][self.M], delta=0.02)
        self.assertGreater(by[td.SRC_TIKTOK], 0)


if __name__ == "__main__":
    unittest.main()
