"""Pure-logic module for the paid Paper Review tool.

The actual review pipeline is a four-layer red team:

  L1 — Vision / integrity scan over rendered PDF pages.
       Catches figure-vs-text contradictions, image anomalies, and
       presentation issues that text extraction would miss.
  L2 — Live citation cross-check.
       Verifies that referenced papers exist in CrossRef and Semantic Scholar
       and that titles + years + authors match the bibliography. Reuses the
       same client pattern as backend/latextools/bibcheck.py.
  L3 — Adversarial four-persona debate.
       Methodology Critic, Statistical Skeptic, Data Integrity Officer, and
       Editor-in-Chief each red-team the paper in parallel. Their findings
       are merged with a consensus filter to suppress single-persona noise.
  L4 — Targeted rectification.
       A final synthesis pass produces a structured Markdown report:
       Critical Blind Spots, Data-to-Claim Contradictions, Rectification
       Checklist, and True Novelty Estimate.

Network calls (Anthropic API, CrossRef, Semantic Scholar) are kept inside
async helpers so the calling endpoint (in app.py) can run them concurrently.
Everything else in this module is pure logic and unit-testable.
"""
from __future__ import annotations

import asyncio
import base64
import dataclasses
import io
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

# Claude Sonnet 4.5 — the current production-quality reasoning model. Set via
# ANTHROPIC_MODEL env var to override (e.g. for a cheaper test pass).
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

# Low temperature — we want consistent reasoning, not creative writing.
TEMPERATURE = 0.1

# Pricing dial: cap the number of PDF pages we send to vision so a 200-page
# thesis doesn't blow up Anthropic costs. 30 pages * ~2k img-tokens * 1 call
# ~ 60k input tokens at $3/Mtok ~ $0.18 of vision cost per review.
MAX_VISION_PAGES = 30

# Reference list cap — long bibliographies are token-expensive to send to L3
# and L4. We truncate to the most-recent-cited 60 entries.
MAX_REFERENCES_TO_REVIEW = 60

# Body-text cap — keep the manuscript under this many characters when passing
# to L3/L4 so the persona prompts stay well within context. ~80k chars is
# roughly 20-25k tokens, leaving headroom for the system prompt + reasoning.
MAX_BODY_CHARS = 80_000

# Output token caps per persona — bound spend even on pathological inputs.
PERSONA_MAX_OUTPUT_TOKENS = 4_000
RECTIFY_MAX_OUTPUT_TOKENS = 6_000
L1_MAX_OUTPUT_TOKENS = 3_000

# Imported lazily inside functions where needed to avoid circular imports
# during module collection. The safety module is dependency-free so this
# is just hygiene, not strictly necessary.
from latextools import safety as _safety   # noqa: E402

# Concurrency cap on the persona panel — 4 parallel calls is the v1 design.
N_PERSONAS = 7


# ----------------------------------------------------------------------------
# PDF extraction (Layer 0 — produces the structured input the other layers
# consume).
# ----------------------------------------------------------------------------

@dataclass
class PaperReference:
    """One extracted reference from the manuscript bibliography."""
    raw: str
    title: str = ""
    doi: str = ""
    arxiv_id: str = ""
    year: str = ""
    authors: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class PaperFigure:
    """One figure or table in the manuscript, by caption."""
    label: str          # e.g. "Figure 3" or "Table 2"
    caption: str = ""
    page: int = 0       # 1-based

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class PaperStructure:
    """The structured view of an uploaded manuscript that all later layers
    consume. Held entirely in memory; never persisted."""
    title: str = ""
    abstract: str = ""
    body: str = ""               # truncated to MAX_BODY_CHARS
    references: list[PaperReference] = field(default_factory=list)
    figures: list[PaperFigure] = field(default_factory=list)
    page_count: int = 0
    n_references_total: int = 0  # before truncation
    n_pages_total: int = 0       # before truncation for vision

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "abstract": self.abstract,
            "body_preview": self.body[:500],
            "n_references": len(self.references),
            "n_references_total": self.n_references_total,
            "n_figures": len(self.figures),
            "page_count": self.page_count,
            "n_pages_total": self.n_pages_total,
        }


_REF_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", re.IGNORECASE)
_REF_ARXIV_RE = re.compile(r"\barXiv:\s*(\d{4}\.\d{4,5})", re.IGNORECASE)
_REF_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def _looks_like_bibliography_heading(line: str) -> bool:
    """Heuristic: is this line the start of the references section?"""
    s = line.strip().lower()
    if not s or len(s) > 40:
        return False
    return s in {
        "references", "bibliography", "works cited", "literature cited",
        "references cited", "reference list",
    } or s.startswith("references") or s.startswith("bibliography")


def _split_references(refs_blob: str) -> list[str]:
    """Best-effort split of a flat references blob into individual entries.

    Tries common reference-list shapes in order:
      1. Numbered: "[1] Author, ..." / "1. Author, ..."
      2. Blank-line separated
      3. Falls back to one giant entry (calling code degrades gracefully)
    """
    txt = refs_blob.strip()
    if not txt:
        return []
    # Pattern 1: numbered entries
    numbered = re.split(r"\n\s*(?:\[\d{1,3}\]|\d{1,3}\.)\s+", "\n" + txt)
    numbered = [s.strip() for s in numbered if s.strip()]
    if len(numbered) >= 3:
        return numbered
    # Pattern 2: blank-line separated
    blanksep = [s.strip() for s in re.split(r"\n\s*\n", txt) if s.strip()]
    if len(blanksep) >= 3:
        return blanksep
    # Pattern 3: single-line entries (each line is a ref) — only when the
    # average line length looks ref-shaped (>= 60 chars)
    lines = [s.strip() for s in txt.split("\n") if s.strip()]
    if len(lines) >= 3 and sum(len(l) for l in lines) / len(lines) >= 60:
        return lines
    return [txt]


def _parse_reference(raw: str) -> PaperReference:
    """Pull DOI, arXiv ID, year, and a probable title out of a raw entry."""
    raw_clean = raw.strip()
    ref = PaperReference(raw=raw_clean)
    if m := _REF_DOI_RE.search(raw_clean):
        ref.doi = m.group(1).rstrip(".,;)")
    if m := _REF_ARXIV_RE.search(raw_clean):
        ref.arxiv_id = m.group(1)
    if m := _REF_YEAR_RE.search(raw_clean):
        ref.year = m.group(1)
    # Title heuristic: take the longest segment between the year and a period.
    # This is brittle by design — anything better needs Grobid or similar.
    if ref.year:
        after_year = raw_clean.split(ref.year, 1)[1]
        # Drop leading punctuation
        after_year = re.sub(r"^[\s.,;):]+", "", after_year)
        # Title ends at the first period followed by whitespace + capital
        m2 = re.match(r"([^.]+?\.[^.]+?)(?=\.\s+[A-Z])", after_year + ".  X")
        if m2:
            ref.title = m2.group(1).strip().rstrip(".")
    return ref


