# Compliance Tracker — Ingestion + Stage 1 Tagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ingestion pipeline (Federal Register, LegiScan, state DOL scraping) and Stage 1 LLM tagging that together produce a database of correctly-classified regulatory items, with no customer-facing pieces yet.

**Architecture:** Three independent source fetchers each return a common `RawItem` shape; an ingestion orchestrator dedupes and writes new items to Postgres (SQLite in-memory for tests); a Stage 1 tagger calls Anthropic once per item to produce structured `ItemTag` rows (jurisdiction, topic, headcount threshold, effective date, confidence), independent of any customer. A Modal cron job ties ingestion and tagging together into a daily scheduled run.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x (Postgres in production via `DATABASE_URL`, SQLite in-memory for tests), httpx for all HTTP (Federal Register API, LegiScan API, Anthropic API, state DOL page fetches), lxml + cssselect for HTML scraping, Modal for scheduled execution — all matching Purplelink's existing backend conventions (`backend/latextools/papercheck.py`'s `httpx.AsyncClient` + `x-api-key` pattern, `asyncio.run(...)` in sync test functions rather than `pytest.mark.asyncio`, `add_local_python_source(...)` on the Modal image per the fix already landed in `backend/app.py`).

---

### Task 1: Package skeleton, database models, connection helpers

**Files:**
- Create: `backend/compliance/__init__.py`
- Create: `backend/compliance/models.py`
- Create: `backend/compliance/db.py`
- Modify: `backend/requirements-dev.txt`
- Test: `backend/tests/compliance/test_models.py`

- [ ] **Step 1: Create the package init file**

`backend/compliance/__init__.py`:
```python
```

(Empty — just marks `compliance` as a package, matching `backend/latextools/__init__.py`'s role.)

- [ ] **Step 2: Write the failing test**

`backend/tests/compliance/test_models.py`:
```python
import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.db import make_engine, get_session
from compliance.models import RegulatoryItem


@pytest.fixture
def session():
    engine = make_engine("sqlite:///:memory:")
    return get_session(engine)


def test_regulatory_item_roundtrip(session):
    item = RegulatoryItem(
        source="federal_register",
        source_ref="2026-12345",
        raw_text="A new rule regarding overtime pay.",
        published_date=dt.date(2026, 7, 1),
    )
    session.add(item)
    session.commit()

    fetched = session.query(RegulatoryItem).filter_by(source_ref="2026-12345").one()
    assert fetched.raw_text == "A new rule regarding overtime pay."
    assert fetched.source == "federal_register"


def test_duplicate_source_ref_rejected(session):
    session.add(RegulatoryItem(
        source="legiscan", source_ref="CA-SB123", raw_text="first",
        published_date=dt.date(2026, 1, 1),
    ))
    session.commit()

    session.add(RegulatoryItem(
        source="legiscan", source_ref="CA-SB123", raw_text="duplicate",
        published_date=dt.date(2026, 1, 2),
    ))
    with pytest.raises(IntegrityError):
        session.commit()
```

- [ ] **Step 3: Run the test to verify it fails**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'compliance.models'` (or similar — the module doesn't exist yet).

- [ ] **Step 4: Write the models**

`backend/compliance/models.py`:
```python
"""SQLAlchemy models for the compliance tracker's regulatory-item pipeline.

RegulatoryItem is one row per raw ingested item, deduplicated on
(source, source_ref). ItemTag is the Stage 1 classifier's output: zero or
more structured tags per item, computed once regardless of how many
customers exist (see
docs/superpowers/specs/2026-07-04-compliance-tracker-design.md).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Float,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class RegulatoryItem(Base):
    __tablename__ = "regulatory_items"

    id = Column(Integer, primary_key=True)
    source = Column(String(32), nullable=False)  # "federal_register" | "legiscan" | "state_dol_scrape"
    source_ref = Column(String(256), nullable=False)
    raw_text = Column(Text, nullable=False)
    published_date = Column(Date, nullable=False)
    ingested_at = Column(DateTime, nullable=False, default=dt.datetime.utcnow)

    tags = relationship("ItemTag", back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source", "source_ref", name="uq_regulatory_item_source_ref"),
    )


class ItemTag(Base):
    __tablename__ = "item_tags"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("regulatory_items.id"), nullable=False)
    jurisdiction = Column(String(64), nullable=False)  # e.g. "CA", "US", "Seattle, WA"
    topic = Column(String(32), nullable=False)
    headcount_threshold = Column(Integer, nullable=True)
    effective_date = Column(Date, nullable=True)
    confidence = Column(Float, nullable=False)

    item = relationship("RegulatoryItem", back_populates="tags")


VALID_TOPICS = {
    "minimum_wage",
    "paid_sick_leave",
    "pay_transparency",
    "final_paycheck",
    "other",
}
```

- [ ] **Step 5: Write the connection helpers**

`backend/compliance/db.py`:
```python
"""Database engine/session management for the compliance tracker.

Uses Postgres in production via the DATABASE_URL env var. Tests pass an
explicit `sqlite:///:memory:` URL to `make_engine()` for full isolation with
no external database needed to run `pytest`.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from compliance.models import Base


def make_engine(database_url: str | None = None) -> Engine:
    """Create a new SQLAlchemy engine and ensure tables exist. Pass an
    explicit database_url for tests; production code omits it and relies on
    the DATABASE_URL env var."""
    url = database_url or os.environ["DATABASE_URL"]
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine: Engine) -> Session:
    """Return a new session bound to the given engine."""
    return sessionmaker(bind=engine, future=True)()
