"""Response-to-Reviewers tool — $6 standalone paid product.

Input: the original manuscript PDF + the reviewer comments (pasted text or
PDF) + the author's draft response (pasted text or PDF).

Output: a Markdown report red-teaming whether each reviewer concern was
actually addressed by the response. Three-persona panel: Skeptical Reviewer
(treats each response as a hand-wave until proven otherwise), Tone Editor
(flags defensive / dismissive / argumentative phrasing), Editor-in-Chief
(big-picture: would these responses unlock acceptance?).

Reuses the same extract_paper + Anthropic helpers as the main pipeline.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from latextools.papercheck import (
    _anthropic_message,
    _call_json_findings,
    _compact_json,
    _consensus_filter,
    _prewarm_cache,
    _PREWARM_MIN_TOKENS,
    _CACHE,
    _TRUNCATION_NOTE,
    DEFAULT_MODEL,
    PaperStructure,
    extract_paper,
    flag_unverified_quotes,
    estimate_input_tokens,
    PERSONA_MAX_OUTPUT_TOKENS,
)
from latextools import safety as _safety

logger = logging.getLogger(__name__)

# Settable in the Modal secret without a code change; defaults to the main review model.
RESPONSE_REVIEW_MODEL = os.environ.get("RESPONSE_REVIEW_MODEL", DEFAULT_MODEL)
# Thinking shares this budget on the 5.x models; 5,000 could cut the report off.
RR_SYNTHESIS_MAX_OUTPUT_TOKENS = 12_000

# One system prompt for the panel calls. The manuscript block is cached, and a cache entry is matched on the
# system prompt first, so the Skeptical Reviewer and the Editor-in-Chief only share it if this is identical.
RR_PANEL_SYSTEM = (
    _safety.SAFETY_PREAMBLE + "\n\n"
    + "You are part of an editorial panel evaluating an author's response letter to peer reviewers. Stay "
    "strictly in the persona you are given at the end of the user message.\n\n"
    "- Quote the reviewer and the author exactly. Quote revised-manuscript text exactly when you say a "
    "change is or is not there.\n"
    "- Judge only what the text shows. If the revised manuscript does not let you check a claimed change, "
    "the verdict is not_evaluable, not hand_waved.\n"
    "- Credit responses that fix the concern. Do not mark a response weak just to have findings.\n"
    "- Plain, specific prose. No em dashes, no emojis, no filler.\n\n"
    "Output a JSON array only: no preface and no code fences."
)


# ---------------------------------------------------------------------------
# Reviewer-comment parsing
# ---------------------------------------------------------------------------


def _truncate_reviewers_json(parsed_reviewers: list[dict], max_chars: int) -> str:
    """Serialize parsed_reviewers to JSON, shrinking at comment/reviewer
    boundaries (never mid-string) so the result never exceeds max_chars and
    is always valid JSON.

    A flat string slice of json.dumps(...) can land mid-string or
    mid-object and produce syntactically invalid JSON for the synthesis
    LLM, and can silently drop later reviewers even though earlier
    per-persona prompts saw the full list. This truncates by dropping whole
    comments (and, if needed, whole trailing reviewers) instead, so every
    reviewer that fits is fully represented and the JSON always parses.
    """
    import json as _json

    full = _json.dumps(parsed_reviewers, indent=2)
    if len(full) <= max_chars:
        return full

    truncated: list[dict] = []
    for reviewer in parsed_reviewers:
        comments = reviewer.get("comments", [])
        kept_comments: list[str] = []
        for comment in comments:
            candidate = truncated + [
                {**reviewer, "comments": kept_comments + [comment]}
            ]
            if len(_json.dumps(candidate, indent=2)) > max_chars:
                break
            kept_comments.append(comment)
        if kept_comments:
            truncated.append({**reviewer, "comments": kept_comments})
        if len(_json.dumps(truncated, indent=2)) >= max_chars:
            break

    return _json.dumps(truncated, indent=2)


def parse_reviewer_block(text: str) -> list[dict]:
    """Split a flat reviewer-comments block into per-reviewer entries.

    Recognises common patterns:
      "Reviewer 1:" / "Reviewer #1" / "R1:" / "Referee 1:" / "Reviewer A:" /
      "Reviewer B (Methods):" — section header
      "Comment 1:" / "1." / "(1)" — numbered points within a reviewer
      "-" / "*" / "•" — bulleted points within a reviewer (used when no
      numbered markers are present)

    Returns: [{"reviewer": "Reviewer 1", "comments": ["...", "..."]}, ...]
    Falls back to a single reviewer with the whole text as one comment if
    no recognisable structure is found.
    """
    import re
    if not text or not text.strip():
        return []
    txt = text.replace("\r\n", "\n")
    # Split by reviewer headers. Supports "Reviewer 1", "Reviewer #1",
    # "R1", "Referee 1", and letter-identified reviewers ("Reviewer A"),
    # each optionally followed by a parenthetical suffix (e.g. "(Methods)")
    # before the terminating colon/period/whitespace. The bare "R<n>" form
    # is kept numeric-only (as before) to avoid false-positives on stray
    # capital letters followed by punctuation in prose; the full words
    # "Reviewer"/"Referee" may take a number or a single letter.
    header_re = (
        r"\n\s*(?:(?:Reviewer|Referee)\s*#?\s*[A-Za-z0-9]+|R\s*#?\s*\d+)"
        r"(?:\s*\([^)\n]*\))?[:\.\s]+"
    )
    header_capture_re = (
        r"\n\s*((?:(?:Reviewer|Referee)\s*#?\s*[A-Za-z0-9]+|R\s*#?\s*\d+)"
        r"(?:\s*\([^)\n]*\))?)[:\.\s]+"
    )
    parts = re.split(header_re, "\n" + txt, flags=re.IGNORECASE)
    headers = re.findall(header_capture_re, "\n" + txt, flags=re.IGNORECASE)
    # parts[0] is everything before the first reviewer header (usually empty)
    if len(parts) <= 1:
        return [{"reviewer": "Reviewer 1", "comments": [txt.strip()]}]

    out = []
    for header, body in zip(headers, parts[1:]):
        body = body.strip()
        if not body:
            continue
        # Split into numbered comments within this reviewer block
        comment_parts = re.split(
            r"\n\s*(?:\(\d{1,3}\)|\d{1,3}\.|Comment\s+\d{1,3}[:.])\s+",
            "\n" + body,
        )
        comments = [c.strip() for c in comment_parts if c.strip()]
        if len(comments) <= 1:
            # No numbered/parenthesized markers found — fall back to
            # bulleted markers ("-", "*", "•") as distinct comments.
            bullet_parts = re.split(r"\n\s*[-*•]\s+", "\n" + body)
            bullet_comments = [c.strip() for c in bullet_parts if c.strip()]
            if len(bullet_comments) > 1:
                comments = bullet_comments
        if not comments:
            comments = [body]
        out.append({"reviewer": header.strip(), "comments": comments})
    return out


# ---------------------------------------------------------------------------
# Persona prompts
# ---------------------------------------------------------------------------

_RR_SKEPTICAL = """<persona name="Skeptical Reviewer">
You are a skeptical reviewer reading the author's response letter. Your
default position is that every response is a hand-wave until proven
otherwise. Your job is to identify responses that:

