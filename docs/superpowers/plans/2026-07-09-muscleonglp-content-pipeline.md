# MuscleOnGLP Content Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the one-time content-production pipeline that drafts the MuscleOnGLP
flagship guide with an LLM, red-teams it through four sequential review passes, and
typesets the approved text into a sellable PDF.

**Architecture:** A new `backend/muscleonglp/` package with one module per pipeline
stage — `sources.py` (citation bank), `draft.py` (initial LLM draft), `redteam.py`
(four-pass review-and-revise loop), `typeset.py` (LaTeX/latexmk PDF rendering), and
`pipeline.py` (the orchestrator tying all three stages together). This is Plan 1 of 3
for MuscleOnGLP (spec: `docs/superpowers/specs/2026-07-09-muscleonglp-design.md`) — the
site (Plan 2) and Stripe/email fulfillment (Plan 3) both depend on this plan producing a
real PDF first.

**Tech Stack:** Python 3.12, `httpx.AsyncClient` (caller-managed lifecycle, matching
existing convention), Anthropic Messages API via the existing
`latextools.papercheck._anthropic_message` helper (reused, not reimplemented), the
existing `latextools.runner`/`latextools.core` LaTeX-via-`latexmk` subprocess pipeline
(this repo has no WeasyPrint/reportlab dependency — LaTeX is the only typesetting path
that exists), pytest + pytest-asyncio (already installed; no new dev dependency needed).

---

## Before You Start

This plan assumes you're working in an isolated git worktree (per
`superpowers:using-git-worktrees`), not directly on `main`. Confirm you're in a
worktree before starting Task 1.

Run the existing backend test suite once to confirm a clean baseline:

```bash
cd backend && python3 -m pytest tests/ -q
```

Expected: all tests pass (no failures), possibly with some skips for
`latexmk`-dependent tests if `latexmk` isn't installed locally (that's fine — those
tests run for real inside the Modal image; Task 4 below explains how to check).

---

### Task 1: Package skeleton + citation source registry

**Files:**
- Create: `backend/muscleonglp/__init__.py`
- Create: `backend/muscleonglp/sources.py`
- Test: `backend/tests/test_muscleonglp_sources.py`

This task builds the citation bank every later stage depends on: a fixed, structured
list of the real sources gathered during brainstorming (STEP 1, SURMOUNT-1, the
routine-care preprint, the protein-intake RCTs, ACSM guidance, and the active
NCT06885736 trial). Keeping citations as data — not prose an LLM has to recall from
training — means both the draft prompt and the medical-accuracy red-team pass reference
the exact same numbers, so they can't drift apart from each other.

- [ ] **Step 1: Write the failing tests**

Create `backend/muscleonglp/__init__.py` as an empty file first (needed for the package
to be importable at all):

```python
```

Then write `backend/tests/test_muscleonglp_sources.py`:

```python
from muscleonglp.sources import CITATIONS, citation_block


def test_all_citations_have_a_real_url():
    for c in CITATIONS.values():
        assert c.url.startswith("https://")


def test_citation_dict_key_matches_citation_key_field():
    for key, c in CITATIONS.items():
        assert c.key == key


def test_preprint_is_flagged_in_the_rendered_block():
    block = citation_block()
    assert "[PREPRINT]" in block
    assert "routine_care_lbm_preprint" in block


def test_non_preprint_is_not_flagged():
    block = citation_block()
    # The line for step1_semaglutide must not carry the preprint tag.
    for line in block.splitlines():
        if "step1_semaglutide" in line:
            assert "[PREPRINT]" not in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'muscleonglp.sources'`

- [ ] **Step 3: Write the implementation**

Create `backend/muscleonglp/sources.py`:

