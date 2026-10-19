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
# Mastodon is written as Ben (first person, his `benampel` skill, tutorial register): the page title on its own line,
# one plain declarative of about 15 to 19 words that says what follows, then the page's own verified facts (sentences
# copied from the page, each under 31 words). Contrast would use a sentence-initial "However"; none is needed here.
# The profile bio discloses AI help.
MASTODON = {
    "release": "I shipped this release this week, and the first changes from the changelog are listed here.",
    "guide": "I published this guide this week, and the page opens with this short summary of what it covers.",
    "blog": "I posted this write-up this week, and the page opens with this short summary of what it covers.",
    "tool": "I added this tool to the site this week, and the page describes what it does in these words.",
    "video": "I uploaded this video this week, and its description says what it covers in these words.",
    "evergreen:guide": "I wrote this guide earlier, and it is still one of the most read pages on the site.",
    "evergreen:tool": "I built this tool earlier, and it is still one of the most used pages on the site.",
    "evergreen:blog": "I wrote this post earlier, and it is still one of the most read pages on the site.",
}
# Wording the fact lines add (sentences built from the page's own headings and step count).
FACT_TEMPLATES = ["It covers {a} and {b}.", "The page lays it out in {steps}."]

# Every word the templates themselves introduce. The vetting gate lets these through and requires everything else
# that looks like a name or a number to appear in the page's own facts.
TEMPLATE_TEXT = " ".join(list(HEADLINE.values()) + list(QUESTION.values()) + list(MASTODON.values()) + FACT_TEMPLATES + ["Link:"])
TEMPLATE_VOCAB = {w.lower() for w in re.findall(r"[A-Za-z]+", TEMPLATE_TEXT)}


class ComposeError(Exception):
    """No wording fits the platform's limit."""


def _key(c) -> str:
    return f"evergreen:{c.page_kind}" if c.kind == "evergreen" else c.kind


def headline(c, facts: dict, fmt: str, platform: str = "") -> str:
    if platform == "mastodon":
        return MASTODON[_key(c)].format(title=facts["title"]) if "{title}" in MASTODON[_key(c)] else \
            f"{facts['title']}\n\n{MASTODON[_key(c)]}"
    table = QUESTION if fmt == "question" else HEADLINE
    return table[_key(c)].format(title=facts["title"])


# Longest a post may be, a little under each platform's limit (LinkedIn is read as a short note).
SOFT_LIMIT = {"linkedin": 600, "bluesky": 300, "threads": 500, "mastodon": 500}
# A sentence that leans on the one before it ("Until then ...", "This also ...") is useless on its own.
DEPENDENT = re.compile(r"^(until|then|this|that|these|those|it|they|its|their|each|also|both|however|but|and|so|"
                       r"which|there|here|such|the same|in that|for that|after that)\b", re.I)
BOILERPLATE = ("earlier versions", "download it", "you can download", "check for updates", "install it through")


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", (text or "").strip())
    return [p.strip() for p in parts if len(p.split()) >= 5]


def lower_first(h: str) -> str:
    """'The ORCID export steps' -> 'the ORCID export steps' (a word with another capital, such as ORCID, stays)."""
    first = h.split(" ", 1)[0]
    return h if len(first) > 1 and any(ch.isupper() for ch in first[1:]) else h[:1].lower() + h[1:]


def fact_units(facts: dict, platform: str) -> list[str]:
    """Verified fact sentences for a post, best first: the page's own description (or, for a release, its changelog
    entry), then a line built from its section headings and one from a step count it states. Boilerplate such as
    'Earlier versions install ... through Check for Updates' is dropped."""
    base = sentences(facts.get("description") or "") or sentences(facts.get("notes") or "")
    base = [s for s in base if not any(b in s.lower() for b in BOILERPLATE) and not DEPENDENT.match(s)][:6]
    units = base[:3]
    heads = facts.get("headings") or []
    if len(heads) >= 2:
        units.append(FACT_TEMPLATES[0].format(a=lower_first(heads[0]), b=lower_first(heads[1])))
    if facts.get("steps"):
        units.append(FACT_TEMPLATES[1].format(steps=facts["steps"]))
    if platform == "mastodon":
        units = [u for u in units if len(u.split()) <= MAX_SENTENCE_WORDS and "?" not in u]
    return units


