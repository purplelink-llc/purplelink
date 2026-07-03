"""Paper Review add-ons and adjacent paid tools.

Houses the smaller pure-LLM features that share infrastructure with the
main 4-layer pipeline but don't justify their own modules:

  - run_cover_letter — $3 add-on: draft a journal cover letter from the
    abstract + journal name.
  - run_anonymity_check — $2 add-on (or bundled): scans for identifying
    information that breaks double-blind review.
  - run_citation_gap — $5 standalone: finds prior art that the manuscript
    should cite but doesn't.
  - run_revision_review — $2 second-pass: re-evaluates a revised paper
    against the original review's flagged issues, plus a light pass for new
    problems introduced by the revision.

All four are async, take an httpx.AsyncClient, and return JSON-friendly
dicts. They use the same Anthropic helper as papercheck (shared model
constants, shared token caps).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

from latextools.papercheck import (
    _anthropic_message,
    _parse_json_findings,
    _string_overlap,
    PaperStructure,
    PERSONA_MAX_OUTPUT_TOKENS,
)
from latextools import safety as _safety

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cover Letter Generator  ($3 add-on)
# ---------------------------------------------------------------------------

_COVER_LETTER_SYSTEM = """You are a senior academic helping the author draft
a journal cover letter for their manuscript. The letter must:

- Be 200-350 words.
- Open with the manuscript title and the journal it's being submitted to.
- State the central claim in one sentence.
- Explain in two-three sentences why this work fits THIS journal — drawing
  on the journal's stated scope and the manuscript's positioning.
- Briefly summarise the methodology and the most significant result.
- Affirm originality (not under review elsewhere; manuscript content has
  not been previously published).
- Suggest 2-3 potential reviewers IF the abstract makes their expertise
  obvious — otherwise omit this paragraph entirely rather than invent
  names. NEVER list reviewers you can't justify.
- Close with the author's contact name as a placeholder
  '[Corresponding Author Name]' and signature placeholder.

Constraints:
- No emojis, no superlatives ("groundbreaking", "novel"), no hype.
- Hedge confidence claims. Don't oversell.
- Output ONLY the cover letter text. No preamble, no markdown headers, no
  meta commentary. Use plain prose with paragraph breaks.
"""


async def run_cover_letter(
    client,
    structure: PaperStructure,
    journal_name: str,
    custom_note: str = "",
) -> dict:
    """Generate a draft cover letter for journal submission.

    All free-text inputs are sanitized + wrapped in untrusted-content
    fences before being embedded in the prompt.
    """
    title = _safety.safe_title(structure.title or "(not extracted)").text
    abstract = _safety.safe_abstract(structure.abstract or "(no abstract extracted)").text
    journal_clean = _safety.safe_journal_name(journal_name or "the target journal").text
    note_clean = _safety.safe_author_note(custom_note or "").text

    user_text = (
        _safety.wrap_user_content(title, "manuscript_title") + "\n\n"
        + _safety.wrap_user_content(abstract, "abstract") + "\n\n"
        + _safety.wrap_user_content(journal_clean, "target_journal") + "\n\n"
    )
    if note_clean:
        user_text += _safety.wrap_user_content(note_clean, "author_note") + "\n\n"
    user_text += "Draft the cover letter now."

    try:
        raw = await _anthropic_message(
            client,
            system=_safety.SAFETY_PREAMBLE + "\n\n" + _COVER_LETTER_SYSTEM,
            user_content=[{"type": "text", "text": user_text}],
            max_tokens=1500,
        )
    except Exception:
        logger.exception("cover letter generation failed")
        return {"status": "error", "text": ""}
    return {"status": "ok", "text": raw.strip()}


# ---------------------------------------------------------------------------
# Anonymity Check  ($2 add-on or bundled with Paper Review)
# ---------------------------------------------------------------------------

_ANONYMITY_SYSTEM = """You are a research-integrity officer scanning a
manuscript for identifying information that would break double-blind peer
review. Your job is to find every concrete leak. Look for:

- Author or co-author names embedded in the body (e.g. "Smith et al."
  referring to the authors' own prior work, especially in self-citation
  patterns).
- Institution names ("at our institution X", "the University of Y", lab
  names, hospital names).
