"""Unit coverage for app._format_citation_gap_md's zero-references case.

A PaperStructure with no extracted references and a well-cited paper with
no flagged gaps both produce gaps == [] from run_citation_gap. They must
render distinct messages: "no reference list was found" (extraction
failure / genuinely uncited manuscript) vs. "no obvious citation gaps
detected" (well-cited paper). Collapsing these into one message misleads
the author into thinking an unchecked manuscript was verified clean.

Imports `app` directly rather than going through the `client` fixture in
test_app_paper_review_endpoints.py because _format_citation_gap_md is a
pure function — importing the module doesn't touch Modal Dicts (those are
only hit on first .get/.put, not at import time).
"""
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import app as backend_app


def test_zero_references_extracted_gets_distinct_message():
    res = {
        "status": "ok",
        "gaps": [],
        "n_gaps": 0,
        "n_confirmed": 0,
        "n_references_reviewed": 0,
        "n_references_total": 0,
        "references_truncated": False,
        "no_references_extracted": True,
    }
    md = backend_app._format_citation_gap_md(res)
    assert "no reference list was found" in md
    assert "no obvious citation gaps detected" not in md


def test_well_cited_paper_keeps_reassuring_message():
    res = {
        "status": "ok",
        "gaps": [],
        "n_gaps": 0,
        "n_confirmed": 0,
        "n_references_reviewed": 12,
        "n_references_total": 12,
        "references_truncated": False,
        "no_references_extracted": False,
    }
    md = backend_app._format_citation_gap_md(res)
    assert "no obvious citation gaps detected" in md
    assert "no reference list was found" not in md


def test_missing_flag_defaults_to_well_cited_message():
    """Backward compatibility: older result dicts without the new key
    (e.g. cached results from before this fix) must not crash and must
    fall back to the original message rather than raising a KeyError."""
    res = {"status": "ok", "gaps": []}
    md = backend_app._format_citation_gap_md(res)
    assert "no obvious citation gaps detected" in md
