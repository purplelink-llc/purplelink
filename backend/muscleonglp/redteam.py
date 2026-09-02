"""Four sequential red-team review passes over the drafted guide.

Order matters: medical_safety runs first. Because a pass that doesn't approve
is revised and re-run *in place* — the loop never restarts from
medical_safety — a later pass's edit can never silently undo an earlier
pass's safety-driven correction by way of that pass being re-litigated. As an
additional guard against a later pass's revision regressing something
medical_safety already required (e.g. a disclaimer), medical_safety is
re-verified once more after all four passes complete; if it no longer
approves, it is resolved the same bounded way as the main loop rather than
shipping a regressed draft.
"""
import json
import logging
import re
from dataclasses import dataclass

from latextools.papercheck import _anthropic_message

from muscleonglp.sources import citation_block

logger = logging.getLogger(__name__)

# 3 was too few for the monthly guide, which is assembled from ~27 sources and
# so gives medical_safety far more citation surface to check than the flagship
# guide's fixed set. Two 2026-08 runs were refused with the objections getting
# finer each round -- structural on the first, then two precise citation-support
# points -- i.e. the reviser was converging and simply ran out of attempts.
# This raises the number of revision rounds only. The approval bar is unchanged
# and an unfixable draft still fails rather than shipping.
MAX_ITERATIONS_PER_PASS = 6
# A revision rewrites the WHOLE document, so this ceiling has to be at least as
# large as the synthesis ceiling or every revision silently truncates the draft
# back down to it. That is exactly what happened on 2026-08: raising
# MAX_SYNTH_TOKENS to 16000 fixed the first draft, and then the first revision
# cut it to 6000 again, so medical_safety kept reporting a truncated conclusion
# no matter how many rounds it was given.
MAX_REVISION_TOKENS = 16000
MAX_VERDICT_TOKENS = 4000  # a first-pass verdict can enumerate many edits; 1500 truncated the JSON

PASS_ORDER = ["medical_safety", "legal_compliance", "voice", "originality"]

_PASS_SYSTEM_PROMPTS = {
    "medical_safety": """You are a medical/safety reviewer for a consumer \
health guide about resistance training and protein intake during GLP-1 \
therapy. Verify every claim against the source list below; flag any claim \
that is unsupported, overstated, or missing its citation key. Flag if the \
guide is missing a "not medical advice, consult your prescriber" \
disclaimer.

Sources:
{citations}

Respond with ONLY a JSON object: {{"approved": bool, "edits": [str, ...]}}. \
"edits" is a list of specific required changes (empty list if approved).""",
    "legal_compliance": """You are an FTC/legal compliance reviewer for a \
consumer health product. Flag any deceptive or implied-medical-endorsement \
health claim, any missing or inadequate disclaimer, and any claim of a \
specific guaranteed outcome (e.g. "you will keep all your muscle"). Note: \
this pass and the medical_safety pass both check for a disclaimer — that \
overlap is intentional (medical-claim substantiation vs. FTC-adequacy of \
the disclaimer's wording are distinct concerns), not duplicate work to be \
removed.

Respond with ONLY a JSON object: {{"approved": bool, "edits": [str, ...]}}.""",
    "voice": """You are reviewing an educational research summary about GLP-1 \
medications and muscle mass, written for a general audience and sourced \
entirely from peer-reviewed papers. Your review covers WRITING STYLE ONLY; \
other reviewers handle clinical accuracy and compliance separately. \
Confirm the text is written \
in an academic, citation-forward, plain register: no marketing buzzwords \
(streamline, supercharge, seamless, world-class), no em dashes, no \
aphoristic "serious statement, then punchy negation" cadence, no emojis, no \
exclamation points.

Respond with ONLY a JSON object: {{"approved": bool, "edits": [str, ...]}}.""",
    "originality": """You are an originality reviewer. Compare this draft \
against the general shape of existing published GLP-1 exercise content from \
health publishers and personal-training studios. Flag any passage that reads \
as derivative of, or too close in structure or phrasing to, generic existing \
guidance rather than a distinct synthesis of the cited sources.

Respond with ONLY a JSON object: {{"approved": bool, "edits": [str, ...]}}.""",
}

_REVISION_SYSTEM_PROMPT = """You are revising a consumer health guide draft \
to address specific required edits from a review pass. Apply every edit \
listed below. Preserve the overall structure, citation keys, academic \
register, and any medical disclaimer already present in the draft — never \
remove or weaken a disclaimer or a citation-grounded claim while addressing \
these edits. Output only the revised guide text (same "## " heading format), \
nothing else.

Required edits:
{edits}"""


@dataclass
class PassVerdict:
    pass_name: str
    approved: bool
    edits: list[str]


class RedTeamExhaustedError(RuntimeError):
    """Raised when a pass still hasn't approved after
    MAX_ITERATIONS_PER_PASS revision attempts — a human needs to look at
    this guide, not loop forever."""


