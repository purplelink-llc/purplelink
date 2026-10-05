#!/usr/bin/env python3
"""Offline tests for the ExtensionPay (Scholar Utility Belt Pro) reader.

    python3 scripts/traffic-dashboard/test_extensionpay.py

Fixtures are constructed from Stripe's documented Charge and Subscription shapes; ids and amounts are invented.
They contain no buyer data. Re-check against a real charge when the first sale arrives.
"""
import contextlib
import datetime as dt
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="traffic-test-")
os.environ["PURPLELINK_TRAFFIC_DIR"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parent))

import traffic_dashboard as td  # noqa: E402

NOW = int(dt.datetime.now().timestamp())


def charge(cid, amount=1900, created=NOW - 3600, fee=87, **kw):
    c = {"id": cid, "amount": amount, "currency": "usd", "paid": True, "status": "succeeded", "created": created,
         "amount_refunded": 0, "refunded": False, "description": "Scholar Utility Belt: lifetime",
         "balance_transaction": {"id": "txn_" + cid, "fee": fee}}
    c.update(kw)
    return c


def sub(amount, interval, count=1, qty=1):
    return {"items": {"data": [{"quantity": qty, "price": {"unit_amount": amount, "recurring": {"interval": interval, "interval_count": count}}}]}}


class Parse(unittest.TestCase):
    def test_paid_charge(self):
        r = td.parse_stripe_charge(charge("ch_1"))
        self.assertEqual((r["id"], r["gross"], r["fee"], r["refunded"]), ("ch_1", 1900, 87, 0))
        self.assertEqual(r["title"], "Scholar Utility Belt: lifetime")

    def test_not_a_sale(self):
        for bad in (charge("a", paid=False), charge("b", status="failed"), charge("c", amount=0), charge("d", currency="eur"), {"id": "x"}, {}):
            self.assertIsNone(td.parse_stripe_charge(bad))

    def test_unexpanded_fee_and_refund(self):
        r = td.parse_stripe_charge(charge("ch_2", balance_transaction="txn_1", refunded=True))
        self.assertIsNone(r["fee"])
        self.assertEqual(r["refunded"], 1900)                         # fully refunded with no amount reported
        r = td.parse_stripe_charge(charge("ch_3", amount_refunded=500))
        self.assertEqual(r["refunded"], 500)

    def test_monthly_equivalents(self):
        self.assertEqual(td._monthly_cents(sub(300, "month")), 300)
        self.assertEqual(td._monthly_cents(sub(2400, "year")), 200)
        self.assertEqual(td._monthly_cents(sub(600, "month", count=2)), 300)
        self.assertEqual(td._monthly_cents(sub(300, "month", qty=2)), 600)
        self.assertEqual(td._monthly_cents({"items": {"data": [{"price": {"unit_amount": 5}}]}}), 0)


class Fetch(unittest.TestCase):
    def setUp(self):
        self.real = td._stripe_get

    def tearDown(self):
        td._stripe_get = self.real

    def test_no_key_is_none(self):
        self.assertIsNone(td.fetch_extpay({}))

    def test_pages_and_subscriptions(self):
        calls = []

        def fake(key, path, params):
            calls.append((path, dict(params)))
            if path == "charges":
                if "starting_after" not in params:
                    return {"data": [charge("ch_1"), charge("ch_bad", paid=False)], "has_more": True}
                return {"data": [charge("ch_2", amount=300)], "has_more": False}
            if params["status"] == "active":
                return {"data": [sub(300, "month"), sub(2400, "year")], "has_more": False}
            return {"data": [sub(300, "month")], "has_more": False}
        td._stripe_get = fake
        r = td.fetch_extpay({"STRIPE_EXTPAY_KEY": "rk_test_x"})
        self.assertEqual([o["id"] for o in r["orders"]], ["ch_1", "ch_2"])
        self.assertEqual(r["skipped"], 1)
        self.assertEqual(r["subs"], {"active": 2, "trialing": 1, "mrr": 500})
        self.assertEqual(calls[1][1]["starting_after"], "ch_bad")

    def test_charge_failure_is_an_error_and_subscription_failure_is_not(self):
        def boom(key, path, params):
            raise RuntimeError("HTTP 403 (key rejected or missing a permission)")
        td._stripe_get = boom
        self.assertIn("403", td.fetch_extpay({"STRIPE_EXTPAY_KEY": "k"})["error"])

        def charges_only(key, path, params):
            if path == "charges":
                return {"data": [charge("ch_1")], "has_more": False}
            raise RuntimeError("HTTP 403")
        td._stripe_get = charges_only
        r = td.fetch_extpay({"STRIPE_EXTPAY_KEY": "k"})
        self.assertEqual(len(r["orders"]), 1)
        self.assertIsNone(r["subs"])


