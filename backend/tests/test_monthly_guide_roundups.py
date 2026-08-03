# backend/tests/test_monthly_guide_roundups.py
"""Coverage for the roundup parser that feeds the paid monthly guide.

There was none before, which is how a silent data-loss bug survived in two
copies of this parser at once: every preprint was dropped from the month's
evidence, with no error and no short-count warning to notice.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from monthly_guide.roundups import (  # noqa: E402
    monthly_citation_block,
    parse_post_html,
)


def _item(url: str, title: str, meta: str, *, preprint: bool) -> str:
    """One roundup item as the site's renderer actually emits it."""
    badge = ' <span class="rr-preprint">Preprint</span>' if preprint else ""
    return (
        '<article class="rr-item">'
        f'<h2><a href="{url}" target="_blank" rel="noopener">{title}</a>{badge}</h2>'
        f'<p class="rr-meta">{meta}</p>'
        "<p>Summary sentence.</p>"
        "<p class=\"rr-why\"><strong>Why it matters:</strong> Because.</p>"
        "</article>"
    )


PEER = _item("https://doi.org/10.1/peer", "Peer reviewed paper",
             "Cell reports. Medicine · 2026-06-18 · Eisner K et al.",
             preprint=False)
PRE = _item("https://doi.org/10.2/pre", "Preprinted paper",
            "Preprint · 2026-07-23 · Ditchfield C et al.", preprint=True)


def test_preprint_badge_does_not_drop_the_paper():
    """The badge sits between </a> and </h2>. A title regex that required
    those two tags to be adjacent skipped every badged item — and preprints
    are most of the weekly supply (3 of 4 papers in the 2026-07-27 roundup),
    so the guide was synthesized from a fraction of the month's evidence."""
    _, papers = parse_post_html(PEER + PRE)
    assert [p.title for p in papers] == ["Peer reviewed paper", "Preprinted paper"]
    assert papers[1].url == "https://doi.org/10.2/pre"
    # the exact-title assertion above is what proves the badge didn't leak:
    # a naive fix that stops at </h2> would yield "Preprinted paper Preprint"
    assert not papers[1].title.endswith("Preprint")


def test_preprints_are_labelled_in_the_citation_block():
    """Including preprints is only safe if they stay marked as preprints: the
    synthesis prompt and the medical_safety red-team pass both read this block.
    The label comes from rr-meta ("Preprint · ..."), not the badge."""
    _, papers = parse_post_html(PEER + PRE)
    block = monthly_citation_block(papers)
    lines = [ln for ln in block.splitlines() if ln.strip()]
    assert len(lines) == 2, block
    assert "[PREPRINT]" not in lines[0], "peer-reviewed paper must not be labelled"
    assert lines[1].startswith("- (p2) [PREPRINT] "), lines[1]


def test_dek_and_empty_post_are_handled():
    dek, papers = parse_post_html(
        '<p class="article-dek">This week in GLP-1.</p>' + PRE)
    assert dek == "This week in GLP-1."
    assert len(papers) == 1
    # a post predating the rr-item markup yields nothing rather than crashing
    assert parse_post_html("<p>old post</p>") == ("", [])
