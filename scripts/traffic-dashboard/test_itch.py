"""itch.io running totals for RubbleFront: one stored reading per day, changes computed from stored readings,
and a card that says plainly when the key is missing or the fetch failed."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import urllib.error
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import traffic_dashboard as td  # noqa: E402

GAME = {"id": 1, "title": "RubbleFront", "url": "https://rubblefront.itch.io/rubblefront", "published": True,
        "min_price": 499, "views_count": 120, "downloads_count": 30, "purchases_count": 4,
        "earnings": [{"currency": "USD", "amount": 1996, "amount_formatted": "$19.96"}]}


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_parses_games_and_sends_bearer(monkeypatch):
    seen = []

    def fake(req, timeout=None, context=None):
        seen.append(req)
        return Resp(json.dumps({"games": [GAME]}).encode())

    monkeypatch.setattr(td.urllib.request, "urlopen", fake)
    out = td.fetch_itch_games("k")
    assert seen[0].get_header("Authorization") == "Bearer k"
    assert seen[0].full_url == td.ITCH_MY_GAMES_URL  # the key travels in the header, never the URL
    assert out == {"games": [{"id": "1", "title": "RubbleFront", "url": GAME["url"], "published": True,
                              "minPrice": 499, "views": 120, "downloads": 30, "purchases": 4,
                              "earningsCents": 1996}]}


def test_fetch_reports_scope_error(monkeypatch):
    def fake(req, timeout=None, context=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {},
                                     io.BytesIO(b'{"errors":["api key does not permit `profile:games`"]}'))

    monkeypatch.setattr(td.urllib.request, "urlopen", fake)
    assert td.fetch_itch_games("k") == {"error": "HTTP 403: api key does not permit `profile:games`"}


def _reading(views, downloads, purchases, cents):
    g = {"id": "1", "title": "RubbleFront", "url": "u", "published": True, "minPrice": 499,
         "views": views, "downloads": downloads, "purchases": purchases, "earningsCents": cents}
    return {"games": [g]}


def test_changes_since_previous_and_seven_days():
    h = {}
    d0 = dt.date(2026, 11, 20)
    td.record_itch(h, _reading(100, 20, 2, 998), d0)
    td.record_itch(h, _reading(110, 22, 3, 1497), d0 + dt.timedelta(days=6))
    td.record_itch(h, _reading(150, 30, 4, 1996), d0 + dt.timedelta(days=7))
    r = td.itch_rows(h["itch"], d0 + dt.timedelta(days=7))[0]
    assert r["views"] == 150 and r["asOf"] == "2026-11-27"
    assert r["sincePrev"]["views"] == 40 and r["prevDay"] == "2026-11-26"
    assert r["last7"] == {"views": 50, "downloads": 10, "purchases": 2, "earningsCents": 998}


def test_first_reading_has_no_changes_and_error_keeps_old_days():
    h = {}
    td.record_itch(h, _reading(5, 1, 0, 0), dt.date(2026, 11, 27))
    td.record_itch(h, {"error": "HTTP 500"}, dt.date(2026, 11, 28))
    r = td.itch_rows(h["itch"], dt.date(2026, 11, 28))[0]
    assert r["sincePrev"] is None and r["last7"] is None
    html_out = td.itch_block(h["itch"])
    assert "Last fetch failed: HTTP 500" in html_out and "RubbleFront" in html_out


def test_block_without_key_says_how_to_set_up():
    out = td.itch_block(None)
    assert "Not set up" in out and "ITCH_API_KEY" in out


def test_card_only_on_rubblefront_tab():
    h = {}
    td.record_itch(h, _reading(5, 1, 0, 0), dt.date(2026, 11, 27))
    summaries = [td.summarise(s, {}) for s in td.SITES]
    page = td.render(summaries, [], "now", None, itch=h["itch"])
    rf = page.split("data-panel='site-rubblefront'")[1].split("<div data-panel=")[0]
    assert "itch.io · as of 2026-11-27" in rf
    assert page.count("itch.io · as of") == 1