```

- [ ] **Step 6: Add new dependencies to requirements-dev.txt**

Modify `backend/requirements-dev.txt` — add these two lines:
```
sqlalchemy==2.0.35
cssselect==1.2.0
```

- [ ] **Step 7: Run the test to verify it passes**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_models.py -v`
Expected: `2 passed`

- [ ] **Step 8: Commit**

```bash
git add backend/compliance/__init__.py backend/compliance/models.py backend/compliance/db.py backend/requirements-dev.txt backend/tests/compliance/test_models.py
git commit -m "feat(compliance): add RegulatoryItem/ItemTag models and DB session helpers"
```

---

### Task 2: Federal Register fetcher

**Files:**
- Create: `backend/compliance/sources/__init__.py`
- Create: `backend/compliance/sources/federal_register.py`
- Test: `backend/tests/compliance/test_federal_register.py`

- [ ] **Step 1: Create the sources package init**

`backend/compliance/sources/__init__.py`:
```python
```

- [ ] **Step 2: Write the failing test**

`backend/tests/compliance/test_federal_register.py`:
```python
import asyncio
import datetime as dt

import httpx

from compliance.sources.federal_register import fetch_federal_register_items


def test_fetch_federal_register_items_parses_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "document_number": "2026-12345",
                        "title": "Minimum Wage Adjustment",
                        "abstract": "Adjusts the federal minimum wage.",
                        "publication_date": "2026-07-01",
                    }
                ]
            },
        )

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_federal_register_items(client, since=dt.date(2026, 6, 1))

    items = asyncio.run(run())

    assert len(items) == 1
    assert items[0].source == "federal_register"
    assert items[0].source_ref == "2026-12345"
    assert "Minimum Wage Adjustment" in items[0].raw_text
    assert items[0].published_date == dt.date(2026, 7, 1)


def test_fetch_federal_register_items_returns_empty_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_federal_register_items(client, since=dt.date(2026, 6, 1))

    items = asyncio.run(run())
    assert items == []
```

- [ ] **Step 3: Run test to verify it fails**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_federal_register.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'compliance.sources.federal_register'`

- [ ] **Step 4: Write the fetcher**

`backend/compliance/sources/federal_register.py`:
```python
"""Fetches recent Federal Register items relevant to labor law.

Federal Register has a free, keyless public API:
https://www.federalregister.gov/developers/documentation/api/v1
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import httpx

FEDERAL_REGISTER_API_URL = "https://www.federalregister.gov/api/v1/documents.json"

# Narrowing to labor-relevant agencies avoids pulling in thousands of
# irrelevant daily notices from every federal agency.
LABOR_RELEVANT_AGENCIES = ["labor-department", "wage-and-hour-division"]


@dataclass
class RawItem:
    source: str
    source_ref: str
    raw_text: str
    published_date: dt.date


async def fetch_federal_register_items(
    client: httpx.AsyncClient, since: dt.date
) -> list[RawItem]:
    """Fetch Federal Register documents published on or after `since` from
    labor-relevant agencies. Returns an empty list (not an exception) on any
    HTTP/network failure — ingest.py treats a failed source as "skip and
    continue", not "fail the whole run"."""
    params = {
        "conditions[agencies][]": LABOR_RELEVANT_AGENCIES,
        "conditions[publication_date][gte]": since.isoformat(),
        "fields[]": ["document_number", "title", "abstract", "publication_date"],
        "per_page": 100,
    }
    try:
        resp = await client.get(FEDERAL_REGISTER_API_URL, params=params, timeout=30.0)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        return []

    data = resp.json()
    items: list[RawItem] = []
    for doc in data.get("results", []):
        published = doc.get("publication_date")
        if not published:
            continue
        title = doc.get("title", "")
        abstract = doc.get("abstract", "") or ""
        items.append(
            RawItem(
                source="federal_register",
                source_ref=doc["document_number"],
                raw_text=f"{title}\n\n{abstract}",
                published_date=dt.date.fromisoformat(published),
            )
        )
    return items
