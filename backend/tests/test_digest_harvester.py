# backend/tests/test_digest_harvester.py
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from digest.sources import SOURCES, SourceDef, SourceType


def test_sources_is_nonempty():
    assert len(SOURCES) >= 10


def test_every_source_has_required_fields():
    for s in SOURCES:
        assert isinstance(s, SourceDef)
        assert s.name
        assert isinstance(s.type, SourceType)
        assert s.url
        assert s.category in {
            "papers", "ai_tech", "cybersecurity",
            "finance", "entrepreneurship", "general_tech",
        }


def test_no_duplicate_urls():
    urls = [s.url for s in SOURCES]
    assert len(urls) == len(set(urls)), "Duplicate URLs found in SOURCES"


def test_no_duplicate_names():
    names = [s.name for s in SOURCES]
    assert len(names) == len(set(names)), "Duplicate names found in SOURCES"

import asyncio
import datetime
from unittest.mock import patch
from digest.harvester import (
    _normalize_url,
    _is_fresh,
    fetch_rss,
    fetch_hn_algolia,
)


FAKE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Breaking: AI does stuff</title>
      <link>https://example.com/article-1</link>
      <pubDate>Mon, 22 Jun 2026 08:00:00 +0000</pubDate>
      <description>A summary of things.</description>
    </item>
    <item>
      <title>Old news nobody cares about</title>
      <link>https://example.com/article-old</link>
      <pubDate>Mon, 01 Jan 2024 08:00:00 +0000</pubDate>
      <description>Very old.</description>
    </item>
  </channel>
</rss>"""


class FakeResp:
    def __init__(self, content=FAKE_RSS, status_code=200):
        self.content = content
        self.status_code = status_code
    def raise_for_status(self): pass


class FakeClient:
    def __init__(self, resp):
        self._resp = resp
    async def get(self, url, **kwargs):
        return self._resp


def test_normalize_url_strips_utm():
    url = "https://example.com/article?utm_source=rss&utm_medium=feed"
    assert _normalize_url(url) == "https://example.com/article"


def test_normalize_url_strips_trailing_slash():
    assert _normalize_url("https://example.com/path/") == "https://example.com/path"


def test_is_fresh_recent():
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=10)
    assert _is_fresh(dt) is True


def test_is_fresh_stale():
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=60)
    assert _is_fresh(dt) is False


def test_fetch_rss_parses_items():
    src = SourceDef("Test Feed", SourceType.RSS, "https://example.com/feed", "ai_tech")
    client = FakeClient(FakeResp(FAKE_RSS))
    # Patch _is_fresh so only the recent item passes.
    with patch("digest.harvester._is_fresh", side_effect=lambda dt: "2026" in str(dt)):
        items = asyncio.run(fetch_rss(client, src))
    assert len(items) == 1
    assert items[0].title == "Breaking: AI does stuff"
    assert items[0].url == "https://example.com/article-1"
    assert items[0].source_name == "Test Feed"
    assert items[0].category == "ai_tech"


def test_fetch_rss_survives_http_error():
    src = SourceDef("Bad Feed", SourceType.RSS, "https://example.com/feed", "ai_tech")

    class ErrorResp:
        content = b""
        status_code = 503
        def raise_for_status(self):
            import httpx
            raise httpx.HTTPStatusError("503", request=None, response=self)

    items = asyncio.run(fetch_rss(FakeClient(ErrorResp()), src))
    assert items == []


FAKE_HN_RESPONSE = {
    "hits": [
        {
            "title": "Show HN: Something cool",
            "url": "https://example.com/hn",
            "points": 150,
            "created_at": "2026-06-22T08:00:00.000Z",
            "story_text": None,
        }
    ]
}


def test_fetch_hn_algolia_returns_items():
    src = SourceDef("Hacker News", SourceType.HN_ALGOLIA,
                    "https://hn.algolia.com/api/v1/search_by_date", "ai_tech",
                    params={"min_points": 100})

    class HNResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return FAKE_HN_RESPONSE

    with patch("digest.harvester._is_fresh", return_value=True):
        items = asyncio.run(fetch_hn_algolia(FakeClient(HNResp()), src))
    assert len(items) == 1
    assert items[0].title == "Show HN: Something cool"


from digest.harvester import (
    fetch_arxiv_oai,
    fetch_semantic_scholar,
    fetch_openalex,
    fetch_huggingface_papers,
)

FAKE_OAI_RESPONSE = b"""<?xml version="1.0"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <metadata>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>Adversarial Attacks on LLMs</dc:title>
          <dc:identifier>https://arxiv.org/abs/2606.12345</dc:identifier>
          <dc:description>We study adversarial attacks on large language models.</dc:description>
          <dc:date>2026-06-22</dc:date>
        </oai_dc:dc>
      </metadata>
    </record>
  </ListRecords>
