"""Subprocess execution of latexmk / latexdiff in a working directory.

This is the only module that requires the TeX toolchain, so it is covered
by integration tests that skip when latexmk is unavailable.
"""
from __future__ import annotations

import os
import signal
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
    cmd = core.build_latexmk_command(engine, "main")  # validates engine; raises on bad
    tex_path = Path(workdir) / "main.tex"
    tex_path.write_text(tex_source, encoding="utf-8")

    proc = subprocess.Popen(
        cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()
        return CompileResult(False, None, [], "", timed_out=True)

    log_path = Path(workdir) / "main.log"
    log = log_path.read_text(errors="replace") if log_path.exists() else stdout
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
    """Run latexdiff(old,new) -> main.tex, then compile it.

    The *timeout* budget is split: latexdiff (a fast Perl pass) gets a small
    slice, the compile gets the remainder, so the total stays within one
    *timeout* window (avoids exceeding the Modal wall-clock limit).
    """
    (Path(workdir) / "old.tex").write_text(old_source, encoding="utf-8")
    (Path(workdir) / "new.tex").write_text(new_source, encoding="utf-8")
    diff_cmd = core.build_latexdiff_command("old.tex", "new.tex")
    diff_timeout = max(10, timeout // 4)

    proc = subprocess.Popen(
        diff_cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        diff_out, diff_err = proc.communicate(timeout=diff_timeout)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()
        return CompileResult(False, None, [], "", timed_out=True)

    if proc.returncode != 0:
        return CompileResult(
            False, None,
            [{"file": "latexdiff", "line": 0, "message": diff_err.strip()[:500]}],
            diff_err,
        )

    diff_tex = diff_out
    if add_legend:
        diff_tex = core.inject_diff_legend(diff_tex)
    return run_compile(workdir, diff_tex, engine, timeout - diff_timeout)


@dataclass
class ConvertResult:
    ok: bool
    docx_bytes: bytes | None
    error: str = ""


def convert_to_manuscript(
    workdir: Path, tex_source: str, anonymize: bool
) -> ConvertResult:
    """pandoc(.tex) -> base.docx, then apply the manuscript post-processor.

    Single-file MVP: no .bib, so native Word citations are skipped (the
    post-processor guards that internally). tex_path is passed so keyword
    injection and cross-references work.
    """
    from latextools import docx_format

    work = Path(workdir)
    tex_path = work / "main.tex"
    base_docx = work / "base.docx"
    out_docx = work / "manuscript.docx"
    tex_path.write_text(tex_source, encoding="utf-8")

    try:
        proc = subprocess.run(
            ["pandoc", str(tex_path), "-o", str(base_docx)],
            cwd=workdir, capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return ConvertResult(False, None, "Conversion timed out.")
    if proc.returncode != 0 or not base_docx.exists():
        return ConvertResult(False, None, proc.stderr.strip()[:500] or "pandoc failed")

    docx_format.format_docx(
        str(base_docx), str(out_docx), tex_path=str(tex_path), anonymize=anonymize
    )
    return ConvertResult(True, out_docx.read_bytes())
