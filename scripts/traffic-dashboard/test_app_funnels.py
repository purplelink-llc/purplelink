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
