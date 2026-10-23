"""Coherence check (latextools/coherence.py): input parsing, rule checks, Paper Bible quote verification,
the model stages with a fake model, and the flag-gated internal endpoint. No network."""
import asyncio
import json
import re

import pytest

from latextools import coherence as c


LATEX = r"""
\documentclass{article}
\newcolumntype{P}[1]{>{\bfseries\raggedright\arraybackslash}p{#1}}
\title{Trust in Robo-Advisors}
\begin{document}
\maketitle
\begin{abstract}
We survey 412 investors and find that transparency raises trust by 12.4\% (see the results).
Accuracy reaches 92.1\%.
\end{abstract}
\section{Introduction}
Large Language Models (LLMs) are used by robo-advisors \cite{smith2020, lee2021}. % a comment 99.9\%
We make two contributions. We ask RQ1: does transparency raise trust? We also ask RQ2: does it last?
\section{Theory}
\subsection{Hypotheses}
H1: Transparency increases trust. H2: Trust increases adoption. H3: Risk aversion moderates H1.
\section{Method}
We recruited 412 investors. A large language model (LLM) generated the vignettes; see Table~\ref{tab:a}.
\begin{table}[htbp]
\begin{tabular}{lr}
Measure & Value \\ \hline
Accuracy & 0.921 \\
\end{tabular}
\end{table}
\section{Results}
H1 is supported: trust rose by 12.7\%. H2 is supported. The first research question is answered by H1.
\section{Discussion}
\subsection{Limitations}
The sample is small.
\section{Conclusion}
Transparency matters.
\end{document}
"""


def _ms():
    return c.from_latex(LATEX)


# --- input --------------------------------------------------------------------------------------------

def test_latex_sections_roles_and_markup():
    ms = _ms()
    assert ms.title == "Trust in Robo-Advisors"
    assert "412 investors" in ms.abstract
    titles = [(s.title, s.role) for s in ms.sections]
    assert ("Abstract", "abstract") in titles
    assert ("Hypotheses", "theory") in titles
    # an empty "Discussion" heading still gives its subsection a role
    assert ("Limitations", "limitations") in titles
    body = ms.body_text()
    assert "[cite: smith2020, lee2021]" in body
    assert "[ref: tab:a]" in body
    assert "Accuracy | 0.921" in body
    assert "99.9" not in body                  # comment stripped
    assert "htbp" not in body and "#1" not in body


def test_markdown_bold_abstract_and_headings():
    md = "My Title\n\n**Abstract**\n\nWe study X with 300 firms.\n\n# Introduction\n\nText.\n\n## Background\n\nMore."
    ms = c.from_markdown(md)
    assert ms.abstract.startswith("We study X")
    assert [s.title for s in ms.sections if s.role != "abstract"][-2:] == ["Introduction", "Background"]
    assert ms.title == "My Title"


def test_plain_text_numbered_headings():
    text = "Title\n1. Introduction\nWe begin.\n2 Literature Review\nPrior work.\n2.1 Trust\nTrust is.\n3. Results\nIt works."
    ms = c.from_plain_text(text)
    got = [(s.title, s.level, s.role) for s in ms.sections]
    assert ("Trust", 2, "literature") in got
    assert ("Results", 1, "results") in got


def test_load_manuscript_rejects_unknown_type():
    with pytest.raises(ValueError):
        c.load_manuscript(b"hello", "paper.odt")


def test_cap_cuts_appendix_first(monkeypatch):
    monkeypatch.setattr(c, "MAX_INPUT_CHARS", 100)
    ms = c.Manuscript(sections=[c.Section("S1", "Intro", 1, "a" * 60, "introduction"),
                                c.Section("S2", "Appendix", 1, "b" * 60, "appendix"),
                                c.Section("S3", "Results", 1, "c" * 30, "results")])
    out = c._cap(ms)
    assert out.truncated
    assert [s.id for s in out.sections] == ["S1", "S2", "S3"]
    assert len(out.section("S2").text) == 10 and len(out.section("S3").text) == 30


