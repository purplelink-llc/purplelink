"""RubbleFront shares Purplelink's analytics collector. The dashboard asks the stats function for its records by host,
keeps them as their own site, and Purplelink's own request never carries the host filter."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import traffic_dashboard as td  # noqa: E402


def _site(key):
    return next(s for s in td.SITES if s["key"] == key)


def test_rubblefront_is_its_own_site_on_the_shared_endpoint():
    rf, pl = _site("rubblefront"), _site("purplelink")
    assert rf["domain"] == "rubblefront.com"
    assert rf["url"] == pl["url"]
    assert rf["token_env"] == pl["token_env"] == "PURPLELINK_STATS_TOKEN"
    assert rf["stats_host"] == "rubblefront.com"
    assert "stats_host" not in pl
    assert rf["gsc_property"] == "sc-domain:rubblefront.com"
    assert [k for k, _ in rf["secondaries"]] == ["steamClicks", "outboundClicks", "downloads", "newsletterSubmits"]
    assert len({s["key"] for s in td.SITES}) == len(td.SITES)


def test_fetch_asks_for_the_host_only_for_rubblefront(monkeypatch):
    seen = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None, context=None):
        seen.append(req.full_url)
        return Resp(json.dumps({"totals": {}, "byDay": {}}).encode())

    monkeypatch.setattr(td.urllib.request, "urlopen", fake_urlopen)
    td.fetch_site(_site("rubblefront"), "tok en")
    td.fetch_site(_site("purplelink"), "tok en")
    assert seen[0].endswith("&host=rubblefront.com") and "token=tok%20en" in seen[0]
    assert "host=" not in seen[1]


def test_summary_reads_the_host_metrics():
    today = dt.datetime.now(dt.timezone.utc).date()
    days = {(today - dt.timedelta(days=i)).isoformat(): {"pageviews": 10, "uniques": 6, "steamClicks": 2, "outboundClicks": 1,
                                                          "downloads": 1, "newsletterSubmits": 1} for i in range(1, 9)}
    snap = {"topPaths": [{"key": "rubblefront.com/", "count": 50}], "topReferrers": [{"key": "reddit.com", "count": 20}],
            "topUtm": [{"key": "steam", "count": 5}], "toolRuns": []}
    hist = {"byDay": days, "snapshots": {today.isoformat(): snap}}
    s = td.summarise(_site("rubblefront"), hist)
    assert s["label"] == "RubbleFront" and s["domain"] == "rubblefront.com"
    labels = [sec["label"] for sec in s["secondaries"]]
    assert labels == ["Steam clicks", "outbound clicks", "downloads", "newsletter signups"]
    steam = next(sec for sec in s["secondaries"] if sec["key"] == "steamClicks")
    assert steam["value"] == 14


# ---- country, device, scroll depth and engaged time (stats.mjs ?host= breakdowns)

def _payload(scroll, **extra):
    p = {"generatedAt": "2026-10-12T07:00:00Z", "totals": {}, "byDay": {},
         "byCountry": {"top": [{"key": "US", "count": 9}, {"key": "DE", "count": 3}], "other": 2, "unknown": 4},
         "device": {"mobile": 10, "tablet": 1, "desktop": 7},
         "scrollDepth": scroll,
         "engagedTime": {"0-10s": 5, "10-30s": 4, "30-60s": 3, "1-3m": 2, "3m-plus": 1}}
    p.update(extra)
    return p


def test_audience_line_for_a_real_sample():
    a = td.audience_summary(_payload({"0": 10, "25": 10, "50": 10, "75": 5, "100": 5}))
    assert a["visits"] == 40 and a["reach50"] == 20 and a["pct50"] == 50
    assert a["sentence"] == "50 percent of visits reached 50 percent scroll (20 of 40)."
    assert [r["key"] for r in a["scroll"]] == ["0", "25", "50", "75", "100"]
    assert [r["key"] for r in a["engaged"]] == ["0-10s", "10-30s", "30-60s", "1-3m", "3m-plus"]
    assert a["device"] == [{"key": "mobile", "count": 10}, {"key": "tablet", "count": 1}, {"key": "desktop", "count": 7}]
    assert a["countryOther"] == 2 and a["countryUnknown"] == 4 and a["countries"][0] == {"key": "US", "count": 9}


def test_audience_line_guards_zero_and_tiny_samples():
    none = td.audience_summary(_payload({}))
    assert none["visits"] == 0 and none["pct50"] is None
    assert "No visit" in none["sentence"] and "percent of visits" not in none["sentence"]
    tiny = td.audience_summary(_payload({"0": 5, "50": 3, "100": 2}))
    assert tiny["visits"] == 10 and tiny["pct50"] is None
    assert tiny["sentence"].startswith("Only 10 visits") and "too few" in tiny["sentence"]
    one = td.audience_summary(_payload({"100": 1}))
    assert one["sentence"].startswith("Only 1 visit reported")
    edge = td.audience_summary(_payload({"0": 10, "50": 10}))
    assert edge["visits"] == 20 and edge["sentence"].startswith("50 percent of visits")


def test_audience_is_absent_without_the_new_fields_and_survives_garbage():
    assert td.audience_summary({"totals": {}, "byDay": {}}) is None
    assert td.audience_summary(None) is None
    a = td.audience_summary({"byCountry": "x", "device": [], "scrollDepth": {"50": "7", "0": -3}, "engagedTime": None})
    assert a["visits"] == 0 and a["countries"] == [] and a["countryUnknown"] == 0


def test_history_keeps_the_audience_and_the_summary_and_page_show_it():
    hist = {"sites": {}}
    td.merge_history(hist, "rubblefront", _payload({"0": 10, "25": 10, "50": 10, "75": 5, "100": 5},
                                                   byDay={"2026-10-11": {"pageviews": 3, "uniques": 2}}))
    assert hist["sites"]["rubblefront"]["latest"]["audience"]["visits"] == 40
    s = td.summarise(_site("rubblefront"), hist["sites"]["rubblefront"])
    assert s["audience"]["reach50"] == 20
    page = td.audience_card(s["audience"])
    assert "50 percent of visits reached 50 percent scroll" in page
    for needle in ("Countries", "Devices", "Scroll depth", "Time on page", "unknown", "other countries", "3m-plus", ">US<"):
        assert needle in page
    # An older response without the fields leaves the archive and the summary as they were.
    old = {"sites": {}}
    td.merge_history(old, "purplelink", {"generatedAt": "2026-10-12T07:00:00Z", "totals": {}, "byDay": {}})
    assert "audience" not in old["sites"]["purplelink"]["latest"]
    assert td.summarise(_site("purplelink"), old["sites"]["purplelink"])["audience"] is None
    assert td.audience_card(None) == ""
