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
