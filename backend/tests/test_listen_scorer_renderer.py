# backend/tests/test_listen_scorer_renderer.py
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from listen.sources import ListenItem
from listen.scorer import score_items
from listen.renderer import render_digest_html


def _item(i=0, source="hn", title="t"):
    return ListenItem(source=source, title=title, url=f"https://x/{i}", snippet="s", created_at=0, id=str(i))


def test_score_items_empty_returns_empty():
    client = AsyncMock()
    result = asyncio.run(score_items(client, []))
    assert result == []


def test_score_items_parses_matching_output():
    items = [_item(0), _item(1)]
    fake_json = (
        '[{"score": 5, "reasoning": "great fit", "draft_reply": "hey, try this"},'
        ' {"score": 1, "reasoning": "spam", "draft_reply": ""}]'
    )
    with patch("listen.scorer.anthropic_message", new=AsyncMock(return_value=fake_json)):
        results = asyncio.run(score_items(AsyncMock(), items))
    assert len(results) == 2
    assert results[0]["score"] == 5
    assert results[1]["draft_reply"] == ""


def test_score_items_handles_scoring_failure_gracefully():
    items = [_item(0)]
    with patch("listen.scorer.anthropic_message", new=AsyncMock(side_effect=Exception("boom"))):
        results = asyncio.run(score_items(AsyncMock(), items))
    assert len(results) == 1
    assert results[0]["score"] == 0


def test_score_items_handles_malformed_output():
    items = [_item(0), _item(1)]
    with patch("listen.scorer.anthropic_message", new=AsyncMock(return_value='{"not": "a list"}')):
        results = asyncio.run(score_items(AsyncMock(), items))
    assert len(results) == 2
    assert all(r["score"] == 0 for r in results)


def test_score_items_caps_batch_and_skips_rest():
    items = [_item(i) for i in range(3)]
    fake_json = '[{"score": 5, "reasoning": "r", "draft_reply": "d"}]'
    with patch("listen.scorer.BATCH_CAP", 1), \
         patch("listen.scorer.anthropic_message", new=AsyncMock(return_value=fake_json)):
        results = asyncio.run(score_items(AsyncMock(), items))
    assert len(results) == 3
    assert results[0]["score"] == 5
    assert results[1]["reasoning"] == "batch cap exceeded"
    assert results[2]["reasoning"] == "batch cap exceeded"


def test_render_digest_html_empty_case():
    html = render_digest_html([])
    assert "nothing today" in html.lower()


def test_render_digest_html_only_shows_actionable_scores():
    pairs = [
        (_item(0, title="High intent"), {"score": 5, "reasoning": "r", "draft_reply": "d"}),
        (_item(1, title="Low intent"), {"score": 1, "reasoning": "spam", "draft_reply": ""}),
    ]
    html = render_digest_html(pairs)
    assert "High intent" in html
    assert "Low intent" not in html
    assert "1 worth a look" in html
    assert "Reviewed 2 posts" in html


def test_render_digest_html_escapes_title():
    pairs = [(_item(0, title='<script>alert(1)</script>'), {"score": 5, "reasoning": "r", "draft_reply": ""})]
    html = render_digest_html(pairs)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