```python
"""Citation bank for the MuscleOnGLP flagship guide.

Every claim the guide makes must trace back to one of these entries. Citations
are kept as structured data (not prose an LLM has to recall) so the initial
draft prompt and the medical-accuracy red-team pass reference the exact same
grounding text — neither can drift from the other.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    key: str
    citation_text: str
    url: str
    is_preprint: bool = False


CITATIONS: dict[str, Citation] = {
    "step1_semaglutide": Citation(
        key="step1_semaglutide",
        citation_text=(
            "Neeland IJ, et al. Changes in lean body mass with glucagon-like "
            "peptide-1-based therapies and mitigation strategies. Diabetes Obes "
            "Metab. 2024. STEP 1 exploratory analysis: semaglutide reduced lean "
            "mass by approximately 13.2% from baseline, accounting for 45.2% of "
            "total weight lost."
        ),
        url="https://dom-pubs.onlinelibrary.wiley.com/doi/10.1111/dom.15728",
    ),
    "surmount1_tirzepatide": Citation(
        key="surmount1_tirzepatide",
        citation_text=(
            "SURMOUNT-1 trial: tirzepatide reduced lean mass by approximately "
            "10.9% from baseline, accounting for 25.7% of total weight lost — a "
            "meaningfully lower fraction than semaglutide's 45.2%."
        ),
        url="https://dom-pubs.onlinelibrary.wiley.com/doi/10.1111/dom.15728",
    ),
    "routine_care_lbm_preprint": Citation(
        key="routine_care_lbm_preprint",
        citation_text=(
            "Routine-care digital-phenotyping analysis: tirzepatide associated "
            "with greater relative lean-body-mass loss than semaglutide at "
            "3/6/9/12 months (excess losses of 1.1%, 1.5%, 1.3%, and 2.0%). "
            "PREPRINT — not yet peer-reviewed; must be labeled as such wherever "
            "cited."
        ),
        url="https://www.medrxiv.org/content/10.64898/2026.04.11.26350687v1",
        is_preprint=True,
    ),
    "protein_target_rct": Citation(
        key="protein_target_rct",
        citation_text=(
            "Higher-protein intake (1.6-2.4 g/kg bodyweight/day) during weight "
            "loss supports lean-mass retention, consistent across multiple "
            "randomized controlled trials of resistance-trained and untrained "
            "populations."
        ),
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC9012799/",
    ),
    "acsm_resistance_guidance": Citation(
        key="acsm_resistance_guidance",
        citation_text=(
            "ACSM resistance-training guidance: 2-3 sessions per week, 8-12 "
            "exercises per session, 2-3 sets of 8-15 reps at 60-80% of one-rep "
            "max."
        ),
        url="https://www.moveyourbonespt.com/blog/2026-acsm-resistance-training-guidelines",
    ),
    "nct06885736_active_trial": Citation(
        key="nct06885736_active_trial",
        citation_text=(
            "NCT06885736 — 'LEAN Mass Preservation With Resistance Exercise and "
            "Protein During Semaglutide/Tirzepatide Therapy' — an actively "
            "enrolling registered clinical trial addressing this exact "
            "question, evidence this is a live area of clinical research."
        ),
        url="https://clinicaltrials.gov/study/NCT06885736",
    ),
}


def citation_block() -> str:
    """Render all citations as one text block for LLM prompts."""
    lines = []
    for c in CITATIONS.values():
        prefix = "[PREPRINT] " if c.is_preprint else ""
        lines.append(f"- ({c.key}) {prefix}{c.citation_text} [{c.url}]")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_sources.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/muscleonglp/__init__.py backend/muscleonglp/sources.py backend/tests/test_muscleonglp_sources.py
git commit -m "feat(muscleonglp): add package skeleton and citation source registry"
```

---

### Task 2: Initial LLM draft

**Files:**
- Create: `backend/muscleonglp/draft.py`
- Test: `backend/tests/test_muscleonglp_draft.py`

Calls the existing `latextools.papercheck._anthropic_message` helper (same retry/
fallback/usage-tracking behavior every other tool in this repo already gets for free)
with a system prompt that requires every claim to cite a citation key from Task 1's
bank, and to explicitly flag any `[PREPRINT]`-tagged source as a preprint in the
sentence that cites it.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_muscleonglp_draft.py`:

```python
import httpx
import pytest

from muscleonglp import draft


class _Resp:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {
            "content": [{"type": "text", "text": "## Introduction\nok"}]
        }
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeClient:
    def __init__(self, sequence):
        self._seq = list(sequence)
        self.calls = 0
        self.last_body = None

    async def post(self, url, json=None, headers=None):
        self.calls += 1
        self.last_body = json
        item = self._seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")


