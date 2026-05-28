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
