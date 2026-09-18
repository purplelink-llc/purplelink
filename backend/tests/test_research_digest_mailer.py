# backend/tests/test_research_digest_mailer.py
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from research_digest.harvester import Paper
from research_digest.models import DigestItem, WeeklyDigest
from research_digest.mailer import (
    subscriber_email_html,
    notify_subscribers,
    SUBSCRIBER_SEND_DELAY,
)


def _digest():
    paper = Paper(
        title="Resistance training preserves lean mass during GLP-1 therapy",
        authors=["A. Researcher"],
        source="PubMed",
        is_preprint=False,
        venue="Journal of Clinical Endocrinology",
        pub_date="2026-09-10",
        url="https://pubmed.ncbi.nlm.nih.gov/example",
        abstract="An abstract.",
    )
    item = DigestItem(
        paper=paper,
        relevance=3,
        summary="A two-sentence plain-language summary of the finding.",
        why_it_matters="This matters because it is directly on-topic for readers.",
    )
    return WeeklyDigest(
        date="2026-09-14",
        week_label="September 14-20, 2026",
        slug="2026-09-14",
        intro="This week's roundup covers one notable paper.",
        items=[item],
    )


def test_subscriber_email_html_renders_every_item():
    html = subscriber_email_html(_digest())
    assert "Resistance training preserves lean mass during GLP-1 therapy" in html
    assert "Journal of Clinical Endocrinology" in html
    assert "A two-sentence plain-language summary" in html
    assert "This matters because" in html
    assert "September 14-20, 2026" in html


def test_subscriber_email_html_escapes_content():
    digest = _digest()
    digest.items[0].summary = "A <script>alert(1)</script> summary."
    html = subscriber_email_html(digest)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


class _FakeResp:
    def __init__(self, status_code=201, text="{}"):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    def __init__(self, status_code=201):
        self.status_code = status_code
        self.calls = []

    async def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResp(status_code=self.status_code)


def test_notify_subscribers_skips_without_key():
    client = _FakeClient()
    ok = asyncio.run(notify_subscribers(client, _digest(), ""))
    assert ok is False
    assert client.calls == []


def test_notify_subscribers_broadcasts_to_whole_list_scheduled_24h_out():
    client = _FakeClient(status_code=201)
    # publish_date is serialized with second precision (no microseconds), so
    # round the bounds the same way rather than let sub-second jitter make
    # this test flaky.
    before = datetime.now(timezone.utc).replace(microsecond=0)
    ok = asyncio.run(notify_subscribers(client, _digest(), "fake-key"))
    after = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=1)
    assert ok is True
    assert len(client.calls) == 1

    call = client.calls[0]
    assert call["url"] == "https://api.buttondown.email/v1/emails"
    assert call["headers"]["Authorization"] == "Token fake-key"

    body = call["json"]
    # No "filters" key at all: Buttondown's own default is the empty filter
    # group, which matches every subscriber -- this must stay a real
    # broadcast, never accidentally scoped to a subset.
    assert "filters" not in body
    assert body["status"] == "scheduled"
    assert "September 14-20, 2026" in body["subject"]

    publish_date = datetime.strptime(body["publish_date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    # Regression guard: this is the review buffer the whole design depends
    # on. If this silently became "now", public sends would go out before
    # Ben's own review email even lands.
    assert before + SUBSCRIBER_SEND_DELAY <= publish_date <= after + SUBSCRIBER_SEND_DELAY


def test_notify_subscribers_returns_false_on_http_error():
    client = _FakeClient(status_code=422)
    ok = asyncio.run(notify_subscribers(client, _digest(), "fake-key"))
    assert ok is False


def test_notify_subscribers_never_raises_on_transport_error():
    class _RaisingClient:
        async def post(self, *a, **k):
            raise ConnectionError("boom")

    ok = asyncio.run(notify_subscribers(_RaisingClient(), _digest(), "fake-key"))
    assert ok is False
