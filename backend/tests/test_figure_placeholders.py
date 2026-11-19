"""Single .tex uploads that use figures: the placeholder retry (2026-11-19)."""
from pathlib import Path

from latextools import core, runner
from latextools.runner import CompileResult

FIG_LOG = "./main.tex:6: LaTeX Error: File `figures/fig1' not found.\n"
PNG_LOG = "! Package pdftex.def Error: File `plot.png' not found: using draft setting.\n"
INPUT_LOG = "./main.tex:4: LaTeX Error: File `intro.tex' not found.\n"
STY_LOG = "! LaTeX Error: File `acmart.cls' not found.\n"
DOC = "\\documentclass{article}\n% \\begin{document} in a comment\n\\begin{document}\nHi\n\\end{document}\n"


def test_only_missing_images():
    assert core.only_missing_images(FIG_LOG)
    assert core.only_missing_images(PNG_LOG)
    assert core.only_missing_images(FIG_LOG + PNG_LOG)
    assert not core.only_missing_images(INPUT_LOG)
    assert not core.only_missing_images(STY_LOG)
    assert not core.only_missing_images(FIG_LOG + INPUT_LOG)
    assert not core.only_missing_images("! Undefined control sequence.\n")
    assert not core.only_missing_images("")


def test_inject_before_the_real_begin_document():
    out = core.inject_figure_placeholders(DOC)
    assert out is not None
    head, _, tail = out.partition("\\AtBeginDocument{\\DeclareDocumentCommand{\\includegraphics}")
    assert "% \\begin{document} in a comment" in head
    assert tail.split("\n", 1)[1].startswith("\\begin{document}")
    assert out.count("\\begin{document}") == 2  # the comment and the real one, nothing added


def test_inject_needs_begin_document():
    assert core.inject_figure_placeholders("% \\begin{document}\nno body") is None


def _fake(results, calls):
    def compile_once(workdir, tex, engine, timeout):
        calls.append((tex, timeout))
        return results.pop(0)
    return compile_once


def test_retry_returns_placeholder_pdf(tmp_path, monkeypatch):
    (tmp_path / "main.tex").write_text(DOC)
    (tmp_path / "main.pdf").write_bytes(b"stale")
    calls = []
    monkeypatch.setattr(runner, "_compile_once", _fake(
        [CompileResult(False, None, [{"message": "x"}], FIG_LOG), CompileResult(True, b"%PDF", [], "")], calls))
    res = runner.run_compile(tmp_path, None, "pdflatex", 60, figure_placeholders=True)
    assert res.ok and res.pdf_bytes == b"%PDF"
    assert len(calls) == 2 and "Figure not uploaded" in calls[1][0]
    assert 0 < calls[1][1] <= 60
    assert not (tmp_path / "main.pdf").exists()  # stale output removed before the second run


def test_failed_retry_keeps_first_errors(tmp_path, monkeypatch):
    (tmp_path / "main.tex").write_text(DOC)
    first = CompileResult(False, None, [{"message": "File not found: figures/fig1."}], FIG_LOG)
    calls = []
    monkeypatch.setattr(runner, "_compile_once", _fake(
        [first, CompileResult(False, None, [{"message": "other"}], INPUT_LOG)], calls))
    assert runner.run_compile(tmp_path, None, "pdflatex", 60, figure_placeholders=True) is first


def test_no_retry_without_flag_or_for_other_errors(tmp_path, monkeypatch):
    (tmp_path / "main.tex").write_text(DOC)
    for log, flag in ((FIG_LOG, False), (INPUT_LOG, True), (STY_LOG, True)):
        calls = []
        first = CompileResult(False, None, [], log)
        monkeypatch.setattr(runner, "_compile_once", _fake([first], calls))
        assert runner.run_compile(tmp_path, None, "pdflatex", 60, figure_placeholders=flag) is first
        assert len(calls) == 1


def test_no_retry_after_timeout(tmp_path, monkeypatch):
    (tmp_path / "main.tex").write_text(DOC)
    calls = []
    first = CompileResult(False, None, [], "", timed_out=True)
    monkeypatch.setattr(runner, "_compile_once", _fake([first], calls))
    assert runner.run_compile(tmp_path, None, "pdflatex", 60, figure_placeholders=True) is first
    assert len(calls) == 1
