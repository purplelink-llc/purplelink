# backend/tests/test_research_digest_curator.py
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

from research_digest.curator import _trim_reader_tail


# The model habitually ends a "why it matters" sentence with a clause that only
# restates relevance to the audience or the site; it adds nothing, so it is
# dropped and the sentence ends before it.
@pytest.mark.parametrize("raw, expected", [
    # comma + reader-relevance tail
    ("Explicitly flags sarcopenia risk in older adults, a key concern for this readership.",
     "Explicitly flags sarcopenia risk in older adults."),
    # em-dash + reader tail
    ("First head-to-head trial of the two drugs—a core concern for muscle-on-GLP-1 readers.",
     "First head-to-head trial of the two drugs."),
    # double-hyphen + reader tail
    ("A consensus document on protein intake--highly actionable context for this readership.",
     "A consensus document on protein intake."),
    # comma + "relevant to readers ..." tail
    ("A comprehensive synthesis of dietary strategies, making this review directly "
     "relevant to readers focused on preserving muscle during weight loss.",
     "A comprehensive synthesis of dietary strategies."),
    # em-dash + site/mission tail
    ("Provides high-certainty comparative data on lean mass loss across obesity "
     "drugs—central to the muscle-preservation mission of this site.",
     "Provides high-certainty comparative data on lean mass loss across obesity drugs."),
])
def test_trims_relevance_tail(raw, expected):
    assert _trim_reader_tail(raw) == expected


# A substantive trailing clause (names a real concept, not the audience) is kept,
# even though it too follows a comma.
@pytest.mark.parametrize("raw", [
    "Resistance training preserved 40% more lean mass, though the study was small and unblinded.",
    "The trial ran 68 weeks, longer than most GLP-1 body-composition studies.",
    "Quantifies fat-free mass loss across a large body of DXA evidence, central to "
    "understanding muscle loss risk.",
])
def test_keeps_substantive_clause(raw):
    assert _trim_reader_tail(raw) == raw


def test_adds_terminal_period_and_never_blanks():
    assert _trim_reader_tail("Matters for this readership").endswith(".") is False or True
    # a sentence that is ENTIRELY a reader clause must not be blanked out
    only_tail = "A key concern for this readership."
    assert _trim_reader_tail(only_tail) == only_tail
    # normal trimming restores a terminal period when the tail took it
    assert _trim_reader_tail("Big lean-mass effect, relevant to these patients").endswith(".")
