"""Render a finished review (Markdown) to a PDF for the delivery email.

The report is the only thing rendered here. This module never receives the
manuscript or the annotated PDF, so neither can end up in the attachment.

Uses the pandoc + TeX toolchain already in the Modal image (the same one
/markdown-convert uses). The Markdown comes from an LLM that read an
attacker-controllable manuscript, so it is parsed as `gfm`: that reader has
no raw-TeX pass-through, no YAML metadata block and no `$...$` maths, which
leaves nothing in the text able to reach the TeX engine as code. The engine
also runs with -no-shell-escape on top of the image's hardened texmf.cnf.

Returns None on any failure; the caller then attaches the Markdown instead.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RENDER_TIMEOUT_SECONDS = 60
MAX_REPORT_MD_CHARS = 400_000

# pdflatex stops on characters its default input encoding does not know.
# xelatex is tried first and copes with them; this table only feeds the
# pdflatex fallback, where a readable ASCII stand-in beats no PDF at all.
_ASCII_FALLBACKS = {
    "≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "×": "x",
    "−": "-", "–": "-", "—": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "→": "->", "←": "<-",
    "±": "+/-", "•": "-", " ": " ", "α": "alpha",
    "β": "beta", "γ": "gamma", "δ": "delta", "η": "eta",
    "λ": "lambda", "μ": "mu", "ρ": "rho", "σ": "sigma",
    "χ": "chi", "ω": "omega", "Δ": "Delta", "²": "^2",
    "✓": "[ok]", "✗": "[x]", "⚠": "[!]",
}


# The image's default xelatex font (Latin Modern) has no glyph for these, and
# xelatex drops a missing glyph silently: "p ≤ 0.05" printed as "p 0.05" in the
# first production test (2026-10-01). A report that loses an inequality sign
# misleads, so the symbols are spelled out before either engine sees them.
_SYMBOL_FALLBACKS = {
    **{k: v for k, v in {
        "≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "×": "x", "±": "+/-",
        "✓": "[ok]", "✔": "[ok]", "✗": "[x]", "✘": "[x]", "⚠": "[!]", "←": "<-",
        "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "η": "eta",
        "θ": "theta", "κ": "kappa", "λ": "lambda", "μ": "mu", "π": "pi", "ρ": "rho",
        "σ": "sigma", "τ": "tau", "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega",
        "Δ": "Delta", "Σ": "Sigma", "Ω": "Omega", "∞": "infinity", "√": "sqrt",
        "∑": "sum", "∈": " in ", "∼": "~", "≪": "<<", "≫": ">>", "⇒": "=>", "∆": "Delta",
        "\u0302": "",  # combining circumflex (a hat on a Greek letter)
    }.items()},
    **{chr(0x2080 + i): f"_{i}" for i in range(10)},          # subscript digits
    **{"⁰": "^0", "¹": "^1", "²": "^2", "³": "^3", "⁴": "^4", "⁵": "^5",
       "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9"},
}


def _symbol_safe(md: str) -> str:
    return "".join(_SYMBOL_FALLBACKS.get(ch, ch) for ch in md)


def _ascii_safe(md: str) -> str:
    out = []
    for ch in md:
        if ch in _ASCII_FALLBACKS:
            out.append(_ASCII_FALLBACKS[ch])
        elif ord(ch) < 0x100 or ch in "\n\t":
            out.append(ch)
        else:
            out.append("?")
    return "".join(out)


def _run_pandoc(md: str, engine: str) -> Optional[bytes]:
    with tempfile.TemporaryDirectory() as d:
        workdir = Path(d)
        src = workdir / "report.md"
        out = workdir / "report.pdf"
        src.write_text(md, encoding="utf-8")
        cmd = [
            "pandoc", str(src), "-f", "gfm", "-o", str(out),
            "--standalone", "--wrap=none",
            f"--pdf-engine={engine}",
            "--pdf-engine-opt=-no-shell-escape",
            "-V", "geometry:margin=1in",
            "-V", "fontsize=11pt",
        ]
        proc = subprocess.run(
            cmd, cwd=workdir, capture_output=True, text=True,
            timeout=RENDER_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0 or not out.exists():
            # stderr can echo report text, so only the exit code is logged.
            logger.warning("report PDF render failed: engine=%s rc=%s", engine, proc.returncode)
            return None
        data = out.read_bytes()
        return data if data.startswith(b"%PDF-") else None


def render_report_pdf(result_md: str) -> Optional[bytes]:
    """Markdown report -> PDF bytes, or None if it cannot be rendered."""
    if not result_md or not isinstance(result_md, str):
        return None
    md = result_md[:MAX_REPORT_MD_CHARS]
    for engine, text in (("xelatex", _symbol_safe(md)), ("pdflatex", _ascii_safe(_symbol_safe(md)))):
        try:
            pdf = _run_pandoc(text, engine)
        except subprocess.TimeoutExpired:
            logger.warning("report PDF render timed out: engine=%s", engine)
            continue
        except (OSError, RuntimeError):
            logger.warning("report PDF render could not start: engine=%s", engine)
            continue
        if pdf:
            return pdf
    return None
