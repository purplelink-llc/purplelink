# backend/tests/test_benchmark_cited_check.py
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from benchmark.cited_check import (
    PaperText, apply_cited_check, check_gap, find_citation, is_counted_gap, split_title_hint, squash,
    strictly_exists, titles_match,
)

TEXT = """1 Introduction
We build on transformers [3].
References
[1] J. Doe. Some unrelated work on graphs. In KDD, 2020.
[2] D. Jiang et al. T2I-R1: Reinforcing image genera-
tion with collaborative semantic-level and token-level CoT. arXiv:2505.00703, 2025.
[3] A.Vaswani,N.Shazeer. Attentionisallyouneed. In NeurIPS, 2017.
[4] K. Black. Training diffusion models with reinforcement learning. doi:10.1234/ddpo.2023.
"""
REFS = [
    {"raw": "J. Doe. Some unrelated work on graphs. In KDD, 2020.", "doi": ""},
    {"raw": "D. Jiang et al. T2I-R1: Reinforcing image generation with collaborative "
            "semantic-level and token-level CoT. arXiv:2505.00703, 2025.", "doi": ""},
    {"raw": "A. Vaswani. Attention is all you need. In NeurIPS, 2017.", "doi": ""},
    {"raw": "K. Black. Training diffusion models with RL. doi:10.1234/ddpo.2023.", "doi": "10.1234/ddpo.2023"},
]


def _paper():
    return PaperText.build(TEXT, REFS)


def _gap(found_title="", found_doi="", hint="", status="confirmed_exists"):
    return {
        "candidate_title_hint": hint,
        "verification": {"status": status, "found_title": found_title, "found_doi": found_doi},
    }


def test_squash_ignores_spacing_case_and_line_break_hyphens():
    assert squash("Attention Is All\nYou-Need") == "attentionisallyouneed"
    assert squash("genera-\ntion") == "generation"


def test_title_found_despite_line_break_hyphen():
    how = find_citation(_paper(), title="T2I-R1: Reinforcing Image Generation with Collaborative "
                                         "Semantic-level and Token-level CoT")
    assert how == "title"


def test_title_found_when_pdf_text_merged_words():
    assert find_citation(_paper(), title="Attention Is All You Need") == "title"


def test_doi_match_and_supplement_suffix():
    assert find_citation(_paper(), doi="10.1234/ddpo.2023") == "doi"
    assert find_citation(_paper(), doi="10.1234/ddpo.2023.s001") == "doi"


def test_arxiv_doi_matches_arxiv_id_in_text():
    assert find_citation(_paper(), doi="10.48550/arXiv.2505.00703") == "arxiv_id"


def test_main_title_before_colon():
    assert find_citation(_paper(), title="Some unrelated work on graphs: a longer subtitle here") == "main_title"


def test_reference_token_coverage():
    # Word order changed and one word differs, so no substring match.
    assert find_citation(_paper(), title="Unrelated Graphs Work Some Survey") == "reference_tokens"


def test_absent_work_is_not_found():
    assert find_citation(_paper(), title="Inference-Time Scaling for Diffusion Models beyond Denoising Steps",
                         doi="10.9999/nothing") is None


def test_short_title_never_matches_by_accident():
    assert find_citation(_paper(), title="CoT") is None


def test_split_title_hint():
    assert split_title_hint("A title; Another title ;") == ["A title", "Another title"]
    assert split_title_hint("unknown") == []


def test_check_gap_counts_cited_if_any_hint_title_is_cited():
    gap = _gap(found_title="Inference-Time Scaling for Diffusion Models", found_doi="10.9/x",
               hint="Inference-Time Scaling for Diffusion Models; Attention Is All You Need")
    verdict = check_gap(_paper(), gap)
    assert verdict["cited"] is True
    assert verdict["matched"] == "Attention Is All You Need"


def test_check_gap_not_cited():
    gap = _gap(found_title="Inference-Time Scaling for Diffusion Models", found_doi="10.9/x",
               hint="Inference-Time Scaling for Diffusion Models")
    assert check_gap(_paper(), gap) == {"cited": False, "how": None, "matched": None}


def test_is_counted_gap_needs_both_conditions():
    [cited, uncited] = apply_cited_check([
        _gap(found_title="Attention Is All You Need", hint="Attention Is All You Need"),
        _gap(found_title="Inference-Time Scaling for Diffusion Models",
             hint="Inference-Time Scaling for Diffusion Models (NeurIPS 2025)"),
    ], TEXT, REFS)
    assert not is_counted_gap(cited)
    assert is_counted_gap(uncited)
    [weak] = apply_cited_check([_gap(found_title="Something Else Entirely Here", status="weak_match")], TEXT, REFS)
    assert not is_counted_gap(weak)
    # Never checked: does not count.
    assert not is_counted_gap(_gap(found_title="Inference-Time Scaling for Diffusion Models",
                                   hint="Inference-Time Scaling for Diffusion Models"))


def test_crossref_neighbour_title_does_not_count():
    [g] = apply_cited_check([_gap(found_title="Conformalized Composite Quantile Regression",
                                  hint="Conformalized Quantile Regression")], TEXT, REFS)
    assert g["already_cited"]["cited"] is False
    assert not strictly_exists(g)
    assert not is_counted_gap(g)
    assert not strictly_exists(_gap(found_title="Fixed-Weight Difference Target Propagation",
                                    hint="Difference Target Propagation"))


def test_titles_match():
    assert titles_match("Exact imposition of boundary conditions with distance functions (CMAME, 2022)",
                        "Exact imposition of boundary conditions with distance functions")
    assert titles_match("Twilight: Adaptive Attention Sparsity with Hierarchical Top-p Pruning",
                        "Twilight: Adaptive Attention Sparsity with Hierarchical Top-$p$  Pruning")
    assert not titles_match("Conformalized Quantile Regression", "Conformalized Composite Quantile Regression")


def test_title_split_across_interleaved_two_column_lines():
    # pdfplumber output from a real two-column bibliography (arXiv 2610.42112, 2026-11-02).
    text = "\n".join([
        "//arxiv.org/abs/2312.00752. [27] Chaofan Lin, Jiaming Tang, Shuo Yang, Hanshuo Wang,",
        "Tian Tang, Boyu Tian, Ion Stoica, Song Han, and",
        "Mingyu Gao. Twilight: Adaptive attention sparsity with",
        "tanu Acharya, Dima Rekesh, Fei Jia, Yang Zhang, and",
        "hierarchical top-p pruning. In NeurIPS, 2025.",
    ])
    paper = PaperText.build(text, [])
    assert find_citation(paper, title="Twilight: Adaptive Attention Sparsity with Hierarchical Top-p Pruning") == "text_window"