- Acknowledgement-style language disclosing identity ("we thank our
  funder", funder names, grant numbers like 'NSF #1234567', 'NIH R01').
- IRB / IACUC / ethics-board protocol numbers tying back to a specific
  institution.
- Author email addresses or URLs to author-owned repositories
  (github.com/<username>, lab webpages).
- Software the authors named (publicly-released code or models) that
  trivially identifies them via GitHub or Hugging Face.
- Geographic or demographic data so specific it identifies the host
  institution.
- Prior-publication boilerplate ("In our previous work [12] ...") where
  [12] is by the same authors.

Output a JSON array (and ONLY a JSON array) of leak objects:
[
  {
    "category": "author_name" | "institution" | "funding" | "irb_number" | "email_or_url" | "self_citation_pattern" | "named_artifact" | "other",
    "severity": "critical" | "major" | "minor",
    "quote": "<exact text from the manuscript>",
    "where": "<approximate location e.g. 'page 8 acknowledgements' or 'methods section'>",
    "fix": "<how to anonymise it for blinded submission>"
  },
  ...
]

If you find no concrete leaks, output an empty array [].
"""


async def run_anonymity_check(
    client,
    structure: PaperStructure,
) -> dict:
    """Run the anonymity-leak scan over the manuscript body + abstract.

    Structure fields are assumed to have already been sanitized by
    extract_paper(); we wrap them in fences here for defense in depth.
    """
    title = structure.title or "(not extracted)"
    abstract = structure.abstract or ""
    body = structure.body or ""
    user_text = (
        _safety.wrap_user_content(title, "manuscript_title") + "\n"
        + _safety.wrap_user_content(abstract, "abstract") + "\n\n"
        + _safety.wrap_user_content(body, "manuscript_body") + "\n\n"
        + "Scan for anonymity leaks and output the JSON array now."
    )
    try:
        raw = await _anthropic_message(
            client,
            system=_safety.SAFETY_PREAMBLE + "\n\n" + _ANONYMITY_SYSTEM,
            user_content=[{"type": "text", "text": user_text}],
            max_tokens=PERSONA_MAX_OUTPUT_TOKENS,
        )
    except Exception:
        logger.exception("anonymity check failed")
        return {"status": "error", "leaks": []}
    leaks = _parse_json_findings(raw)
    return {
        "status": "ok",
        "leaks": leaks,
        "n_critical": sum(1 for l in leaks if (l.get("severity") or "").lower() == "critical"),
        "n_total": len(leaks),
    }


# ---------------------------------------------------------------------------
# Citation Gap Analysis  ($5 standalone)
# ---------------------------------------------------------------------------

_CITATION_GAP_SYSTEM = """You are a domain expert tasked with finding
citations the manuscript SHOULD include but doesn't. Read the manuscript
body, identify the core claims and methods, then list prior work that:

- Directly precedes the manuscript's central claim (the "obvious" papers
  any expert reviewer would expect cited).
- Provides the canonical method baseline or framework the manuscript
  builds on.
- Reports a near-identical experiment or finding the authors should
  acknowledge (even if to differentiate).
- Is the foundational reference for a technique, dataset, or theoretical
  framework the manuscript uses without citation.

For each gap, output a JSON object. DO NOT make up paper titles or authors.
If you can't recall the specific paper but you know the area, describe the
gap qualitatively instead and tag it 'qualitative_gap'.

Output a JSON array (and ONLY a JSON array):
[
  {
    "gap_type": "missing_canonical_paper" | "missing_baseline" | "missing_prior_finding" | "missing_framework" | "qualitative_gap",
    "topic": "<one-line topic this gap covers>",
    "expected_work_description": "<what should be cited>",
    "candidate_authors": ["<author1>", ...],   // [] if unknown
    "candidate_title_hint": "<approximate title or 'unknown'>",
    "why_it_matters": "<what reviewer would flag the omission>",
    "where_in_paper": "<section name where the citation should appear>"
  },
  ...
]

