# backend/listen/scorer.py
"""Score listen items for genuine reply-worthiness and draft a suggested
reply for the best ones.

Uses Claude via digest._http (the digest package's Anthropic HTTP helper,
which already has retry/backoff) rather than a duplicate implementation.
One batched call per run keeps this fast and cheap even on a full day's
worth of hits. Nothing here posts anywhere — drafts are for a human to
read, edit, and post themselves.
"""
from __future__ import annotations

import logging

import httpx

from digest._http import anthropic_message, parse_json

logger = logging.getLogger(__name__)

SCORE_MODEL = "claude-sonnet-4-6"

# Keep the batch bounded so the prompt + JSON response stay small and fast
# even on an unusually busy day; going over this cap just means those extra
# items are skipped (scored 0) rather than the call failing outright.
BATCH_CAP = 40

SYSTEM_PROMPT = """You are screening public forum posts (Hacker News, Stack Exchange) \
for genuine, near-term intent to use one of these tools, all built by an \
independent developer at purplelink.llc:

- Paper Review: an AI red-team peer review for academic manuscripts before submission
- Response Review: help drafting a response-to-reviewers letter
- Citation Gap / reference formatting tools

Score each post 1-5 for how likely the poster would welcome someone mentioning \
one of these tools as a reply, where:
  1 = no genuine connection, a mention would read as spam
  3 = tangentially relevant, a mention could be useful but isn't clearly wanted
  5 = poster is visibly struggling with exactly this problem right now

Only draft a suggested reply for posts scoring 4 or 5. The reply must be short \
(2-4 sentences), written as a peer who has the same problem, mention the tool \
only once and only if it is a natural fit, and never use marketing language. \
For posts scoring below 4, leave draft_reply as an empty string.

Return ONLY a JSON array, one object per input post in the same order, each \
shaped exactly like:
{"score": <1-5 integer>, "reasoning": "<one sentence>", "draft_reply": "<string, may be empty>"}"""


async def score_items(client: httpx.AsyncClient, items: list) -> list[dict]:
    """items: list of ListenItem (see sources.py). Returns a list of
    {score, reasoning, draft_reply} dicts, same order and length as items."""
    if not items:
        return []

    working = items[:BATCH_CAP]
    skipped = len(items) - len(working)
    if skipped:
        logger.info("listen: %d items beyond BATCH_CAP=%d, skipping scoring for them", skipped, BATCH_CAP)

    listing = "\n\n".join(
        f"[{i}] source={it.source} title={it.title!r}\nsnippet={it.snippet[:300]!r}"
        for i, it in enumerate(working)
    )
    user_content = [{"type": "text", "text": listing}]

    try:
        raw = await anthropic_message(
            client,
            system=SYSTEM_PROMPT,
            user_content=user_content,
            max_tokens=4000,
            model=SCORE_MODEL,
        )
        results = parse_json(raw)
    except Exception:
        logger.exception("listen: scoring call failed, treating all items as unscored")
        results = None

    if not isinstance(results, list) or len(results) != len(working):
        if results is not None:
            logger.warning("listen: scorer returned malformed output (expected %d items, got %r), discarding", len(working), type(results))
        results = [{"score": 0, "reasoning": "scoring unavailable", "draft_reply": ""} for _ in working]

    results.extend({"score": 0, "reasoning": "batch cap exceeded", "draft_reply": ""} for _ in range(skipped))
    return results
