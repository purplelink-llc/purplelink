import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from latextools import citation_audit as ca
from latextools.papercheck import PaperStructure, PaperReference


def test_extract_numeric_claim_citations():
    body = (
        "Transformers improve translation quality [12]. "
        "The sky is blue. "
        "Our method outperforms all baselines [3, 4]."
    )
    struct = PaperStructure(body=body)
    claims = ca.extract_claim_citations(struct)
    # Two sentences carry citations; the middle one has none.
    assert len(claims) == 2
    first = claims[0]
    assert "Transformers improve" in first.claim_sentence
    assert first.ref_keys == ["12"]
    second = claims[1]
    assert second.ref_keys == ["3", "4"]


def test_extract_author_year_and_numeric_range():
    body = (
        "Prior work established this effect (Smith et al., 2021). "
        "Replications confirmed it [5-7]."
    )
    struct = PaperStructure(body=body)
    claims = ca.extract_claim_citations(struct)
    assert claims[0].ref_keys == ["Smith et al., 2021"]
    assert claims[1].ref_keys == ["5", "6", "7"]


def test_extract_author_year_lowercase_prefix_surnames():
    body = (
        "This was first shown by (van der Berg et al., 2021). "
        "It was later refined (de Bruijn and Smith, 2018)."
    )
    struct = PaperStructure(body=body)
    claims = ca.extract_claim_citations(struct)
    assert claims[0].ref_keys == ["van der Berg et al., 2021"]
    assert claims[1].ref_keys == ["de Bruijn and Smith, 2018"]


def test_rank_claims_prioritizes_load_bearing():
    weak = ca.ClaimCitation("Related work also touches this area [1].", ["1"])
    strong = ca.ClaimCitation(
        "Our method significantly outperforms all baselines by 12% [2].", ["2"]
    )
    ranked = ca.rank_claims([weak, strong])
    assert ranked[0] is strong          # causal verb + number rank first
    assert ranked[1] is weak
    assert ranked[0].salience > ranked[1].salience


def test_rank_claims_is_stable_for_ties():
    a = ca.ClaimCitation("A plain mention [1].", ["1"])
    b = ca.ClaimCitation("Another plain mention [2].", ["2"])
    ranked = ca.rank_claims([a, b])
    assert ranked[0] is a and ranked[1] is b   # equal salience keeps input order


def test_reconstruct_abstract_from_inverted_index():
    inv = {"The": [0], "cat": [1], "sat": [2]}
    assert ca.reconstruct_abstract(inv) == "The cat sat"
    assert ca.reconstruct_abstract(None) is None
    assert ca.reconstruct_abstract({}) is None


def test_resolve_ref_numeric_and_author_year():
    refs = [
        PaperReference(raw="[1] Smith J. 2021. Deep nets. doi:10.1/x", title="Deep nets",
                       doi="10.1/x", year="2021", authors="Smith J."),
        PaperReference(raw="[2] Jones A. 2019. Shallow nets.", title="Shallow nets",
                       year="2019", authors="Jones A."),
    ]
    # Numeric key indexes 1-based into the reference list.
    assert ca._resolve_ref("2", refs) is refs[1]
    # Author-year key matches on surname + year in the raw text.
    assert ca._resolve_ref("Smith, 2021", refs) is refs[0]
    # Unknown key -> None.
    assert ca._resolve_ref("Nobody, 1900", refs) is None


def test_resolve_ref_lowercase_prefix_surname():
    refs = [
        PaperReference(raw="[1] van der Berg M. 2021. Graph nets.", title="Graph nets",
                       year="2021", authors="van der Berg M."),
    ]
    # The captured surname ("Berg") + year must resolve past the particles.
    assert ca._resolve_ref("van der Berg et al., 2021", refs) is refs[0]
