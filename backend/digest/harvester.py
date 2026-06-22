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