def extract_paper(pdf_bytes: bytes) -> PaperStructure:
    """Extract structured content from a manuscript PDF using pdfplumber.

    Returns a PaperStructure dataclass populated as best we can. This is
    inherently best-effort — academic PDFs vary wildly — but the downstream
    layers degrade gracefully on missing fields.

    Imports pdfplumber lazily so this module can be imported in test
    environments without it installed.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError(
            "pdfplumber is required for paper extraction; install it in the "
            "Modal image"
        ) from e

    structure = PaperStructure()
    all_text_parts: list[str] = []
    references_blob = ""

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        structure.page_count = len(pdf.pages)
        structure.n_pages_total = len(pdf.pages)

        for page_idx, page in enumerate(pdf.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                # pdfplumber occasionally chokes on malformed pages — skip
                # and keep going rather than failing the whole review.
                logger.warning("pdfplumber failed on page %d", page_idx)
                continue

            # First page → title + abstract heuristics
            if page_idx == 1:
                lines = [l.strip() for l in page_text.split("\n") if l.strip()]
                # Title = first non-trivial line. Real first-page text often
                # starts with author headers; take the longest of the first 5
                # lines that's plausibly title-shaped (5-200 chars, no email).
                title_candidates = [
                    l for l in lines[:8]
                    if 5 <= len(l) <= 200
                    and "@" not in l
                    and not l.lower().startswith(("abstract", "introduction"))
                ]
                if title_candidates:
                    structure.title = max(title_candidates, key=len)
                # Abstract = text between "Abstract" header and the next
                # all-caps or numbered section header.
                m_abs = re.search(
                    r"(?:^|\n)\s*Abstract\s*[\n:]+(.*?)(?=\n\s*(?:\d+\.?\s+[A-Z]|[A-Z][A-Z\s]{4,}\n))",
                    page_text,
                    re.DOTALL,
                )
                if m_abs:
                    structure.abstract = re.sub(
                        r"\s+", " ", m_abs.group(1).strip()
                    )[:2000]

            # Detect figure / table captions (Figure 1: ..., Table 3. ...)
            for fig_m in re.finditer(
                r"^\s*(Figure|Fig\.|Table)\s+(\d+)[:.\s]+([^\n]+)",
                page_text,
                re.MULTILINE,
            ):
                label = f"{fig_m.group(1).rstrip('.')} {fig_m.group(2)}"
                caption = re.sub(r"\s+", " ", fig_m.group(3).strip())[:300]
                structure.figures.append(
                    PaperFigure(label=label, caption=caption, page=page_idx)
                )

            # Check for the references section starting on this page
            if not references_blob:
                for line in page_text.split("\n"):
                    if _looks_like_bibliography_heading(line):
                        # Everything from this point forward across the rest
                        # of the document is treated as the references blob.
                        idx = page_text.find(line)
                        references_blob = page_text[idx + len(line):]
                        break
                else:
                    all_text_parts.append(page_text)
                    continue
                # Found heading — append remaining pages to references blob
                continue

            # Already in references → keep appending to references blob
            references_blob += "\n" + page_text

    # If we never hit a heading, references blob is empty. Try a last-resort
    # split: the final 30% of the document.
    if not references_blob and all_text_parts:
        combined = "\n".join(all_text_parts)
        tail_start = int(len(combined) * 0.7)
        # Search the tail for a numbered-citation pattern; if found, take from
        # there. Otherwise leave references empty.
        m_tail = re.search(r"\n\s*\[\s*1\s*\]|\n\s*1\.\s+[A-Z]", combined[tail_start:])
        if m_tail:
            references_blob = combined[tail_start + m_tail.start():]
            combined = combined[: tail_start + m_tail.start()]
            structure.body = combined
        else:
            structure.body = combined
    else:
        structure.body = "\n".join(all_text_parts)

    # Truncate body to keep tokens bounded
    if len(structure.body) > MAX_BODY_CHARS:
        # Keep the front (intro/methods) — that's where most of the
        # methodological claims live — and a chunk of the tail (discussion).
        front = structure.body[: int(MAX_BODY_CHARS * 0.7)]
        tail = structure.body[-int(MAX_BODY_CHARS * 0.25):]
        structure.body = (
            front
            + "\n\n[... section omitted to keep within model context ...]\n\n"
            + tail
        )

    # Parse references
    raw_refs = _split_references(references_blob)
    structure.n_references_total = len(raw_refs)
    for raw in raw_refs[:MAX_REFERENCES_TO_REVIEW]:
        structure.references.append(_parse_reference(raw))

    # Sanitize every text field that will be embedded in an LLM prompt:
    # strip invisible Unicode, neutralise chat-template tokens, neutralise
    # closing tags for our own pseudo-XML wrappers, flag prompt-injection
    # patterns. The PDF is attacker-controllable; this is the single
    # choke point for everything that follows.
    metrics = _safety.sanitize_paper_structure(structure)
    if metrics.get("n_suspicious_fields", 0) > 0:
        logger.warning(
            "extract_paper: %d field(s) contained injection-pattern signal; "
            "review proceeding with sanitised text. Metrics: %s",
            metrics["n_suspicious_fields"], metrics,
        )

    return structure


def render_pages_as_images(
    pdf_bytes: bytes,
    max_pages: int = MAX_VISION_PAGES,
    dpi: int = 110,
) -> list[bytes]:
    """Render the first *max_pages* of a PDF to PNG bytes (one per page).

    Uses pdf2image (which shells out to poppler). Returns an empty list and
    logs if rendering fails — the L1 layer treats that as "vision skipped"
    rather than failing the whole review.
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        logger.warning("pdf2image not installed; vision layer will be skipped")
        return []

    images: list[bytes] = []
    try:
        pil_pages = convert_from_bytes(
            pdf_bytes, dpi=dpi, fmt="png", first_page=1, last_page=max_pages
        )
    except Exception:
        logger.exception("pdf2image rendering failed")
        return []

    for pil in pil_pages:
        buf = io.BytesIO()
        pil.save(buf, format="PNG", optimize=True)
        images.append(buf.getvalue())
    return images


# ----------------------------------------------------------------------------
# Domain-specific attack-vector modules
# ----------------------------------------------------------------------------

DOMAINS = ("general", "machine_learning", "biomedicine", "psychology_social", "chemistry_materials")

_ML_MODULE = """<domain_module name="machine_learning">
You are reviewing a machine-learning paper. Attack these high-frequency
failure modes with maximum skepticism:

- Test/train contamination, pre-training contamination on common
  benchmarks (especially LLM evaluation papers).
- "Cherry-picked seeds": single-run reporting, no error bars, no
  significance testing of multiple-run differences.
- Benchmark over-fitting: was the test set used during model selection?
- Unfair baselines: stronger compute / data / tuning for the proposed
  method than for baselines.
- Hyperparameter search asymmetry — the proposed method has a search
  budget that the baselines did not.
- Missing ablations: each architectural choice should have an ablation.
- Cost-of-compute claims that don't account for hyperparameter search.
- Statistical claims based on n=3 or n=5 runs with no test.
- Results table with bold-the-winner that masks within-noise differences.
- Code/data availability: is the artifact actually released, or just
  "available upon request"?
- LLM-as-judge evaluation with the same model family as the system under
  test (self-preference bias).
</domain_module>"""

_BIOMED_MODULE = """<domain_module name="biomedicine">
You are reviewing a biomedical paper. Attack these high-frequency failure
modes with maximum skepticism:

- Sample-size justification: was a power calculation actually performed,
  or is "30 mice" pulled from convention?
- Animal welfare and IRB / IACUC compliance claims — are they specific?
- Multiple-comparisons handling: was Bonferroni / FDR applied where it
  should have been?
- Western blot / gel image manipulation: bands that look spliced, repeated,
  or inconsistent with the loading control.
- "Representative image" claims unsupported by quantification.
- Survival curves without log-rank tests or censoring disclosure.
- Inappropriate parametric tests on small or non-normal samples.
- Blinding and randomization claims — are they evidenced by methods, or
  asserted in passing?
- Clinical trial registration: is the trial registered and does the
  pre-registered primary endpoint match what's reported?
- p-value clustering near 0.05 (potential p-hacking).
- Conflicts of interest, especially for industry-funded efficacy claims.
- Conversion of effect sizes to clinical relevance — large-N studies
  often report statistically significant but clinically tiny effects.
</domain_module>"""

_PSYCH_MODULE = """<domain_module name="psychology_social">
You are reviewing a psychology or social-science paper. Attack these
high-frequency failure modes with maximum skepticism:

- Pre-registration: was the study pre-registered, and does the reported
  analysis match the pre-registered plan?
- Sample composition: WEIRD samples generalized to all humans; MTurk /
  Prolific samples treated as nationally representative.
- Effect sizes: small d's reported as practically meaningful.
- Garden of forking paths: many DVs, many moderators, only the "winners"
  reported.
- Order effects and counterbalancing — disclosed?
- Manipulation checks — present and significant?
- Replication: is there independent replication, or is this the only
  evidence?
- Measurement validity: novel scales used without reported reliability
  (alpha < 0.7 should be flagged).
- Confounding by demographic variables not controlled for.
- "We predicted X" claims that look like HARKing — re-read for whether
  the prediction was actually pre-registered.
- Researcher-degrees-of-freedom robustness checks (multiverse analysis).
</domain_module>"""

