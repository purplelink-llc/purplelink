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
