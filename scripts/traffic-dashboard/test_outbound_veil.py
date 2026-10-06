"""Outbound Veil must be its own product line in the dashboard, not fall into "Paper Review & tools"."""
import sys, time
import os, tempfile
os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))   # never touch the real archive
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td


def _row(product="outbound-veil", gross=2900, net=2816):
    return {"id": "cs_x", "kind": "purchase", "product": product, "site": "purplelink",
            "gross": gross, "net": net, "ts": time.time(), "refunded": 0}


def test_group_and_label():
    assert td.product_group(_row()) == "Outbound Veil"
    assert td.PRODUCT_LABELS["outbound-veil"] == "Outbound Veil"
    assert td.product_group(_row("moderntex")) == "ModernTex"


def test_weekly_chart_and_profit_line_have_it():
    assert "Outbound Veil" in [g for g, _c in td.PRODUCT_GROUPS]
    assert "Outbound Veil" in td.PROFIT_LINES
    pv = td.profit_view({"ledger": {"cs_x": _row()}}, {}, 7)
    line = next(r for r in pv["rows"] if r["line"] == "Outbound Veil")
    assert line["orders"] == 1 and round(line["revenue"], 2) == 28.16


def test_checkout_rate_denominator_counts_its_page():
    purplelink = next(s for s in td.SITES if s["key"] == "purplelink")
    assert "/outbound-veil/" in purplelink["product_paths"]
    assert "ovTrialDownloads" in [k for k, _ in purplelink["secondaries"]]


def test_legroom_page_and_trial_downloads_are_tracked():
    purplelink = next(s for s in td.SITES if s["key"] == "purplelink")
    assert "/legroom/" in purplelink["product_paths"]
    assert "lgTrialDownloads" in [k for k, _ in purplelink["secondaries"]]


def test_legroom_is_its_own_line_under_either_name():
    assert td.product_group(_row("legroom", 900, 871)) == "Legroom"
    assert td.product_group(_row("freeboard", 900, 871)) == "Legroom"
    assert "Legroom" in [g for g, _c in td.PRODUCT_GROUPS] and "Legroom" in td.PROFIT_LINES
    pv = td.profit_view({"ledger": {"cs_x": _row("legroom", 900, 871)}}, {}, 7)
    assert any(r["line"] == "Legroom" and r["orders"] == 1 for r in pv["rows"])


def test_mac_suite_is_its_own_line():
    assert td.product_group(_row("app-suite", 4900, 4758)) == "Mac Suite"
    assert td.PRODUCT_LABELS["app-suite"] == "Mac Suite"
    assert "Mac Suite" in [g for g, _c in td.PRODUCT_GROUPS] and "Mac Suite" in td.PROFIT_LINES
    pv = td.profit_view({"ledger": {"cs_x": _row("app-suite", 4900, 4758)}}, {}, 7)
    assert any(r["line"] == "Mac Suite" and r["orders"] == 1 for r in pv["rows"])
