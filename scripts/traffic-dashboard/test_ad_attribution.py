"""The channel funnel prints, Google Ads is no longer read, and touches classify into channels."""
import sys, time, os, tempfile
os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td


def _row(attr, product="moderntex", ts=None):
    return {"product": product, "kind": "purchase", "gross": 1999, "net": 1900, "ts": ts or time.time(), "attr": attr}


def test_funnel_prints_and_ignores_a_google_ads_reading(capsys):
    # Google Ads for ModernTex was turned off on 2026-10-19; the funnel no longer reads or compares it.
    h = {"ledger": {}, "adFunnel": {"days": 7, "channels": {
        "paid:google": {"pageviews": 12, "pageviewsByPath": {"/moderntex/": 10, "/": 2}, "trial": {"moderntex": 3}, "checkout": {"moderntex": 1}},
        "direct": {"pageviews": 40, "pageviewsByPath": {}, "trial": {}, "checkout": {}}}}}
    td.print_ad_funnel(h)
    out = capsys.readouterr().out
    assert "direct" in out and "3 trial downloads" in out
    assert "Google Ads reports" not in out and "per trial download" not in out
    assert not hasattr(td, "google_ads_attributed") and not hasattr(td, "moderntex_ads_block")


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
    td.print_ad_funnel(h)
    assert "tool:latex-diff" in capsys.readouterr().out
