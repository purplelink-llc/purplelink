"""Claims and Evidence table: the prompt asks for it, and quoted claims are
checked against the manuscript so an invented quote is marked, not shipped."""
from latextools import papercheck as p

BODY = (
    "Abstract. We show that the proposed method reduces error by 12% on the held-out set.\n"
    "Section 5. Our approach general-\nizes to unseen domains without fine-tuning."
)

REPORT = """# Manuscript Review

## What's Working
- Clear writing.

## Claims and Evidence

| Claim | Where | Evidence in the paper | Assessment |
|---|---|---|---|
| "reduces error by 12% on the held-out set" | Abstract | Table 2 reports 12% | Supported |
| "generalizes to unseen domains without fine-tuning" | Section 5 | Table 4 | Partly supported |
| "outperforms every baseline by a wide margin" | Abstract | None located in the text. | Not supported |
| "we show ... on the held-out set" | Abstract | Table 2 | Supported |

## Critical Blind Spots
- **[Confidence: high]** Something.
"""


def test_the_prompt_asks_for_the_table_in_the_right_place():
    core = p._L4_SYSTEM_CORE
    assert "## Claims and Evidence" in core
    assert core.index("## What's Working") < core.index("## Claims and Evidence") < core.index("## Critical Blind Spots")
    assert "| Claim | Where | Evidence in the paper | Assessment |" in core
    assert "No\ntestable claims were found in the extracted text." in core
    assert "Supported, Partly supported, Not supported,\n  Contradicted, Cannot assess" in core


def test_verbatim_quotes_pass_including_hyphenation_and_ellipsis():
    out = p.verify_claim_quotes(REPORT, BODY)
    rows = [l for l in out.split("\n") if l.startswith("|")]
    assert "quote not found" not in rows[2]      # verbatim, different quote marks
    assert "quote not found" not in rows[3]      # PDF hyphenation "general-\nizes"
    assert "quote not found" not in rows[5]      # ellipsis segments both present


def test_an_invented_quote_is_marked_and_the_table_is_footnoted():
    out = p.verify_claim_quotes(REPORT, BODY)
    bad = [l for l in out.split("\n") if "outperforms every baseline" in l][0]
    assert bad.endswith("Not supported (quote not found verbatim in the extracted text) |")
    assert out.count(p._QUOTE_NOTE) == 1
    # The footnote sits inside the section, before the next heading.
    assert out.index(p._QUOTE_NOTE) < out.index("## Critical Blind Spots")
    # Nothing else was lost.
    assert out.count("\n|") == REPORT.count("\n|")


def test_running_it_twice_changes_nothing_more():
    once = p.verify_claim_quotes(REPORT, BODY)
    assert p.verify_claim_quotes(once, BODY) == once


def test_no_section_no_body_or_no_flagged_rows_returns_the_input_unchanged():
    plain = "# Manuscript Review\n\n## What's Working\n- ok\n"
    assert p.verify_claim_quotes(plain, BODY) == plain
    assert p.verify_claim_quotes(REPORT, "") == REPORT
    clean = REPORT.replace('| "outperforms every baseline by a wide margin" | Abstract | None located in the text. | Not supported |\n', "")
    assert p.verify_claim_quotes(clean, BODY) == clean


def test_the_no_claims_sentence_is_left_alone():
    md = "## Claims and Evidence\nNo testable claims were found in the extracted text.\n\n## Critical Blind Spots\n- x\n"
    assert p.verify_claim_quotes(md, BODY) == md


def test_malformed_rows_are_never_dropped_or_changed():
    md = (
        "## Claims and Evidence\n\n| Claim | Where | Evidence in the paper | Assessment |\n|---|---|---|---|\n"
        '| "a | b" | Abstract | Table | Supported |\n'          # pipe inside a cell: five cells
        "| only two | cells |\n"
        '| "short" | Abstract | Table | Supported |\n'         # quote under the length floor
        "\n## Next\n"
    )
    assert p.verify_claim_quotes(md, BODY) == md


def test_non_string_input_does_not_raise():
    assert p.verify_claim_quotes("", BODY) == ""
    assert p.verify_claim_quotes("## Claims and Evidence\n| a | b | c | d |\n", None) == "## Claims and Evidence\n| a | b | c | d |\n"


def test_normalisation_handles_ligatures_case_and_punctuation():
    assert p._norm_for_match("The ﬁnal  RESULT, is: 12%!") == "the final result is 12"
    assert p._norm_for_match("self-\nsupervised") == "selfsupervised"


def test_layer4_applies_the_quote_check_to_the_model_output(monkeypatch):
    import asyncio

    async def fake_message(client, *, system, user_content, max_tokens, **kw):
        assert max_tokens >= 7_500          # room for the table
        assert "## Claims and Evidence" in system
        return "  " + REPORT + "\n"

    monkeypatch.setattr(p, "_anthropic_message", fake_message)

    class S:
        title = "T"
        page_count = 3
        references = []
        n_references_total = 0
        abstract = "A"
        body = BODY

    out = asyncio.run(p.run_layer_4_rectify(None, S(), {}, {}, {"merged_findings": [], "panel": []}))
    assert out["status"] == "ok"
    assert "Not supported (quote not found verbatim in the extracted text)" in out["markdown"]
    assert out["markdown"].startswith("# Manuscript Review")