# --- rules --------------------------------------------------------------------------------------------

def test_label_mentions_ranges_lists_ordinals():
    got = [l for l, _, _ in c.label_mentions("H1-H3 and Hypotheses 4 and 5; H100 GPUs; H2O; H0; pH7", "H")]
    assert sorted(set(got)) == ["H1", "H2", "H3", "H4", "H5"]
    # words glued together by PDF extraction
    glued = [l for l, _, _ in c.label_mentions("supportingH10. HypothesisH12was not tested; H5concerning; H1a.", "H")]
    assert glued == ["H10", "H12", "H5", "H1a"]
    rq = [l for l, _, _ in c.label_mentions("RQ1–RQ3, the second research question, RQ 4", "RQ")]
    assert sorted(set(rq)) == ["RQ1", "RQ2", "RQ3", "RQ4"]


def test_untested_hypothesis_and_unanswered_rq():
    findings = c.check_labels(_ms(), "H") + c.check_labels(_ms(), "RQ")
    keys = {f.key for f in findings}
    assert "hypothesis_untested:h3" in keys       # H3 never reported
    assert "hypothesis_untested:h1" not in keys
    assert "research_question_unanswered:rq2" in keys
    assert "research_question_unanswered:rq1" not in keys   # "the first research question" answers it
    f = next(f for f in findings if f.key == "hypothesis_untested:h3")
    assert "H3" in f.quotes[0]["text"] and len(f.quotes[0]["text"].split()) <= c.MAX_QUOTE_WORDS + 2


def test_undeclared_hypothesis_and_parent_child_labels():
    ms = c.Manuscript(sections=[
        c.Section("S1", "Theory", 1, "H1a: X raises Y. H1b: X raises Z.", "theory"),
        c.Section("S2", "Results", 1, "H1 is supported. H4 is also supported.", "results"),
    ])
    keys = {f.key for f in c.check_labels(ms, "H")}
    assert "hypothesis_untested:h1a" not in keys       # the parent H1 is reported
    assert "hypothesis_undeclared:h4" in keys
    assert "label_gap:h" in keys                       # H2, H3 missing


def test_labels_skipped_without_section_roles():
    ms = c.Manuscript(sections=[c.Section("S1", "Body", 1, "H1: X. H2: Y.", "other")])
    assert c.check_labels(ms, "H") == []


def test_acronym_conflict_but_not_plural_or_case():
    ms = c.Manuscript(sections=[
        c.Section("S1", "Intro", 1, "Large Language Models (LLMs, e.g., GPT) help. A large language model (LLM) "
                                    "is big.", "introduction"),
        c.Section("S2", "Method", 1, "We use Structural Equation Modeling (SEM). Later, search engine "
                                     "marketing (SEM) is measured.", "method"),
    ])
    found = {f.key for f in c.check_acronyms(ms)}
    assert found == {"acronym_conflict:sem"}


def test_acronym_british_and_us_spelling_are_one_expansion():
    ms = c.Manuscript(sections=[
        c.Section("S1", "Intro", 1, "We apply Structural Equation Modelling (SEM) to a survey.", "introduction"),
        c.Section("S2", "Method", 1, "We use partial least squares structural equation modeling (SEM).", "method"),
        c.Section("S3", "Method", 1, "The International Standards Organisation (ISO) and the International "
                                     "Standards Organization (ISO) agree.", "method"),
    ])
    assert c.check_acronyms(ms) == []


def test_hypotheses_heading_after_results_counts_as_results():
    ms = c.from_plain_text("1. Introduction\nWe study trust.\n2. Hypotheses\nH1: X raises Y.\n"
                           "3. Results\nThe model fits well.\n4. Hypotheses\nH1 supported (beta = 0.31).\n"
                           "5. Conclusion\nDone.")
    assert [s.role for s in ms.sections] == ["introduction", "theory", "results", "results", "conclusion"]
    assert c.check_labels(ms, "H") == []


