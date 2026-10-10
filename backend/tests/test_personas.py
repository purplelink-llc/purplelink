"""The adversarial review panel includes the deep equation / literature / number reviewers."""

from latextools import papercheck as p


def test_seven_personas_registered():
    assert p.N_PERSONAS == 7
    assert len(p.PERSONA_PROMPTS) == 7


def test_deep_reviewers_present_with_focus():
    for key in ("equation_analyst", "literature_auditor", "numerical_realist"):
        assert key in p.PERSONA_PROMPTS
        assert "<persona" in p.PERSONA_PROMPTS[key]
    assert "Dimensional" in p.PERSONA_PROMPTS["equation_analyst"]
    assert "Provability" in p.PERSONA_PROMPTS["equation_analyst"]
    assert "over-claimed" in p.PERSONA_PROMPTS["literature_auditor"]
    assert "add up" in p.PERSONA_PROMPTS["numerical_realist"]


def test_l4_report_has_new_sections():
    core = p._L4_SYSTEM_CORE
    assert "## Equation Audit" in core
    assert "## Literature & Citation Usage" in core
    assert "## Number Realism" in core
    assert "### Equation Analyst" in core  # panel transcript


# ---- caps and model for the persona calls (measured 2026-10-09) -------------------------------

def test_persona_and_report_caps_leave_room_for_a_5x_models_thinking():
    assert p.PERSONA_MAX_OUTPUT_TOKENS >= 12_000      # a persona review takes 5,000 to 6,000 tokens
    assert p.RECTIFY_MAX_OUTPUT_TOKENS >= 12_000
    assert p.L1_MAX_OUTPUT_TOKENS >= 6_000


def test_personas_run_on_opus_55_by_default_and_both_persona_paths_pass_the_model(monkeypatch):
    import asyncio
    assert p.PERSONA_MODEL == "claude-opus-5-5"
    seen = []

    async def fake(client, *, system, user_content, max_tokens, **kw):
        seen.append((kw.get("model"), max_tokens))
        return '[{"category": "stats", "severity": "major", "claim_quoted": "x", "issue": "y"}]'

    monkeypatch.setattr(p, "_anthropic_message", fake)
    s = p.PaperStructure(title="T", abstract="A", body="B" * 500, page_count=3)
    out = asyncio.run(p._run_one_persona(None, "methodology_critic", p.PERSONA_PROMPTS["methodology_critic"],
                                         s, {"findings": []}, {"issues": []}, "general"))
    assert out["status"] == "ok" and len(out["findings"]) == 1
    deep = asyncio.run(p._run_one_persona_deep(None, "methodology_critic", p.PERSONA_PROMPTS["methodology_critic"],
                                               s, {"findings": []}, {"issues": []}, [], "general"))
    assert seen[0] == ("claude-opus-5-5", 12_000)
    assert all(m == "claude-opus-5-5" for m, _ in seen)
