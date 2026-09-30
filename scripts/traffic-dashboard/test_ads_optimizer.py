#!/usr/bin/env python3
"""Offline tests for ads_optimizer.analyze (python3 scripts/traffic-dashboard/test_ads_optimizer.py)."""
import datetime as dt, importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("ao", Path(__file__).with_name("ads_optimizer.py"))
ao = importlib.util.module_from_spec(spec); spec.loader.exec_module(ao)
D0 = dt.date(2026, 10, 1)


def kw(name, bid, spend=0.0, impr=0, taps=0, inst=0, status="Running"):
    return {"keyword": name, "status": status, "bid": bid, "spend": spend, "impressions": impr, "taps": taps, "installs": inst}


def snap(day, kws, budget=10.0):
    return (D0 + dt.timedelta(days=day)).isoformat(), {"window": "Last 30 days", "dailyBudget": budget, "keywords": kws}


def check(cond, msg):
    if not cond:
        print("FAIL:", msg); sys.exit(1)


def action(res, name):
    return next(r for r in res["keywords"] if r["keyword"] == name)


# baseline only
s = dict([snap(0, [kw("a", 1.0)])])
r = ao.analyze(s, D0)
check(r["delivery"]["baselineOnly"] and action(r, "a")["action"] == "hold", "single snapshot is a baseline")

# six days: dead keyword at $1 -> raise to 1.5; junk keyword with impressions and no taps -> pause; winner -> scale
s = {}
for d in range(0, 6):
    s.update([snap(d, [kw("dead", 1.0), kw("junk", 0.75, impr=60 * d), kw("win", 0.75, spend=0.5 * d, impr=100 * d, taps=3 * d, inst=d // 2 if d > 0 else 0)])])
r = ao.analyze(s, D0 + dt.timedelta(days=5))
check(action(r, "dead")["action"] == "raise" and action(r, "dead")["newBid"] == 1.5, "dead keyword bumps to 1.5")
check(action(r, "junk")["action"] == "pause", "300 impressions, 0 taps pauses")
check(action(r, "win")["action"] == "scale", "cheap installs scale")
check(r["delivery"]["utilization"] is not None and r["delivery"]["utilization"] < 0.5, "spend far under budget is auction limited")
check("Auction/volume limited" in r["delivery"]["verdict"], "verdict names the constraint")

# too early: only two days at the bid
s = {}
for d in range(0, 3):
    s.update([snap(d, [kw("new", 1.0)])])
check(ao.analyze(s, D0 + dt.timedelta(days=2))["keywords"][0]["action"] == "hold", "not judged before DEAD_DAYS")

# bid change resets the clock
s = {}
for d in range(0, 8):
    s.update([snap(d, [kw("k", 0.75 if d < 4 else 1.0)])])
res = ao.analyze(s, D0 + dt.timedelta(days=7))
check(action(res, "k")["daysAtBid"] == 4 and action(res, "k")["action"] == "hold", "days at bid restart after a bid change")

# budget limited
s = {}
for d in range(0, 4):
    s.update([snap(d, [kw("big", 1.0, spend=9.5 * d, impr=500 * d, taps=20 * d)])])
check("Budget limited" in ao.analyze(s, D0 + dt.timedelta(days=3))["delivery"]["verdict"], "near-full spend is budget limited")
print("ads optimizer tests ok")