class Merge(unittest.TestCase):
    def setUp(self):
        self.real = td.fetch_extpay

    def tearDown(self):
        td.fetch_extpay = self.real

    def result(self, subs=True):
        return {"orders": [td.parse_stripe_charge(charge("ch_1")), td.parse_stripe_charge(charge("ch_old", amount=900, created=NOW - 40 * 86400))],
                "skipped": 0, "subs": {"active": 1, "trialing": 0, "mrr": 300} if subs else None,
                "asOf": dt.datetime.now(dt.timezone.utc).isoformat()}

    def test_rows_group_profit_and_summary(self):
        td.fetch_extpay = lambda cfg: self.result()
        hist = {"sites": {}, "ledger": {}}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            events, changed = td.marketplace_step(hist, {"STRIPE_EXTPAY_KEY": "k"}, fetch=True)
        self.assertTrue(changed)
        self.assertIn("ok ExtensionPay (Stripe): 2 paid charge(s) read", out.getvalue())
        row = hist["ledger"]["extensionpay:ch_1"]
        self.assertEqual((row["product"], row["market"], row["gross"], row["fee"], row["net"], row["feeEstimated"]), ("scholar-belt", "extensionpay", 1900, 87, 1813, False))
        self.assertEqual(td.product_group(row), "Scholar Utility Belt Pro")
        self.assertEqual(len(events), 1)                                # only the charge from the last 48 hours is a feed event
        with contextlib.redirect_stdout(io.StringIO()):
            td.marketplace_step(hist, {"STRIPE_EXTPAY_KEY": "k"}, fetch=True)   # a second run does not duplicate rows
        self.assertEqual(len([k for k in hist["ledger"] if k.startswith("extensionpay:")]), 2)
        s = td.marketplace_summary(hist)
        self.assertEqual((s["extensionpay"]["orders"], s["extensionpay"]["windowOrders"], s["extensionpay"]["windowNet"]), (2, 1, 1813))
        p = td.profit_view(hist, {})
        line = next(r for r in p["rows"] if r["line"] == "Scholar Utility Belt Pro")
        self.assertAlmostEqual(line["revenue"], 18.13)

    def test_quiet_without_a_key(self):
        td.fetch_extpay = lambda cfg: None
        hist = {"sites": {}, "ledger": {}}
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            td.marketplace_step(hist, {}, fetch=True)
        self.assertNotIn("ExtensionPay", err.getvalue())
        self.assertNotIn("extensionpay", td.marketplace_summary(hist))   # no row and no "never read" gap for a source not set up
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            td.print_extensionpay(hist)
        self.assertEqual(out.getvalue(), "")

    def test_error_is_reported_once_and_does_not_hide_stored_rows(self):
        td.fetch_extpay = lambda cfg: self.result()
        hist = {"sites": {}, "ledger": {}}
        with contextlib.redirect_stdout(io.StringIO()):
            td.marketplace_step(hist, {"STRIPE_EXTPAY_KEY": "k"}, fetch=True)
        td.fetch_extpay = lambda cfg: {"error": "HTTP 401 (key rejected or missing a permission)"}
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            td.marketplace_step(hist, {"STRIPE_EXTPAY_KEY": "k"}, fetch=True)
        self.assertIn("ExtensionPay (Stripe): HTTP 401", err.getvalue())
        s = td.marketplace_summary(hist)["extensionpay"]
        self.assertEqual(s["orders"], 2)                                 # stored orders stay
        self.assertTrue(any("401" in i for i in s["issues"]))

    def test_report_lines(self):
        td.fetch_extpay = lambda cfg: self.result()
        hist = {"sites": {}, "ledger": {}, "chromeWebStore": {"users": "1,000"}}
        with contextlib.redirect_stdout(io.StringIO()):
            td.marketplace_step(hist, {"STRIPE_EXTPAY_KEY": "k"}, fetch=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            td.print_extensionpay(hist)
        text = out.getvalue()
        self.assertIn("Web Store users 1,000 (rounded) -> 2 paid charge(s) all time (0.2% of installs)", text)
        self.assertIn("Last 30d: 1 charge(s)", text)
        self.assertIn("Subscriptions: 1 active, 0 trialing, MRR $3", text)


if __name__ == "__main__":
    unittest.main()
