#!/usr/bin/env python3
# backend/benchmark/rescore.py
"""Re-run the already-cited check on a saved benchmark run. No model calls.

Reads a run's .jsonl, takes each paper's text from the run's texts-<run_id>/
folder (or downloads and extracts the arXiv PDF again when it is missing,
as for runs made before the check existed), re-applies cited_check, and
writes <run>.rescored.jsonl, <run>.rescored.md and <run>.csv next to it.

Usage:
  python3 backend/benchmark/rescore.py ~/.purplelink/benchmark/citation-gap-benchmark-<run_id>.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

logger = logging.getLogger(__name__)


async def _paper_text(client, arxiv_id: str, text_dir: Path) -> tuple[str, list[dict]] | None:
    """Full page text plus parsed references, re-extracted from the PDF.
    The references always come from extract_paper; the text is cached."""
    from benchmark.arxiv_corpus import fetch_pdf
    from latextools import papercheck

    pdf = await fetch_pdf(client, arxiv_id)
    if pdf is None:
        return None
    page_texts: list = []
    try:
        structure = papercheck.extract_paper(pdf, page_texts=page_texts)
    except Exception:
        logger.exception("extraction failed for %s", arxiv_id)
        return None
    text = "\n".join(t or "" for _, t in page_texts)
    (text_dir / f"{arxiv_id}.txt").write_text(text, encoding="utf-8")
    return text, [r.to_dict() for r in structure.references]


async def rescore(jsonl: Path) -> int:
    import httpx
    from benchmark.aggregate import CSV_FIELDS, PaperResult, csv_rows, summarize
    from benchmark.cited_check import apply_cited_check

    run_id = re.search(r"\d{8}T\d{6}Z", jsonl.name).group(0)
    text_dir = jsonl.parent / f"texts-{run_id}"
    text_dir.mkdir(exist_ok=True)
    rows = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]

    results, meta, out_rows = [], {}, []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i, row in enumerate(rows, 1):
            gaps = row.get("gaps") or []
            if row.get("status") == "ok":
                cached = text_dir / f"{row['arxiv_id']}.txt"
                if cached.exists() and row.get("references") is not None:
                    text, refs = cached.read_text(encoding="utf-8"), row["references"]
                else:
                    logger.info("[%d/%d] re-extracting %s", i, len(rows), row["arxiv_id"])
                    got = await _paper_text(client, row["arxiv_id"], text_dir)
                    if got is None:
                        # Without the paper text there is no way to tell; drop the
                        # verdict so the gap cannot count.
                        text, refs = None, None
                    else:
                        text, refs = got
                        row["references"] = refs
                if text is not None:
                    gaps = apply_cited_check(gaps, text, refs)
                else:
                    gaps = [{k: v for k, v in g.items() if k != "already_cited"} for g in gaps]
                row["gaps"] = gaps
            results.append(PaperResult(row["arxiv_id"], row.get("title", ""), row.get("status", "error"), gaps))
            cats = row.get("categories") or []
            meta[row["arxiv_id"]] = {"published": row.get("published", ""), "primary_category": cats[0] if cats else ""}
            out_rows.append(row)

    summary = summarize(results)
    # Re-scoring a .rescored.jsonl again overwrites it rather than stacking suffixes.
    stem = jsonl.parent / f"citation-gap-benchmark-{run_id}"
    Path(f"{stem}.rescored.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in out_rows), encoding="utf-8")
    with open(f"{stem}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(csv_rows(results, meta))
    Path(f"{stem}.rescored.md").write_text(
        f"# Rescored {jsonl.name}\n\n"
        f"- Papers analyzed: {summary.n_papers_ok} of {summary.n_papers_attempted}\n"
        f"- With a CrossRef-matched gap: {summary.n_papers_with_confirmed_gap} ({summary.pct_with_confirmed_gap}%)\n"
        f"- With a matched gap the paper does not cite: {summary.n_papers_with_uncited_gap} "
        f"({summary.pct_with_uncited_gap}%)\n"
        f"- Matched gaps: {summary.n_confirmed_gaps}; strict title match: {summary.n_strict_gaps}; already cited: {summary.n_confirmed_gaps_already_cited}; "
        f"counted: {summary.n_counted_gaps}\n"
        f"- Verification statuses: {json.dumps(summary.verification_status_counts)}\n",
        encoding="utf-8",
    )
    print(Path(f"{stem}.rescored.md").read_text(encoding="utf-8"))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jsonl", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(rescore(args.jsonl.expanduser()))


if __name__ == "__main__":
    raise SystemExit(main())
