"""Pure logic for building .bib entries from DOIs and arXiv IDs.

Network calls (CrossRef transform, arXiv API) live in app.py.
This module handles classification and BibTeX formatting only.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

MAX_IDS = 50  # max entries per request

_DOI_RE = re.compile(r"^10\.\d{4,}/")
_ARXIV_BARE_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")

_URL_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "doi:",
    "DOI:",
)
_ARXIV_PREFIXES = (
    "https://arxiv.org/abs/",
    "http://arxiv.org/abs/",
    "arxiv.org/abs/",
    "arXiv:",
    "arxiv:",
)


def classify_id(raw: str) -> tuple[str, str]:
    """Classify and clean a raw ID string.

    Returns (type, cleaned) where type is "doi", "arxiv", or "unknown".
    """
    s = raw.strip()
    for p in _URL_PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break
    for p in _ARXIV_PREFIXES:
        if s.lower().startswith(p.lower()):
            s = s[len(p):]
            break

    if _DOI_RE.match(s):
        return ("doi", s)
    if _ARXIV_BARE_RE.match(s):
        return ("arxiv", s.split("v")[0])  # strip version suffix
    return ("unknown", s)


def parse_ids(text: str) -> list[tuple[str, str]]:
    """Parse a newline/comma-separated block of IDs.

    Returns list of (type, cleaned_id), capped at MAX_IDS, skipping blanks
    and unknowns.
    """
    if len(text) > 10_000:
        text = text[:10_000]
    raw_ids = re.split(r"[\n,]+", text)
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in raw_ids:
        raw = raw.strip()
        if not raw:
            continue
        kind, clean = classify_id(raw)
        if kind == "unknown":
            continue
        if clean not in seen:
            seen.add(clean)
            results.append((kind, clean))
        if len(results) >= MAX_IDS:
            break
    return results


def format_arxiv_bib(arxiv_id: str, feed_xml: str) -> str | None:
    """Parse an arXiv Atom feed and format as a BibTeX @misc entry.

    Returns None if the feed has no entries (ID not found).
    """
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    try:
        root = ET.fromstring(feed_xml)
    except ET.ParseError:
        return None

    entries = root.findall("atom:entry", ns)
    if not entries:
        return None
    entry = entries[0]

    # If arXiv returns an error entry (title contains "Error") skip it
    title_text = (entry.findtext("atom:title", "", ns) or "").strip()
    if title_text.lower() == "error":
        return None
    title = " ".join(title_text.split())

    authors = entry.findall("atom:author", ns)
    author_parts: list[str] = []
    for a in authors:
        name = (a.findtext("atom:name", "", ns) or "").strip()
        if name:
            tokens = name.rsplit(" ", 1)
            author_parts.append(f"{tokens[1]}, {tokens[0]}" if len(tokens) == 2 else name)
    author_str = " and ".join(author_parts)

    year = (entry.findtext("atom:published", "", ns) or "")[:4]

    primary = entry.find("arxiv:primary_category", ns)
    category = primary.get("term", "") if primary is not None else ""

    # Build a safe BibTeX key from the ID
    bib_key = "arxiv" + arxiv_id.replace(".", "_")

    lines = [
        f"@misc{{{bib_key},",
        f"  author        = {{{author_str}}},",
        f"  title         = {{{{{title}}}}},",
        f"  year          = {{{year}}},",
        f"  eprint        = {{{arxiv_id}}},",
        f"  archivePrefix = {{arXiv}},",
    ]
    if category:
        lines.append(f"  primaryClass  = {{{category}}},")
    lines.append(f"  url           = {{https://arxiv.org/abs/{arxiv_id}}}")
    lines.append("}")
    return "\n".join(lines)


def bib_key_from_crossref(bib_snippet: str) -> str:
    """Extract the BibTeX key from a CrossRef-returned snippet."""
    m = re.search(r"@\w+\{([^,\s]+)", bib_snippet)
    return m.group(1) if m else "unknown"
