"""Tests for latextools.response_review.parse_reviewer_block."""
import inspect
import json
import re

from latextools.response_review import (
    parse_reviewer_block,
    _truncate_reviewers_json,
    run_response_review,
)


def test_numbered_parenthesized_comments():
    text = """Reviewer 1:
(1) First point.
(2) Second point.
"""
    result = parse_reviewer_block(text)
    assert len(result) == 1
    assert result[0]["reviewer"].startswith("Reviewer 1")
    assert result[0]["comments"] == ["First point.", "Second point."]


def test_comment_n_prefix():
    text = """R1:
Comment 1: First point.
Comment 2: Second point.
"""
    result = parse_reviewer_block(text)
    assert len(result[0]["comments"]) == 2


def test_dot_numbered_comments():
    text = """Reviewer 1:
1. First point.
2. Second point.
3. Third point.
"""
    result = parse_reviewer_block(text)
    assert len(result[0]["comments"]) == 3


def test_bulleted_comments_split_into_distinct_units():
    """Regression test: bullet lists must not collapse into one comment."""
    text = """Reviewer 1:
- The intro lacks motivation.
- Related work is thin.
- Fig 3 unreadable.
"""
    result = parse_reviewer_block(text)
    assert len(result) == 1
    assert result[0]["comments"] == [
        "The intro lacks motivation.",
        "Related work is thin.",
        "Fig 3 unreadable.",
    ]


def test_asterisk_bullets_split_into_distinct_units():
    text = """Reviewer 1:
* First concern.
* Second concern.
"""
    result = parse_reviewer_block(text)
    assert len(result[0]["comments"]) == 2


def test_multiple_reviewers_mixed_bullets_and_numbers():
    text = """Reviewer 1:
- The intro lacks motivation.
- Related work is thin.
- Fig 3 unreadable.

Reviewer 2:
1. Please clarify the sample size.
2. The discussion section needs more depth.
"""
    result = parse_reviewer_block(text)
    assert len(result) == 2
    assert result[0]["reviewer"].startswith("Reviewer 1")
    assert len(result[0]["comments"]) == 3
    assert result[1]["reviewer"].startswith("Reviewer 2")
    assert len(result[1]["comments"]) == 2


def test_unstructured_prose_falls_back_to_single_comment():
    text = """Reviewer 1:
This is just prose with no bullets or numbers, spanning multiple sentences
and containing no recognisable per-comment structure.
"""
    result = parse_reviewer_block(text)
    assert len(result[0]["comments"]) == 1


def test_empty_text_returns_empty_list():
    assert parse_reviewer_block("") == []
    assert parse_reviewer_block("   \n  ") == []


def test_no_reviewer_headers_falls_back_to_single_reviewer():
    text = "- concern one\n- concern two\n"
    result = parse_reviewer_block(text)
    assert len(result) == 1
    assert result[0]["reviewer"] == "Reviewer 1"


def test_referee_header_recognised():
    text = """Referee 1:
- The intro lacks motivation.
- Related work is thin.

Referee 2:
- Please clarify the sample size.
"""
    result = parse_reviewer_block(text)
    assert len(result) == 2
    assert result[0]["reviewer"].startswith("Referee 1")
    assert len(result[0]["comments"]) == 2
    assert result[1]["reviewer"].startswith("Referee 2")
    assert len(result[1]["comments"]) == 1


def test_lettered_reviewer_header_recognised():
    text = """Reviewer A:
- The intro lacks motivation.

Reviewer B (Methods):
- Please clarify the sample size.
- The discussion section needs more depth.
"""
    result = parse_reviewer_block(text)
    assert len(result) == 2
    assert result[0]["reviewer"].startswith("Reviewer A")
    assert len(result[0]["comments"]) == 1
    assert result[1]["reviewer"].startswith("Reviewer B")
    assert len(result[1]["comments"]) == 2
    # The parenthetical suffix must not leak into the comment body.
    assert "Methods" not in result[1]["comments"][0]


def test_r_letter_form_not_treated_as_header():
    """Bare 'R<letter>' (e.g. stray 'RA:' in prose) must NOT be parsed as a
    reviewer header — only 'R<digits>' is a safe unambiguous bare form."""
    text = "Reviewer 1:\n- Some point about RA: signalling in the model.\n"
    result = parse_reviewer_block(text)
    assert len(result) == 1
    assert result[0]["reviewer"].startswith("Reviewer 1")


# ---------------------------------------------------------------------------
# _truncate_reviewers_json
# ---------------------------------------------------------------------------


def _make_reviewers(n_reviewers: int, n_comments: int, comment_len: int = 400) -> list[dict]:
    filler = "x" * comment_len
    return [
        {
            "reviewer": f"Reviewer {i + 1}",
            "comments": [f"Comment {j + 1}: {filler}" for j in range(n_comments)],
        }
        for i in range(n_reviewers)
    ]


def test_truncate_reviewers_json_under_limit_returns_full_payload():
    reviewers = _make_reviewers(2, 2, comment_len=10)
    out = _truncate_reviewers_json(reviewers, max_chars=50_000)
    assert json.loads(out) == reviewers


def test_truncate_reviewers_json_over_limit_is_always_valid_json():
    """Regression test: a large realistic panel (5 reviewers x 14 comments)
    that overflows the truncation cap must still produce parseable JSON,
    never a mid-string cut."""
    reviewers = _make_reviewers(5, 14, comment_len=400)
    full = json.dumps(reviewers, indent=2)
    assert len(full) > 20_000  # sanity check: this reproduces the overflow

    out = _truncate_reviewers_json(reviewers, max_chars=20_000)
    parsed = json.loads(out)  # must not raise
    assert len(out) <= 20_000


def test_truncate_reviewers_json_keeps_early_reviewers_intact():
    """Comments/reviewers that fit must be fully preserved verbatim — only
    trailing content that doesn't fit should be dropped."""
    reviewers = _make_reviewers(5, 14, comment_len=400)
    out = _truncate_reviewers_json(reviewers, max_chars=20_000)
    parsed = json.loads(out)

    assert len(parsed) >= 1
    # Every reviewer/comment present in the truncated output must exactly
    # match the corresponding entry in the source (no partial/mangled text).
    for i, reviewer in enumerate(parsed):
        assert reviewer["reviewer"] == reviewers[i]["reviewer"]
        for j, comment in enumerate(reviewer["comments"]):
            assert comment == reviewers[i]["comments"][j]


def test_truncate_reviewers_json_empty_list():
    assert _truncate_reviewers_json([], max_chars=100) == "[]"


# ---------------------------------------------------------------------------
# Regression: author_response truncation must be consistent across the
# per-persona panel stage and the synthesis stage within run_response_review.
# A mismatch here means the panel personas can "see" and credit a response
# (e.g. one addressing Reviewer 3's comments near the end of a long letter)
# that the synthesis step truncates away, producing a report that
# contradicts its own panel findings (e.g. listing that same response under
# "Missing Responses").
# ---------------------------------------------------------------------------


def test_author_response_truncation_consistent_across_pipeline_stages():
    source = inspect.getsource(run_response_review)
    limits = [
        int(m.group(1).replace("_", ""))
        for m in re.finditer(r"author_response\[:(\d[\d_]*)\]", source)
    ]
    assert len(limits) >= 2, "expected author_response to be sliced at both the panel and synthesis stages"
    assert len(set(limits)) == 1, (
        f"author_response truncation limits differ across pipeline stages: {limits} "
        "— panel personas and the synthesis step must see the same amount of the "
        "author's response, or the final report can contradict the panel findings"
    )
