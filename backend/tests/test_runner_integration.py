import shutil
from pathlib import Path

import pytest

from latextools import runner

FIXTURES = Path(__file__).parent / "fixtures"
has_latexmk = pytest.mark.skipif(
    shutil.which("latexmk") is None,
    reason="latexmk not installed (run inside the Modal image)",
)


@has_latexmk
def test_compile_clean_doc_returns_pdf(tmp_path):
    tex = (FIXTURES / "clean.tex").read_text()
    result = runner.run_compile(tmp_path, tex, engine="pdflatex", timeout=60)
    assert result.ok is True
    assert result.pdf_bytes[:4] == b"%PDF"
    assert result.errors == []


@has_latexmk
def test_compile_error_doc_reports_errors(tmp_path):
    tex = (FIXTURES / "error.tex").read_text()
    result = runner.run_compile(tmp_path, tex, engine="pdflatex", timeout=60)
    assert result.ok is False
    assert result.pdf_bytes is None
    assert any("Undefined control sequence" in e["message"] for e in result.errors)


@has_latexmk
def test_shell_escape_is_blocked(tmp_path):
    tex = (FIXTURES / "shell_escape.tex").read_text()
    runner.run_compile(tmp_path, tex, engine="pdflatex", timeout=60)
    assert not Path("/tmp/pwned_by_latex").exists()


@has_latexmk
def test_infinite_loop_times_out(tmp_path):
    tex = (FIXTURES / "infinite_loop.tex").read_text()
    result = runner.run_compile(tmp_path, tex, engine="pdflatex", timeout=5)
    assert result.ok is False
    assert result.timed_out is True
