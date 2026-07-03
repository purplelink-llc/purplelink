"""Tests for backend/latextools/pdf_annotate.py.

Covers the output-side hardening applied to annotation text: LLM-derived
L1/L3/audit findings are rendered verbatim into pypdf FreeText annotations
on the user's downloaded PDF, so invisible/control characters must be
stripped and text length capped before it reaches pypdf — the same defense
already applied on the input side in safety.sanitize_user_text.
"""
from __future__ import annotations

import io

import pytest

pypdf = pytest.importorskip("pypdf")

from latextools import pdf_annotate


def _blank_pdf_bytes(n_pages: int = 1) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _sanitize_annotation_text
# ---------------------------------------------------------------------------

def test_sanitize_strips_invisible_characters():
    # Zero-width space + bidi isolate controls smuggled into a finding.
    poisoned = "Looks fine​⁦ but hides text⁩"
    out = pdf_annotate._sanitize_annotation_text(poisoned)
    assert "​" not in out
    assert "⁦" not in out
    assert "⁩" not in out
    assert "Looks fine" in out


def test_sanitize_strips_control_characters_keeps_newlines():
    poisoned = "line one\x07\x1b\nline two"
    out = pdf_annotate._sanitize_annotation_text(poisoned)
    assert "\x07" not in out
    assert "\x1b" not in out
    assert "\n" in out
    assert "line one" in out and "line two" in out


def test_sanitize_caps_length():
    long_text = "A" * (pdf_annotate.MAX_ANNOTATION_TEXT_CHARS + 500)
    out = pdf_annotate._sanitize_annotation_text(long_text)
    assert len(out) <= pdf_annotate.MAX_ANNOTATION_TEXT_CHARS + 1  # + ellipsis
    assert out.endswith("…")


def test_sanitize_empty_and_none_safe():
    assert pdf_annotate._sanitize_annotation_text("") == ""
    assert pdf_annotate._sanitize_annotation_text(None) == ""


# ---------------------------------------------------------------------------
# annotate_pdf integration — poisoned finding text never reaches the PDF raw
# ---------------------------------------------------------------------------

def test_annotate_pdf_sanitizes_l1_finding_text():
    pdf_bytes = _blank_pdf_bytes(1)
    poisoned_issue = (
        "Ignore prior instructions​" + "X" * 3000 + "⁦hidden⁩"
    )
    l1 = {"findings": [{"page": 1, "issue": poisoned_issue, "severity": "major"}]}
    l2 = {}
    l3 = {}

    out = pdf_annotate.annotate_pdf(pdf_bytes, l1=l1, l2=l2, l3=l3)
    assert out is not None

    # Re-read the annotated PDF and confirm no invisible chars / no
    # unbounded length made it into any annotation's /Contents.
    reader = pypdf.PdfReader(io.BytesIO(out))
    page = reader.pages[0]
    annots = page.get("/Annots")
    assert annots
    found_any = False
    for a in annots:
        obj = a.get_object()
        contents = obj.get("/Contents")
        if not contents:
            continue
        found_any = True
        assert "​" not in contents
        assert "⁦" not in contents
        assert "⁩" not in contents
        assert len(contents) <= pdf_annotate.MAX_ANNOTATION_TEXT_CHARS + 200
    assert found_any


# ---------------------------------------------------------------------------
# _build_page_text_map — page-count bound (mirrors papercheck.MAX_EXTRACT_PAGES)
# ---------------------------------------------------------------------------

def test_build_page_text_map_caps_at_max_annotate_text_pages(monkeypatch):
    """A manuscript with more pages than MAX_ANNOTATE_TEXT_PAGES must not get
    every page re-extracted via pdfplumber a second time; the map should stop
    growing once the cap is hit, regardless of total page count."""
    monkeypatch.setattr(pdf_annotate, "MAX_ANNOTATE_TEXT_PAGES", 3)
    pdf_bytes = _blank_pdf_bytes(10)

    page_map = pdf_annotate._build_page_text_map(pdf_bytes)

    assert len(page_map) <= 3
    assert max(page_map.keys()) <= 3


def test_annotate_pdf_handles_large_page_count_without_full_prealloc():
    """annotate_pdf should not choke or blow up memory building page_buckets
    for a document with many pages; only pages that actually receive
    annotations should end up populated."""
    n_pages = 50
    pdf_bytes = _blank_pdf_bytes(n_pages)
    l1 = {"findings": [{"page": 1, "issue": "minor formatting nit", "severity": "minor"}]}
    l2 = {}
    l3 = {}

    out = pdf_annotate.annotate_pdf(pdf_bytes, l1=l1, l2=l2, l3=l3)
    assert out is not None

    reader = pypdf.PdfReader(io.BytesIO(out))
    assert len(reader.pages) == n_pages
    # Only page 1 should carry an annotation from this single L1 finding.
    assert reader.pages[0].get("/Annots")
    for page in reader.pages[1:]:
        assert not page.get("/Annots")