def _pad(ms):
    # the abstract-number rule needs a body of some length to be meaningful
    ms.sections.append(c.Section("S99", "Appendix", 1, "filler words " * 200, "appendix"))
    return ms


def test_abstract_numbers():
    findings = c.check_abstract_numbers(_pad(_ms()))
    titles = " ".join(f.title for f in findings)
    assert "12.4%" in titles and "12.7%" in titles      # near miss reported with the body's value
    assert "92.1" not in titles                         # 92.1% appears as 0.921
    assert "412" not in titles


# --- Paper Bible and model stages -------------------------------------------------------------------

def test_accept_items_verifies_quotes_and_reassigns_section():
    ms = _ms()
    hyp = next(s for s in ms.sections if s.title == "Hypotheses")
    res = next(s for s in ms.sections if s.title == "Results")
    raw = [
        {"section": hyp.id, "kind": "hypothesis", "label": "H1", "text": "t",
         "quote": "H1: Transparency increases trust."},
        {"section": hyp.id, "kind": "hypothesis_result", "label": "H1", "text": "t",
         "quote": "H1 is supported: trust rose by 12.7%"},                      # wrong section, same chunk
        {"section": hyp.id, "kind": "hypothesis", "label": "H9", "text": "t",
         "quote": "H9: an invented hypothesis here"},
        {"section": hyp.id, "kind": "not_a_kind", "label": "x", "text": "t",
         "quote": "H1: Transparency increases trust."},
        "junk",
    ]
    kept, dropped = c.accept_items(raw, ms, [hyp.id, res.id])
    assert dropped == 3
    assert [k["section"] for k in kept] == [hyp.id, res.id]


def test_findings_from_model_uses_only_bible_quotes():
    items = [{"id": "B1", "section": "S2", "kind": "construct_definition", "label": "Trust", "text": "a",
              "quote": "trust is belief"},
             {"id": "B2", "section": "S5", "kind": "construct_definition", "label": "trust", "text": "b",
              "quote": "trust is behaviour"}]
    items.append({"id": "B3", "section": "S5", "kind": "claim", "label": "x", "text": "c", "quote": "Trust is behaviour."})
    raw = [{"type": "construct_definition_conflict", "item_ids": ["B1", "B2", "B3", "B77"], "title": "Trust two ways",
            "why": "w", "fix": "f", "confidence": "HIGH", "quotes": ["invented by the model"]},
           {"type": "made_up_type", "item_ids": ["B1"]},
           {"type": "term_drift", "item_ids": ["B99"]}]
    out = c.findings_from_model(raw, items)
    assert len(out) == 1
    f = out[0]
    assert [q["text"] for q in f.quotes] == ["trust is belief", "trust is behaviour"]
    assert f.confidence == "high" and f.sections == ["S2", "S5"]


def test_dedupe_drops_model_repeat_of_rule():
    rule = [c.Finding("hypothesis_untested", "t", [], [], "", "", key="hypothesis_untested:h3")]
    model = [c.Finding("hypothesis_untested", "t", [], [], "", "", source="model", key="hypothesis_untested:h3"),
             c.Finding("theory_unused", "t", [], [], "", "", source="model", key="theory_unused:tam")]
    assert [f.type for f in c.dedupe(rule, model)] == ["hypothesis_untested", "theory_unused"]


def _nth(listing: str, k: int) -> str:
    return next((b for b in listing.split("\n\n") if b.startswith(f"{k}. ")), "")


