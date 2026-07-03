"""Journal Compliance Pack — rule library and rule-based checker.

Each journal entry encodes the must-meet submission requirements that can
be checked automatically from a PaperStructure: abstract word/char limits,
manuscript word-count cap, presence of structured sections (Background /
Methods / Results / Discussion / etc.), reference style hints, and figure
file requirements. We do NOT make an LLM call for compliance — it's
deterministic rules over the extracted structure plus a few regex passes.

Rules are intentionally conservative: when a rule can't be unambiguously
checked (e.g. figure resolution from a PDF render), we emit a "manual
verification needed" hint rather than a false positive.

The pack is loaded from JOURNAL_SPECS below — a literal dict so it ships
with the module. To add a new journal, append a new entry and document the
sources in the spec's `sources` field.
"""
from __future__ import annotations

import re
from typing import Optional


# Section names commonly required; structure-checks look for any of the
# variants in the manuscript body.
_SECTION_VARIANTS: dict[str, list[str]] = {
    "introduction": ["introduction", "background"],
    "methods": ["methods", "materials and methods", "experimental"],
    "results": ["results", "findings"],
    "discussion": ["discussion"],
    "conclusion": ["conclusion", "conclusions"],
    "limitations": ["limitations", "limitations of the study"],
    "data_availability": ["data availability", "data and code availability"],
    "ethics_statement": ["ethics statement", "ethics", "ircc", "irb", "iacuc"],
    "competing_interests": [
        "competing interests", "conflict of interest",
        "declaration of interests",
    ],
    "author_contributions": ["author contributions", "author contribution"],
}


