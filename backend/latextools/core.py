"""Pure, dependency-free logic for the LaTeX tools backend.

Nothing in this module shells out or imports Modal/TeX. It is unit-tested
directly so the security-critical decisions (validation, command building,
log parsing) have fast, deterministic coverage.
"""
from __future__ import annotations

import hashlib
import io
import ipaddress
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


MAX_MD_UPLOAD_BYTES = 2 * 1024 * 1024   # 2 MB cap for markdown files
MAX_PDF_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB cap for PDFs to compress


def validate_md_upload(filename: str, size_bytes: int) -> None:
    """Validate a markdown upload's name and size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_MD_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_MD_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith((".md", ".markdown", ".txt")):
        raise ValidationError("File must be a .md, .markdown, or .txt file.")


def validate_pdf_upload(filename: str, size_bytes: int) -> None:
    """Validate a .pdf upload's name and size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_PDF_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_PDF_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(".pdf"):
        raise ValidationError("File must be a .pdf file.")


MAX_DOC2MD_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB cap for files converted to Markdown
MAX_PAPER_UPLOAD_BYTES = 20 * 1024 * 1024   # 20 MB cap for paper-review submissions


def validate_paper_upload(filename: str, size_bytes: int) -> None:
    """Validate a Paper Review upload's name and size. Raises ValidationError.

    Paper Review accepts only PDF manuscripts; the magic-byte check happens
    in the endpoint to keep this helper pure.
    """
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_PAPER_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_PAPER_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(".pdf"):
        raise ValidationError("File must be a .pdf manuscript.")

DOC2MD_ALLOWED_EXTENSIONS = (
    ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".csv", ".epub",
)


def validate_doc2md_upload(filename: str, size_bytes: int) -> None:
    """Validate a file-to-markdown upload's name and size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_DOC2MD_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_DOC2MD_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(DOC2MD_ALLOWED_EXTENSIONS):
        raise ValidationError(
            "Unsupported file type. Allowed: PDF, DOCX, PPTX, XLSX, HTML, CSV, EPUB."
        )


# Word-stats accepts everything doc2md does PLUS plain-text-shaped formats
# (the stat engine just needs text). .tex/.md/.txt are read directly; .rtf
# and .odt go through markitdown.
WORDSTATS_ALLOWED_EXTENSIONS = DOC2MD_ALLOWED_EXTENSIONS + (
    ".txt", ".md", ".markdown", ".tex", ".rtf", ".odt",
)
WORDSTATS_PLAINTEXT_EXTENSIONS = (".txt", ".md", ".markdown", ".tex")


def validate_wordstats_upload(filename: str, size_bytes: int) -> None:
    """Validate a Word Counter (Document Insights) upload. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_DOC2MD_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_DOC2MD_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(WORDSTATS_ALLOWED_EXTENSIONS):
        raise ValidationError(
            "Unsupported file type. Allowed: PDF, DOCX, ODT, RTF, EPUB, HTML, "
            "CSV, LaTeX (.tex), Markdown, and plain text."
        )


def doc2md_signature_ok(filename: str, data: bytes) -> bool:
    """Lightweight magic-byte check for binary doc2md formats.

    PDF starts with %PDF-; the ZIP-based Office/EPUB formats start with the
    local-file-header signature PK\\x03\\x04. Text formats (.html/.htm/.csv)
    have no reliable signature and pass.
    """
    name = filename.lower()
    if name.endswith(".pdf"):
        return data[:5] == b"%PDF-"
    if name.endswith((".docx", ".pptx", ".xlsx", ".epub")):
        return data[:4] == b"PK\x03\x04"
    return True


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


DAILY_LIMIT = 25  # requests per IP per endpoint bucket per UTC day


def _is_public_ip(ip: str) -> bool:
    """True only for well-formed, globally routable addresses."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_unspecified
        or addr.is_multicast
    )


def client_ip_from_forwarded(xff: str, peer: str | None) -> str:
    """Resolve the rate-limiting identity from an X-Forwarded-For chain.

    X-Forwarded-For is fully caller-controllable *except* the single entry the
    trusted ingress appends after the request arrives. We therefore only ever
    trust the *last* entry in the chain -- the one position a caller cannot
    write to, because the proxy appends after any client-supplied value and
    does not let the client add anything after that. We do NOT keep scanning
    further left looking for "the first public-looking address": doing so
    would let a caller smuggle a fabricated public IP one hop earlier and have
    it accepted whenever the true last hop happens to be private, malformed,
    or missing (e.g. a proxy quirk, an added CDN hop, or a bare peer socket).
    If that last entry isn't a well-formed public address, the chain is not
    trustworthy and we fall back to the direct socket peer instead.

    NOTE: this assumes the ingress appends exactly one trusted hop to the
    right of XFF and never forwards a client-supplied XFF verbatim. Verify
    against the deployment's proxy before relying on it as a hard security
    boundary; today it is a soft cost-control, not an auth gate.
    """
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts and _is_public_ip(parts[-1]):
            return parts[-1]
    if peer and _is_public_ip(peer):
        return peer
    return peer or "0.0.0.0"


def rate_limit_key(ip: str, day: str, bucket: str = "") -> str:
    """Build a daily, hashed, per-bucket rate-limit key. Raw IP is never persisted.

    *bucket* lets each endpoint family carry an independent daily quota so heavy
    use of one tool does not exhaust a user's allowance for the others.
    """
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
    prefix = f"rl:{bucket}:" if bucket else "rl:"
    return f"{prefix}{day}:{digest}"


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
