"""Tests for the transient-failure retry hardening in papercheck._anthropic_message.

Mirrors the ModernTex ClaudeService fix: retry 429/529/timeouts with backoff (sleep patched to
no-op), re-raise everything else. Uses a fake httpx-like client so no network or key is needed.
"""
import httpx
import pytest

from latextools import papercheck


class _Resp:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {"content": [{"type": "text", "text": "ok"}]}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeClient:
    """Yields a queued sequence of responses/exceptions on successive .post calls."""
    def __init__(self, sequence):
        self._seq = list(sequence)
        self.calls = 0

    async def post(self, *args, **kwargs):
        self.calls += 1
        item = self._seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _fast(_):
        return None
    monkeypatch.setattr("asyncio.sleep", _fast)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")


@pytest.mark.asyncio
async def test_succeeds_first_try():
    client = _FakeClient([_Resp(200)])
    out = await papercheck._anthropic_message(
        client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    assert out == "ok"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds():
    client = _FakeClient([_Resp(429), _Resp(200)])
    out = await papercheck._anthropic_message(
        client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    assert out == "ok"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_retries_on_timeout_then_succeeds():
    client = _FakeClient([httpx.ReadTimeout("timed out"), _Resp(200)])
    out = await papercheck._anthropic_message(
        client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    assert out == "ok"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_raises_after_exhausting_retries_on_timeout():
    client = _FakeClient([httpx.ReadTimeout("t1"), httpx.ReadTimeout("t2"), httpx.ReadTimeout("t3")])
    with pytest.raises(httpx.TimeoutException):
        await papercheck._anthropic_message(
            client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    assert client.calls == 3


@pytest.mark.asyncio
async def test_does_not_retry_non_transient_4xx():
    # A 400 should surface immediately (one call), not be retried.
    client = _FakeClient([_Resp(400)])
    with pytest.raises(httpx.HTTPStatusError):
        await papercheck._anthropic_message(
            client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    assert client.calls == 1