# Built-in journal specs. v1 includes 25 widely-targeted journals across
# the four supported domains. Each spec is conservative; verify against
# the journal's current author guide before claiming "compliant".
JOURNAL_SPECS: dict[str, dict] = {
    # ------------------ Machine Learning / Computer Science --------------
    "neurips": {
        "name": "NeurIPS (Conference on Neural Information Processing Systems)",
        "domain": "machine_learning",
        "abstract_max_words": 250,
        "manuscript_max_pages": 9,        # main body, refs/appendix unlimited
        "manuscript_max_words": None,
        "required_sections": ["introduction", "methods", "results"],
        "recommended_sections": [
            "limitations", "ethics_statement", "data_availability",
        ],
        "reference_style_hint": "numbered (NeurIPS bibstyle)",
        "figures_in_text": True,
        "anonymous_submission": True,
        "notes": "Double-blind. Author info, acknowledgements, and self-cites that reveal identity must be stripped from initial submission.",
        "sources": "https://neurips.cc/Conferences/2024/CallForPapers",
    },
    "icml": {
        "name": "ICML (International Conference on Machine Learning)",
        "domain": "machine_learning",
        "abstract_max_words": 250,
        "manuscript_max_pages": 8,
        "manuscript_max_words": None,
        "required_sections": ["introduction", "methods", "results"],
        "recommended_sections": ["limitations", "data_availability"],
        "reference_style_hint": "numbered (ICML bibstyle)",
        "figures_in_text": True,
        "anonymous_submission": True,
        "notes": "Double-blind. Reproducibility checklist required.",
        "sources": "https://icml.cc/Conferences/2024/CallForPapers",
    },
    "iclr": {
        "name": "ICLR (International Conference on Learning Representations)",
        "domain": "machine_learning",
        "abstract_max_words": 250,
        "manuscript_max_pages": 10,
        "manuscript_max_words": None,
        "required_sections": ["introduction", "methods", "results"],
        "recommended_sections": ["limitations", "ethics_statement"],
        "reference_style_hint": "numbered",
        "figures_in_text": True,
        "anonymous_submission": True,
        "notes": "Double-blind. Open review.",
        "sources": "https://iclr.cc/Conferences/2024/CallForPapers",
    },
    "aaai": {
        "name": "AAAI Conference on Artificial Intelligence",
        "domain": "machine_learning",
        "abstract_max_words": 200,
        "manuscript_max_pages": 7,
        "manuscript_max_words": None,
        "required_sections": ["introduction", "methods", "results"],
        "recommended_sections": ["limitations"],
        "reference_style_hint": "numbered (AAAI style)",
        "figures_in_text": True,
        "anonymous_submission": True,
        "notes": "Author info goes in supplementary at submission.",
        "sources": "https://aaai.org/conference/aaai/",
    },
    "tmlr": {
        "name": "Transactions on Machine Learning Research (TMLR)",
        "domain": "machine_learning",
        "abstract_max_words": 350,
        "manuscript_max_pages": None,
        "manuscript_max_words": None,
        "required_sections": ["introduction", "methods", "results"],
        "recommended_sections": ["limitations"],
        "reference_style_hint": "TMLR style file",
        "figures_in_text": True,
        "anonymous_submission": False,
        "notes": "Single-blind, rolling submission, certified vs accepted vs survey distinction.",
        "sources": "https://jmlr.org/tmlr/",
    },
    "jmlr": {
        "name": "Journal of Machine Learning Research (JMLR)",
        "domain": "machine_learning",
        "abstract_max_words": 250,
        "manuscript_max_pages": None,
        "manuscript_max_words": None,
        "required_sections": ["introduction", "methods", "results", "discussion"],
        "recommended_sections": ["limitations", "data_availability"],
        "reference_style_hint": "JMLR style",
        "figures_in_text": True,
        "anonymous_submission": False,
        "notes": "Code release required.",
        "sources": "https://jmlr.org/",
    },

    # ----------------------------- Biomedicine ----------------------------
    "nature": {
        "name": "Nature",
        "domain": "biomedicine",
        "abstract_max_words": 150,
        "manuscript_max_words": 4500,
        "manuscript_max_pages": None,
        "required_sections": [
            "methods", "results", "discussion",
        ],
        "recommended_sections": [
            "data_availability", "ethics_statement", "competing_interests",
            "author_contributions",
        ],
        "reference_style_hint": "Nature numbered (max ~50 in main text)",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Strict 4,500-word limit on main text. Methods can be 3,000 additional words.",
        "sources": "https://www.nature.com/nature/for-authors/formatting-guide",
    },
    "science": {
        "name": "Science",
        "domain": "biomedicine",
        "abstract_max_words": 125,
        "manuscript_max_words": 4500,
        "manuscript_max_pages": None,
        "required_sections": ["methods", "results", "discussion"],
        "recommended_sections": [
            "data_availability", "ethics_statement", "competing_interests",
        ],
        "reference_style_hint": "Science numbered (max ~50)",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Research Articles 4,500 words; Reports 2,500 words.",
        "sources": "https://www.science.org/content/page/instructions-preparing-initial-manuscript",
    },
    "cell": {
        "name": "Cell",
        "domain": "biomedicine",
        "abstract_max_words": 150,
        "manuscript_max_words": None,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "results", "discussion", "methods",
        ],
        "recommended_sections": [
            "data_availability", "ethics_statement",
            "author_contributions", "competing_interests",
        ],
        "reference_style_hint": "Cell numbered",
        "figures_in_text": True,
        "anonymous_submission": False,
        "notes": "STAR Methods structured format required.",
        "sources": "https://www.cell.com/cell/authors",
    },
    "nature-medicine": {
        "name": "Nature Medicine",
        "domain": "biomedicine",
        "abstract_max_words": 150,
        "manuscript_max_words": 4500,
        "manuscript_max_pages": None,
        "required_sections": ["methods", "results", "discussion"],
        "recommended_sections": [
            "data_availability", "ethics_statement", "competing_interests",
        ],
        "reference_style_hint": "Nature numbered",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Clinical trial registration required for trial papers.",
        "sources": "https://www.nature.com/nm/for-authors",
    },
    "plos-one": {
        "name": "PLOS ONE",
        "domain": "biomedicine",
        "abstract_max_words": 300,
        "manuscript_max_words": None,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "methods", "results", "discussion",
        ],
        "recommended_sections": [
            "data_availability", "ethics_statement", "competing_interests",
        ],
        "reference_style_hint": "PLOS Vancouver numbered",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Data Availability Statement required.",
        "sources": "https://journals.plos.org/plosone/s/submission-guidelines",
    },
    "jama": {
        "name": "JAMA",
        "domain": "biomedicine",
        "abstract_max_words": 350,
        "manuscript_max_words": 3000,
        "manuscript_max_pages": None,
        "required_sections": ["methods", "results", "discussion"],
        "recommended_sections": [
            "limitations", "ethics_statement", "competing_interests",
        ],
        "reference_style_hint": "AMA numbered",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "CONSORT/STROBE/PRISMA checklist required where applicable.",
        "sources": "https://jamanetwork.com/journals/jama/pages/instructions-for-authors",
    },
    "nejm": {
        "name": "New England Journal of Medicine (NEJM)",
        "domain": "biomedicine",
        "abstract_max_words": 250,
        "manuscript_max_words": 2700,
        "manuscript_max_pages": None,
        "required_sections": ["methods", "results", "discussion"],
        "recommended_sections": ["ethics_statement", "competing_interests"],
        "reference_style_hint": "NEJM numbered (≤40)",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Trial registration mandatory.",
        "sources": "https://www.nejm.org/author-center",
    },
    "lancet": {
        "name": "The Lancet",
        "domain": "biomedicine",
        "abstract_max_words": 300,
        "manuscript_max_words": 4500,
        "manuscript_max_pages": None,
        "required_sections": ["methods", "results", "discussion"],
        "recommended_sections": [
            "limitations", "ethics_statement", "competing_interests",
            "author_contributions",
        ],
        "reference_style_hint": "Vancouver numbered",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Structured abstract: Background, Methods, Findings, Interpretation, Funding.",
        "sources": "https://www.thelancet.com/lancet/information-for-authors",
    },
    "bmj": {
        "name": "The BMJ",
        "domain": "biomedicine",
        "abstract_max_words": 350,
        "manuscript_max_words": 3500,
        "manuscript_max_pages": None,
        "required_sections": ["methods", "results", "discussion"],
        "recommended_sections": [
            "limitations", "ethics_statement", "competing_interests",
        ],
        "reference_style_hint": "Vancouver numbered",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Patient and public involvement statement required.",
        "sources": "https://www.bmj.com/about-bmj/resources-authors",
    },

    # ------------------ Psychology / Social science -----------------------
    "psych-science": {
        "name": "Psychological Science",
        "domain": "psychology_social",
        "abstract_max_words": 150,
        "manuscript_max_words": 4000,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "methods", "results", "discussion",
        ],
        "recommended_sections": [
            "data_availability", "competing_interests",
        ],
        "reference_style_hint": "APA 7th",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Open data, open materials, preregistration badges encouraged.",
        "sources": "https://journals.sagepub.com/author-instructions/PSS",
    },
    "jpsp": {
        "name": "Journal of Personality and Social Psychology",
        "domain": "psychology_social",
        "abstract_max_words": 250,
        "manuscript_max_words": 12000,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "methods", "results", "discussion",
        ],
        "recommended_sections": [
            "limitations", "data_availability", "competing_interests",
        ],
        "reference_style_hint": "APA 7th",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Power analysis and preregistration strongly encouraged.",
        "sources": "https://www.apa.org/pubs/journals/psp",
    },
    "cognition": {
        "name": "Cognition",
        "domain": "psychology_social",
        "abstract_max_words": 250,
        "manuscript_max_words": None,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "methods", "results", "discussion",
        ],
        "recommended_sections": ["data_availability"],
        "reference_style_hint": "Elsevier APA",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Cognition prefers concise reports.",
        "sources": "https://www.sciencedirect.com/journal/cognition",
    },
    "amj": {
        "name": "Academy of Management Journal",
        "domain": "psychology_social",
        "abstract_max_words": 250,
        "manuscript_max_words": 12000,
        "manuscript_max_pages": 40,
        "required_sections": [
            "introduction", "methods", "results", "discussion",
        ],
        "recommended_sections": ["limitations"],
        "reference_style_hint": "AMJ style",
        "figures_in_text": False,
        "anonymous_submission": True,
        "notes": "Double-blind. 40-page hard cap including all elements.",
        "sources": "https://aom.org/research/journals/journal",
    },

    # ------------------- Chemistry / Materials ----------------------------
    "jacs": {
        "name": "Journal of the American Chemical Society (JACS)",
        "domain": "chemistry_materials",
        "abstract_max_words": 200,
        "manuscript_max_words": 4500,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "results", "discussion", "methods",
        ],
        "recommended_sections": ["data_availability", "competing_interests"],
        "reference_style_hint": "ACS numbered",
        "figures_in_text": True,
        "anonymous_submission": False,
        "notes": "Communications and Articles have different limits.",
        "sources": "https://pubs.acs.org/journal/jacsat",
    },
    "angew-chem": {
        "name": "Angewandte Chemie International Edition",
        "domain": "chemistry_materials",
        "abstract_max_words": 200,
        "manuscript_max_words": 6000,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "results", "discussion",
        ],
        "recommended_sections": ["data_availability"],
        "reference_style_hint": "Angewandte Chemie style",
        "figures_in_text": True,
        "anonymous_submission": False,
        "notes": "Communication ≤ 4,500 words; Research Article ≤ 6,000.",
        "sources": "https://onlinelibrary.wiley.com/journal/15213773",
    },
    "nature-materials": {
        "name": "Nature Materials",
        "domain": "chemistry_materials",
        "abstract_max_words": 150,
        "manuscript_max_words": 4500,
        "manuscript_max_pages": None,
        "required_sections": ["methods", "results", "discussion"],
        "recommended_sections": [
            "data_availability", "competing_interests",
        ],
        "reference_style_hint": "Nature numbered",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Methods up to 3,000 additional words. CCDC deposition required for crystal structures.",
        "sources": "https://www.nature.com/nmat/for-authors",
    },
    "nature-chemistry": {
        "name": "Nature Chemistry",
        "domain": "chemistry_materials",
        "abstract_max_words": 150,
        "manuscript_max_words": 4500,
        "manuscript_max_pages": None,
        "required_sections": ["methods", "results", "discussion"],
        "recommended_sections": [
            "data_availability", "competing_interests",
        ],
        "reference_style_hint": "Nature numbered",
        "figures_in_text": False,
        "anonymous_submission": False,
        "notes": "Methods up to 3,000 additional words.",
        "sources": "https://www.nature.com/nchem/for-authors",
    },
    "acs-nano": {
        "name": "ACS Nano",
        "domain": "chemistry_materials",
        "abstract_max_words": 200,
        "manuscript_max_words": None,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "results", "discussion", "methods",
        ],
        "recommended_sections": ["data_availability"],
        "reference_style_hint": "ACS numbered",
        "figures_in_text": True,
        "anonymous_submission": False,
        "notes": "Strong novelty bar; characterisation completeness scrutinised.",
        "sources": "https://pubs.acs.org/journal/ancac3",
    },
    "advanced-materials": {
        "name": "Advanced Materials",
        "domain": "chemistry_materials",
        "abstract_max_words": 200,
        "manuscript_max_words": None,
        "manuscript_max_pages": None,
        "required_sections": [
            "introduction", "results", "discussion",
        ],
        "recommended_sections": ["data_availability"],
        "reference_style_hint": "Advanced Materials style",
        "figures_in_text": True,
        "anonymous_submission": False,
        "notes": "Communication, Research Article, and Review formats differ.",
        "sources": "https://onlinelibrary.wiley.com/journal/15214095",
    },
}


