# backend/tests/test_benchmark_arxiv_corpus.py
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from benchmark.arxiv_corpus import fetch_corpus, fetch_pdf

_ATOM_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2507.01234v2</id>
    <title>A Real Paper Title About Adversarial ML</title>
    <published>2026-07-01T12:00:00Z</published>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.CR" />
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2507.05678v1</id>
    <title>Another Paper
      With A Line Break In The Title</title>
    <published>2026-07-02T09:00:00Z</published>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.AI" />
  </entry>
</feed>"""


def test_fetch_corpus_parses_real_atom_shape():
    client = AsyncMock()
    resp = MagicMock()
    resp.text = _ATOM_FIXTURE
    resp.raise_for_status = lambda: None
    client.get.return_value = resp

    papers = asyncio.run(fetch_corpus(client, categories=["cs.CR"], max_results=10))

    assert len(papers) == 2
    assert papers[0].arxiv_id == "2507.01234"
    assert papers[0].title == "A Real Paper Title About Adversarial ML"
    assert papers[0].categories == ["cs.CR"]
    assert papers[1].arxiv_id == "2507.05678"
    assert "Line Break" in papers[1].title


def test_fetch_corpus_caps_max_results_at_100():
    client = AsyncMock()
    resp = MagicMock()
    resp.text = "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"
    resp.raise_for_status = lambda: None
    client.get.return_value = resp

    asyncio.run(fetch_corpus(client, max_results=500))

    params = client.get.call_args[1]["params"]
    assert params["max_results"] == 100


def test_fetch_corpus_returns_empty_on_request_failure():
    client = AsyncMock()
    client.get.side_effect = Exception("network error")

    papers = asyncio.run(fetch_corpus(client))
    assert papers == []


def test_fetch_corpus_returns_empty_on_malformed_xml():
    client = AsyncMock()
    resp = MagicMock()
    resp.text = "not xml at all <<<"
    resp.raise_for_status = lambda: None
    client.get.return_value = resp

    papers = asyncio.run(fetch_corpus(client))
    assert papers == []


def test_fetch_pdf_returns_bytes_on_success():
    client = AsyncMock()
    resp = MagicMock()
    resp.content = b"%PDF-1.4 fake pdf bytes"
    resp.raise_for_status = lambda: None
    client.get.return_value = resp

    result = asyncio.run(fetch_pdf(client, "2507.01234"))
    assert result == b"%PDF-1.4 fake pdf bytes"


def test_fetch_pdf_returns_none_on_failure():
    client = AsyncMock()
    client.get.side_effect = Exception("404")

    result = asyncio.run(fetch_pdf(client, "9999.99999"))
    assert result is None
