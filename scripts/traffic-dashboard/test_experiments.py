#!/usr/bin/env python3
"""Offline tests for experiments_check.evaluate (run: python3 scripts/traffic-dashboard/test_experiments.py)."""
import datetime as dt, importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("ec", Path(__file__).with_name("experiments_check.py"))
ec = importlib.util.module_from_spec(spec); spec.loader.exec_module(ec)

T0 = dt.date(2026, 9, 1)
ts = lambda d: dt.datetime.combine(d, dt.time(12)).timestamp()
hist = {"ledger": {
    "cs_1": {"id": "cs_1", "product": "sheet-tenure", "gross": 1200, "net": 1100, "ts": ts(T0 + dt.timedelta(days=2))},
    "etsy:1": {"id": "etsy:1", "product": "sheet-tenure", "gross": 1200, "net": 900, "ts": ts(T0 + dt.timedelta(days=3))},
    "cs_old": {"id": "cs_old", "product": "sheet-tenure", "gross": 1200, "net": 1100, "ts": ts(T0 - dt.timedelta(days=5))},
    "cs_zero": {"id": "cs_zero", "product": "sheet-tenure", "gross": 0, "net": 0, "ts": ts(T0 + dt.timedelta(days=4))},
}, "sites": {"purplelink": {"latest": {"topPaths": [{"key": "/x/", "count": 70}], "checkoutByProduct": []}}}}
base = {"id": "t", "name": "t", "status": "running", "started": T0.isoformat()}


def run(ex, days):
    return ec.evaluate({**base, **ex}, hist, T0 + dt.timedelta(days=days))


def check(cond, msg):
    if not cond:
        print("FAIL:", msg); sys.exit(1)


r = run({"metric": {"kind": "orders", "products": ["sheet-tenure"]}, "scale_if": {"gte": 2, "min_n": 2}}, 10)
check(r["verdict"] == "SCALE" and r["measured"] == 2, "counts both channels, skips old and $0 rows")
r = run({"metric": {"kind": "orders", "products": ["sheet-tenure"], "source": "etsy"}, "scale_if": {"gte": 2, "min_n": 2}}, 10)
check(r["verdict"] == "HOLD" and r["measured"] == 1, "source filter")
r = run({"metric": {"kind": "orders", "products": ["nothing"]}, "kill_if": {"lte": 0, "after_days": 45}}, 10)
check(r["verdict"] == "HOLD", "no kill before after_days")
r = run({"metric": {"kind": "orders", "products": ["nothing"]}, "kill_if": {"lte": 0, "after_days": 45}}, 46)
check(r["verdict"] == "KILL", "kill after after_days")
r = run({"metric": {"kind": "views", "path": "/x/"}, "scale_if": {"gte": 60}}, 5)
check(r["verdict"] == "SCALE" and r["measured"] == 70, "views from snapshot")
r = run({"metric": {"kind": "manual", "how": "x"}, "review": (T0 + dt.timedelta(days=7)).isoformat()}, 8)
check(r["verdict"] == "REVIEW", "review date")
r = run({"status": "kill-pending-ben", "metric": {"kind": "manual"}}, 3)
check(r["verdict"] == "PENDING", "pending")
print("experiments tests ok")
