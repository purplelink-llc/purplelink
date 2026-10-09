"""Retraction detection for cited references (CrossRef carries Retraction
Watch data in `updated-by`). Hermetic: the CrossRef transport is mocked and
the DOI redirect walk is stubbed, so no network is used."""
import asyncio

import httpx
import pytest

from latextools import papercheck, preview
from latextools.papercheck import PaperReference


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# The pure detector
# ---------------------------------------------------------------------------

WAKEFIELD = {
    "title": ["RETRACTED: Ileal-lymphoid-nodular hyperplasia"],
    "updated-by": [
        {"DOI": "10.1016/s0140-6736(04)15715-2", "type": "correction", "source": "retraction-watch",
         "updated": {"date-parts": [[2004, 3, 6]]}},
        {"DOI": "10.1016/s0140-6736(10)60175-4", "type": "retraction", "source": "retraction-watch",
         "updated": {"date-parts": [[2010, 2, 6]]}},
    ],
}


def test_retraction_is_found_with_notice_and_date():
    r = papercheck.crossref_retraction(WAKEFIELD)
    assert r == {"kind": "retracted", "types": ["retraction"],
                 "notice_doi": "10.1016/s0140-6736(10)60175-4", "date": "2010-02-06"}


def test_correction_alone_is_not_a_retraction():
    msg = {"title": ["A paper"], "updated-by": [{"DOI": "10.1/c", "type": "correction"},
                                                {"DOI": "10.1/e", "type": "erratum"}]}
    assert papercheck.crossref_retraction(msg) is None


def test_expression_of_concern_and_partial_retraction_are_concerns():
    msg = {"updated-by": [{"DOI": "10.1/x", "type": "expression_of_concern",
                           "updated": {"date-parts": [[2021, 5]]}}]}
    r = papercheck.crossref_retraction(msg)
    assert r["kind"] == "concern" and r["date"] == "2021-05"
    msg = {"updated-by": [{"DOI": "10.1/y", "type": "partial_retraction"}]}
    assert papercheck.crossref_retraction(msg)["kind"] == "concern"


def test_a_retraction_wins_over_a_concern():
    msg = {"updated-by": [{"DOI": "10.1/a", "type": "expression_of_concern"},
                          {"DOI": "10.1/b", "type": "withdrawal"}]}
    r = papercheck.crossref_retraction(msg)
    assert r["kind"] == "retracted" and r["notice_doi"] == "10.1/b"
    assert r["types"] == ["expression_of_concern", "withdrawal"]


def test_publisher_title_flag_counts_when_crossref_lists_no_update():
    assert papercheck.crossref_retraction({"title": ["RETRACTED: Some result"]})["types"] == ["title_flag"]
    assert papercheck.crossref_retraction({"title": ["Withdrawn - Some result"]})["kind"] == "retracted"


def test_a_paper_about_retraction_is_not_flagged():
    assert papercheck.crossref_retraction({"title": ["Retraction notices in medical journals"]}) is None
    assert papercheck.crossref_retraction({"title": ["Withdrawn consent in clinical trials"]}) is None


@pytest.mark.parametrize("bad", [None, [], "x", {"updated-by": "retraction"}, {"updated-by": [None, 3]},
                                 {"updated-by": [{"type": None}]}, {"title": None}, {"title": [5]}])
def test_malformed_records_never_raise(bad):
    assert papercheck.crossref_retraction(bad) is None


def test_hostile_dates_are_dropped():
    msg = {"updated-by": [{"DOI": "10.1/z", "type": "retraction", "updated": {"date-parts": [["<script>"]]}}]}
    assert papercheck.crossref_retraction(msg)["date"] == ""
    msg = {"updated-by": [{"DOI": "10.1/z", "type": "retraction", "updated": {"date-parts": [[99999]]}}]}
    assert papercheck.crossref_retraction(msg)["date"] == ""


# ---------------------------------------------------------------------------
# Paid pipeline: layer 2
# ---------------------------------------------------------------------------

def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ok_head(monkeypatch):
    async def _head(client, doi):
        return httpx.Response(200)
    monkeypatch.setattr(papercheck, "_resolve_doi_redirects_safely", _head)


def test_layer2_collects_retracted_references_and_still_counts_them_verified(monkeypatch):
    _ok_head(monkeypatch)
    seen = []

    def handler(request):
        seen.append(request.url.host)
        assert request.url.host == "api.crossref.org"
        if request.url.path.endswith("10.1016/retracted"):
            return httpx.Response(200, json={"message": WAKEFIELD})
        return httpx.Response(200, json={"message": {"title": ["Fine"]}})

    refs = [PaperReference(raw="Wakefield 1998. doi:10.1016/retracted", doi="10.1016/retracted"),
            PaperReference(raw="Fine 2020. doi:10.1000/fine", doi="10.1000/fine")]

    async def go():
        async with _client(handler) as c:
            return await papercheck.run_layer_2_citations(c, refs)

    l2 = _run(go())
    assert l2["checked"] == 2 and l2["verified"] == 2 and l2["issues"] == []
    assert len(l2["retractions"]) == 1
    r = l2["retractions"][0]
    assert r["doi"] == "10.1016/retracted" and r["kind"] == "retracted" and "Wakefield" in r["raw"]
    assert set(seen) == {"api.crossref.org"}


