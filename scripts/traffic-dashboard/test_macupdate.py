"""MacUpdate listing counts: parsed from the listing page, archived daily, turned into weekly figures, and shown
next to our own download counts."""
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td

# The parts of a real listing page (moderntex.macupdate.com, 2026-10-18) the parser reads, trimmed.
PAGE = ('<script type="application/ld+json">{"name":"ModernTex","operatingSystem":"macOS 14.0 or later",'
        '"offers":{"@type":"Offer","price":"10.00","priceCurrency":"USD"}}</script>'
        '<span>Version<!-- --> 1.3.0</span>'
        '<li class="specs_list_item"><h3 class="specs_list_title">OS</h3><p class="specs_list_description">'
        '<span>macOS 14.0</span> <!-- -->or later</p></li>'
        '<li class="specs_list_item"><h3 class="specs_list_title">Downloads</h3>'
        '<p class="specs_list_description">1,245</p></li>')


def test_parse_listing():
    assert td.parse_macupdate_listing(PAGE) == {"downloads": 1245, "version": "1.3.0", "price": 10.0}
    assert td.parse_macupdate_listing("<html>no specs</html>") is None


def test_weekly_figure_needs_a_reading_seven_days_back():
    h = {}
    day = dt.date(2026, 10, 18)
    td.merge_macupdate(h, "moderntex", {"downloads": 45, "version": "1.3.0", "price": 10.0}, "2026-10-18")
    s = td.macupdate_summary(h["macupdate"]["moderntex"], day)
    assert s["total"] == 45 and s["week"] is None and s["sinceFirst"] is None
    td.merge_macupdate(h, "moderntex", {"downloads": 49, "version": "1.11.0", "price": 19.99}, "2026-10-21")
    s = td.macupdate_summary(h["macupdate"]["moderntex"], dt.date(2026, 10, 21))
    assert s["week"] is None and s["sinceFirst"] == 4 and s["version"] == "1.11.0"
    td.merge_macupdate(h, "moderntex", {"downloads": 60, "version": "1.11.0", "price": 19.99}, "2026-10-25")
    s = td.macupdate_summary(h["macupdate"]["moderntex"], dt.date(2026, 10, 25))
    assert s["week"] == 15  # 60 against the 2026-10-18 reading
    td.merge_macupdate(h, "moderntex", {"downloads": 40, "version": "1.11.0", "price": 19.99}, "2026-10-26")
    assert td.macupdate_summary(h["macupdate"]["moderntex"], dt.date(2026, 10, 26))["week"] == 0  # never negative


def test_all_sources_rows_and_print(capsys):
    today = dt.date.today()
    d1 = (today - dt.timedelta(days=1)).isoformat()
    h = {"sites": {"purplelink": {"byDay": {d1: {"trialDownloads": 3, "lgTrialDownloads": 1}}}},
         "appstore": {"days": {d1: {"downloads": 2}}}, "macupdate": {}}
    td.merge_macupdate(h, "moderntex", {"downloads": 45, "version": "1.3.0", "price": 10.0},
                       (today - dt.timedelta(days=8)).isoformat())
    td.merge_macupdate(h, "moderntex", {"downloads": 52, "version": "1.11.0", "price": 19.99}, today.isoformat())
    rows = {r["app"]: r for r in td.downloads_all_sources(h, today)}
    assert rows["ModernTex"]["site7"] == 3 and rows["ModernTex"]["mu"]["week"] == 7
    assert rows["Legroom"]["site7"] == 1 and rows["Legroom"]["mu"] is None
    assert rows["GlobePin (App Store)"]["store7"] == 2
    td.print_downloads_all_sources(h)
    out = capsys.readouterr().out
    assert "MacUpdate   7 (52 all time), listing shows 1.11.0 at $19.99" in out
    assert "Mac apps incl. Vitae: 4 from our site, 7 from MacUpdate" in out


def test_redirected_listing_reads_as_not_live(monkeypatch):
    class R:
        def __init__(self, url): self._u = url
        def geturl(self): return self._u
        def read(self): return PAGE.encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(td.urllib.request, "urlopen", lambda req, timeout=20: R("https://www.macupdate.com/"))
    assert td.fetch_macupdate("https://legroom.macupdate.com/") is None
    monkeypatch.setattr(td.urllib.request, "urlopen", lambda req, timeout=20: R(req.full_url))
    assert td.fetch_macupdate("https://moderntex.macupdate.com/")["downloads"] == 1245
