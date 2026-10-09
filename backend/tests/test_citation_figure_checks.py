"""In-text citation matching and figure/table numbering over PDF-extracted text.

The weight of these tests is on silence: every guard exists because a lossy
extraction (merged references, appendix after the bibliography, truncated
body) would otherwise produce a confident, wrong finding.
"""
from latextools import manuscript_checks as mc
from latextools.papercheck import PaperReference


def refs(n, style="numeric"):
    if style == "numeric":
        return [PaperReference(raw=f"Author{i}, A. Title of paper number {i}. Journal, 20{10 + i % 10}.", year=f"20{10 + i % 10}") for i in range(1, n + 1)]
    return None


def summaries(findings):
    return [f.summary for f in findings]


# ---- numeric citations ------------------------------------------------------------------

NUMERIC_BODY = (
    "Prior work [1] showed this. Later studies [2, 3] and [4-6] extended it, as in [7]. "
    "We build on [1], [5] and [8]. The result in [2] holds for [9, 10]. Finally [3] and [6]."
)


def test_numeric_style_with_everything_cited_is_silent():
    assert mc.citation_matching_checks(NUMERIC_BODY, refs(10), 10) == []


def test_ranges_and_lists_are_expanded():
    cited, n = mc._numeric_citations("See [1], [2, 3] and [4-6]; also [8–10].")
    assert cited == {1, 2, 3, 4, 5, 6, 8, 9, 10} and n == 4


def test_a_citation_beyond_the_list_is_a_warning():
    body = NUMERIC_BODY + " Also [14] and [15]."
    f = mc.citation_matching_checks(body, refs(10), 10)
    assert len(f) == 1 and f[0].severity == "warning"
    assert "[15]" in f[0].summary and "10 entries" in f[0].summary
    assert "[14], [15]" in f[0].detail
    assert "extracted from the PDF" in f[0].detail


def test_uncited_references_are_listed_with_a_hedge():
    body = "Work [1] and [2, 3] and [4-6] and [7] and [9] and [10]. Again [1] [2] [3] [4]."
    f = mc.citation_matching_checks(body, refs(10), 10)
    assert len(f) == 1 and f[0].severity == "info"
    assert "[8]" in f[0].summary and "appendix" in f[0].detail


def test_brackets_glued_to_words_are_not_citations():
    body = "Set x[1] = 3 and arr[2] = 4, then a[5] and b[6]. " + "See [1] [2] [3] [4] [5]."
    cited, n = mc._numeric_citations(body)
    assert cited == {1, 2, 3, 4, 5} and n == 5


def test_too_few_markers_means_no_style_and_no_findings():
    assert mc.citation_matching_checks("Only [1] and [2].", refs(10), 10) == []


def test_uncited_check_is_skipped_for_a_truncated_body():
    body = NUMERIC_BODY.replace("[8]", "[1]").replace("[9, 10]", "[2]") + "\n[... section omitted to keep within model context ...]\n"
    f = mc.citation_matching_checks(body, refs(10), 10)
    assert not any("not cited" in s for s in summaries(f))


def test_uncited_check_is_skipped_when_more_references_exist_than_were_parsed():
    body = "Work [1] and [2, 3] and [4-6] and [7] again [1] [2] [3] [4] [5] [6]."
    f = mc.citation_matching_checks(body, refs(10), 85)
    assert not any("not cited" in s for s in summaries(f))


def test_uncited_check_is_skipped_when_coverage_looks_wrong():
    # Only 3 of 10 cited: the list or the markers were probably misread.
    body = "Work [1] [2] [3] [1] [2] [3] [1] [2] [3]."
    assert mc.citation_matching_checks(body, refs(10), 10) == []


def test_too_short_a_list_is_ignored():
    assert mc.citation_matching_checks(NUMERIC_BODY + " [14]", refs(2), 2) == []
    assert mc.citation_matching_checks("", refs(10), 10) == []
    assert mc.citation_matching_checks(NUMERIC_BODY, None, None) == []


# ---- author-year citations ----------------------------------------------------------------

