from latextools import docx_format as f


def test_latex_to_unicode_umlaut_and_quotes():
    assert f._latex_to_unicode(r'Sch\"on') == "Schön"
    assert f._latex_to_unicode("``hi''") == "“hi”"


def test_parse_authors_lastfirst_and_and():
    authors = f._parse_authors("Smith, John and Doe, Jane")
    assert authors == [("Smith", "John"), ("Doe", "Jane")]


def test_parse_authors_corporate_braced():
    assert f._parse_authors("{World Health Organization}") == [
        ("World Health Organization", "")
    ]


def test_cite_surname_strips_particle():
    assert f._cite_surname("vom Brocke") == "Brocke"


def test_rendered_citation_two_authors():
    entry = {"author": "Smith, John and Doe, Jane", "year": "2020"}
    assert f._rendered_citation(entry) == "Smith and Doe 2020"


def test_rendered_citation_four_authors_uses_etal():
    entry = {"author": "A, X and B, Y and C, Z and D, W", "year": "2021"}
    assert f._rendered_citation(entry) == "A et al. 2021"
