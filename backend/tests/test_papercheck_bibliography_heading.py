"""Regression tests for backend/latextools/papercheck.py's bibliography
heading detection.

These lock in the real-world failure modes found by testing extract_paper()
against actual academic PDFs (two-column IEEE/ACM-style layouts, numbered
section headings, and pdfplumber's tendency to merge a short heading onto
the tail or front of an adjacent line): see the papercheck.py module for
the underlying two-column/x_tolerance extraction fixes these headings rely
on.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from latextools.papercheck import _bibliography_heading_split  # noqa: E402


def test_plain_heading_line_splits_at_end_of_line():
    line = "References"
    assert _bibliography_heading_split(line) == len(line)


def test_numbered_heading_line_splits_at_end_of_line():
    line = "9 References"
    assert _bibliography_heading_split(line) == len(line)


def test_heading_with_trailing_colon_splits_at_end_of_line():
    line = "References:"
    assert _bibliography_heading_split(line) == len(line)


def test_bibliography_variant_matches():
    line = "Bibliography"
    assert _bibliography_heading_split(line) == len(line)


def test_toc_entry_with_page_number_does_not_match():
    """'9 References 32' is a table-of-contents line (numbered section +
    trailing page number), not the real heading — must not match, or the
    whole document gets treated as one giant references blob."""
    assert _bibliography_heading_split("9 References 32") is None


def test_prose_ending_in_references_does_not_match():
    """Ordinary prose that happens to end a sentence with the word
    "references" must never be mistaken for a heading."""
    line = "We summarize the datasets, task, metrics, and references"
    assert _bibliography_heading_split(line) is None


def test_hyphen_merged_suffix_heading_splits_at_end_of_line():
    """Two-column extraction artifact: a hyphenated word-break from one
    column runs directly into the next column's heading on the same
    output line ('...unmod- References'). The whole line should be
    discarded (the split point is the end of the line), since the
    following line has the real first reference entry."""
    line = "uidity, or cross-venue dislocation. Additionally, unmod- References"
    assert _bibliography_heading_split(line) == len(line)


def test_prefix_merged_heading_splits_right_after_phrase():
    """Two-column extraction artifact in the other direction: the heading
    is the last thing in one column, and the next column's first reference
    entry starts immediately on the same output line ('References DeSarbo,
    Wayne S., ...'). The split point must be right after the heading
    phrase, so the entry itself isn't discarded."""
    line = "References DeSarbo, Wayne S., Venkatram Ramaswamy, and Steven H. Cohen"
    split_at = _bibliography_heading_split(line)
    assert split_at is not None
    assert line[split_at:] == "DeSarbo, Wayne S., Venkatram Ramaswamy, and Steven H. Cohen"


def test_prefix_heading_without_following_capital_does_not_match():
    """A line merely starting with 'references' followed by lowercase text
    is not a heading+entry merge — it's just prose, and must not match."""
    line = "references are listed in the appendix for completeness"
    assert _bibliography_heading_split(line) is None


def test_empty_and_unrelated_lines_do_not_match():
    assert _bibliography_heading_split("") is None
    assert _bibliography_heading_split("   ") is None
    assert _bibliography_heading_split("Introduction") is None
    assert _bibliography_heading_split("This is a real sentence of body text.") is None