```

- [ ] **Step 5: Run test to verify it passes**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_federal_register.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/compliance/sources/__init__.py backend/compliance/sources/federal_register.py backend/tests/compliance/test_federal_register.py
git commit -m "feat(compliance): add Federal Register ingestion fetcher"
```

---

### Task 3: LegiScan fetcher

**Files:**
- Create: `backend/compliance/sources/legiscan.py`
- Test: `backend/tests/compliance/test_legiscan.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/compliance/test_legiscan.py`:
```python
import asyncio
import datetime as dt

import httpx

from compliance.sources.legiscan import fetch_legiscan_items


def test_fetch_legiscan_items_parses_results(monkeypatch):
    monkeypatch.setenv("LEGISCAN_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "searchresult": {
                    "summary": {"page": 1},
                    "0": {
                        "bill_id": 999,
                        "title": "AB 123 - Minimum Wage Increase",
                        "last_action": "Passed committee",
                        "last_action_date": "2026-07-01",
                    },
                }
            },
        )

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_legiscan_items(client, state="CA", since=dt.date(2026, 6, 1))

    items = asyncio.run(run())

    # One matching bill is returned per search query (4 queries, same mock
    # response each time) — dedup across queries/sources happens later in
    # ingest.py, not in this function.
    assert len(items) == 4
    assert items[0].source == "legiscan"
    assert items[0].source_ref == "CA-999"
    assert "Minimum Wage Increase" in items[0].raw_text


def test_fetch_legiscan_items_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("LEGISCAN_API_KEY", raising=False)

    async def run():
        async with httpx.AsyncClient() as client:
            return await fetch_legiscan_items(client, state="CA", since=dt.date(2026, 6, 1))

    items = asyncio.run(run())
    assert items == []
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_legiscan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'compliance.sources.legiscan'`

- [ ] **Step 3: Write the fetcher**

`backend/compliance/sources/legiscan.py`:
```python
"""Fetches state-legislature bill activity relevant to labor law via the
LegiScan API (https://legiscan.com/legiscan). Requires LEGISCAN_API_KEY.
"""
from __future__ import annotations

import datetime as dt
import os

import httpx

from compliance.sources.federal_register import RawItem

LEGISCAN_API_URL = "https://api.legiscan.com/"

# Full-text search terms covering the labor-law topics this product tracks.
LABOR_SEARCH_QUERIES = [
    "minimum wage",
    "paid sick leave",
    "pay transparency",
    "final paycheck",
]


async def fetch_legiscan_items(
    client: httpx.AsyncClient, state: str, since: dt.date
) -> list[RawItem]:
    """Search LegiScan for labor-law-relevant bills in `state` with activity
    on or after `since`. Returns an empty list on any API/network failure or
    missing API key so a single state's outage doesn't take down the whole
    ingestion run."""
    api_key = os.environ.get("LEGISCAN_API_KEY")
    if not api_key:
        return []

    items: list[RawItem] = []
    for query in LABOR_SEARCH_QUERIES:
        params = {"key": api_key, "op": "getSearch", "state": state, "query": query}
        try:
            resp = await client.get(LEGISCAN_API_URL, params=params, timeout=30.0)
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException):
            continue

        data = resp.json()
        results = data.get("searchresult") or {}
        for key, bill in results.items():
            if key == "summary" or not isinstance(bill, dict):
                continue
            last_action_date = bill.get("last_action_date")
            if not last_action_date:
                continue
            bill_date = dt.date.fromisoformat(last_action_date)
            if bill_date < since:
                continue
            items.append(
                RawItem(
                    source="legiscan",
                    source_ref=f"{state}-{bill.get('bill_id')}",
                    raw_text=f"{bill.get('title', '')}\n\n{bill.get('last_action', '')}",
                    published_date=bill_date,
                )
            )
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_legiscan.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/compliance/sources/legiscan.py backend/tests/compliance/test_legiscan.py
git commit -m "feat(compliance): add LegiScan ingestion fetcher"
```

