"""Read the month's weekly research roundups out of a cloned site checkout.

The weekly pipeline (research_digest) publishes one post per week into the
site repo: a manifest at ``research/index.json`` plus one
``research/<slug>/index.html`` per roundup. This module selects the roundups
whose publish date falls in a given ``YYYY-MM`` month and renders each into a
compact plain-text block (paper title, journal/meta, source link, abstract
summary, and "why it matters") that the monthly synthesizer draws from.

These roundups are ALREADY citation-vetted by the weekly pipeline's curator,
so the monthly guide synthesizes only from them; it does not fetch or invent
new papers.
"""
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field

MANIFEST_REL = "research/index.json"


@dataclass
class RoundupPaper:
    title: str
    url: str
    meta: str          # e.g. "BMJ (Clinical research ed.) · 2026-07-08 · Nong K et al."
    summary: str       # abstract-derived plain-language summary
    why: str           # 1-2 sentences tying it to muscle-on-GLP-1 readers


@dataclass
class Roundup:
    slug: str
    week_label: str
    date: str          # YYYY-MM-DD
    dek: str = ""
    papers: list[RoundupPaper] = field(default_factory=list)

    def to_text(self) -> str:
        """Render this roundup as one plain-text block for the synthesizer."""
        lines = [f"# Weekly roundup: {self.week_label} (published {self.date})"]
        if self.dek:
            lines.append(self.dek)
        for p in self.papers:
            lines.append("")
            lines.append(f"Paper: {p.title}")
            if p.meta:
                lines.append(f"Journal/meta: {p.meta}")
            if p.url:
                lines.append(f"Link: {p.url}")
            if p.summary:
                lines.append(f"Summary: {p.summary}")
            if p.why:
                lines.append(f"Why it matters: {p.why}")
        return "\n".join(lines)


def _is_preprint(paper: "RoundupPaper") -> bool:
    """True if the roundup text flags this paper as a preprint / not yet
    peer-reviewed, so ``monthly_citation_block`` can label it the same way
    ``muscleonglp.sources.citation_block`` labels its ``[PREPRINT]`` entries."""
    blob = f"{paper.meta} {paper.summary} {paper.why}".lower()
    return "preprint" in blob or "not yet peer-reviewed" in blob or "not peer-reviewed" in blob


def assign_paper_keys(papers: list["RoundupPaper"]) -> list[tuple[str, "RoundupPaper"]]:
    """Assign each paper a STABLE citation key (``p1``, ``p2``, ...) in the
    order given. Roundups are gathered oldest-first and papers keep their
    in-document order, so the same month's papers always map to the same
    keys — re-runs are deterministic.

    Papers are de-duplicated first. A single paper is often covered by more
    than one weekly roundup (in August 2026, "Protecting Musculoskeletal
    Development ... in Adolescents on GLP-1" ran in both the 4th and the
    10th), and without this it was handed to the model twice under two keys.
    The synthesis then treated one paper as two independent sources and wrote
    that it "appeared in two roundups this month" as if that were corroborating
    evidence. De-duplicating by URL, falling back to title where a URL is
    missing, keeping first occurrence so ordering stays stable."""
    seen: set[str] = set()
    unique: list["RoundupPaper"] = []
    for p in papers:
        ident = (getattr(p, "url", "") or "").strip().lower() or (p.title or "").strip().lower()
        if ident and ident in seen:
            continue
        if ident:
            seen.add(ident)
        unique.append(p)
    return [(f"p{i}", p) for i, p in enumerate(unique, start=1)]


def monthly_citation_block(papers: list["RoundupPaper"]) -> str:
    """Render the month's papers as one approved-source block, in the SAME
    ``- (key) [PREPRINT] text [url]`` shape that
    ``muscleonglp.sources.citation_block`` produces, so the synthesis prompt
    and the red-team medical_safety pass share the exact same grounding text.
    """
    lines = []
    for key, p in assign_paper_keys(papers):
        prefix = "[PREPRINT] " if _is_preprint(p) else ""
        parts = [p.title]
        if p.meta:
            parts.append(p.meta)
        if p.summary:
            parts.append(p.summary)
        text = ". ".join(part for part in parts if part)
        url = f" [{p.url}]" if p.url else ""
        lines.append(f"- ({key}) {prefix}{text}{url}")
    return "\n".join(lines)


