import shutil

import pytest

from muscleonglp import typeset

has_latexmk = pytest.mark.skipif(
    shutil.which("latexmk") is None,
    reason="latexmk not installed (run inside the Modal image)",
)


def test_escape_latex_handles_special_chars():
    assert typeset._escape_latex("100% & $5_guide") == r"100\% \& \$5\_guide"


def test_body_to_latex_converts_headings_and_preserves_body():
    text = "## Introduction\nSome text.\n\n## Protein Targets\nMore text."
    out = typeset._body_to_latex(text)
    assert r"\section*{Introduction}" in out
    assert r"\section*{Protein Targets}" in out
    assert "Some text." in out
    assert "More text." in out


@has_latexmk
def test_render_guide_pdf_produces_a_real_pdf(tmp_path):
    output_path = tmp_path / "guide.pdf"
    text = "## Introduction\nThis is a test guide with a 1.6 g/kg protein target."
    result = typeset.render_guide_pdf(text, output_path)
    assert result == output_path
    assert output_path.read_bytes()[:4] == b"%PDF"


@has_latexmk
def test_render_guide_pdf_raises_on_compile_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        typeset,
        "_TEX_TEMPLATE",
        "\\documentclass{article}\n\\begin{document}\n\\undefinedcommand\n%s\n\\end{document}\n",
    )
    output_path = tmp_path / "guide.pdf"
    with pytest.raises(RuntimeError):
        typeset.render_guide_pdf("## Intro\ntext", output_path)