def _parse_verdict(raw: str, pass_name: str) -> PassVerdict:
    """Parse a pass's JSON verdict. Tolerant of fenced code blocks and of
    wrong-typed fields (e.g. "approved": "no", or "edits": null) — a
    malformed or wrong-shaped verdict must never crash the pipeline or be
    silently treated as an approval. Only an *exact* JSON `true` for
    "approved" counts as approved; anything else (including a truthy
    string) is treated as not approved."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end < start:
        return PassVerdict(
            pass_name, False, ["Reviewer response was not valid JSON; re-run this pass."]
        )
    try:
        data = json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return PassVerdict(
            pass_name, False, ["Reviewer response was not valid JSON; re-run this pass."]
        )
    if not isinstance(data, dict):
        return PassVerdict(
            pass_name, False, ["Reviewer response was not a JSON object; re-run this pass."]
        )
    approved = data.get("approved") is True
    raw_edits = data.get("edits", [])
    edits = [str(e) for e in raw_edits] if isinstance(raw_edits, list) else []
    if not approved and not edits:
        edits = ["Reviewer did not approve but returned no specific edits; re-run this pass."]
    return PassVerdict(pass_name=pass_name, approved=approved, edits=edits)


async def _run_pass(client, pass_name: str, draft: str,
                    citations: str | None = None) -> PassVerdict:
    if not (draft or "").strip():
        raise RuntimeError(f"redteam {pass_name}: received an empty draft to review "
                           "(synthesis returned nothing)")
    if citations is None:
        citations = citation_block()
    system = _PASS_SYSTEM_PROMPTS[pass_name].format(citations=citations)
    # Same empty-completion hiccup _revise_draft already guards against, which
    # hits the verdict call too. Without a retry an empty response parses as
    # "not valid JSON", counts as a rejection, triggers a revision that is also
    # empty, and burns the entire iteration budget on a transient blip -- the
    # 2026-08 'voice' pass failed all 6 rounds this way without ever producing
    # a real objection. Retry before treating silence as a verdict.
    raw = ""
    for attempt in range(3):
        raw = await _anthropic_message(
            client,
            system=system,
            user_content=[{"type": "text", "text": draft}],
            max_tokens=MAX_VERDICT_TOKENS,
        )
        if (raw or "").strip():
            break
        logger.warning("redteam %s: empty verdict response (attempt %d/3)",
                       pass_name, attempt + 1)
    if not (raw or "").strip():
        # An empty body here is not a verdict. In the 2026-08 run it was
        # stop_reason='refusal' with zero content blocks -- the model declining
        # the request outright. Parsing that as "not valid JSON" turned a
        # refusal into a rejection, which triggered a revision, which was
        # reviewed and refused again, consuming the whole iteration budget
        # while never producing a single real objection. Fail loudly instead:
        # a reviewer that will not answer is an operational fault, not a draft
        # that needs another rewrite.
        raise RuntimeError(
            f"redteam {pass_name}: the reviewer returned no content after 3 attempts "
            "(see the anthropic empty-text-response log for stop_reason; a refusal "
            "will not resolve by revising the draft)"
        )
    verdict = _parse_verdict(raw, pass_name)
    if not verdict.approved and any(
        "not valid JSON" in e or "not a JSON object" in e for e in verdict.edits
    ):
        logger.warning("redteam %s: unparseable verdict (%d chars): %r",
                       pass_name, len(raw), raw[:500])
    return verdict


async def _revise_draft(client, draft: str, edits: list[str]) -> str:
    system = _REVISION_SYSTEM_PROMPT.format(edits="\n".join(f"- {e}" for e in edits))
    # Fable occasionally returns an empty completion. Retry once (a transient
    # hiccup usually clears), then fall back to keeping the prior draft — never
    # let an empty response blank it, which would send an empty content block on
    # the next pass (Anthropic 400) and crash the unattended run.
    for attempt in range(2):
        revised = await _anthropic_message(
            client,
            system=system,
            user_content=[{"type": "text", "text": draft}],
            max_tokens=MAX_REVISION_TOKENS,
        )
        if (revised or "").strip():
            return revised
        logger.warning("redteam: empty revision (attempt %d/2, edits=%r)", attempt + 1, edits[:3])
    logger.warning("redteam: empty revision persisted; keeping prior draft")
    return draft


async def _run_pass_until_approved(client, pass_name: str, draft: str,
                                   citations: str | None = None) -> tuple[str, PassVerdict]:
    """Run *pass_name* against *draft*, revising and re-running the same
    pass (never a different pass) until it approves or
    MAX_ITERATIONS_PER_PASS is exhausted. Returns (possibly-revised draft,
    final approving verdict)."""
    current = draft
    verdict = await _run_pass(client, pass_name, current, citations)
    attempts = 1
    while not verdict.approved:
        if attempts >= MAX_ITERATIONS_PER_PASS:
            raise RedTeamExhaustedError(
                f"Pass '{pass_name}' did not approve after "
                f"{MAX_ITERATIONS_PER_PASS} attempts. Last edits: {verdict.edits}"
            )
        current = await _revise_draft(client, current, verdict.edits)
        verdict = await _run_pass(client, pass_name, current, citations)
        attempts += 1
    return current, verdict


async def run_redteam_passes(client, draft: str,
                             citations: str | None = None) -> tuple[str, list[PassVerdict]]:
    """Run all four red-team passes in PASS_ORDER against *draft*. Then
    re-verify medical_safety once more, since a later pass's revision could
    in principle regress something medical_safety already required (e.g. a
    disclaimer) — if it no longer approves, resolve it the same bounded way
    rather than shipping a regressed draft.

    Returns (final_text, verdicts) — verdicts holds each pass's final
    approving PassVerdict, in PASS_ORDER order (verdicts[0] is the
    post-recheck medical_safety verdict).

    *citations* is the approved-source block the medical_safety pass checks
    claims against. When None it falls back to the flagship guide's fixed
    ``citation_block()`` (so the flagship pipeline is unchanged); the monthly
    guide passes its own month-specific source block instead.
    """
    current = draft
    final_verdicts: list[PassVerdict] = []
    for pass_name in PASS_ORDER:
        current, verdict = await _run_pass_until_approved(client, pass_name, current, citations)
        final_verdicts.append(verdict)

    current, safety_recheck = await _run_pass_until_approved(
        client, "medical_safety", current, citations)
    final_verdicts[0] = safety_recheck
    return current, final_verdicts
