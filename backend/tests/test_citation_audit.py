import asyncio
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from latextools import citation_audit as ca
from latextools.papercheck import PaperStructure, PaperReference


def test_extract_numeric_claim_citations():
    body = (
        "Transformers improve translation quality [12]. "
        "The sky is blue. "
        "Our method outperforms all baselines [3, 4]."
    )
    struct = PaperStructure(body=body)
    claims = ca.extract_claim_citations(struct)
    # Two sentences carry citations; the middle one has none.
    assert len(claims) == 2
    first = claims[0]
    assert "Transformers improve" in first.claim_sentence
    assert first.ref_keys == ["12"]
    second = claims[1]
    assert second.ref_keys == ["3", "4"]


def test_extract_author_year_and_numeric_range():
    body = (
        "Prior work established this effect (Smith et al., 2021). "
        "Replications confirmed it [5-7]."
    )
    struct = PaperStructure(body=body)
    claims = ca.extract_claim_citations(struct)
    assert claims[0].ref_keys == ["Smith et al., 2021"]
    assert claims[1].ref_keys == ["5", "6", "7"]


def test_extract_author_year_lowercase_prefix_surnames():
    body = (
        "This was first shown by (van der Berg et al., 2021). "
        "It was later refined (de Bruijn and Smith, 2018)."
    )
    struct = PaperStructure(body=body)
    claims = ca.extract_claim_citations(struct)
    assert claims[0].ref_keys == ["van der Berg et al., 2021"]
    assert claims[1].ref_keys == ["de Bruijn and Smith, 2018"]


def test_rank_claims_prioritizes_load_bearing():
    weak = ca.ClaimCitation("Related work also touches this area [1].", ["1"])
    strong = ca.ClaimCitation(
        "Our method significantly outperforms all baselines by 12% [2].", ["2"]
    )
    ranked = ca.rank_claims([weak, strong])
    assert ranked[0] is strong          # causal verb + number rank first
    assert ranked[1] is weak
    assert ranked[0].salience > ranked[1].salience


def test_rank_claims_is_stable_for_ties():
    a = ca.ClaimCitation("A plain mention [1].", ["1"])
    b = ca.ClaimCitation("Another plain mention [2].", ["2"])
    ranked = ca.rank_claims([a, b])
    assert ranked[0] is a and ranked[1] is b   # equal salience keeps input order


def test_reconstruct_abstract_from_inverted_index():
    inv = {"The": [0], "cat": [1], "sat": [2]}
    assert ca.reconstruct_abstract(inv) == "The cat sat"
    assert ca.reconstruct_abstract(None) is None
    assert ca.reconstruct_abstract({}) is None


def test_resolve_ref_numeric_and_author_year():
    refs = [
        PaperReference(raw="[1] Smith J. 2021. Deep nets. doi:10.1/x", title="Deep nets",
                       doi="10.1/x", year="2021", authors="Smith J."),
        PaperReference(raw="[2] Jones A. 2019. Shallow nets.", title="Shallow nets",
                       year="2019", authors="Jones A."),
    ]
    # Numeric key indexes 1-based into the reference list.
    assert ca._resolve_ref("2", refs) is refs[1]
    # Author-year key matches on surname + year in the raw text.
    assert ca._resolve_ref("Smith, 2021", refs) is refs[0]
    # Unknown key -> None.
    assert ca._resolve_ref("Nobody, 1900", refs) is None


def test_resolve_ref_lowercase_prefix_surname():
    refs = [
        PaperReference(raw="[1] van der Berg M. 2021. Graph nets.", title="Graph nets",
                       year="2021", authors="van der Berg M."),
    ]
    # The captured surname ("Berg") + year must resolve past the particles.
    assert ca._resolve_ref("van der Berg et al., 2021", refs) is refs[0]


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


def test_fetch_source_abstract_openalex_hit():
    ref = PaperReference(raw="x", title="Deep nets", doi="10.1/x")
    client = _FakeClient([
        ("openalex.org", _FakeResp(200, {
            "abstract_inverted_index": {"Deep": [0], "nets": [1]},
            "title": "Deep nets",
        })),
    ])
    out = asyncio.run(
        ca.fetch_source_abstract(client, "1", ref)
    )
    assert out.status == "ok"
    assert out.source == "openalex"
    assert out.text == "Deep nets"


def test_fetch_source_abstract_all_miss_is_unavailable():
    ref = PaperReference(raw="x", title="Ghost paper")
    client = _FakeClient([])        # every route 404 / empty
    out = asyncio.run(
        ca.fetch_source_abstract(client, "1", ref)
    )
    assert out.status == "unavailable"
    assert out.text is None


def test_fetch_source_abstract_all_three_http_miss():
    # DOI present so every fetcher reaches the network; all routes 404. This
    # exercises the Semantic Scholar + CrossRef HTTP-failure fallback paths.
    ref = PaperReference(raw="x", title="Ghost paper", doi="10.9/missing")
    client = _FakeClient([])        # every route -> _FakeResp(404)
    out = asyncio.run(
        ca.fetch_source_abstract(client, "7", ref)
    )
    assert out.status == "unavailable"
    assert out.text is None
    assert out.ref_key == "7"


