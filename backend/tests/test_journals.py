"""Tests for backend/latextools/journals.py check_compliance rules."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from latextools.journals import check_compliance
from latextools.papercheck import PaperStructure


def _structure(word_count: int) -> PaperStructure:
    body = " ".join(["word"] * word_count)
    return PaperStructure(title="T", abstract="", body=body, page_count=1)


def _manuscript_wc_result(cap: int, word_count: int) -> dict:
    spec = {
        "key": "custom",
        "name": "Custom Journal",
        "domain": "general",
        "manuscript_max_words": cap,
    }
    result = check_compliance(_structure(word_count), spec)
    rules = {r["rule"]: r for r in result["results"]}
    return rules["manuscript_word_count"]


def test_manuscript_word_count_pass_note_matches_status():
    # 950/1000 -> within [0.9*cap, cap], should pass with reassuring note.
    r = _manuscript_wc_result(cap=1000, word_count=950)
    assert r["status"] == "pass"
    assert "Approximately within target" in r["note"]


def test_manuscript_word_count_fail_note_matches_status():
    r = _manuscript_wc_result(cap=1000, word_count=1200)
    assert r["status"] == "fail"
    assert "above target" in r["note"]


def test_manuscript_word_count_warn_note_does_not_say_within_target():
    # 500/1000 -> below 0.9*cap threshold, should warn — note text must
    # reflect the warning, not reuse the pass-branch reassurance text.
    r = _manuscript_wc_result(cap=1000, word_count=500)
    assert r["status"] == "warn"
    assert "Approximately within target" not in r["note"]
    assert "500" in r["note"] and "1000" in r["note"]


# --- Information Systems packs (MISQ, CAIS) and section detection ---------

from latextools.journals import (  # noqa: E402
    JOURNAL_SPECS,
    _has_section,
    list_journals_for_domain,
)

# Values of the domain radios on site/tools/paper-review/upload/index.html.
_UPLOAD_DOMAINS = {
    "general", "machine_learning", "biomedicine",
    "psychology_social", "chemistry_materials",
}


def test_every_spec_domain_is_selectable_on_upload_form():
    for key, spec in JOURNAL_SPECS.items():
        assert spec["domain"] in _UPLOAD_DOMAINS, key


def test_is_packs_listed_for_general_and_psychology():
    for domain in ("general", "psychology_social"):
        keys = {j["key"] for j in list_journals_for_domain(domain)}
        assert {"misq", "cais"} <= keys, domain


def _is_structure(abstract_words: int) -> PaperStructure:
    body = "1 Introduction\ntext\n5 Conclusion\ntext\n"
    return PaperStructure(
        title="T", abstract=" ".join(["w"] * abstract_words),
        body=body, page_count=40,
    )


def test_misq_pack_rules():
    result = check_compliance(_is_structure(180), "misq")
    assert "error" not in result
    rules = {r["rule"]: r for r in result["results"]}
    # No caps are encoded for MISQ, so no count rules and no hard fails.
    assert "abstract_word_count" not in rules
    assert "manuscript_word_count" not in rules
    assert "page_count" not in rules
    assert rules["anonymous_submission"]["status"] == "info"
    assert rules["reference_style"]["status"] == "info"
    assert not any(r.startswith(("section_", "recommended_")) for r in rules)
    assert result["summary"]["n_fail"] == 0


def test_cais_pack_abstract_cap_and_single_blind():
    ok = check_compliance(_is_structure(200), "cais")
    rules = {r["rule"]: r for r in ok["results"]}
    assert rules["abstract_word_count"]["status"] == "pass"
    assert "anonymous_submission" not in rules
    assert "page_count" not in rules
    assert ok["summary"]["n_fail"] == 0
    over = check_compliance(_is_structure(201), "cais")
    rules = {r["rule"]: r for r in over["results"]}
    assert rules["abstract_word_count"]["status"] == "fail"


def test_has_section_accepts_roman_and_dotted_numbering():
    assert _has_section("x\nI. INTRODUCTION\ntext", ["introduction"])
    assert _has_section("x\nIV. Discussion\n", ["discussion"])
    assert _has_section("x\n4.1 Results\n", ["results"])
    assert _has_section("x\n3. Methods\n", ["methods"])
    assert not _has_section("we discuss the introduction of x", ["introduction"])