_CHEM_MODULE = """<domain_module name="chemistry_materials">
You are reviewing a chemistry or materials-science paper. Attack these
high-frequency failure modes with maximum skepticism:

- Yield reporting: was the synthesis actually run multiple times, or is
  the reported yield a single-run optimum?
- Characterization completeness: NMR + MS + IR + elemental for new
  compounds, or claims unsupported by enough orthogonal techniques?
- Crystal structures: CCDC deposition number present?
- DFT calculations with under-specified basis set / functional / solvation
  model.
- Catalytic claims with TONs/TOFs but no leaching test, no mercury drop
  test, no recyclability data.
- Spectrum cleanliness — chromatograms cropped to remove side peaks.
- Materials properties measured with unstated sample preparation, leading
  to irreproducibility.
- Stability claims based on single short-duration measurements.
- "Green chemistry" framing without solvent or atom-economy quantification.
- Scale-up feasibility addressed or hand-waved?
</domain_module>"""

_GENERAL_MODULE = """<domain_module name="general">
You are reviewing a research paper. Read the methods carefully. For every
claim, ask:

- Is the evidence presented sufficient for the strength of the claim?
- What's the smallest counter-experiment that would falsify the claim?
  Is that counter-experiment ruled out?
- Where do the numbers in the abstract come from — table N? Are they the
  right numbers (e.g. accuracy vs. F1 vs. recall) for the use-case
  implied by the framing?
- Is the comparison fair (matched setting, matched compute, matched data)?
- Could a different test set / sample / metric flip the conclusion?
- Are reported uncertainties consistent with sample sizes?
- Are limitations and threats-to-validity meaningful, or boilerplate?
</domain_module>"""

DOMAIN_MODULES: dict[str, str] = {
    "machine_learning": _ML_MODULE,
    "biomedicine": _BIOMED_MODULE,
    "psychology_social": _PSYCH_MODULE,
    "chemistry_materials": _CHEM_MODULE,
    "general": _GENERAL_MODULE,
}


# ----------------------------------------------------------------------------
# Persona prompts (L3 — adversarial debate)
# ----------------------------------------------------------------------------

_METHODOLOGY_CRITIC = """<persona name="Methodology Critic">
You are a senior, deeply skeptical methodologist. Your single job is to
identify methodological failures — design choices that could invalidate
the paper's central claims.

Your output must be a JSON array (and ONLY a JSON array — no prose
preamble) of finding objects:
[
  {
    "category": "design" | "stats" | "analysis" | "reproducibility" | "validity",
    "severity": "critical" | "major" | "minor",
    "claim_quoted": "<exact text quoted from the paper>",
    "issue": "<one or two sentences naming the problem>",
    "evidence": "<which section/figure/table substantiates this concern>",
    "what_a_referee_would_say": "<the verdict you'd write in a journal review>"
  },
  ...
]

Be precise. Quote the paper. If the paper does not support a quoted
critique, do not invent one — drop the finding instead.
</persona>"""

_STATISTICAL_SKEPTIC = """<persona name="Statistical Skeptic">
You are a statistician who reviews papers professionally. You are
laser-focused on numerical claims, statistical tests, and the integrity
of inferential reasoning.

For every numerical claim, ask:
- Is the test appropriate for the data?
- Was the test pre-specified or post-hoc?
- Are the assumptions (normality, independence, etc.) met or checked?
- Is the sample size justified, or is power inadequate?
- Are corrections for multiple comparisons applied?
- Are effect sizes reported with confidence intervals?
- Are p-values reported with sufficient precision (not just "p<0.05")?

Your output must be a JSON array (and ONLY a JSON array) with the same
schema as the Methodology Critic. Be quantitative. Where you can compute
a sanity check from the paper's reported numbers (e.g., recovering
omitted CIs from n + se), do so and include the computation in
"evidence".
</persona>"""

_DATA_INTEGRITY_OFFICER = """<persona name="Data Integrity Officer">
You are a research-integrity officer trained to detect data fabrication,
image manipulation, plagiarism patterns, and citation fraud — not to
make accusations, but to identify anomalies that warrant a closer look.

Look for:
- Numbers that don't add up (rows in a table not summing to the totals;
  effect sizes inconsistent with reported n and SE).
- Figures whose captions describe one thing and content shows another.
- Tables where significance stars are inconsistent with the cell values.
- Suspiciously round numbers when the precision of the methodology
  would predict noisier results.
- Citation patterns that look hallucinated (papers cited that don't
  match the cross-check evidence supplied to you).
- Self-citation rings.

Hedged language is mandatory: "anomaly worth manual review", NEVER
"fraud" or "fabrication". You are flagging things to check, not
adjudicating.

Output: same JSON-array schema as the Methodology Critic.
</persona>"""

_EDITOR_IN_CHIEF = """<persona name="Editor-in-Chief">
You are the editor of a high-tier journal making the publish / revise /
reject call. Your job is the BIG-PICTURE view that the other reviewers
miss:

- Is the central claim novel — or has it been published before, possibly
  by the same group?
- Is the contribution incremental in a way that the framing oversells?
- Does the paper engage with the obvious competing work, or does it
  ignore inconvenient prior art?
- Is the writing clear enough that the methodology is reproducible from
  the text alone?
- Is the conclusion supported by the evidence, or does it overreach?
- What would the field gain or lose if this paper were published as-is?

Output: same JSON-array schema as the Methodology Critic. Plus, end with
one summary finding:
{
  "category": "editorial_verdict",
  "severity": "<critical|major|minor>",
  "claim_quoted": "Overall publication recommendation",
  "issue": "<accept | minor revisions | major revisions | reject>",
  "evidence": "<one paragraph summary of why>",
  "what_a_referee_would_say": "<the recommendation in one sentence>"
}
</persona>"""

_EQUATION_ANALYST = """<persona name="Equation Analyst">
You are a rigorous applied mathematician. Examine EVERY equation, derivation, and formal claim in
the manuscript with deep scrutiny. For each, check:
- Dimensional / units consistency (both sides of every equation carry the same units).
- Derivation validity: does each step follow from the previous one? Re-derive key steps yourself
  and flag any that don't follow or contain algebra errors.
- Provability: does the stated result actually follow from the stated assumptions? Are the
  assumptions sufficient, or is an unstated one being used?
- Internal consistency: are symbols defined before use and used consistently across all equations?
  Do equations agree with each other and with the surrounding prose?
- Limiting / boundary cases: do the formulas behave sensibly at limits (zero, infinity, edge
  inputs)? Do special cases reduce to known results?
- Well-posedness: divisions by potentially-zero terms, undefined operations, domain violations,
  or non-convergent expressions.
- Whether the math genuinely supports the paper's central claim or is decorative.

For every issue, QUOTE the exact equation or step, and in "evidence" show the concrete check you
performed (the re-derivation, the dimensional analysis, the counterexample, or the limiting-case
substitution). Use category "math". If the paper contains no equations, return an empty array [].
Do not invent equations that aren't present.

Output: same JSON-array schema as the Methodology Critic.
</persona>"""

_LITERATURE_AUDITOR = """<persona name="Literature Auditor">
You scrutinize how the manuscript USES the literature — not citation formatting, but whether the
scholarship is sound. You are given a citation cross-check (Layer 2) listing which references
verified; use it. Check:
- Claim-support fidelity: for each "X et al. show/prove/find Y" statement, does the cited work
  plausibly support exactly that claim, or is it over-claimed, misattributed, or stretched?
- Missing prior art: are obvious seminal or directly-competing works conspicuously absent, such
  that the contribution's novelty or framing is suspect?
- Strawmanning: is competing work characterized fairly, or set up to be knocked down?
- Uncited assertions: strong empirical/theoretical claims stated as fact with no citation and no
  in-paper evidence.
- Citation inflation / self-citation rings: padding or disproportionate self-citation.
- Novelty contradictions: does the paper claim novelty for something its own cited prior art did?

You cannot read the cited papers, so HEDGE ("appears to over-claim", "warrants verification against
the source"). Quote the exact sentence + citation. Use category "literature".

Output: same JSON-array schema as the Methodology Critic.
</persona>"""

