#!/usr/bin/env python3
# backend/benchmark/run_benchmark.py
"""Citation Gap benchmark runner — produces an original, defensible
statistic ("N% of a real arXiv sample had at least one confirmed-real
missing citation") for future marketing/content use.

THIS SCRIPT COSTS REAL MONEY WHEN RUN. It calls the same Anthropic API
Citation Gap uses in production, once per paper in the sample. It is NOT
wired into any cron, Modal app, or CI job — it only runs if invoked
directly, and only proceeds past the cost estimate with --confirm-cost.

Do not run this until there's budget allocated for it (see the
conversation this was built in: the founder explicitly declined to publish
fabricated/estimated statistics and asked for this pipeline to be built,
cheap to execute, rather than run speculatively).

Every input paper is a real, citable arXiv ID pulled live from arXiv's own
API — nothing in the corpus or the output is synthetic. The full raw
per-paper results are written alongside the summary so the eventual
statistic is independently reproducible against the same arXiv IDs.

Usage:
  python3 backend/benchmark/run_benchmark.py --confirm-cost --sample-size 50

Requires ANTHROPIC_API_KEY in the environment (same as the production
pipeline — see backend/latextools/paperreview_extras.py).
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cost estimate — sourced from real numbers already in the codebase, not
# invented for this script. See PAID_PRODUCTS pricing comment in app.py
# ("Fable 5 is ~$10/$50 per MTok") and PERSONA_MAX_OUTPUT_TOKENS in
# latextools/papercheck.py (the actual output cap run_citation_gap uses).
# Input tokens vary a lot by paper length; this is a rough per-paper upper
# bound assuming a ~15k-token manuscript excerpt + prompt overhead, not a
# precise cost model — treat it as "don't run this without checking your
# Anthropic billing dashboard afterward," not a guarantee.
# ---------------------------------------------------------------------------
_FABLE5_INPUT_PER_MTOK = 10.0
_FABLE5_OUTPUT_PER_MTOK = 50.0
_EST_INPUT_TOKENS_PER_PAPER = 15_000
_EST_OUTPUT_TOKENS_PER_PAPER = 4_000  # PERSONA_MAX_OUTPUT_TOKENS


def _estimate_cost_usd(n_papers: int) -> float:
    per_paper = (
        _EST_INPUT_TOKENS_PER_PAPER / 1_000_000 * _FABLE5_INPUT_PER_MTOK
        + _EST_OUTPUT_TOKENS_PER_PAPER / 1_000_000 * _FABLE5_OUTPUT_PER_MTOK
    )
    return round(per_paper * n_papers, 2)


async def _run_one(client, arxiv_paper):
    from benchmark.arxiv_corpus import fetch_pdf
    from benchmark.aggregate import PaperResult
    from latextools import papercheck
    from latextools.paperreview_extras import run_citation_gap

    pdf_bytes = await fetch_pdf(client, arxiv_paper.arxiv_id)
    if pdf_bytes is None:
        return PaperResult(arxiv_paper.arxiv_id, arxiv_paper.title, status="error")

    try:
        structure = papercheck.extract_paper(pdf_bytes)
    except Exception:
        logger.exception("extraction failed for %s", arxiv_paper.arxiv_id)
        return PaperResult(arxiv_paper.arxiv_id, arxiv_paper.title, status="extraction_failed")

    result = await run_citation_gap(client, structure)
    if result.get("status") == "error":
        return PaperResult(arxiv_paper.arxiv_id, arxiv_paper.title, status="error")

    return PaperResult(
        arxiv_paper.arxiv_id, arxiv_paper.title,
        status="ok", gaps=result.get("gaps", []),
    )


async def main_async(args):
    import httpx
    from benchmark.arxiv_corpus import fetch_corpus, DEFAULT_CATEGORIES
    from benchmark.aggregate import summarize

    categories = args.categories or DEFAULT_CATEGORIES

    async with httpx.AsyncClient() as client:
        logger.info("fetching corpus: categories=%s sample_size=%d", categories, args.sample_size)
        papers = await fetch_corpus(client, categories=categories, max_results=args.sample_size)
        if not papers:
            logger.error("no papers returned from arXiv API; aborting")
            return 1
        logger.info("fetched %d real arXiv papers", len(papers))

        results = []
        for i, paper in enumerate(papers, 1):
            logger.info("[%d/%d] %s — %s", i, len(papers), paper.arxiv_id, paper.title[:80])
            results.append(await _run_one(client, paper))

    summary = summarize(results)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    raw_path = out_dir / f"citation-gap-benchmark-{run_id}.jsonl"
    with raw_path.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps({
                "arxiv_id": r.arxiv_id, "title": r.title,
                "status": r.status, "gaps": r.gaps,
            }) + "\n")

    report_path = out_dir / f"citation-gap-benchmark-{run_id}.md"
    report_path.write_text(_render_report(summary, categories, run_id, len(papers)))

    logger.info("wrote %s", raw_path)
    logger.info("wrote %s", report_path)
    print(f"\n{summary.pct_with_confirmed_gap}% of {summary.n_papers_ok} papers "
          f"had at least one CrossRef-confirmed missing citation.")
    return 0


def _render_report(summary, categories, run_id, n_fetched) -> str:
    today = datetime.date.today().isoformat()
    return f"""# Citation Gap Benchmark — {run_id}

