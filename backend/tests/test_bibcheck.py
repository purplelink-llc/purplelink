"""Unit tests for latextools.bibcheck (pure logic, no network)."""
import importlib

import pytest
from latextools import bibcheck, core

has_bibtexparser = pytest.mark.skipif(
    importlib.util.find_spec("bibtexparser") is None,
    reason="bibtexparser not installed (run inside the Modal image)",
)


MINIMAL_BIB = r"""
@article{smith2023,
  author  = {Smith, John},
  title   = {A Study of Things},
  journal = {Journal of Things},
  year    = {2023},
  doi     = {10.1234/things.2023},
}

@inproceedings{jones2022,
  author    = {Jones, Alice},
  title     = {Fast Algorithms},
  booktitle = {Proc. ACM STOC},
  year      = {2022},
}
"""

MISSING_FIELDS_BIB = r"""
@article{bad2021,
  author = {Nobody},
  title  = {Missing Journal},
  year   = {2021},
}
"""

# ---------------------------------------------------------------------------
# core.validate_bib_upload
# ---------------------------------------------------------------------------

def test_validate_bib_upload_accepts():
    core.validate_bib_upload("refs.bib", 1024)


def test_validate_bib_upload_rejects_wrong_ext():
    with pytest.raises(core.ValidationError, match="must be a .bib"):
        core.validate_bib_upload("refs.tex", 1024)


def test_validate_bib_upload_rejects_empty():
    with pytest.raises(core.ValidationError, match="empty"):
        core.validate_bib_upload("refs.bib", 0)


def test_validate_bib_upload_rejects_too_large():
    with pytest.raises(core.ValidationError, match="too large"):
        core.validate_bib_upload("refs.bib", core.MAX_BIB_UPLOAD_BYTES + 1)


# ---------------------------------------------------------------------------
# bibcheck.parse_bib
# ---------------------------------------------------------------------------

@has_bibtexparser
def test_parse_bib_returns_entries():
    results = bibcheck.parse_bib(MINIMAL_BIB)
    assert len(results) == 2
    assert results[0].key == "smith2023"
    assert results[0].entry_type == "article"
    assert results[0].doi == "10.1234/things.2023"
    assert results[1].key == "jones2022"


@has_bibtexparser
def test_parse_bib_strips_doi_prefix():
    bib = r"@article{x, author={A}, title={T}, journal={J}, year={2020}, doi={https://doi.org/10.9/test}}"
    results = bibcheck.parse_bib(bib)
    assert results[0].doi == "10.9/test"


@has_bibtexparser
def test_parse_bib_empty_string():
    assert bibcheck.parse_bib("") == []


# ---------------------------------------------------------------------------
# completeness checks
# ---------------------------------------------------------------------------

@has_bibtexparser
def test_completeness_ok_article():
    results = bibcheck.parse_bib(MINIMAL_BIB)
    assert results[0].missing_fields == []


@has_bibtexparser
def test_completeness_missing_journal():
    results = bibcheck.parse_bib(MISSING_FIELDS_BIB)
    assert "journal" in results[0].missing_fields


@has_bibtexparser
def test_completeness_misc_has_no_required():
    bib = r"@misc{note2020, note={something}}"
    results = bibcheck.parse_bib(bib)
    assert results[0].missing_fields == []


# ---------------------------------------------------------------------------
# title normalization and similarity
# ---------------------------------------------------------------------------

def test_normalize_title_strips_latex():
    n = bibcheck.normalize_title(r"\textbf{Deep} Learning: {A Survey}")
    assert "deep" in n
    assert "\\" not in n
    assert "{" not in n


def test_title_similarity_identical():
    assert bibcheck.title_similarity("Deep Learning", "Deep Learning") == pytest.approx(1.0)


def test_title_similarity_completely_different():
    score = bibcheck.title_similarity("Quantum Mechanics", "Cooking Pasta")
    assert score < 0.4


def test_title_similarity_close():
    score = bibcheck.title_similarity(
        "Attention Is All You Need",
        "Attention is All You Need",
    )
    assert score > 0.95


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

@has_bibtexparser
def test_summarize_counts():
    results = bibcheck.parse_bib(MINIMAL_BIB + MISSING_FIELDS_BIB)
    summary = bibcheck.summarize(results)
    assert summary["total"] == 3
    assert summary["ok"] == 2
    assert summary["error"] == 1
    assert summary["warning"] == 0


# ---------------------------------------------------------------------------
# annotate_bib
# ---------------------------------------------------------------------------

@has_bibtexparser
def test_annotate_bib_adds_comment_above_entry():
    results = bibcheck.parse_bib(MINIMAL_BIB)
    annotated = bibcheck.annotate_bib(MINIMAL_BIB, results)
    assert "% [bib-validator]" in annotated
    comment_pos = annotated.index("% [bib-validator]")
    entry_pos = annotated.index("@article{smith2023")
    assert comment_pos < entry_pos


