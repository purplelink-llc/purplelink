#!/usr/bin/env python3
"""Every source's revenue per day, archived in history.json, exported as CSV and drawn on the Overview.

    python3 scripts/traffic-dashboard/test_revenue_daily.py
"""
import contextlib
import csv
import datetime as dt
import importlib.util
import io
import json
import os
import random
import re
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


def _json(block: str) -> dict:
    m = re.search(r'<script type="application/json" id="rev-data">(.*?)</script>', block, re.S)
    assert m, "no embedded data"
    return json.loads(m.group(1))


def synthetic(n=60, seed=3, level=1000, noise=800):
    """Daily cents: mostly zero days with an order now and then, like the real series."""
    rnd = random.Random(seed)
    return [float(level + rnd.randint(-noise, noise)) if rnd.random() < 0.4 else 0.0 for _ in range(n)]


class Forecast(unittest.TestCase):
    def setUp(self):
        self._arima = td.FC_ARIMA
        td.FC_ARIMA = False          # statsmodels is optional and slow; the plain-Python candidates are what always runs

    def tearDown(self):
        td.FC_ARIMA = self._arima

    def test_backtest_picks_the_candidate_with_the_lowest_error(self):
        y = [100.0 + (i % 3) for i in range(40)]
        good = lambda yy, h: ([sum(yy[-7:]) / 7] * h, [0.0, 1.0, -1.0])
        bad = lambda yy, h: ([0.0] * h, [0.0])
        f = td.forecast_series(y, 30, candidates={"zero": bad, "recent mean": good})
        self.assertEqual(f["model"], "recent mean")
        self.assertLess(f["scores"]["recent mean"], f["scores"]["zero"])
        self.assertEqual(f["mae"], round(f["scores"]["recent mean"]))

    def test_real_candidates_chosen_model_has_the_minimum_score(self):
        y = [0.0] * 30 + [10000.0 if i % 2 == 0 else 0.0 for i in range(30)]      # the level moved a month ago
        f = td.forecast_series(y, 30)
        self.assertEqual(f["model"], min(f["scores"], key=lambda k: (f["scores"][k], k)))
        self.assertNotEqual(f["model"], "Mean of all days")                       # the all-days mean is slow to follow the move

    def test_never_negative_and_band_holds_the_forecast(self):
        series = [synthetic(60, 1), [max(0.0, 3000 - 60 * i) for i in range(60)], [0.0] * 40,
                  [5000.0] + [0.0] * 39, synthetic(25, 9, 300, 250)]
        for y in series:
            f = td.forecast_series(y)
            self.assertEqual(len(f["fc"]), td.FC_HORIZON)
            for j in range(td.FC_HORIZON):
                self.assertGreaterEqual(f["fc"][j], 0)
                self.assertGreaterEqual(f["lo"][j], 0)
                self.assertLessEqual(f["lo"][j], f["fc"][j])
                self.assertGreaterEqual(f["hi"][j], f["fc"][j])
            self.assertLessEqual(f["total30_lo"], f["total30_hi"])
            self.assertGreaterEqual(f["total30_lo"], 0)

    def test_too_little_history_gives_no_forecast(self):
        self.assertIsNone(td.forecast_series([100.0] * 20))

    @unittest.skipUnless(importlib.util.find_spec("statsmodels"), "statsmodels not installed")
    def test_arima_candidates_join_when_statsmodels_imports(self):
        td.FC_ARIMA = True
        f = td.forecast_series(synthetic(60, 2))
        self.assertIn("ARIMA (order by AIC)", f["scores"])
        td.FC_ARIMA = False
        self.assertNotIn("ARIMA (order by AIC)", td.forecast_series(synthetic(60, 2))["scores"])

    def test_without_statsmodels_the_plain_candidates_still_run(self):
        import builtins
        real = builtins.__import__
        def no_sm(name, *a, **k):
            if name.startswith("statsmodels"):
                raise ImportError(name)
            return real(name, *a, **k)
        td.FC_ARIMA = True
        builtins.__import__ = no_sm
        try:
            f = td.forecast_series(synthetic(60, 2))
        finally:
            builtins.__import__ = real
        self.assertTrue(f["scores"])
        self.assertFalse([k for k in f["scores"] if k.startswith("ARIMA")])

    def test_the_forecast_is_deterministic(self):
        y = synthetic(60, 4)
        self.assertEqual(td.forecast_series(y), td.forecast_series(y))


