"""Response letter drafting: the $24 tier of Response Review (product key "response-draft").

Input: the manuscript PDF the reviewers saw, the reviewer and editor comments, optional notes from the author
on what they changed, and an optional revised manuscript PDF.

Method (log first, reconcile second):
1. Parse the comments into numbered items (R1.1, R1.2, ...) in code, so every comment gets an id.
2. Ask the model, per batch of items, for the manuscript passages each item touches, a point-by-point reply,
   and every change the reply relies on, each with a verbatim quote from the revised manuscript.
3. Check in code: a passage is kept only if it is really in the manuscript; a change is kept only if its quote
   is in the revised manuscript and not in the original. Anything else becomes a [PLACEHOLDER] for the
   author. With no revised manuscript, every change is a placeholder. Never claim a change we cannot see.
4. Every parsed id appears exactly once in the letter; an item the model missed is marked "not drafted".
5. The free coherence rules run on the manuscript and are listed for the author.
6. The existing Response Review panel (Skeptical Reviewer, Tone Editor, Editor-in-Chief) critiques the draft.

The report opens, in code, with a plain statement that this is a draft for the author to edit.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Optional

from latextools import coherence as _coh
from latextools import safety as _safety
from latextools.papercheck import (
    DEFAULT_MODEL,
    MAX_BODY_CHARS,
    MODEL_PRICING_PER_MTOK,
    CACHE_WRITE_MULTIPLIER,
    PERSONA_MAX_OUTPUT_TOKENS,
    PaperStructure,
    _CACHE,
    _PREWARM_MIN_TOKENS,
    _TRUNCATION_NOTE,
    _call_json_findings,
    _compact_json,
    _prewarm_cache,
    estimate_input_tokens,
    extract_paper,
)
from latextools.response_review import (
    RR_SYNTHESIS_MAX_OUTPUT_TOKENS,
    RESPONSE_REVIEW_MODEL,
    PanelSynthesisError,
    ResponseReviewProgress,
    parse_reviewer_block,
    run_panel_and_synthesis,
)

logger = logging.getLogger(__name__)

RESPONSE_DRAFT_MODEL = os.environ.get("RESPONSE_DRAFT_MODEL", DEFAULT_MODEL)
DRAFT_MAX_OUTPUT_TOKENS = 16_000
DRAFT_BATCH_SIZE = 10          # comments per drafting call; a long letter is split so no reply is cut off
MAX_DRAFT_ITEMS = 80           # beyond this, items are listed as not drafted (a normal letter has 10 to 40)
MAX_AUTHOR_NOTES_CHARS = 30_000
MAX_PASSAGES_PER_ITEM = 3
MAX_CHANGES_PER_ITEM = 4

DRAFT_NOTICE = (
    "> **This is a draft for you to edit, not a finished letter.** It was written by an AI from your reviewer "
    "comments and manuscript. Read every reply, change anything that does not say what you mean, and fill in "
    "each [PLACEHOLDER]. A change is stated as made only where we found its text in the revised manuscript "
    "you uploaded; everything else is left for you to describe."
)

# Text the panel sees after its persona prompt (uncached), so it judges a draft fairly.
PANEL_DRAFT_NOTE = (
    "Note: this response letter is an automated DRAFT for the author to finish. Text in [PLACEHOLDER: ...] "
    "or [CHECK: ...] brackets marks something the author must still write or confirm. Do not call a "
    "placeholder a hand-wave; treat it as an open item and say what the author needs to put there."
)

_DRAFT_SYSTEM = (
    _safety.SAFETY_PREAMBLE + "\n\n"
    + "You draft a point-by-point response letter to peer reviewers on behalf of the authors. The authors "
    "will edit your draft before sending it.\n\n"
    "Rules:\n"
    "- Answer each comment you are given, by its id, once. Do not merge or skip comments.\n"
    "- Be courteous and direct: thank the reviewer briefly once per comment at most, then engage with the "
    "substance. No flattery, no defensiveness.\n"
    "- Never state in the reply that the authors changed, added, removed or revised anything. Put every "
    "change the reply relies on in the changes list instead, each with a verbatim quote of 25 words or fewer "
    "copied from the REVISED manuscript. If there is no revised manuscript, or you cannot find the change in "
    "it, still list the change, with revised_quote set to an empty string.\n"
    "- Use the author's notes for what they changed and why. Do not invent analyses, results, numbers, "
    "citations or page numbers.\n"
    "- Where the author must supply something you cannot know (a new result, a decision, a citation), write "
    "[PLACEHOLDER: what is needed] in the reply.\n"
    "- passages: up to three verbatim quotes (25 words or fewer each) from the ORIGINAL manuscript that the "
    "comment is about. Copy them exactly; leave the list empty if the comment is general.\n"
    "- Plain, specific prose. No em dashes, no emojis, no filler.\n\n"
    "Output a JSON array only, one object per comment, no preface and no code fences:\n"
    '[{"id": "R1.1", "type": "major" | "minor" | "editorial" | "question" | "praise",\n'
    '  "request": "<one sentence: what the reviewer asks for>",\n'
    '  "passages": ["<verbatim quote from the original manuscript>"],\n'
    '  "reply": "<the response paragraph, in the authors\' voice (we)>",\n'
    '  "changes": [{"description": "<the change, one sentence>", "revised_quote": "<verbatim quote from the '
    'revised manuscript, or empty>"}],\n'
    '  "disagree": true | false}]'
)

# A reply that says a change was made, e.g. "we have added", "we now report", "we revised".
_CHANGE_CLAIM_RE = re.compile(
    r"\bwe\s+(?:have\s+|now\s+|also\s+)*(?:added|revised|rewrote|rewritten|removed|deleted|expanded|clarified|"
    r"included|changed|updated|moved|reorganized|reorganised|shortened|corrected|replaced|introduced|"
    r"restructured|extended|reran|re-ran|conducted|now\s+report|now\s+include|now\s+discuss)\b",
    re.IGNORECASE,
)


def number_items(parsed_reviewers: list[dict]) -> list[dict]:
    """[{"id": "R1.1", "reviewer": "Reviewer 1", "index": 1, "text": "..."}, ...] in letter order."""
    items = []
    for ri, reviewer in enumerate(parsed_reviewers, start=1):
        for ci, comment in enumerate(reviewer.get("comments", []), start=1):
            items.append({"id": f"R{ri}.{ci}", "reviewer": reviewer.get("reviewer") or f"Reviewer {ri}",
                          "index": ci, "text": comment})
    return items


def _manuscript_block(original: PaperStructure, revised: Optional[PaperStructure], author_notes: str,
                      coherence_notes: str) -> dict:
    parts = [
        _safety.wrap_user_content(original.title or "", "manuscript_title"),
        _safety.wrap_user_content(original.abstract or "", "manuscript_abstract"),
        _safety.wrap_user_content(original.body or "", "original_manuscript_body"),
    ]
    if revised is not None:
        parts.append(_safety.wrap_user_content(revised.body or "", "revised_manuscript_body"))
    else:
        parts.append("There is no revised manuscript. Every change must have an empty revised_quote.")
    if author_notes:
        parts.append(_safety.wrap_user_content(author_notes, "author_notes_on_changes"))
    if coherence_notes:
        parts.append(_safety.wrap_user_content(coherence_notes, "coherence_check_findings"))
    return {"type": "text", "text": "\n\n".join(parts), "cache_control": dict(_CACHE)}


def _coherence_notes(data: bytes) -> tuple[str, list[dict]]:
    """The free rule checks (no model call). Non-fatal: any failure gives no notes."""
    try:
        ms = _coh.from_pdf(data)
        found = [f.to_dict() for f in _coh.rule_findings(ms)][:_coh.MAX_FINDINGS]
    except Exception:
        logger.exception("response_draft: coherence rules failed")
        return "", []
    lines = [f"- {f.get('title', '')}: {f.get('why', '')}" for f in found]
    return "\n".join(lines), found


def verify_item(entry: dict, original_body: str, revised_body: Optional[str]) -> dict:
    """Reconcile one drafted item against the manuscripts. Pure function, no model call."""
    passages = []
    for q in (entry.get("passages") or [])[:MAX_PASSAGES_PER_ITEM]:
        if isinstance(q, str) and _coh.quote_in_text(q, original_body):
            passages.append(_coh.trim_quote(q))
    changes = []
    for ch in (entry.get("changes") or [])[:MAX_CHANGES_PER_ITEM]:
        if not isinstance(ch, dict):
            continue
        desc = str(ch.get("description") or "").strip()
        quote = str(ch.get("revised_quote") or "").strip()
        if not desc:
            continue
        if revised_body is None:
            status = "no_revised_manuscript"
        elif not quote or not _coh.quote_in_text(quote, revised_body):
            status = "not_found"
        elif _coh.quote_in_text(quote, original_body):
            status = "already_in_original"
        else:
            status = "verified"
        changes.append({"description": desc, "quote": _coh.trim_quote(quote) if status == "verified" else "",
                        "status": status})
    reply = str(entry.get("reply") or "").strip()
    has_verified = any(c["status"] == "verified" for c in changes)
    if reply and _CHANGE_CLAIM_RE.search(reply) and not has_verified:
        reply = ("[CHECK: this reply says a change was made, but we could not find it in the revised "
                 "manuscript. Confirm it or reword.] " + reply)
    return {
        "type": str(entry.get("type") or ""),
        "request": str(entry.get("request") or "").strip(),
        "passages": passages,
        "reply": reply,
        "changes": changes,
        "disagree": bool(entry.get("disagree")),
    }


_STATUS_TEXT = {
    "no_revised_manuscript": "no revised manuscript uploaded",
    "not_found": "not found in the revised manuscript",
    "already_in_original": "this text was already in the original",
}


def _change_line(ch: dict) -> str:
    if ch["status"] == "verified":
        return f"- {ch['description']} The revised manuscript now reads: \"{ch['quote']}\""
    return (f"- [PLACEHOLDER: {ch['description']} Describe where and how this was changed "
            f"({_STATUS_TEXT[ch['status']]}).]")


def render_letter(items: list[dict], drafted: dict[str, dict]) -> str:
    """The draft letter, every parsed id exactly once, in letter order."""
    out = []
    current = None
    for it in items:
        if it["reviewer"] != current:
            current = it["reviewer"]
            out.append(f"### {current}\n")
        out.append(f"**Comment {it['id']}.** {it['text'].strip()}\n")
        d = drafted.get(it["id"])
        if d is None or not d["reply"]:
            out.append("**Response.** [PLACEHOLDER: not drafted. Write the response to this comment.]\n")
            continue
        out.append(f"**Response.** {d['reply']}\n")
        if d["changes"]:
            out.append("Changes in the manuscript:\n\n" + "\n".join(_change_line(c) for c in d["changes"]) + "\n")
    return "\n".join(out).rstrip() + "\n"


def render_ledger(items: list[dict], drafted: dict[str, dict]) -> str:
    rows = ["| Comment | Request | Passages found | Changes verified | Placeholders |",
            "|---|---|---|---|---|"]
    for it in items:
        d = drafted.get(it["id"])
        if d is None or not d["reply"]:
            rows.append(f"| {it['id']} | (not drafted) | 0 | 0 | 1 |")
            continue
        verified = sum(1 for c in d["changes"] if c["status"] == "verified")
        open_ = sum(1 for c in d["changes"] if c["status"] != "verified") + d["reply"].count("[PLACEHOLDER")
        open_ += d["reply"].count("[CHECK")
        req = d["request"].replace("|", "/")[:120] or "(not stated)"
        rows.append(f"| {it['id']} | {req} | {len(d['passages'])} | {verified} | {open_} |")
    return "\n".join(rows) + "\n"


def _plain_letter(items: list[dict], drafted: dict[str, dict]) -> str:
    """The letter as the panel reads it: replies only, keyed by reviewer and comment number (the panel has
    the parsed comments already), so a long letter still fits the panel's 30,000-character window."""
    out = []
    for it in items:
        d = drafted.get(it["id"])
        reply = d["reply"] if d and d["reply"] else "[PLACEHOLDER: not drafted.]"
        out.append(f"{it['reviewer']}, comment {it['index']}: {reply}")
        if d:
            out += [_change_line(c) for c in d["changes"]]
    return "\n\n".join(out)


