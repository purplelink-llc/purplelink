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
r = run({"metric": {"kind": "forms", "form": "waitlist-x"}, "scale_if": {"gte": 3}}, 3)
check(r["measured"] == 0, "forms metric missing key reads as 0")
hist["sites"]["purplelink"]["latest"]["formBreakdown"] = [{"key": "waitlist-x", "count": 5}]
r = run({"metric": {"kind": "forms", "form": "waitlist-x"}, "scale_if": {"gte": 3}}, 3)
check(r["verdict"] == "SCALE" and r["measured"] == 5, "forms metric")
r = run({"status": "proposed", "metric": {"kind": "manual", "how": "later"}}, 3)
check(r["verdict"] == "PROPOSED", "proposed rows are not evaluated")
r = run({"status": "proposed", "started": None, "metric": {"kind": "manual", "how": "later"}}, 3)
check(r["verdict"] == "PROPOSED" and r["age_days"] is None, "proposed row without a start date does not raise")
r = run({"started": None, "metric": {"kind": "manual"}}, 3)
check(r["verdict"] == "NOSTART", "running row without a start date is reported, not raised")

# Waitlist reviews (AB-20261031-1): the Netlify form count next to each build-rule threshold, from forms.json.
rule = {"form": "grant-review-waitlist", "path": "/grant-review/", "yes_field": "would-pay-19",
        "any_of": [{"signups_gte": 25, "yes_share_gte": 0.4}, {"signups_gte": 10, "visits_lt": 150}]}
review = {"metric": {"kind": "manual", "how": "x"}, "review": (T0 + dt.timedelta(days=30)).isoformat(), "forms_rule": rule}
hist["sites"]["purplelink"]["latest"]["topPaths"].append({"key": "/grant-review/", "count": 120})
doc = lambda total, yes, spam=0: {"generated": "2026-10-31T13:00:00+00:00", "forms": [
    {"form": "grant-review-waitlist", "total": total, "spam": spam, "answers": {"would-pay-19": {"Yes": yes, "Maybe": total - yes}}}]}
r = ec.evaluate({**base, **review}, hist, T0 + dt.timedelta(days=30), doc(0, 0))
check(r["verdict"] == "REVIEW" and r["forms"].startswith("grant-review-waitlist (2026-10-31): 0 signups, 0 Yes, 120 views"),
      "zero signups printed as a count: " + r["forms"])
check(r["forms"].endswith(">=25 signups >=40% Yes [not met] or >=10 signups from <150 visits [not met]"), "both rules shown: " + r["forms"])
r = ec.evaluate({**base, **review}, hist, T0 + dt.timedelta(days=30), doc(12, 3, spam=2))
check("12 signups, 3 Yes (25%), 2 in spam" in r["forms"] and "[not met] or >=10 signups from <150 visits [met]" in r["forms"],
      "second rule met on few visits: " + r["forms"])
r = ec.evaluate({**base, **review}, hist, T0 + dt.timedelta(days=30), doc(30, 13))
check(">=40% Yes [met]" in r["forms"], "first rule met: " + r["forms"])
r = ec.evaluate({**base, **review}, hist, T0 + dt.timedelta(days=30), None)
check("not measured" in r["forms"] and "0 signups" not in r["forms"], "missing forms.json is not 0: " + r["forms"])
r = ec.evaluate({**base, **review}, hist, T0 + dt.timedelta(days=30), {"generated": "x", "forms": []})
check("not measured" in r["forms"], "form absent from forms.json is not 0")
check("forms" not in run({"metric": {"kind": "manual"}}, 3), "rows without forms_rule get no forms line")
r = ec.evaluate({**base, **review, "forms_rule": {**rule, "path": "/nowhere/"}}, hist, T0 + dt.timedelta(days=30), doc(0, 0))
check("0 views of /nowhere/ in 30 days (not in the path list)" in r["forms"], "absent path is labelled: " + r["forms"])

spec2 = importlib.util.spec_from_file_location("fe", Path(__file__).with_name("forms_export.py"))
fe = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(fe)
rows = fe.summarize([
    {"name": "grant-review-waitlist", "spam": 1, "submissions": [
        {"created_at": "2026-10-05T10:00:00Z", "data": {"would-pay-19": "Yes", "email": "a@example.com"}},
        {"created_at": "2026-09-20T10:00:00Z", "data": {"would-pay-19": "Maybe"}},
        {"created_at": "2026-10-30T10:00:00Z", "data": {}}]},
    {"name": "waitlist-x", "submissions": []}], dt.date(2026, 10, 31))
g = rows[0]
check(g["form"] == "grant-review-waitlist" and g["total"] == 3 and g["last30"] == 2 and g["spam"] == 1, "counts: %r" % g)
check((g["first"], g["last"]) == ("2026-09-20", "2026-10-30"), "first and last day")
check(g["answers"]["would-pay-19"] == {"Yes": 1, "Maybe": 1, "(blank)": 1}, "answer counts")
check("example.com" not in str(rows) and "email" not in g["answers"], "no email or unlisted field in the output")
check(rows[1] == {"form": "waitlist-x", "total": 0, "last30": 0, "first": None, "last": None, "spam": None}, "empty form, no answers key")
print("experiments tests ok")
