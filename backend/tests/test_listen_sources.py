# backend/tests/test_listen_sources.py
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from listen.sources import fetch_hn, fetch_stackexchange, KEYWORDS


def _hn_response(hits):
    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.json = lambda: {"hits": hits}
    return resp


def test_fetch_hn_dedupes_across_keyword_queries():
    now = time.time()
    hit = {
        "objectID": "123",
        "title": "How do I respond to reviewer 2?",
        "url": "https://example.com/story",
        "created_at_i": now,
    }
    client = AsyncMock()
    client.get.return_value = _hn_response([hit])

    items = asyncio.run(fetch_hn(client))

    assert client.get.call_count == len(KEYWORDS)
    assert len(items) == 1
    assert items[0].id == "123"
    assert items[0].source == "hn"


def test_fetch_hn_falls_back_to_item_url_when_missing():
    now = time.time()
    hit = {"objectID": "456", "title": "Ask HN: manuscript rejected", "created_at_i": now}
    client = AsyncMock()
    client.get.return_value = _hn_response([hit])

    items = asyncio.run(fetch_hn(client))

    assert items[0].url == "https://news.ycombinator.com/item?id=456"


def test_fetch_hn_skips_failed_queries():
    client = AsyncMock()
    client.get.side_effect = Exception("network error")

    items = asyncio.run(fetch_hn(client))

    assert items == []


def _se_response(items):
    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.json = lambda: {"items": items}
    return resp


def test_fetch_stackexchange_dedupes_and_strips_html():
    q = {
        "question_id": 789,
        "title": "How to write a response to reviewers letter?",
        "link": "https://academia.stackexchange.com/q/789",
        "body": "<p>I need <b>help</b> with this.</p>",
        "creation_date": time.time(),
    }
    client = AsyncMock()
    client.get.return_value = _se_response([q])

    items = asyncio.run(fetch_stackexchange(client))

    assert client.get.call_count == len(KEYWORDS)
    assert len(items) == 1
    assert items[0].id == "789"
    assert "<b>" not in items[0].snippet
    assert "help" in items[0].snippet


def test_fetch_stackexchange_skips_failed_queries():
    client = AsyncMock()
    client.get.side_effect = Exception("network error")

    items = asyncio.run(fetch_stackexchange(client))

    assert items == []
