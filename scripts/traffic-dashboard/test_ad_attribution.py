"""Google Ads cost per sale divides by click-attributed orders only, and the channel funnel prints."""
import sys, time, os, tempfile
os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td


def _row(attr, product="moderntex", ts=None):
    return {"product": product, "kind": "purchase", "gross": 1999, "net": 1900, "ts": ts or time.time(), "attr": attr}


def test_only_orders_with_a_google_ad_touch_count():
    h = {"ledger": {
        "a": _row({"first": {"g": 1, "s": "google"}, "last": {"g": 1, "s": "google"}}),
        "b": _row({"first": {"s": "google", "m": "cpc"}}),
        "c": _row({"first": {"r": "google.com"}}),           # organic search
        "d": _row(None),                                      # direct
        "e": _row({"first": {"g": 1}}, ts=time.time() - 30 * 86400),  # outside the window
        "f": _row({"first": {"g": 1}}, product="legroom"),
    }}
    got = td.google_ads_attributed(h, 7, "moderntex")
    assert got["orders"] == 2 and abs(got["net"] - 38.0) < 1e-6
    assert td.google_ads_attributed(h, 7)["orders"] == 3


def test_funnel_prints_and_flags_missing_tracking(capsys):
    h = {"ledger": {}, "adFunnel": {"days": 7, "channels": {
        "paid:google": {"pageviews": 12, "pageviewsByPath": {"/moderntex/": 10, "/": 2}, "trial": {"moderntex": 3}, "checkout": {"moderntex": 1}},
        "direct": {"pageviews": 40, "pageviewsByPath": {}, "trial": {}, "checkout": {}}}}}
    ads = {"googleAdsModerntex": {"clicks": 39, "spend": 10.13, "window": "Last 7 days"}}
    td.print_ad_funnel(h, ads)
    out = capsys.readouterr().out
    assert "paid:google" in out and "3 trial downloads" in out and "$3.38 per trial" in out
    assert "0 orders attributed" in out
    h["adFunnel"]["channels"].pop("paid:google")
    td.print_ad_funnel(h, ads)
    assert "we saw none" in capsys.readouterr().out


def test_tool_offer_visits_are_their_own_channel():
    assert td.classify_touch({"s": "tool-latex-diff", "m": "tool", "c": "moderntex"}) == "Tool offers"
    assert td.classify_touch({"s": "Tool-Bib-Validator", "r": "purplelink.llc"}) == "Tool offers"
    # Not the tool channel: a referrer or campaign that only mentions tool, and a paid click.
    assert td.classify_touch({"r": "tool-time.example"}) == "Other sites"
    assert td.classify_touch({"s": "tools"}) == "Campaign: tools"
    assert td.classify_touch({"s": "toolbox", "m": "email"}) == "Campaign: toolbox"
    assert td.classify_touch({"g": 1, "s": "tool-latex-diff"}) == "Google Ads"
    assert td.classify_touch({"s": "google", "m": "cpc"}) == "Google Ads"
    assert td.classify_touch({"s": "newsletter"}) == "Email & RSS"


def test_tool_channels_print_with_their_slug(capsys):
    h = {"ledger": {}, "adFunnel": {"days": 7, "channels": {
        "tool:latex-diff": {"pageviews": 4, "pageviewsByPath": {"/moderntex/": 4}, "trial": {"moderntex": 1}, "checkout": {}}}}}
    td.print_ad_funnel(h, {})
    assert "tool:latex-diff" in capsys.readouterr().out
