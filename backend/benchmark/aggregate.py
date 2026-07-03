# backend/benchmark/aggregate.py
"""Pure aggregation over a batch of run_citation_gap() results.

No network calls, no LLM calls — takes the raw per-paper results the
runner already collected and computes the summary statistic. Kept
separate from run_benchmark.py so the math is unit-testable without
needing Anthropic credentials or a live arXiv fetch.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class PaperResult:
    arxiv_id: str
    title: str
    status: str                 # "ok" | "error" | "extraction_failed"
    gaps: list[dict] = field(default_factory=list)


@dataclass
class BenchmarkSummary:
    n_papers_attempted: int
    n_papers_ok: int
    n_papers_with_confirmed_gap: int
    pct_with_confirmed_gap: float
    median_gaps_per_paper: float
    gap_type_counts: dict
    verification_status_counts: dict


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def summarize(results: list[PaperResult]) -> BenchmarkSummary:
    """CONFIRMED gap == a gap whose CrossRef verification came back
    "confirmed_exists" (see _verify_gap_candidate in paperreview_extras.py)
    — i.e. the model named a real, independently-verifiable paper that the
    manuscript didn't cite. Gaps that are "qualitative_gap" or
    "not_searched"/"not_found"/"weak_match" are excluded from the headline
    percentage on purpose: the point of this benchmark is a defensible
    statistic, not the largest possible number."""
    ok_results = [r for r in results if r.status == "ok"]

    gap_type_counts: Counter = Counter()
    verification_counts: Counter = Counter()
    gaps_per_paper: list[float] = []
    n_with_confirmed = 0

    for r in ok_results:
        confirmed_this_paper = 0
        for gap in r.gaps:
            gap_type_counts[gap.get("gap_type", "unknown")] += 1
            v_status = (gap.get("verification") or {}).get("status", "not_searched")
            verification_counts[v_status] += 1
            if v_status == "confirmed_exists":
                confirmed_this_paper += 1
        gaps_per_paper.append(len(r.gaps))
        if confirmed_this_paper > 0:
            n_with_confirmed += 1

    n_ok = len(ok_results)
    pct = (n_with_confirmed / n_ok * 100) if n_ok else 0.0

    return BenchmarkSummary(
        n_papers_attempted=len(results),
        n_papers_ok=n_ok,
        n_papers_with_confirmed_gap=n_with_confirmed,
        pct_with_confirmed_gap=round(pct, 1),
        median_gaps_per_paper=_median(gaps_per_paper),
        gap_type_counts=dict(gap_type_counts),
        verification_status_counts=dict(verification_counts),
    )
