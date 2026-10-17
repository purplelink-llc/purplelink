"""The eval script (scripts/ai_review_eval.py) is never run in CI; these tests cover its offline parts only:
request building, the cost estimate and the report, with synthetic papers and fake batch results."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from latextools import papercheck as pc

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ev():
    spec = importlib.util.spec_from_file_location("ai_review_eval", REPO / "scripts" / "ai_review_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def old(ev):
    try:
        return ev.load_old_module(ev.DEFAULT_OLD_REF)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("old ref not available in this checkout (shallow clone)")


def _papers():
    s = pc.PaperStructure(title="T", abstract="A", body="We measured accuracy of 91.2 percent. " * 400, page_count=5)
    return [{"id": "9999.00001", "title": "T", "domain": "general", "structure": s}]


def test_old_module_has_the_old_prompts(old):
    assert old._build_persona_user_content.__name__ == "_build_persona_user_content"
    content = old._build_persona_user_content("P", _papers()[0]["structure"], {"findings": []}, {"issues": []}, "general")
    assert len(content) == 1 and "cache_control" not in content[0]          # one block, no breakpoint
    assert "Panel Transcript" in old.L4_SYSTEM


def test_requests_for_both_arms_and_the_estimate(ev, old):
    papers = _papers()
    reqs = ev.persona_requests(pc, old, papers)
    assert len(reqs) == 2 * pc.N_PERSONAS
    ids = {r["custom_id"] for r in reqs}
    assert "9999.00001__old__methodology_critic" in ids and "9999.00001__new__methodology_critic" in ids
    new = next(r for r in reqs if "__new__" in r["custom_id"])
    assert new["params"]["system"] == pc.PANEL_SYSTEM
    assert new["params"]["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert all("temperature" not in r["params"] for r in reqs)
    est = ev.estimate(pc, reqs, papers)
    assert est["persona_calls"] == 14 and est["l4_calls"] == 2 and 0 < est["batch_usd"] < est["list_price_usd"]


def test_report_end_to_end_with_fake_results(ev, old, tmp_path):
    papers = _papers()
    finding = [{"severity": "major", "issue": "No interval.", "claim_quoted": "accuracy of 91.2 percent"}]
    persona_res = {f"9999.00001__{arm}__{k}": {"text": json.dumps(finding), "stop_reason": "end_turn",
                                                "usage": {"input_tokens": 1000, "output_tokens": 500}}
                   for arm in ("old", "new") for k in pc.PERSONA_PROMPTS}
    l4 = ev.l4_requests(pc, old, papers, persona_res)
    assert [r["custom_id"] for r in l4] == ["9999.00001__old__l4", "9999.00001__new__l4"]
    old_user = l4[0]["params"]["messages"][0]["content"][0]["text"]
    new_user = l4[1]["params"]["messages"][0]["content"][0]["text"]
    assert old_user.count("No interval.") == 2 * 7 and new_user.count("No interval.") == 7   # old sent each twice
    report = "# Manuscript Review\n\n## Claims and Evidence\n| Claim | Where | Evidence in the paper | Assessment |\n|---|---|---|---|\n| \"x\" | A | T | Supported |\n\n## Critical Blind Spots\n- **[Confidence: high]** a\n\n## Citation Support Audit\nNone.\n"
    l4_res = {r["custom_id"]: {"text": report, "stop_reason": "end_turn", "usage": {"output_tokens": 100}} for r in l4}
    path = ev.write_report(pc, papers, persona_res, l4_res, tmp_path, {"batch_usd": 1.0}, seed=1)
    text = path.read_text()
    assert "## Layer 3 panel" in text and "## Key" in text and "Report A" in text
    assert (tmp_path / "raw.json").exists()
    assert ev.actual_cost({"input_tokens": 1_000_000}) == pytest.approx(2.0)      # $4 per MTok, halved for batch