class Block(unittest.TestCase):
    TODAY = dt.date(2026, 10, 20)

    def setUp(self):
        self._arima = td.FC_ARIMA
        td.FC_ARIMA = False

    def tearDown(self):
        td.FC_ARIMA = self._arima

    def archive(self, days=45):
        a = {}
        rnd = random.Random(5)
        for k in range(days):
            d = (self.TODAY - dt.timedelta(days=days - 1 - k)).isoformat()
            if rnd.random() < 0.5:
                a.setdefault(d, {})["App Store"] = {"received": rnd.randint(200, 2000), "estimated": 0}
            a.setdefault(d, {})[td.SRC_TIKTOK] = {"received": 0, "estimated": rnd.randint(0, 400)}
        return a

    def test_embedded_data_shape(self):
        a = self.archive()
        data = _json(td.daily_revenue_block(a, self.TODAY))
        self.assertEqual(data["today"], "2026-10-20")
        self.assertEqual(data["n"], 45)
        self.assertEqual(data["start"], "2026-09-06")
        self.assertEqual(sorted(data["order"]), sorted(["App Store", td.SRC_TIKTOK]))
        self.assertEqual(list(data["sources"]), data["order"])
        for src in data["sources"].values():
            self.assertEqual(set(src), {"r", "e"})
            self.assertEqual((len(src["r"]), len(src["e"])), (45, 45))
        # nothing lost: the per-day sums equal the archive
        self.assertEqual(sum(sum(s["r"]) + sum(s["e"]) for s in data["sources"].values()),
                         sum(c["received"] + c["estimated"] for d in a.values() for c in d.values()))
        for key in ("all", "received"):
            f = data["forecast"][key]
            self.assertEqual(set(f), {"model", "mae", "scores", "fc", "lo", "hi", "total30", "total30_lo", "total30_hi"})
            self.assertEqual((len(f["fc"]), len(f["lo"]), len(f["hi"])), (td.FC_HORIZON,) * 3)
        self.assertEqual(data["horizon"], td.FC_HORIZON)

    def test_received_only_forecast_leaves_estimates_out(self):
        a = {}
        for k in range(40):
            d = (self.TODAY - dt.timedelta(days=39 - k)).isoformat()
            a[d] = {"App Store": {"received": 0, "estimated": 1000}}      # estimates only
        f = _json(td.daily_revenue_block(a, self.TODAY))["forecast"]
        self.assertEqual(f["received"]["total30"], 0)
        self.assertGreater(f["all"]["total30"], 25000)

    def test_a_short_archive_still_draws_without_a_forecast(self):
        a = {"2026-10-20": {"App Store": {"received": 500, "estimated": 0}}, "2026-10-18": {td.SRC_TIKTOK: {"received": 0, "estimated": 298}}}
        data = _json(td.daily_revenue_block(a, self.TODAY))
        self.assertEqual(data["n"], 3)
        self.assertEqual(data["forecast"], {})

    def test_a_forecast_failure_does_not_break_the_block(self):
        real = td.forecast_series
        td.forecast_series = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                block = td.daily_revenue_block(self.archive(), self.TODAY)
        finally:
            td.forecast_series = real
        self.assertEqual(_json(block)["forecast"], {})
        self.assertIn("revenue forecast skipped", out.getvalue())

    def test_json_in_the_script_tag_cannot_close_it(self):
        a = {"2026-10-20": {"A</script><b>": {"received": 100, "estimated": 0}}}
        block = td.daily_revenue_block(a, self.TODAY)
        self.assertEqual(block.count("</script>"), 1)
        self.assertEqual(_json(block)["order"], ["A</script><b>"])

    def test_future_days_in_the_archive_are_ignored(self):
        a = {"2026-10-20": {"App Store": {"received": 500, "estimated": 0}}, "2026-11-01": {"App Store": {"received": 9999, "estimated": 0}}}
        data = _json(td.daily_revenue_block(a, self.TODAY))
        self.assertEqual(data["n"], 1)

    def test_nothing_to_show_is_empty(self):
        self.assertEqual(td.daily_revenue_block({}, self.TODAY), "")
        self.assertEqual(td.daily_revenue_block(None, self.TODAY), "")
        self.assertEqual(td.daily_revenue_block({"2026-10-20": {"App Store": {"received": 0, "estimated": 0}}}, self.TODAY), "")


if __name__ == "__main__":
    unittest.main()
