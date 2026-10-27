# backend/tests/test_muscleonglp_indexing.py
"""Coverage for getmuscleonglp.com indexing and the monthly page template.

Search Console showed every weekly roundup since 2026-08-31 as "Discovered -
currently not indexed", the /research/ hub's sitemap lastmod stuck at
2026-08-22, nothing pinging IndexNow for the site, and the monthly guide
template shipping pages without analytics and with a $5 handbook price.
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from monthly_guide import publish  # noqa: E402
from research_digest import indexnow  # noqa: E402
from research_digest.publisher import HUB_URL, _sitemap_add, bump_lastmod  # noqa: E402


def _sitemap(*entries: tuple[str, str]) -> str:
    urls = "".join(
        f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{mod}</lastmod>\n"
        f"    <changefreq>weekly</changefreq>\n    <priority>0.9</priority>\n  </url>\n"
        for loc, mod in entries
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")


# ---------------------------------------------------------------- lastmod ----

def test_bump_lastmod_changes_only_the_named_entry():
    xml = _sitemap((HUB_URL, "2026-08-22"), ("https://getmuscleonglp.com/learn/", "2026-08-01"))
    out = bump_lastmod(xml, HUB_URL, "2026-11-02")
    assert f"<loc>{HUB_URL}</loc>\n    <lastmod>2026-11-02</lastmod>" in out
    assert "<lastmod>2026-08-01</lastmod>" in out


def test_bump_lastmod_does_not_touch_a_longer_url_with_the_same_prefix():
    post = HUB_URL + "2026-10-26/"
    xml = _sitemap((post, "2026-10-26"))
    assert bump_lastmod(xml, HUB_URL, "2026-11-02") == xml


def test_weekly_roundup_refreshes_the_hub_lastmod():
    xml = _sitemap((HUB_URL, "2026-08-22"))
    out = _sitemap_add(xml, "2026-11-02", "2026-11-02")
    assert f"<loc>{HUB_URL}</loc>\n    <lastmod>2026-11-02</lastmod>" in out
    assert "<loc>https://getmuscleonglp.com/research/2026-11-02/</loc>" in out
    assert out.count(f"<loc>{HUB_URL}</loc>") == 1


def test_monthly_sitemap_add_refreshes_the_guides_hub(tmp_path):
    (tmp_path / "sitemap.xml").write_text(_sitemap((publish.GUIDES_HUB_URL, "2026-08-22")))
    assert publish.sitemap_add(str(tmp_path), "research-review-2026-10", "2026-11-01")
    xml = (tmp_path / "sitemap.xml").read_text()
    assert f"<loc>{publish.GUIDES_HUB_URL}</loc>\n    <lastmod>2026-11-01</lastmod>" in xml
    assert "<loc>https://getmuscleonglp.com/guides/research-review-2026-10/</loc>" in xml


# --------------------------------------------------------------- indexnow ----

def test_payload_keeps_only_site_urls_once_in_order():
    body = indexnow.build_payload([
        "https://getmuscleonglp.com/research/x/", "https://purplelink.llc/a/",
        "https://getmuscleonglp.com/research/", "https://getmuscleonglp.com/research/x/",
    ])
    assert body["host"] == "getmuscleonglp.com"
    assert body["keyLocation"] == f"https://getmuscleonglp.com/{indexnow.KEY}.txt"
    assert body["urlList"] == ["https://getmuscleonglp.com/research/x/", "https://getmuscleonglp.com/research/"]


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code


class _Client:
    def __init__(self, status=202, error=None):
        self.status, self.error, self.calls = status, error, []

    async def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        if self.error:
            raise self.error
        return _Resp(self.status)


def test_ping_posts_to_the_shared_endpoint():
    client = _Client(status=202)
    assert asyncio.run(indexnow.ping(client, [HUB_URL])) is True
    url, body = client.calls[0]
    assert url == indexnow.ENDPOINT and body["urlList"] == [HUB_URL]


def test_ping_failures_never_raise():
    assert asyncio.run(indexnow.ping(_Client(status=403), [HUB_URL])) is False
    assert asyncio.run(indexnow.ping(_Client(error=OSError("down")), [HUB_URL])) is False


def test_ping_with_no_site_urls_skips_the_request():
    client = _Client()
    assert asyncio.run(indexnow.ping(client, ["https://example.com/"])) is False
    assert client.calls == []


# ------------------------------------------------------------- templates ----

def test_landing_page_loads_analytics_and_shows_real_prices():
    page = publish._render_landing("research-review-2026-10", "Review", "October 2026", [])
    assert '<script src="/analytics.js" defer></script>' in page
    assert f"covers the fundamentals for {publish.HANDBOOK_PRICE}." in page
    assert "One dollar" not in page
    assert "__" not in page  # no unfilled placeholders


def test_success_page_loads_analytics():
    page = publish._render_success("research-review-2026-10", "Review", "October 2026")
    assert '<script src="/analytics.js"></script>' in page
