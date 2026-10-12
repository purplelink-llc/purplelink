"""Legroom and Vitae get the same funnel block Outbound Veil has: views, downloads, buy clicks, orders."""
import sys, time
import os, tempfile
os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))   # never touch the real archive
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td
import datetime as dt


def _history(ledger=None, metric="lgTrialDownloads", n=3):
    today = dt.date.today()
    by_day = {(today - dt.timedelta(days=i)).isoformat(): {metric: 1} for i in range(1, n + 1)}
    latest = {"topPaths": [{"key": "/legroom/", "count": 40}, {"key": "/vitae/", "count": 90}, {"key": "/vitae/plus/", "count": 7}],
              "checkoutByProduct": [{"key": "legroom", "count": 2}, {"key": "vitae-plus-annual", "count": 1}]}
    return {"sites": {"purplelink": {"latest": latest, "byDay": by_day}}, "ledger": ledger or {}}


def _row(product, kind="purchase", ts=None):
    return {"product": product, "kind": kind, "gross": 900, "net": 871, "ts": ts or time.time()}


def test_legroom_counts_its_own_orders_and_reports_suite_apart():
    h = _history({"a": _row("legroom"), "b": _row("freeboard"), "c": _row("app-suite")})
    r = td.legroom_report(h)
    assert r["ordersAll"] == 2 and r["suiteOrders"] == 1 and r["clicks"] == 2
    assert r["views"]["/legroom/"] == 40


def test_vitae_conversion_is_a_plus_subscription_not_a_download():
    h = _history({"a": _row("vitae-plus-monthly"), "b": _row("vitae-plus-annual", kind="refund"), "c": _row("moderntex")},
                 metric="vitaeDownloads")
    r = td.vitae_report(h)
    assert r["ordersAll"] == 1 and r["clicks"] == 1
    assert r["viewsTotal"] == 97  # /vitae/ and /vitae/plus/


def test_outbound_veil_report_unchanged_for_its_keys():
    r = td.outbound_veil_report(_history())
    assert {"views", "dl7", "dlToday", "dlAll", "dlSince", "clicks", "orders30", "ordersAll", "gsc"} <= set(r)


def test_print_says_when_there_are_no_downloads(capsys):
    td.print_legroom(td.legroom_report(_history(metric="other", n=0)))
    assert "no downloads yet" in capsys.readouterr().out


# --- Panely and Summonly --------------------------------------------------------------------

def _two_apps_history(ledger=None):
    today = dt.date.today()
    by_day = {(today - dt.timedelta(days=i)).isoformat(): {"pnTrialDownloads": 2, "smTrialDownloads": 1} for i in range(1, 4)}
    latest = {"topPaths": [{"key": "/panely/", "count": 30}, {"key": "/summonly/", "count": 50}, {"key": "/summonly/success/", "count": 2}],
              "checkoutByProduct": [{"key": "panely", "count": 3}, {"key": "summonly", "count": 5}, {"key": "app-suite", "count": 1}]}
    return {"sites": {"purplelink": {"latest": latest, "byDay": by_day}}, "ledger": ledger or {}}


def test_panely_and_summonly_count_their_own_orders_and_report_suite_apart():
    h = _two_apps_history({"a": _row("panely"), "b": _row("summonly"), "c": _row("summonly"), "d": _row("app-suite"), "e": _row("legroom")})
    p, s = td.panely_report(h), td.summonly_report(h)
    assert p["ordersAll"] == 1 and s["ordersAll"] == 2 and p["suiteOrders"] == s["suiteOrders"] == 1
    assert p["clicks"] == 3 and s["clicks"] == 5
    assert p["views"]["/panely/"] == 30 and s["viewsTotal"] == 52
    assert p["dl7"] == 6 and s["dl7"] == 3          # three complete days each, own metric each


def test_app_server_counts_sum_public_buyer_and_updates_by_version():
    today = dt.date.today()
    entry = {"updates": {"Panely-1.0.1.dmg": 2, "Panely-1.0.0.dmg": 5},
             "public": {"Panely-1.0.0.dmg": 7, "Panely-1.0.1.dmg": 3}, "buyer": {"Panely-1.0.0.dmg": 4},
             "byDay": {(today - dt.timedelta(days=1)).isoformat(): {"public": 6, "buyer": 1},
                       (today - dt.timedelta(days=30)).isoformat(): {"public": 4, "buyer": 3},
                       today.isoformat(): {"public": 2, "buyer": 0}}}
    sv = td.app_stats_summary(entry)
    assert (sv["publicAll"], sv["buyerAll"], sv["updatesAll"]) == (10, 4, 7)
    assert (sv["public7"], sv["buyer7"], sv["publicToday"]) == (6, 1, 2)      # today and day 30 are outside the 7 complete days
    assert list(sv["updates"]) == ["Panely-1.0.0.dmg", "Panely-1.0.1.dmg"]    # oldest version first
    assert td.app_stats_summary(None) is None


def test_print_panely_and_summonly_say_what_is_and_is_not_measured(capsys):
    h = _two_apps_history({"a": _row("panely")})
    h["appStats"] = {"panely": {"updates": {"Panely-1.0.0.dmg": 3}, "public": {"Panely-1.0.0.dmg": 5}, "buyer": {}, "byDay": {}}}
    td.print_panely(td.panely_report(h))
    out = capsys.readouterr().out
    assert "Panely (Mac app, $9.99" in out and "5 public (trial)" in out and "Panely-1.0.0 x3" in out and "trials started" in out
    td.print_summonly(td.summonly_report(h))
    assert "not available this run" in capsys.readouterr().out      # no counters archived for Summonly yet
