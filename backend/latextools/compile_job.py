"""One compile for the LaTeX compile app: source (+ optional bibliography) in, PDF and explained errors out.

Runs where TeX is installed: the TeX Live function in compile_mcp_app.py, or this Mac for local tests
(scripts/compile_mcp_local.py). The hardening is the site's: latexmk with -no-shell-escape (core.py), a minimal
environment, a process-group kill on timeout (runner.py), and in the Modal image texmf.cnf with
openin_any/openout_any = p. Nothing is kept: the working folder is deleted when the call returns.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from latextools import compile_explain, core, runner
from latextools.safe_exec import minimal_env

MAX_SOURCE_CHARS = 300_000
MAX_BIB_CHARS = 300_000
MAX_PDF_BYTES = 4_000_000          # larger PDFs are compiled but not returned
COMPILE_TIMEOUT = 45
ENGINES = ("pdflatex", "xelatex", "lualatex")

_BIB_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_BIBLIOGRAPHY = re.compile(r"\\bibliography\{([^}]*)\}")
_ADDBIBRESOURCE = re.compile(r"\\addbibresource(?:\[[^\]]*\])?\{([^}]*)\}")
_PAGES = re.compile(r"Output written on \S+ \((\d+) pages?")


class InputError(ValueError):
    pass


def bib_filenames(source: str) -> list[str]:
    """Names the document reads its bibliography from (refs for \\bibliography{refs}, refs.bib for biblatex).
    Unsafe names (paths, dots) are dropped, so a .bib can only be written inside the working folder."""
    names: list[str] = []
    for m in _BIBLIOGRAPHY.finditer(source):
        names += [n.strip() for n in m.group(1).split(",")]
    for m in _ADDBIBRESOURCE.finditer(source):
        names.append(m.group(1).strip())
    out = []
    for n in names:
        stem = n[:-4] if n.lower().endswith(".bib") else n
        if _BIB_NAME.match(stem) and f"{stem}.bib" not in out:
            out.append(f"{stem}.bib")
    return out or ["refs.bib"]


def validate(source: str, engine: str, bibliography: Optional[str]) -> None:
    if not source or not source.strip():
        raise InputError("The LaTeX source is empty.")
    if len(source) > MAX_SOURCE_CHARS:
        raise InputError(f"The source is {len(source):,} characters; the limit is {MAX_SOURCE_CHARS:,}.")
    if "\\documentclass" not in source:
        raise InputError("The source has no \\documentclass line. Send a complete document, from \\documentclass "
                         "to \\end{document}.")
    if engine not in ENGINES:
        raise InputError(f"Unknown engine {engine!r}; use one of {', '.join(ENGINES)}.")
    if bibliography is not None and len(bibliography) > MAX_BIB_CHARS:
        raise InputError(f"The bibliography is {len(bibliography):,} characters; the limit is {MAX_BIB_CHARS:,}.")


def _preview_png(workdir: Path) -> Optional[bytes]:
    """Page 1 as a small PNG, when poppler's pdftoppm is installed (it is in the Modal image)."""
    if not shutil.which("pdftoppm"):
        return None
    try:
        subprocess.run(["pdftoppm", "-png", "-r", "60", "-f", "1", "-l", "1", "-singlefile", "main.pdf", "preview"],
                       cwd=workdir, capture_output=True, timeout=15, env=minimal_env(workdir))
    except subprocess.TimeoutExpired:
        return None
    p = workdir / "preview.png"
    return p.read_bytes() if p.exists() else None


def compile_document(source: str, engine: str = "pdflatex", bibliography: Optional[str] = None,
                     timeout: int = COMPILE_TIMEOUT) -> dict:
    """Compile one document. Returns a plain dict (it crosses a Modal function boundary):
    ok, timed_out, engine, pages, errors [{file, line, message, kind, title, explanation, fix, learn_more}],
    warnings [...], pdf (bytes or None), pdf_bytes, pdf_omitted, preview_png (bytes or None), log_tail."""
    validate(source, engine, bibliography)
    with tempfile.TemporaryDirectory(prefix="pl-compile-") as d:
        work = Path(d)
        if bibliography:
            for name in bib_filenames(source):
                (work / name).write_text(bibliography, encoding="utf-8")
        res = runner.run_compile(work, source, engine, timeout=timeout)
        out: dict = {
            "ok": bool(res.ok), "timed_out": bool(res.timed_out), "engine": engine, "pages": None,
            "errors": [], "warnings": compile_explain.warnings_from_log(res.log),
            "pdf": None, "pdf_bytes": 0, "pdf_omitted": False, "preview_png": None, "log_tail": "",
        }
        m = _PAGES.search(res.log or "")
        if m:
            out["pages"] = int(m.group(1))
        for e in res.errors or core.parse_latex_log(res.log or ""):
            if e.get("message", "").startswith("==> Fatal error occurred"):
                continue   # TeX's closing line after the real error, not an error of its own
            ex = compile_explain.explain(e.get("message", "")) or {}
            out["errors"].append({**e, **ex})
        if res.ok and res.pdf_bytes:
            out["pdf_bytes"] = len(res.pdf_bytes)
            if len(res.pdf_bytes) <= MAX_PDF_BYTES:
                out["pdf"] = res.pdf_bytes
            else:
                out["pdf_omitted"] = True
            out["preview_png"] = _preview_png(work)
        elif not res.timed_out:
            out["log_tail"] = (res.log or "")[-3000:]
        return out
