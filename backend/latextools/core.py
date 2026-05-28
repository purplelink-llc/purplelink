"""Pure, dependency-free logic for the LaTeX tools backend.

Nothing in this module shells out or imports Modal/TeX. It is unit-tested
directly so the security-critical decisions (validation, command building,
log parsing) have fast, deterministic coverage.
"""
from __future__ import annotations

import os
import re

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB hard cap (matches spec)


class ValidationError(Exception):
    """Raised when an uploaded file fails a safety/format check."""


def validate_upload(filename: str, size_bytes: int) -> None:
    """Validate an uploaded LaTeX file's name and size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    base = os.path.basename(filename)
    if base != filename or base in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not base.lower().endswith(".tex"):
        raise ValidationError("File must be a .tex file.")


# Engine name -> latexmk engine flag. LuaLaTeX deliberately excluded (spec §RCE).
_ENGINE_FLAGS = {
    "pdflatex": "-pdf",
    "xelatex": "-xelatex",
}


def build_latexmk_command(engine: str, jobname: str) -> list[str]:
    """Build the latexmk argv for a hardened single-file compile.

    -no-shell-escape disables \\write18. File-read/write confinement is set
    via texmf.cnf (openin_any/openout_any=p) baked into the image.
    """
    flag = _ENGINE_FLAGS.get(engine)
    if flag is None:
        raise ValidationError(f"unsupported engine: {engine}")
    return [
        "latexmk",
        flag,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-no-shell-escape",
        "-file-line-error",
        f"{jobname}.tex",
    ]


MAX_REPORTED_ERRORS = 20

# With -file-line-error, errors look like:  main.tex:12: Undefined control sequence.
_FILE_LINE_ERROR = re.compile(r"^(?P<file>[^:\n]+\.tex):(?P<line>\d+):\s*(?P<msg>.+)$")


def parse_latex_log(log_text: str) -> list[dict]:
    """Extract structured errors from a latexmk/pdflatex log.

    Returns a list of {"file", "line", "message"} dicts, capped at
    MAX_REPORTED_ERRORS. Returns [] when no errors are found.
    """
    errors: list[dict] = []
    for raw in log_text.splitlines():
        m = _FILE_LINE_ERROR.match(raw.strip())
        if not m:
            continue
        errors.append(
            {
                "file": m.group("file"),
                "line": int(m.group("line")),
                "message": m.group("msg").strip(),
            }
        )
        if len(errors) >= MAX_REPORTED_ERRORS:
            break
    return errors