def list_journals_for_domain(domain: str) -> list[dict]:
    """Return a list of journal options for a domain (or all if 'general')."""
    out = []
    for key, spec in JOURNAL_SPECS.items():
        if domain in (None, "general") or spec.get("domain") == domain:
            out.append({"key": key, "name": spec["name"], "domain": spec.get("domain")})
    return out


def _word_count(s: str) -> int:
    if not s:
        return 0
    return len(re.findall(r"\b\w+\b", s))


def _has_section(body: str, variants: list[str]) -> bool:
    """Detect whether the manuscript body contains any of the section
    name variants as a header. Heuristic: look for the variant at the
    start of a line, optionally numbered (e.g. "3. Methods")."""
    low = body.lower()
    for v in variants:
        pattern = rf"(?:^|\n)\s*(?:\d+\.?\s+)?{re.escape(v)}\b"
        if re.search(pattern, low, re.MULTILINE):
            return True
    return False


def check_compliance(structure, journal_key_or_spec) -> Optional[dict]:
    """Run the journal compliance pack against a PaperStructure.

    Accepts a journal key (string) or a spec dict. Returns a results dict
    with per-rule pass/fail/warn outcomes. None inputs → None.
    """
    if not journal_key_or_spec:
        return None
    if isinstance(journal_key_or_spec, str):
        spec = JOURNAL_SPECS.get(journal_key_or_spec.lower())
        if spec is None:
            return {"error": f"Unknown journal key: {journal_key_or_spec}"}
        journal_key = journal_key_or_spec.lower()
    else:
        spec = journal_key_or_spec
        journal_key = spec.get("key", "custom")

    body = structure.body or ""
    abstract = structure.abstract or ""

    results: list[dict] = []

    # Abstract word count
    if spec.get("abstract_max_words"):
        wc = _word_count(abstract)
        cap = spec["abstract_max_words"]
        results.append({
            "rule": "abstract_word_count",
            "label": "Abstract word count",
            "status": "fail" if wc > cap else "pass",
            "current": wc,
            "target": f"≤ {cap}",
            "note": (
                "Trim the abstract." if wc > cap
                else "Within limit." if wc > 0
                else "Abstract not detected — verify manually."
            ),
        })

    # Manuscript word count
    if spec.get("manuscript_max_words"):
        wc = _word_count(body)
        cap = spec["manuscript_max_words"]
        # Body is capped at MAX_BODY_CHARS upstream — flag this as
        # approximate to avoid false positives on truncated extractions.
        results.append({
            "rule": "manuscript_word_count",
            "label": "Manuscript body word count",
            "status": "warn" if wc < cap * 0.9 else ("fail" if wc > cap else "pass"),
            "current": wc,
            "target": f"≤ {cap}",
            "note": (
                "Word count above target — trim main text."
                if wc > cap else
                f"Well under target ({wc} extracted vs. {cap} cap) — this may "
                f"indicate truncated extraction rather than a genuinely short "
                f"manuscript; verify with your editor's word count."
                if wc < cap * 0.9 else
                f"Approximately within target ({wc} extracted; verify with your "
                f"editor's word count)."
            ),
        })

    # Page count vs cap
    if spec.get("manuscript_max_pages"):
        cap = spec["manuscript_max_pages"]
        results.append({
            "rule": "page_count",
            "label": "Page count (main + supplementary)",
            "status": "warn" if structure.page_count > cap else "pass",
            "current": structure.page_count,
            "target": f"≤ {cap} pages",
            "note": (
                "PDF exceeds journal page cap; check if main vs supplementary "
                "are bundled."
                if structure.page_count > cap else "Within page cap."
            ),
        })

    # Required sections present
    for sec_key in spec.get("required_sections", []):
        variants = _SECTION_VARIANTS.get(sec_key, [sec_key.replace("_", " ")])
        present = _has_section(body, variants)
        results.append({
            "rule": f"section_{sec_key}",
            "label": f"Required section: {sec_key.replace('_', ' ').title()}",
            "status": "pass" if present else "fail",
            "current": "present" if present else "not found",
            "target": "section header detected",
            "note": (
                f"Add a clearly labelled {sec_key.replace('_', ' ')} section."
                if not present else "Detected in the manuscript."
            ),
        })

    # Recommended sections present
    for sec_key in spec.get("recommended_sections", []):
        variants = _SECTION_VARIANTS.get(sec_key, [sec_key.replace("_", " ")])
        present = _has_section(body, variants)
        results.append({
            "rule": f"recommended_{sec_key}",
            "label": f"Recommended section: {sec_key.replace('_', ' ').title()}",
            "status": "pass" if present else "warn",
            "current": "present" if present else "not found",
            "target": "section header detected",
            "note": (
                f"This journal recommends a {sec_key.replace('_', ' ')} section."
                if not present else "Detected."
            ),
        })

    # Reference-style hint (manual verify)
    if spec.get("reference_style_hint"):
        results.append({
            "rule": "reference_style",
            "label": "Reference style",
            "status": "info",
            "current": "verify manually",
            "target": spec["reference_style_hint"],
            "note": (
                "Reference formatting can't be auto-checked end-to-end. "
                "Compare your reference list against the journal's style."
            ),
        })

    # Anonymous submission warning
    if spec.get("anonymous_submission"):
        results.append({
            "rule": "anonymous_submission",
            "label": "Double-blind submission",
            "status": "info",
            "current": "manual",
            "target": "remove author identity from manuscript + acks",
            "note": (
                "This venue is double-blind. Strip author names, "
                "affiliations, acknowledgements, and grant numbers from the "
                "submission PDF. The Anonymity Check add-on will scan for "
                "obvious leaks."
            ),
        })

    summary = {
        "n_pass": sum(1 for r in results if r["status"] == "pass"),
        "n_fail": sum(1 for r in results if r["status"] == "fail"),
        "n_warn": sum(1 for r in results if r["status"] == "warn"),
        "n_info": sum(1 for r in results if r["status"] == "info"),
    }
    return {
        "journal_key": journal_key,
        "journal_name": spec["name"],
        "domain": spec.get("domain"),
        "notes": spec.get("notes", ""),
        "sources": spec.get("sources", ""),
        "results": results,
        "summary": summary,
    }