def description_for(facts: dict) -> list[str]:
    return fact_units(facts, "")


def clause(sentence: str) -> str | None:
    """The part of a long sentence before its first colon, as its own sentence (a verbatim prefix), if it is whole."""
    head, sep, _ = sentence.partition(": ")
    return head.rstrip(",;") + "." if sep and len(head.split()) >= 6 else None


def _options(units: list[str], fmt: str, platform: str = "") -> list[list[str]]:
    """Fact lists to try, richest first. card and link carry one fact (two on LinkedIn, which has no image);
    question and statement carry up to two. When the last sentence is too long, its clause before a colon is tried."""
    most = 2 if platform == "linkedin" or fmt not in ("card", "link") or \
        (units and len(units[0].split()) < 8) else 1       # a very short first fact ("New: Where your space went.") needs a second
    opts = []
    for k in range(min(most, len(units)), 0, -1):
        cut = clause(units[k - 1])
        if cut and len(units[k - 1]) > 220:                   # a long list sentence reads better as its lead clause
            opts.append(units[:k - 1] + [cut])
        opts.append(units[:k])
        if cut and len(units[k - 1]) <= 220:
            opts.append(units[:k - 1] + [cut])
    seen, out = set(), []
    for o in opts:
        if o and tuple(o) not in seen:
            seen.add(tuple(o))
            out.append(o)
    return out


def _body(c, facts: dict, fmt: str, platform: str, facts_used: list[str]) -> str:
    head = headline(c, facts, fmt, platform)
    text = " ".join(facts_used)
    if platform == "linkedin":
        return f"{head}\n\n{text}\n\n{{link}}"
    if platform == "mastodon":
        title, intro = head.split("\n\n", 1)
        return f"{title}\n\n{intro}\n\n{text}\n\n{{link}}"
    if head[-1] not in ".?!:":
        head += "."
    return f"{head} {text}\n\n{{link}}"


def render_preview(text: str, platform: str, link: str, campaign: str) -> str:
    return text.replace("{link}", utm_link(link, platform, campaign))


def compose(c, facts: dict, fmt: str, platforms: list[str], campaign: str) -> dict[str, str]:
    """{platform: text with {link}}; raises ComposeError if any platform cannot be served (see compose_best)."""
    out, bad = compose_best(c, facts, fmt, platforms, campaign)
    if bad:
        raise ComposeError("; ".join(bad.values()))
    return out


def title_is_a_fact(c, facts: dict) -> bool:
    """A guide, post, tool or video title says what the page is about; a release title is only 'Name 1.2.3'."""
    return c.kind != "release" and len(facts["title"].split()) >= 5


def compose_best(c, facts: dict, fmt: str, platforms: list[str], campaign: str):
    """({platform: text with {link}}, {platform: why not}). Every post carries at least one verified fact: sentences
    from the page's own description or changelog entry, its headings or a step count it states. When the room is
    too small for any sentence, a guide, post, tool or video may go out as its descriptive title plus the link
    (Mastodon never: its template needs a fact to introduce). The richest wording that fits wins."""
    out, bad = {}, {}
    for p in platforms:
        spec = SPEC[p]
        limit = min(spec["text"], SOFT_LIMIT.get(p, spec["text"]))
        units = fact_units(facts, p)
        for opt in _options(units, fmt, p):
            body = _body(c, facts, fmt, p, opt)
            if measure(render_preview(body, p, c.url, campaign), spec["count"]) <= limit:
                out[p] = body
                break
        else:
            if p != "mastodon" and title_is_a_fact(c, facts):
                body = _body(c, facts, fmt, p, [])
                body = body.replace("  ", " ").replace(" \n\n", "\n\n")
                if measure(render_preview(body, p, c.url, campaign), spec["count"]) <= limit:
                    out[p] = body
                    continue
            bad[p] = f"{p}: no verified fact fits within {limit} {spec['count']}" if units else \
                f"{p}: the page gives no verified fact sentence to use"
    return out, bad
