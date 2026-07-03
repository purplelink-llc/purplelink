# backend/benchmark/arxiv_corpus.py
"""Pull a real, citable sample of arXiv papers for the Citation Gap
benchmark pipeline.

Uses arXiv's public Search API (export.arxiv.org/api/query) — free, no
auth, returns real paper metadata (title, arXiv ID, categories, published
date). PDFs are fetched via arXiv's standard PDF URL pattern. Nothing here
is synthetic: every paper in the resulting corpus is a real, citable arXiv
identifier, so any statistic later computed over it can be reproduced and
verified against the same IDs.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"

# Categories matching Purplelink's own research focus (see BEN_PROFILE in
# digest/curator.py) — cybersecurity, AI/ML, information systems. Keeping
# the benchmark scoped to categories the founder can sanity-check the
# results against, rather than an arbitrary all-of-arXiv sample.
DEFAULT_CATEGORIES = ["cs.CR", "cs.AI", "cs.LG", "cs.CY"]


@dataclass
class ArxivPaper:
    arxiv_id: str          # e.g. "2507.01234"
    title: str
    categories: list[str] = field(default_factory=list)
    published: str = ""    # ISO date string from the API, unmodified


async def fetch_corpus(
    client: httpx.AsyncClient,
    *,
    categories: list[str] = DEFAULT_CATEGORIES,
    max_results: int = 50,
    start: int = 0,
) -> list[ArxivPaper]:
    """Query the arXiv Search API for a page of real papers.

    max_results is capped at 100 by arXiv's own API; page with `start` for
    a larger sample. Results are whatever arXiv's relevance-sorted default
    returns for the category query — no filtering or cherry-picking here,
    since a benchmark sample has to be representative to mean anything.
    """
    max_results = min(max_results, 100)
    query = " OR ".join(f"cat:{c}" for c in categories)
    try:
        resp = await client.get(
            ARXIV_API_URL,
            params={
                "search_query": query,
                "start": start,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        logger.exception("fetch_corpus: arXiv API request failed")
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        logger.exception("fetch_corpus: arXiv API returned unparseable XML")
        return []

    papers = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        id_url = (entry.findtext(f"{_ATOM_NS}id") or "").strip()
        # id_url looks like "http://arxiv.org/abs/2507.01234v1"
        arxiv_id = id_url.rsplit("/", 1)[-1]
        arxiv_id = arxiv_id.rsplit("v", 1)[0] if "v" in arxiv_id else arxiv_id
        title = (entry.findtext(f"{_ATOM_NS}title") or "").strip().replace("\n", " ")
        published = (entry.findtext(f"{_ATOM_NS}published") or "").strip()
        cats = [
            c.get("term", "")
            for c in entry.findall("{http://arxiv.org/schemas/atom}primary_category")
        ]
        if not arxiv_id or not title:
            continue
        papers.append(ArxivPaper(
            arxiv_id=arxiv_id, title=title, categories=cats, published=published,
        ))
    return papers


async def fetch_pdf(client: httpx.AsyncClient, arxiv_id: str) -> bytes | None:
    """Download the PDF bytes for one arXiv paper. Returns None on any
    failure — a single unavailable PDF shouldn't abort the whole run."""
    try:
        resp = await client.get(
            ARXIV_PDF_URL.format(arxiv_id=arxiv_id),
            timeout=60.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content
    except Exception:
        logger.warning("fetch_pdf: failed for %s", arxiv_id)
        return None
