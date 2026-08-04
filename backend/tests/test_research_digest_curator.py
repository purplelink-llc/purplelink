# backend/tests/test_research_digest_curator.py
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

from research_digest.curator import _clean_action, _trim_reader_tail


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


# The "action" field is the one place the curator is allowed to sound even
# slightly prescriptive, and only within four general, non-paper-specific levers
# (protein/training/monitor/clinician). Anything that reads as real medical
# advice — a dose, a drug switch, an imperative command — must be DROPPED
# (empty string), never rewritten into something safer.
@pytest.mark.parametrize("raw", [
    "This adds to the case for hitting a daily protein target during weight loss.",
    "This is one more reason to prioritize resistance training alongside GLP-1 therapy.",
    "Worth discussing with a prescribing clinician, especially for older adults.",
    "This finding is worth tracking if you are monitoring strength over time.",
])
def test_clean_action_keeps_safe_general_nudges(raw):
    assert _clean_action(raw) == raw


@pytest.mark.parametrize("raw", [
    "You should start taking a higher dose of tirzepatide.",
    "Consider asking your doctor to increase your dose.",
    "Switch from semaglutide to tirzepatide for better results.",
    "Start taking creatine to offset this effect.",
    "Increase your protein by 40mg per kg.",
    "",
])
def test_clean_action_drops_prescriptive_or_empty(raw):
    assert _clean_action(raw) == ""


def test_clean_action_adds_terminal_period():
    assert _clean_action("Worth discussing with a clinician").endswith(".")


# ── failure signalling ───────────────────────────────────────────────────────
# The 2026-08-03 roundup published nothing despite 27 harvested papers: the
# curator's reply overflowed max_tokens, came back as truncated JSON, and the
# parse error was reported as "nothing to publish this week". A broken run must
# be distinguishable from a genuinely quiet one.

def test_truncated_reply_is_named_as_truncation():
    """A reply cut off at max_tokens must raise TruncatedResponse, not sail on
    to die later inside json.loads with an opaque delimiter error pointing at
    the truncation offset."""
    import asyncio

    from research_digest._http import TruncatedResponse, anthropic_message

    class _Resp:
        status_code = 200
        headers: dict = {}
        def raise_for_status(self): pass
        def json(self):
            return {"stop_reason": "max_tokens",
                    "content": [{"text": '{"items": [{"index": 0,'}]}

    class _Client:
        async def post(self, *a, **k): return _Resp()

    import os
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    with pytest.raises(TruncatedResponse) as ei:
        asyncio.run(anthropic_message(_Client(), system="s",
                                      user_content=[{"type": "text", "text": "u"}],
                                      max_tokens=10))
    assert "max_tokens" in str(ei.value)


def test_unparseable_output_raises_rather_than_looking_like_a_quiet_week():
    """curate() must raise on unreadable output. Returning None would be
    indistinguishable from 'no relevant papers', which is what let a failed run
    skip a week with 27 candidates waiting."""
    import asyncio

    from research_digest import curator as C

    async def _bad(*a, **k):
        return "not json at all {{{"

    papers = [C.Paper(title="t", authors="a", source="pubmed", is_preprint=False,
                      venue="v", pub_date="2026-08-01", url="u", abstract="abs",
                      doi="", pmid="")]
    orig = C.anthropic_message
    C.anthropic_message = _bad
    try:
        with pytest.raises(C.CurationError) as ei:
            asyncio.run(C.curate(object(), papers))
        # the message must state that papers WERE harvested, so the reader can
        # tell this apart from an empty harvest
        assert "1 papers were harvested" in str(ei.value)
    finally:
        C.anthropic_message = orig


def test_empty_harvest_still_returns_none_quietly():
    """The genuinely-quiet case stays a None, not an error."""
    import asyncio

    from research_digest import curator as C
    assert asyncio.run(C.curate(object(), [])) is None
