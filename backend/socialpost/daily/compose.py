"""Deterministic post text: templates plus the page's own facts. No model, no paid API.

Four formats are rotated across days so they can be compared (the weekly report does that):
  card       image plus a short headline and the link
  link       the headline and the link, nothing else
  question   a question hook (fixed wording per kind), then the page's own description
  statement  a plain statement: the headline, then the page's own description

Voice (CLAUDE.md, .agents/product-marketing.md): calm, plain, specific. No em dashes, no emojis, no buzzwords.
Every sentence of description is copied from the page, never paraphrased, so the vetting gate can check it.
"""
from __future__ import annotations

import re

from ..spec import SPEC
from ..text import measure, utm_link

MAX_SENTENCE_WORDS = 30  # Ben-voice limit for Mastodon text (enforced again in vet.py)
FORMATS = ("card", "link", "question", "statement")

HEADLINE = {
    "release": "{title} is out.",
    "guide": "New guide: {title}",
    "blog": "New on the blog: {title}",
    "tool": "New tool: {title}",
    "video": "New video: {title}",
    "evergreen:guide": "From our guides: {title}",
    "evergreen:tool": "From our tools: {title}",
    "evergreen:blog": "From the blog: {title}",
}
QUESTION = {
    "release": "What changed in {title}?",
    "guide": "Looking for a plain answer? {title}",
    "blog": "Curious how this went? {title}",
    "tool": "Need this done quickly? {title}",
    "video": "Stuck on this? {title}",
    "evergreen:guide": "Still looking for this? {title}",
    "evergreen:tool": "Still looking for this? {title}",
    "evergreen:blog": "Still looking for this? {title}",
}
# Mastodon is written as Ben (first person, his `benampel` skill, tutorial register): one template per kind: the page
# title on its own line, then one plain declarative of about 15 to 19 words, no questions, no em dashes, contrast only with a sentence-initial "However"
# (none is needed here). The page's own description sentences follow, copied verbatim. The profile bio discloses AI help.
MASTODON = {
    "release": "{title}\n\nI shipped this release this week, and the changelog on the site lists every change in it.",
    "guide": "{title}\n\nI published this guide this week, and the link below goes to the full page.",
    "blog": "{title}\n\nI posted this write-up this week, and the full text is on the Purplelink blog.",
    "tool": "{title}\n\nI added this tool to the site this week, and you can open it from the link below.",
    "video": "{title}\n\nI uploaded this video this week, and the link below goes to it on YouTube.",
    "evergreen:guide": "{title}\n\nI wrote this guide earlier, and it is still one of the most read pages on the site.",
    "evergreen:tool": "{title}\n\nI built this tool earlier, and it is still one of the most used pages on the site.",
    "evergreen:blog": "{title}\n\nI wrote this post earlier, and it is still one of the most read pages on the site.",
}

# Every word the templates themselves introduce. The vetting gate lets these through and requires everything else
# that looks like a name or a number to appear in the page's own facts.
TEMPLATE_TEXT = " ".join(list(HEADLINE.values()) + list(QUESTION.values()) + list(MASTODON.values()) + ["Link:"])
TEMPLATE_VOCAB = {w.lower() for w in re.findall(r"[A-Za-z]+", TEMPLATE_TEXT)}


class ComposeError(Exception):
    """No wording fits the platform's limit."""


def _key(c) -> str:
    return f"evergreen:{c.page_kind}" if c.kind == "evergreen" else c.kind


def headline(c, facts: dict, fmt: str, platform: str = "") -> str:
    table = MASTODON if platform == "mastodon" else QUESTION if fmt == "question" else HEADLINE
    return table[_key(c)].format(title=facts["title"])


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", (text or "").strip())
    return [p.strip() for p in parts if len(p.split()) >= 6]


def description_for(facts: dict) -> list[str]:
    """The page's own sentences, best source first: the meta description, else the changelog entry."""
    return sentences(facts.get("description") or "") or sentences(facts.get("notes") or "")


def _bodies(c, facts: dict, fmt: str, platform: str) -> list[str]:
    """Candidate texts for a platform, richest first. `{link}` marks where the tagged link goes."""
    head = headline(c, facts, fmt, platform)
    if fmt in ("card", "link"):
        return [f"{head}\n\n{{link}}"]
    desc = description_for(facts)
    if platform == "mastodon":
        desc = [s for s in desc if len(s.split()) <= MAX_SENTENCE_WORDS and "?" not in s]
    out = []
    if platform == "linkedin":
        for n in (2, 1):
            if len(desc) >= n:
                out.append(f"{head}\n\n{' '.join(desc[:n])}\n\n{{link}}")
    elif platform == "mastodon":
        for n in (2, 1):
            if len(desc) >= n:
                out.append(f"{head}\n\n{' '.join(desc[:n])}\n\n{{link}}")
    else:
        for n in (2, 1):
            if len(desc) >= n:
                out.append(f"{head} {' '.join(desc[:n])}\n\n{{link}}")
    out.append(f"{head}\n\n{{link}}")
    return out


def render_preview(text: str, platform: str, link: str, campaign: str) -> str:
    return text.replace("{link}", utm_link(link, platform, campaign))


def compose(c, facts: dict, fmt: str, platforms: list[str], campaign: str) -> dict[str, str]:
    """{platform: text with {link}}. Takes the richest wording that fits each platform's limit."""
    out = {}
    for p in platforms:
        spec = SPEC[p]
        for body in _bodies(c, facts, fmt, p):
            rendered = render_preview(body, p, c.url, campaign)
            if measure(rendered, spec["count"]) <= spec["text"]:
                out[p] = body
                break
        else:
            raise ComposeError(f"{p}: even the shortest wording is over {spec['text']} {spec['count']}")
    return out