async def _draft_batches(client, block: dict, items: list[dict]) -> tuple[dict[str, dict], int]:
    """Draft every batch. Returns ({id: raw entry}, failed batch count)."""
    batches = [items[i:i + DRAFT_BATCH_SIZE] for i in range(0, len(items), DRAFT_BATCH_SIZE)]

    async def _one(batch: list[dict]) -> tuple[list[dict], bool]:
        tail = (
            _safety.wrap_user_content(
                _compact_json([{"id": it["id"], "reviewer": it["reviewer"], "comment": it["text"]} for it in batch]),
                "reviewer_comments_to_answer",
            )
            + "\n\nDraft the reply for each of these comments now. Output the JSON array."
        )
        try:
            found, status = await _call_json_findings(
                client, system=_DRAFT_SYSTEM, user_content=[block, {"type": "text", "text": tail}],
                max_tokens=DRAFT_MAX_OUTPUT_TOKENS, model=RESPONSE_DRAFT_MODEL,
            )
        except Exception:
            logger.exception("response_draft: drafting batch failed")
            return [], False
        return found, status != "unparsed"

    if len(batches) > 1 and estimate_input_tokens(_DRAFT_SYSTEM, [block]) >= _PREWARM_MIN_TOKENS:
        if await _prewarm_cache(client, system=_DRAFT_SYSTEM, user_content=[block], model=RESPONSE_DRAFT_MODEL):
            results = await asyncio.gather(*(_one(b) for b in batches))
        else:
            results = [await _one(b) for b in batches]
    else:
        results = await asyncio.gather(*(_one(b) for b in batches))

    wanted = {it["id"] for it in items}
    out: dict[str, dict] = {}
    failed = 0
    for found, ok in results:
        failed += 0 if ok else 1
        for entry in found:
            eid = str(entry.get("id") or "").strip() if isinstance(entry, dict) else ""
            if eid in wanted and eid not in out:      # first answer wins; stray or repeated ids are dropped
                out[eid] = entry
    return out, failed


