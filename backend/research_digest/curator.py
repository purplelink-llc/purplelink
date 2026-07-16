"""Curate harvested papers into a weekly digest via a single LLM pass.

The model rates each paper's relevance to a muscle-on-GLP-1 audience, writes a
conservative plain-language summary drawn ONLY from the abstract, and drafts a
short editor's intro. Accuracy guardrails live in the system prompt; the code
enforces the structural rules (relevance threshold, minimum items, no item that
the harvester did not actually return).
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Optional

from ._http import anthropic_message, parse_json
from .harvester import Paper
from .models import DigestItem, WeeklyDigest

logger = logging.getLogger(__name__)

MIN_RELEVANCE = 2
MIN_ITEMS = 2
MAX_ITEMS = 8

# The model habitually ends a "why it matters" sentence with a trailing clause
# that just restates reader-relevance ("..., a key concern for this readership").
# It adds nothing, so drop that final clause and end the sentence before it. Only
# fires when the trailing clause names the audience, so a substantive why is never
# truncated. Matches a comma / em-dash / double-hyphen lead-in.
_READER_TAIL = re.compile(
    r"\s*(?:[,—]|--)"                      # separator: comma, em-dash, or --
    r"[^,—]*?\b(?:readership|readers|this\s+population|this\s+audience"
    r"|this\s+cohort|this\s+group|these\s+patients|this\s+site"
    r"|mission\s+of\s+this\s+site|muscle-preservation\s+mission)\b[^,—]*?[.\s]*$",
    re.IGNORECASE,
)


def _trim_reader_tail(text: str) -> str:
    """Strip a trailing reader-relevance clause from a 'why it matters' sentence."""
    text = (text or "").strip()
    trimmed = _READER_TAIL.sub("", text).rstrip()
    if not trimmed:
        return text  # never blank out the whole sentence
    if trimmed[-1] not in ".!?":
        trimmed += "."
    return trimmed


# The "action" field is the one place this pipeline is allowed to sound even
# slightly prescriptive, so it gets a closed vocabulary (four general, already-
# published, non-paper-specific levers) instead of free text, plus a hard ban
# filter below. If the model drifts into real medical advice — a dose, a drug
# switch, an imperative command — the finding is DROPPED (action="", never
# silently rewritten), the same "hold, don't launder" approach as the rest of
# this file. A paper that doesn't cleanly fit one of the four gets no action
# line; forcing one onto a pure mechanism/drug-comparison paper would be either
# filler or an invented recommendation, both against the IRON RULES.
ACTION_CATEGORIES = (
    "protein: a general nudge toward hitting a daily protein target",
    "training: a general nudge toward resistance/strength training",
    "monitor: a general nudge to track strength/lean mass or watch for signs of "
    "muscle loss over time",
    "clinician: a general nudge to discuss the finding with a prescribing "
    "clinician (never a specific dose or drug change)",
)

_ACTION_BAN = re.compile(
    r"\byou should\b|\bstart taking\b|\bstop taking\b|\b(increase|decrease|lower|"
    r"raise)\s+(your\s+)?dose\b|\bswitch\s+(to|from)\b.*\b(semaglutide|tirzepatide|"
    r"ozempic|wegovy|mounjaro|zepbound)\b|\bmg\b|\bmilligrams?\b|^(take|start|stop|"
    r"increase|decrease|ask|request)\b",
    re.IGNORECASE,
)


def _clean_action(text: str) -> str:
    """Return the action sentence unchanged, or '' if it reads as prescriptive
    (a dose, a drug switch, an imperative command) rather than a general nudge."""
    text = (text or "").strip()
    if not text or _ACTION_BAN.search(text):
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text

SYSTEM = """You are a careful scientific-literature editor for MuscleOnGLP, a site \
for people preserving muscle and lean mass while losing weight on GLP-1 medications \
(semaglutide/Ozempic/Wegovy, tirzepatide/Mounjaro/Zepbound).

Your job: from a list of recent papers (title + abstract only), select the ones \
relevant to our readers and summarize them.