---

### Task 4: State DOL scraper (California)

**Files:**
- Create: `backend/compliance/sources/state_dol.py`
- Test: `backend/tests/compliance/test_state_dol.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/compliance/test_state_dol.py`:
```python
import datetime as dt

from compliance.sources.state_dol import _parse_california_dir_html

SAMPLE_HTML = """
<html><body>
<div class="news-item">
  <span class="date">07/01/2026</span>
  <a href="/news/2026/release-50.html">DIR Announces 2027 Minimum Wage Increase</a>
  <p class="summary">Effective January 1, 2027, the state minimum wage rises to $17.50/hour.</p>
</div>
<div class="news-item">
  <span class="date">01/01/2020</span>
  <a href="/news/2020/release-1.html">Old unrelated release</a>
  <p class="summary">This is from before the since-date cutoff.</p>
</div>
</body></html>
"""


def test_parse_california_dir_html_extracts_recent_items():
    items = _parse_california_dir_html(SAMPLE_HTML, since=dt.date(2026, 1, 1))

    assert len(items) == 1
    assert items[0].source == "state_dol_scrape"
    assert items[0].source_ref == "CA-DIR-/news/2026/release-50.html"
    assert "Minimum Wage Increase" in items[0].raw_text
    assert items[0].published_date == dt.date(2026, 7, 1)


def test_parse_california_dir_html_filters_out_old_items():
    items = _parse_california_dir_html(SAMPLE_HTML, since=dt.date(2026, 6, 1))
    assert len(items) == 1
    assert items[0].published_date == dt.date(2026, 7, 1)
```

Note: this test asserts against a hand-authored HTML fixture, not the live
`dir.ca.gov` page. The CSS selectors in `_parse_california_dir_html` below
(`div.news-item`, `span.date`, `a`, `p.summary`) are a reasonable starting
structure — when this task is actually deployed, fetch the real page once
and confirm the selectors match its current markup, adjusting them if the
live site's structure differs. That's a real-world verification step every
scraper needs periodically (sites change their HTML), not a sign this task
is incomplete.

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_state_dol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'compliance.sources.state_dol'`

- [ ] **Step 3: Write the scraper**

`backend/compliance/sources/state_dol.py`:
```python
"""Scrapes state Department of Labor announcement pages for labor-law
changes. Each state needs its own parser since page structures differ;
this module currently implements California only. Add another state by
writing another `fetch_<state>_items` function following the same shape
(fetch HTML, delegate to a pure parsing function, return a list of
RawItem) and registering it in STATE_FETCHERS below.
"""
from __future__ import annotations

import datetime as dt

import httpx
from lxml import html

from compliance.sources.federal_register import RawItem

CALIFORNIA_DIR_NEWS_URL = "https://www.dir.ca.gov/DIRNews.html"


async def fetch_california_items(
    client: httpx.AsyncClient, since: dt.date
) -> list[RawItem]:
    """Scrape the California Department of Industrial Relations news page.
    Returns an empty list on any fetch failure so a broken scraper doesn't
    take down the rest of the ingestion run — the caller (ingest.py) is
    responsible for noticing a source has gone quiet over time."""
    try:
        resp = await client.get(CALIFORNIA_DIR_NEWS_URL, timeout=30.0)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        return []
    return _parse_california_dir_html(resp.text, since)


def _parse_california_dir_html(page_html: str, since: dt.date) -> list[RawItem]:
    """Pure parsing function, separated from the network fetch so it can be
    unit-tested against a static HTML fixture instead of the live site."""
    tree = html.fromstring(page_html)
    items: list[RawItem] = []
    for node in tree.cssselect("div.news-item"):
        date_nodes = node.cssselect("span.date")
        link_nodes = node.cssselect("a")
        summary_nodes = node.cssselect("p.summary")
        if not date_nodes or not link_nodes:
            continue
        try:
            published = dt.datetime.strptime(
                date_nodes[0].text_content().strip(), "%m/%d/%Y"
            ).date()
        except ValueError:
            continue
        if published < since:
            continue
        title = link_nodes[0].text_content().strip()
        href = link_nodes[0].get("href", "")
        summary = summary_nodes[0].text_content().strip() if summary_nodes else ""
        items.append(
            RawItem(
                source="state_dol_scrape",
                source_ref=f"CA-DIR-{href}",
                raw_text=f"{title}\n\n{summary}",
                published_date=published,
            )
        )
    return items


