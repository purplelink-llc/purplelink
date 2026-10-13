"""Subprocess execution of latexmk / latexdiff in a working directory.

This is the only module that requires the TeX toolchain, so it is covered
by integration tests that skip when latexmk is unavailable.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from latextools import core, texflatten
from latextools.safe_exec import minimal_env

logger = logging.getLogger(__name__)


@dataclass
class CompileResult:
    ok: bool
    pdf_bytes: bytes | None
    errors: list[dict]
    log: str
    timed_out: bool = False


def run_compile(
    workdir: Path, tex_source: str | None, engine: str, timeout: int
) -> CompileResult:
    """Compile workdir/main.tex with latexmk.

    If *tex_source* is given it is written to main.tex first; pass None when
    the file already exists in *workdir* (e.g. extracted from a project ZIP).
    """
    cmd = core.build_latexmk_command(engine, "main")  # validates engine; raises on bad
    if tex_source is not None:
        tex_path = Path(workdir) / "main.tex"
        tex_path.write_text(tex_source, encoding="utf-8")

    proc = subprocess.Popen(
        cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True, env=minimal_env(workdir),
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
    old_source: str | None,
    new_source: str | None,
    engine: str,
    timeout: int,
    add_legend: bool,
) -> CompileResult:
    """Run latexdiff(old,new) -> main.tex, then compile it.

    Pass None for *old_source* / *new_source* when the corresponding
    old.tex / new.tex already exist in *workdir* (e.g. extracted from project
    ZIPs by the caller).

    The *timeout* budget is split: latexdiff (a fast Perl pass) gets a small
    slice, the compile gets the remainder, so the total stays within one
    *timeout* window (avoids exceeding the Modal wall-clock limit).
    """
    if old_source is not None:
        (Path(workdir) / "old.tex").write_text(old_source, encoding="utf-8")
    if new_source is not None:
        (Path(workdir) / "new.tex").write_text(new_source, encoding="utf-8")
    diff_cmd = core.build_latexdiff_command("old.tex", "new.tex")
    diff_timeout = max(10, timeout // 4)

    proc = subprocess.Popen(
        diff_cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True, env=minimal_env(workdir),
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
    workdir: Path, tex_source: str | None, anonymize: bool,
    style: str = "manuscript",
) -> ConvertResult:
    """pandoc(.tex) -> base.docx, then apply the manuscript post-processor.

    If *tex_source* is given it is written to main.tex first; pass None when
    the file already exists in *workdir* (e.g. extracted from a project ZIP).
    When a .bib file is present in *workdir*, pandoc --bibliography --citeproc
    is used so citations become editable Word references.
    """
    from latextools import docx_format

    work = Path(workdir)
    tex_path = work / "main.tex"
    base_docx = work / "base.docx"
    out_docx = work / "manuscript.docx"

    if tex_source is not None:
        tex_path.write_text(tex_source, encoding="utf-8")

    # pandoc must not follow \\input, \\includegraphics and similar commands to
    # files outside the project. Flatten the safe relative includes ourselves
    # and drop every other file reference (see latextools.texflatten).
    prepared = texflatten.prepare_for_pandoc(
        work, tex_path.read_text(encoding="utf-8", errors="replace"), tex_path
    )
    flat_path = work / "flat.tex"
    flat_path.write_text(prepared.tex, encoding="utf-8")

    bib_args: list[str] = []
    bib_files = sorted(work.glob("*.bib"))
    if bib_files:
        bib_args = ["--bibliography", str(bib_files[0]), "--citeproc"]

    # --sandbox limits pandoc to the files named on the command line. Figures
    # and listings are read from disk, so it can only be used when the project
    # has none; a document that builds command names at run time is always
    # sandboxed (its figures are not embedded).
    # If a sandboxed run fails for a reason that is only about the sandbox
    # (for example the bibliography), the flattened file is converted once more
    # without it; the file references were already checked above.
    if prepared.risky:
        attempts = [True]
    elif not prepared.needs_fs:
        attempts = [True, False]
    else:
        attempts = [False]
    proc = None
    for use_sandbox in attempts:
        base_docx.unlink(missing_ok=True)
        cmd = ["pandoc", str(flat_path), "-o", str(base_docx)]
        if use_sandbox:
            cmd.append("--sandbox")
        cmd += bib_args
        try:
            proc = subprocess.run(
                cmd,
                cwd=workdir, capture_output=True, text=True, timeout=60,
                env=minimal_env(workdir),
            )
        except subprocess.TimeoutExpired:
            return ConvertResult(False, None, "Conversion timed out.")
        if proc.returncode == 0 and base_docx.exists():
            break
        if use_sandbox and len(attempts) > 1:
            logger.warning("pandoc --sandbox run failed rc=%s; retrying without it", proc.returncode)
    if proc is None or proc.returncode != 0 or not base_docx.exists():
        return ConvertResult(False, None, (proc.stderr.strip()[:500] if proc else "") or "pandoc failed")

    try:
        docx_format.format_docx(
            str(base_docx), str(out_docx), tex_path=str(flat_path),
            anonymize=anonymize, style=style,
        )
    except Exception as exc:
        return ConvertResult(False, None, f"Post-processing failed: {exc}"[:500])
    return ConvertResult(True, out_docx.read_bytes())
