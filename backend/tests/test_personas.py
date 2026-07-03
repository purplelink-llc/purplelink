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
