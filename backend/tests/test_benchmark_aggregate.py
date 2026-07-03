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
