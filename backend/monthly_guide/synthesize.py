"""Synthesize the month's weekly roundups into a cohesive consumer guide.

The output is the same "## Heading" plain-prose format that
``muscleonglp.typeset.render_guide_pdf`` consumes and that
``muscleonglp.redteam.run_redteam_passes`` reviews, so the monthly guide flows
through the exact same draft -> red-team -> typeset toolchain the flagship
guide uses.

IRON RULE (enforced in the system prompt): the model may use ONLY facts,
numbers, papers, and journals that appear in the provided roundup texts. Those
roundups are already citation-vetted by the weekly pipeline; the monthly guide
must not introduce a single new claim, statistic, or citation.
"""
from __future__ import annotations

from latextools.papercheck import _anthropic_message

# 6000 truncated the 2026-08 guide mid-sentence in its final section, which
# also silently dropped the "## Not Medical Advice" closing block the prompt
# below requires -- so the red team correctly refused a health guide with no
# disclaimer. The cap is the whole guide, not a section, so it needs real
# headroom.
MAX_SYNTH_TOKENS = 16000

_SYNTH_SYSTEM_PROMPT = """You are writing a short consumer health guide that \
reviews a single month of newly published research on GLP-1 medications \
(semaglutide, tirzepatide, and related incretin therapies) and their effect \
on muscle, lean mass, protein needs, and training. The guide is titled \
"{title}".

You are given the plain-text of every weekly research roundup published on \
MuscleOnGLP during {month_label}. Each roundup lists real, already \
citation-vetted papers with their journal, publication date, source link, an \
abstract-derived summary, and a note on why it matters.

This month's approved source list, each paper with its citation key, is:
{citations}

Every substantive claim, statistic, dosage, or finding must cite one of the \
sources above by its key in parentheses, e.g. "(p1)". Do not make a claim \
that lacks a matching citation key. If a source is marked [PREPRINT], say so \
explicitly in the sentence that cites it (e.g. "a preprint analysis \
suggests..."). When you state a finding, also attribute it to the paper by \
name and/or journal exactly as it appears in the roundups (for example, "a \
BMJ network meta-analysis (p1)" or "the EASO/EFAD/ECPO consensus statement \
(p2)").

IRON RULE: Use ONLY facts, numbers, papers, journals, and findings that \
appear in the roundup texts and approved source list below. Do NOT introduce \
any new paper, statistic, dosage, percentage, or claim that is not explicitly \
present in those texts. If the roundups do not support a point, do not make \
it. Never invent a citation or a citation key. Do not fabricate author lists, \
years, or DOIs.

Write in an academic, citation-forward, plain register: precise, evidence-led, \
no marketing tone, no buzzwords (streamline, supercharge, seamless, \
world-class), no em dashes, no exclamation points, no emojis. Do not promise \
guaranteed outcomes.

If any paper in the roundups is described as a preprint or as not yet \
peer-reviewed, say so explicitly in the sentence that cites it.

Structure the guide with these sections, each heading on its own line \
prefixed by "## ":
## Introduction  (what this month's research collectively shows)
## The Papers This Month  (walk through each cited study and what it found)
## What It Means for Preserving Muscle  (synthesize the practical takeaways \
that the cited evidence actually supports)
## Where the Evidence Is Still Thin  (name the limitations, preprints, and \
open questions the roundups flag)
## Not Medical Advice  (a closing disclaimer that this is educational, is not \
medical advice, and that readers should consult their prescribing clinician \
before changing exercise, nutrition, or medication)

Output plain prose with those "## " headings only. Do not output LaTeX, HTML, \
or Markdown formatting beyond the "## " headings. Do not wrap the output in a \
code fence."""


async def draft_monthly_guide(client, month_label: str, roundup_texts: list[str],
                              citations: str) -> str:
    """Draft the monthly review guide text from the month's roundup texts.

    *month_label* is a human label such as "July 2026". *roundup_texts* is the
    list of plain-text roundups (see ``roundups.Roundup.to_text``).
    *citations* is the keyed approved-source block from
    ``roundups.monthly_citation_block`` — the same block the red-team
    medical_safety pass checks against — so the draft tags each claim with a
    citation key the reviewer recognizes. Returns the guide body in the "##
    Heading" format the typeset/red-team stages expect.
    """
    title = f"GLP-1 & Muscle: Research Review, {month_label}"
    system = _SYNTH_SYSTEM_PROMPT.format(
        title=title, month_label=month_label, citations=citations)
    joined = "\n\n" + ("\n\n" + ("-" * 60) + "\n\n").join(roundup_texts)
    user = (
        "Here are all of this month's weekly research roundups. Synthesize "
        "them into the guide, using only what appears below:\n" + joined
    )
    # Retry once if the model returns an empty completion (transient Fable
    # behaviour); an empty synthesis is fatal downstream (red-team gets nothing).
    for _ in range(2):
        text = await _anthropic_message(
            client,
            system=system,
            user_content=[{"type": "text", "text": user}],
            max_tokens=MAX_SYNTH_TOKENS,
        )
        if (text or "").strip():
            return text
    raise RuntimeError("draft_monthly_guide: model returned an empty synthesis twice")
