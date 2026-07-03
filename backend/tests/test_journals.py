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
