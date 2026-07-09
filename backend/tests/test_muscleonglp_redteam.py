import json

import httpx
import pytest

from muscleonglp import redteam


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


def _verdict_resp(approved, edits=None):
    body = json.dumps({"approved": approved, "edits": edits or []})
    return _Resp(200, {"content": [{"type": "text", "text": body}]})


def _text_resp(text):
    return _Resp(200, {"content": [{"type": "text", "text": text}]})


class _FakeClient:
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
def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")


def test_parse_verdict_handles_fenced_json():
    raw = '```json\n{"approved": true, "edits": []}\n```'
    verdict = redteam._parse_verdict(raw, "medical_safety")
    assert verdict.approved is True
    assert verdict.edits == []


def test_parse_verdict_treats_malformed_json_as_not_approved():
    verdict = redteam._parse_verdict("not json at all", "voice")
    assert verdict.approved is False
    assert verdict.edits  # non-empty — a generic re-run request


@pytest.mark.asyncio
async def test_run_redteam_passes_all_approve_first_try():
    client = _FakeClient([_verdict_resp(True) for _ in redteam.PASS_ORDER])
    final_text, verdicts = await redteam.run_redteam_passes(client, "draft text")
    assert final_text == "draft text"
    assert [v.pass_name for v in verdicts] == redteam.PASS_ORDER
    assert all(v.approved for v in verdicts)
    assert client.calls == len(redteam.PASS_ORDER)


@pytest.mark.asyncio
async def test_run_redteam_passes_revises_then_approves():
    sequence = [
        _verdict_resp(False, ["fix citation"]),  # medical_safety: fails
        _text_resp("revised draft"),               # revision call
        _verdict_resp(True),                        # medical_safety: re-run, approves
        _verdict_resp(True),                        # legal_compliance
        _verdict_resp(True),                        # voice
        _verdict_resp(True),                        # originality
    ]
    client = _FakeClient(sequence)
    final_text, verdicts = await redteam.run_redteam_passes(client, "draft text")
    assert final_text == "revised draft"
    assert verdicts[0].pass_name == "medical_safety"
    assert client.calls == 6


@pytest.mark.asyncio
async def test_run_redteam_passes_raises_after_max_iterations():
    sequence = [
        _verdict_resp(False, ["edit 1"]),
        _text_resp("draft v2"),
        _verdict_resp(False, ["edit 2"]),
        _text_resp("draft v3"),
        _verdict_resp(False, ["edit 3"]),
    ]
    client = _FakeClient(sequence)
    with pytest.raises(redteam.RedTeamExhaustedError):
        await redteam.run_redteam_passes(client, "draft text")
    assert client.calls == 5
