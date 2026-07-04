"""Tests for latextools.resume_review."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from latextools import resume_review
from latextools.resume_review import extract_resume_text, run_resume_review


def test_extract_resume_text_uses_doc2md():
    with patch("latextools.doc2md.convert_to_markdown", return_value="John Doe\nSoftware Engineer") as mock_convert:
        text = extract_resume_text(b"fake pdf bytes", "resume.pdf")
    assert text == "John Doe\nSoftware Engineer"
    assert mock_convert.called


def test_extract_resume_text_truncates_to_max_chars():
    long_text = "x" * (resume_review.MAX_RESUME_CHARS + 5000)
    with patch("latextools.doc2md.convert_to_markdown", return_value=long_text):
        text = extract_resume_text(b"fake pdf bytes", "resume.pdf")
    assert len(text) == resume_review.MAX_RESUME_CHARS


def test_extract_resume_text_handles_docx_suffix():
    with patch("latextools.doc2md.convert_to_markdown", return_value="text") as mock_convert:
        extract_resume_text(b"fake docx bytes", "resume.docx")
    called_path = mock_convert.call_args[0][0]
    assert called_path.endswith(".docx")


def test_run_resume_review_empty_extraction_returns_error():
    with patch("latextools.resume_review.extract_resume_text", return_value=""):
        result = asyncio.run(run_resume_review(b"bytes", "resume.pdf"))
    assert result["status"] == "error"
    assert result["error"] == "empty_resume"


def test_run_resume_review_extraction_exception_returns_error():
    with patch("latextools.resume_review.extract_resume_text", side_effect=RuntimeError("boom")):
        result = asyncio.run(run_resume_review(b"bytes", "resume.pdf"))
    assert result["status"] == "error"
    assert "extraction_failed" in result["error"]


def _fake_persona_response(findings):
    import json
    return json.dumps(findings)


def test_run_resume_review_end_to_end_produces_report():
    persona_calls = []

    async def _fake_anthropic_message(client, *, system, user_content, max_tokens):
        text = user_content[0]["text"]
        persona_calls.append(text)
        # Distinguish persona calls (return JSON array) from the synthesis
        # call (return Markdown) by checking for the JSON-array instruction.
        if "Now produce your JSON array." in text:
            return _fake_persona_response([{"issue": "example", "severity": "minor"}])
        return "# Resume Review\n\n## Overall Verdict\nLooks fine."

    with patch("latextools.resume_review.extract_resume_text", return_value="John Doe\nExperience: Did things."), \
         patch("latextools.resume_review._anthropic_message", new=AsyncMock(side_effect=_fake_anthropic_message)):
        result = asyncio.run(run_resume_review(b"bytes", "resume.pdf"))

    assert result["status"] == "done"
    assert result["result_md"].startswith("# Resume Review")
    assert result["ats_findings"] == 1
    assert result["hiring_manager_findings"] == 1
    assert result["recruiter_findings"] == 1
    # 3 persona calls + 1 synthesis call
    assert len(persona_calls) == 4


def test_run_resume_review_same_resume_text_seen_by_all_stages():
    """Every persona call and the synthesis call must see the identical
    resume text — a mismatch here would let the synthesis stage
    contradict findings the personas were actually shown."""
    seen_texts = []

    async def _fake_anthropic_message(client, *, system, user_content, max_tokens):
        text = user_content[0]["text"]
        seen_texts.append(text)
        if "Now produce your JSON array." in text:
            return "[]"
        return "# Resume Review\n"

    resume_text = "Jane Smith\nSenior Engineer\nExperience: Built things."
    with patch("latextools.resume_review.extract_resume_text", return_value=resume_text), \
         patch("latextools.resume_review._anthropic_message", new=AsyncMock(side_effect=_fake_anthropic_message)):
        asyncio.run(run_resume_review(b"bytes", "resume.pdf"))

    assert len(seen_texts) == 4
    for text in seen_texts:
        assert resume_text in text


def test_run_resume_review_persona_failure_does_not_crash_pipeline():
    call_count = 0

    async def _fake_anthropic_message(client, *, system, user_content, max_tokens):
        nonlocal call_count
        call_count += 1
        text = user_content[0]["text"]
        if "Now produce your JSON array." in text:
            if call_count == 1:
                raise RuntimeError("transient failure")
            return "[]"
        return "# Resume Review\n"

    with patch("latextools.resume_review.extract_resume_text", return_value="Some resume text"), \
         patch("latextools.resume_review._anthropic_message", new=AsyncMock(side_effect=_fake_anthropic_message)):
        result = asyncio.run(run_resume_review(b"bytes", "resume.pdf"))

    assert result["status"] == "done"


def test_run_resume_review_synthesis_failure_returns_error():
    async def _fake_anthropic_message(client, *, system, user_content, max_tokens):
        text = user_content[0]["text"]
        if "Now produce your JSON array." in text:
            return "[]"
        raise RuntimeError("synthesis boom")

    with patch("latextools.resume_review.extract_resume_text", return_value="Some resume text"), \
         patch("latextools.resume_review._anthropic_message", new=AsyncMock(side_effect=_fake_anthropic_message)):
        result = asyncio.run(run_resume_review(b"bytes", "resume.pdf"))

    assert result["status"] == "error"
    assert result["error"] == "synthesis_failed"
