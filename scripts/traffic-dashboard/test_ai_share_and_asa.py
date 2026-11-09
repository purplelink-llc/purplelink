"""AI-assistant referral share reads ChatGPT's utm_source tag, and an old Apple Search Ads reading stays
out of the "last 7 days" acquisition table (both wrong on the 2026-11-09 dashboard)."""
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td

# purplelink's archived snapshot for 2026-11-09, as stored (top 12 referrers, top 8 utm sources).
# ChatGPT is only in topUtm: its links carry utm_source=chatgpt.com and no Referer header.
REFS_1109 = [{"count": 723, "key": "www.reddit.com"}, {"count": 645, "key": "www.google.com"},
             {"count": 92, "key": "duckduckgo.com"}, {"count": 90, "key": "l.instagram.com"},
             {"count": 81, "key": "m.facebook.com"}, {"count": 80, "key": "www.facebook.com"},
             {"count": 26, "key": "www.bing.com"}, {"count": 23, "key": "checkout.stripe.com"},
             {"count": 19, "key": "search.brave.com"}, {"count": 11, "key": "www.ecosia.org"},
             {"count": 10, "key": "chromewebstore.google.com"}, {"count": 9, "key": "www.youtube.com"}]
UTM_1109 = [{"count": 715, "key": "reddit"}, {"count": 211, "key": "chatgpt.com"}, {"count": 160, "key": "instagram"},
            {"count": 112, "key": "youtube"}, {"count": 95, "key": "facebook"}, {"count": 50, "key": "macupdate"},
            {"count": 49, "key": "macmenubar"}, {"count": 31, "key": "youtube-latex"}]
# 2026-07-25: the same assistants arrived both ways.
REFS_0725 = [{"count": 30, "key": "www.google.com"}, {"count": 4, "key": "github.com"},
             {"count": 4, "key": "chatgpt.com"}, {"count": 3, "key": "www.linkedin.com"},
             {"count": 2, "key": "www.bing.com"}, {"count": 2, "key": "www.perplexity.ai"},
             {"count": 1, "key": "search.brave.com"}, {"count": 1, "key": "www.google.se"}]
UTM_0725 = [{"count": 4, "key": "perplexity"}, {"count": 4, "key": "chatgpt.com"}]


def test_chatgpt_tagged_only_by_utm_counts():
    ai, total, extra = td.ai_referred(REFS_1109, UTM_1109)
    assert (ai, extra) == (211, 211)
    assert total == sum(r["count"] for r in REFS_1109) + 211
    assert round(ai / total * 100, 1) == 10.4   # was 0% before the fix


def test_assistant_with_both_referrer_and_tag_counts_once():
    ai, total, extra = td.ai_referred(REFS_0725, UTM_0725)
    # chatgpt: referrer 4, utm 4 -> 4. perplexity: referrer 2, utm 4 -> 4 (2 extra).
    assert (ai, extra, total) == (8, 2, 49)


def test_trend_no_longer_reads_zero_on_1109():
    hist = {"snapshots": {f"2026-11-0{d}": {"topReferrers": REFS_1109, "topUtm": UTM_1109} for d in range(6, 10)}}
    hist["snapshots"]["2026-07-25"] = {"topReferrers": REFS_0725, "topUtm": UTM_0725}
    trend = td.ai_referrer_trend(hist)
    assert trend[0]["day"] == "2026-07-25" and round(trend[0]["pct"]) == 16
    assert trend[-1]["day"] == "2026-11-09" and trend[-1]["ai"] == 211 and trend[-1]["pct"] > 10


def test_gemini_is_an_assistant_not_google_search():
    rows = {r["key"]: r["count"] for r in td.channel_mix(
        [{"count": 645, "key": "www.google.com"}, {"count": 8, "key": "gemini.google.com"}], 2000,
        [{"count": 211, "key": "chatgpt.com"}])}
    assert rows["Search engines"] == 645
    assert rows["AI assistants"] == 219
    assert rows["Direct / untagged"] == 2000 - 645 - 219


def test_snapshot_keeps_25_referrers_and_utms():
    history = {"sites": {}}
    many = [{"count": 100 - i, "key": f"site{i}.example"} for i in range(30)]
    td.merge_history(history, "purplelink", {"generatedAt": "2026-11-09T09:00:00Z", "byDay": {},
                                             "topReferrers": many, "topUtm": many})
    snap = history["sites"]["purplelink"]["snapshots"]["2026-11-09"]
    assert len(snap["topReferrers"]) == 25 and len(snap["topUtm"]) == 25


ASA_1005 = {"asOf": "2026-10-05", "window": "Last 7 days",
            "campaigns": [{"key": "GlobePin - Search Results - US", "spend": 40.47, "installs": 15}]}


def test_asa_reading_stale_after_14_days():
    assert td.asa_reading_stale(ASA_1005, dt.date(2026, 11, 9))
    assert not td.asa_reading_stale(ASA_1005, dt.date(2026, 10, 19))
    assert not td.asa_reading_stale({"asOf": "?"}, dt.date(2026, 11, 9))


def test_old_asa_reading_left_out_of_last_7_days_acquisition():
    hist = {"sales": {}, "sites": {}, "appstore": {"days": {"2026-11-08": {"downloads": 3}}}}
    fresh = {**ASA_1005, "asOf": dt.date.today().isoformat()}
    assert [a["spend"] for a in td.revenue_metrics(hist, [], {"appleSearchAds": fresh})["acquisition"]] == [40.47]
    assert td.revenue_metrics(hist, [], {"appleSearchAds": ASA_1005})["acquisition"] == []
    assert "Acquisition" not in td.metrics_block(td.revenue_metrics(hist, [], {"appleSearchAds": ASA_1005}))
    html = td.manual_ads_block({"appleSearchAds": ASA_1005})
    assert "no reading since 2026-10-05" in html
