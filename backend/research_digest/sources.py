"""Search configuration for the MuscleOnGLP weekly research roundup.

Two high-precision sources are used (see harvester.py): PubMed E-utilities
(peer-reviewed, clean abstracts) and Europe PMC (adds preprints and non-Medline
records). A direct medRxiv/bioRxiv feed was evaluated and dropped: filtering the
full daily preprint firehose by keyword produced mostly false positives, and
Europe PMC already surfaces the on-topic preprints with far better precision.

The query intentionally pairs a GLP-1 drug term AND a muscle/body-composition
term, so a paper about (say) semaglotide and cardiovascular outcomes, or about
muscle in an unrelated context, does not match.
"""
from __future__ import annotations

# GLP-1 / incretin drug terms (generic + brand names).
DRUG_TERMS = [
    "semaglutide", "tirzepatide", "liraglutide", "retatrutide",
    "GLP-1", "GLP-1 receptor agonist", "incretin",
    "Ozempic", "Wegovy", "Mounjaro", "Zepbound",
]

# Next-generation multi-agonists: the frontier beyond single GLP-1 and the
# GLP-1/GIP duals. Retatrutide (in DRUG_TERMS above) is the GLP-1/GIP/glucagon
# TRIPLE agonist; the newer quadruple agonists add PYY. These are named
# molecules (high precision) plus the mechanism phrases that class papers use
# when no brand name exists yet. The LLM curator drops any tangential match.
NEXT_GEN_DRUG_TERMS = [
    # named multi-agonist molecules in / near clinical development
    "survodutide", "mazdutide", "pemvidutide", "efinopegdutide",
    "ecnoglutide", "orforglipron", "cagrilintide", "CagriSema",
    # mechanism / receptor phrases (catch the class before a brand name lands)
    "GIP receptor agonist", "glucagon receptor agonist", "amylin agonist",
    "dual agonist", "triple agonist", "quadruple agonist", "peptide YY",
]

# Muscle / lean-mass / training / protein terms.
TOPIC_TERMS = [
    "lean mass", "muscle", "muscle mass", "skeletal muscle", "sarcopenia",
    "body composition", "fat-free mass", "resistance training",
    "protein intake", "muscle strength", "physical function",
]


def _or_group(terms: list[str]) -> str:
    return " OR ".join(f'"{t}"' if " " in t else t for t in terms)


def core_query() -> str:
    """(drug OR drug ...) AND (topic OR topic ...). The drug group spans both
    the established GLP-1 agonists and the next-gen multi-agonist frontier."""
    drugs = _or_group(DRUG_TERMS + NEXT_GEN_DRUG_TERMS)
    return f"({drugs}) AND ({_or_group(TOPIC_TERMS)})"


def europepmc_query(start_date: str, end_date: str) -> str:
    """Core query restricted to a first-publication-date window (YYYY-MM-DD)."""
    return f"{core_query()} AND (FIRST_PDATE:[{start_date} TO {end_date}])"
