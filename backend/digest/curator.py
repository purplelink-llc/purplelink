# backend/digest/curator.py
"""Curation layer: Claude scores and selects items, writes editorial notes.

One call per run. Input: list[RawItem]. Output: DigestData or None if
fewer than MIN_ITEMS_TO_PUBLISH items are available.
"""
from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass
from typing import Optional

from digest._http import anthropic_message, parse_json
from digest.harvester import RawItem

logger = logging.getLogger(__name__)

MIN_ITEMS_TO_PUBLISH = 5

# Max items per category passed to Claude. Prevents context-window saturation
# (781 raw items → attention degrades; ~100 curated candidates → better picks).
_INPUT_CAP_PER_CATEGORY = 18

SECTION_CAPS: dict[str, int] = {
    "papers":         6,
    "ai_tech":        5,
    "cybersecurity":  4,
    "finance":        3,
    "entrepreneurship": 3,
    "general_tech":   2,
}

_SECTION_LABELS: dict[str, str] = {
    "papers":          "Papers & Research",
    "ai_tech":         "AI & Technology",
    "cybersecurity":   "Cybersecurity",
    "finance":         "Finance & Business",
    "entrepreneurship": "Entrepreneurship",
    "general_tech":    "Worth Reading",
}

BEN_PROFILE = """
Benjamin Ampel is a PhD-level researcher in cybersecurity, AI, and Information
Systems based in Atlanta, GA. He runs Purplelink LLC, a one-person macOS/iOS
software studio. Research focus: LLMs applied to cybersecurity, adversarial ML,
dark web intelligence, cyber threat detection, and information systems. Side
interests: AI/ML tooling and inference infrastructure, startup/indie hacking on
Apple platforms, quantitative finance and macro trends, and the business of
academic publishing. Prefers novel findings over incremental work, practical
implications over pure theory, papers with reproducible results or strong
empirical evidence, and well-argued contrarian takes. Skeptical of hype; values
specificity. Already reads widely in these areas, so novelty and non-obviousness
matter more than topic relevance alone.
""".strip()

_SYSTEM = f"""You are the curator of a daily digest for one reader:

{BEN_PROFILE}

Your job: select the most valuable items and write an editorial note for each.
Optimize for novelty and non-obviousness — things this reader probably has NOT
already seen. Skip surveys, literature reviews, and incremental "we fine-tuned
GPT on X dataset" papers unless the dataset itself is exceptional.

VOICE — strict rules, no exceptions:
- Write in third person. Never use "you" or "your". Address the reader as a
  technically sophisticated peer: "Security defenders building triage pipelines
  will care because..." not "This matters to you because..."
- Be specific: cite numbers, method names, dataset sizes, threat actors, tickers
- Lead with the finding or implication, not the methodology
- Short sentences. Active voice. No filler.
- NEVER use: "this paper explores", "the authors demonstrate", "the study shows",
  "the research examines", "delves into", "groundbreaking", "comprehensive",
  "novel approach", "leveraging", "utilizing", "in conclusion", "notably"
- Do NOT summarize the abstract — add a perspective the abstract doesn't give
- Do not use em-dashes

EDITORIAL NOTE format (2-3 sentences):
  Sentence 1: The specific finding, result, or claim (with numbers if available)
  Sentence 2: Why it matters and what's surprising or non-obvious
  Sentence 3 (optional): A caveat, limitation, or a specific follow-on question
  If two selected items are directly related (same threat actor, technology, or
  event), end the second item's note with: "Connects to: [first item title]."

AI TECH SELECTION — aim to include 2-3 items when strong content exists:
  Prefer: technical posts from Anthropic/OpenAI/DeepMind/Mistral on model
  capabilities, inference techniques, or safety findings; TLDR AI items on
  significant benchmark results or infrastructure shifts; HuggingFace/The
  Gradient posts with specific empirical findings.
  Reject: press releases without technical substance, "AI is transforming X"
  think-pieces, incremental model version announcements with no new capability.

FINANCE SELECTION — strict bar, reject noise:
  Only include items with a direct, specific connection to AI infrastructure
  economics, cybersecurity market dynamics, software-startup mechanics, or
  quantitative methods with reproducible signals.
  Reject: generic macro commentary, IPO market predictions, crypto price action,
  earnings summaries, market crash takes, and anything that reads like Bloomberg
  opinion. Ask: would a PhD researcher in cybersecurity or AI learn something
  operationally or strategically specific from this? If no, skip it.

INTRO format (1-2 sentences, 100-140 characters ideal for SEO):
  State what's actually in today's digest — specific topics, not a meta-comment
  about the feed quality. Write in third person. Include searchable terms
  (e.g., "LLM red-teaming", "ransomware", "AI chip export controls", "SBIR").
  Do NOT write "Today's digest covers..." or "A mix of..." or reference the feed.

Section caps (hard limits):
- papers: {SECTION_CAPS["papers"]}
- ai_tech: {SECTION_CAPS["ai_tech"]}
- cybersecurity: {SECTION_CAPS["cybersecurity"]}
- finance: {SECTION_CAPS["finance"]}
- entrepreneurship: {SECTION_CAPS["entrepreneurship"]}
- general_tech: {SECTION_CAPS["general_tech"]}

Return ONLY valid JSON, no prose before or after:
{{
  "intro": "<1-2 sentences, specific, SEO-friendly, third person>",
  "items": [
    {{
      "title": "<original title>",
      "url": "<original url>",
      "source_name": "<source name>",
      "category": "<papers|ai_tech|cybersecurity|finance|entrepreneurship|general_tech>",
      "editorial_note": "<2-3 sentences per the format above>"
    }}
  ]
}}"""


