# backend/digest/harvester.py
"""Async content harvester — fetches all sources → list[RawItem].

Each fetcher handles one SourceType. All failures are caught and logged;
no source failure blocks the run.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

logger = logging.getLogger(__name__)

FRESHNESS_HOURS = 48  # items older than this are dropped
_USER_AGENT = "PurplelinkDigest/1.0 contact@purplelink.llc"


@dataclass
class RawItem:
    title: str
    url: str
    source_name: str
    snippet: str
    published_at: datetime.datetime
    category: str


def _normalize_url(url: str) -> str:
    """Strip UTM params and trailing slash for deduplication."""
    parsed = urlparse(url)
    qs = {k: v for k, v in parse_qs(parsed.query).items()
          if not k.startswith("utm_")}
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    clean = urlunparse(parsed._replace(query=new_query, fragment=""))
    return clean.rstrip("/")


def _is_fresh(dt: Optional[datetime.datetime], hours: int = FRESHNESS_HOURS) -> bool:
    if dt is None:
        return True  # unknown timestamp → include it
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    age = datetime.datetime.now(datetime.timezone.utc) - dt
    return age.total_seconds() < hours * 3600


def _parse_dt(value) -> Optional[datetime.datetime]:
    """Convert feedparser time_struct or ISO string to datetime."""
    if value is None:
        return None
    if hasattr(value, "tm_year"):  # feedparser time_struct
        import calendar
        ts = calendar.timegm(value)
        return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(value, fmt).replace(
                    tzinfo=datetime.timezone.utc)
            except ValueError:
                continue
    return None


async def fetch_rss(client, source_def) -> list[RawItem]:
    """Fetch an RSS or Atom feed and return fresh RawItems."""
    import feedparser
    try:
        resp = await client.get(
            source_def.url,
            headers={"User-Agent": _USER_AGENT},
            timeout=10.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("fetch_rss %s failed: %s", source_def.name, exc)
        return []

    feed = feedparser.parse(resp.content)
    items: list[RawItem] = []
    for entry in feed.entries:
        # feedparser: entry.link is preferred; fall back to entry.id for
        # feeds that use <guid isPermaLink="true"> without a <link> element.
        url = getattr(entry, "link", None) or getattr(entry, "id", None) or ""
        if not url:
            continue
        title = getattr(entry, "title", "").strip() or "(untitled)"
        snippet = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
        )
        # Strip HTML tags from snippet.
        snippet = re.sub(r"<[^>]+>", " ", snippet).strip()[:500]
        pub = _parse_dt(getattr(entry, "published_parsed", None)
                        or getattr(entry, "updated_parsed", None))
        if not _is_fresh(pub):
            continue
        items.append(RawItem(
            title=title,
            url=_normalize_url(url),
            source_name=source_def.name,
            snippet=snippet,
            published_at=pub or datetime.datetime.now(datetime.timezone.utc),
            category=source_def.category,
        ))
    return items


async def fetch_hn_algolia(client, source_def) -> list[RawItem]:
    """Fetch HN front-page stories from Algolia with a score threshold."""
    yesterday = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
    unix_cutoff = int(yesterday.timestamp())
    min_points = source_def.params.get("min_points", 100)
    try:
        resp = await client.get(
            source_def.url,
            params={
                "tags": "front_page,story",
                "numericFilters": f"points>={min_points},created_at_i>{unix_cutoff}",
                "hitsPerPage": 30,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("fetch_hn_algolia failed: %s", exc)
        return []

    data = resp.json()
    items: list[RawItem] = []
    for hit in data.get("hits", []):
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        pub = _parse_dt(hit.get("created_at"))
        if not _is_fresh(pub):
            continue
        items.append(RawItem(
            title=hit.get("title", "").strip(),
            url=_normalize_url(url),
            source_name=source_def.name,
            snippet=hit.get("story_text", "") or "",
            published_at=pub or datetime.datetime.now(datetime.timezone.utc),
            category=source_def.category,
        ))
    return items


async def fetch_arxiv_oai(client, source_def) -> list[RawItem]:
    """Fetch arXiv papers via OAI-PMH for each configured set."""
    import xml.etree.ElementTree as ET

    yesterday = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)).strftime("%Y-%m-%d")
    sets = source_def.params.get("sets", ["cs"])
    items: list[RawItem] = []

    for set_spec in sets:
        try:
            resp = await client.get(
                source_def.url,
                params={
                    "verb": "ListRecords",
                    "metadataPrefix": "oai_dc",
                    "set": set_spec,
                    "from": yesterday,
                },
                headers={"User-Agent": _USER_AGENT},
                timeout=15.0,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("fetch_arxiv_oai set=%s failed: %s", set_spec, exc)
            continue

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as exc:
            logger.warning("fetch_arxiv_oai XML parse error: %s", exc)
            continue

        ns = {
            "oai": "http://www.openarchives.org/OAI/2.0/",
            "dc": "http://purl.org/dc/elements/1.1/",
            "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        }
        for record in root.findall(".//oai:record", ns):
            dc = record.find(".//oai_dc:dc", ns)
            if dc is None:
                continue
            title = (dc.findtext("dc:title", namespaces=ns) or "").strip()
            desc = (dc.findtext("dc:description", namespaces=ns) or "").strip()[:500]
            date_str = dc.findtext("dc:date", namespaces=ns) or ""
            identifier = dc.findtext("dc:identifier", namespaces=ns) or ""
            url = next((v for v in [identifier] if "arxiv.org" in v), "")
            if not url or not title:
                continue
            pub = _parse_dt(date_str)
            if not _is_fresh(pub):
                continue
            items.append(RawItem(
                title=title,
                url=_normalize_url(url),
                source_name=source_def.name,
                snippet=desc,
                published_at=pub or datetime.datetime.now(datetime.timezone.utc),
                category=source_def.category,
            ))
    return items


async def fetch_semantic_scholar(client, source_def) -> list[RawItem]:
    """Fetch recent papers from Semantic Scholar bulk search."""
    import os

    api_key = ""
    key_env = source_def.params.get("api_key_env", "")
    if key_env:
        api_key = os.environ.get(key_env, "")

    headers = {"User-Agent": _USER_AGENT}
    if api_key:
        headers["x-api-key"] = api_key

    fields = "paperId,title,abstract,publicationDate,externalIds"
    items: list[RawItem] = []
    seen_ids: set[str] = set()

    for query in source_def.params.get("queries", []):
        try:
            resp = await client.get(
                source_def.url,
                params={"query": query, "fields": fields, "limit": 10},
                headers=headers,
                timeout=12.0,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("fetch_semantic_scholar query=%r failed: %s", query, exc)
            continue

        for paper in resp.json().get("data", []):
            pid = paper.get("paperId", "")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            arxiv_id = (paper.get("externalIds") or {}).get("ArXiv", "")
            url = (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
                   else f"https://www.semanticscholar.org/paper/{pid}")
            pub = _parse_dt(paper.get("publicationDate"))
            if not _is_fresh(pub):
                continue
            items.append(RawItem(
                title=(paper.get("title") or "").strip(),
                url=_normalize_url(url),
                source_name=source_def.name,
                snippet=(paper.get("abstract") or "")[:500],
                published_at=pub or datetime.datetime.now(datetime.timezone.utc),
                category=source_def.category,
            ))
    return items


def _reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    """Reconstruct abstract text from OpenAlex inverted index."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for pos in idxs:
            positions.append((pos, word))
    positions.sort()
    return " ".join(w for _, w in positions)