_NUMERICAL_REALIST = """<persona name="Numerical Realist">
You verify that the numbers are real, internally consistent, and plausible. For every reported
number, table, and statistic, check:
- Arithmetic: do table rows/columns sum to stated totals? Do subgroup sample sizes add up to the
  total N? Do percentages sum to ~100 where they should?
- Mutual statistical consistency: is each mean within its reported range? Are mean / SD / SE / CI /
  N mutually coherent (recompute SE = SD/sqrt(N); recover a CI from mean +/- 1.96*SE)? Are t/F/p/df
  values consistent with each other?
- Effect-size plausibility: are reported effect sizes consistent with the reported N and variance?
  Is the claimed precision justified by the sample size?
- Magnitude realism: are quantities physically/empirically plausible for the domain? Are orders of
  magnitude and units sane and consistent across the paper?
- Anomalies: suspiciously round numbers, impossible values (negative variance, probabilities > 1,
  accuracy > 100%), or precision the methodology can't support.

Always SHOW your computation in "evidence". Use hedged language for anything you can't fully
verify. Use category "numbers". If the paper reports no numbers, return [].

Output: same JSON-array schema as the Methodology Critic.
</persona>"""

PERSONA_PROMPTS: dict[str, str] = {
    "methodology_critic": _METHODOLOGY_CRITIC,
    "statistical_skeptic": _STATISTICAL_SKEPTIC,
    "data_integrity_officer": _DATA_INTEGRITY_OFFICER,
    "editor_in_chief": _EDITOR_IN_CHIEF,
    "equation_analyst": _EQUATION_ANALYST,
    "literature_auditor": _LITERATURE_AUDITOR,
    "numerical_realist": _NUMERICAL_REALIST,
}


# ----------------------------------------------------------------------------
# Anthropic API helpers
# ----------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


async def _anthropic_message(
    client,
    *,
    system: str,
    user_content: list[dict],
    max_tokens: int,
    model: str = DEFAULT_MODEL,
    temperature: float = TEMPERATURE,
) -> str:
    """Call Anthropic's /v1/messages endpoint and return the assistant text.

    *client* is an httpx.AsyncClient (the caller manages the lifecycle).
    *user_content* is the raw Anthropic content-block list: text + image
    blocks are both supported.

    Retries transient failures (HTTP 429 rate-limit, 529 overloaded, and
    network timeouts / connection drops) with exponential backoff, honoring
    Retry-After. A long generation no longer surfaces as a read timeout the way
    it did at read=120s — the client is configured with generous headroom and
    transient stalls are retried rather than fatal. Non-transient HTTP errors
    (4xx other than 429) are raised immediately so the caller sees real faults.
    """
    import asyncio
    import httpx

    api_key = os.environ["ANTHROPIC_API_KEY"]
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    max_attempts = 3
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.post(ANTHROPIC_API_URL, json=body, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            # Connection/read timeout or dropped connection — transient.
            last_exc = e
            if attempt < max_attempts:
                await asyncio.sleep((attempt * attempt) * 2.0)  # 2s, 8s
                continue
            raise

        if resp.status_code in (429, 529) and attempt < max_attempts:
            retry_after = resp.headers.get("retry-after")
            try:
                delay = float(retry_after) if retry_after else (attempt * attempt) * 2.0
            except ValueError:
                delay = (attempt * attempt) * 2.0
            await asyncio.sleep(delay)
            continue

        resp.raise_for_status()
        data = resp.json()
        # Concatenate all text blocks in the assistant response.
        parts: list[str] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts).strip()

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Anthropic request failed after retries (rate-limited).")


def _parse_json_findings(raw: str) -> list[dict]:
    """Parse a JSON array out of an LLM response. Tolerant of fenced code.

    Returns [] on parse failure rather than raising — a malformed persona
    response shouldn't blow up the whole review.
    """
    import json

    s = raw.strip()
    # Strip ```json ... ``` fences if present
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    # Find the first '[' and the matching last ']'
    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    blob = s[start : end + 1]
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        logger.warning("persona response did not parse as JSON: %r", blob[:200])
        return []
    if not isinstance(parsed, list):
        return []
    # Drop entries that aren't dicts
    return [f for f in parsed if isinstance(f, dict)]


# ----------------------------------------------------------------------------
# Layer 1 — Vision integrity scan
# ----------------------------------------------------------------------------

_L1_SYSTEM_CORE = """You are a careful scientific integrity reviewer specializing
in figure and presentation analysis. You will see rendered pages of a
research manuscript. Your job:

1. Flag any figure or image that shows signs of digital manipulation:
   suspicious duplication of regions, mismatched scales/legends, spliced
   western blots, etc. Use hedged language ("appears", "warrants closer
   review"). Do NOT make accusations.
2. Flag figures whose visual content contradicts the manuscript text or
   the figure caption.
3. Flag tables with internal inconsistency (rows don't sum, totals
   inconsistent with the cell values).
4. Flag presentation issues that mask comparison: log scales without
   labels, missing error bars on plotted means, broken y-axes that
   exaggerate differences.
5. Flag accessibility issues: axis text too small to read, color-only
   encoding of categories, etc.

Output a JSON array (and ONLY a JSON array) of finding objects:
[
  {
    "page": <1-based page number>,
    "type": "manipulation_concern" | "text_contradiction" | "table_inconsistency" | "presentation" | "accessibility",
    "severity": "critical" | "major" | "minor",
    "where": "<Figure N / Table N / general>",
    "observation": "<what you observed>",
    "recommendation": "<what the authors should do>"
  },
  ...
]
"""

# Compose the final L1 system prompt with the safety preamble prepended.
L1_SYSTEM = _safety.SAFETY_PREAMBLE + "\n\n" + _L1_SYSTEM_CORE


async def run_layer_1_vision(
    client,
    pdf_bytes: bytes,
    domain: str,
) -> dict:
    """Run the L1 figure/integrity scan over rendered PDF pages.

    Returns {"status": "ok"|"skipped"|"error", "findings": [...]}.
    Failures are non-fatal — the L1 layer is the most expensive and the
    most likely to time out on weird PDFs.
    """
    images = render_pages_as_images(pdf_bytes, max_pages=MAX_VISION_PAGES)
    if not images:
        return {"status": "skipped", "reason": "no rendered pages", "findings": []}

    # Build user content: one text intro + one image block per page (Claude
    # Vision encoding).
    user_content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"Reviewing manuscript (domain: {domain}). "
                f"{len(images)} pages attached. Analyse each page; flag any "
                "issues you see. JSON array only — no prose."
            ),
        }
    ]
    for img in images:
        user_content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(img).decode("ascii"),
                },
            }
        )

    try:
        raw = await _anthropic_message(
            client,
            system=L1_SYSTEM,
            user_content=user_content,
            max_tokens=L1_MAX_OUTPUT_TOKENS,
        )
    except Exception:
        logger.exception("L1 vision call failed")
        return {"status": "error", "findings": []}

    findings = _parse_json_findings(raw)
    return {"status": "ok", "findings": findings}


# ----------------------------------------------------------------------------
# Layer 2 — Live citation cross-check
# ----------------------------------------------------------------------------