@pytest.mark.asyncio
async def test_draft_guide_returns_the_model_text():
    client = _FakeClient([_Resp(200)])
    out = await draft.draft_guide(client)
    assert out == "## Introduction\nok"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_draft_guide_prompt_includes_citation_keys():
    client = _FakeClient([_Resp(200)])
    await draft.draft_guide(client)
    assert "step1_semaglutide" in client.last_body["system"]


@pytest.mark.asyncio
async def test_draft_guide_prompt_flags_preprints():
    client = _FakeClient([_Resp(200)])
    await draft.draft_guide(client)
    assert "[PREPRINT]" in client.last_body["system"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_draft.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'muscleonglp.draft'`

- [ ] **Step 3: Write the implementation**

Create `backend/muscleonglp/draft.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_draft.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/muscleonglp/draft.py backend/tests/test_muscleonglp_draft.py
git commit -m "feat(muscleonglp): add initial LLM guide draft stage"
```

---

### Task 3: Four-pass red-team review loop

**Files:**
- Create: `backend/muscleonglp/redteam.py`
- Test: `backend/tests/test_muscleonglp_redteam.py`

Runs `medical_safety`, `legal_compliance`, `voice`, and `originality` passes in that
exact order. Order matters: per the design spec's error-handling section, a conflict
between the safety pass and a later pass must resolve in favor of safety, which this
loop guarantees structurally — `medical_safety` finishes (and its edits are already
baked into the draft) before any later pass gets a chance to suggest something that
might undo it. If a pass doesn't approve, the draft is revised and *that same pass* is
re-run (never restarting from `medical_safety`), capped at `MAX_ITERATIONS_PER_PASS` to
avoid looping forever on a pass that never approves.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_muscleonglp_redteam.py`:

```python
import json

import httpx
import pytest

from muscleonglp import redteam


class _Resp:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {"content": [{"type": "text", "text": "ok"}]}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def _verdict_resp(approved, edits=None):
    body = json.dumps({"approved": approved, "edits": edits or []})
    return _Resp(200, {"content": [{"type": "text", "text": body}]})


def _text_resp(text):
    return _Resp(200, {"content": [{"type": "text", "text": text}]})


class _FakeClient:
    def __init__(self, sequence):
        self._seq = list(sequence)
        self.calls = 0

    async def post(self, *args, **kwargs):
        self.calls += 1
        item = self._seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")


def test_parse_verdict_handles_fenced_json():
    raw = '```json\n{"approved": true, "edits": []}\n```'
    verdict = redteam._parse_verdict(raw, "medical_safety")
    assert verdict.approved is True
    assert verdict.edits == []


def test_parse_verdict_treats_malformed_json_as_not_approved():
    verdict = redteam._parse_verdict("not json at all", "voice")
    assert verdict.approved is False
    assert verdict.edits  # non-empty — a generic re-run request


@pytest.mark.asyncio
async def test_run_redteam_passes_all_approve_first_try():
    client = _FakeClient([_verdict_resp(True) for _ in redteam.PASS_ORDER])
    final_text, verdicts = await redteam.run_redteam_passes(client, "draft text")
    assert final_text == "draft text"
    assert [v.pass_name for v in verdicts] == redteam.PASS_ORDER
    assert all(v.approved for v in verdicts)
    assert client.calls == len(redteam.PASS_ORDER)


@pytest.mark.asyncio
async def test_run_redteam_passes_revises_then_approves():
    sequence = [
        _verdict_resp(False, ["fix citation"]),  # medical_safety: fails
        _text_resp("revised draft"),               # revision call
        _verdict_resp(True),                        # medical_safety: re-run, approves
        _verdict_resp(True),                        # legal_compliance
        _verdict_resp(True),                        # voice
        _verdict_resp(True),                        # originality
    ]
    client = _FakeClient(sequence)
    final_text, verdicts = await redteam.run_redteam_passes(client, "draft text")
    assert final_text == "revised draft"
    assert verdicts[0].pass_name == "medical_safety"
    assert client.calls == 6


@pytest.mark.asyncio
async def test_run_redteam_passes_raises_after_max_iterations():
    sequence = [
        _verdict_resp(False, ["edit 1"]),
        _text_resp("draft v2"),
        _verdict_resp(False, ["edit 2"]),
        _text_resp("draft v3"),
        _verdict_resp(False, ["edit 3"]),
    ]
    client = _FakeClient(sequence)
    with pytest.raises(redteam.RedTeamExhaustedError):
        await redteam.run_redteam_passes(client, "draft text")
    assert client.calls == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_redteam.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'muscleonglp.redteam'`

- [ ] **Step 3: Write the implementation**

Create `backend/muscleonglp/redteam.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_redteam.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/muscleonglp/redteam.py backend/tests/test_muscleonglp_redteam.py
git commit -m "feat(muscleonglp): add four-pass red-team review loop"
```

---

### Task 4: PDF typesetting

**Files:**
- Create: `backend/muscleonglp/typeset.py`
- Test: `backend/tests/test_muscleonglp_typeset.py`

There is no WeasyPrint/reportlab dependency anywhere in this repo — the only
battle-tested PDF-production path is `latextools.runner.run_compile()`, which shells
out to `latexmk` (the same mechanism the manuscript-review tools use). This task wraps
that in a guide-specific LaTeX template, converting the `"## Heading"` plain-text
format the draft/red-team stages use into `\section*{}` commands and escaping LaTeX
special characters in the body text.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_muscleonglp_typeset.py`:

```python
import shutil

import pytest

from muscleonglp import typeset

has_latexmk = pytest.mark.skipif(
    shutil.which("latexmk") is None,
    reason="latexmk not installed (run inside the Modal image)",
)


def test_escape_latex_handles_special_chars():
    assert typeset._escape_latex("100% & $5_guide") == r"100\% \& \$5\_guide"


def test_body_to_latex_converts_headings_and_preserves_body():
    text = "## Introduction\nSome text.\n\n## Protein Targets\nMore text."
    out = typeset._body_to_latex(text)
    assert r"\section*{Introduction}" in out
    assert r"\section*{Protein Targets}" in out
    assert "Some text." in out
    assert "More text." in out


@has_latexmk
def test_render_guide_pdf_produces_a_real_pdf(tmp_path):
    output_path = tmp_path / "guide.pdf"
    text = "## Introduction\nThis is a test guide with a 1.6 g/kg protein target."
    result = typeset.render_guide_pdf(text, output_path)
    assert result == output_path
    assert output_path.read_bytes()[:4] == b"%PDF"


@has_latexmk
def test_render_guide_pdf_raises_on_compile_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        typeset,
        "_TEX_TEMPLATE",
        "\\documentclass{article}\n\\begin{document}\n\\undefinedcommand\n%s\n\\end{document}\n",
    )
    output_path = tmp_path / "guide.pdf"
    with pytest.raises(RuntimeError):
        typeset.render_guide_pdf("## Intro\ntext", output_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_typeset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'muscleonglp.typeset'`

- [ ] **Step 3: Write the implementation**

Create `backend/muscleonglp/typeset.py`:

```python
"""Typeset the red-teamed guide text into a PDF via the existing LaTeX
toolchain. This repo has no WeasyPrint/reportlab dependency, so a one-off
guide reuses the same latexmk-subprocess path the manuscript tools already
rely on (backend/latextools/runner.py)."""
import tempfile
from pathlib import Path

from latextools import runner

ENGINE = "pdflatex"
COMPILE_TIMEOUT_SECONDS = 60

_LATEX_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape_latex(text: str) -> str:
    return "".join(_LATEX_SPECIAL_CHARS.get(ch, ch) for ch in text)


def _body_to_latex(text: str) -> str:
    """Convert the guide's "## Heading" plain-text format into LaTeX,
    escaping everything else. Blank lines become paragraph breaks."""
    lines = []
    for line in text.splitlines():
        if line.startswith("## "):
            lines.append(f"\\section*{{{_escape_latex(line[3:].strip())}}}")
        elif line.strip() == "":
            lines.append("")
        else:
            lines.append(_escape_latex(line))
    return "\n".join(lines)


_TEX_TEMPLATE = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=1in]{geometry}
\usepackage{parskip}
\title{Preserving Lean Mass on GLP-1 Therapy}
\author{MuscleOnGLP}
\date{}
\begin{document}
\maketitle
%s
\end{document}
"""


def render_guide_pdf(text: str, output_path: Path) -> Path:
    """Typeset *text* (the "## "-headed guide format) into a PDF at
    *output_path*. Raises RuntimeError if the LaTeX compile fails."""
    tex_source = _TEX_TEMPLATE % _body_to_latex(text)
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        result = runner.run_compile(workdir, tex_source, ENGINE, COMPILE_TIMEOUT_SECONDS)
        if not result.ok:
            raise RuntimeError(f"Guide PDF compile failed: {result.errors or result.log}")
        output_path.write_bytes(result.pdf_bytes)
    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_typeset.py -v`
Expected: `4 passed` if `latexmk` is installed locally, or `2 passed, 2 skipped` if not
(the two `has_latexmk`-marked tests skip; they run for real inside the Modal image).

- [ ] **Step 5: Commit**

```bash
git add backend/muscleonglp/typeset.py backend/tests/test_muscleonglp_typeset.py
git commit -m "feat(muscleonglp): add LaTeX-based PDF typesetting stage"
```

---

### Task 5: Pipeline orchestrator

**Files:**
- Create: `backend/muscleonglp/pipeline.py`
- Test: `backend/tests/test_muscleonglp_pipeline.py`

Wires draft → red-team → typeset into the single entry point Plan 3's Modal function
(or a one-off manual script) will call to actually produce the sellable PDF.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_muscleonglp_pipeline.py`:

```python
import pytest

from muscleonglp import pipeline


@pytest.mark.asyncio
async def test_produce_guide_wires_stages_in_order(monkeypatch, tmp_path):
    calls = []

    async def fake_draft(client):
        calls.append("draft")
        return "draft text"

    async def fake_redteam(client, draft):
        calls.append(("redteam", draft))
        return "final text", []

    def fake_render(text, output_path):
        calls.append(("render", text, output_path))
        output_path.write_bytes(b"%PDF-fake")
        return output_path

    monkeypatch.setattr(pipeline, "draft_guide", fake_draft)
    monkeypatch.setattr(pipeline, "run_redteam_passes", fake_redteam)
    monkeypatch.setattr(pipeline, "render_guide_pdf", fake_render)

    output_path = tmp_path / "guide.pdf"
    result = await pipeline.produce_guide(object(), output_path)

    assert result == output_path
    assert calls[0] == "draft"
    assert calls[1] == ("redteam", "draft text")
    assert calls[2] == ("render", "final text", output_path)
    assert output_path.read_bytes() == b"%PDF-fake"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'muscleonglp.pipeline'`

- [ ] **Step 3: Write the implementation**

Create `backend/muscleonglp/pipeline.py`:

```python
"""End-to-end MuscleOnGLP flagship-guide production pipeline: draft, red
team, typeset. A one-time content-production run, not a recurring cron (see
design doc's Architecture section)."""
from pathlib import Path

from muscleonglp.draft import draft_guide
from muscleonglp.redteam import run_redteam_passes
from muscleonglp.typeset import render_guide_pdf


async def produce_guide(client, output_path: Path) -> Path:
    """Run the full pipeline and write the final PDF to *output_path*."""
    draft = await draft_guide(client)
    final_text, verdicts = await run_redteam_passes(client, draft)
    return render_guide_pdf(final_text, output_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_muscleonglp_pipeline.py -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/muscleonglp/pipeline.py backend/tests/test_muscleonglp_pipeline.py
git commit -m "feat(muscleonglp): add end-to-end guide-production pipeline"
```

---

## Final Verification

Run the full backend test suite once more to confirm nothing else broke:

```bash
cd backend && python3 -m pytest tests/ -q
```

Expected: all tests pass (plus the new `test_muscleonglp_*` files), with the same
`latexmk`-dependent skips as the baseline run if `latexmk` isn't installed locally.

## Explicitly Deferred (not part of this plan)

- Actually running `produce_guide()` against the real Anthropic API to generate the
  real flagship guide content — this plan builds the pipeline; running it to produce
  the shipped PDF is an operator action after this plan lands, not a coded task.
- The static site, drug-specific landing pages, and Stripe Checkout wiring (Plan 2).
- The Stripe webhook → Modal function → Resend email fulfillment path (Plan 3).
- Manual creation of the Gumroad and Etsy listings (operator action, not code).