async def run_response_draft(
    pdf_bytes: bytes,
    reviewer_comments: str,
    author_notes: str = "",
    revised_pdf_bytes: Optional[bytes] = None,
    on_progress=None,
) -> dict:
    """Draft the response letter, verify it, and critique it with the Response Review panel."""
    import httpx

    progress = ResponseReviewProgress(status="running", progress_pct=2, stage="extracting", started_at=time.time())

    def _emit():
        if on_progress is not None:
            try:
                on_progress(progress)
            except Exception:
                logger.exception("on_progress callback raised")

    def _fail(code: str) -> dict:
        progress.status = "error"
        progress.error = code
        progress.finished_at = time.time()
        _emit()
        return {"status": "error", "error": code}

    _emit()
    try:
        original = extract_paper(pdf_bytes)
    except Exception as e:
        return _fail(f"extraction_failed: {type(e).__name__}")
    revised = None
    if revised_pdf_bytes:
        try:
            revised = extract_paper(revised_pdf_bytes)
        except Exception as e:
            return _fail(f"revised_extraction_failed: {type(e).__name__}")

    rev_clean = _safety.safe_reviewer_comments(reviewer_comments or "")
    notes_clean = _safety.safe_author_response((author_notes or "")[:MAX_AUTHOR_NOTES_CHARS])
    if rev_clean.suspicious_patterns or notes_clean.suspicious_patterns:
        logger.warning("response_draft: injection patterns flagged (rev=%s, notes=%s)",
                       rev_clean.suspicious_patterns, notes_clean.suspicious_patterns)
    parsed = parse_reviewer_block(rev_clean.text)
    items = number_items(parsed)
    if not items:
        return _fail("no_reviewer_comments_parsed")
    to_draft = items[:MAX_DRAFT_ITEMS]

    coherence_text, coherence_found = _coherence_notes(revised_pdf_bytes or pdf_bytes)

    progress.progress_pct = 15
    progress.stage = "drafting"
    _emit()

    revised_body = revised.body if revised is not None else None
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:
        block = _manuscript_block(original, revised, notes_clean.text, coherence_text)
        raw, failed_batches = await _draft_batches(client, block, to_draft)
        if not raw:
            return _fail("drafting_failed")
        drafted = {eid: verify_item(entry, original.body or "", revised_body) for eid, entry in raw.items()}

        progress.progress_pct = 55
        progress.stage = "panel"
        _emit()

        letter_md = render_letter(items, drafted)
        panel_md = ""
        try:
            panel = await run_panel_and_synthesis(
                client, revised or original, parsed, _plain_letter(items, drafted),
                persona_note=PANEL_DRAFT_NOTE,
            )
            panel_md = panel["md"].strip() + (_TRUNCATION_NOTE if panel["truncated"] else "")
        except PanelSynthesisError:
            panel_md = ("# Response Letter Review\n\nThe critique of this draft could not be completed. "
                        "The draft above is complete; run it through Response Review once you have edited it.")

    sections = [
        "# Response Letter Draft",
        DRAFT_NOTICE,
        f"Comments parsed: {len(items)}. Drafted: {len(drafted)}. "
        + ("A revised manuscript was checked for every stated change."
           if revised is not None else
           "No revised manuscript was uploaded, so every change is left as a placeholder."),
        "## Draft letter",
        letter_md,
        "## Change verification",
        "Each reply was checked against your manuscripts. \"Changes verified\" counts changes whose quoted "
        "text we found in the revised manuscript and not in the original.",
        render_ledger(items, drafted),
    ]
    if coherence_found:
        sections += ["## Coherence notes",
                     "Automatic checks on the manuscript that reviewers may also notice:",
                     "\n".join(f"- **{f.get('title', '')}** {f.get('why', '')}" for f in coherence_found)]
    sections += ["---", panel_md]
    md = "\n\n".join(s.strip() for s in sections if s.strip()) + "\n"

    progress.progress_pct = 100
    progress.stage = "done"
    progress.status = "done"
    progress.result_md = md
    progress.finished_at = time.time()
    _emit()
    return {
        "status": "done",
        "progress_pct": 100,
        "stage": "done",
        "result_md": md,
        "items_parsed": len(items),
        "items_drafted": len(drafted),
        "failed_batches": failed_batches,
        "changes_verified": sum(1 for d in drafted.values() for c in d["changes"] if c["status"] == "verified"),
    }


