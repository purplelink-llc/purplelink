# backend/listen/sources.py
"""Fetch recent posts from HN (Algolia) + Stack Exchange (Academia) for the
listen-and-surface agent.

Both APIs are public and require no auth. Results are deduped by ID and
filtered to items posted within the last LOOKBACK_HOURS. This module only
fetches and normalizes — scoring for reply-worthiness happens in scorer.py,
and nothing here ever posts anywhere.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# Slightly over 24h so a daily cron running a few minutes late never leaves
# a gap between one day's lookback window and the next.
LOOKBACK_HOURS = 26

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
SE_API_URL = "https://api.stackexchange.com/2.3/search/advanced"

# Purplelink's tools solve for: peer-review prep, reviewer-response writing,
# and citation/reference formatting. These phrases are chosen to catch
# someone visibly in that moment, not general "AI" or "research" chatter —
# broader keywords would flood the digest with irrelevant noise.
KEYWORDS = [
    "reviewer 2",
    "peer review feedback",
    "response to reviewers",
    "manuscript rejected",
    "desk reject",
    "camera ready deadline",
    "citation formatting",
    "LaTeX bibliography",
]


@dataclass
class ListenItem:
    source: str          # "hn" | "stackexchange"
    title: str
    url: str
    snippet: str
    created_at: float    # unix ts
    id: str = field(default="")


async def fetch_hn(client: httpx.AsyncClient) -> list[ListenItem]:
    """Search HN stories + comments posted in the lookback window, one
    query per keyword phrase (Algolia's query param does relevance
    matching, not keyword OR, so separate calls are the reliable way to
    cover the whole keyword list)."""
    cutoff = time.time() - LOOKBACK_HOURS * 3600
    seen_ids: set[str] = set()
    items: list[ListenItem] = []
    for kw in KEYWORDS:
        try:
            resp = await client.get(
                HN_ALGOLIA_URL,
                params={
                    "query": kw,
                    "tags": "(story,comment)",
                    "numericFilters": f"created_at_i>{int(cutoff)}",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as exc:
            logger.warning("listen: HN query %r failed: %s", kw, exc)
            continue
        for hit in hits:
            oid = hit.get("objectID", "")
            if not oid or oid in seen_ids:
                continue
            title = (hit.get("title") or hit.get("story_title")
                     or (_strip_html(hit.get("comment_text") or ""))[:120]).strip()
            snippet = _strip_html(hit.get("comment_text") or hit.get("story_text") or "")[:500]
            # Algolia's relevance search matches on individual words, not the
            # whole phrase — a query for "camera ready deadline" happily
            # returns posts that only mention "deadline". Require the exact
            # phrase to actually appear so the digest stays signal, not noise.
            if not _contains_phrase(kw, title, snippet):
                continue
            seen_ids.add(oid)
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
            items.append(ListenItem(
                source="hn",
                title=title,
                url=url,
                snippet=snippet,
                created_at=hit.get("created_at_i", 0),
                id=oid,
            ))
    return items


async def fetch_stackexchange(client: httpx.AsyncClient) -> list[ListenItem]:
    """Search academia.stackexchange.com question titles for the same
    keyword list, restricted to questions created in the lookback window."""
    cutoff = int(time.time() - LOOKBACK_HOURS * 3600)
    seen_ids: set[str] = set()
    items: list[ListenItem] = []
    for kw in KEYWORDS:
        try:
            resp = await client.get(
                SE_API_URL,
                params={
                    "order": "desc",
                    "sort": "creation",
                    "title": kw,
                    "site": "academia",
                    "fromdate": cutoff,
                    "filter": "withbody",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("listen: Stack Exchange query %r failed: %s", kw, exc)
            continue
        for q in data.get("items", []):
            qid = str(q.get("question_id", ""))
            if not qid or qid in seen_ids:
                continue
            title = q.get("title", "")
            snippet = _strip_html(q.get("body") or "")[:500]
            if not _contains_phrase(kw, title, snippet):
                continue
            seen_ids.add(qid)
            items.append(ListenItem(
                source="stackexchange",
                title=title,
                url=q.get("link", ""),
                snippet=snippet,
                created_at=q.get("creation_date", 0),
                id=qid,
            ))
    return items


def _strip_html(raw: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", raw).strip()


def _contains_phrase(phrase: str, *texts: str) -> bool:
    needle = phrase.lower()
    return any(needle in t.lower() for t in texts if t)
