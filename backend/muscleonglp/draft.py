"""Initial LLM draft of the MuscleOnGLP flagship guide."""
from latextools.papercheck import _anthropic_message

from muscleonglp.sources import citation_block

MAX_DRAFT_TOKENS = 6000

_DRAFT_SYSTEM_PROMPT = """You are writing a short consumer health guide titled \
"Preserving Lean Mass on GLP-1 Therapy: A Resistance Training and Protein \
Protocol." Write in an academic, citation-forward register: precise, \
evidence-led, no marketing tone, no exclamation points, no emojis.

Every substantive claim must cite one of the sources below by its key in \
parentheses, e.g. "(step1_semaglutide)". Do not invent claims without a \
matching citation. If a source is marked [PREPRINT], say so explicitly in \
the sentence that cites it (e.g. "a preprint analysis suggests...").

Sources:
{citations}

Structure the guide with these sections: Introduction, Why Lean Mass Is at \
Risk, The Resistance Training Protocol, Protein Targets, A Note on Preprints \
and Evidence Quality, and a closing disclaimer that this is not medical \
advice and readers should consult their prescriber.

Output plain prose with section headings on their own line prefixed by \
"## ". Do not output LaTeX, HTML, or Markdown formatting beyond those \
headings."""


async def draft_guide(client) -> str:
    """Produce the initial LLM draft of the flagship guide's text."""
    system = _DRAFT_SYSTEM_PROMPT.format(citations=citation_block())
    return await _anthropic_message(
        client,
        system=system,
        user_content=[{"type": "text", "text": "Write the guide now."}],
        max_tokens=MAX_DRAFT_TOKENS,
    )
