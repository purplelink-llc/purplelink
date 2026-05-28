import pytest
from latextools import core


def test_validate_upload_accepts_tex():
    core.validate_upload("paper.tex", 1024)  # should not raise


def test_validate_upload_rejects_wrong_extension():
    with pytest.raises(core.ValidationError, match="must be a .tex file"):
        core.validate_upload("paper.pdf", 1024)


def test_validate_upload_rejects_too_large():
    with pytest.raises(core.ValidationError, match="too large"):
        core.validate_upload("paper.tex", core.MAX_UPLOAD_BYTES + 1)


def test_validate_upload_rejects_empty():
    with pytest.raises(core.ValidationError, match="empty"):
        core.validate_upload("paper.tex", 0)


def test_validate_upload_rejects_path_traversal_name():
    with pytest.raises(core.ValidationError, match="invalid filename"):
        core.validate_upload("../../etc/passwd.tex", 10)


def test_latexmk_command_pdflatex_default():
    cmd = core.build_latexmk_command("pdflatex", "main")
    assert cmd[0] == "latexmk"
    assert "-pdf" in cmd
    assert "-interaction=nonstopmode" in cmd
    assert "-no-shell-escape" in cmd
    assert cmd[-1] == "main.tex"


def test_latexmk_command_xelatex():
    cmd = core.build_latexmk_command("xelatex", "main")
    assert "-xelatex" in cmd
    assert "-pdf" not in cmd
    assert "-no-shell-escape" in cmd


def test_latexmk_command_rejects_unknown_engine():
    with pytest.raises(core.ValidationError, match="unsupported engine"):
        core.build_latexmk_command("lualatex", "main")


SAMPLE_LOG = r"""
This is pdfTeX, Version 3.141592653
(./main.tex
LaTeX Font Info: ...
main.tex:12: Undefined control sequence.
l.12 \badcommand
                 here
main.tex:40: Missing $ inserted.
Output written on main.pdf (2 pages).
"""


def test_parse_latex_log_extracts_errors():
    errors = core.parse_latex_log(SAMPLE_LOG)
    assert len(errors) == 2
    assert errors[0]["line"] == 12
    assert "Undefined control sequence" in errors[0]["message"]
    assert errors[1]["line"] == 40


def test_parse_latex_log_no_errors_returns_empty():
    assert core.parse_latex_log("Output written on main.pdf (1 page).") == []


def test_parse_latex_log_truncates_to_cap():
    big = "\n".join(f"main.tex:{i}: Error number {i}." for i in range(1, 50))
    errors = core.parse_latex_log(big)
    assert len(errors) == core.MAX_REPORTED_ERRORS