def test_assess_claims_short_circuits_unavailable(monkeypatch):
    # When the abstract is unavailable, no LLM call happens and the verdict
    # is "Source unavailable".
    async def _boom(*a, **k):
        raise AssertionError("LLM must not be called for unavailable sources")
    monkeypatch.setattr(ca, "_anthropic_message", _boom)

    claim = ca.ClaimCitation("A claim [1].", ["1"])
    src = ca.SourceAbstract(ref_key="1", text=None, status="unavailable")
    findings = asyncio.run(
        ca.assess_claims(object(), [(claim, src)])
    )
    assert len(findings) == 1
    assert findings[0].verdict == "Source unavailable"
    assert findings[0].source_quote is None


def test_assess_claims_parses_llm_verdicts(monkeypatch):
    async def _fake_llm(client, system, user_content, max_tokens, **k):
        return (
            '[{"index": 0, "verdict": "Supported", '
            '"source_quote": "We show X improves Y.", '
            '"rationale": "Abstract states the same result."}]'
        )
    monkeypatch.setattr(ca, "_anthropic_message", _fake_llm)

    claim = ca.ClaimCitation("X improves Y [1].", ["1"])
    src = ca.SourceAbstract(ref_key="1", text="We show X improves Y.", status="ok")
    findings = asyncio.run(
        ca.assess_claims(object(), [(claim, src)])
    )
    assert findings[0].verdict == "Supported"
    assert findings[0].source_quote == "We show X improves Y."


def test_assess_claims_clamps_unknown_verdict(monkeypatch):
    async def _fake_llm(client, system, user_content, max_tokens, **k):
        return '[{"index": 0, "verdict": "Totally Made Up", "rationale": "x"}]'
    monkeypatch.setattr(ca, "_anthropic_message", _fake_llm)
    claim = ca.ClaimCitation("X [1].", ["1"])
    src = ca.SourceAbstract(ref_key="1", text="abstract", status="ok")
    findings = asyncio.run(
        ca.assess_claims(object(), [(claim, src)])
    )
    # Unknown verdicts clamp to the conservative "Not supported by abstract".
    assert findings[0].verdict == "Not supported by abstract"


def test_run_citation_audit_end_to_end(monkeypatch):
    refs = [
        PaperReference(raw="[1] Smith 2021 Deep nets", title="Deep nets", doi="10.1/x"),
        PaperReference(raw="[2] Jones 2019 Shallow nets", title="Shallow nets"),
    ]
    body = (
        "Our method significantly outperforms baselines [1]. "
        "Related work mentions this [2]."
    )
    struct = PaperStructure(body=body, references=refs)

    async def _fake_fetch(client, ref_key, ref):
        if ref_key == "1":
            return ca.SourceAbstract(ref_key="1", text="We show big gains.", status="ok")
        return ca.SourceAbstract(ref_key="2", text=None, status="unavailable")
    monkeypatch.setattr(ca, "fetch_source_abstract", _fake_fetch)

    async def _fake_assess(client, pairs):
        out = []
        for claim, src in pairs:
            if src.status == "ok":
                out.append(ca.AuditFinding(claim.claim_sentence, src.ref_key,
                                           "Supported", "We show big gains.", "ok"))
            else:
                out.append(ca.AuditFinding(claim.claim_sentence, src.ref_key,
                                           "Source unavailable"))
        return out
    monkeypatch.setattr(ca, "assess_claims", _fake_assess)

    audit = asyncio.run(ca.run_citation_audit(object(), struct))
    assert audit["audited"] == 2
    assert audit["skipped"] == 0
    assert audit["by_verdict"]["Supported"] == 1
    assert audit["by_verdict"]["Source unavailable"] == 1
    # The load-bearing claim is audited first.
    assert "outperforms" in audit["findings"][0]["claim_sentence"]


def test_run_citation_audit_caps_and_reports_skipped(monkeypatch):
    refs = [PaperReference(raw=f"[{i}] ref", title=f"t{i}") for i in range(1, 60)]
    body = " ".join(f"Claim number {i} shows an effect [{i}]." for i in range(1, 60))
    struct = PaperStructure(body=body, references=refs)

    async def _fake_fetch(client, ref_key, ref):
        return ca.SourceAbstract(ref_key=ref_key, text="abstract", status="ok")
    async def _fake_assess(client, pairs):
        return [ca.AuditFinding(c.claim_sentence, s.ref_key, "Supported") for c, s in pairs]
    monkeypatch.setattr(ca, "fetch_source_abstract", _fake_fetch)
    monkeypatch.setattr(ca, "assess_claims", _fake_assess)

    audit = asyncio.run(ca.run_citation_audit(object(), struct))
    assert audit["audited"] == ca.MAX_AUDIT_PAIRS
    assert audit["skipped"] == 59 - ca.MAX_AUDIT_PAIRS


def test_layer2_audit_key_is_attached():
    # Prove the orchestrator attaches audit onto the l2 dict additively.
    from latextools import papercheck

    base_l2 = {"checked": 2, "verified": 2, "issues": []}
    audit = {"audited": 1, "skipped": 0,
             "by_verdict": {v: 0 for v in ca.VERDICTS}, "findings": []}
    merged = papercheck.attach_audit(dict(base_l2), audit)
    assert merged["checked"] == 2          # existing keys preserved
    assert merged["audit"]["audited"] == 1
