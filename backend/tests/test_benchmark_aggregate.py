# backend/tests/test_benchmark_aggregate.py
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from benchmark.aggregate import PaperResult, summarize


def _gap(gap_type="missing_baseline", verification_status="confirmed_exists"):
    return {"gap_type": gap_type, "verification": {"status": verification_status}}


def test_summarize_empty_results():
    s = summarize([])
    assert s.n_papers_attempted == 0
    assert s.n_papers_ok == 0
    assert s.pct_with_confirmed_gap == 0.0
    assert s.median_gaps_per_paper == 0.0


def test_summarize_excludes_failed_papers_from_denominator():
    results = [
        PaperResult("1", "t1", status="ok", gaps=[_gap()]),
        PaperResult("2", "t2", status="error"),
        PaperResult("3", "t3", status="extraction_failed"),
    ]
    s = summarize(results)
    assert s.n_papers_attempted == 3
    assert s.n_papers_ok == 1
    assert s.n_papers_with_confirmed_gap == 1
    assert s.pct_with_confirmed_gap == 100.0


def test_summarize_only_counts_confirmed_exists_for_headline_pct():
    results = [
        PaperResult("1", "t1", status="ok", gaps=[_gap(verification_status="not_found")]),
        PaperResult("2", "t2", status="ok", gaps=[_gap(verification_status="weak_match")]),
        PaperResult("3", "t3", status="ok", gaps=[_gap(verification_status="confirmed_exists")]),
    ]
    s = summarize(results)
    assert s.n_papers_ok == 3
    assert s.n_papers_with_confirmed_gap == 1
    assert s.pct_with_confirmed_gap == round(1 / 3 * 100, 1)


def test_summarize_paper_with_zero_gaps_is_not_confirmed():
    results = [PaperResult("1", "t1", status="ok", gaps=[])]
    s = summarize(results)
    assert s.n_papers_with_confirmed_gap == 0
    assert s.median_gaps_per_paper == 0.0


def test_summarize_median_gaps_per_paper():
    results = [
        PaperResult("1", "t1", status="ok", gaps=[_gap(), _gap()]),
        PaperResult("2", "t2", status="ok", gaps=[_gap()]),
        PaperResult("3", "t3", status="ok", gaps=[_gap(), _gap(), _gap(), _gap()]),
    ]
    s = summarize(results)
    assert s.median_gaps_per_paper == 2.0


def test_summarize_gap_type_and_verification_breakdowns():
    results = [
        PaperResult("1", "t1", status="ok", gaps=[
            _gap(gap_type="missing_baseline", verification_status="confirmed_exists"),
            _gap(gap_type="missing_baseline", verification_status="not_found"),
            _gap(gap_type="qualitative_gap", verification_status="not_searched"),
        ]),
    ]
    s = summarize(results)
    assert s.gap_type_counts == {"missing_baseline": 2, "qualitative_gap": 1}
    assert s.verification_status_counts == {
        "confirmed_exists": 1, "not_found": 1, "not_searched": 1,
    }


def _checked(verification_status="confirmed_exists", cited=False, title="T", doi="10.1/x"):
    return {
        "gap_type": "missing_baseline",
        "candidate_title_hint": title,
        "verification": {"status": verification_status, "found_title": title, "found_doi": doi},
        "already_cited": {"cited": cited},
    }


def test_summarize_headline_excludes_already_cited_gaps():
    results = [
        PaperResult("1", "t1", status="ok", gaps=[_checked(cited=True)]),
        PaperResult("2", "t2", status="ok", gaps=[_checked(cited=True), _checked(cited=False)]),
        PaperResult("3", "t3", status="ok", gaps=[_checked(verification_status="weak_match")]),
        PaperResult("4", "t4", status="ok", gaps=[_gap()]),  # never checked
    ]
    s = summarize(results)
    assert s.n_papers_with_confirmed_gap == 3
    assert s.pct_with_confirmed_gap == 75.0
    assert s.n_papers_with_uncited_gap == 1
    assert s.pct_with_uncited_gap == 25.0
    assert s.n_confirmed_gaps == 4
    assert s.n_strict_gaps == 3  # paper 4 has no title hint
    assert s.n_confirmed_gaps_already_cited == 2
    assert s.n_counted_gaps == 1


def test_csv_rows_list_only_counted_gaps():
    from benchmark.aggregate import CSV_FIELDS, csv_rows
    results = [
        PaperResult("2611.00001", "t1", status="ok", gaps=[
            _checked(cited=False, title="Missing A", doi="10.1/a"),
            _checked(cited=True, title="Cited B", doi="10.1/b"),
            _checked(cited=False, title="Missing C", doi="10.1/c"),
        ]),
        PaperResult("2611.00002", "t2", status="error"),
    ]
    rows = csv_rows(results, {"2611.00001": {"published": "2026-11-01", "primary_category": "cs.CR"}})
    assert list(rows[0]) == CSV_FIELDS
    assert rows[0]["n_confirmed_exists"] == 3
    assert rows[0]["n_counted_gaps"] == 2
    assert rows[0]["counted_gap_titles"] == "Missing A | Missing C"
    assert rows[0]["counted_gap_dois"] == "10.1/a | 10.1/c"
    assert rows[0]["primary_category"] == "cs.CR"
    assert rows[1]["n_counted_gaps"] == 0 and rows[1]["status"] == "error"