def test_layer2_survives_crossref_failures(monkeypatch):
    _ok_head(monkeypatch)

    def handler(request):
        return httpx.Response(503)

    refs = [PaperReference(raw="X 2020. doi:10.1/x", doi="10.1/x")]

    async def go():
        async with _client(handler) as c:
            return await papercheck.run_layer_2_citations(c, refs)

    l2 = _run(go())
    assert l2["verified"] == 1 and l2["retractions"] == []


def test_layer2_without_references_has_an_empty_retractions_list():
    l2 = _run(papercheck.run_layer_2_citations(None, []))
    assert l2 == {"checked": 0, "verified": 0, "issues": [], "retractions": []}


def test_title_search_match_carries_the_retraction():
    def handler(request):
        return httpx.Response(200, json={"message": {"items": [{
            "title": ["Ileal lymphoid nodular hyperplasia"], "DOI": "10.1016/s0140-6736(97)11096-0",
            "updated-by": WAKEFIELD["updated-by"]}]}})

    ref = PaperReference(raw="Wakefield. Ileal lymphoid nodular hyperplasia. Lancet.",
                         title="Ileal lymphoid nodular hyperplasia")

    async def go():
        async with _client(handler) as c:
            return await papercheck._crossref_lookup(c, ref)

    res = _run(go())
    assert res["status"] == "matched" and res["retraction"]["kind"] == "retracted"


def test_title_search_weak_match_is_not_flagged():
    def handler(request):
        return httpx.Response(200, json={"message": {"items": [{
            "title": ["Something else entirely about birds"], "DOI": "10.1/b",
            "updated-by": WAKEFIELD["updated-by"]}]}})

    ref = PaperReference(raw="X. Ileal lymphoid nodular hyperplasia.", title="Ileal lymphoid nodular hyperplasia")

    async def go():
        async with _client(handler) as c:
            return await papercheck._crossref_lookup(c, ref)

    res = _run(go())
    assert res["status"] == "weak_match" and "retraction" not in res


def test_retraction_findings_feed_the_report_as_errors_and_warnings():
    l2 = {"retractions": [
        {"raw": "Wakefield 1998", "doi": "10.1/r", "kind": "retracted", "notice_doi": "10.1/n", "date": "2010-02-06"},
        {"raw": "Smith 2019", "doi": "10.1/c", "kind": "concern", "notice_doi": "", "date": ""},
    ]}
    f = papercheck.retraction_findings(l2)
    assert [x["severity"] for x in f] == ["error", "warning"]
    assert "retracted" in f[0]["summary"] and "2010-02-06" in f[0]["detail"] and "10.1/n" in f[0]["detail"]
    assert "expression of concern" in f[1]["summary"]
    assert papercheck.retraction_findings({}) == []


# ---------------------------------------------------------------------------
# Free preview
# ---------------------------------------------------------------------------

def test_preview_reports_a_retracted_reference_first_and_counts_it():
    def handler(request):
        host = request.url.host
        assert host == "api.crossref.org", f"unexpected host {host}"
        if request.url.path.endswith("10.1016/retracted"):
            return httpx.Response(200, json={"message": {
                "title": ["Ileal-lymphoid-nodular hyperplasia"], "updated-by": WAKEFIELD["updated-by"]}})
        return httpx.Response(200, json={"message": {"title": ["A real paper about gravity waves"]}})

    refs = [
        PaperReference(raw="Wakefield, A. (1998). Ileal-lymphoid-nodular hyperplasia. Lancet. doi:10.1016/retracted",
                       title="Ileal-lymphoid-nodular hyperplasia", doi="10.1016/retracted"),
        PaperReference(raw="Doe, J. (2019). A real paper about gravity waves. Physics Letters. doi:10.1000/real",
                       title="A real paper about gravity waves", doi="10.1000/real"),
    ]

    async def go():
        async with _client(handler) as c:
            return await preview.check_references(c, refs)

    results = _run(go())

    class _S:
        n_references_total = 2
        page_count = 2

    body = preview.build_response(_S(), results, [])
    assert body["counts"]["retracted"] == 1 and body["counts"]["verified"] == 2
    first = body["findings"][0]
    assert first["type"] == "retracted" and first["label"] == "Cites a retracted paper"
    assert "Wakefield" in first["quote"] and "2010-02-06" in first["detail"]


def test_preview_does_not_flag_a_retraction_when_the_doi_names_another_paper():
    def handler(request):
        return httpx.Response(200, json={"message": {
            "title": ["Zebra migration patterns across seasonal savanna corridors"],
            "updated-by": WAKEFIELD["updated-by"]}})

    refs = [PaperReference(raw="Roe, R. (2018). Deep learning for protein folding. Nature Methods. doi:10.1000/wrong",
                           title="Deep learning for protein folding", doi="10.1000/wrong")]

    async def go():
        async with _client(handler) as c:
            return await preview.check_references(c, refs)

    res = _run(go())[0]
    assert res["status"] == "doi_mismatch" and "retraction" not in res
