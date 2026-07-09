"""Four sequential red-team review passes over the drafted guide.

Order matters: medical_safety runs first. Because a pass that doesn't approve
is revised and re-run *in place* — the loop never restarts from
medical_safety — a later pass's edit can never silently undo an earlier
pass's safety-driven correction.
"""
import json
import re
from dataclasses import dataclass

from latextools.papercheck import _anthropic_message

from muscleonglp.sources import citation_block

MAX_ITERATIONS_PER_PASS = 3
MAX_REVISION_TOKENS = 6000
MAX_VERDICT_TOKENS = 1500

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
specific guaranteed outcome (e.g. "you will keep all your muscle").

Respond with ONLY a JSON object: {{"approved": bool, "edits": [str, ...]}}.""",
    "voice": """You are a voice/style reviewer. Confirm the text is written \
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
listed below. Preserve the overall structure, citation keys, and academic \
register. Output only the revised guide text (same "## " heading format), \
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
    """Parse a pass's JSON verdict. Tolerant of fenced code blocks. Treats
    unparseable output as NOT approved with a generic edit request, rather
    than raising — a malformed verdict must never silently pass content."""
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
    return PassVerdict(
        pass_name=pass_name,
        approved=bool(data.get("approved", False)),
        edits=[str(e) for e in data.get("edits", [])],
    )


async def _run_pass(client, pass_name: str, draft: str) -> PassVerdict:
    system = _PASS_SYSTEM_PROMPTS[pass_name].format(citations=citation_block())
    raw = await _anthropic_message(
        client,
        system=system,
        user_content=[{"type": "text", "text": draft}],
        max_tokens=MAX_VERDICT_TOKENS,
    )
    return _parse_verdict(raw, pass_name)


async def _revise_draft(client, draft: str, edits: list[str]) -> str:
    system = _REVISION_SYSTEM_PROMPT.format(edits="\n".join(f"- {e}" for e in edits))
    return await _anthropic_message(
        client,
        system=system,
        user_content=[{"type": "text", "text": draft}],
        max_tokens=MAX_REVISION_TOKENS,
    )


async def run_redteam_passes(client, draft: str) -> tuple[str, list[PassVerdict]]:
    """Run all four red-team passes in PASS_ORDER against *draft*, revising
    and re-running a pass (never restarting from the first pass) until it
    approves or MAX_ITERATIONS_PER_PASS is exhausted.

    Returns (final_text, verdicts) — verdicts holds each pass's final
    approving PassVerdict, in PASS_ORDER.
    """
    current = draft
    final_verdicts: list[PassVerdict] = []
    for pass_name in PASS_ORDER:
        verdict = await _run_pass(client, pass_name, current)
        attempts = 1
        while not verdict.approved:
            if attempts >= MAX_ITERATIONS_PER_PASS:
                raise RedTeamExhaustedError(
                    f"Pass '{pass_name}' did not approve after "
                    f"{MAX_ITERATIONS_PER_PASS} attempts. Last edits: {verdict.edits}"
                )
            current = await _revise_draft(client, current, verdict.edits)
            verdict = await _run_pass(client, pass_name, current)
            attempts += 1
        final_verdicts.append(verdict)
    return current, final_verdicts