@has_bibtexparser
def test_annotate_bib_marks_missing_fields():
    results = bibcheck.parse_bib(MISSING_FIELDS_BIB)
    annotated = bibcheck.annotate_bib(MISSING_FIELDS_BIB, results)
    assert "MISSING" in annotated
    assert "journal" in annotated


@has_bibtexparser
def test_annotate_bib_marks_ok():
    results = bibcheck.parse_bib(MINIMAL_BIB)
    annotated = bibcheck.annotate_bib(MINIMAL_BIB, results)
    assert "OK" in annotated


# ---------------------------------------------------------------------------
# EntryResult.overall()
# ---------------------------------------------------------------------------

def test_overall_ok():
    r = bibcheck.EntryResult(key="x", entry_type="article")
    assert r.overall() == "ok"


def test_overall_error_on_missing_fields():
    r = bibcheck.EntryResult(key="x", entry_type="article", missing_fields=["journal"])
    assert r.overall() == "error"


def test_overall_error_on_dead_doi():
    r = bibcheck.EntryResult(key="x", entry_type="article", doi="10.x/y", doi_ok=False, doi_status=404)
    assert r.overall() == "error"


def test_overall_warning_on_low_crossref_confidence():
    r = bibcheck.EntryResult(key="x", entry_type="article")
    r.crossref_confidence = 0.65
    assert r.overall() == "warning"


def test_overall_error_on_very_low_crossref_confidence():
    r = bibcheck.EntryResult(key="x", entry_type="article")
    r.crossref_confidence = 0.2
    assert r.overall() == "error"


# ---------------------------------------------------------------------------
# Author normalization & comparison
# ---------------------------------------------------------------------------

def test_normalize_author_name_last_first():
    assert bibcheck.normalize_author_name("Smith, John") == "smith"


def test_normalize_author_name_first_last():
    assert bibcheck.normalize_author_name("John Smith") == "smith"


def test_normalize_author_name_initialed():
    assert bibcheck.normalize_author_name("J. A. Smith") == "smith"


def test_normalize_author_name_hyphenated():
    assert bibcheck.normalize_author_name("Smith-Jones, John") == "smith-jones"


def test_normalize_author_name_accented():
    # Accented characters should be folded so "Müller" matches "Muller"
    assert bibcheck.normalize_author_name("Müller, Otto") == "muller"


def test_normalize_author_name_handles_braces():
    assert bibcheck.normalize_author_name("{van der Berg}, Jan") == "van der berg"


def test_split_authors_simple():
    out = bibcheck.split_authors("Smith, John and Doe, Jane")
    assert out == ["Smith, John", "Doe, Jane"]


def test_split_authors_empty():
    assert bibcheck.split_authors("") == []


def test_split_authors_single():
    assert bibcheck.split_authors("Smith, John") == ["Smith, John"]


def test_author_similarity_identical_set():
    score = bibcheck.author_similarity(
        "Smith, John and Doe, Jane",
        ["Smith, John", "Doe, Jane"],
    )
    assert score == pytest.approx(1.0)


def test_author_similarity_different_formats():
    # Same authors expressed differently should still match
    score = bibcheck.author_similarity(
        "Smith, John and Doe, Jane",
        ["John A. Smith", "J. Doe"],
    )
    assert score == pytest.approx(1.0)


def test_author_similarity_partial_overlap():
    # 1 of 2 authors match → Jaccard = 1/3 (one shared, one only on each side)
    score = bibcheck.author_similarity(
        "Smith, John and Doe, Jane",
        ["Smith, J.", "Brown, Bob"],
    )
    assert 0.30 < score < 0.40


def test_author_similarity_no_overlap():
    score = bibcheck.author_similarity(
        "Smith, John",
        ["Brown, Bob"],
    )
    assert score == pytest.approx(0.0)


def test_author_similarity_empty_inputs():
    assert bibcheck.author_similarity("", []) == 0.0
    assert bibcheck.author_similarity("Smith, John", []) == 0.0
    assert bibcheck.author_similarity("", ["Smith, John"]) == 0.0


# ---------------------------------------------------------------------------
# Year mismatch detection
# ---------------------------------------------------------------------------

@has_bibtexparser
def test_year_mismatch_flag_set_when_off_by_two():
    bib = r"@article{x, author={A}, title={T}, journal={J}, year={2020}, doi={10.x/y}}"
    results = bibcheck.parse_bib(bib)
    r = results[0]
    r.crossref_year = 2015
    assert bibcheck.year_mismatch(r) is True


