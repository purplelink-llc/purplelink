"""Word (.docx) uploads for Paper Review: archive inspection, conversion with a
stubbed pandoc, the report note, and upload validation. The real toolchain is
exercised separately on Modal (the local pandoc is the wrong architecture)."""
import io
import subprocess
import zipfile

import pytest

from latextools import core, docx_to_pdf as d2p


def make_docx(extra=None, drop=(), content_types=True, document=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if content_types and "[Content_Types].xml" not in drop:
            z.writestr("[Content_Types].xml", "<Types/>")
        if document and "word/document.xml" not in drop:
            z.writestr("word/document.xml", "<w:document/>")
        for name, body in (extra or {}).items():
            z.writestr(name, body)
    return buf.getvalue()


# ---- inspect_docx ---------------------------------------------------------------------

def test_a_plain_docx_passes_inspection():
    d2p.inspect_docx(make_docx())


@pytest.mark.parametrize("data,why", [
    (b"%PDF-1.7 not a zip", "not a Word"),
    (b"PK\x03\x04garbage", "damaged"),
    (make_docx(drop=("word/document.xml",)), "not a Word"),
    (make_docx(drop=("[Content_Types].xml",)), "not a Word"),
])
def test_things_that_are_not_word_files_are_refused_with_a_plain_message(data, why):
    with pytest.raises(d2p.DocxError) as e:
        d2p.inspect_docx(data)
    assert why in str(e.value)


def test_too_many_entries_are_refused(monkeypatch):
    monkeypatch.setattr(d2p, "MAX_ENTRIES", 5)
    with pytest.raises(d2p.DocxError, match="too many parts"):
        d2p.inspect_docx(make_docx({f"word/media/{i}.png": "x" for i in range(10)}))


def test_a_zip_bomb_by_ratio_is_refused():
    big = make_docx({"word/media/huge.bin": b"\0" * (4 * 1024 * 1024)})
    with pytest.raises(d2p.DocxError, match="could not be read safely"):
        d2p.inspect_docx(big)


def test_an_oversized_unpacked_total_is_refused(monkeypatch):
    monkeypatch.setattr(d2p, "MAX_UNCOMPRESSED_BYTES", 1000)
    with pytest.raises(d2p.DocxError, match="too large once unpacked"):
        d2p.inspect_docx(make_docx({"word/media/a.bin": b"abcdefgh" * 500}))


def test_path_traversal_names_are_refused():
    for name in ("../evil.txt", "/abs/evil.txt", "word\\evil.txt"):
        with pytest.raises(d2p.DocxError, match="could not be read safely"):
            d2p.inspect_docx(make_docx({name: "x"}))


def test_an_encrypted_entry_is_refused_with_advice():
    buf = io.BytesIO(make_docx())
    with zipfile.ZipFile(buf) as z:
        infos = z.infolist()
    raw = bytearray(buf.getvalue())
    # Set general-purpose flag bit 0 (encrypted) in the first local and central headers.
    raw[6] |= 0x01
    cd = raw.rfind(b"PK\x01\x02")
    raw[cd + 8] |= 0x01
    with pytest.raises(d2p.DocxError, match="password-protected"):
        d2p.inspect_docx(bytes(raw))


# ---- convert --------------------------------------------------------------------------

class FakePandoc:
    """Stands in for subprocess.run. `script` is a list of outcomes, one per call:
    "ok", "fail", "timeout", "oserror", or "badpdf"."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, cmd, cwd=None, capture_output=None, timeout=None, **kw):
        self.calls.append({"cmd": cmd, "timeout": timeout})
        outcome = self.script.pop(0)
        out = cmd[cmd.index("-o") + 1]
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout)
        if outcome == "oserror":
            raise FileNotFoundError("pandoc")
        if outcome == "ok":
            open(out, "wb").write(b"%PDF-1.5\nfake")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        if outcome == "badpdf":
            open(out, "wb").write(b"not a pdf")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        return subprocess.CompletedProcess(cmd, 43, b"", b"secret manuscript text in an error")


def run_convert(monkeypatch, script, **kw):
    fake = FakePandoc(script)
    monkeypatch.setattr(d2p.subprocess, "run", fake)
    return fake, d2p.convert(make_docx(), **kw)


def test_a_clean_conversion_returns_the_pdf_and_the_standard_note(monkeypatch):
    fake, res = run_convert(monkeypatch, ["ok"])
    assert res.pdf.startswith(b"%PDF-") and res.images_dropped is False
    assert res.note == d2p.NOTE_CONVERTED
    cmd = fake.calls[0]["cmd"]
    assert cmd[0] == "pandoc" and "--sandbox" in cmd and "-f" in cmd and cmd[cmd.index("-f") + 1] == "docx"
    assert "--pdf-engine-opt=-no-shell-escape" in cmd and "--pdf-engine=xelatex" in cmd
    assert len(fake.calls) == 1


def test_a_failed_first_attempt_retries_without_pictures_and_says_so(monkeypatch):
    fake, res = run_convert(monkeypatch, ["fail", "ok"])
    assert res.images_dropped is True and res.note.endswith(d2p.NOTE_IMAGES)
    assert "--lua-filter" in fake.calls[1]["cmd"]
    assert "--lua-filter" not in fake.calls[0]["cmd"]


def test_both_attempts_failing_gives_advice_and_logs_no_document_text(monkeypatch, caplog):
    caplog.set_level("WARNING")
    with pytest.raises(d2p.DocxError, match="Export it to PDF from Word"):
        run_convert(monkeypatch, ["fail", "fail"])
    assert "secret manuscript text" not in caplog.text


def test_a_timeout_is_reported_as_too_slow(monkeypatch):
    with pytest.raises(d2p.DocxError, match="took too long"):
        run_convert(monkeypatch, ["timeout"])


def test_pandoc_missing_is_reported_without_a_traceback(monkeypatch):
    with pytest.raises(d2p.DocxError, match="cannot be converted right now"):
        run_convert(monkeypatch, ["oserror"])


def test_output_that_is_not_a_pdf_is_refused(monkeypatch):
    with pytest.raises(d2p.DocxError, match="could not be converted"):
        run_convert(monkeypatch, ["badpdf", "badpdf"])


def test_the_retry_shares_the_time_budget(monkeypatch):
    fake, _ = run_convert(monkeypatch, ["fail", "ok"], timeout=30)
    assert fake.calls[0]["timeout"] <= 30 and fake.calls[1]["timeout"] <= fake.calls[0]["timeout"]


def test_inspection_runs_before_pandoc_is_started(monkeypatch):
    fake = FakePandoc(["ok"])
    monkeypatch.setattr(d2p.subprocess, "run", fake)
    with pytest.raises(d2p.DocxError):
        d2p.convert(b"%PDF-1.4 renamed")
    assert fake.calls == []


# ---- upload validation ------------------------------------------------------------------

def test_manuscript_validation_returns_the_kind():
    assert core.validate_manuscript_upload("paper.pdf", 10) == "pdf"
    assert core.validate_manuscript_upload("Paper.DOCX", 10) == "docx"


@pytest.mark.parametrize("name,size", [("paper.doc", 10), ("paper.docm", 10), ("paper.txt", 10), ("", 10),
                                        ("a/b.docx", 10), ("paper.docx", 0), ("paper.docx", core.MAX_PAPER_UPLOAD_BYTES + 1)])
def test_manuscript_validation_rejects_the_rest(name, size):
    with pytest.raises(core.ValidationError):
        core.validate_manuscript_upload(name, size)


def test_the_pdf_only_validator_other_tools_use_is_unchanged():
    core.validate_paper_upload("paper.pdf", 10)
    with pytest.raises(core.ValidationError):
        core.validate_paper_upload("paper.docx", 10)