class _FakeModel:
    """Answers each stage by its system prompt and records every call."""

    def __init__(self, verify_reply=None):
        self.calls = []
        self.verify_reply = verify_reply

    async def __call__(self, client, *, system, user_content, max_tokens, model, on_truncated=None, effort=None):
        self.calls.append(system)
        text = user_content[0]["text"]
        if system is c.EXTRACT_SYSTEM:
            items = []
            if "H1: Transparency increases trust." in text:
                sid = text.split("H1: Transparency")[0].rsplit("[[", 1)[1].split(" |")[0]
                items.append({"section": sid, "kind": "theory", "label": "Signalling theory", "text": "lens",
                              "quote": "H1: Transparency increases trust."})
                items.append({"section": sid, "kind": "hypothesis", "label": "H2", "text": "t",
                              "quote": "a quote that is not in the paper at all"})
            return json.dumps(items)
        if system is c.CHECK_SYSTEM:
            return json.dumps([{"type": "theory_unused", "item_ids": ["B1"], "title": "Signalling theory unused",
                                "why": "w", "fix": "f", "confidence": "medium"}])
        if system is c.VERIFY_SYSTEM:
            if self.verify_reply is not None:
                return self.verify_reply
            listing = user_content[1]["text"]
            n = len(re.findall(r"(?m)^\d+\. \[", listing))
            # keep the model finding, drop every rule finding
            return json.dumps([{"n": k, "verdict": "keep" if "[theory_unused]" in _nth(listing, k) else "drop",
                                "confidence": "low", "note": "ok"} for k in range(1, n + 1)])
        raise AssertionError("unexpected prompt")


def test_full_run_with_fake_model():
    fake = _FakeModel()
    report = asyncio.run(c.run_coherence_check(_ms(), client=object(), message_fn=fake))
    assert report["bible"]["n_dropped_unquoted"] == 1
    assert [it["kind"] for it in report["bible"]["items"]] == ["theory"]
    assert [f["type"] for f in report["findings"]] == ["theory_unused"]
    assert report["findings"][0]["confidence"] == "low"
    assert report["dropped"] and all(f["source"] == "rule" for f in report["dropped"])
    assert report["status"]["verify"] == "ok"
    md = c.render_markdown(report)
    assert "H1: Transparency increases trust." in md and "### Paper Bible" in md


def test_unreadable_verifier_keeps_findings_marked():
    fake = _FakeModel(verify_reply="not json")
    report = asyncio.run(c.run_coherence_check(_ms(), client=object(), message_fn=fake))
    assert report["status"]["verify"] == "unparsed"
    assert report["findings"] and all("not verified" in f["verifier_note"] for f in report["findings"])


def test_rules_only_makes_no_model_call():
    fake = _FakeModel()
    report = asyncio.run(c.run_coherence_check(_ms(), use_model=False, message_fn=fake))
    assert fake.calls == [] and report["mode"] == "rules_only"
    assert "rule-based checks only" in c.render_markdown(report)


def test_report_copy_has_no_emoji_or_em_dash():
    fake = _FakeModel()
    md = c.render_markdown(asyncio.run(c.run_coherence_check(_ms(), client=object(), message_fn=fake)))
    assert "—" not in md
    assert not any(ord(ch) >= 0x1F300 for ch in md)


def test_flags_default_off(monkeypatch):
    monkeypatch.delenv("COHERENCE_CHECK_ENABLED", raising=False)
    monkeypatch.delenv("COHERENCE_IN_REVIEW", raising=False)
    assert not c.check_enabled() and not c.in_review_enabled()


# --- internal endpoint ------------------------------------------------------------------------------

@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    import app as backend_app
    monkeypatch.setattr(backend_app, "rate_dict", {})
    return TestClient(backend_app.web.local())


def _post(api, secret="s3cret", mode="rules"):
    return api.post("/paper-review/coherence/internal", headers={"x-webhook-secret": secret},
                    files={"file": ("paper.tex", LATEX.encode(), "text/plain")}, data={"mode": mode})


def test_endpoint_hidden_when_flag_off(api, monkeypatch):
    monkeypatch.delenv("COHERENCE_CHECK_ENABLED", raising=False)
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "s3cret")
    assert _post(api).status_code == 404


def test_endpoint_requires_secret(api, monkeypatch):
    monkeypatch.setenv("COHERENCE_CHECK_ENABLED", "1")
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "s3cret")
    assert _post(api, secret="wrong").status_code == 401