@has_bibtexparser
def test_year_mismatch_tolerates_one_year_drift():
    # Online vs print years often differ by 1 — not a mismatch
    bib = r"@article{x, author={A}, title={T}, journal={J}, year={2020}}"
    results = bibcheck.parse_bib(bib)
    r = results[0]
    r.crossref_year = 2021
    assert bibcheck.year_mismatch(r) is False


@has_bibtexparser
def test_year_mismatch_false_when_unknown():
    bib = r"@article{x, author={A}, title={T}, journal={J}, year={2020}}"
    results = bibcheck.parse_bib(bib)
    r = results[0]
    # Neither cr_year nor s2_year set → no mismatch
    assert bibcheck.year_mismatch(r) is False


# ---------------------------------------------------------------------------
# overall() with author mismatch
# ---------------------------------------------------------------------------

def test_overall_warning_on_author_mismatch():
    r = bibcheck.EntryResult(key="x", entry_type="article")
    r.crossref_confidence = 0.95  # title matches
    r.author_match = 0.3          # but authors don't
    assert r.overall() == "warning"


def test_overall_ok_when_authors_match():
    r = bibcheck.EntryResult(key="x", entry_type="article")
    r.crossref_confidence = 0.95
    r.author_match = 0.95
    assert r.overall() == "ok"


# ---------------------------------------------------------------------------
# correct_bib — produce a corrected .bib for high-confidence matches
# ---------------------------------------------------------------------------

@has_bibtexparser
def test_correct_bib_replaces_high_confidence_entry():
    bib = (
        "@article{x,\n"
        "  author = {Smith, John},\n"
        "  title  = {Old wrong title},\n"
        "  journal= {Old Journal},\n"
        "  year   = {2020},\n"
        "}\n"
    )
    results = bibcheck.parse_bib(bib)
    r = results[0]
    r.crossref_confidence = 0.95
    r.crossref_title = "The Correct Title"
    r.crossref_authors = ["Jane Doe"]
    r.crossref_year = 2019
    r.crossref_doi = "10.1234/correct"
    r.crossref_journal = "Correct Journal"

    corrected = bibcheck.correct_bib(bib, results)
    assert "The Correct Title" in corrected
    assert "Doe, Jane" in corrected
    assert "Correct Journal" in corrected
    assert "10.1234/correct" in corrected
    assert "Old wrong title" not in corrected


@has_bibtexparser
def test_correct_bib_preserves_low_confidence_entry():
    bib = (
        "@article{x,\n"
        "  author = {Smith, John},\n"
        "  title  = {Some Title},\n"
        "  journal= {Some Journal},\n"
        "  year   = {2020},\n"
        "}\n"
    )
    results = bibcheck.parse_bib(bib)
    r = results[0]
    r.crossref_confidence = 0.3  # below correction threshold
    r.crossref_title = "Different Paper"

    corrected = bibcheck.correct_bib(bib, results)
    # Should pass through unchanged
    assert "Some Title" in corrected
    assert "Different Paper" not in corrected


@has_bibtexparser
def test_correct_bib_adds_corrected_comment():
    bib = (
        "@article{x,\n"
        "  author = {Smith, John},\n"
        "  title  = {Wrong Title},\n"
        "  journal= {J},\n"
        "  year   = {2020},\n"
        "}\n"
    )
    results = bibcheck.parse_bib(bib)
    r = results[0]
    r.crossref_confidence = 0.95
    r.crossref_title = "Correct Title"
    r.crossref_authors = ["A. Author"]
    r.crossref_year = 2020

    corrected = bibcheck.correct_bib(bib, results)
    assert "% [bib-validator] CORRECTED from CrossRef" in corrected


@has_bibtexparser
def test_correct_bib_preserves_entry_key_and_type():
    bib = (
        "@inproceedings{my-key-2020,\n"
        "  author    = {Smith, John},\n"
        "  title     = {Old},\n"
        "  booktitle = {Old Conf},\n"
        "  year      = {2020},\n"
        "}\n"
    )
    results = bibcheck.parse_bib(bib)
    r = results[0]
    r.crossref_confidence = 0.95
    r.crossref_title = "New Title"
    r.crossref_authors = ["Jane Doe"]
    r.crossref_year = 2020
    r.crossref_journal = "Some Proc"  # CrossRef returns container-title

    corrected = bibcheck.correct_bib(bib, results)
    assert "@inproceedings{my-key-2020" in corrected


@has_bibtexparser
def test_correct_bib_with_no_results_unchanged():
    # No CrossRef matches → output equals input (modulo trailing newline)
    bib = "@article{x, author={A}, title={T}, journal={J}, year={2020}}\n"
    results = bibcheck.parse_bib(bib)
    corrected = bibcheck.correct_bib(bib, results)
    assert "@article{x" in corrected
    assert "title" in corrected
