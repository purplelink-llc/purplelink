# backend/tests/test_digest_curator.py
import asyncio
import datetime
import json
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from digest.curator import curate, SECTION_CAPS, MIN_ITEMS_TO_PUBLISH
from digest.harvester import RawItem


def _make_item(title, category, n=0):
    return RawItem(
        title=title,
        url=f"https://example.com/{n}",
        source_name="Test",
        snippet="A snippet.",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        category=category,
    )


FAKE_CLAUDE_RESPONSE = json.dumps({
    "intro": "Here is what caught my eye today.",
    "items": [
        {
            "title": "Adversarial Attacks on LLMs",
            "url": "https://example.com/0",
            "source_name": "arXiv",
            "category": "papers",
            "editorial_note": "This paper examines prompt injection at scale. The results are sobering for anyone deploying LLMs in production."
        },
        {
            "title": "New Ransomware Variant Targets Healthcare",
            "url": "https://example.com/1",
            "source_name": "Bleeping Computer",
            "category": "cybersecurity",
            "editorial_note": "Detailed breakdown of the attack chain. Worth reading if you work in defensive security."
        },
    ]
})


def test_curate_returns_digest_data(monkeypatch):
    async def _fake_llm(client, *, system, user_content, max_tokens, **k):
        return FAKE_CLAUDE_RESPONSE
    monkeypatch.setattr("digest.curator.anthropic_message", _fake_llm)

    items = [_make_item("Adversarial Attacks on LLMs", "papers", 0),
             _make_item("New Ransomware Variant", "cybersecurity", 1),
             _make_item("Morning news 1", "finance", 2),
             _make_item("Morning news 2", "finance", 3),
             _make_item("Morning news 3", "finance", 4),
             _make_item("Morning news 4", "finance", 5)]
    result = asyncio.run(curate(object(), items))

    assert result is not None
    assert result.intro == "Here is what caught my eye today."
    assert result.sources_reviewed == 6
    assert result.items_selected == 2
    assert result.date == datetime.date.today()


def test_curate_aborts_below_min_items(monkeypatch):
    async def _fake_llm(client, *, system, user_content, max_tokens, **k):
        return FAKE_CLAUDE_RESPONSE
    monkeypatch.setattr("digest.curator.anthropic_message", _fake_llm)

    items = [_make_item("One item only", "ai_tech", 0)]
    result = asyncio.run(curate(object(), items))
    assert result is None


def test_curate_respects_section_caps(monkeypatch):
    many_papers = [
        {"title": f"Paper {i}", "url": f"https://example.com/{i}",
         "source_name": "arXiv", "category": "papers",
         "editorial_note": "Note."}
        for i in range(10)
    ]
    response = json.dumps({"intro": "Today.", "items": many_papers})

    async def _fake_llm(client, *, system, user_content, max_tokens, **k):
        return response
    monkeypatch.setattr("digest.curator.anthropic_message", _fake_llm)

    items = [_make_item(f"Paper {i}", "papers", i) for i in range(10)]
    result = asyncio.run(curate(object(), items))
    papers = result.sections.get("Papers & Research", [])
    assert len(papers) <= SECTION_CAPS["papers"]
