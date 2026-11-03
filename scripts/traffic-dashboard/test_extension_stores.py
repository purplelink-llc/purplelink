"""Firefox (AMO) and Edge Add-ons readings for Scholar Utility Belt: parsed from the public JSON, kept as a daily
series per store next to Chrome, and shown with the change since the previous reading. HTTP is mocked."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import urllib.error
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td

# Trimmed from the live AMO response, 2026-11-01.
AMO = {"average_daily_users": 1, "weekly_downloads": 3,
       "ratings": {"average": 0.0, "bayesian_average": 0.0, "count": 0, "text_count": 0},
       "current_version": {"version": "1.1.1"}, "last_updated": "2026-11-01T20:31:31Z",
       "url": "https://addons.mozilla.org/en-US/firefox/addon/google-scholar-utility-belt/"}
EDGE = {"name": "Scholar Utility Belt", "activeInstallCount": 12, "averageRating": 4.5, "ratingCount": 2,
        "version": "1.1.0"}


class _Resp:
    def __init__(self, body): self._b = json.dumps(body).encode()
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _serve(monkeypatch, routes, seen=None):
    def fake(req, timeout=None, context=None):
        if seen is not None:
            seen.append(req.full_url)
        for frag, body in routes.items():
            if frag in req.full_url:
                if isinstance(body, int):
                    raise urllib.error.HTTPError(req.full_url, body, "err", {}, io.BytesIO(b""))
                return _Resp(body)
        raise AssertionError(f"unexpected URL {req.full_url}")
    monkeypatch.setattr(td.urllib.request, "urlopen", fake)
    monkeypatch.setattr(td, "RETRIES", 1)


def test_amo_reading(monkeypatch):
    _serve(monkeypatch, {"addons.mozilla.org/api/v5/addons/addon/google-scholar-utility-belt/": AMO})
    r = td.fetch_amo(None)
    assert (r["users"], r["weeklyDownloads"], r["ratingCount"], r["version"]) == (1, 3, 0, "1.1.1")
    assert r["asOf"] == dt.date.today().isoformat()


def test_amo_failure_keeps_prior(monkeypatch):
    _serve(monkeypatch, {"addons.mozilla.org": 404})
    prior = {"users": 1, "asOf": "2026-10-31"}
    assert td.fetch_amo(prior) is prior


def test_edge_without_id_says_so_and_makes_no_request(monkeypatch):
    seen = []
    _serve(monkeypatch, {}, seen)
    assert td.fetch_edge_addon("", None) == {"missing": "Edge listing id not set"}
    assert seen == []


def test_edge_reading_and_failure(monkeypatch):
    _serve(monkeypatch, {"getproductdetailsbycrxid/abcdefghijklmnopabcdefghijklmnop": EDGE})
    r = td.fetch_edge_addon("abcdefghijklmnopabcdefghijklmnop", None)
    assert (r["users"], r["ratingAvg"], r["ratingCount"], r["version"]) == (12, 4.5, 2, "1.1.0")
    _serve(monkeypatch, {"getproductdetailsbycrxid": 404})
    assert td.fetch_edge_addon("abcdefghijklmnopabcdefghijklmnop", r) is r


def test_series_change_and_block():
    h = {}
    chrome = {"label": "Scholar Utility Belt", "url": "https://chromewebstore.google.com/x", "users": "1,000",
              "asOf": "2026-10-31"}
    td.record_extension_stores(h, {"chrome": chrome, "firefox": {**AMO, "users": 1, "asOf": "2026-10-31",
                                                                 "ratingCount": 0, "version": "1.1.0"},
                                   "edge": {"missing": "Edge listing id not set"}})
    td.record_extension_stores(h, {"chrome": {**chrome, "users": "1,100", "asOf": "2026-11-01"},
                                   "firefox": {"users": 4, "asOf": "2026-11-01", "ratingCount": 0,
                                               "version": "1.1.1", "url": AMO["url"]},
                                   "edge": {"missing": "Edge listing id not set"}})
    rows = {r["store"]: r for r in td.extension_store_rows(h)}
    assert rows["chrome"]["users"] == 1100 and rows["chrome"]["change"] == 100
    assert rows["firefox"]["change"] == 3 and rows["firefox"]["version"] == "1.1.1"
    assert rows["edge"]["missing"] == "Edge listing id not set" and rows["edge"]["users"] is None
    page = td.extension_stores_block(h)
    assert "Browser extension stores" in page and "Edge listing id not set" in page
    assert "<td>1,100</td><td>+100</td>" in page and "<td>4</td><td>+3</td><td>none yet</td><td>1.1.1</td>" in page


def test_stale_prior_does_not_land_on_today():
    h = {}
    td.record_extension_stores(h, {"firefox": {"users": 1, "asOf": "2026-10-31"}})
    td.record_extension_stores(h, {"firefox": {"users": 1, "asOf": "2026-10-31"}})  # fetch failed, prior returned
    assert list(h["extensionStores"]["firefox"]["days"]) == ["2026-10-31"]
    assert td.extension_stores_block({}) == ""
