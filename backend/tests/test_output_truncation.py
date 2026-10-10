"""A model reply cut off at max_tokens must be noticed, not passed off as a finished report."""
import asyncio

import httpx

from latextools import papercheck as p


def _reply(stop_reason, text="partial text"):
    def handler(request):
        return httpx.Response(200, json={"content": [{"type": "text", "text": text}], "stop_reason": stop_reason,
                                         "usage": {"input_tokens": 10, "output_tokens": 20}})
    return handler


def _call(handler, monkeypatch, **kw):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await p._anthropic_message(c, system="s", user_content=[{"type": "text", "text": "u"}],
                                              max_tokens=50, **kw)
    return asyncio.run(go())


def test_callback_fires_only_when_cut_off(monkeypatch):
    hits = []
    assert _call(_reply("max_tokens"), monkeypatch, on_truncated=hits.append) == "partial text"
    assert hits == [p.DEFAULT_MODEL]
    hits.clear()
    _call(_reply("end_turn"), monkeypatch, on_truncated=hits.append)
    assert hits == []


def test_callback_is_optional(monkeypatch):
    assert _call(_reply("max_tokens"), monkeypatch) == "partial text"


def test_report_gets_a_note_when_cut_off():
    assert "cut off by the model's output limit" in p._TRUNCATION_NOTE
    assert "Fable" not in p._TRUNCATION_NOTE


def test_defaults_after_leaving_fable():
    assert p.DEFAULT_MODEL == "claude-opus-5-5"
    assert p.RECTIFY_MAX_OUTPUT_TOKENS >= 30_000
