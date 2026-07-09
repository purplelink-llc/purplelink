import httpx
import pytest

from muscleonglp import draft


class _Resp:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {
            "content": [{"type": "text", "text": "## Introduction\nok"}]
        }
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeClient:
    def __init__(self, sequence):
        self._seq = list(sequence)
        self.calls = 0
        self.last_body = None

    async def post(self, url, json=None, headers=None):
        self.calls += 1
        self.last_body = json
        item = self._seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")


@pytest.mark.asyncio
async def test_draft_guide_returns_the_model_text():
    client = _FakeClient([_Resp(200)])
    out = await draft.draft_guide(client)
    assert out == "## Introduction\nok"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_draft_guide_prompt_includes_citation_keys():
    client = _FakeClient([_Resp(200)])
    await draft.draft_guide(client)
    assert "step1_semaglutide" in client.last_body["system"]


@pytest.mark.asyncio
async def test_draft_guide_prompt_flags_preprints():
    client = _FakeClient([_Resp(200)])
    await draft.draft_guide(client)
    assert "[PREPRINT]" in client.last_body["system"]