**Methodology:** {n_fetched} papers pulled live from arXiv's public Search
API on {today}, from categories: {", ".join(categories)}, sorted by most
recent submission (no cherry-picking). Each paper's PDF was run through
Purplelink's Citation Gap analysis exactly as a paying customer would
receive it — the same `run_citation_gap()` function, same model, same
CrossRef verification step. Every arXiv ID here is real and independently
checkable.

**Headline statistic:** {summary.pct_with_confirmed_gap}% of the
{summary.n_papers_ok} successfully-analyzed papers had at least one
citation gap that Citation Gap flagged AND CrossRef independently
confirmed corresponds to a real, existing paper (`verification.status ==
"confirmed_exists"`). This excludes qualitative/unverified gaps on
purpose — see aggregate.py's summarize() docstring for why.

**Sample size:** {summary.n_papers_attempted} attempted, {summary.n_papers_ok} successfully analyzed
(the rest failed PDF download or text extraction — this is expected for a
fully-automated pull straight from arXiv, not a data-quality problem to
paper over).

**Median gaps flagged per paper (all types, not just confirmed):** {summary.median_gaps_per_paper}

**Gap type breakdown:** {json.dumps(summary.gap_type_counts)}

**Verification status breakdown:** {json.dumps(summary.verification_status_counts)}

---
Before publishing this statistic anywhere: re-read this methodology
section for accuracy, spot-check a handful of the confirmed gaps in the
.jsonl file against the actual papers, and disclose the sample size and
category scope alongside the headline number — don't present a
category-scoped, single-run sample as a general claim about "academic
papers."
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-size", type=int, default=50, help="Number of papers to pull (max 100 per arXiv API call).")
    parser.add_argument("--categories", nargs="*", default=None, help="arXiv category codes, e.g. cs.CR cs.AI. Defaults to Purplelink's research-focus categories.")
    parser.add_argument("--output-dir", default="backend/benchmark/output", help="Where to write the raw .jsonl and .md report.")
    parser.add_argument(
        "--confirm-cost", action="store_true",
        help="Required to actually run. Without it, prints the cost estimate and exits.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    est_cost = _estimate_cost_usd(args.sample_size)
    print(f"Estimated Anthropic API cost for {args.sample_size} papers: ~${est_cost:.2f}")
    print("(Rough upper-bound estimate — see the comment above _estimate_cost_usd for the basis. "
          "Check your Anthropic billing dashboard after running.)")

    if not args.confirm_cost:
        print("\nNot running — pass --confirm-cost to proceed.")
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nANTHROPIC_API_KEY is not set in the environment. Aborting.")
        return 1

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
