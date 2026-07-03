"""Inline PDF annotation rendering for Paper Review.

Takes the original manuscript PDF plus the structured findings from each
layer and overlays sticky-note / free-text annotations on the right pages.
The output is a downloadable annotated PDF the user can hand to a co-author.

Annotation strategy:
  - L1 findings have explicit `page` numbers → place a Text annotation on
    that page.
  - L3 panel findings quote the manuscript → search the page-text map for
    the quoted snippet, place a Text annotation on the page where it lives.
    Falls back to page 1 if the quote can't be located.
  - L2 citation issues all go to the references section (we approximate as
    the last page of the document).

Everything happens in memory; no temp files. Uses pypdf (already pulled in
by pdfplumber). Falls back gracefully — if pypdf isn't available, returns
None and the caller skips the annotated-PDF feature without failing.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)


# Cap so a pathological pipeline doesn't paste 200 sticky notes on one page
MAX_ANNOTATIONS_TOTAL = 60
MAX_ANNOTATIONS_PER_PAGE = 8

# Mirrors papercheck.MAX_EXTRACT_PAGES: the primary extraction path already
# bounds pdfplumber text extraction to the first N pages, so re-extracting
# text here for annotation placement should honor the same bound rather than
# re-parsing an unbounded number of pages a second time.
MAX_ANNOTATE_TEXT_PAGES = 400

# Defense in depth: even though these findings come from our own pipeline,
# a successful prompt-injection upstream (e.g. via the L1 vision channel)
# could steer L1/L3 output into arbitrary text that gets embedded verbatim
# in a FreeText annotation on the user's downloaded PDF. Mirror the
# invisible/control-character stripping that safety.sanitize_user_text
# applies on the input side, plus a hard length cap per annotation, so a
# manipulated finding can't smuggle hidden Unicode or blow up the PDF with
# an oversized sticky note.
MAX_ANNOTATION_TEXT_CHARS = 2_000

_INVISIBLE_PATTERN = re.compile(
    r"[​-‏‪-‮⁠-⁩⁪-⁯﻿؜]"
)
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize_annotation_text(text: str) -> str:
    """Strip invisible/control characters and cap length for PDF annotations.

    Applied to every string that ends up inside a FreeText annotation, since
    that text is LLM-derived and (in a chained-exploit scenario) could carry
    attacker-steered content through to a file the user forwards to others.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE_PATTERN.sub("", text)
    text = _CONTROL_PATTERN.sub("", text)
    if len(text) > MAX_ANNOTATION_TEXT_CHARS:
        text = text[:MAX_ANNOTATION_TEXT_CHARS].rstrip() + "…"
    return text


def _build_page_text_map(pdf_bytes: bytes) -> dict[int, str]:
    """Return {1-based page number: text} extracted via pdfplumber.

    Bounded by MAX_ANNOTATE_TEXT_PAGES (mirrors papercheck.MAX_EXTRACT_PAGES)
    so a manuscript with a huge page count doesn't force a second unbounded
    full-document pdfplumber pass here, on top of the one extract_paper()
    already did.
    """
    try:
        import pdfplumber
    except ImportError:
        return {}
    out: dict[int, str] = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                if idx > MAX_ANNOTATE_TEXT_PAGES:
                    logger.warning(
                        "_build_page_text_map: PDF exceeds MAX_ANNOTATE_TEXT_PAGES "
                        "(%d); truncating quote-search text extraction",
                        MAX_ANNOTATE_TEXT_PAGES,
                    )
                    break
                try:
                    out[idx] = page.extract_text() or ""
                except Exception:
                    out[idx] = ""
    except Exception:
        logger.warning("pdfplumber failed during annotation page-text map build")
    return out


