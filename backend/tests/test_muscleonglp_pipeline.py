import pytest

from muscleonglp import pipeline


@pytest.mark.asyncio
async def test_produce_guide_wires_stages_in_order(monkeypatch, tmp_path):
    calls = []

    async def fake_draft(client):
        calls.append("draft")
        return "draft text"

    async def fake_redteam(client, draft):
        calls.append(("redteam", draft))
        return "final text", []

    def fake_render(text, output_path):
        calls.append(("render", text, output_path))
        output_path.write_bytes(b"%PDF-fake")
        return output_path

    monkeypatch.setattr(pipeline, "draft_guide", fake_draft)
    monkeypatch.setattr(pipeline, "run_redteam_passes", fake_redteam)
    monkeypatch.setattr(pipeline, "render_guide_pdf", fake_render)

    output_path = tmp_path / "guide.pdf"
    result = await pipeline.produce_guide(object(), output_path)

    assert result == output_path
    assert calls[0] == "draft"
    assert calls[1] == ("redteam", "draft text")
    assert calls[2] == ("render", "final text", output_path)
    assert output_path.read_bytes() == b"%PDF-fake"