STATE_FETCHERS = {
    "CA": fetch_california_items,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_state_dol.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/compliance/sources/state_dol.py backend/tests/compliance/test_state_dol.py
git commit -m "feat(compliance): add California DOL news-page scraper"
```

---

### Task 5: Ingestion orchestrator with dedup

**Files:**
- Create: `backend/compliance/ingest.py`
- Test: `backend/tests/compliance/test_ingest.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/compliance/test_ingest.py`:
```python
import datetime as dt

import pytest

from compliance.db import make_engine, get_session
from compliance.ingest import _write_new_items
from compliance.models import RegulatoryItem
from compliance.sources.federal_register import RawItem


@pytest.fixture
def session():
    engine = make_engine("sqlite:///:memory:")
    return get_session(engine)


def test_write_new_items_writes_new_and_skips_duplicates(session):
    session.add(RegulatoryItem(
        source="federal_register", source_ref="2026-001", raw_text="existing",
        published_date=dt.date(2026, 1, 1),
    ))
    session.commit()

    raw_items = [
        RawItem(source="federal_register", source_ref="2026-001", raw_text="dup", published_date=dt.date(2026, 1, 1)),
        RawItem(source="federal_register", source_ref="2026-002", raw_text="new item", published_date=dt.date(2026, 7, 1)),
    ]

    written = _write_new_items(session, raw_items)

    assert written == 1
    all_items = session.query(RegulatoryItem).all()
    assert len(all_items) == 2
    new_item = session.query(RegulatoryItem).filter_by(source_ref="2026-002").one()
    assert new_item.raw_text == "new item"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'compliance.ingest'`

- [ ] **Step 3: Write the orchestrator**

`backend/compliance/ingest.py`:
```python
"""Orchestrates fetching from all source types and writing new,
deduplicated RegulatoryItem rows to the database. Dedup is enforced at the
database level via the (source, source_ref) unique constraint on
RegulatoryItem (see models.py) — this module skips items that would
violate it rather than crashing the whole run on the first duplicate.
"""
from __future__ import annotations

import datetime as dt

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.models import RegulatoryItem
from compliance.sources.federal_register import fetch_federal_register_items, RawItem
from compliance.sources.legiscan import fetch_legiscan_items
from compliance.sources.state_dol import STATE_FETCHERS

# The states with live scrapers (state_dol.STATE_FETCHERS) plus the states
# LegiScan is queried for. Kept as one small, extensible list for now —
# Plan 1 deliberately scopes to a few states rather than all 50; see
# docs/superpowers/specs/2026-07-04-compliance-tracker-design.md.
TRACKED_STATES = ["CA"]


async def _fetch_all_raw_items(
    client: httpx.AsyncClient, since: dt.date
) -> list[RawItem]:
    """Fetch from every source, tolerating individual source failures (each
    fetch function already returns [] on its own errors)."""
    items: list[RawItem] = list(await fetch_federal_register_items(client, since))
    for state in TRACKED_STATES:
        items.extend(await fetch_legiscan_items(client, state, since))
        state_fetcher = STATE_FETCHERS.get(state)
        if state_fetcher is not None:
            items.extend(await state_fetcher(client, since))
    return items


def _write_new_items(session: Session, raw_items: list[RawItem]) -> int:
    """Write raw items to the database, skipping ones that already exist
    (same source + source_ref). Returns the count of new items written."""
    written = 0
    for raw in raw_items:
        exists = (
            session.query(RegulatoryItem)
            .filter_by(source=raw.source, source_ref=raw.source_ref)
            .first()
        )
        if exists is not None:
            continue
        session.add(
            RegulatoryItem(
                source=raw.source,
                source_ref=raw.source_ref,
                raw_text=raw.raw_text,
                published_date=raw.published_date,
            )
        )
        try:
            session.commit()
            written += 1
        except IntegrityError:
            # Race with another writer inserting the same source_ref between
            # our existence check and our commit — the row already exists.
            session.rollback()
    return written


async def ingest_all(session: Session, since: dt.date) -> int:
    """Fetch from all sources and write new items to the database. Returns
    the number of new items written."""
    async with httpx.AsyncClient() as client:
        raw_items = await _fetch_all_raw_items(client, since)
    return _write_new_items(session, raw_items)
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_ingest.py -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/compliance/ingest.py backend/tests/compliance/test_ingest.py
git commit -m "feat(compliance): add ingestion orchestrator with dedup"
```

---

### Task 6: Stage 1 LLM tagging

**Files:**
- Create: `backend/compliance/tagging.py`
- Test: `backend/tests/compliance/test_tagging.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/compliance/test_tagging.py`:
```python
import asyncio
import datetime as dt

import httpx

from compliance.tagging import tag_item, _parse_tag_response


def test_parse_tag_response_valid_json():
    raw = '[{"jurisdiction": "CA", "topic": "minimum_wage", "headcount_threshold": null, "effective_date": "2027-01-01", "confidence": 0.95}]'
    tags = _parse_tag_response(raw)

    assert len(tags) == 1
    assert tags[0]["jurisdiction"] == "CA"
    assert tags[0]["topic"] == "minimum_wage"
    assert tags[0]["effective_date"] == dt.date(2027, 1, 1)
    assert tags[0]["confidence"] == 0.95


def test_parse_tag_response_empty_list():
    assert _parse_tag_response("[]") == []


def test_parse_tag_response_rejects_invalid_topic():
    raw = '[{"jurisdiction": "CA", "topic": "not_a_real_topic", "confidence": 0.9}]'
    assert _parse_tag_response(raw) == []


def test_parse_tag_response_handles_malformed_json():
    assert _parse_tag_response("not json at all") == []


def test_tag_item_calls_anthropic_and_parses_result(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": '[{"jurisdiction": "US", "topic": "paid_sick_leave", "headcount_threshold": 50, "effective_date": null, "confidence": 0.8}]',
                    }
                ]
            },
        )

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await tag_item(client, item_id=1, raw_text="Some bill text about sick leave.")

    tags = asyncio.run(run())

    assert len(tags) == 1
    assert tags[0]["jurisdiction"] == "US"
    assert tags[0]["headcount_threshold"] == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_tagging.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'compliance.tagging'`

- [ ] **Step 3: Write the tagger**

`backend/compliance/tagging.py`:
```python
"""Stage 1 classification: reads a RegulatoryItem's raw text and produces
zero or more ItemTag rows describing which jurisdiction/topic/threshold it
applies to. Runs once per item, independent of any customer — see
docs/superpowers/specs/2026-07-04-compliance-tracker-design.md.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import httpx

from compliance.models import VALID_TOPICS

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
TAGGING_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-fable-5")

_TAGGING_SYSTEM_PROMPT = """You classify US labor-law regulatory text for a
compliance-alert product aimed at small businesses (5-50 employees).

