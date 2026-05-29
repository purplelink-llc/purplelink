import pytest

from latextools import core


def test_validate_doc2md_rejects_empty():
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("a.pdf", 0)


def test_validate_doc2md_rejects_oversize():
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("a.pdf", core.MAX_DOC2MD_UPLOAD_BYTES + 1)


def test_validate_doc2md_rejects_bad_extension():
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("a.zip", 1000)
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("a.mp3", 1000)


def test_validate_doc2md_rejects_path_chars():
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("../a.pdf", 1000)


def test_validate_doc2md_accepts_allowed():
    for name in ("a.pdf", "a.docx", "a.pptx", "a.xlsx",
                 "a.html", "a.htm", "a.csv", "a.epub", "A.PDF"):
        core.validate_doc2md_upload(name, 1000)  # must not raise


def test_signature_pdf():
    assert core.doc2md_signature_ok("a.pdf", b"%PDF-1.7\n...")
    assert not core.doc2md_signature_ok("a.pdf", b"NOTPDF")


def test_signature_zip_office():
    assert core.doc2md_signature_ok("a.docx", b"PK\x03\x04rest")
    assert core.doc2md_signature_ok("a.epub", b"PK\x03\x04rest")
    assert not core.doc2md_signature_ok("a.xlsx", b"notazip")


def test_signature_text_passes():
    assert core.doc2md_signature_ok("a.csv", b"col1,col2\n1,2\n")
    assert core.doc2md_signature_ok("a.html", b"<html></html>")


import importlib.util

markitdown_installed = pytest.mark.skipif(
    importlib.util.find_spec("markitdown") is None,
    reason="markitdown not installed (run inside the Modal image)",
)


@markitdown_installed
def test_convert_csv_to_markdown(tmp_path):
    from latextools import doc2md
    p = tmp_path / "t.csv"
    p.write_text("name,score\nAda,99\n", encoding="utf-8")
    md = doc2md.convert_to_markdown(str(p))
    assert "Ada" in md
    assert "score" in md


@markitdown_installed
def test_convert_html_to_markdown(tmp_path):
    from latextools import doc2md
    p = tmp_path / "t.html"
    p.write_text("<h1>Title</h1><p>Body text here.</p>", encoding="utf-8")
    md = doc2md.convert_to_markdown(str(p))
    assert "Title" in md
    assert "Body text here." in md
