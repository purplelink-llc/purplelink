"""Resume Review — new paid product.

Input: a resume file (PDF or DOCX — resumes are commonly submitted as
either, unlike academic manuscripts which are near-universally PDF).
Output: a Markdown report from a three-persona panel:

  - ATS Screener: would an applicant-tracking system's parser choke on
    this file's formatting, and does it match the target role's likely
    keywords?
  - Hiring Manager Skeptic: does each bullet point make a quantified
    case, or is it generic duty-listing filler a hiring manager skims
    past in six seconds?
  - Recruiter Red Flags: career gaps, short stints, inconsistent dates,
    missing basics — framed as "here's what a recruiter's first pass
    would flag," not exhaustive HR-hostile scrutiny.

Unlike the academic Paper Review pipeline, this does NOT reuse
papercheck.extract_paper — resumes have no abstract, references, or
figures, so that extraction's structural assumptions don't apply. This
reuses doc2md's generic file-to-text conversion instead, the same one
the free word-counter tool uses.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from latextools.papercheck import (
    _anthropic_message,
    _parse_json_findings,
    PERSONA_MAX_OUTPUT_TOKENS,
)
from latextools import safety as _safety

logger = logging.getLogger(__name__)

MAX_RESUME_CHARS = 15_000  # resumes are 1-3 pages; this is generous headroom


# ---------------------------------------------------------------------------
# Persona prompts
# ---------------------------------------------------------------------------

_RESUME_ATS_SCREENER = """<persona name="ATS Screener">
You simulate how an Applicant Tracking System (ATS) parser would handle
this resume before a human ever sees it. Your job is to flag:

- Formatting that commonly breaks ATS parsing: multi-column layouts,
  tables, text boxes, headers/footers containing contact info, graphics
  or icons standing in for text, non-standard section headings.
- Missing or non-standard section headers (ATS systems look for
  conventional headers like "Experience," "Education," "Skills" — a
  creative header like "My Journey" instead of "Experience" can fail to
  parse into the right field).
- Date format inconsistency (ATS systems parse employment dates to
  compute tenure and gaps — inconsistent or missing month/year formats
  break this).
