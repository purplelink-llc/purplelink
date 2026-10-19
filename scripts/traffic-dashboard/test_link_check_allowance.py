"""The channel funnel subtracts link-checker visits per newly tagged URL, marks one-view email tags, and the
7-day profit card does not charge an ad reading taken before its window."""
import datetime as dt
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td


def test_allowance_counts_only_batches_inside_the_window():
    batches = [{"date": "2026-10-03", "channel": "youtube-latex", "urls": 9},
               {"date": "2026-10-14", "channel": "youtube-promo", "urls": 13},
               {"date": "2026-10-15", "channel": "youtube-howto", "urls": 2},
               {"date": "2026-10-17", "channel": "youtube-howto", "urls": 2},
               {"date": "2026-10-18", "channel": "youtube-howto", "urls": 2}]
    got = td.link_check_allowance("2026-10-17", 7, batches)
    assert got == {"youtube-promo": 13, "youtube-howto": 4}


def test_human_estimate_never_goes_below_zero():
    assert td.human_estimate(27, 5, 13) == (1, 0)
    assert td.human_estimate(4, 4, 2) == (0, 0)
    assert td.human_estimate(30, 6, 1) == (28, 4)


def test_tagged_links_file_and_howto_ledger_are_read():
    batches = td.tagged_link_batches()
    assert any(b["channel"] == "youtube-latex" and b["urls"] == 14 for b in batches)
    assert all(b["date"] <= dt.date.today().isoformat() or b["channel"] == "youtube-howto" for b in batches)


def test_funnel_prints_human_estimate_and_scanner_tags(capsys, monkeypatch):
    # The 2026-10-17 pattern: two views on each promo page, one trial per app, no buy clicks.
    promo_paths = {f"/{p}/": 2 for p in ("legroom", "panely", "summonly", "tapefolio", "outbound-veil")}
    h = {"ledger": {}, "adFunnel": {"asOf": "2026-10-17", "days": 7, "channels": {
        "youtube-promo": {"pageviews": 10, "pageviewsByPath": promo_paths,
                          "trial": {"legroom": 1, "panely": 1, "summonly": 1, "tapefolio": 1, "outbound-veil": 1},
                          "checkout": {}},
        "macmenubar": {"pageviews": 50, "pageviewsByPath": {"/moderntex/": 9}, "trial": {"moderntex": 3},
                           "checkout": {"moderntex": 2}},
        "utk": {"pageviews": 1, "pageviewsByPath": {"/moderntex/": 1}, "trial": {}, "checkout": {}}}}}
    monkeypatch.setattr(td, "tagged_link_batches",
                        lambda: [{"date": "2026-10-14", "channel": "youtube-promo", "urls": 5}])
    td.print_ad_funnel(h)
    out = capsys.readouterr().out
    assert "est. human: 0 views, 0 trials" in out
    assert "8 counted, about 3 after the link-check allowance" in out
    assert "judge those emails by replies): utk" in out
    assert "macmenubar" in out and "3 trial downloads" in out


def _gp_ads(manual_ads):
    row = {"product": "moderntex", "kind": "purchase", "gross": 1999, "net": 1900, "ts": time.time(), "attr": None,
           "site": "purplelink"}
    p = td.profit_view({"ledger": {"cs_x": row}}, manual_ads, 7)
    return p


def test_ad_reading_from_before_the_window_is_not_charged(monkeypatch):
    monkeypatch.setattr(td, "load_costs", lambda: [])
    old = (dt.date.today() - dt.timedelta(days=13)).isoformat()
    fresh = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    ads = {"appleSearchAds": {"asOf": old, "campaigns": [{"spend": 40.47}]},
           "googleAdsModerntex": {"asOf": fresh, "spend": 12.24}}
    p = _gp_ads(ads)
    assert any("before this window; not counted" in g for g in p["gaps"])
    assert abs(p["total"]["ads"]) < 0.01  # the old Apple reading is not charged, and Google Ads is no longer read
    assert not any("Google Ads" in g for g in p["gaps"])
