import asyncio
import json
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from latextools import paperreview_extras as pre
from latextools.papercheck import PaperReference, PaperStructure


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeClient:
    """Returns queued responses keyed by URL substring."""
    def __init__(self, routes):
        self.routes = routes          # list of (url_substr, _FakeResp)

    async def get(self, url, **kwargs):
        for sub, resp in self.routes:
            if sub in url:
                return resp
        return _FakeResp(404, {})


# ---------------------------------------------------------------------------
# _verify_gap_candidate — live CrossRef grounding for citation-gap suggestions
# ---------------------------------------------------------------------------

def test_verify_gap_candidate_unknown_title_is_not_searched():
    gap = {"candidate_title_hint": "unknown", "gap_type": "qualitative_gap"}
    client = _FakeClient([])
    out = asyncio.run(pre._verify_gap_candidate(client, gap))
    assert out["verification"]["status"] == "not_searched"
    # network never hit — no route needed to satisfy this


def test_verify_gap_candidate_confirmed_exists():
    gap = {"candidate_title_hint": "Attention Is All You Need"}
    client = _FakeClient([
        ("api.crossref.org", _FakeResp(200, {
            "message": {
                "items": [{
                    "title": ["Attention Is All You Need"],
                    "DOI": "10.1234/abc",
                }]
            }
        })),
    ])
    out = asyncio.run(pre._verify_gap_candidate(client, gap))
    v = out["verification"]
    assert v["status"] == "confirmed_exists"
    assert v["found_doi"] == "10.1234/abc"


def test_verify_gap_candidate_not_found():
    gap = {"candidate_title_hint": "A Totally Fabricated Paper Title Xyz"}
    client = _FakeClient([
        ("api.crossref.org", _FakeResp(200, {"message": {"items": []}})),
    ])
    out = asyncio.run(pre._verify_gap_candidate(client, gap))
    assert out["verification"]["status"] == "not_found"


def test_verify_gap_candidate_weak_match():
    gap = {"candidate_title_hint": "Deep Learning for Widget Detection"}
    client = _FakeClient([
        ("api.crossref.org", _FakeResp(200, {
            "message": {
                "items": [{"title": ["Something Completely Unrelated"], "DOI": "10.9/z"}]
            }
        })),
    ])
    out = asyncio.run(pre._verify_gap_candidate(client, gap))
    assert out["verification"]["status"] == "weak_match"


def test_verify_gap_candidate_network_error_does_not_raise():
    gap = {"candidate_title_hint": "Some Paper"}

    class _BoomClient:
        async def get(self, *a, **k):
            raise RuntimeError("network down")

    out = asyncio.run(pre._verify_gap_candidate(_BoomClient(), gap))
    assert out["verification"]["status"] == "network_error"


def test_verify_gap_candidate_crossref_unavailable():
    gap = {"candidate_title_hint": "Some Paper"}
    client = _FakeClient([("api.crossref.org", _FakeResp(503, {}))])
    out = asyncio.run(pre._verify_gap_candidate(gap=gap, client=client))
    assert out["verification"]["status"] == "crossref_unavailable"


# ---------------------------------------------------------------------------
# run_citation_gap — orchestration: LLM findings get annotated with live
# verification before being returned.
# ---------------------------------------------------------------------------

def test_run_citation_gap_annotates_each_gap_with_verification(monkeypatch):
    llm_gaps = [
        {
            "gap_type": "missing_canonical_paper",
            "topic": "transformers",
            "expected_work_description": "the original transformer paper",
            "candidate_authors": ["Vaswani"],
            "candidate_title_hint": "Attention Is All You Need",
            "why_it_matters": "foundational",
            "where_in_paper": "related work",
        },
        {
            "gap_type": "qualitative_gap",
            "topic": "some niche subarea",
            "expected_work_description": "prior work on X",
            "candidate_authors": [],
            "candidate_title_hint": "unknown",
            "why_it_matters": "reviewers expect coverage",
            "where_in_paper": "intro",
        },
    ]

    async def _fake_anthropic_message(*a, **k):
        return json.dumps(llm_gaps)

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    client = _FakeClient([
        ("api.crossref.org", _FakeResp(200, {
            "message": {
                "items": [{"title": ["Attention Is All You Need"], "DOI": "10.1/xyz"}]
            }
        })),
    ])

    struct = PaperStructure(title="T", abstract="A", body="B", references=[])
    result = asyncio.run(pre.run_citation_gap(client, struct))

    assert result["status"] == "ok"
    assert result["n_gaps"] == 2
    assert result["n_confirmed"] == 1

    verified_gap = result["gaps"][0]
    assert verified_gap["verification"]["status"] == "confirmed_exists"
    assert verified_gap["verification"]["found_doi"] == "10.1/xyz"

    unknown_gap = result["gaps"][1]
    assert unknown_gap["verification"]["status"] == "not_searched"