- Promise a change but don't show evidence the change was made.
- Argue the reviewer was wrong without addressing the underlying concern.
- Move the goalposts (e.g. "this was out of scope" when the reviewer
  asked about a core claim).
- Add new content (a paragraph, a figure, additional analysis) but you
  can't find that content in the revised manuscript.
- Acknowledge a limitation without committing to a fix.

Output a JSON array of finding objects:
[
  {
    "reviewer": "<which reviewer the comment is from, e.g. 'Reviewer 1'>",
    "comment_index": <int — 1-based within that reviewer>,
    "comment_quoted": "<the reviewer's original comment>",
    "response_quoted": "<the author's response, quoted exactly>",
    "verdict": "addressed" | "partially_addressed" | "hand_waved" | "rejected_with_argument" | "not_evaluable",
    "issue": "<one or two sentences: what's weak about this response>",
    "what_to_do": "<concrete change to the response or the manuscript>",
    "severity": "critical" | "major" | "minor"
  },
  ...
]

Output ONLY the JSON array. No preamble.
</persona>"""

_RR_TONE_EDITOR = """<persona name="Tone Editor">
You are a senior editor reading the response for TONE, not for substance.
Your job is to flag any phrasing that:

- Sounds defensive or argumentative (likely to anger a reviewer who
  already invested time in the original critique).