def test_endpoint_rules_mode(api, monkeypatch):
    monkeypatch.setenv("COHERENCE_CHECK_ENABLED", "1")
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "s3cret")
    r = _post(api)
    assert r.status_code == 200
    body = r.json()
    assert body["report"]["mode"] == "rules_only"
    assert any(f["key"] == "hypothesis_untested:h3" for f in body["report"]["findings"])
    assert r.headers["cache-control"] == "no-store"


def test_pipeline_mounts_coherence_flags_secret():
    # COHERENCE_IN_REVIEW reaches the paid pipeline only through this secret.
    import inspect
    import app as backend_app
    src = inspect.getsource(backend_app)
    block = src[src.index("def paper_review_pipeline(") - 400:src.index("def paper_review_pipeline(")]
    assert "coherence_flags_secret" in block


# --- voice, type correction, quote expansion, placement (2026-10-23) ------------------------------

def test_short_quote_expands_to_its_sentence_across_pdf_line_wraps():
    text = ("Attitude toward technical infrastructure also had a significant relationship\n"
            "with job satisfaction with a small effect size supporting H6. Sociotechnical\n"
            "infrastructure was not a significant predictor.")
    q = c.expand_quote("with a small effect size supporting", text)
    assert q.startswith("Attitude toward technical infrastructure") and q.endswith("supporting H6.")
    assert c.quote_in_text(q, text)
    assert c.expand_quote("not in this text at all", text) == "not in this text at all"


def test_voice_rules_reach_the_check_prompt():
    assert c.VOICE_RULES in c.CHECK_SYSTEM
    for rule in ("second person", "em-dashes", "However,", "never adjectives", '"but"'):
        assert rule in c.VOICE_RULES


def test_verifier_corrects_model_finding_type():
    f = c.Finding("sample_inconsistency", "H6 and H7 swap", ["S1"], [], "w", "f", source="model")
    rule = c.Finding("acronym_conflict", "SEM two ways", ["S1"], [], "w", "f", source="rule")

    async def fake(client, *, system, user_content, max_tokens, model, on_truncated=None, effort=None):
        return json.dumps([{"n": 1, "verdict": "keep", "type": "hypothesis_undeclared", "confidence": "high"},
                           {"n": 2, "verdict": "keep", "type": "term_drift", "confidence": "high"}])

    kept, dropped, status = asyncio.run(c.verify(object(), _ms(), [f, rule], message_fn=fake))
    assert [k.type for k in kept] == ["hypothesis_undeclared", "acronym_conflict"]   # rules keep their type


def test_rule_copy_has_no_banned_style():
    ms = _pad(_ms())
    text = " ".join(f.why + " " + f.fix + " " + f.title for f in c.rule_findings(ms))
    assert text
    for bad in ("—", ";", "moreover", "notably", "it is worth", "crucial"):
        assert bad not in text.lower()


def test_coherence_section_goes_after_data_to_claim():
    import app as backend_app
    md = "## What's Working\nA\n\n## Data-to-Claim Contradictions\nB\n\n## Equation Audit\nC\n\n## Panel Transcript\nD\n"
    out = backend_app._insert_coherence_section(md, "## Coherence Check\n\nX\n")
    assert out.index("## Data-to-Claim") < out.index("## Coherence Check") < out.index("## Equation Audit")
    md2 = "## What's Working\nA\n\n## Panel Transcript\nD\n"
    out2 = backend_app._insert_coherence_section(md2, "## Coherence Check\n\nX\n")
    assert out2.index("## Coherence Check") < out2.index("## Panel Transcript")
    assert backend_app._insert_coherence_section("## A\nx", "").startswith("## A")
    assert backend_app._insert_coherence_section("## A\nx", "## Coherence Check\n").rstrip().endswith("## Coherence Check")


def test_label_mismatch_is_a_known_type_in_both_prompts():
    assert "label_mismatch" in c.CHECK_TYPES and "label_mismatch" in c.TYPE_TITLES
    assert "label_mismatch" in c.CHECK_SYSTEM and "label_mismatch" in c.VERIFY_SYSTEM