async def fetch_openalex(client, source_def) -> list[RawItem]:
    """Fetch recent works from OpenAlex."""
    yesterday = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)).strftime("%Y-%m-%d")
    items: list[RawItem] = []

    try:
        resp = await client.get(
            source_def.url,
            params={
                "filter": f"from_publication_date:{yesterday}",
                "sort": "publication_date:desc",
                "per-page": 25,
                "select": "id,title,abstract_inverted_index,publication_date,primary_location",
            },
            headers={
                "User-Agent": _USER_AGENT,
                "mailto": "contact@purplelink.llc",
            },
            timeout=12.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("fetch_openalex failed: %s", exc)
        return []

    for work in resp.json().get("results", []):
        title = (work.get("title") or "").strip()
        if not title:
            continue
        url = ((work.get("primary_location") or {}).get("landing_page_url")
               or work.get("id") or "")
        if not url:
            continue
        pub = _parse_dt(work.get("publication_date"))
        if not _is_fresh(pub):
            continue
        snippet = _reconstruct_abstract(work.get("abstract_inverted_index"))[:500]
        items.append(RawItem(
            title=title,
            url=_normalize_url(url),
            source_name=source_def.name,
            snippet=snippet,
            published_at=pub or datetime.datetime.now(datetime.timezone.utc),
            category=source_def.category,
        ))
    return items


async def fetch_huggingface_papers(client, source_def) -> list[RawItem]:
    """Fetch daily trending papers from HuggingFace."""
    try:
        resp = await client.get(
            source_def.url,
            headers={"User-Agent": _USER_AGENT},
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("fetch_huggingface_papers failed: %s", exc)
        return []

    items: list[RawItem] = []
    for entry in resp.json():
        paper = entry.get("paper") or {}
        arxiv_id = paper.get("id", "")
        title = (paper.get("title") or "").strip()
        if not title or not arxiv_id:
            continue
        url = f"https://arxiv.org/abs/{arxiv_id}"
        pub = _parse_dt(paper.get("publishedAt"))
        if not _is_fresh(pub):
            continue
        items.append(RawItem(
            title=title,
            url=_normalize_url(url),
            source_name=source_def.name,
            snippet=(paper.get("summary") or "")[:500],
            published_at=pub or datetime.datetime.now(datetime.timezone.utc),
            category=source_def.category,
        ))
    return items


import digest.sources as _sources_mod
from digest.sources import SourceType as _SourceType


def _get_fetcher(source_type):
    """Look up fetcher by SourceType using current module globals (monkeypatch-friendly)."""
    import sys
    _self = sys.modules[__name__]
    mapping = {
        _SourceType.RSS: "fetch_rss",
        _SourceType.HN_ALGOLIA: "fetch_hn_algolia",
        _SourceType.ARXIV_OAI: "fetch_arxiv_oai",
        _SourceType.SEMANTIC_SCHOLAR: "fetch_semantic_scholar",
        _SourceType.OPENALEX: "fetch_openalex",
        _SourceType.HF_PAPERS: "fetch_huggingface_papers",
    }
    name = mapping.get(source_type)
    return getattr(_self, name) if name else None


async def harvest_all(client) -> list[RawItem]:
    """Fetch all sources concurrently, deduplicate by URL, return fresh items."""
    sources = _sources_mod.SOURCES
    tasks = []
    for src in sources:
        fetcher = _get_fetcher(src.type)
        if fetcher:
            tasks.append(fetcher(client, src))
        else:
            logger.warning("No fetcher for SourceType %s", src.type)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_urls: set[str] = set()
    items: list[RawItem] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("harvest_all task error: %s", result)
            continue
        for item in result:
            norm = _normalize_url(item.url)
            if norm not in seen_urls:
                seen_urls.add(norm)
                item.url = norm
                items.append(item)

    logger.info("harvest_all: %d unique items from %d sources", len(items), len(sources))
    return items