Given the text of a bill, regulation, or agency announcement, identify
every distinct (jurisdiction, topic) combination it establishes or changes.
Valid topics are exactly: minimum_wage, paid_sick_leave, pay_transparency,
final_paycheck, other. Use "other" only when the text is genuinely
labor-law related but doesn't fit the other four categories — if the text
isn't about labor law affecting employers at all, return an empty list.

Respond with ONLY a JSON array, no other text. Each element:
{
  "jurisdiction": "<state code, or 'US' for federal, or 'City, ST' for a local ordinance>",
  "topic": "<one of the five valid topics>",
  "headcount_threshold": <integer or null, if the rule only applies above/below a specific employee count>,
  "effective_date": "<YYYY-MM-DD or null if not stated>",
  "confidence": <float 0.0-1.0, your own confidence this tag is correct>
}

If nothing in the text is relevant, respond with exactly: []
"""


async def tag_item(
    client: httpx.AsyncClient, item_id: int, raw_text: str
) -> list[dict]:
    """Classify one item's raw text. Returns a list of tag dicts (matching
    the ItemTag fields, minus item_id which the caller attaches). Returns an
    empty list if the API call fails or the response can't be parsed —
    callers should treat this as "tagging failed, retry later", not
    "confirmed no tags apply"."""
    api_key = os.environ["ANTHROPIC_API_KEY"]
    body = {
        "model": TAGGING_MODEL,
        "max_tokens": 1024,
        "system": _TAGGING_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": [{"type": "text", "text": raw_text}]}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    try:
        resp = await client.post(ANTHROPIC_API_URL, json=body, headers=headers, timeout=60.0)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        return []

    data = resp.json()
    text_parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    raw_response = "".join(text_parts).strip()
    return _parse_tag_response(raw_response)


def _parse_tag_response(raw_response: str) -> list[dict]:
    """Pure parsing/validation function, separated from the network call so
    it can be unit-tested against canned LLM output without mocking HTTP."""
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []

    tags: list[dict] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        topic = entry.get("topic")
        jurisdiction = entry.get("jurisdiction")
        confidence = entry.get("confidence")
        if topic not in VALID_TOPICS or not jurisdiction or not isinstance(confidence, (int, float)):
            continue
        effective_date = None
        if entry.get("effective_date"):
            try:
                effective_date = dt.date.fromisoformat(entry["effective_date"])
            except ValueError:
                effective_date = None
        tags.append({
            "jurisdiction": jurisdiction,
            "topic": topic,
            "headcount_threshold": entry.get("headcount_threshold"),
            "effective_date": effective_date,
            "confidence": float(confidence),
        })
    return tags
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `backend/`): `python3 -m pytest tests/compliance/test_tagging.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/compliance/tagging.py backend/tests/compliance/test_tagging.py
git commit -m "feat(compliance): add Stage 1 LLM tagging"
```

---

### Task 7: Golden-set evaluation harness

**Files:**
- Create: `backend/tests/compliance/golden_set.py`
- Create: `backend/tests/compliance/test_golden_set.py`
- Create: `backend/tests/__init__.py` (if it doesn't already exist)
- Create: `backend/tests/compliance/__init__.py`

- [ ] **Step 1: Check whether `backend/tests/__init__.py` already exists**

Run: `ls backend/tests/__init__.py 2>&1`

If it prints a path, skip creating it in Step 2 below (some pytest setups
work fine without it — only add it if it's missing and the import in Step
4 fails without it).

- [ ] **Step 2: Create the compliance tests package init**

`backend/tests/compliance/__init__.py`:
```python
```

- [ ] **Step 3: Write the golden set fixture**

`backend/tests/compliance/golden_set.py`:
```python
"""A small, hand-curated set of real historical labor-law texts with
known-correct Stage 1 classifications, used to evaluate tagging accuracy
before trusting a prompt change in production. See
docs/superpowers/specs/2026-07-04-compliance-tracker-design.md, Testing
section. This is NOT a CI-run unit test fixture (it calls the real
Anthropic API and costs real money) — see test_golden_set.py for how it's
invoked manually.
"""
from __future__ import annotations

GOLDEN_SET = [
    {
        "raw_text": (
            "SB 3, Chapter 4 (2016): Effective January 1, 2027, the "
            "California minimum wage for all employers increases to "
            "$17.50 per hour."
        ),
        "expected_topics": {"minimum_wage"},
    },
    {
        "raw_text": (
            "AB 1522 requires all California employers to provide at "
            "least 24 hours (or three days) of paid sick leave per year "
            "to employees who work 30 or more days within a year."
        ),
        "expected_topics": {"paid_sick_leave"},
    },
    {
        "raw_text": (
            "This press release announces the opening of a new state "
            "park visitor center in Sacramento."
        ),
        "expected_topics": set(),
    },
]
```

- [ ] **Step 4: Write the evaluation script**

`backend/tests/compliance/test_golden_set.py`:
```python
"""Evaluates the Stage 1 tagger's accuracy against golden_set.GOLDEN_SET.
Not run as part of the normal `pytest` suite (it calls the real Anthropic
API and costs real money) — run manually via:

    python3 -m tests.compliance.test_golden_set

