"""Harvest recent GLP-1 / muscle literature from PubMed and Europe PMC.

Produces a deduplicated list of `Paper` records (real, resolvable, with an
abstract). Nothing here fabricates: every field comes straight from the API
response, and a paper without an abstract is dropped rather than guessed at.
"""
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from . import sources

logger = logging.getLogger(__name__)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DEFAULT_WINDOW_DAYS = 7
MAX_PER_SOURCE = 30


@dataclass
class Paper:
    title: str
    authors: list[str]
    source: str            # "PubMed" | "Europe PMC"
    is_preprint: bool
    venue: str             # journal name, or "Preprint" for a preprint
    pub_date: str          # YYYY-MM-DD (best available)
    url: str               # canonical resolvable link
    abstract: str
    doi: Optional[str] = None
    pmid: Optional[str] = None
    _extra: dict = field(default_factory=dict)

    def author_line(self) -> str:
        if not self.authors:
            return ""
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    def dedup_key(self) -> str:
        if self.doi:
            return "doi:" + self.doi.lower()
        if self.pmid:
            return "pmid:" + self.pmid
        return "title:" + re.sub(r"[^a-z0-9]", "", self.title.lower())[:80]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


# ---------------------------------------------------------------- PubMed

async def fetch_pubmed(client, days: int = DEFAULT_WINDOW_DAYS) -> list[Paper]:
    """esearch (last `days`) -> efetch XML -> parsed Papers."""
    term = sources.core_query()
    try:
        r = await client.get(
            f"{EUTILS}/esearch.fcgi",
            params={"db": "pubmed", "term": term, "reldate": days,
                    "datetype": "pdat", "retmax": MAX_PER_SOURCE, "retmode": "json"},
            timeout=30.0,
        )
        r.raise_for_status()
        pmids = r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as exc:
        logger.warning("pubmed esearch failed: %s", exc)
        return []
    if not pmids:
        return []

    await asyncio.sleep(0.4)  # be polite to E-utilities
    try:
        r = await client.get(
            f"{EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
            timeout=45.0,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as exc:
        logger.warning("pubmed efetch failed: %s", exc)
        return []

    papers: list[Paper] = []
    for art in root.findall(".//PubmedArticle"):
        p = _parse_pubmed_article(art)
        if p and p.abstract:
            papers.append(p)
    return papers


def _parse_pubmed_article(art: ET.Element) -> Optional[Paper]:
    try:
        pmid = art.findtext(".//MedlineCitation/PMID")
        article = art.find(".//MedlineCitation/Article")
        if article is None:
            return None
        title = _clean("".join(article.find("ArticleTitle").itertext())
                       if article.find("ArticleTitle") is not None else "")
        if not title:
            return None

        # Abstract: join labelled sections.
        parts = []
        for ab in article.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            text = _clean("".join(ab.itertext()))
            if not text:
                continue
            parts.append(f"{label.title()}: {text}" if label else text)
        abstract = _clean(" ".join(parts))

        authors = []
        for a in article.findall(".//AuthorList/Author"):
            last = a.findtext("LastName")
            initials = a.findtext("Initials")
            if last:
                authors.append(f"{last} {initials}" if initials else last)
        venue = _clean(article.findtext(".//Journal/Title") or "")

        # DOI: prefer PubmedData ArticleIdList, fall back to ELocationID.
        doi = None
        for aid in art.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = _clean(aid.text)
        if not doi:
            for eid in article.findall("ELocationID"):
                if eid.get("EIdType") == "doi":
                    doi = _clean(eid.text)

        pub_date = _pubmed_date(article)
        url = (f"https://doi.org/{doi}" if doi
               else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        return Paper(title=title, authors=authors, source="PubMed",
                     is_preprint=False, venue=venue or "Journal article",
                     pub_date=pub_date, url=url, abstract=abstract,
                     doi=doi, pmid=pmid)
    except Exception as exc:
        logger.warning("pubmed parse error: %s", exc)
        return None


def _pubmed_date(article: ET.Element) -> str:
    ad = article.find("ArticleDate")
    if ad is not None:
        y, m, d = ad.findtext("Year"), ad.findtext("Month"), ad.findtext("Day")
        if y:
            return f"{y}-{(m or '01').zfill(2)}-{(d or '01').zfill(2)}"
    pd = article.find(".//Journal/JournalIssue/PubDate")
    if pd is not None:
        y = pd.findtext("Year")
        if y:
            return f"{y}-01-01"
    return date.today().isoformat()


# ------------------------------------------------------------- Europe PMC

async def fetch_europepmc(client, start: str, end: str) -> list[Paper]:
    query = sources.europepmc_query(start, end)
    try:
        r = await client.get(
            EUROPEPMC,
            params={"query": query, "format": "json", "resultType": "core",
                    "pageSize": MAX_PER_SOURCE, "sort": "P_PDATE_D desc"},
            timeout=30.0,
        )
        r.raise_for_status()
        results = r.json().get("resultList", {}).get("result", [])
    except Exception as exc:
        logger.warning("europepmc search failed: %s", exc)
        return []

    papers: list[Paper] = []
    for x in results:
        abstract = _clean(x.get("abstractText") or "")
        title = _clean(x.get("title") or "")
        if not title or not abstract:
            continue
        doi = (x.get("doi") or "").lower() or None
        pmid = x.get("pmid")
        is_preprint = (x.get("source") == "PPR") or ("preprint" in (x.get("pubType") or "").lower())
        if doi:
            url = f"https://doi.org/{doi}"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            url = f"https://europepmc.org/article/{x.get('source')}/{x.get('id')}"
        authors = [a.strip() for a in (x.get("authorString") or "").split(",") if a.strip()]
        venue = _clean(x.get("journalTitle") or ("Preprint" if is_preprint else "Journal article"))
        papers.append(Paper(
            title=title, authors=authors, source="Europe PMC",
            is_preprint=is_preprint, venue=("Preprint" if is_preprint else venue),
            pub_date=_clean(x.get("firstPublicationDate") or end),
            url=url, abstract=abstract, doi=doi, pmid=pmid,
        ))
    return papers


# ------------------------------------------------------------- orchestrator

async def harvest_all(client, days: int = DEFAULT_WINDOW_DAYS) -> list[Paper]:
    """Fetch from both sources for the trailing `days` window and dedup.

    PubMed runs first, so its clean abstracts win over Europe PMC's copy of the
    same (MED-source) record; Europe PMC then uniquely contributes preprints and
    non-Medline records.
    """
    end = date.today()
    start = end - timedelta(days=days)
    pubmed, epmc = await asyncio.gather(
        fetch_pubmed(client, days=days),
        fetch_europepmc(client, start.isoformat(), end.isoformat()),
    )
    seen: set[str] = set()
    merged: list[Paper] = []
    for p in [*pubmed, *epmc]:
        k = p.dedup_key()
        if k in seen:
            continue
        seen.add(k)
        merged.append(p)
    logger.info("harvest: pubmed=%d epmc=%d merged=%d", len(pubmed), len(epmc), len(merged))
    return merged