async def _crossref_lookup(client, ref: PaperReference) -> dict:
    """Best-effort CrossRef lookup. Returns a dict suitable for inclusion in
    the L2 report. Never raises."""
    from urllib.parse import quote as _q

    # Prefer DOI — it's authoritative.
    if ref.doi:
        try:
            resp = await client.head(
                f"https://doi.org/{ref.doi}", follow_redirects=True, timeout=10.0,
            )
            if resp.status_code < 400:
                return {"raw": ref.raw, "doi": ref.doi, "status": "verified", "method": "doi"}
            return {
                "raw": ref.raw, "doi": ref.doi,
                "status": "dead_doi", "method": "doi",
                "http_status": resp.status_code,
            }
        except Exception:
            return {"raw": ref.raw, "doi": ref.doi, "status": "network_error", "method": "doi"}

    # No DOI — fall back to title search.
    if not ref.title:
        return {"raw": ref.raw, "status": "no_identifier", "method": "title"}

    try:
        resp = await client.get(
            "https://api.crossref.org/works",
            params={
                "query.bibliographic": ref.title[:200],
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
            return {"raw": ref.raw, "status": "crossref_unavailable", "method": "title"}
        items = (resp.json().get("message") or {}).get("items") or []
        if not items:
            return {"raw": ref.raw, "status": "not_found", "method": "title"}
        item = items[0]
        found_title = ((item.get("title") or [""])[0]).lower()
        confidence = _string_overlap(ref.title.lower(), found_title)
        return {
            "raw": ref.raw,
            "status": "matched" if confidence >= 0.7 else "weak_match",
            "method": "title",
            "confidence": round(confidence, 2),
            "found_title": (item.get("title") or [""])[0],
            "found_doi": item.get("DOI", ""),
        }
    except Exception:
        return {"raw": ref.raw, "status": "network_error", "method": "title"}


def _string_overlap(a: str, b: str) -> float:
    """Cheap title-similarity score using token Jaccard.

    Avoids loading difflib for the typical reference-list size (~60 calls)
    — keeps the L2 layer fast.
    """
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


async def run_layer_2_citations(
    client,
    references: list[PaperReference],
) -> dict:
    """Verify every parsed reference against CrossRef.

    Returns {"checked": N, "verified": K, "issues": [...]} where issues
    enumerates references that did NOT cleanly verify.
    """
    if not references:
        return {"checked": 0, "verified": 0, "issues": []}

    results = await asyncio.gather(
        *[_crossref_lookup(client, r) for r in references],
        return_exceptions=True,
    )

    issues: list[dict] = []
    verified = 0
    for r in results:
        if isinstance(r, Exception):
            continue
        status = r.get("status", "")
        if status in ("verified", "matched"):
            verified += 1
        else:
            issues.append(r)
    return {
        "checked": len(references),
        "verified": verified,
        "issues": issues,
    }


def attach_audit(l2: dict, audit: dict) -> dict:
    """Additively attach the deep-citation-audit result onto the L2 dict.

    Kept as a named helper so the wiring is unit-testable without running the
    full network pipeline.
    """
    l2 = dict(l2)
    l2["audit"] = audit
    return l2


# ----------------------------------------------------------------------------
# Layer 3 — Adversarial 4-persona debate
# ----------------------------------------------------------------------------

def _build_persona_user_content(
    persona_prompt: str,
    structure: PaperStructure,
    l1: dict,
    l2: dict,
    domain: str,
) -> list[dict]:
    """Compose the user message for a single persona call.

    The persona sees: domain module + paper structure + summarised L1 and L2
    findings. We pass JSON-tagged sections so the model can navigate.
    """
    import json as _json

    domain_module = DOMAIN_MODULES.get(domain, _GENERAL_MODULE)
    text = (
        f"{domain_module}\n\n"
        f"{persona_prompt}\n\n"
        + _safety.wrap_user_content(
            (
                f"Title: {structure.title or '(not extracted)'}\n"
                f"Pages: {structure.page_count}\n"
                f"Figures detected: {len(structure.figures)}\n"
                f"References extracted: {len(structure.references)} of "
                f"{structure.n_references_total}"
            ),
            "paper_metadata",
        ) + "\n\n"
        + _safety.wrap_user_content(
            structure.abstract or "(not extracted)", "abstract",
        ) + "\n\n"
        + _safety.wrap_user_content(
            _json.dumps([f.to_dict() for f in structure.figures[:30]], indent=2),
            "figure_inventory",
        ) + "\n\n"
        + _safety.wrap_user_content(
            _json.dumps(l1.get("findings", [])[:30], indent=2),
            "vision_findings_from_l1",
        ) + "\n\n"
        + _safety.wrap_user_content(
            _json.dumps(l2.get("issues", [])[:30], indent=2),
            "citation_issues_from_l2",
        ) + "\n\n"
        + _safety.wrap_user_content(structure.body, "manuscript_body") + "\n\n"
        + "Now produce your JSON array of findings."
    )
    return [{"type": "text", "text": text}]


async def _run_one_persona(
    client,
    persona_key: str,
    persona_prompt: str,
    structure: PaperStructure,
    l1: dict,
    l2: dict,
    domain: str,
) -> dict:
    user_content = _build_persona_user_content(
        persona_prompt, structure, l1, l2, domain
    )
    system = (
        _safety.SAFETY_PREAMBLE + "\n\n" +
        "You are part of a four-reviewer adversarial panel red-teaming an "
        "academic manuscript. Stay strictly in your assigned persona. Quote "
        "the paper exactly when you cite it. Output a JSON array of "
        "findings and nothing else."
    )
    try:
        raw = await _anthropic_message(
            client,
            system=system,
            user_content=user_content,
            max_tokens=PERSONA_MAX_OUTPUT_TOKENS,
        )
    except Exception:
        logger.exception("persona %s failed", persona_key)
        return {"persona": persona_key, "findings": [], "status": "error"}
    findings = _parse_json_findings(raw)
    # Stamp each finding with its persona so the consensus filter can see
    # which reviewer raised it.
    for f in findings:
        f["persona"] = persona_key
    return {"persona": persona_key, "findings": findings, "status": "ok"}


def _consensus_filter(panel: list[dict]) -> dict:
    """Merge findings across the panel; flag overlaps as high-consensus.

    Two findings are considered to overlap when their issue strings share
    >= 35% of tokens. This is fuzzy on purpose — different personas phrase
    the same concern differently. The output structure preserves every
    finding (so nothing is dropped) but marks ones with cross-persona
    support.
    """
    all_findings: list[dict] = []
    for entry in panel:
        all_findings.extend(entry.get("findings", []))

    # Compute pairwise overlap on the 'issue' field.
    for i, f in enumerate(all_findings):
        f["_consensus"] = [f.get("persona", "?")]
        f_tokens = set(re.findall(r"\w+", (f.get("issue") or "").lower()))
        if not f_tokens:
            continue
        for j, g in enumerate(all_findings):
            if i == j:
                continue
            g_tokens = set(re.findall(r"\w+", (g.get("issue") or "").lower()))
            if not g_tokens:
                continue
            jaccard = len(f_tokens & g_tokens) / len(f_tokens | g_tokens)
            if jaccard >= 0.35 and g.get("persona") not in f["_consensus"]:
                f["_consensus"].append(g.get("persona", "?"))

    # Severity ordering for downstream rendering
    def _sev_key(f):
        return {"critical": 0, "major": 1, "minor": 2}.get(f.get("severity", "minor"), 3)

    all_findings.sort(key=lambda f: (-len(f["_consensus"]), _sev_key(f)))
    return {
        "panel": panel,
        "merged_findings": all_findings,
        "n_findings": len(all_findings),
        "n_high_consensus": sum(1 for f in all_findings if len(f["_consensus"]) >= 2),
    }


async def run_layer_3_personas(
    client,
    structure: PaperStructure,
    l1: dict,
    l2: dict,
    domain: str,
) -> dict:
    """Run the four personas in parallel and merge with the consensus filter."""
    coros = [
        _run_one_persona(client, key, prompt, structure, l1, l2, domain)
        for key, prompt in PERSONA_PROMPTS.items()
    ]
    panel = await asyncio.gather(*coros, return_exceptions=True)
    panel_clean: list[dict] = []
    for entry in panel:
        if isinstance(entry, Exception):
            logger.exception("persona call raised: %s", entry)
            continue
        panel_clean.append(entry)
    return _consensus_filter(panel_clean)


# ----------------------------------------------------------------------------
# Layer 3.5 — Deep pass (only for the "deep" tier)
#
# Re-runs each persona with access to the other personas' findings from the
# first pass. The output is a tightened, cross-aware set of findings: each
# persona can endorse, refine, or push back on what the others raised.
# ----------------------------------------------------------------------------

_DEEP_PASS_SUFFIX = """

This is the SECOND pass. Below are the findings the other three reviewers
produced on their first independent pass. Now that you can see them:

- If their findings reinforce something you flagged, push the severity up
  and tighten your evidence.
- If their findings contradict what you flagged, either refine your finding
  or drop it (be willing to retract on encountering better evidence).
- Raise NEW findings that you only see now in light of theirs (e.g. a
  combined methodology + stats concern neither of you saw alone).
- DON'T just restate the other personas' findings — they're already in the
  record. Stay in your lane; bring what only YOUR lens catches.

Output the same JSON-array schema as before — your final, second-pass set
of findings only. The merge will replace your first-pass results with these.
"""


async def _run_one_persona_deep(
    client,
    persona_key: str,
    persona_prompt: str,
    structure: PaperStructure,
    l1: dict,
    l2: dict,
    other_findings: list[dict],
    domain: str,
) -> dict:
    """Second-pass call for one persona — sees the other personas' findings."""
    import json as _json

    base_user = _build_persona_user_content(
        persona_prompt + _DEEP_PASS_SUFFIX,
        structure, l1, l2, domain,
    )
    # Append the other personas' findings as a tagged block
    base_user[0]["text"] += (
        "\n\n"
        + _safety.wrap_user_content(
            _json.dumps(other_findings, indent=2)[:30_000],
            "other_personas_first_pass_findings",
        )
        + "\n\nNow produce your SECOND-PASS JSON array of findings."
    )
    system = (
        _safety.SAFETY_PREAMBLE + "\n\n" +
        "You are part of a four-reviewer adversarial panel red-teaming an "
        "academic manuscript, now on the second pass. Stay strictly in your "
        "assigned persona but use the other reviewers' first-pass findings "
        "to sharpen your own. Output a JSON array of findings only."
    )
    try:
        raw = await _anthropic_message(
            client,
            system=system,
            user_content=base_user,
            max_tokens=PERSONA_MAX_OUTPUT_TOKENS,
        )
    except Exception:
        logger.exception("deep-pass persona %s failed", persona_key)
        return {"persona": persona_key, "findings": [], "status": "error"}
    findings = _parse_json_findings(raw)
    for f in findings:
        f["persona"] = persona_key
    return {"persona": persona_key, "findings": findings, "status": "ok"}


async def run_layer_3_deep_pass(
    client,
    structure: PaperStructure,
    l1: dict,
    l2: dict,
    first_pass: dict,
    domain: str,
) -> dict:
    """Second L3 pass — each persona sees the others' first-pass findings.

    Returns a fresh consensus-filtered structure, replacing the first-pass
    one. The intent is sharpening, not piling on; deep_pass typically
    surfaces 0-3 new high-confidence findings the single-pass missed.
    """
    coros = []
    for key, prompt in PERSONA_PROMPTS.items():
        # Everyone *except* this persona's own first-pass findings is shown
        # to this persona for the second pass.
        others: list[dict] = []
        for entry in first_pass.get("panel", []):
            if entry.get("persona") == key:
                continue
            others.extend(entry.get("findings", []))
        coros.append(_run_one_persona_deep(
            client, key, prompt, structure, l1, l2, others, domain,
        ))
    panel = await asyncio.gather(*coros, return_exceptions=True)
    panel_clean: list[dict] = []
    for entry in panel:
        if isinstance(entry, Exception):
            logger.exception("deep persona call raised: %s", entry)
            continue
        panel_clean.append(entry)
    return _consensus_filter(panel_clean)


# ----------------------------------------------------------------------------
# Layer 4 — Targeted rectification
# ----------------------------------------------------------------------------

_L4_SYSTEM_CORE = """You are the senior reviewer producing the final, structured
red-team report for the authors. You have access to:

- The paper structure (title, abstract, body, figures, references).
- Layer 1 vision findings (figure / table integrity).
- Layer 2 citation cross-check (which references didn't verify).
- Layer 3 seven-persona panel debate (merged findings, with consensus flags).

Your job is to produce a single Markdown report with EXACTLY these sections:

# Manuscript Review

## What's Working
A balanced 3-6 bullet list of the paper's genuine strengths. Be specific and
quote when possible. This is not flattery — it's calibration. The authors
need to know which parts to keep when revising. If a strength is also
emphasised in your other sections, mention it here briefly anyway.

## Critical Blind Spots
The 3-7 most important issues the authors must address. Each is a top-level
bullet with:
- **One-line summary** in bold, prefixed with a confidence tag in brackets:
  **[Confidence: high]**, **[Confidence: medium]**, or **[Confidence: low]**.
  "High" means at least two personas raised this independently AND you can
  point to a specific paper artifact. "Low" means a single persona flagged
  it with weak evidence. Default to "medium" when uncertain.
- A quoted snippet from the paper showing the claim being challenged.
- The specific failure mode and which layer surfaced it.
- A "why it matters:" tag with a short clause naming the failure mode in
  canonical terms (e.g. "test-train contamination", "p-hacking",
  "WEIRD-sample over-generalization"). Use one of these canonical tags
  when possible so we can link to a deeper explainer:
  test-train-contamination, hyperparameter-asymmetry, cherry-picked-seeds,
  benchmark-overfitting, missing-ablations, llm-self-judge,
  underpowered-sample, multiple-comparisons, p-hacking, hark-ing,
  garden-of-forking-paths, weird-sample, manipulation-check-missing,
  yield-single-run, missing-characterization, dft-underspecified,
  catalyst-leaching, figure-presentation, table-inconsistency,
  hallucinated-citation, year-mismatch, unfair-baseline,
  ablation-missing, blinding-not-evidenced, trial-not-registered.
- The concrete fix.

Sort by confidence × severity. High-confidence + critical comes first.

## Data-to-Claim Contradictions
Places where the numbers, figures, or tables don't support the textual claim.
Each entry: claim quoted → contradicting evidence quoted → explanation.
If there are no clear contradictions, write exactly: "No clear contradictions
detected between the textual claims and the numerical evidence we examined."

## Equation Audit
Synthesize the Equation Analyst's findings. For each flagged equation/derivation: quote the
equation, state the specific problem (dimensional mismatch, invalid derivation step, unproven
result, inconsistent notation, ill-posed expression, failing limiting case), and show the check
that exposed it. If the paper has no equations, write exactly: "No equations to audit." If all
equations check out, say so explicitly and note what you verified.

## Literature & Citation Usage
Synthesize the Literature Auditor's findings on how scholarship is used: over-claimed or
misattributed citations (quote "X et al. show Y" and explain the mismatch), conspicuously missing
prior art, strawmanning, uncited strong claims, citation inflation, and novelty claims contradicted
by cited work. Keep integrity language hedged. If nothing of concern, say so in one sentence.

## Number Realism
Synthesize the Numerical Realist's findings: arithmetic that doesn't add up (totals, subgroup Ns,
percentages), mutually inconsistent statistics (mean/SD/SE/CI/N, t/F/p/df), implausible magnitudes
or impossible values, and unjustified precision. Show the arithmetic for each. If the numbers are
internally consistent and plausible, state that and note what you recomputed.

## Rectification Checklist
A flat A/B/C ordered list the author can work through. Each item starts with
its priority letter:
- **[A]** Must fix before resubmission.
- **[B]** Should fix; reviewers will flag.
- **[C]** Polish; would strengthen the paper.
Each item is concrete enough to be actioned without re-reading the review.
Where the fix involves a specific page, figure, or table, name it.

## True Novelty Estimate
A short paragraph honestly assessing what's genuinely new in this paper vs.
what's incremental over prior art. End with a one-sentence verdict:
"Genuinely novel contribution: <…>" or "Marginal advance: <…>".

## Reference Verification Summary
A short paragraph summarising how many references verified cleanly, how many
look dead or hallucinated, and which specific ones to manually re-check.

## Citation Support Audit
Render the deep citation audit supplied in layer_2_citations.audit. This audit
fetched the abstract of each cited source and judged whether it supports the
claim it was attached to. Produce:
- A one-line tally: counts per verdict (Supported, Partially supported, Not
  supported by abstract, Contradicted, Source unavailable).
- A Markdown table of the most important non-Supported findings (skip
  "Supported" rows to keep it focused), columns: Claim (quoted, trimmed) |
  Cited ref | Verdict | What the source's abstract says (source_quote).
- If audit.skipped > 0, add a final italic line: "_N citations with weaker
  claims were not audited (per-run cap)._" using the real number.
- If audit.audited == 0, write exactly: "No in-text citations were available
  to audit at the abstract level."
Keep wording hedged: "Not supported by abstract" means verify against the full
text, not that the citation is wrong.

## Panel Transcript
A subsection per persona showing their raw findings as you received them.
Format:

### Methodology Critic
- (one line per finding, with severity and a one-clause description)

### Statistical Skeptic
- ...

### Data Integrity Officer
- ...

### Editor-in-Chief
- ...

### Equation Analyst
- ...

### Literature Auditor
- ...

### Numerical Realist
- ...

If a persona returned no findings, write "(no findings)" under its heading.
This transcript is for transparency — it's normal for some persona findings
to NOT appear in Critical Blind Spots above (because a single-persona
low-confidence finding shouldn't dominate the summary). The transcript lets
the author see what each reviewer actually said.

Constraints:
- Quote the paper exactly when challenging a claim.
- Do not invent issues. If a layer reported nothing, say so honestly.
- Hedged language for any integrity concern ("appears", "warrants review").
- No emojis, no marketing language, no "I hope this helps" sign-offs.
- Output ONLY the Markdown report — no preamble, no JSON, no code fences.
- Do NOT use Markdown image syntax (`![...](...)`), Markdown link syntax
  (`[text](url)`), or raw HTML in the output. Plain Markdown only.
"""

L4_SYSTEM = _safety.SAFETY_PREAMBLE + "\n\n" + _L4_SYSTEM_CORE


async def run_layer_4_rectify(
    client,
    structure: PaperStructure,
    l1: dict,
    l2: dict,
    l3: dict,
    *,
    anonymity: Optional[dict] = None,
    compliance: Optional[dict] = None,
    deterministic: Optional[list[dict]] = None,
) -> dict:
    """Final synthesis pass — produces the Markdown report the user buys."""
    import json as _json

    extras = ""
    if deterministic:
        # Reproducible, no-LLM checks (statcheck/GRIM/number/text/open-science/reference). These are
        # ground truth — the panel cannot override them. They are our own output (not untrusted user
        # content), so they are not wrapped; we instruct the model to surface them verbatim.
        extras += (
            "\n<deterministic_checks>\n"
            + _json.dumps(deterministic, indent=2)[:20_000]
            + "\n</deterministic_checks>\n"
            + "The deterministic_checks above were computed by reproducible, non-AI engines "
              "(statcheck p-value recomputation, GRIM, arithmetic, reporting-completeness). Treat "
              "them as VERIFIED FACTS that override any contradicting panel claim. Add a section "
              "'## Verified Checks (automated, reproducible)' near the top of the report listing "
              "every error- and warning-severity item with its summary and detail; fold info-level "
              "items in where relevant. If the list is empty, omit the section.\n"
        )
    if anonymity:
        extras += (
            "\n"
            + _safety.wrap_user_content(
                _json.dumps(anonymity, indent=2)[:8_000], "anonymity_check",
            )
            + "\n"
            + "If the anonymity_check reports concrete leaks, add a section "
              "'## Anonymity Concerns (for blinded submission)' AFTER 'Reference "
              "Verification Summary' listing them. If it found no leaks, do NOT "
              "add that section.\n"
        )
    if compliance:
        # Journal name is from our own (trusted) catalog so doesn't need
        # sanitization, but the compliance.results values come from the
        # untrusted manuscript text — wrap the whole block.
        journal_label = compliance.get("journal_name", "journal")
        extras += (
            "\n"
            + _safety.wrap_user_content(
                _json.dumps(compliance, indent=2)[:8_000], "journal_compliance",
            )
            + "\n"
            + f"Add a section '## Journal Compliance ({journal_label})' "
              f"AFTER 'Reference Verification Summary' (and before any Anonymity "
              f"section). List each non-compliant item with the rule it violated, "
              f"the current value, and the target value. If everything passed, "
              f"say so in one sentence.\n"
        )

    text = (
        _safety.wrap_user_content(
            (
                f"Title: {structure.title or '(not extracted)'}\n"
                f"Pages: {structure.page_count}\n"
                f"References extracted: {len(structure.references)} of "
                f"{structure.n_references_total}"
            ),
            "paper_metadata",
        ) + "\n\n"
        + _safety.wrap_user_content(
            structure.abstract or "(not extracted)", "abstract",
        ) + "\n\n"
        + _safety.wrap_user_content(
            _json.dumps(l1, indent=2)[:30_000], "layer_1_vision",
        ) + "\n\n"
        + _safety.wrap_user_content(
            _json.dumps(l2, indent=2)[:30_000], "layer_2_citations",
        ) + "\n\n"
        + _safety.wrap_user_content(
            _json.dumps(
                {
                    "merged_findings": l3.get("merged_findings", []),
                    "panel": l3.get("panel", []),
                },
                indent=2,
            )[:60_000],
            "layer_3_panel",
        ) + "\n"
        + f"{extras}\n"
        + _safety.wrap_user_content(structure.body, "manuscript_body") + "\n\n"
        + "Produce the final Markdown report now."
    )

    try:
        markdown = await _anthropic_message(
            client,
            system=L4_SYSTEM,
            user_content=[{"type": "text", "text": text}],
            max_tokens=RECTIFY_MAX_OUTPUT_TOKENS,
        )
    except Exception:
        logger.exception("L4 rectify call failed")
        return {"status": "error", "markdown": ""}
    return {"status": "ok", "markdown": markdown.strip()}


# ----------------------------------------------------------------------------
# Top-level pipeline
# ----------------------------------------------------------------------------

@dataclass
class ReviewProgress:
    """Mutable progress record written to the modal.Dict so the polling UI
    can render an accurate stage bar."""
    status: str = "running"   # running | done | error
    progress_pct: int = 0
    stage: str = "extracting"   # extracting | vision | citations | panel | rectifying | annotating | done
    started_at: float = 0.0
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result_md: Optional[str] = None
    result_pdf_b64: Optional[str] = None
    annotated_pdf_b64: Optional[str] = None
    layer_status: dict = field(default_factory=dict)
    tier: str = "standard"

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


async def run_review_pipeline(
    pdf_bytes: bytes,
    domain: str,
    on_progress=None,
    *,
    tier: str = "standard",
    journal_pack: Optional[dict] = None,
    anonymity_check: bool = False,
) -> dict:
    """End-to-end review pipeline. Returns a dict with the final result.

    *on_progress* is an optional callable that receives a ReviewProgress
    snapshot after every stage transition. The endpoint wires this up so the
    modal.Dict job entry is updated and the polling UI sees real progress.
    """
    import base64 as _base64
    import time
    import httpx

    # AI-SCoRe (NCA) is its own checklist-based evaluation; delegate and return its result,
    # which shares the {status:"done", result_md, ...} shape the status endpoint expects.
    if domain == "nca":
        from .aiscore import run_aiscore
        # on_progress for the standard pipeline expects ReviewProgress objects; AI-SCoRe emits
        # plain dicts, so we don't forward it. The single-call evaluation is quick and the final
        # {status:"done", result_md, ...} dict is what the status endpoint stores either way.
        return await run_aiscore(pdf_bytes, on_progress=None)

    progress = ReviewProgress(
        status="running", progress_pct=2, stage="extracting",
        started_at=time.time(), tier=tier,
    )

    def _emit():
        if on_progress is not None:
            try:
                on_progress(progress)
            except Exception:
                logger.exception("on_progress callback raised")

    _emit()

    # Layer 0 — extract
    try:
        structure = extract_paper(pdf_bytes)
    except Exception as e:
        logger.exception("paper extraction failed")
        progress.status = "error"
        progress.error = f"extraction_failed: {type(e).__name__}"
        progress.finished_at = time.time()
        _emit()
        return progress.to_dict()

    progress.progress_pct = 15
    progress.stage = "vision"
    _emit()

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=8),
    ) as client:
        # L1 + L2 + deep citation audit run concurrently — no inter-dependencies.
        from latextools import citation_audit
        l1_task = asyncio.create_task(run_layer_1_vision(client, pdf_bytes, domain))
        l2_task = asyncio.create_task(run_layer_2_citations(client, structure.references))
        audit_task = asyncio.create_task(
            citation_audit.run_citation_audit(client, structure)
        )
        l1, l2, audit = await asyncio.gather(l1_task, l2_task, audit_task)
        l2 = attach_audit(l2, audit)
        progress.layer_status["l1"] = l1.get("status", "ok")
        progress.layer_status["l2"] = "ok"
        progress.progress_pct = 45
        progress.stage = "panel"
        _emit()

        # L3 — 4-persona panel debate. For the "deep" tier, run a second
        # pass where each persona sees the others' findings.
        l3 = await run_layer_3_personas(client, structure, l1, l2, domain)
        if tier == "deep":
            progress.progress_pct = 65
            progress.stage = "panel"
            progress.layer_status["l3"] = "deep_pass_1_done"
            _emit()
            l3 = await run_layer_3_deep_pass(client, structure, l1, l2, l3, domain)
        progress.layer_status["l3"] = "ok"
        progress.progress_pct = 80
        progress.stage = "rectifying"
        _emit()

        # Anonymity check (optional add-on)
        anonymity_result = None
        if anonymity_check:
            from latextools import paperreview_extras
            try:
                anonymity_result = await paperreview_extras.run_anonymity_check(
                    client, structure,
                )
            except Exception:
                logger.exception("anonymity check failed")

        # Journal-compliance check (rule-based, no API call)
        compliance_result = None
        if journal_pack:
            from latextools import journals
            try:
                compliance_result = journals.check_compliance(
                    structure, journal_pack,
                )
            except Exception:
                logger.exception("journal compliance check failed")

        # Deterministic ground-truth checks (no LLM): statcheck/GRIM, number arithmetic, text
        # hygiene, open-science statements, and reference integrity over the extracted bibliography.
        deterministic_findings: list[dict] = []
        try:
            from latextools import manuscript_checks
            import datetime as _dt
            deterministic_findings = [
                f.to_dict() for f in manuscript_checks.all_findings(
                    structure.body, structure.references,
                    current_year=_dt.date.today().year,
                )
            ]
        except Exception:
            logger.exception("deterministic checks failed (non-fatal)")

        # L4 — synthesis
        l4 = await run_layer_4_rectify(
            client, structure, l1, l2, l3,
            anonymity=anonymity_result,
            compliance=compliance_result,
            deterministic=deterministic_findings,
        )
        progress.layer_status["l4"] = l4.get("status", "ok")

    # Annotated PDF (post-pipeline; no further LLM calls).
    progress.progress_pct = 92
    progress.stage = "annotating"
    _emit()
    annotated_b64: Optional[str] = None
    try:
        from latextools import pdf_annotate
        annotated_bytes = pdf_annotate.annotate_pdf(pdf_bytes, l1=l1, l2=l2, l3=l3)
        if annotated_bytes:
            annotated_b64 = _base64.b64encode(annotated_bytes).decode("ascii")
            progress.layer_status["annotation"] = "ok"
    except Exception:
        logger.exception("PDF annotation failed (non-fatal)")
        progress.layer_status["annotation"] = "error"

    progress.progress_pct = 100
    progress.stage = "done"
    progress.status = "done" if l4.get("status") == "ok" else "error"
    progress.result_md = l4.get("markdown") or ""
    progress.annotated_pdf_b64 = annotated_b64
    progress.finished_at = time.time()
    _emit()
    return {
        **progress.to_dict(),
        "structure_summary": structure.to_dict(),
        "l1_summary": {"status": l1.get("status"), "n_findings": len(l1.get("findings", []))},
        "l2_summary": {
            "checked": l2.get("checked", 0),
            "verified": l2.get("verified", 0),
            "issues": len(l2.get("issues", [])),
        },
        "l3_summary": {
            "n_findings": l3.get("n_findings", 0),
            "n_high_consensus": l3.get("n_high_consensus", 0),
        },
        "anonymity_result": anonymity_result,
        "compliance_result": compliance_result,
        "deterministic_findings": deterministic_findings,
    }


