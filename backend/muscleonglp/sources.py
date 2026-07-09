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
            "American College of Sports Medicine Position Stand: Resistance "
            "Training Prescription for Muscle Function, Hypertrophy, and "
            "Physical Performance in Healthy Adults: An Overview of Reviews. "
            "Guidance: 2-3 resistance-training sessions per week, 8-12 "
            "exercises per session, 2-3 sets of 8-15 reps at 60-80% of "
            "one-rep max."
        ),
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12965823/",
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
