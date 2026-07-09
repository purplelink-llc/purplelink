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