# ----------------------------------------------------------------------------
# Text-based section splicing (used by the free Word Counter / Document
# Insights tool). Unlike extract_paper(), this works on already-extracted
# plain text from any format, not just PDF bytes.
# ----------------------------------------------------------------------------

# Canonical section -> header-name variants. Order matters: we scan the text
# for the first occurrence of each header and slice between them.
_WS_SECTION_HEADERS = [
    ("abstract", ["abstract", "summary"]),
    ("introduction", ["introduction", "background"]),
    ("methods", ["methods", "materials and methods", "method", "methodology",
                 "experimental", "experimental setup"]),
    ("results", ["results", "findings", "results and discussion"]),
    ("discussion", ["discussion"]),
    ("conclusion", ["conclusion", "conclusions", "concluding remarks"]),
    ("references", ["references", "bibliography", "works cited",
                    "literature cited", "reference list"]),
    ("appendix", ["appendix", "appendices", "supplementary material",
                  "supplementary information", "supporting information"]),
    ("acknowledgements", ["acknowledgements", "acknowledgments"]),
]


def splice_text_sections(text: str) -> dict:
    """Best-effort split of an academic manuscript's plain text into named
    sections. Returns a dict; only detected sections appear. Also returns a
    "figure_captions" list. Designed to be tolerant — when nothing matches,
    returns {"body": text}.

    This is a heuristic over header lines: a short line (<= 60 chars) whose
    text (minus any leading numbering) matches a known section name is
    treated as a section boundary.
    """
    if not text or not text.strip():
        return {"body": ""}

    lines = text.split("\n")

    # Build a flat list of section variant -> canonical for matching.
    variant_to_canon = {}
    for canon, variants in _WS_SECTION_HEADERS:
        for v in variants:
            variant_to_canon[v] = canon

    # Find header boundaries: (line_index, canonical_name)
    boundaries = []
    seen_canon = set()
    for idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped or len(stripped) > 60:
            continue
        # Strip leading numbering like "3.", "III.", "3.1"
        cleaned = re.sub(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.)\s*", "", stripped)
        cleaned = cleaned.strip().rstrip(":").lower()
        canon = variant_to_canon.get(cleaned)
        if canon and canon not in seen_canon:
            boundaries.append((idx, canon))
            seen_canon.add(canon)

    figure_captions = []
    for m in re.finditer(
        r"^\s*(?:Figure|Fig\.|Table)\s+\d+[:.\s]+([^\n]+)",
        text, re.MULTILINE,
    ):
        cap = re.sub(r"\s+", " ", m.group(1).strip())[:300]
        if cap:
            figure_captions.append(cap)

    if not boundaries:
        out = {"body": text.strip()}
        if figure_captions:
            out["figure_captions"] = figure_captions
        return out

    # Anything before the first detected header is the "header/title" zone;
    # fold it into body unless an abstract starts it.
    sections = {}
    first_idx = boundaries[0][0]
    preamble = "\n".join(lines[:first_idx]).strip()

    for i, (line_idx, canon) in enumerate(boundaries):
        start = line_idx + 1
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if body:
            sections[canon] = body

    # "body" = everything that's narrative (intro/methods/results/discussion/
    # conclusion) plus the preamble, so the UI can offer "main text" easily.
    narrative_keys = ["introduction", "methods", "results", "discussion", "conclusion"]
    body_parts = [preamble] if preamble else []
    for k in narrative_keys:
        if k in sections:
            body_parts.append(sections[k])
    if body_parts:
        sections["body"] = "\n\n".join(body_parts)
    elif "body" not in sections:
        sections["body"] = preamble or text.strip()

    if figure_captions:
        sections["figure_captions"] = figure_captions

    return sections