- Dismisses the reviewer's expertise ("the reviewer misunderstood our
  point" without immediately clarifying).
- Sounds condescending or pedagogical.
- Uses unnecessary emphasis ("clearly", "obviously", "trivially").
- Lacks acknowledgement before disagreeing ("Thank you for the comment,
  but...").

Your job is NOT to police politeness — it IS to prevent the response from
giving the reviewer a reason to reject the resubmission on principle.

Output a JSON array of finding objects:
[
  {
    "reviewer": "<which reviewer>",
    "comment_index": <int>,
    "quoted_phrasing": "<the exact response phrasing flagged>",
    "issue": "<what the tone signals>",
    "suggested_rewrite": "<a less-charged rephrasing that says the same thing>",
    "severity": "minor" | "major"
  },
  ...
]

Be conservative — only flag genuine tone risks, not every sentence that
could be marginally softer. Output ONLY the JSON array.
</persona>"""

_RR_EDITOR_IN_CHIEF = """<persona name="Editor-in-Chief">
You are the journal editor deciding whether this revision + response
package warrants acceptance. The reviewers will see what you see. Your
big-picture questions:

- If you forwarded these responses to the original reviewers, would
  Reviewer 1 / Reviewer 2 / etc. each be satisfied?
- Are there any reviewer concerns the response letter NEVER addresses?
  (Authors sometimes omit responses entirely.)
- Does the response pattern suggest the authors took the critique
  seriously, or did they do the minimum?
- Is there a single "must fix or reject" issue that wasn't fully fixed?

Output a JSON array with ONE final summary finding:
[
  {
    "verdict": "ready_to_accept" | "needs_minor_changes" | "needs_substantial_revision" | "reject_after_response",
    "summary": "<one paragraph synthesising the overall response quality>",
    "blocking_concerns": ["<short concern>", ...],   // [] if none
    "missing_responses": ["<short description of unaddressed reviewer comments>", ...],
    "tone_pattern": "professional" | "defensive" | "dismissive" | "mixed"
  }
]

Output ONLY the JSON array (one element).
</persona>"""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@dataclass
class ResponseReviewProgress:
    status: str = "running"
    progress_pct: int = 0
    stage: str = "extracting"   # extracting | panel | rectifying | done
    started_at: float = 0.0
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result_md: Optional[str] = None
    layer_status: dict = field(default_factory=dict)


_RR_SYNTHESIS_SYSTEM = """You are the senior editor producing the final
Markdown report for the authors. You have:

- The paper's title and abstract.
- The reviewer comments, parsed by reviewer.
- The author's response letter (parsed alongside the comments).
- Skeptical Reviewer findings (per-comment verdicts).
- Tone Editor findings (phrasing risks).
- Editor-in-Chief verdict (overall).

Produce a Markdown report with EXACTLY these sections:

# Response Letter Review

## Overall Verdict
Quote the editor-in-chief verdict in one sentence. Then a short paragraph
explaining what would block resubmission acceptance if anything.

## Per-Comment Tracker
A subsection PER REVIEWER. Inside each reviewer's block, a bulleted list:

- **[R1.1] addressed:** Reviewer asked X. Response says Y. Quote evidence
  in the revision.
- **[R1.2] hand_waved:** Reviewer asked X. Response says Y — but this
  doesn't actually engage with the concern because Z. To fix: ...

Use the canonical verdicts: addressed / partially_addressed / hand_waved /
rejected_with_argument / not_evaluable.

## Tone Concerns
List each tone issue with the flagged phrasing and a suggested rewrite.
If none: "(no tone concerns flagged)".

## Missing Responses
If any reviewer comments were not addressed at all in the response letter,
list them here. If none: "(every comment received some response)".

## Action Checklist Before Resubmission
A short A/B/C list — what to change in the response letter or manuscript
before hitting submit. [A] must-fix. [B] should-fix. [C] polish.

Constraints: quote both the reviewer and the response exactly when
challenging an item. No emojis. Output ONLY the Markdown report.
"""


async def run_response_review(
    pdf_bytes: bytes,
    reviewer_comments: str,
    author_response: str,
    on_progress=None,
) -> dict:
    """End-to-end response-letter review."""
    import time
    import json as _json
    import httpx

    progress = ResponseReviewProgress(
        status="running", progress_pct=2, stage="extracting",
        started_at=time.time(),
    )

    def _emit():
        if on_progress is not None:
            try:
                on_progress(progress)
            except Exception:
                logger.exception("on_progress callback raised")
    _emit()

    # Extract the manuscript
    try:
        structure = extract_paper(pdf_bytes)
    except Exception as e:
        progress.status = "error"
        progress.error = f"extraction_failed: {type(e).__name__}"
        progress.finished_at = time.time()
        _emit()
        return {"status": "error", "error": progress.error}

    # Sanitize the two highest-risk free-text inputs BEFORE parsing or
    # embedding. extract_paper already sanitized the PDF.
    rev_clean = _safety.safe_reviewer_comments(reviewer_comments or "")
    resp_clean = _safety.safe_author_response(author_response or "")
    reviewer_comments = rev_clean.text
    author_response = resp_clean.text
    if rev_clean.suspicious_patterns or resp_clean.suspicious_patterns:
        logger.warning(
            "response_review: injection patterns flagged (rev=%s, resp=%s)",
            rev_clean.suspicious_patterns,
            resp_clean.suspicious_patterns,
        )

    parsed_reviewers = parse_reviewer_block(reviewer_comments)
    if not parsed_reviewers:
        progress.status = "error"
        progress.error = "no_reviewer_comments_parsed"
        progress.finished_at = time.time()
        _emit()
        return {"status": "error", "error": "no_reviewer_comments_parsed"}

    progress.progress_pct = 25
    progress.stage = "panel"
    _emit()

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:

        reviewers_json = _compact_json(parsed_reviewers)
        shared_block = {
            "type": "text",
            "text": (
                _safety.wrap_user_content(structure.title or "", "manuscript_title") + "\n"
                + _safety.wrap_user_content(structure.abstract or "", "manuscript_abstract") + "\n\n"
                + _safety.wrap_user_content(reviewers_json, "reviewer_comments_parsed") + "\n\n"
                + _safety.wrap_user_content(author_response[:30_000], "author_response") + "\n\n"
                + _safety.wrap_user_content(structure.body or "", "revised_manuscript_body")
            ),
            "cache_control": dict(_CACHE),
        }
        # The Tone Editor judges phrasing only, so it gets the letter and the comments but not the
        # manuscript (about 20,000 tokens it has no use for).
        tone_block = {
            "type": "text",
            "text": (
                _safety.wrap_user_content(reviewers_json, "reviewer_comments_parsed") + "\n\n"
                + _safety.wrap_user_content(author_response[:30_000], "author_response")
            ),
        }

        async def _persona(persona_key: str, persona_prompt: str) -> dict:
            blocks = [tone_block if persona_key == "tone_editor" else shared_block,
                      {"type": "text", "text": f"{persona_prompt}\n\nNow produce your JSON array."}]
            try:
                findings, call_status = await _call_json_findings(
                    client,
                    system=RR_PANEL_SYSTEM,
                    user_content=blocks,
                    max_tokens=PERSONA_MAX_OUTPUT_TOKENS,
                    model=RESPONSE_REVIEW_MODEL,
                )
            except Exception:
                logger.exception("RR persona %s failed", persona_key)
                return {"persona": persona_key, "findings": [], "status": "error"}
            flag_unverified_quotes(findings, structure.body)
            for f in findings:
                f["persona"] = persona_key
            return {"persona": persona_key, "findings": findings,
                    "status": "error" if call_status == "unparsed" else "ok"}

        async def _skeptical_and_editor() -> tuple[dict, dict]:
            # Both read the same cached manuscript block: write the cache once, then run them together.
            if estimate_input_tokens(RR_PANEL_SYSTEM, [shared_block]) >= _PREWARM_MIN_TOKENS:
                if not await _prewarm_cache(client, system=RR_PANEL_SYSTEM, user_content=[shared_block],
                                            model=RESPONSE_REVIEW_MODEL):
                    first = await _persona("skeptical_reviewer", _RR_SKEPTICAL)
                    return first, await _persona("editor_in_chief", _RR_EDITOR_IN_CHIEF)
            return tuple(await asyncio.gather(
                _persona("skeptical_reviewer", _RR_SKEPTICAL),
                _persona("editor_in_chief", _RR_EDITOR_IN_CHIEF),
            ))

        tone_task = asyncio.create_task(_persona("tone_editor", _RR_TONE_EDITOR))
        (skeptical, editor), tone = await asyncio.gather(_skeptical_and_editor(), tone_task)

        progress.progress_pct = 80
        progress.stage = "rectifying"
        _emit()

        # Synthesis
        synth_user = (
            _safety.wrap_user_content(
                f"Title: {structure.title}", "paper_metadata",
            ) + "\n\n"
            + _safety.wrap_user_content(
                _truncate_reviewers_json(parsed_reviewers, 20_000),
                "reviewer_comments_parsed",
            ) + "\n\n"
            + _safety.wrap_user_content(
                author_response[:30_000], "author_response",
            ) + "\n\n"
            + _safety.wrap_user_content(
                _compact_json(skeptical.get('findings', []))[:30_000],
                "skeptical_reviewer_findings",
            ) + "\n\n"
            + _safety.wrap_user_content(
                _compact_json(tone.get('findings', []))[:10_000],
                "tone_editor_findings",
            ) + "\n\n"
            + _safety.wrap_user_content(
                _compact_json(editor.get('findings', []))[:5_000],
                "editor_in_chief_verdict",
            ) + "\n\n"
            + "Produce the final Markdown report now."
        )
        truncated: list[bool] = []
        try:
            md = await _anthropic_message(
                client,
                system=_safety.SAFETY_PREAMBLE + "\n\n" + _RR_SYNTHESIS_SYSTEM,
                user_content=[{"type": "text", "text": synth_user}],
                max_tokens=RR_SYNTHESIS_MAX_OUTPUT_TOKENS,
                model=RESPONSE_REVIEW_MODEL,
                on_truncated=lambda _m: truncated.append(True),
            )
        except Exception:
            logger.exception("RR synthesis failed")
            progress.status = "error"
            progress.error = "synthesis_failed"
            progress.finished_at = time.time()
            _emit()
            return {"status": "error", "error": "synthesis_failed"}

    progress.progress_pct = 100
    progress.stage = "done"
    progress.status = "done"
    if truncated:
        md = md.rstrip() + _TRUNCATION_NOTE
    progress.result_md = md.strip()
    progress.finished_at = time.time()
    _emit()
    return {
        "status": "done",
        "progress_pct": 100,
        "stage": "done",
        "result_md": md.strip(),
        "reviewers_parsed": len(parsed_reviewers),
        "skeptical_findings": len(skeptical.get("findings", [])),
        "tone_findings": len(tone.get("findings", [])),
    }
