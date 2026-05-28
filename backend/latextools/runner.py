"""Subprocess execution of latexmk / latexdiff in a working directory.

This is the only module that requires the TeX toolchain, so it is covered
by integration tests that skip when latexmk is unavailable.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from latextools import core


@dataclass
class CompileResult:
    ok: bool
    pdf_bytes: bytes | None
    errors: list[dict]
    log: str
    timed_out: bool = False


def run_compile(
    workdir: Path, tex_source: str, engine: str, timeout: int
) -> CompileResult:
    """Write *tex_source* to workdir/main.tex and compile it with latexmk."""
    core.build_latexmk_command(engine, "main")  # validates engine early
    tex_path = Path(workdir) / "main.tex"
    tex_path.write_text(tex_source, encoding="utf-8")
    cmd = core.build_latexmk_command(engine, "main")

    try:
        proc = subprocess.run(
            cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, [], "", timed_out=True)

    log_path = Path(workdir) / "main.log"
    log = log_path.read_text(errors="replace") if log_path.exists() else proc.stdout
    pdf_path = Path(workdir) / "main.pdf"

    if proc.returncode == 0 and pdf_path.exists():
        return CompileResult(True, pdf_path.read_bytes(), [], log)
    return CompileResult(False, None, core.parse_latex_log(log), log)


def run_diff(
    workdir: Path,
    old_source: str,
    new_source: str,
    engine: str,
    timeout: int,
    add_legend: bool,
) -> CompileResult:
    """Run latexdiff(old,new) -> main.tex, then compile it."""
    (Path(workdir) / "old.tex").write_text(old_source, encoding="utf-8")
    (Path(workdir) / "new.tex").write_text(new_source, encoding="utf-8")
    diff_cmd = core.build_latexdiff_command("old.tex", "new.tex")
    try:
        diff_proc = subprocess.run(
            diff_cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, [], "", timed_out=True)
    if diff_proc.returncode != 0:
        return CompileResult(
            False, None, [{"file": "latexdiff", "line": 0, "message": diff_proc.stderr.strip()[:500]}], diff_proc.stderr
        )

    diff_tex = diff_proc.stdout
    if add_legend:
        diff_tex = core.inject_diff_legend(diff_tex)
    return run_compile(workdir, diff_tex, engine, timeout)