- Keyword sparsity relative to what the resume's own stated target role
  or industry would require (infer the likely target role from the
  content itself — do not assume a role you weren't told).

Output a JSON array of finding objects:
[
  {
    "issue_type": "formatting" | "section_headers" | "dates" | "keywords",
    "location": "<where in the resume, e.g. 'Experience section, Acme Corp entry'>",
    "issue": "<what would break or get missed>",
    "fix": "<concrete change>",
    "severity": "critical" | "major" | "minor"
  },
  ...
]

Be conservative — only flag things that would genuinely affect ATS
parsing or scoring, not stylistic preferences. Output ONLY the JSON
array. No preamble.
</persona>"""

_RESUME_HIRING_MANAGER = """<persona name="Hiring Manager Skeptic">
You are a hiring manager who reads dozens of resumes a week and skims
each one for about six seconds before deciding whether to read further.
Your default assumption is that a bullet point is generic filler until
it proves otherwise. Flag bullets that:

- Describe a duty or responsibility without a quantified outcome
  ("Managed a team" vs. "Managed a team of 6, cutting onboarding time
  40%").
- Use vague buzzwords with no supporting evidence ("detail-oriented,"
  "team player," "results-driven" with nothing backing the claim).
- Use weak or passive verbs ("Responsible for," "Helped with," "Worked
  on") where a stronger action verb would make the same claim more
  concrete.
- Fail to make clear WHY the reader should care — impact on revenue,
  cost, time, quality, or team, not just activity.
- Read as copy-pasted from a job description rather than the
  candidate's own actual work.

Output a JSON array of finding objects:
[
  {
    "bullet_quoted": "<the exact bullet or line flagged>",
    "issue": "<what's weak about it>",
    "suggested_rewrite": "<a stronger version using the same underlying facts — do not invent numbers or facts not in the original>",
    "severity": "critical" | "major" | "minor"
  },
  ...
]

Never invent a metric or fact the candidate didn't provide — if a bullet
needs a number to be convincing, say so in the issue field rather than
fabricating one in the rewrite. Output ONLY the JSON array.
</persona>"""

_RESUME_RECRUITER_REDFLAGS = """<persona name="Recruiter Red Flags">
You are a recruiter doing a first-pass screen. Your job is to flag
anything that would make you pause or ask a follow-up question before
moving the candidate forward — not to reject the resume, just to name
what would come up. Look for:

- Unexplained employment gaps of 6+ months.
- A pattern of short stints (multiple roles under ~12 months) without
  context suggesting contract/freelance work.
- Inconsistent or missing dates that make tenure hard to verify.
- Missing basics: no contact info, no location, no way to reach the
  candidate.
- Title or seniority regressions between consecutive roles without an
  obvious explanation (e.g. career change, return from leave).
- Overqualification or underqualification signals relative to the
  resume's apparent target level.

Output a JSON array of finding objects:
[
  {
    "flag_type": "employment_gap" | "short_stints" | "date_inconsistency" | "missing_info" | "title_regression" | "level_mismatch",
    "location": "<where in the resume>",
    "issue": "<what a recruiter would notice and ask about>",
    "suggested_fix": "<how to address it on the resume itself, e.g. a one-line explanation, not advice about the interview>",
    "severity": "critical" | "major" | "minor"
  },
  ...
]

Frame every finding as "here's what would come up," not as a judgment
about the candidate. Output ONLY the JSON array.
</persona>"""

_RESUME_SYNTHESIS_SYSTEM = """You are producing the final Markdown report
for someone who just paid for a resume review. You have:

- The resume's extracted text.
- ATS Screener findings (parsing/formatting/keyword issues).
- Hiring Manager Skeptic findings (weak bullets, generic filler).
- Recruiter Red Flags findings (gaps, stints, missing basics).

Produce a Markdown report with EXACTLY these sections:

# Resume Review

## Overall Verdict
Two or three sentences: would this resume clear an ATS filter and make
a hiring manager want to read further, or does it need work first? Be
direct — this report is only useful if it's honest.

## ATS Compatibility
List each ATS finding with its severity and fix. If none: "(no ATS
parsing issues found)".

## Content & Impact
List each Hiring Manager Skeptic finding — the weak bullet, why it's
weak, and the suggested rewrite. Group by resume section if there are
several.

## What a Recruiter Would Flag
List each Recruiter Red Flags finding. If none: "(no red flags found)".

## Action Checklist
An A/B/C priority list of concrete edits. [A] must-fix before sending
this out. [B] should-fix. [C] polish.

Constraints: quote the resume's own text when referencing a specific
bullet or section. Never invent facts, dates, or numbers not present in
the original resume — if a fix needs information you don't have, say
what's missing rather than making it up. No emojis. Output ONLY the
Markdown report.
"""


@dataclass
class ResumeReviewProgress:
    status: str = "running"
    progress_pct: int = 0
    stage: str = "extracting"   # extracting | panel | synthesizing | done
    started_at: float = 0.0
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result_md: Optional[str] = None


def extract_resume_text(file_bytes: bytes, filename: str) -> str:
    """Generic file-to-text conversion via doc2md — deliberately NOT
    papercheck.extract_paper, since resumes have no abstract/references/
    figures structure for that extractor to find."""
    from latextools import doc2md

    suffix = Path(filename).suffix or ".pdf"
    with tempfile.TemporaryDirectory() as d:
        in_path = Path(d) / f"resume{suffix}"
        in_path.write_bytes(file_bytes)
        text = doc2md.convert_to_markdown(str(in_path))
    return (text or "")[:MAX_RESUME_CHARS]


async def run_resume_review(
    file_bytes: bytes,
    filename: str,
    on_progress=None,
) -> dict:
    """End-to-end resume review. Mirrors response_review.run_response_review's
    shape: extract -> parallel persona panel -> synthesis -> Markdown report."""
    import time
    import json as _json
    import httpx

    progress = ResumeReviewProgress(
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

    try:
        resume_text = extract_resume_text(file_bytes, filename)
    except Exception as e:
        progress.status = "error"
        progress.error = f"extraction_failed: {type(e).__name__}"
        progress.finished_at = time.time()
        _emit()
        return {"status": "error", "error": progress.error}

    if not resume_text.strip():
        progress.status = "error"
        progress.error = "empty_resume"
        progress.finished_at = time.time()
        _emit()
        return {"status": "error", "error": "empty_resume"}

    sanitized = _safety.safe_resume_text(resume_text)
    if sanitized.suspicious_patterns:
        logger.warning("resume_review: injection patterns flagged: %s", sanitized.suspicious_patterns)
    clean = _safety.wrap_user_content(sanitized.text, "resume_text")

    progress.progress_pct = 20
    progress.stage = "panel"
    _emit()

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:

        async def _persona(persona_key: str, persona_prompt: str) -> dict:
            user_text = f"{persona_prompt}\n\n{clean}\n\nNow produce your JSON array."
            try:
                raw = await _anthropic_message(
                    client,
                    system=(
                        _safety.SAFETY_PREAMBLE + "\n\n"
                        + "You are part of a resume-review panel. Stay "
                        + "strictly in your assigned persona. Output a "
                        + "JSON array only."
                    ),
                    user_content=[{"type": "text", "text": user_text}],
                    max_tokens=PERSONA_MAX_OUTPUT_TOKENS,
                )
            except Exception:
                logger.exception("resume review persona %s failed", persona_key)
                return {"persona": persona_key, "findings": [], "status": "error"}
            findings = _parse_json_findings(raw)
            for f in findings:
                f["persona"] = persona_key
            return {"persona": persona_key, "findings": findings, "status": "ok"}

        ats_task = asyncio.create_task(_persona("ats_screener", _RESUME_ATS_SCREENER))
        hm_task = asyncio.create_task(_persona("hiring_manager_skeptic", _RESUME_HIRING_MANAGER))
        recruiter_task = asyncio.create_task(_persona("recruiter_red_flags", _RESUME_RECRUITER_REDFLAGS))
        ats, hm, recruiter = await asyncio.gather(ats_task, hm_task, recruiter_task)

        progress.progress_pct = 75
        progress.stage = "synthesizing"
        _emit()

        synth_user = (
            clean + "\n\n"
            + _safety.wrap_user_content(
                _json.dumps(ats.get("findings", []), indent=2)[:15_000],
                "ats_screener_findings",
            ) + "\n\n"
            + _safety.wrap_user_content(
                _json.dumps(hm.get("findings", []), indent=2)[:15_000],
                "hiring_manager_findings",
            ) + "\n\n"
            + _safety.wrap_user_content(
                _json.dumps(recruiter.get("findings", []), indent=2)[:15_000],
                "recruiter_red_flag_findings",
            ) + "\n\n"
            + "Produce the final Markdown report now."
        )
        try:
            md = await _anthropic_message(
                client,
                system=_safety.SAFETY_PREAMBLE + "\n\n" + _RESUME_SYNTHESIS_SYSTEM,
                user_content=[{"type": "text", "text": synth_user}],
                max_tokens=5_000,
            )
        except Exception:
            logger.exception("resume review synthesis failed")
            progress.status = "error"
            progress.error = "synthesis_failed"
            progress.finished_at = time.time()
            _emit()
            return {"status": "error", "error": "synthesis_failed"}

    progress.progress_pct = 100
    progress.stage = "done"
    progress.status = "done"
    progress.result_md = md.strip()
    progress.finished_at = time.time()
    _emit()
    return {
        "status": "done",
        "progress_pct": 100,
        "stage": "done",
        "result_md": md.strip(),
        "ats_findings": len(ats.get("findings", [])),
        "hiring_manager_findings": len(hm.get("findings", [])),
        "recruiter_findings": len(recruiter.get("findings", [])),
    }