AY_REFS = [
    PaperReference(raw="Smith, J., & Lee, K. (2020). Learning to cite. Journal of Things, 4, 1-10."),
    PaperReference(raw="Garcia, M. (2019). Careful counting. Annals of Counting, 2, 11-20."),
    PaperReference(raw="Nguyen, T., Patel, R., & Brown, L. (2018). Panels and priors. Econometrica, 9, 21-30."),
    PaperReference(raw="Okafor, C. (2021). Tables and trust. Review of Tables, 3, 31-40."),
    PaperReference(raw="van der Berg, H. (2017). Sampling schemes. Statistics Today, 5, 41-50."),
]
AY_BODY = (
    "Earlier work (Smith & Lee, 2020) and Garcia (2019) differ from Nguyen et al. (2018). "
    "Others agree (Okafor, 2021; van der Berg, 2017), see also (Smith and Lee, 2020)."
)


def test_author_year_with_everything_matched_is_silent():
    assert mc.citation_matching_checks(AY_BODY, AY_REFS, 5) == []


def test_an_unmatched_author_year_citation_is_reported_gently():
    body = AY_BODY + " This contradicts Fischer (2016) as well as (Smith & Lee, 2020)."
    f = mc.citation_matching_checks(body, AY_REFS, 5)
    assert len(f) == 1 and f[0].severity == "info"
    assert "Fischer (2016)" in f[0].summary and "could not be matched" in f[0].summary


def test_a_listed_reference_the_text_never_cites_is_reported():
    body = AY_BODY.replace("Garcia (2019)", "prior work")
    f = mc.citation_matching_checks(body, AY_REFS, 5)
    assert len(f) == 1 and "Garcia (2019)" in f[0].summary


def test_a_year_suffix_and_multiple_years_match():
    refs_ = AY_REFS[:1] + [PaperReference(raw="Garcia, M. (2019a). One. J. Garcia, M. (2019b). Two.")] + AY_REFS[2:]
    body = AY_BODY.replace("Garcia (2019)", "Garcia (2019a, 2019b)")
    assert mc.citation_matching_checks(body, refs_, 5) == []


def test_a_high_miss_rate_means_the_list_was_misread_so_say_nothing():
    body = "Per (Alpha, 2001) (Beta, 2002) (Gamma, 2003) (Delta, 2004) (Smith & Lee, 2020) (Garcia, 2019)."
    assert mc.citation_matching_checks(body, AY_REFS, 5) == []


def test_author_year_checks_need_a_complete_list():
    body = AY_BODY + " Fischer (2016)."
    assert mc.citation_matching_checks(body, AY_REFS, 40) == []


def test_surnames_with_particles_parse():
    cites = mc._author_year_citations("Others agree (van der Berg, 2017; de la Cruz et al., 2015) and Van Dijk (2012).")
    assert ("van der Berg", "2017") in cites
    assert any(n.endswith("Dijk") and y == "2012" for n, y in cites)   # a capitalised particle still matches by surname
    assert any(n.endswith("Cruz") and y == "2015" for n, y in cites)


def test_possessives_are_stripped_from_author_names():
    cites = mc._author_year_citations("As Hardin\u2019s (1968) essay and Lee's (1995) paper argue, see Kim's (2001).")
    assert [n for n, _ in cites] == ["Hardin", "Lee", "Kim"]


def test_figure_and_section_words_are_not_authors():
    cites = mc._author_year_citations("As Table (2019) and Figure (2020) show, see Section (2018).")
    assert cites == []


# ---- figures and tables --------------------------------------------------------------------

FIG_BODY = """
We present the setup in Figure 1 and the data in Table 1. Results appear in Fig. 2 and Tables 2-3.
Figure 3 shows the ablation. See also Figure 2(b) and Table 1.

Figure 1: The experimental setup.
Figure 2. Main results across seeds.
Figure 3: Ablation of components.
Table 1: Dataset statistics.
Table 2. Main results.
Table 3: Ablation numbers.
"""


def test_a_consistent_document_is_silent():
    assert mc.figure_table_checks(FIG_BODY) == []