def worst_case_cost_usd(n_items: int = MAX_DRAFT_ITEMS) -> float:
    """Upper bound on one order's model spend, from the caps in this module and the panel's.

    Assumes every call sends its whole input uncached (no cache reads), every output hits its cap, and every
    call is retried once (the JSON retry in _call_json_findings). Real runs cost far less.
    """
    def price(model: str) -> dict:
        return MODEL_PRICING_PER_MTOK.get(model, MODEL_PRICING_PER_MTOK[DEFAULT_MODEL])

    chars_per_token = 3.5
    manuscript_tokens = (2 * MAX_BODY_CHARS + MAX_AUTHOR_NOTES_CHARS + 10_000) / chars_per_token
    batches = -(-n_items // DRAFT_BATCH_SIZE)
    d = price(RESPONSE_DRAFT_MODEL)
    batch_in = manuscript_tokens * CACHE_WRITE_MULTIPLIER + 4_000
    draft = 2 * batches * (batch_in * d["input"] + DRAFT_MAX_OUTPUT_TOKENS * d["output"]) / 1e6

    r = price(RESPONSE_REVIEW_MODEL)
    panel_in = (MAX_BODY_CHARS + 30_000 + 60_000) / chars_per_token * CACHE_WRITE_MULTIPLIER
    panel = 2 * 3 * (panel_in * r["input"] + PERSONA_MAX_OUTPUT_TOKENS * r["output"]) / 1e6
    synth_in = (20_000 + 30_000 + 45_000) / chars_per_token
    synth = (synth_in * r["input"] + RR_SYNTHESIS_MAX_OUTPUT_TOKENS * r["output"]) / 1e6
    return draft + panel + synth


def typical_cost_usd(n_items: int = 25, manuscript_chars: int = 60_000, revised: bool = True) -> float:
    """A realistic estimate: one cache write, cache reads for the other batches, outputs about a third of cap."""
    d = MODEL_PRICING_PER_MTOK.get(RESPONSE_DRAFT_MODEL, MODEL_PRICING_PER_MTOK[DEFAULT_MODEL])
    r = MODEL_PRICING_PER_MTOK.get(RESPONSE_REVIEW_MODEL, MODEL_PRICING_PER_MTOK[DEFAULT_MODEL])
    block = manuscript_chars * (2 if revised else 1) / 3.5 + 3_000
    batches = -(-n_items // DRAFT_BATCH_SIZE)
    out_per_batch = 600 * min(n_items, DRAFT_BATCH_SIZE) + 2_000           # replies plus thinking
    draft = (block * CACHE_WRITE_MULTIPLIER * d["input"] + (batches - 1) * block * d.get("cache_read", d["input"] / 10)
             + batches * (1_500 * d["input"] + out_per_batch * d["output"])) / 1e6
    panel_block = manuscript_chars / 3.5 + n_items * 250
    panel = (panel_block * CACHE_WRITE_MULTIPLIER * r["input"] + 2 * panel_block * r.get("cache_read", r["input"] / 10)
             + 3 * (1_000 * r["input"] + 5_000 * r["output"])) / 1e6
    synth = (n_items * 600 / 3.5 * r["input"] + 5_000 * r["output"]) / 1e6
    return draft + panel + synth