whenever the tagging prompt changes, before trusting it in production.
"""
from __future__ import annotations

import asyncio

import httpx

from compliance.tagging import tag_item
from tests.compliance.golden_set import GOLDEN_SET


async def _evaluate() -> None:
    correct = 0
    async with httpx.AsyncClient() as client:
        for i, case in enumerate(GOLDEN_SET):
            tags = await tag_item(client, item_id=i, raw_text=case["raw_text"])
            got_topics = {t["topic"] for t in tags}
            match = got_topics == case["expected_topics"]
            correct += int(match)
            status = "PASS" if match else "FAIL"
            print(f"[{status}] case {i}: expected {case['expected_topics']}, got {got_topics}")

    print(f"\n{correct}/{len(GOLDEN_SET)} correct")


if __name__ == "__main__":
    asyncio.run(_evaluate())
```

- [ ] **Step 5: Run pytest to confirm this file doesn't break the normal suite**

Run (from `backend/`): `python3 -m pytest tests/compliance/ -v`
Expected: all tests from Tasks 1-6 still pass; `test_golden_set.py` contains
no `test_*` functions itself (only the `_evaluate` helper and a
`__main__` guard), so pytest collects it without running anything from it.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/compliance/golden_set.py backend/tests/compliance/test_golden_set.py backend/tests/compliance/__init__.py
git commit -m "feat(compliance): add golden-set tagging accuracy evaluation script"
```

---

### Task 8: Modal cron wiring

**Files:**
- Create: `backend/compliance/cron.py`

- [ ] **Step 1: Write the cron app**

`backend/compliance/cron.py`:
```python
"""Modal app + scheduled function for the compliance tracker's daily
ingestion + Stage 1 tagging run. Deploy with:

    modal deploy compliance/cron.py