def test_a_cited_table_without_a_caption_is_reported():
    body = FIG_BODY + "\nWe also report Table 5 in the text.\n"
    f = mc.figure_table_checks(body)
    assert any("Tables cited in the text with no caption found: Table 5" in s for s in summaries(f))


def test_a_caption_the_text_never_cites_is_reported():
    body = FIG_BODY + "\nFigure 4: An orphan caption.\n"
    f = mc.figure_table_checks(body)
    assert any("Figure 4" in s and "never refers to" in s for s in summaries(f))


def test_skipped_numbers_are_reported_only_when_neither_captioned_nor_cited():
    body = FIG_BODY.replace("Figure 3: Ablation of components.\n", "").replace("Figure 3 shows the ablation. ", "") \
        + "\nFigure 4: Later.\nThe text uses Figure 4.\n"
    f = mc.figure_table_checks(body)
    assert any("Figure numbers skip: 3" in s for s in summaries(f))


def test_out_of_order_first_citation_is_reported():
    body = (
        "First Figure 2 then Figure 1 and Figure 3 appear.\nFigure 1: A.\nFigure 2: B.\nFigure 3: C.\n"
        "Also Table 1 and Table 2 and Table 3.\nTable 1: A.\nTable 2: B.\nTable 3: C.\n"
    )
    f = mc.figure_table_checks(body)
    assert any("out of numerical order" in s and "Figure 1 before Figure 2" in s for s in summaries(f))


def test_supplementary_labels_and_external_figures_are_ignored():
    body = FIG_BODY + "\nSee Figure S1 and Table A2. Figure 9 in [12] and Table 4 of Smith et al. differ.\n" \
        "Figure 7 from Lee (2019) is reproduced under permission.\n"
    assert mc.figure_table_checks(body) == []


def test_a_sentence_starting_with_table_n_is_not_a_caption():
    body = FIG_BODY + "\nTable 4 shows that the effect is robust.\nTable 4 also lists sizes.\n"
    f = mc.figure_table_checks(body)
    # Table 4 is cited twice, never captioned: reported as uncaptioned, not as a skipped number.
    assert any("no caption found: Table 4" in s for s in summaries(f))


def test_a_truncated_body_or_too_few_mentions_stay_silent():
    assert mc.figure_table_checks(FIG_BODY + "\n[... section omitted to keep within model context ...]\n") == []
    assert mc.figure_table_checks("Figure 1: A.\nFigure 2: B.\nSee Figure 1.") == []
    assert mc.figure_table_checks("") == []


def test_lists_and_ranges_in_mentions_are_expanded():
    f = mc.figure_table_checks(
        "Figures 1 and 2, then Figures 3-4 and Table 1.\nFigure 1: A.\nFigure 2: B.\nFigure 3: C.\nTable 1: T.\n"
    )
    assert any("Figure 4" in s and "no caption" in s for s in summaries(f))


def test_long_lists_are_capped():
    body = "Mentions: " + ", ".join(f"Table {n}" for n in range(1, 21)) + ".\nTable 1: a.\nTable 2: b.\n"
    f = mc.figure_table_checks(body)
    big = [x for x in f if "no caption found" in x.summary][0]
    assert "(and " in big.summary and "more)" in big.summary


# ---- wiring ---------------------------------------------------------------------------------

def test_all_findings_runs_both_for_pdf_text_but_not_for_latex_source():
    body = NUMERIC_BODY + " Also [14]. " + FIG_BODY + " We cite Table 5."
    pdf = mc.all_findings(body, refs(10), n_references_total=10)
    kinds = {f.kind for f in pdf}
    assert "citation" in kinds and "structure" in kinds
    assert any("reach [14]" in f.summary for f in pdf)
    tex = mc.all_findings(body, refs(10), latex_source=True, n_references_total=10)
    assert not any("reach [14]" in f.summary for f in tex)


def test_findings_serialise_for_the_report():
    f = mc.citation_matching_checks(NUMERIC_BODY + " Also [15].", refs(10), 10)[0].to_dict()
    assert set(f) == {"kind", "severity", "summary", "detail"}