IRON RULES:
- Use ONLY information stated in the provided abstract. Never add a number, finding, \
population, or conclusion that is not in the abstract. If the abstract does not give \
a number, do not invent one.
- Be conservative and neutral. No medical advice, no dosing, no recommendations. \
Describe what the study found, not what the reader should do.
- If a paper is a preprint, a protocol, a small study, an animal/cell study, or a \
narrative review, note that framing plainly in the summary.
- Relevance is to MUSCLE / lean mass / body composition / protein / resistance \
training / physical function in the context of GLP-1 weight-loss medication. A paper \
that merely mentions GLP-1 or muscle in passing (e.g. a cardiac or oncology paper) is \
LOW relevance.

Relevance scale: 3 = directly about muscle/body composition on GLP-1 drugs; \
2 = clearly useful adjacent (protein, training, sarcopenia, function in this population); \
1 = tangential; 0 = not relevant.

ACTION FIELD — the one place you may sound even slightly prescriptive, and only \
within these four general levers (never a paper-specific instruction, never a dose, \
never a drug switch):
  - protein: a general nudge toward hitting a daily protein target
  - training: a general nudge toward resistance/strength training
  - monitor: a general nudge to track strength/lean mass or watch for signs of muscle loss
  - clinician: a general nudge to discuss the finding with a prescribing clinician
Pick the ONE lever this paper's finding most naturally supports, and write ONE plain \
sentence for it — descriptive framing ("this adds to the case for...", "this is one \
more reason to...", "worth discussing with...") not commands ("you should...", "start \
taking..."). If the paper is a pure mechanism, pharmacokinetics, or drug-vs-drug \
comparison that does not naturally support any of the four levers, return an empty \
string for action rather than forcing one.

Return ONLY JSON:
{"intro": "<2-3 sentence neutral editor's note for the week>",
 "items": [{"index": <int>, "relevance": <0-3>, "include": <bool>,
            "summary": "<2-4 sentences, plain language, abstract-only>",
            "why": "<1 sentence: the substantive reason it matters. State the reason \
and stop. Do NOT end with a clause that just restates the audience, e.g. \
'..., a key concern for this readership' or '..., relevant to these readers'.>",
            "action": "<1 sentence per the ACTION FIELD rules above, or \"\" if none fit>"}]}
Include every input paper's index exactly once. Set include=true only for relevance >= 2."""


def _week_label(end: date) -> str:
    start = end - timedelta(days=6)
    if start.month == end.month:
        return f"{start.strftime('%B')} {start.day}-{end.day}, {end.year}"
    return f"{start.strftime('%B %-d')} - {end.strftime('%B %-d, %Y')}"


async def curate(client, papers: list[Paper], today: Optional[date] = None) -> Optional[WeeklyDigest]:
    if not papers:
        logger.info("curate: no papers harvested")
        return None
    today = today or date.today()

    listing = []
    for i, p in enumerate(papers):
        listing.append(
            f"[{i}] TITLE: {p.title}\nVENUE: {p.venue}"
            f"{' (PREPRINT)' if p.is_preprint else ''}\nABSTRACT: {p.abstract[:2600]}"
        )
    user = ("Here are this week's candidate papers. Rate, select, and summarize each "
            "per your rules.\n\n" + "\n\n".join(listing))

    raw = await anthropic_message(
        client, system=SYSTEM,
        user_content=[{"type": "text", "text": user}],
        max_tokens=4000, temperature=0.1,
    )
    try:
        data = parse_json(raw)
    except Exception as exc:
        logger.warning("curate: could not parse model output: %s", exc)
        return None

    items: list[DigestItem] = []
    for entry in data.get("items", []):
        idx = entry.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(papers):
            continue  # never invent an item the harvester did not return
        rel = int(entry.get("relevance", 0))
        if not entry.get("include") or rel < MIN_RELEVANCE:
            continue
        summary = (entry.get("summary") or "").strip()
        if not summary:
            continue
        items.append(DigestItem(paper=papers[idx], relevance=rel,
                                summary=summary,
                                why_it_matters=_trim_reader_tail(entry.get("why") or ""),
                                action=_clean_action(entry.get("action") or "")))

    items.sort(key=lambda it: it.relevance, reverse=True)
    items = items[:MAX_ITEMS]
    if len(items) < MIN_ITEMS:
        logger.info("curate: only %d relevant items (< %d); skipping this week",
                    len(items), MIN_ITEMS)
        return None

    return WeeklyDigest(
        date=today.isoformat(),
        week_label=_week_label(today),
        slug=today.isoformat(),
        intro=(data.get("intro") or "").strip(),
        items=items,
    )
