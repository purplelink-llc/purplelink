"""Pure, dependency-free logic for the LaTeX tools backend.

Nothing in this module shells out or imports Modal/TeX. It is unit-tested
directly so the security-critical decisions (validation, command building,
log parsing) have fast, deterministic coverage.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path

MAX_UPLOAD_BYTES = 5 * 1024 * 1024   # 5 MB cap for single .tex files
MAX_ZIP_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB cap for project ZIPs (compressed)
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB uncompressed (zip-bomb guard)
MAX_ZIP_FILES = 500

# Extensions allowed inside a project ZIP.
ALLOWED_ZIP_EXTENSIONS = frozenset({
    ".tex", ".bib", ".cls", ".sty", ".bst",
    ".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg",
    ".tikz", ".pgf", ".dat", ".csv",
    ".bbx", ".cbx", ".lbx",  # biblatex driver files
    ".clo",   # class option files
    ".def",   # definition files
    ".fd",    # font definition files
    ".cfg",   # config files
    ".ist",   # makeindex style
})


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
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(".tex"):
        raise ValidationError("File must be a .tex file.")


MAX_BIB_UPLOAD_BYTES = 2 * 1024 * 1024   # 2 MB cap for .bib files
MAX_DOCX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB cap for .docx files


def validate_bib_upload(filename: str, size_bytes: int) -> None:
    """Validate a .bib upload's name and size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_BIB_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_BIB_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(".bib"):
        raise ValidationError("File must be a .bib file.")


def validate_docx_upload(filename: str, size_bytes: int) -> None:
    """Validate a .docx upload's name and size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_DOCX_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_DOCX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(".docx"):
        raise ValidationError("File must be a .docx file.")


def validate_zip_upload(filename: str, size_bytes: int) -> None:
    """Validate a project ZIP upload's name and compressed size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_ZIP_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_ZIP_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(".zip"):
        raise ValidationError("File must be a .zip file.")


def extract_project_zip(zip_bytes: bytes, workdir: Path) -> None:
    """Safely extract a LaTeX project ZIP to *workdir*.

    Security invariants enforced:
    - No path traversal (rejects '..' components and paths outside workdir)
    - No symlinks (Unix external_attr mode check)
    - Extension whitelist (TeX-ecosystem types only)
    - File-count cap (MAX_ZIP_FILES)
    - Uncompressed-size cap (MAX_UNCOMPRESSED_BYTES, zip-bomb guard)

    Raises ValidationError on any violation, or if the archive contains no
    top-level main.tex.
    """
    try:
        zf_handle = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise ValidationError("File is not a valid ZIP archive.")

    workdir_real = workdir.resolve()
    total_uncompressed = 0
    file_count = 0

    with zf_handle as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            # Reject symlinks (Unix mode 0120000 in the high 16 bits of external_attr).
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValidationError(
                    f"ZIP contains a symbolic link: {info.filename!r}"
                )

            file_count += 1
            if file_count > MAX_ZIP_FILES:
                raise ValidationError(
                    f"ZIP contains too many files (max {MAX_ZIP_FILES})."
                )

            # Build a safe destination path (ZIP paths use forward slashes).
            raw = info.filename.replace("\\", "/")
            parts = [p for p in raw.split("/") if p and p != "."]
            if ".." in parts:
                raise ValidationError(
                    f"ZIP contains path traversal in: {info.filename!r}"
                )
            if not parts:
                continue

            dest = workdir_real.joinpath(*parts)
            try:
                dest.relative_to(workdir_real)
            except ValueError:
                raise ValidationError(
                    f"ZIP path escapes workdir: {info.filename!r}"
                )

            suffix = Path(info.filename).suffix.lower()
            if suffix not in ALLOWED_ZIP_EXTENSIONS:
                raise ValidationError(
                    f"ZIP contains unsupported file type {suffix!r}. "
                    f"Allowed: {', '.join(sorted(ALLOWED_ZIP_EXTENSIONS))}"
                )

            total_uncompressed += info.file_size
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise ValidationError(
                    f"ZIP uncompressed content exceeds "
                    f"{MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB."
                )

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info.filename))

    if not (workdir / "main.tex").exists():
        raise ValidationError(
            "ZIP must contain a top-level main.tex."
        )


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


_PICTUREENV = r"PICTUREENV=(?:picture|DIFnomarkup|tabular)[\w\d*@]*"

_DIFF_LEGEND = (
    r"\fbox{\parbox{0.9\linewidth}{\textbf{How to read this revision diff:} "
    r"\textcolor{blue}{\uwave{blue underlined text}} was added; "
    r"\textcolor{red}{\sout{red struck-through text}} was deleted. "
    r"Changes inside tables are shown in final form only.}}"
)


def build_latexdiff_command(old_name: str, new_name: str) -> list[str]:
    """Build the latexdiff argv with table-safe defaults (spec §latex-diff)."""
    return [
        "latexdiff",
        "--type=UNDERLINE",
        f"--config={_PICTUREENV}",
        "--",
        old_name,
        new_name,
    ]


def inject_diff_legend(diff_tex: str) -> str:
    r"""Insert a 'how to read this diff' box immediately after \maketitle.

    No-op if the document has no \maketitle.
    """
    marker = r"\maketitle"
    idx = diff_tex.find(marker)
    if idx == -1:
        return diff_tex
    insert_at = idx + len(marker)
    return diff_tex[:insert_at] + "\n" + _DIFF_LEGEND + "\n" + diff_tex[insert_at:]


DAILY_LIMIT = 25  # compiles per IP per UTC day


def rate_limit_key(ip: str, day: str) -> str:
    """Build a daily, hashed rate-limit key. Raw IP is never persisted."""
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
    return f"rl:{day}:{digest}"


def check_and_increment(store, key: str) -> tuple[bool, int]:
    """Increment the counter for *key* in a dict-like *store*.

    Returns (allowed, remaining). When the prior count is already at
    DAILY_LIMIT, returns (False, 0) and does not increment further.
    *store* is any object supporting .get(key, default) and item assignment
    (a plain dict in tests, a modal.Dict in production).
    """
    current = store.get(key, 0)
    if current >= DAILY_LIMIT:
        return False, 0
    store[key] = current + 1
    return True, DAILY_LIMIT - (current + 1)
