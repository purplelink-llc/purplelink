"""Pure-logic tests for latextools.texflatten and latextools.safe_exec."""
import os
import subprocess

import pytest

from latextools import core, texflatten
from latextools.safe_exec import minimal_env, run_pandoc_sandboxed


def _project(tmp_path, files):
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def _prep(tmp_path, main):
    return texflatten.prepare_for_pandoc(tmp_path, main, tmp_path / "main.tex")


def test_relative_input_is_inlined(tmp_path):
    _project(tmp_path, {"main.tex": "x", "sub.tex": "SUBFILE_MARKER_OK"})
    out = _prep(tmp_path, r"\begin{document}\input{sub}\end{document}")
    assert "SUBFILE_MARKER_OK" in out.tex
    assert r"\input" not in out.tex
    assert not out.needs_fs


def test_input_with_extension_and_nested_dir_and_bare_form(tmp_path):
    _project(tmp_path, {"sections/a.tex": r"A \input{sections/b}", "sections/b.tex": "BEE"})
    out = _prep(tmp_path, r"\input{sections/a.tex} and \input sections/b.tex")
    assert out.tex.count("BEE") == 2 and "A " in out.tex


def test_absolute_and_traversal_paths_are_removed(tmp_path):
    out = _prep(tmp_path, "\\input{/etc/os-release}\n\\include{../secret}\n\\input{a/../../x}\nEND")
    assert "os-release" not in out.tex and "secret" not in out.tex and "../" not in out.tex
    assert "END" in out.tex


def test_url_and_macro_paths_are_removed(tmp_path):
    out = _prep(tmp_path, r"\includegraphics{http://169.254.169.254/x.png} \includegraphics{\figdir/a.png}")
    assert "169.254" not in out.tex and "figdir" not in out.tex


def test_symlink_is_not_followed(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "_outside.tex")
    outside.write_text("LEAKED", encoding="utf-8")
    link = tmp_path / "evil.tex"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symlinks unavailable")
    out = _prep(tmp_path, r"\input{evil}")
    assert "LEAKED" not in out.tex


def test_symlinked_directory_is_not_followed(tmp_path):
    other = tmp_path.parent / (tmp_path.name + "_dir")
    other.mkdir()
    (other / "x.tex").write_text("LEAKED", encoding="utf-8")
    try:
        os.symlink(other, tmp_path / "d")
    except OSError:
        pytest.skip("symlinks unavailable")
    assert "LEAKED" not in _prep(tmp_path, r"\input{d/x}").tex


def test_commented_include_is_left_alone(tmp_path):
    _project(tmp_path, {"sub.tex": "SUB"})
    out = _prep(tmp_path, "% \\input{sub}\nline \\% \\input{sub}\n")
    assert out.tex.count("SUB") == 1  # only the one after the escaped percent


def test_escaped_backslash_before_name_is_not_a_command(tmp_path):
    _project(tmp_path, {"sub.tex": "SUB"})
    out = _prep(tmp_path, "a\\\\input{sub}")
    assert "SUB" not in out.tex


def test_cycle_and_depth_are_cut(tmp_path):
    _project(tmp_path, {"a.tex": r"A\input{b}", "b.tex": r"B\input{a}"})
    out = _prep(tmp_path, r"\input{a}")
    assert out.tex.count("A") == 1 and out.tex.count("B") == 1


def test_total_size_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(texflatten, "MAX_TOTAL_BYTES", 100)
    _project(tmp_path, {"big.tex": "x" * 500})
    with pytest.raises(core.ValidationError):
        _prep(tmp_path, r"\input{big}")


def test_subfile_body_only(tmp_path):
    _project(tmp_path, {"s.tex": "\\documentclass[main]{subfiles}\n\\begin{document}BODY\\end{document}"})
    out = _prep(tmp_path, r"\subfile{s}")
    assert "BODY" in out.tex and "documentclass" not in out.tex


def test_import_two_arguments(tmp_path):
    _project(tmp_path, {"chap/one.tex": "ONE"})
    assert "ONE" in _prep(tmp_path, r"\import{chap/}{one}").tex


def test_safe_figure_kept_and_needs_fs(tmp_path):
    _project(tmp_path, {"fig/a.png": "png"})
    out = _prep(tmp_path, r"\includegraphics[width=3cm]{fig/a.png}")
    assert r"\includegraphics[width=3cm]{fig/a.png}" in out.tex
    assert out.needs_fs


def test_figure_reference_without_files_does_not_need_fs(tmp_path):
    out = _prep(tmp_path, r"\includegraphics{fig/a.png}")
    assert not out.needs_fs


def test_unsafe_listing_and_bib_and_graphicspath_removed(tmp_path):
    out = _prep(
        tmp_path,
        "\\lstinputlisting{/etc/passwd}\\verbatiminput{../x}\\bibliography{/etc/x}\n"
        "\\graphicspath{{/etc/}}\\InputIfFileExists{/etc/x}{a}{b}\\inputminted{c}{/etc/x}",
    )
    assert "/etc" not in out.tex and "../x" not in out.tex


def test_safe_bibliography_kept(tmp_path):
    out = _prep(tmp_path, r"\bibliography{refs,more}")
    assert r"\bibliography{refs,more}" in out.tex


def test_risky_macros_are_flagged(tmp_path):
    assert _prep(tmp_path, r"\csname input\endcsname{/etc/passwd}").risky
    assert _prep(tmp_path, r"\catcode`\#=12").risky
    assert not _prep(tmp_path, "plain text").risky


def test_macro_definition_containing_input_is_cleaned(tmp_path):
    out = _prep(tmp_path, r"\newcommand{\x}{\input{/etc/passwd}}\x")
    assert "passwd" not in out.tex


def test_resolve_inside_rejections(tmp_path):
    for bad in ["/etc/passwd", "../a", "a/../../b", "http://x/y", "a|b", "~/x", "", "C:/x", "a\\b"]:
        assert texflatten.resolve_inside(tmp_path, bad) is None, bad
    assert texflatten.resolve_inside(tmp_path, "sub/ok.tex") == (tmp_path.resolve() / "sub" / "ok.tex")


# ---- safe_exec -----------------------------------------------------------

def test_minimal_env_has_only_needed_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    env = minimal_env(tmp_path)
    assert set(env) == {"PATH", "HOME", "LANG"}
    assert env["HOME"] == str(tmp_path) and env["PATH"] == "/usr/bin:/bin"


def test_pandoc_sandbox_flag_and_fallback(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw))
        return subprocess.CompletedProcess(cmd, 1 if "--sandbox" in cmd else 0, "", "boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    p = run_pandoc_sandboxed(["pandoc", "in.md", "-o", "out.docx"], cwd=tmp_path, timeout=60, fallback=True)
    assert p.returncode == 0 and len(calls) == 2
    assert "--sandbox" in calls[0][0] and "--sandbox" not in calls[1][0]
    assert all(set(kw["env"]) == {"PATH", "HOME", "LANG"} for _, kw in calls)
    calls.clear()
    p = run_pandoc_sandboxed(["pandoc", "in.md"], cwd=tmp_path, timeout=60)
    assert p.returncode == 1 and len(calls) == 1
