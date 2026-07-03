"""AI-SCoRe — evaluate an empirical NCA (Necessary Condition Analysis) manuscript against the
SCoRe checklist (Strengthening / Conducting / Reporting) using generative AI.

Reconstructed from the public NCA materials at https://jandul.github.io/NCA/ (MIT-licensed).
The 42-item checklist and the exact scoring formula are ported verbatim from the source tool.

This module mirrors the structure of ``papercheck.run_review_pipeline`` and reuses its helpers
(``extract_paper``, ``_anthropic_message``, ``_parse_json_findings``) so AI-SCoRe can run as the
``nca`` domain of the review pipeline or via its own entry point.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from . import safety as _safety

logger = logging.getLogger("latextools.aiscore")

# ---------------------------------------------------------------------------
# Checklist data
# ---------------------------------------------------------------------------

_CHECKLIST_PATH = Path(__file__).with_name("score_checklist.json")

SECTION_TO_PHASE = {
    "Introduction/General": "Strengthening",
    "Theory/Hypotheses": "Strengthening",
    "Methods - data": "Conducting",
    "Methods - data analysis": "Conducting",
    "Results": "Reporting",
    "Discussion": "Reporting",
}

PHASE_SUBTITLE = {
    "Strengthening": "theoretical rigor",
    "Conducting": "data & analysis quality",
    "Reporting": "transparency",
}


def load_checklist() -> list[dict]:
    """Return the 42 SCoRe checklist items, each augmented with an ``id`` and ``phase``."""
    items = json.loads(_CHECKLIST_PATH.read_text(encoding="utf-8"))
    for it in items:
        it["id"] = f"{it['section']}#{it['number']}"
        it["phase"] = SECTION_TO_PHASE.get(it["section"], "Strengthening")
    return items


# ---------------------------------------------------------------------------
# Scoring — verbatim port of the source tool's calculateTotalScore
# ---------------------------------------------------------------------------

PUBLICATION_THRESHOLD = 60.0


def total_score(
    must_satisfied: int, must_total: int,
    should_satisfied: int, should_total: int,
    nice_satisfied: int, nice_total: int,
) -> float:
    """0–100 SCoRe score. Must-have items gate the 60 publication threshold; should/nice add
    up to 40 more, scaled by must-have completion. Capped at 59 unless all must-haves pass."""
    MUST_MAX, EXTRA_MAX = 60.0, 40.0
    must_fraction = (must_satisfied / must_total) if must_total > 0 else 0.0
    must_part = MUST_MAX * must_fraction
    should_weight, nice_weight = 2.0, 1.0
    weighted_done = should_satisfied * should_weight + nice_satisfied * nice_weight
    weighted_total = should_total * should_weight + nice_total * nice_weight
    extra_fraction = (weighted_done / weighted_total) if weighted_total > 0 else 0.0
    extra_base = EXTRA_MAX * extra_fraction
    activation = 0.10 + 0.90 * must_fraction
    total = must_part + extra_base * activation
    all_must_done = must_total > 0 and must_satisfied == must_total
    if not all_must_done:
        total = min(total, 59.0)
    return total


def score_from_verdicts(verdicts: dict[str, str], items: Optional[list[dict]] = None) -> dict:
    """Compute the score from an ``{id: "satisfied"|"notMet"|"notApplicable"}`` map.

    N/A and unjudged items are excluded from their priority's total.
    """
    items = items if items is not None else load_checklist()
    counts = {"Must-have": [0, 0], "Should-have": [0, 0], "Nice-to-have": [0, 0]}
    for it in items:
        v = verdicts.get(it["id"])
        bucket = counts.get(it["priority"])
        if bucket is None:
            continue
        if v == "satisfied":
            bucket[0] += 1
            bucket[1] += 1
        elif v == "notMet":
            bucket[1] += 1
        # notApplicable / None: excluded from total
    m, s, n = counts["Must-have"], counts["Should-have"], counts["Nice-to-have"]
    total = total_score(m[0], m[1], s[0], s[1], n[0], n[1])
    return {
        "total": round(total, 1),
        "publication_ready": total >= PUBLICATION_THRESHOLD,
        "must": {"satisfied": m[0], "total": m[1]},
        "should": {"satisfied": s[0], "total": s[1]},
        "nice": {"satisfied": n[0], "total": n[1]},
    }


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_CORE = (
    "You are AI-SCoRe, an expert evaluator of empirical Necessary Condition Analysis (NCA) "
    "studies. You assess a manuscript against the SCoRe checklist — Strengthening (theoretical "
    "rigor), Conducting (data & analysis quality), and Reporting (transparency). For EACH "
    "checklist item you are given, decide whether the manuscript satisfies it. Judge ONLY from "
    "the manuscript text provided; do not assume content that is not present.\n\n"
    "Return one verdict per item:\n"
    '- "satisfied": the manuscript clearly meets the item.\n'
    '- "notMet": the item is not met or is addressed incorrectly.\n'
    '- "notApplicable": the item genuinely does not apply to this study.\n\n'
    "Be critical but fair, grounding each rationale in the manuscript, and give a concrete, "
    "actionable improvement for every item that is not fully satisfied. NCA is a young method "
    "often applied incorrectly — flag terminology misuse and conceptual errors. Your output "
    "inspires the author's critical reflection; it is not a final verdict.\n\n"
    'Output ONLY a JSON array, each element: {"id": "<item id>", "verdict": '
    '"satisfied|notMet|notApplicable", "rationale": "<1-3 sentences>", '
    '"improvement": "<concrete suggestion, or empty if satisfied>"}'
)

SYSTEM = _safety.SAFETY_PREAMBLE + "\n\n" + _SYSTEM_CORE


def build_user_content(manuscript: str, items: list[dict]) -> list[dict]:
    compact = [
        {"id": it["id"], "section": it["section"], "priority": it["priority"],
         "question": it["question"], "recommendation": it["recommendation"]}
        for it in items
    ]
    sanitized_manuscript = _safety.safe_body(manuscript).text
    text = (
        "CHECKLIST ITEMS (evaluate every one, by id):\n"
        + json.dumps(compact, ensure_ascii=False)
        + "\n\n"
        + _safety.wrap_user_content(sanitized_manuscript, "manuscript_body")
        + "\n\n"
        "Return the JSON array of evaluations now — one element per checklist item id above."
    )
    return [{"type": "text", "text": text}]


def render_markdown(score: dict, evaluations: list[dict], items: list[dict]) -> str:
    by_id = {it["id"]: it for it in items}
    out = ["# AI-SCoRe Review\n"]
    ready = "meets" if score["publication_ready"] else "below"
    out.append(f"**Score: {int(round(score['total']))}/100** — {ready} the SCoRe publication "
               f"threshold (60).\n")
    out.append(f"- Must-have: {score['must']['satisfied']}/{score['must']['total']}  ·  "
               f"Should-have: {score['should']['satisfied']}/{score['should']['total']}  ·  "
               f"Nice-to-have: {score['nice']['satisfied']}/{score['nice']['total']}\n")
    for phase in ("Strengthening", "Conducting", "Reporting"):
        phase_evals = [e for e in evaluations
                       if by_id.get(e.get("id"), {}).get("phase") == phase]
        if not phase_evals:
            continue
        out.append(f"\n## {phase} ({PHASE_SUBTITLE[phase]})\n")
        for e in phase_evals:
            it = by_id.get(e.get("id"), {})
            mark = {"satisfied": "✓", "notMet": "✗"}.get(e.get("verdict"), "–")
            out.append(f"- {mark} **[{it.get('priority', '')}]** {it.get('question', e.get('id'))}")
            if e.get("rationale"):
                out.append(f"  - {e['rationale']}")
            if e.get("improvement"):
                out.append(f"  - → {e['improvement']}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

async def run_aiscore(
    pdf_bytes: bytes,
    on_progress=None,
    *,
    model: Optional[str] = None,
) -> dict:
    """Extract the manuscript, evaluate against the SCoRe checklist via Claude, and score it.

    Returns a dict: ``{status, score, evaluations, result_md, domain}``.
    """
    import time
    import httpx
    # Reuse papercheck's extractor + Anthropic helpers to stay consistent.
    from .papercheck import extract_paper, _anthropic_message, _parse_json_findings, DEFAULT_MODEL

    def _emit(pct, stage):
        if on_progress is not None:
            try:
                on_progress({"status": "running", "progress_pct": pct, "stage": stage})
            except Exception:
                logger.exception("on_progress callback raised")

    _emit(5, "extracting")
    try:
        structure = extract_paper(pdf_bytes)
    except Exception as e:
        logger.exception("paper extraction failed")
        return {
            "status": "error",
            "error": f"extraction_failed: {type(e).__name__}",
            "domain": "nca",
        }
    manuscript = "\n\n".join(p for p in [
        f"TITLE: {structure.title}" if structure.title else "",
        f"ABSTRACT: {structure.abstract}" if structure.abstract else "",
        structure.body,
    ] if p).strip()
    if not manuscript:
        return {"status": "error", "error": "empty_manuscript", "domain": "nca"}

    items = load_checklist()
    _emit(30, "evaluating")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0),
    ) as client:
        raw = await _anthropic_message(
            client,
            system=SYSTEM,
            user_content=build_user_content(manuscript, items),
            max_tokens=8192,
            model=model or DEFAULT_MODEL,
            temperature=0.1,
        )

    evaluations = _parse_json_findings(raw)
    verdicts = {e["id"]: e.get("verdict", "notMet") for e in evaluations if e.get("id")}
    score = score_from_verdicts(verdicts, items)
    _emit(95, "scoring")

    # status="done" + result_md match the shape run_review_pipeline returns, so the existing
    # job-status endpoint and polling UI consume AI-SCoRe results without changes.
    return {
        "status": "done",
        "stage": "done",
        "progress_pct": 100,
        "domain": "nca",
        "score": score,
        "evaluations": evaluations,
        "result_md": render_markdown(score, evaluations, items),
    }
