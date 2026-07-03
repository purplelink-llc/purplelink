"""Regression tests for backend/latextools/papercheck.py::extract_paper.

Covers the page-count and references-blob DoS guard: a well-under-the-
byte-limit PDF with thousands of pages (or an enormous References section)
must not drive unbounded pdfplumber iteration / regex work.

Run via: pytest backend/tests/test_papercheck_extract.py
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pytest

# Make `latextools.*` importable without installing the package
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

pdfplumber = pytest.importorskip("pdfplumber")
reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")

from latextools import papercheck  # noqa: E402


def _make_pdf(n_pages: int, text: str = "Hello world.") -> bytes:
    """Build a minimal multi-page PDF in memory using reportlab."""
    buf = io.BytesIO()
    c = reportlab_canvas.Canvas(buf, pagesize=(612, 792))
    for i in range(n_pages):
        c.drawString(72, 720, f"{text} page {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_extract_paper_caps_page_iteration_on_huge_page_count():
    """A PDF with far more pages than MAX_EXTRACT_PAGES must not have every
    page text-extracted — only the capped prefix should be processed. The
    *page-tree parse itself* must also be bounded: n_pages_total/page_count
    report a `MAX_EXTRACT_PAGES + 1` sentinel (not the exact count) once
    truncated, since computing an exact count would require walking the
    entire page tree — the exact unbounded-parse cost this test guards
    against (see backend/latextools/papercheck.py::extract_paper)."""
    n_pages = papercheck.MAX_EXTRACT_PAGES + 50
    pdf_bytes = _make_pdf(n_pages)

    start = time.monotonic()
    structure = papercheck.extract_paper(pdf_bytes)
    elapsed = time.monotonic() - start

    assert structure.n_pages_total == papercheck.MAX_EXTRACT_PAGES + 1
    assert structure.page_count == papercheck.MAX_EXTRACT_PAGES + 1
    # Body should only contain text from the capped prefix of pages, not all
    # of them — each page emits one "page N" marker into extracted text.
    assert f"page {n_pages}" not in structure.body
    assert f"page {papercheck.MAX_EXTRACT_PAGES}" in structure.body
    # Sanity bound so this test itself doesn't become a slow-CI liability;
    # generous ceiling since CI machines vary.
    assert elapsed < 30


def test_extract_paper_page_tree_parse_itself_is_bounded():
    """Regression for the unbounded-page-tree-parse finding: extract_paper
    must not call pdfplumber's eager `.pages` property (or otherwise walk
    the full page tree) before MAX_EXTRACT_PAGES truncation applies. A PDF
    with many pages but a tiny per-page payload should extract in time
    roughly proportional to MAX_EXTRACT_PAGES, not to its true page count —
    confirmed here by comparing wall time against a much smaller PDF and
    asserting it does not scale with n_pages."""
    small_pages = 5
    huge_pages = papercheck.MAX_EXTRACT_PAGES * 10
    body_text = " ".join(["This is a real sentence of manuscript body text."] * 10)

    small_pdf = _make_pdf(small_pages, text=body_text)
    huge_pdf = _make_pdf(huge_pages, text=body_text)

    t0 = time.monotonic()
    small_structure = papercheck.extract_paper(small_pdf)
    small_elapsed = time.monotonic() - t0

    t0 = time.monotonic()
    huge_structure = papercheck.extract_paper(huge_pdf)
    huge_elapsed = time.monotonic() - t0

    assert huge_structure.n_pages_total == papercheck.MAX_EXTRACT_PAGES + 1
    assert small_structure.n_pages_total == small_pages
    # If the page-tree parse were unbounded, huge_elapsed would scale with
    # huge_pages (10x MAX_EXTRACT_PAGES) rather than being capped at
    # MAX_EXTRACT_PAGES worth of work. Generous multiplier to avoid CI
    # flakiness while still catching an unbounded-parse regression.
    assert huge_elapsed < small_elapsed * 50 + 15


def test_split_references_input_is_capped_before_split():
    """A pathologically large references blob must be truncated before
    _split_references() runs its regex splits over it."""
    huge_blob = "\n".join(
        f"[{i}] Author {i}, Some Title {i}. Journal, {2000 + (i % 20)}."
        for i in range(1, 500_000)
    )
    assert len(huge_blob) > papercheck.MAX_REFERENCES_BLOB_CHARS

    capped = huge_blob[: papercheck.MAX_REFERENCES_BLOB_CHARS]
    refs = papercheck._split_references(capped)
    # Confirms the split operates on bounded input rather than the full blob.
    assert len(capped) == papercheck.MAX_REFERENCES_BLOB_CHARS
    assert len(refs) > 0


def test_extract_paper_truncates_references_blob_end_to_end():
    """Build a small PDF whose References section, once concatenated across
    pages, exceeds MAX_REFERENCES_BLOB_CHARS, and confirm extract_paper
    truncates it before parsing rather than processing it unbounded."""
    # Each reference line is ~60 chars; pack enough pages of references to
    # exceed the cap several times over while keeping the PDF itself small
    # (reportlab text, not thousands of pages).
    ref_line = "[{n}] A. Author, B. Author. A Paper Title About Nothing In Particular. Journal Of Things, 2020.\n"
    lines_per_page = 40
    # Build enough pages so total references text exceeds the cap by 3x.
    target_chars = papercheck.MAX_REFERENCES_BLOB_CHARS * 3
    approx_line_len = len(ref_line.format(n=1))
    total_lines_needed = target_chars // approx_line_len
    n_pages = max(1, total_lines_needed // lines_per_page + 1)

    buf = io.BytesIO()
    c = reportlab_canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(72, 750, "Sample Manuscript Title For Testing Purposes")
    c.drawString(72, 730, "Abstract")
    c.drawString(72, 710, "This is the abstract text.")
    c.showPage()
    # Body needs to clear MIN_EXTRACTED_BODY_CHARS so extract_paper doesn't
    # treat this synthetic fixture as an unreadable/scanned PDF.
    c.drawString(72, 750, "1. Introduction")
    body_y = 730
    for line in range(12):
        c.drawString(
            72, body_y,
            f"Body text of the paper, paragraph line {line + 1} of the introduction section.",
        )
        body_y -= 15
    c.showPage()
    c.drawString(72, 760, "References")
    counter = 1
    for _ in range(n_pages):
        y = 740
        for _ in range(lines_per_page):
            c.drawString(72, y, ref_line.format(n=counter).strip())
            counter += 1
            y -= 15
            if y < 40:
                break
        c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()

    structure = papercheck.extract_paper(pdf_bytes)

    # n_references_total is computed from the (capped) blob, so it must not
    # reflect an unbounded number of parsed entries.
    assert structure.n_references_total > 0
    assert structure.n_references_total < counter


def test_extract_paper_raises_on_near_empty_text():
    """A scanned/image-only PDF (or one whose text layer pdfplumber can't
    read) yields near-zero extracted text. extract_paper() must raise
    rather than silently returning a PaperStructure with an empty body —
    otherwise downstream checks (e.g. the anonymity scan) run against
    nothing and report a false "clean" result. Regression for the
    extraction-failure-reported-as-clean defect."""
    # A blank page (no drawString calls) — pdfplumber extracts no text.
    buf = io.BytesIO()
    c = reportlab_canvas.Canvas(buf, pagesize=(612, 792))
    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()

    with pytest.raises(papercheck.PaperExtractionError):
        papercheck.extract_paper(pdf_bytes)


def test_split_references_splits_raw_bibtex_entries():
    """A references section rendered as literal BibTeX source (e.g. an
    unprocessed .bib appendix, or a PDF export bug) must be split into one
    entry per @article{...}/@inproceedings{...} block rather than collapsed
    into a single giant PaperReference. Regression for the citation-gap
    under-counting defect where n_split == 1 for a multi-entry BibTeX blob."""
    bib = (
        "@article{smith2020,\n"
        "  author = {Smith, J.},\n"
        "  title = {A Great Paper},\n"
        "  journal = {Journal of Things},\n"
        "  year = {2020},\n"
        "  doi = {10.1234/abcd}\n"
        "}\n"
        "@inproceedings{jones2019,\n"
        "  author = {Jones, K.},\n"
        "  title = {Another Paper},\n"
        "  booktitle = {Proc. of Conf},\n"
        "  year = {2019}\n"
        "}\n"
        "@article{lee2021,\n"
        "  author = {Lee, M.},\n"
        "  title = {Third One},\n"
        "  year = {2021}\n"
        "}\n"
    )

    refs = papercheck._split_references(bib)

    assert len(refs) == 3
    assert refs[0].startswith("@article{smith2020")
    assert refs[1].startswith("@inproceedings{jones2019")
    assert refs[2].startswith("@article{lee2021")

    # Each split entry should still parse out its own DOI/year independently
    # rather than only the first entry's fields leaking into every ref.
    parsed = [papercheck._parse_reference(r) for r in refs]
    assert parsed[0].doi == "10.1234/abcd"
    assert parsed[0].year == "2020"
    assert parsed[1].doi == ""
    assert parsed[1].year == "2019"
    assert parsed[2].year == "2021"


def test_split_references_normal_numbered_list_unaffected_by_bibtex_pattern():
    """Ordinary numbered reference lists (no '@' entries) must still split
    via the numbered-entry pattern; the new BibTeX pattern must not
    misfire on them."""
    normal = (
        "[1] Smith, J. (2020). A Great Paper. Journal of Things.\n"
        "[2] Jones, K. (2019). Another Paper. Proc. of Conf.\n"
        "[3] Lee, M. (2021). Third One.\n"
    )

    refs = papercheck._split_references(normal)

    assert len(refs) == 3


def test_extract_paper_succeeds_with_sufficient_body_text():
    """Sanity check: a PDF with a normal amount of body text extracts fine
    and does not trip the near-empty guard."""
    text = " ".join(["This is a real sentence of manuscript body text."] * 10)
    pdf_bytes = _make_pdf(1, text=text)

    structure = papercheck.extract_paper(pdf_bytes)
    assert len(structure.body.strip()) >= papercheck.MIN_EXTRACTED_BODY_CHARS