</OAI-PMH>"""


def test_fetch_arxiv_oai_returns_items():
    src = SourceDef("arXiv", SourceType.ARXIV_OAI,
                    "http://export.arxiv.org/oai2", "papers",
                    params={"sets": ["cs:AI"]})
    client = FakeClient(FakeResp(FAKE_OAI_RESPONSE))
    with patch("digest.harvester._is_fresh", return_value=True):
        items = asyncio.run(fetch_arxiv_oai(client, src))
    assert len(items) == 1
    assert items[0].title == "Adversarial Attacks on LLMs"
    assert "arxiv.org" in items[0].url


FAKE_S2_RESPONSE = {
    "data": [
        {
            "paperId": "abc123",
            "title": "LLM Security Survey",
            "abstract": "A survey of security issues in LLMs.",
            "publicationDate": "2026-06-21",
            "externalIds": {"ArXiv": "2606.99999"},
        }
    ],
    "token": None,
}


def test_fetch_semantic_scholar_returns_items():
    src = SourceDef("Semantic Scholar", SourceType.SEMANTIC_SCHOLAR,
                    "https://api.semanticscholar.org/graph/v1/paper/search/bulk",
                    "papers", params={"queries": ["cybersecurity LLM"]})

    class S2Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return FAKE_S2_RESPONSE

    with patch("digest.harvester._is_fresh", return_value=True):
        items = asyncio.run(fetch_semantic_scholar(FakeClient(S2Resp()), src))
    assert len(items) == 1
    assert items[0].title == "LLM Security Survey"
    assert items[0].snippet == "A survey of security issues in LLMs."


FAKE_OPENALEX_RESPONSE = {
    "results": [
        {
            "id": "https://openalex.org/W9999",
            "title": "Cyber Threat Detection via ML",
            "abstract_inverted_index": {"Cyber": [0], "threats": [1], "detected": [2]},
            "publication_date": "2026-06-20",
            "primary_location": {
                "landing_page_url": "https://doi.org/10.1/test"
            },
        }
    ]
}


def test_fetch_openalex_returns_items():
    src = SourceDef("OpenAlex", SourceType.OPENALEX,
                    "https://api.openalex.org/works", "papers")

    class OAResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return FAKE_OPENALEX_RESPONSE

    with patch("digest.harvester._is_fresh", return_value=True):
        items = asyncio.run(fetch_openalex(FakeClient(OAResp()), src))
    assert len(items) == 1
    assert items[0].title == "Cyber Threat Detection via ML"


FAKE_HF_PAPERS = [
    {
        "paper": {
            "id": "2606.11111",
            "title": "Diffusion Agents for Code",
            "summary": "We propose a new approach using diffusion.",
            "publishedAt": "2026-06-22T00:00:00.000Z",
        }
    }
]


def test_fetch_huggingface_papers_returns_items():
    src = SourceDef("HuggingFace Daily Papers", SourceType.HF_PAPERS,
                    "https://huggingface.co/api/daily_papers", "papers")

    class HFResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return FAKE_HF_PAPERS

    with patch("digest.harvester._is_fresh", return_value=True):
        items = asyncio.run(fetch_huggingface_papers(FakeClient(HFResp()), src))
    assert len(items) == 1
    assert items[0].title == "Diffusion Agents for Code"
    assert "arxiv.org" in items[0].url


from unittest.mock import AsyncMock
from digest.harvester import harvest_all, RawItem as _RawItem  # noqa: F401 — ensures RawItem in scope

# Alias so the test body can use the name directly
RawItem = _RawItem


def test_harvest_all_deduplicates_by_url(monkeypatch):
    """Two sources returning the same URL (trailing slash differs) → one item."""
    item_a = RawItem("Title A", "https://example.com/post", "Source A",
                     "snippet a", datetime.datetime.now(datetime.timezone.utc), "ai_tech")
    item_b = RawItem("Title B", "https://example.com/post/", "Source B",
                     "snippet b", datetime.datetime.now(datetime.timezone.utc), "cybersecurity")

    async def _fake_rss(client, src): return [item_a]
    async def _fake_rss2(client, src): return [item_b]
    async def _fake_empty(client, src): return []

    monkeypatch.setattr("digest.harvester.fetch_rss", _fake_rss)
    monkeypatch.setattr("digest.harvester.fetch_hn_algolia", _fake_empty)
    monkeypatch.setattr("digest.harvester.fetch_arxiv_oai", _fake_empty)
    monkeypatch.setattr("digest.harvester.fetch_semantic_scholar", _fake_empty)
    monkeypatch.setattr("digest.harvester.fetch_openalex", _fake_empty)
    monkeypatch.setattr("digest.harvester.fetch_huggingface_papers", _fake_empty)

    import digest.sources as _src_mod
    from digest.sources import SourceType, SourceDef
    orig_sources = list(_src_mod.SOURCES)
    _src_mod.SOURCES = [
        SourceDef("S1", SourceType.RSS, "https://s1.com/feed", "ai_tech"),
        SourceDef("S2", SourceType.RSS, "https://s2.com/feed", "cybersecurity"),
    ]
    try:
        items = asyncio.run(harvest_all(object()))
    finally:
        _src_mod.SOURCES = orig_sources

    # Both items have the same normalized URL → only one survives.
    assert len(items) == 1


def test_harvest_all_source_failure_does_not_block(monkeypatch):
    """If all fetchers return empty, harvest_all returns []."""
    monkeypatch.setattr("digest.harvester.fetch_rss", AsyncMock(return_value=[]))
    monkeypatch.setattr("digest.harvester.fetch_hn_algolia", AsyncMock(return_value=[]))
    monkeypatch.setattr("digest.harvester.fetch_arxiv_oai", AsyncMock(return_value=[]))
    monkeypatch.setattr("digest.harvester.fetch_semantic_scholar", AsyncMock(return_value=[]))
    monkeypatch.setattr("digest.harvester.fetch_openalex", AsyncMock(return_value=[]))
    monkeypatch.setattr("digest.harvester.fetch_huggingface_papers", AsyncMock(return_value=[]))
    items = asyncio.run(harvest_all(object()))
    assert items == []
