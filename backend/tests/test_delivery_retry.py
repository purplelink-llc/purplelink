"""Tests for the transient-failure retry hardening in delivery.send_email.

Mirrors test_anthropic_retry.py: retry network errors, 429, and 5xx with
backoff (sleep patched to no-op); fail fast on non-transient 4xx.
"""
import pytest

from latextools import delivery


class _Resp:
    def __init__(self, status_code, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"id": "email_123"}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


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
    monkeypatch.setenv("RESEND_API_KEY", "re_test")


@pytest.mark.asyncio
async def test_succeeds_first_try():
    client = _FakeClient([_Resp(200)])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out == {"status": "ok", "id": "email_123"}
    assert client.calls == 1


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds():
    client = _FakeClient([_Resp(429), _Resp(200)])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out["status"] == "ok"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_retries_on_5xx_then_succeeds():
    client = _FakeClient([_Resp(502, text="bad gateway"), _Resp(200)])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out["status"] == "ok"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_retries_on_network_error_then_succeeds():
    client = _FakeClient([ConnectionError("boom"), _Resp(200)])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out["status"] == "ok"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_exhausts_retries_and_returns_error():
    client = _FakeClient([_Resp(500), _Resp(502), _Resp(503)])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out["status"] == "error"
    assert out["reason"] == "resend_http_503"
    assert client.calls == 3


@pytest.mark.asyncio
async def test_does_not_retry_non_transient_4xx():
    client = _FakeClient([_Resp(422, text="invalid")])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out["status"] == "error"
    assert out["reason"] == "resend_http_422"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_domain_not_verified_returns_distinct_reason_not_retried():
    client = _FakeClient([
        _Resp(403, text='{"message": "The purplelink.llc domain is not verified"}'),
    ])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out["status"] == "error"
    assert out["reason"] == "domain_not_verified"
    assert client.calls == 1  # fails fast, no retry


@pytest.mark.asyncio
async def test_other_403_falls_back_to_generic_http_reason():
    client = _FakeClient([_Resp(403, text='{"message": "invalid API key"}')])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out["status"] == "error"
    assert out["reason"] == "resend_http_403"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_skips_when_no_api_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    client = _FakeClient([])
    out = await delivery.send_email(client, to="a@example.com", subject="s", html="<p>hi</p>")
    assert out == {"status": "skipped", "reason": "no_api_key"}
    assert client.calls == 0


@pytest.mark.asyncio
async def test_invalid_email_not_retried():
    client = _FakeClient([])
    out = await delivery.send_email(client, to="not-an-email", subject="s", html="<p>hi</p>")
    assert out == {"status": "error", "reason": "invalid_email"}
    assert client.calls == 0