@dataclass
class DigestItem:
    title: str
    url: str
    source_name: str
    category: str
    editorial_note: str


@dataclass
class DigestData:
    date: datetime.date
    number: int
    intro: str
    sections: dict[str, list[DigestItem]]
    sources_reviewed: int
    items_selected: int


def _prefilter(items: list[RawItem]) -> list[RawItem]:
    """Reduce candidate pool before the LLM call.

    Passes at most _INPUT_CAP_PER_CATEGORY items per category to Claude,
    sorted by recency. This prevents context-window saturation (781 raw items
    degrade attention quality) while keeping the full freshness signal.
    """
    from collections import defaultdict
    buckets: dict[str, list[RawItem]] = defaultdict(list)
    for it in items:
        buckets[it.category].append(it)
    result: list[RawItem] = []
    for cat, cat_items in buckets.items():
        cat_items.sort(key=lambda x: x.published_at, reverse=True)
        result.extend(cat_items[:_INPUT_CAP_PER_CATEGORY])
    logger.info("prefilter: %d -> %d items (%d categories)",
                len(items), len(result), len(buckets))
    return result


async def curate(client, items: list[RawItem]) -> Optional[DigestData]:
    """Run curation. Returns None if too few input items to bother calling LLM."""
    if len(items) < MIN_ITEMS_TO_PUBLISH:
        logger.warning("curate: only %d items, below minimum %d — aborting",
                       len(items), MIN_ITEMS_TO_PUBLISH)
        return None

    candidates = _prefilter(items)

    item_list = [
        {
            "title": it.title,
            "url": it.url,
            "source_name": it.source_name,
            "category": it.category,
            "snippet": it.snippet[:300],
        }
        for it in candidates
    ]

    raw = await anthropic_message(
        client,
        system=_SYSTEM,
        user_content=[{"type": "text", "text": json.dumps(item_list)}],
        max_tokens=4096,
    )

    try:
        data = parse_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("curate: failed to parse Claude response: %s\n%s", exc, raw[:500])
        return None

    counts: dict[str, int] = {k: 0 for k in SECTION_CAPS}
    sections: dict[str, list[DigestItem]] = {label: [] for label in _SECTION_LABELS.values()}

    for raw_item in data.get("items", []):
        cat = raw_item.get("category", "general_tech")
        cap = SECTION_CAPS.get(cat, 2)
        if counts.get(cat, 0) >= cap:
            continue
        label = _SECTION_LABELS.get(cat, "Worth Reading")
        sections[label].append(DigestItem(
            title=raw_item.get("title", ""),
            url=raw_item.get("url", ""),
            source_name=raw_item.get("source_name", ""),
            category=cat,
            editorial_note=raw_item.get("editorial_note", ""),
        ))
        counts[cat] = counts.get(cat, 0) + 1

    sections = {k: v for k, v in sections.items() if v}
    total = sum(len(v) for v in sections.values())

    return DigestData(
        date=datetime.date.today(),
        number=0,  # publisher fills this in after counting existing digests
        intro=data.get("intro", ""),
        sections=sections,
        sources_reviewed=len(items),
        items_selected=total,
    )
