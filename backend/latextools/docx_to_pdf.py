"""Word (.docx) manuscript -> PDF, so the Paper Review pipeline can read it.

The review pipeline works on a PDF: it extracts text, renders pages for the
figure scan and annotates the pages. A Word upload is therefore converted first,
with pandoc and xelatex (both already in the Modal image).

The conversion is not Word's own rendering. Fonts, page breaks, page numbers and
figure placement differ from the original, and Word-only objects (some charts,
EMF and WMF pictures) may not survive. The caller tells the author so, and the
report notes it.

The upload is untrusted, so:
  * the archive is inspected before pandoc sees it (size, entry count, ratio,
    encryption, path names, required Word parts), which bounds a zip bomb;
  * pandoc runs with --sandbox, a hardened xelatex (no shell escape), a fixed
    argument list (no shell), a private temporary directory and a timeout;
  * nothing from the document is logged, and the temporary directory is removed.

Raises DocxError with a message that is safe to show to the author.
"""
from __future__ import annotations

import io
import logging
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_UNCOMPRESSED_BYTES = 150 * 1024 * 1024
MAX_ENTRIES = 3000
MAX_COMPRESSION_RATIO = 250            # per entry, and only for entries over 1 MB
CONVERT_TIMEOUT_SECONDS = 90
MAX_PDF_BYTES = 60 * 1024 * 1024
ZIP_MAGIC = b"PK\x03\x04"

NOTE_CONVERTED = (
    "_Note: this review ran on a PDF converted from your Word file. Fonts, page breaks and figure "
    "placement differ from Word, so page numbers and some comments on the annotated PDF will not "
    "match the original._"
)
NOTE_IMAGES = (
    " _Pictures that could not be converted were left out, so the figure review covers only what "
    "appears in the converted PDF._"
)

# Pandoc keeps going after dropping a picture it cannot place, but xelatex stops on
# some formats (EMF, WMF, certain TIFFs). This filter removes images for the retry.
_DROP_IMAGES_LUA = "function Image(el) return {} end\n"


class DocxError(Exception):
    """An upload that cannot be converted. The message is shown to the author."""


@dataclass
class Conversion:
    pdf: bytes
    images_dropped: bool = False

    @property
    def note(self) -> str:
        return NOTE_CONVERTED + (NOTE_IMAGES if self.images_dropped else "")


def inspect_docx(data: bytes) -> None:
    """Reject anything that is not a plain, readable Word document. Never extracts."""
    if not data.startswith(ZIP_MAGIC):
        raise DocxError("That file is not a Word (.docx) document.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, OSError, ValueError):
        raise DocxError("That Word file is damaged and could not be opened.")
    if len(infos) > MAX_ENTRIES:
        raise DocxError("That Word file contains too many parts to read.")
    names = set()
    total = 0
    for info in infos:
        name = info.filename
        if name.startswith("/") or ".." in name.split("/") or "\\" in name:
            raise DocxError("That Word file could not be read safely.")
        if info.flag_bits & 0x1:
            raise DocxError("That Word file is password-protected. Save an unprotected copy and upload that.")
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise DocxError("That Word file is too large once unpacked.")
        if info.file_size > 1024 * 1024 and info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO:
            raise DocxError("That Word file could not be read safely.")
        names.add(name)
    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
        raise DocxError("That file is not a Word (.docx) document.")


def _run_pandoc(src: Path, out: Path, workdir: Path, extra: list[str], timeout: float) -> subprocess.CompletedProcess:
    cmd = [
        "pandoc", str(src), "-f", "docx", "-o", str(out),
        "--sandbox", "--wrap=none", "--standalone",
        "--pdf-engine=xelatex", "--pdf-engine-opt=-no-shell-escape",
        "-V", "geometry:margin=1in", "-V", "fontsize=11pt",
    ] + extra
    return subprocess.run(cmd, cwd=workdir, capture_output=True, timeout=timeout)


def convert(data: bytes, timeout: float = CONVERT_TIMEOUT_SECONDS) -> Conversion:
    """Convert docx bytes to a PDF within `timeout` seconds in total (the retry without
    pictures shares the same budget). Raises DocxError if it cannot."""
    import time

    inspect_docx(data)
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryDirectory() as d:
        workdir = Path(d)
        src = workdir / "manuscript.docx"
        out = workdir / "manuscript.pdf"
        src.write_bytes(data)
        images_dropped = False
        try:
            proc = _run_pandoc(src, out, workdir, [], max(1.0, deadline - time.monotonic()))
            if proc.returncode != 0 or not out.exists():
                # Usually a picture format xelatex cannot place. Retry without pictures.
                out.unlink(missing_ok=True)
                filt = workdir / "drop_images.lua"
                filt.write_text(_DROP_IMAGES_LUA)
                remaining = deadline - time.monotonic()
                if remaining < 5:
                    raise subprocess.TimeoutExpired("pandoc", timeout)
                proc = _run_pandoc(src, out, workdir, ["--lua-filter", str(filt)], remaining)
                images_dropped = True
        except subprocess.TimeoutExpired:
            raise DocxError("Converting that Word file took too long. Export it to PDF from Word and upload the PDF.")
        except OSError:
            logger.error("docx conversion could not start pandoc")
            raise DocxError("Word files cannot be converted right now. Export it to PDF from Word and upload the PDF.")
        if proc.returncode != 0 or not out.exists():
            # stderr can echo document text, so only the exit code is logged.
            logger.warning("docx conversion failed rc=%s", proc.returncode)
            raise DocxError("That Word file could not be converted. Export it to PDF from Word and upload the PDF.")
        pdf = out.read_bytes()
        if not pdf.startswith(b"%PDF-") or len(pdf) > MAX_PDF_BYTES:
            raise DocxError("That Word file could not be converted. Export it to PDF from Word and upload the PDF.")
        return Conversion(pdf=pdf, images_dropped=images_dropped)
