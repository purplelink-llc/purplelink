#!/usr/bin/env python3
"""Offline tests for the marketplace readers and their dashboard merge.

    python3 scripts/traffic-dashboard/test_marketplaces.py

Fixtures are CONSTRUCTED, not recorded: on 2026-09-29 the Etsy, Gumroad and Payhip
accounts had no orders yet, so the row shapes below follow each site's documented
or expected layout with invented ids, dates and amounts. They contain no buyer
data. Re-check the parsers against a real order when the first one arrives.
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="traffic-test-")
os.environ["PURPLELINK_TRAFFIC_DIR"] = TMP          # never touch the real archive
sys.path.insert(0, str(Path(__file__).resolve().parent))

import record_marketplaces as rm  # noqa: E402
import traffic_dashboard as td  # noqa: E402

NOW = dt.datetime.now()
TODAY = NOW.strftime("%b %d, %Y").replace(" 0", " ")

ETSY_ROWS = [
    {"href": "https://www.etsy.com/your/orders/sold/3100000001", "listings": ["Tenure Tracker Spreadsheet, Promotion Dossier Planner"],
     "text": f"Order #3100000001\n{TODAY}\nTenure Tracker Spreadsheet, Promotion Dossier Planner\n$12.00"},
    {"href": "https://www.etsy.com/your/orders/sold/3100000002", "listings": ["Sunset over Lake, Fine Art Print"],
     "text": f"Order #3100000002\n{TODAY}\nSunset over Lake, Fine Art Print\n$24.00"},
    {"href": "https://www.etsy.com/your/orders/sold/3100000001", "listings": [], "text": "duplicate link"},
]
ETSY_DETAIL = """Order #3100000001
Item total
$12.00
Order total
$12.00
Transaction fee
-$0.78
Processing fee
-$0.61
Net
$10.61
"""
PAYHIP_TABLE = (["Order", "Date", "Product", "Customer email", "Total", "Status"],
                [["PH-1001", "2026-09-29 14:05", "Academic Job Market Tracker", "x@example.invalid", "$9.00", "Paid"],
                 ["PH-1002", "2026-09-29 15:10", "Grant Pipeline Tracker", "y@example.invalid", "$12.00", "Refunded"],
                 ["short"]])
GUMROAD_TABLE = (["Date", "Product", "Amount"],
                 [["Sep 29, 2026", "Researcher Spreadsheet Bundle", "$29.00"],
                  ["Sep 29, 2026", "Researcher Spreadsheet Bundle", "$29.00"]])


class Parsers(unittest.TestCase):
    def test_money_and_dates(self):
        self.assertEqual(rm.parse_money("Paid $1,234.50 total"), 123450)
        self.assertEqual(rm.parse_money("-$0.78"), -78)
        self.assertIsNone(rm.parse_money("no price"))
        d = dt.datetime.fromtimestamp(rm.parse_date("Sep 29, 2026, 3:04 PM"))
        self.assertEqual((d.month, d.day, d.hour, d.minute), (9, 29, 15, 4))
        self.assertEqual(dt.datetime.fromtimestamp(rm.parse_date("2026-09-29")).hour, 12)
        self.assertEqual(dt.datetime.fromtimestamp(rm.parse_date("9/29/2026")).day, 29)

    def test_etsy_rows(self):
        o = rm.parse_etsy_rows(ETSY_ROWS)
        self.assertEqual([x["id"] for x in o], ["3100000001", "3100000002"])
        self.assertEqual(o[0]["gross"], 1200)
        self.assertTrue(o[0]["title"].startswith("Tenure"))
        self.assertNotIn("buyer", json.dumps(o))

    def test_etsy_detail_fees(self):
        d = rm.parse_etsy_detail(ETSY_DETAIL)
        self.assertEqual((d["gross"], d["fee"], d["net"]), (1200, 139, 1061))
        self.assertNotIn("fee", rm.parse_etsy_detail("Order total\n$12.00\n"))

    def test_tables_by_header_name(self):
        o = rm.parse_table(*PAYHIP_TABLE, "payhip")
        self.assertEqual([x["id"] for x in o], ["PH-1001", "PH-1002"])
        self.assertEqual(o[1]["refunded"], 1200)
        self.assertNotIn("example.invalid", json.dumps(o))          # email column never kept
        g = rm.parse_table(*GUMROAD_TABLE, "gumroad")
        self.assertEqual(len(g), 2)
        self.assertNotEqual(g[0]["id"], g[1]["id"])                 # identical rows stay distinct
        self.assertEqual(g[0]["id"], rm.parse_table(*GUMROAD_TABLE, "gumroad")[0]["id"])  # and stable
        self.assertEqual(rm.parse_table(["Foo"], [["x"]], "payhip"), [])

    def test_page_state(self):
        self.assertEqual(rm.classify_page("https://www.etsy.com/signin?x", "", False), "signed out")
        self.assertEqual(rm.classify_page("https://payhip.com/orders", "Email\nPassword", True), "signed out")
        self.assertEqual(rm.classify_page("https://payhip.com/x", "404 Page Not Found", False), "not found")
        self.assertEqual(rm.classify_page("https://payhip.com/orders", "Orders\n...", False), "ok")
        self.assertTrue(rm.rendered("etsy", "Orders\nTake a tour", 0))
        self.assertFalse(rm.rendered("payhip", "", 0))
        self.assertFalse(rm.rendered("payhip", "Loading", 0))

    def test_merge_never_erases(self):
        data = rm.merge_read({}, "payhip", "ok", rm.parse_table(*PAYHIP_TABLE, "payhip"), "T1")
        self.assertEqual(len(data["orders"]), 2)
        rm.merge_read(data, "payhip", "not rendered", [], "T2", "url")
        self.assertEqual(len(data["orders"]), 2)                    # bad read keeps orders
        self.assertEqual(data["asOf"]["payhip"], "T1")              # and the old asOf
        self.assertIn("payhip: not rendered", data["errors"][0])
        rm.merge_read(data, "payhip", "ok", [], "T3")               # a genuine empty page
        self.assertEqual(len(data["orders"]), 2)
        self.assertEqual(data["errors"], [])


class Dashboard(unittest.TestCase):
    def test_gumroad_sale(self):
        s = {"id": "abc==", "created_at": "2026-09-29T14:05:00Z", "product_name": "Tenure Tracker", "price": 1200,
             "gumroad_fee": 170, "currency": "usd", "refunded": False, "email": "buyer@example.invalid"}
        o = td.parse_gumroad_sale(s)
        self.assertEqual((o["gross"], o["fee"], o["refunded"]), (1200, 170, 0))
        self.assertNotIn("email", o)
        self.assertEqual(td.parse_gumroad_sale({**s, "refunded": True})["refunded"], 1200)
        self.assertEqual(td.parse_gumroad_sale({**s, "amount_refunded_cents": 500, "partially_refunded": True})["refunded"], 500)
        self.assertIsNone(td.parse_gumroad_sale({**s, "price": 0}))
        self.assertIsNone(td.parse_gumroad_sale({**s, "currency": "eur"}))

    def test_no_token_is_quiet(self):
        self.assertIsNone(td.fetch_gumroad({}))

    def test_product_mapping(self):
        cases = {
            "Tenure Tracker Spreadsheet, Promotion Dossier": "sheet-tenure",
            "Journal Submission Tracker Spreadsheet, Revise": "sheet-submission",
            "Academic Job Market Tracker Spreadsheet": "sheet-jobmarket",
            "Grant Pipeline Tracker Spreadsheet": "sheet-grantpipeline",
            "Systematic Review Screening Matrix Spreadsheet": "sheet-reviewmatrix",
            "Academic Researcher Spreadsheet Bundle, NSF, Journal Submission Tracker, Tenure Dossier": "sheet-bundle",
            "GLP-1 Muscle Tracker Spreadsheet": "tracker-sheet",
        }
        for title, key in cases.items():
            self.assertEqual(td.marketplace_product("etsy", title)[0], key, title)
        self.assertEqual(td.marketplace_product("etsy", "Sunset Print")[0], "photo-print")
        self.assertEqual(td.marketplace_product("payhip", "Something new")[0], "sheet-other")
        self.assertEqual(td.marketplace_product("etsy", "GLP-1 tracker")[1], "muscleonglp")
        row = lambda p, s: {"product": p, "site": s}  # noqa: E731
        self.assertEqual(td.product_group(row("sheet-tenure", "purplelink")), "Spreadsheets")
        self.assertEqual(td.product_group(row("tracker-sheet", "muscleonglp")), "MuscleOnGLP")
        self.assertEqual(td.product_group(row("photo-print", "purplelink")), "Photo prints (Etsy)")
        self.assertIn("Photo prints (Etsy)", td.PROFIT_LINES)
        self.assertIn("Photo prints (Etsy)", [g for g, _c in td.PRODUCT_GROUPS])

    def test_fees(self):
        self.assertEqual(td.estimate_fee("etsy", 1200), round(78 + 36 + 25))
        self.assertEqual(td.estimate_fee("gumroad", 1200), 170)
        self.assertEqual(td.estimate_fee("payhip", 1200), round(60 + 34.8 + 30))
        est = td.marketplace_row("payhip", {"id": "1", "ts": 1.0, "gross": 1200, "title": "x"})
        self.assertTrue(est["feeEstimated"])
        act = td.marketplace_row("etsy", {"id": "1", "ts": 1.0, "gross": 1200, "fee": 139, "title": "Tenure"})
        self.assertFalse(act["feeEstimated"])
        self.assertEqual(act["net"], 1061)
        self.assertEqual(act["attr"], {"first": {"s": "etsy"}})

    def test_channels(self):
        self.assertEqual([td.classify_touch({"s": s}) for s in ("etsy", "gumroad", "payhip")],
                         ["Etsy", "Gumroad", "Payhip"])
        self.assertEqual(td.classify_touch({"s": "reddit.com"}), "Reddit")

    def _write_market_file(self, orders):
        td.MARKETPLACES_PATH.write_text(json.dumps({"orders": orders, "asOf": {"etsy": NOW.isoformat()},
                                                     "status": {"etsy": "ok"}, "errors": []}))

    def test_step_merge_dedupe_render(self):
        ts = NOW.timestamp() - 3600
        stripe = {"id": "cs_1", "kind": "purchase", "product": "sheet-tenure", "site": "purplelink",
                  "gross": 1200, "net": 1100, "refunded": 0, "ts": ts + 60}
        hist = {"sites": {}, "ledger": {"cs_1": stripe}}
        self._write_market_file({
            "etsy:1": {"id": "1", "site": "etsy", "ts": ts, "title": "Tenure Tracker Spreadsheet", "gross": 1200},   # dup of Stripe
            "etsy:2": {"id": "2", "site": "etsy", "ts": ts, "title": "Sunset Print", "gross": 2400, "fee": 300},
            "payhip:3": {"id": "3", "site": "payhip", "ts": ts, "title": "Grant Pipeline Tracker", "gross": 1200},
        })
        ev, changed = td.marketplace_step(hist, {}, fetch=False)
        self.assertTrue(changed)
        self.assertEqual(sorted(k for k in hist["ledger"] if ":" in k), ["etsy:2", "payhip:3"])
        self.assertEqual(len(ev), 2)
        self.assertIn("on Etsy", td._event_text(ev[0]) + td._event_text(ev[1]))
        self.assertEqual(td.marketplace_step(hist, {}, fetch=False), ([], False))   # idempotent

        s = td.marketplace_summary(hist)
        self.assertEqual((s["etsy"]["windowOrders"], s["etsy"]["windowGross"], s["etsy"]["windowNet"]), (1, 2400, 2100))
        self.assertEqual(s["payhip"]["estimated"], 1)
        self.assertTrue(any("never read" in i for i in s["gumroad"]["issues"]))
        ch = td.channel_revenue(hist)
        self.assertEqual({r["channel"] for r in ch["rows"]} >= {"Etsy", "Payhip"}, True)
        p = td.profit_view(hist, {})
        lines = {r["line"]: r for r in p["rows"]}
        self.assertAlmostEqual(lines["Photo prints (Etsy)"]["revenue"], 21.0)
        self.assertIn("Spreadsheets", lines)
        self.assertTrue(any("Etsy costs" in g for g in p["gaps"]))
        m = td.revenue_metrics(hist, [], {})
        self.assertEqual(m["web"]["orders"], 1)                     # marketplaces excluded from site conversion
        out = td.render([], [], "now", None, None, None, {}, None, None, m, p, ch, None, s,
                        list(hist["ledger"].values()))
        for needle in ("Sales · marketplaces", "Photo prints (Etsy)", "Etsy", "$1.40"):
            self.assertIn(needle, out)

    def test_render_with_zero_orders(self):
        hist = {"sites": {}, "ledger": {}}
        self._write_market_file({})
        td.marketplace_step(hist, {}, fetch=False)
        s = td.marketplace_summary(hist)
        out = td.render([], [], "now", None, None, None, {}, None, None, None, None, None, None, s, [])
        self.assertIn("none yet", out)
        td.print_marketplaces(s)

    def test_stale_reading_is_a_gap(self):
        old = (NOW - dt.timedelta(days=5)).isoformat()
        hist = {"marketplaceMeta": {"etsy": {"asOf": old, "status": "ok"},
                                    "payhip": {"asOf": NOW.isoformat(), "status": "signed out"}}, "ledger": {}}
        s = td.marketplace_summary(hist)
        self.assertTrue(any("days ago" in i for i in s["etsy"]["issues"]))
        self.assertIn("signed out", s["payhip"]["issues"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
