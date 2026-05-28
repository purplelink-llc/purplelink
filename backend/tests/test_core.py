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


def test_latexdiff_command_has_safe_defaults():
    cmd = core.build_latexdiff_command("old.tex", "new.tex")
    assert cmd[0] == "latexdiff"
    assert "--type=UNDERLINE" in cmd
    # tabular treated as opaque to avoid "Missing \\cr" table corruption
    assert any("PICTUREENV" in a and "tabular" in a for a in cmd)
    assert cmd[-2:] == ["old.tex", "new.tex"]


def test_inject_diff_legend_after_maketitle():
    src = r"\begin{document}" "\n" r"\maketitle" "\n" r"Body" "\n" r"\end{document}"
    out = core.inject_diff_legend(src)
    assert r"\maketitle" in out
    assert "How to read this revision diff" in out
    assert out.index("How to read") > out.index(r"\maketitle")


def test_inject_diff_legend_noop_without_maketitle():
    src = r"\begin{document}" "\n" r"Body" "\n" r"\end{document}"
    assert core.inject_diff_legend(src) == src


def test_rate_limit_key_is_stable_and_hashed():
    k1 = core.rate_limit_key("203.0.113.7", day="2026-05-28")
    k2 = core.rate_limit_key("203.0.113.7", day="2026-05-28")
    assert k1 == k2
    assert "203.0.113.7" not in k1  # raw IP never stored
    assert k1.startswith("rl:2026-05-28:")
    k_other = core.rate_limit_key("10.0.0.1", day="2026-05-28")
    assert k_other != k1  # different IP must produce a different key


def test_rate_limit_key_buckets_are_independent():
    base = core.rate_limit_key("203.0.113.7", day="2026-05-28")
    compile_k = core.rate_limit_key("203.0.113.7", day="2026-05-28", bucket="compile")
    render_k = core.rate_limit_key("203.0.113.7", day="2026-05-28", bucket="render-equation")
    assert compile_k != render_k  # each endpoint family gets its own quota
    assert compile_k != base      # bucketed key differs from the no-bucket key
    assert compile_k.startswith("rl:compile:2026-05-28:")
    assert "203.0.113.7" not in compile_k  # raw IP still never stored


def test_client_ip_prefers_rightmost_public_address():
    # Attacker prepends a fake public IP; trusted ingress appends the real one.
    xff = "1.1.1.1, 8.8.8.8"
    assert core.client_ip_from_forwarded(xff, peer="9.9.9.9") == "8.8.8.8"


def test_client_ip_skips_private_and_reserved_hops():
    xff = "8.8.8.8, 10.0.0.1, 192.168.1.1"
    assert core.client_ip_from_forwarded(xff, peer=None) == "8.8.8.8"


def test_client_ip_ignores_malformed_entries():
    xff = "not-an-ip, 8.8.8.8"
    assert core.client_ip_from_forwarded(xff, peer=None) == "8.8.8.8"


def test_client_ip_falls_back_to_peer_when_no_public_forwarded():
    assert core.client_ip_from_forwarded("10.0.0.1, 192.168.0.5", peer="8.8.8.8") == "8.8.8.8"


def test_client_ip_falls_back_to_peer_string_when_nothing_public():
    # No public address anywhere: still return a stable, non-empty key source.
    assert core.client_ip_from_forwarded("", peer="10.0.0.1") == "10.0.0.1"
    assert core.client_ip_from_forwarded("", peer=None) == "0.0.0.0"


def test_validate_upload_rejects_backslash_and_nullbyte():
    with pytest.raises(core.ValidationError, match="invalid filename"):
        core.validate_upload("..\\evil.tex", 10)
    with pytest.raises(core.ValidationError, match="invalid filename"):
        core.validate_upload("evil\x00.tex", 10)


# ---------------------------------------------------------------------------
# ZIP upload validation
# ---------------------------------------------------------------------------

def test_validate_zip_upload_accepts_zip():
    core.validate_zip_upload("project.zip", 1024)  # should not raise


def test_validate_zip_upload_rejects_wrong_extension():
    with pytest.raises(core.ValidationError, match="must be a .zip"):
        core.validate_zip_upload("project.tex", 1024)


def test_validate_zip_upload_rejects_too_large():
    with pytest.raises(core.ValidationError, match="too large"):
        core.validate_zip_upload("project.zip", core.MAX_ZIP_UPLOAD_BYTES + 1)


def test_validate_zip_upload_rejects_empty():
    with pytest.raises(core.ValidationError, match="empty"):
        core.validate_zip_upload("project.zip", 0)


def test_validate_zip_upload_rejects_path_traversal_name():
    with pytest.raises(core.ValidationError, match="invalid filename"):
        core.validate_zip_upload("../../evil.zip", 10)


# ---------------------------------------------------------------------------
# ZIP extraction helpers
# ---------------------------------------------------------------------------

import io
import zipfile
from pathlib import Path


def _make_zip(files: dict) -> bytes:
    """Build an in-memory ZIP from {member_name: bytes_content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_extract_project_zip_basic(tmp_path):
    z = _make_zip({"main.tex": b"\\documentclass{article}", "fig/f.png": b"\x89PNG"})
    core.extract_project_zip(z, tmp_path)
    assert (tmp_path / "main.tex").read_bytes() == b"\\documentclass{article}"
    assert (tmp_path / "fig" / "f.png").read_bytes() == b"\x89PNG"


def test_extract_project_zip_requires_main_tex(tmp_path):
    z = _make_zip({"other.tex": b"hello"})
    with pytest.raises(core.ValidationError, match="main.tex"):
        core.extract_project_zip(z, tmp_path)


def test_extract_project_zip_rejects_path_traversal(tmp_path):
    z = _make_zip({"../evil.tex": b"bad"})
    with pytest.raises(core.ValidationError, match="path traversal|escapes workdir"):
        core.extract_project_zip(z, tmp_path)


def test_extract_project_zip_rejects_bad_extension(tmp_path):
    z = _make_zip({"main.tex": b"ok", "script.sh": b"rm -rf /"})
    with pytest.raises(core.ValidationError, match="unsupported file type"):
        core.extract_project_zip(z, tmp_path)


def test_extract_project_zip_rejects_too_many_files(tmp_path):
    files = {"main.tex": b"ok"}
    for i in range(core.MAX_ZIP_FILES):
        files[f"fig/f{i}.png"] = b"\x89PNG"
    z = _make_zip(files)
    with pytest.raises(core.ValidationError, match="too many files"):
        core.extract_project_zip(z, tmp_path)


def test_extract_project_zip_rejects_zip_bomb(tmp_path, monkeypatch):
    # Lower the limit so a small real file triggers the guard.
    monkeypatch.setattr(core, "MAX_UNCOMPRESSED_BYTES", 5)
    z = _make_zip({"main.tex": b"x" * 10})
    with pytest.raises(core.ValidationError, match="uncompressed"):
        core.extract_project_zip(z, tmp_path)


def test_extract_project_zip_rejects_bad_zip(tmp_path):
    with pytest.raises(core.ValidationError, match="valid ZIP"):
        core.extract_project_zip(b"not a zip at all", tmp_path)


def test_rate_limit_check_allows_under_limit():
    store = {}
    for i in range(core.DAILY_LIMIT):
        allowed, remaining = core.check_and_increment(store, "k")
        assert allowed is True
    assert remaining == 0


def test_rate_limit_check_blocks_over_limit():
    store = {}
    for _ in range(core.DAILY_LIMIT):
        core.check_and_increment(store, "k")
    allowed, remaining = core.check_and_increment(store, "k")
    assert allowed is False
    assert remaining == 0