def _normalize_for_search(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _find_page_for_quote(quote: str, page_texts: dict[int, str]) -> Optional[int]:
    """Best-effort: locate which page contains a quoted manuscript snippet.

    Tries the full quote first, then prefixes of decreasing length so a
    slightly-paraphrased quote still maps to the right page.
    """
    if not quote or not page_texts:
        return None
    q = _normalize_for_search(quote.strip().strip('"“”'))
    if len(q) < 20:
        return None

    for trim in (len(q), 80, 50, 30):
        needle = q[:trim] if trim < len(q) else q
        if len(needle) < 20:
            break
        for page_num, text in page_texts.items():
            if needle in _normalize_for_search(text):
                return page_num
    return None


def _wrap_text(s: str, width: int = 60) -> str:
    """Wrap a long string into max-width lines without breaking words."""
    words = s.split()
    out: list[str] = []
    line: list[str] = []
    line_len = 0
    for w in words:
        if line_len + len(w) + 1 > width and line:
            out.append(" ".join(line))
            line = [w]
            line_len = len(w)
        else:
            line.append(w)
            line_len += len(w) + 1
    if line:
        out.append(" ".join(line))
    return "\n".join(out)


def _make_annotation_text(finding: dict, source_layer: str) -> str:
    """Render a finding dict into a sticky-note body."""
    severity = (finding.get("severity") or "minor").upper()
    issue = finding.get("issue") or finding.get("observation") or "(no description)"
    where = finding.get("where") or ""
    persona = finding.get("persona") or ""
    fix = finding.get("what_a_referee_would_say") or finding.get("recommendation") or ""

    header = f"[{source_layer.upper()} | {severity}]"
    if where:
        header += f" {where}"
    if persona:
        header += f" — {persona.replace('_', ' ').title()}"

    body = _wrap_text(issue, 60)
    parts = [header, body]
    if fix:
        parts.append("\nFix: " + _wrap_text(fix, 60))
    return "\n".join(parts)


def _make_audit_annotation_text(finding: dict) -> str:
    """Render one audit finding into a sticky-note body."""
    verdict = finding.get("verdict") or "(no verdict)"
    ref = finding.get("ref_key") or ""
    quote = finding.get("source_quote") or ""
    rationale = finding.get("rationale") or ""
    head = f"CITATION AUDIT — {verdict}"
    if ref:
        head += f" [{ref}]"
    lines = [head]
    if quote:
        lines.append(_wrap_text(f"Source abstract: {quote}"))
    if rationale:
        lines.append(_wrap_text(rationale))
    return "\n".join(lines)


def _audit_findings_to_annotate(findings: list) -> list:
    """Only Contradicted / Not-supported findings earn a margin annotation."""
    keep = {"Contradicted", "Not supported by abstract"}
    return [f for f in (findings or []) if f.get("verdict") in keep]


def annotate_pdf(
    pdf_bytes: bytes,
    *,
    l1: dict,
    l2: dict,
    l3: dict,
) -> Optional[bytes]:
    """Build an annotated PDF from the original + structured findings.

    Returns the annotated PDF bytes, or None if annotation isn't available
    in the current environment. The caller is expected to skip the
    annotated-PDF feature gracefully on None.
    """
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import FreeText
        from pypdf.generic import Fit
    except ImportError:
        logger.warning("pypdf not installed; PDF annotation skipped")
        return None

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        logger.exception("pypdf failed to read input PDF")
        return None

    n_pages = len(reader.pages)
    if n_pages == 0:
        return None

    page_texts = _build_page_text_map(pdf_bytes)

    # Gather (page, source, finding) triples, capped + balanced across pages.
    # A defaultdict avoids pre-allocating one entry per page up front, which
    # matters for manuscripts with a very large page count (see
    # MAX_ANNOTATE_TEXT_PAGES above for the matching text-extraction bound).
    page_buckets: dict[int, list[tuple[str, dict]]] = defaultdict(list)
    total = 0

    def _add(page: int, source: str, f: dict) -> None:
        nonlocal total
        page = max(1, min(page, n_pages))
        if total >= MAX_ANNOTATIONS_TOTAL:
            return
        if len(page_buckets[page]) >= MAX_ANNOTATIONS_PER_PAGE:
            return
        page_buckets[page].append((source, f))
        total += 1

    # L1 — explicit page numbers
    for f in l1.get("findings", []) or []:
        page = int(f.get("page") or 1)
        _add(page, "l1", f)

    # L3 — search the body for the quoted claim
    for f in (l3.get("merged_findings") or [])[:40]:
        quote = f.get("claim_quoted", "")
        page = _find_page_for_quote(quote, page_texts) or 1
        _add(page, "l3", f)

    # Audit — place a note on the page where the claim sentence lives.
    audit = (l2.get("audit") or {})
    for f in _audit_findings_to_annotate(audit.get("findings", []))[:20]:
        page = _find_page_for_quote(f.get("claim_sentence", ""), page_texts) or 1
        _add(page, "audit", {
            "issue": _make_audit_annotation_text(f),
            "severity": "major" if f.get("verdict") == "Contradicted" else "minor",
        })

    # L2 — references-section findings; land them on the last page
    for issue in (l2.get("issues") or [])[:10]:
        _add(n_pages, "l2", {
            "severity": "minor",
            "issue": (
                f"Citation issue ({issue.get('status', 'unknown')}): "
                f"{(issue.get('raw') or '')[:200]}"
            ),
            "where": "References",
        })

    if total == 0:
        # Nothing to annotate — return the original so the user still gets
        # a "no-issues" PDF rather than nothing.
        try:
            buf = io.BytesIO()
            writer = PdfWriter(clone_from=reader)
            writer.write(buf)
            return buf.getvalue()
        except Exception:
            return None

    writer = PdfWriter(clone_from=reader)

    # Place annotations as small FreeText boxes stacked in the right margin.
    for page_idx in range(n_pages):
        bucket = page_buckets.get(page_idx + 1) or []
        if not bucket:
            continue
        page = writer.pages[page_idx]
        media = page.mediabox
        page_w = float(media.width)
        page_h = float(media.height)

        # Right-margin column. Each annotation ~120 pt tall.
        col_x_left = page_w - 170
        col_x_right = page_w - 10
        ann_height = 120
        slot_gap = 6
        for slot, (source, f) in enumerate(bucket):
            top = page_h - 40 - slot * (ann_height + slot_gap)
            bottom = top - ann_height
            if bottom < 30:
                break
            text = _sanitize_annotation_text(_make_annotation_text(f, source))
            severity = (f.get("severity") or "minor").lower()
            # Colour by severity: critical = light red, major = light amber,
            # minor = light blue. RGB tuples in 0..1.
            if severity == "critical":
                bg = (1.0, 0.85, 0.85)
                border = (0.7, 0.1, 0.1)
            elif severity == "major":
                bg = (1.0, 0.95, 0.78)
                border = (0.85, 0.55, 0.05)
            else:
                bg = (0.86, 0.92, 1.0)
                border = (0.2, 0.4, 0.85)

            try:
                annotation = FreeText(
                    text=text,
                    rect=(col_x_left, bottom, col_x_right, top),
                    font="Helvetica",
                    font_size="7pt",
                    font_color="222222",
                    border_color=("%02x%02x%02x" % tuple(int(c * 255) for c in border)),
                    background_color=("%02x%02x%02x" % tuple(int(c * 255) for c in bg)),
                )
                writer.add_annotation(page_number=page_idx, annotation=annotation)
            except Exception:
                # If FreeText placement fails on this page (e.g. unusual
                # mediabox), drop this annotation and continue.
                logger.warning("annotation placement failed on page %d", page_idx + 1)

    # Cover-page summary annotation (TOC of issues)
    try:
        cover_lines = [f"Purplelink Paper Review — annotated copy"]
        cover_lines.append(f"Total issues: {total}")
        for sev in ("critical", "major", "minor"):
            n = sum(
                1 for bucket in page_buckets.values() for _, f in bucket
                if (f.get("severity") or "minor").lower() == sev
            )
            if n:
                cover_lines.append(f"  {sev}: {n}")
        cover_lines.append("")
        cover_lines.append("Each annotation is colour-coded by severity:")
        cover_lines.append("  red = critical · amber = major · blue = minor.")
        cover_lines.append("The full Markdown report has the rectification checklist.")
        cover_text = "\n".join(cover_lines)
        cover_page = writer.pages[0]
        media = cover_page.mediabox
        w, h = float(media.width), float(media.height)
        toc_ann = FreeText(
            text=cover_text,
            rect=(10, h - 180, 200, h - 30),
            font="Helvetica",
            font_size="8pt",
            font_color="111111",
            border_color="7c3aed",
            background_color="f3eafd",
        )
        writer.add_annotation(page_number=0, annotation=toc_ann)
    except Exception:
        logger.warning("cover-page TOC annotation failed")

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