def _clean(fragment: str) -> str:
    """Strip HTML tags and normalize whitespace/entities in *fragment*."""
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


_ITEM_RE = re.compile(r'<article class="rr-item">(.*?)</article>', re.S)
# Stops at </a> rather than demanding </a></h2>. The roundup renderer puts a
# badge inside the heading for non-peer-reviewed sources —
# `<h2><a ...>Title</a> <span class="rr-preprint">Preprint</span></h2>` — so
# requiring the tags to be adjacent silently skipped EVERY preprint. Preprints
# are most of the weekly supply (3 of 4 papers in the 2026-07-27 roundup), so
# the monthly guide has been synthesized from a fraction of the month's
# evidence with no error to show for it. Those papers ARE labelled correctly
# once parsed: their rr-meta begins "Preprint · ...", which _is_preprint
# already detects, so monthly_citation_block still prefixes them [PREPRINT].
_TITLE_RE = re.compile(r'<h2><a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_META_RE = re.compile(r'<p class="rr-meta">(.*?)</p>', re.S)
_SUMMARY_RE = re.compile(r'</p>\s*<p>(.*?)</p>', re.S)
_WHY_RE = re.compile(r'<p class="rr-why">.*?</strong>\s*(.*?)</p>', re.S)
_DEK_RE = re.compile(r'<p class="article-dek">(.*?)</p>', re.S)


def parse_post_html(post_html: str) -> tuple[str, list[RoundupPaper]]:
    """Extract the dek and the per-paper items from a roundup post's HTML.

    Falls back to an empty paper list if the post predates the ``rr-item``
    markup; the synthesizer then simply has less to work with rather than
    crashing.
    """
    dek_m = _DEK_RE.search(post_html)
    dek = _clean(dek_m.group(1)) if dek_m else ""

    papers: list[RoundupPaper] = []
    for block in _ITEM_RE.findall(post_html):
        title_m = _TITLE_RE.search(block)
        if not title_m:
            continue
        url, title = title_m.group(1).strip(), _clean(title_m.group(2))
        meta_m = _META_RE.search(block)
        summary_m = _SUMMARY_RE.search(block)
        why_m = _WHY_RE.search(block)
        papers.append(
            RoundupPaper(
                title=title,
                url=url,
                meta=_clean(meta_m.group(1)) if meta_m else "",
                summary=_clean(summary_m.group(1)) if summary_m else "",
                why=_clean(why_m.group(1)) if why_m else "",
            )
        )
    return dek, papers


def gather_month_roundups(site_dir: str, year: int, month: int) -> list[Roundup]:
    """Return the roundups whose manifest ``date`` falls in *year*-*month*.

    Sorted oldest-first so the synthesized guide reads chronologically.
    Returns an empty list if the manifest is missing or nothing matches.
    """
    mpath = os.path.join(site_dir, MANIFEST_REL)
    if not os.path.exists(mpath):
        return []
    with open(mpath) as f:
        manifest = json.load(f)

    prefix = f"{year:04d}-{month:02d}"
    selected = [m for m in manifest if str(m.get("date", "")).startswith(prefix)]
    selected.sort(key=lambda m: m["date"])

    roundups: list[Roundup] = []
    for entry in selected:
        slug = entry["slug"]
        post_path = os.path.join(site_dir, "research", slug, "index.html")
        dek, papers = ("", [])
        if os.path.exists(post_path):
            with open(post_path) as f:
                dek, papers = parse_post_html(f.read())
        roundups.append(
            Roundup(
                slug=slug,
                week_label=entry.get("week_label", slug),
                date=entry["date"],
                dek=dek,
                papers=papers,
            )
        )
    return roundups