Be conservative — list 3-10 high-confidence gaps. Don't pad. If everything
looks well-cited for the scope, return an empty array.
"""


async def _verify_gap_candidate(client, gap: dict) -> dict:
    """Best-effort CrossRef title search for one LLM-suggested gap.

    Mutates nothing — returns a NEW dict with a "verification" key attached.
    Never raises; a network failure just yields an "unverified" status so a
    single flaky lookup can't take down the whole report.
    """
    hint = (gap.get("candidate_title_hint") or "").strip()
    if not hint or hint.lower() in {"unknown", "n/a", "none"}:
        return {
            **gap,
            "verification": {"status": "not_searched", "reason": "no title hint provided"},
        }

    try:
        resp = await client.get(
            "https://api.crossref.org/works",
            params={
                "query.bibliographic": hint[:200],
                "rows": "1",
                "select": "title,DOI,author,issued",
                "mailto": "ben@purplelink.llc",
            },
            headers={
                "User-Agent": "purplelink-paper-review/1.0 (mailto:ben@purplelink.llc)",
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            return {
                **gap,
                "verification": {"status": "crossref_unavailable", "http_status": resp.status_code},
            }
        items = (resp.json().get("message") or {}).get("items") or []
        if not items:
            return {**gap, "verification": {"status": "not_found"}}
        item = items[0]
        found_title = (item.get("title") or [""])[0]
        confidence = _string_overlap(hint.lower(), found_title.lower())
        return {
            **gap,
            "verification": {
                "status": "confirmed_exists" if confidence >= 0.6 else "weak_match",
                "confidence": round(confidence, 2),
                "found_title": found_title,
                "found_doi": item.get("DOI", ""),
            },
        }
    except Exception:
        return {**gap, "verification": {"status": "network_error"}}


async def run_citation_gap(
    client,
    structure: PaperStructure,
) -> dict:
    """Find citations the manuscript should include but doesn't.

    The candidate list itself is knowledge-recall (Claude's training data
    proposes what's missing) — but every candidate with a concrete title
    hint is then checked live against CrossRef so the author isn't handed
    an unverified, possibly-hallucinated title. Gaps the model couldn't
    name (qualitative_gap, candidate_title_hint == "unknown") are left as
    "not_searched" rather than silently presented as verified.
    """
    references = structure.references or []
    refs_summary = "\n".join(f"- {r.raw[:200]}" for r in references[:80])
    n_total = structure.n_references_total or len(references)
    truncated = n_total > len(references)
    title = structure.title or "(not extracted)"
    abstract = structure.abstract or ""
    body = structure.body or ""
    user_text = (
        _safety.wrap_user_content(title, "manuscript_title") + "\n"
        + _safety.wrap_user_content(abstract, "abstract") + "\n\n"
        + _safety.wrap_user_content(
            f"Showing {len(references)} of {n_total} total references extracted "
            f"from the manuscript."
            + (
                " The list below is INCOMPLETE — treat any candidate gap as "
                "tentative if it might already be covered by a reference "
                "outside this excerpt."
                if truncated else ""
            )
            + f"\n{refs_summary}",
            "current_references",
        ) + "\n\n"
        + _safety.wrap_user_content(body, "manuscript_body") + "\n\n"
        + "Now identify the citation gaps and output the JSON array."
    )
    try:
        raw = await _anthropic_message(
            client,
            system=_safety.SAFETY_PREAMBLE + "\n\n" + _CITATION_GAP_SYSTEM,
            user_content=[{"type": "text", "text": user_text}],
            max_tokens=PERSONA_MAX_OUTPUT_TOKENS,
        )
    except Exception:
        logger.exception("citation gap analysis failed")
        return {"status": "error", "gaps": []}
    gaps = _parse_json_findings(raw)

    if gaps:
        verified = await asyncio.gather(
            *[_verify_gap_candidate(client, g) for g in gaps],
            return_exceptions=True,
        )
        gaps = [
            v if not isinstance(v, Exception) else g
            for v, g in zip(verified, gaps)
        ]

    n_confirmed = sum(
        1 for g in gaps if (g.get("verification") or {}).get("status") == "confirmed_exists"
    )
    return {
        "status": "ok",
        "gaps": gaps,
        "n_gaps": len(gaps),
        "n_confirmed": n_confirmed,
        "n_references_reviewed": len(references),
        "n_references_total": n_total,
        "references_truncated": truncated,
        # Distinguishes "well-cited paper, no gaps found" from "we found
        # nothing to check against" (extraction failure or a genuinely
        # uncited manuscript) — both would otherwise collapse into the
        # same empty-gaps result.
        "no_references_extracted": n_total == 0,
    }


# ---------------------------------------------------------------------------
# Revision Review  ($2 second-pass)
# ---------------------------------------------------------------------------

_REVISION_SYSTEM = """You are the senior reviewer evaluating whether the
authors successfully addressed the issues raised in a prior round of
review. You have:

- The ORIGINAL review (Markdown) from the previous pass.
- The REVISED manuscript (text + figures' captions).

BEFORE doing anything else, perform a match check:

- Does the original review's "Rectification Checklist" section (or an
  equivalent numbered list of required fixes) actually exist in the
  pasted review text?
- Does the original review appear to be ABOUT this manuscript — same
  general topic, claims, and terminology — rather than a review of some
  other, unrelated paper?

If EITHER check fails (no checklist/numbered-items section is present, OR
the review is clearly discussing a different manuscript: different title,
different subject matter, different core claims/methods), do NOT attempt
to force-fit checklist items onto this manuscript and do NOT fabricate an
Address Tracker. Instead output ONLY this Markdown, nothing else:

# Revision Review

## Mismatch Warning
MISMATCH_DETECTED: <one-line reason — "no rectification checklist found in
pasted review" or "original review appears to be for a different
manuscript (<what it seems to be about> vs. this paper's <topic>)">

Do not proceed to Address Tracker or New Issues Introduced sections in this
case.

Otherwise, if the match check passes, your job is TWO separate evaluations:

1. **Address tracker.** For every numbered item in the original review's
   "Rectification Checklist" section, determine whether the revision:
     - "addressed" (the fix is in place and looks adequate)
     - "partially_addressed" (some attempt; gaps remain)
     - "not_addressed" (no change visible)
     - "not_evaluable" (the revision didn't include enough information to
       judge)
   Quote the revision text that demonstrates the fix where possible.

2. **New issues.** Did the revision introduce NEW problems? Sometimes
   fixing one thing breaks another (e.g. adding an experiment whose stats
   weren't done; trimming text that removed key caveats). Flag at most 5
   new issues, with severity.

Output a single Markdown report with the following sections, in this order:

# Revision Review

## Summary
- One sentence on the overall verdict: ready-for-resubmission, needs-more-work,
  or substantial-changes-introduced-new-problems.
- One line counting addressed vs. not-addressed checklist items.

## Address Tracker
A table-like list. One bullet per original checklist item:
- **[A1] addressed:** <one-line evidence>
- **[A2] partially_addressed:** <one-line evidence + what's still missing>
- **[B1] not_addressed:** <why this matters; concrete action>
... and so on.

## New Issues Introduced
A short bulleted list (or "(none)" if nothing was introduced).

Constraints: quote the revision text exactly when claiming a fix.
No emojis, no marketing language. Output ONLY Markdown.
"""


# Matches the heading the original Paper Review report always emits for its
# rectification list — tolerant of "##"/"###" and minor wording drift, but
# still requires the actual "Rectification Checklist" phrase.
_RECTIFICATION_HEADING_RE = re.compile(
    r"^#{1,6}\s*rectification\s+checklist\b", re.IGNORECASE | re.MULTILINE,
)

# The model is instructed to emit this exact token when its own match check
# (title/topic vs. the uploaded manuscript) fails — see _REVISION_SYSTEM.
_MISMATCH_TOKEN_RE = re.compile(r"MISMATCH_DETECTED\s*:\s*(.+)")


async def run_revision_review(
    client,
    structure: PaperStructure,
    original_review_md: str,
) -> dict:
    """Second-pass evaluation: did the revision address the original review?

    `original_review_md` is pasted by the user and NOT verified to come
    from our previous output — so it gets the full sanitization treatment.

    Two layers guard against evaluating a review that doesn't belong to
    this manuscript (wrong paper, garbage text, or a review round that never
    had a checklist):

    1. A cheap server-side pre-flight: if the sanitized review text has no
       "Rectification Checklist" heading at all, we never call the LLM —
       there's nothing to track, and the model can't be trusted not to
       invent one. This also saves the API cost on an obviously bad input.
    2. A prompt-level self-check (_REVISION_SYSTEM): even when a checklist
       heading IS present, the model is required to verify the review is
       actually about this manuscript before producing an Address Tracker,
       and to emit a MISMATCH_DETECTED marker instead of fabricating one if
       not. We detect that marker here and surface it as its own status
       rather than "ok", so a mismatched review is never silently billed
       and presented as a normal report.
    """
    review_clean = _safety.safe_review_md(original_review_md or "").text

    if not _RECTIFICATION_HEADING_RE.search(review_clean):
        return {
            "status": "mismatch",
            "markdown": "",
            "error": (
                "The pasted original review doesn't contain a 'Rectification "
                "Checklist' section, so there's nothing to track against this "
                "revision. Paste the full review from your previous Paper "
                "Review report, or double-check you uploaded the right file."
            ),
        }

    title = structure.title or ""
    abstract = structure.abstract or ""
    body = structure.body or ""

    user_text = (
        _safety.wrap_user_content(review_clean, "original_review") + "\n\n"
        + _safety.wrap_user_content(title, "revised_manuscript_title") + "\n"
        + _safety.wrap_user_content(abstract, "revised_abstract") + "\n\n"
        + _safety.wrap_user_content(body, "revised_manuscript_body") + "\n\n"
        + "Produce the Markdown revision-review report now."
    )
    try:
        raw = await _anthropic_message(
            client,
            system=_safety.SAFETY_PREAMBLE + "\n\n" + _REVISION_SYSTEM,
            user_content=[{"type": "text", "text": user_text}],
            max_tokens=4_000,
        )
    except Exception:
        logger.exception("revision review failed")
        return {"status": "error", "markdown": ""}

    markdown = raw.strip()
    mismatch = _MISMATCH_TOKEN_RE.search(markdown)
    if mismatch:
        return {
            "status": "mismatch",
            "markdown": "",
            "error": (
                "This review doesn't appear to match the uploaded manuscript: "
                + mismatch.group(1).strip()
            ),
        }
    return {"status": "ok", "markdown": markdown}