Requires three Modal secrets to exist first:
    modal secret create anthropic-secret ANTHROPIC_API_KEY=...
    modal secret create compliance-db DATABASE_URL=...
    modal secret create legiscan-secret LEGISCAN_API_KEY=...
"""
from __future__ import annotations

import datetime as dt

import modal

app = modal.App("purplelink-compliance-tracker")

anthropic_secret = modal.Secret.from_name("anthropic-secret")
compliance_db_secret = modal.Secret.from_name("compliance-db")
legiscan_secret = modal.Secret.from_name("legiscan-secret")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("httpx", "sqlalchemy", "psycopg[binary]", "lxml", "cssselect")
    .add_local_python_source("compliance")
)


@app.function(
    image=image,
    schedule=modal.Cron("0 12 * * *"),  # daily, noon UTC
    timeout=600,
    secrets=[anthropic_secret, compliance_db_secret, legiscan_secret],
)
def daily_ingest_and_tag() -> None:
    import asyncio

    import httpx

    from compliance.db import make_engine, get_session
    from compliance.ingest import ingest_all
    from compliance.models import ItemTag, RegulatoryItem
    from compliance.tagging import tag_item

    engine = make_engine()
    session = get_session(engine)

    since = dt.date.today() - dt.timedelta(days=2)  # small overlap window
    written = asyncio.run(ingest_all(session, since))
    print(f"Ingested {written} new items")

    untagged = (
        session.query(RegulatoryItem)
        .outerjoin(ItemTag)
        .filter(ItemTag.id.is_(None))
        .all()
    )

    async def tag_all() -> None:
        async with httpx.AsyncClient() as client:
            for item in untagged:
                tags = await tag_item(client, item.id, item.raw_text)
                for tag in tags:
                    session.add(ItemTag(item_id=item.id, **tag))
                session.commit()

    asyncio.run(tag_all())
    print(f"Tagged {len(untagged)} items")


if __name__ == "__main__":
    daily_ingest_and_tag.local()
```

- [ ] **Step 2: Verify the module imports cleanly**

Run (from `backend/`): `python3 -c "import compliance.cron"`
Expected: no output, exit code 0 (confirms no syntax errors and that
`modal` is importable in the local dev environment — it should already be,
since the rest of Purplelink's backend uses it).

- [ ] **Step 3: Commit**

```bash
git add backend/compliance/cron.py
git commit -m "feat(compliance): wire daily ingestion + tagging into a Modal cron job"
```

---

## What This Plan Does Not Cover

Per the design spec's decomposition into three plans:
- Customer profiles, Stage 2 matching, and alert generation (Plan 2).
- Email delivery, the authenticated dashboard, and Stripe billing (Plan 3).
- Expanding `TRACKED_STATES` beyond California, and `LABOR_RELEVANT_AGENCIES`
  tuning — an ongoing content-ops task once real ingested data is visible,
  not a one-time build task.
- Actually creating the `compliance-db` Postgres instance and the three
  Modal secrets referenced in Task 8 — those are manual, one-time
  operator setup steps (creating a Neon database, running `modal secret
  create`), not code.
- The design spec's "silent scraper breakage" monitoring (alerting the
  operator when a source's daily item count deviates from its historical
  baseline) is deliberately not built in this plan: a baseline is only
  meaningful after this pipeline has actually run for a couple of weeks
  and produced real history to compare against. Add it as a small follow-up
  task once `daily_ingest_and_tag` has real run history in the database —
  building it against zero historical data now would just be guessed
  thresholds, not a real safety net.
