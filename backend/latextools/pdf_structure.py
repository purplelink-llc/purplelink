"""Pure helpers for the free PDF-to-Structured-Data tool.

Resolved interface (OpenDataLoader-PDF v2.4.7, Apache-2.0):
  - Install: `pip install opendataloader-pdf` (bundles the CLI JAR + LICENSE/
    NOTICE/THIRD_PARTY). Needs a JRE (Java 17) on PATH.
  - Run: opendataloader_pdf.convert(input_path=..., output_dir=...,
    format=["json","markdown"]). `format` defaults to JSON-only, so both
    formats are passed explicitly. It WRITES files; default mode is
    deterministic-local (OCR / hybrid / picture description are hybrid-server
    parameters only and `hybrid` defaults off).
    NOTE: `output_folder` / `generate_markdown` belong to the DEPRECATED
    `run()` wrapper, NOT `convert()`. Passing them to convert() raises
    TypeError. Verified against convert_generated.py upstream.
  - Output JSON root: {"number of pages": int, "kids": [ ...recursive blocks ]};
    each block has "type" (heading/paragraph/table/image/figure/...) and
    "content" (text), and may have its own "kids".

No Modal/JVM imports here so it stays unit-testable. The actual convert()
call + temp-dir lifecycle lives in app.py's pdf_structure_run.
"""
from __future__ import annotations

import json as _json
import re

_WORD = re.compile(r"\b\w+\b")


def safe_convert_kwargs(input_path: str, output_dir: str) -> dict:
    """Kwargs for opendataloader_pdf.convert() (the modern API).

    convert() takes `output_dir` + a `format` list; `format` defaults to JSON
    only, so we pass both "json" and "markdown" explicitly. OCR / picture
    description are NOT convert() parameters (hybrid-server-only; `hybrid`
    defaults off), so default convert() is deterministic + local.
    `pages="1-50"` bounds CPU/cost per the design's page cap.
    """
    return {
        "input_path": input_path,
        "output_dir": output_dir,
        "format": ["json", "markdown"],
        "pages": "1-50",
    }


def _walk(node, on_block):
    """Depth-first walk over the recursive 'kids' tree."""
    if isinstance(node, dict):
        on_block(node)
        kids = node.get("kids")
        if isinstance(kids, list):
            for k in kids:
                _walk(k, on_block)
    elif isinstance(node, list):
        for k in node:
            _walk(k, on_block)


def summarize(doc: dict) -> dict:
    """Compute {pages, tables, figures, words} from the OpenDataLoader JSON."""
    if not isinstance(doc, dict):
        return {"pages": 0, "tables": 0, "figures": 0, "words": 0}
    n_pages = int(doc.get("number of pages") or 0)
    counts = {"tables": 0, "figures": 0, "words": 0}

    def on_block(b):
        t = str(b.get("type") or "").lower()
        if "table" in t:
            counts["tables"] += 1
        elif "image" in t or "figure" in t or "picture" in t:
            counts["figures"] += 1
        content = b.get("content")
        if isinstance(content, str):
            counts["words"] += len(_WORD.findall(content))

    for kid in (doc.get("kids") or []):
        _walk(kid, on_block)
    return {"pages": n_pages, **counts}


def parse_output_dir(out_dir, read_text, list_files) -> dict:
    """Given injected IO (read_text(name)->str, list_files(dir)->[names]),
    return {markdown, json, summary}. Injected IO keeps this pure/testable."""
    md = ""
    structured = {}
    for name in list_files(out_dir):
        low = name.lower()
        if low.endswith(".md") or low.endswith(".markdown"):
            md = read_text(name)
        elif low.endswith(".json"):
            try:
                structured = _json.loads(read_text(name))
            except Exception:
                structured = {}
    return {"markdown": md, "json": structured, "summary": summarize(structured)}
