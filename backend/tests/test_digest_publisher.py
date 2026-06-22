import datetime
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from digest.curator import DigestData, DigestItem
from digest.publisher import render_html, render_email_html, render_index_entry


def _make_digest():
    return DigestData(
        date=datetime.date(2026, 6, 22),
        number=7,
        intro="Here is what caught my eye today in cybersecurity and AI.",
        sections={
            "Papers & Research": [
                DigestItem(
                    title="Adversarial Attacks on LLMs",
                    url="https://arxiv.org/abs/2606.12345",
                    source_name="arXiv",
                    category="papers",
                    editorial_note="This paper examines prompt injection at scale.",
                )
            ],
            "Cybersecurity": [
                DigestItem(
                    title="New Ransomware Variant",
                    url="https://bleepingcomputer.com/article",
                    source_name="Bleeping Computer",
                    category="cybersecurity",
                    editorial_note="Detailed breakdown of the attack chain.",
                )
            ],
        },
        sources_reviewed=45,
        items_selected=2,
    )


def test_render_html_contains_title():
    html = render_html(_make_digest())
    assert "Daily Digest #7" in html
    assert "June 22, 2026" in html


def test_render_html_contains_sections():
    html = render_html(_make_digest())
    assert "Papers &amp; Research" in html or "Papers & Research" in html
    assert "Cybersecurity" in html


def test_render_html_contains_items():
    html = render_html(_make_digest())
    assert "Adversarial Attacks on LLMs" in html
    assert "https://arxiv.org/abs/2606.12345" in html
    assert "prompt injection at scale" in html


def test_render_html_contains_subscribe_link():
    html = render_html(_make_digest())
    assert "subscribe" in html.lower() or "buttondown" in html.lower()


def test_render_html_no_inline_styles():
    html = render_html(_make_digest())
    assert ' style="' not in html


def test_render_index_entry_is_anchor():
    entry = render_index_entry(_make_digest())
    assert '<a ' in entry
    assert "digest/2026-06-22.html" in entry
    assert "Daily Digest #7" in entry
    assert "June 22, 2026" in entry


def test_render_email_html_has_no_nav():
    email = render_email_html(_make_digest())
    assert 'class="topbar"' not in email
    assert "Adversarial Attacks on LLMs" in email


import asyncio
from unittest.mock import AsyncMock, MagicMock
from digest.publisher import (
    github_count_digests,
    github_write_digest,
    github_update_digest_index,
    buttondown_send,
    publish,
)


class FakeGitHubListResp:
    status_code = 200
    def raise_for_status(self): pass
    def json(self):
        return [
            {"name": "2026-06-21.html", "type": "file"},
            {"name": "2026-06-20.html", "type": "file"},
            {"name": "index.html", "type": "file"},   # should not count
        ]


class FakeGitHubGetResp:
    status_code = 200
    def raise_for_status(self): pass
    def json(self):
        import base64
        content = "<html><body><!-- DIGEST_LIST_START --></body></html>"
        return {
            "content": base64.b64encode(content.encode()).decode(),
            "sha": "abc123",
            "encoding": "base64",
        }


class FakeGitHubPutResp:
    status_code = 201
    def raise_for_status(self): pass
    def json(self): return {}


def test_github_count_digests():
    async def run():
        client = AsyncMock()
        client.get.return_value = FakeGitHubListResp()
        return await github_count_digests(client, "token123")
    count = asyncio.run(run())
    assert count == 2


def test_github_write_digest_calls_put():
    async def run():
        client = AsyncMock()
        client.get.return_value = MagicMock(status_code=404, json=lambda: {})
        client.get.return_value.raise_for_status = lambda: None
        client.put.return_value = FakeGitHubPutResp()
        digest = _make_digest()
        await github_write_digest(client, "<html>test</html>", digest, "token123")
        assert client.put.called
        call_kwargs = client.put.call_args
        assert "2026-06-22.html" in str(call_kwargs)
    asyncio.run(run())


def test_github_update_digest_index_prepends_entry():
    async def run():
        client = AsyncMock()
        client.get.return_value = FakeGitHubGetResp()
        client.put.return_value = FakeGitHubPutResp()
        digest = _make_digest()
        entry = render_index_entry(digest)
        await github_update_digest_index(client, entry, "token123")
        assert client.put.called
        put_body = client.put.call_args[1]["json"]
        import base64
        content = base64.b64decode(put_body["content"]).decode()
        assert "Daily Digest #7" in content
    asyncio.run(run())


def test_buttondown_send_posts_email():
    async def run():
        client = AsyncMock()
        client.post.return_value = MagicMock(
            status_code=201,
            raise_for_status=lambda: None,
            json=lambda: {"id": "abc"},
        )
        digest = _make_digest()
        email_html = render_email_html(digest)
        await buttondown_send(client, digest, email_html, "bd_key_123")
        assert client.post.called
        call_kwargs = client.post.call_args[1]["json"]
        assert "Daily Digest #7" in call_kwargs["subject"]
        assert call_kwargs["status"] == "about_to_send"
    asyncio.run(run())


def test_publish_calls_all_three_steps(monkeypatch):
    write_called = []
    index_called = []
    bd_called = []

    async def _fake_count(client, token): return 6
    async def _fake_write(client, html, digest, token): write_called.append(1)
    async def _fake_index(client, entry, token): index_called.append(1)
    async def _fake_bd(client, digest, email_html, key): bd_called.append(1)

    monkeypatch.setattr("digest.publisher.github_count_digests", _fake_count)
    monkeypatch.setattr("digest.publisher.github_write_digest", _fake_write)
    monkeypatch.setattr("digest.publisher.github_update_digest_index", _fake_index)
    monkeypatch.setattr("digest.publisher.buttondown_send", _fake_bd)

    digest = _make_digest()
    asyncio.run(publish(digest, "gh_token", "bd_key"))

    assert write_called, "github_write_digest was not called"
    assert index_called, "github_update_digest_index was not called"
    assert bd_called, "buttondown_send was not called"
    assert digest.number == 7
