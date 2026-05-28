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