def test_run_citation_gap_empty_llm_output_short_circuits(monkeypatch):
    async def _fake_anthropic_message(*a, **k):
        return "[]"

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    called = {"n": 0}

    class _CountingClient:
        async def get(self, *a, **k):
            called["n"] += 1
            return _FakeResp(200, {"message": {"items": []}})

    struct = PaperStructure(title="T", abstract="A", body="B", references=[])
    result = asyncio.run(pre.run_citation_gap(_CountingClient(), struct))

    assert result == {
        "status": "ok",
        "gaps": [],
        "n_gaps": 0,
        "n_confirmed": 0,
        "n_references_reviewed": 0,
        "n_references_total": 0,
        "references_truncated": False,
        "no_references_extracted": True,
    }
    assert called["n"] == 0   # no gaps -> no CrossRef calls at all


def test_run_citation_gap_llm_failure_still_returns_error_shape(monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("anthropic down")

    monkeypatch.setattr(pre, "_anthropic_message", _boom)

    struct = PaperStructure(title="T", abstract="A", body="B", references=[])
    result = asyncio.run(pre.run_citation_gap(_FakeClient([]), struct))
    assert result == {"status": "error", "gaps": []}


# ---------------------------------------------------------------------------
# run_citation_gap — truncated bibliographies (structure.references is
# already capped at MAX_REFERENCES_TO_REVIEW by extract_paper()) must surface
# their true, pre-truncation reference count so the LLM prompt and the
# customer-facing result both reflect that only a partial list was reviewed.
# ---------------------------------------------------------------------------

def test_run_citation_gap_flags_truncated_reference_list(monkeypatch):
    captured_prompt = {}

    async def _fake_anthropic_message(*a, **k):
        # user_content is passed as a kwarg list of {"type": "text", "text": ...}
        captured_prompt["text"] = k["user_content"][0]["text"]
        return "[]"

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    # 60 parsed references (the MAX_REFERENCES_TO_REVIEW cap) but 150 total
    # in the manuscript's actual bibliography.
    refs = [PaperReference(raw=f"Ref {i}") for i in range(60)]
    struct = PaperStructure(
        title="T", abstract="A", body="B",
        references=refs, n_references_total=150,
    )

    result = asyncio.run(pre.run_citation_gap(_FakeClient([]), struct))

    assert result["n_references_reviewed"] == 60
    assert result["n_references_total"] == 150
    assert result["references_truncated"] is True
    # The LLM must be told the list is incomplete, not just handed 60 refs
    # silently.
    assert "150" in captured_prompt["text"]
    assert "INCOMPLETE" in captured_prompt["text"]


def test_run_citation_gap_not_truncated_when_all_refs_captured(monkeypatch):
    async def _fake_anthropic_message(*a, **k):
        return "[]"

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    refs = [PaperReference(raw="Ref 1"), PaperReference(raw="Ref 2")]
    struct = PaperStructure(
        title="T", abstract="A", body="B",
        references=refs, n_references_total=2,
    )

    result = asyncio.run(pre.run_citation_gap(_FakeClient([]), struct))

    assert result["n_references_reviewed"] == 2
    assert result["n_references_total"] == 2
    assert result["references_truncated"] is False
    assert result["no_references_extracted"] is False


# ---------------------------------------------------------------------------
# run_citation_gap — zero extracted references must be distinguishable from
# a well-cited paper with no gaps. Both produce gaps == [], but only the
# former should set no_references_extracted so the caller can render a
# distinct "we found nothing to check against" message instead of the
# reassuring "no obvious citation gaps detected" one.
# ---------------------------------------------------------------------------

def test_run_citation_gap_flags_zero_references_extracted(monkeypatch):
    async def _fake_anthropic_message(*a, **k):
        return "[]"

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    struct = PaperStructure(title="T", abstract="A", body="B", references=[], n_references_total=0)
    result = asyncio.run(pre.run_citation_gap(_FakeClient([]), struct))

    assert result["n_references_total"] == 0
    assert result["no_references_extracted"] is True


def test_run_citation_gap_well_cited_paper_not_flagged(monkeypatch):
    async def _fake_anthropic_message(*a, **k):
        return "[]"

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    refs = [PaperReference(raw="Ref 1")]
    struct = PaperStructure(
        title="T", abstract="A", body="B",
        references=refs, n_references_total=1,
    )
    result = asyncio.run(pre.run_citation_gap(_FakeClient([]), struct))

    assert result["n_references_total"] == 1
    assert result["no_references_extracted"] is False


# ---------------------------------------------------------------------------
# run_revision_review — must never bill/present a fabricated "ok" report when
# the pasted original review is unrelated to the uploaded manuscript or has
# no Rectification Checklist to track against.
# ---------------------------------------------------------------------------

def test_run_revision_review_missing_checklist_short_circuits_without_llm_call(monkeypatch):
    called = {"n": 0}

    async def _fake_anthropic_message(*a, **k):
        called["n"] += 1
        return "# Revision Review\n"

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    struct = PaperStructure(title="T", abstract="A", body="B", references=[])
    garbage_review = "This is just some random text pasted by the user, no structure at all."
    result = asyncio.run(pre.run_revision_review(_FakeClient([]), struct, garbage_review))

    assert result["status"] == "mismatch"
    assert result["markdown"] == ""
    assert "Rectification Checklist" in result["error"]
    assert called["n"] == 0   # never spent the LLM call on an unusable input


def test_run_revision_review_model_detects_unrelated_manuscript(monkeypatch):
    original_review_md = (
        "## Rectification Checklist\n"
        "1. [A1] Fix the stats in Table 2.\n"
    )

    async def _fake_anthropic_message(*a, **k):
        return (
            "# Revision Review\n\n"
            "## Mismatch Warning\n"
            "MISMATCH_DETECTED: original review discusses a materials-science "
            "paper on battery electrolytes, but the uploaded manuscript is "
            "about transformer language models.\n"
        )

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    struct = PaperStructure(title="Attention Is All You Need", abstract="A", body="B", references=[])
    result = asyncio.run(pre.run_revision_review(_FakeClient([]), struct, original_review_md))

    assert result["status"] == "mismatch"
    assert result["markdown"] == ""
    assert "battery electrolytes" in result["error"]


def test_run_revision_review_happy_path_returns_ok(monkeypatch):
    original_review_md = (
        "## Rectification Checklist\n"
        "1. [A1] Fix the stats in Table 2.\n"
    )
    report_md = (
        "# Revision Review\n\n"
        "## Summary\n- ready-for-resubmission\n\n"
        "## Address Tracker\n- **[A1] addressed:** stats corrected\n\n"
        "## New Issues Introduced\n(none)\n"
    )

    async def _fake_anthropic_message(*a, **k):
        return report_md

    monkeypatch.setattr(pre, "_anthropic_message", _fake_anthropic_message)

    struct = PaperStructure(title="T", abstract="A", body="B", references=[])
    result = asyncio.run(pre.run_revision_review(_FakeClient([]), struct, original_review_md))

    assert result["status"] == "ok"
    assert result["markdown"] == report_md.strip()


def test_run_revision_review_llm_failure_still_returns_error_shape(monkeypatch):
    original_review_md = "## Rectification Checklist\n1. [A1] Fix the stats.\n"

    async def _boom(*a, **k):
        raise RuntimeError("anthropic down")

    monkeypatch.setattr(pre, "_anthropic_message", _boom)

    struct = PaperStructure(title="T", abstract="A", body="B", references=[])
    result = asyncio.run(pre.run_revision_review(_FakeClient([]), struct, original_review_md))
    assert result == {"status": "error", "markdown": ""}
