"""Typeset the red-teamed guide text into a PDF via the existing LaTeX
toolchain. This repo has no WeasyPrint/reportlab dependency, so a one-off
guide reuses the same latexmk-subprocess path the manuscript tools already
rely on (backend/latextools/runner.py)."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from latextools import runner

ENGINE = "pdflatex"
COMPILE_TIMEOUT_SECONDS = 60

_LATEX_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    # Unicode punctuation / math symbols that pdflatex + inputenc(utf8) does not
    # set up by default. Auto-generated scientific text (copied from paper data)
    # routinely contains these, so map them to LaTeX-safe equivalents rather than
    # let one stray glyph fail the whole compile.
    "−": "-",            # minus sign − (the crash: "-14.9%")
    "‐": "-",            # hyphen ‐
    "‑": "-",            # non-breaking hyphen
    "–": "--",           # en dash –
    "—": "---",          # em dash —
    "‘": "`",            # left single quote ‘
    "’": "'",            # right single quote / apostrophe ’
    "“": "``",           # left double quote “
    "”": "''",           # right double quote ”
    "…": r"\ldots{}",    # ellipsis …
    " ": " ",            # non-breaking space
    "×": r"$\times$",    # multiplication ×
    "±": r"$\pm$",       # plus-minus ±
    "≈": r"$\approx$",   # ≈
    "≤": r"$\leq$",      # ≤
    "≥": r"$\geq$",      # ≥
    "→": r"$\rightarrow$",  # →
    "°": r"\textdegree{}",  # degree °
    "µ": r"$\mu$",       # micro sign µ
    "μ": r"$\mu$",       # Greek mu μ
}


def _escape_latex(text: str) -> str:
    # Drop C0 control characters (U+0000-U+001F) — they have no place in the
    # guide text and pdflatex aborts on them ("Unicode character ^^[").
    return "".join(
        _LATEX_SPECIAL_CHARS.get(ch, "" if ord(ch) < 0x20 else ch) for ch in text
    )


_DISCLAIMER_RE = re.compile(r"medical advice|disclaimer|not medical", re.I)


def _body_to_latex(text: str) -> str:
    """Convert the guide's "## Heading" plain-text format into LaTeX, escaping
    everything else. Blank lines become paragraph breaks. The closing
    medical-disclaimer section is rendered in a soft green callout box instead
    of a plain heading, so it reads like a newsletter sidebar."""
    out: list[str] = []
    in_disclaimer = False
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            if not in_disclaimer and _DISCLAIMER_RE.search(heading):
                out.append(r"\bigskip\noindent\colorbox{tint}{\begin{minipage}"
                           r"{\dimexpr\textwidth-2\fboxsep\relax}\vspace{5pt}")
                out.append(r"{\color{brand}\bfseries " + _escape_latex(heading)
                           + r"}\par\vspace{3pt}\small")
                in_disclaimer = True
                continue
            out.append(f"\\section*{{{_escape_latex(heading)}}}")
        elif line.strip() == "":
            out.append("")
        else:
            out.append(_escape_latex(line))
    if in_disclaimer:
        out.append(r"\vspace{5pt}\end{minipage}}")
    return "\n".join(out)


def _references_to_latex(references) -> str:
    """Render the month's papers as a 'The Research This Month' section:
    each keyed (p1, p2, ...) with its title, journal/meta, and a link.
    *references* is a list of (key, title, meta, url) tuples; empty -> ''."""
    if not references:
        return ""
    parts = [r"\section*{The Research This Month}"]
    for key, title, meta, url in references:
        entry = (r"\noindent{\color{brand}\bfseries (" + _escape_latex(key) + r")}~ "
                 + _escape_latex(title))
        if meta:
            entry += r".\ {\color{softink}\small " + _escape_latex(meta) + r"}"
        if url:
            safe = url.replace("%", r"\%").replace("#", r"\#")
            entry += r"\ {\small\href{" + safe + r"}{\color{bright}Read the paper $\rightarrow$}}"
        parts.append(entry + r"\par\vspace{7pt}")
    return "\n".join(parts)


# A calm, green, fitness-newsletter look (not an academic paper): sans-serif
# body, a brand-green masthead, green section headings with a bright rule, and a
# branded footer. Only packages present in the Modal image's TeX Live set
# (latex-recommended + extra + fonts-recommended) are used. Placeholders are
# substituted with str.replace (not %-formatting) so LaTeX comments/% survive.
_TEX_TEMPLATE = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=0.85in,top=0.7in,bottom=1in]{geometry}
\usepackage{xcolor}
\usepackage{helvet}
\renewcommand{\familydefault}{\sfdefault}
\usepackage{microtype}
\usepackage{parskip}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{hyperref}

\definecolor{brand}{HTML}{2F6F5E}
\definecolor{bright}{HTML}{34A07F}
\definecolor{tint}{HTML}{E7F1EE}
\definecolor{ink}{HTML}{1B2420}
\definecolor{softink}{HTML}{45524C}
\color{ink}
\hypersetup{colorlinks=true, urlcolor=bright, linkcolor=brand}

\titleformat{\section}{\color{brand}\large\bfseries}{}{0pt}{}[{\color{bright}\vspace{2pt}\titlerule[1.1pt]}]
\titlespacing*{\section}{0pt}{18pt}{6pt}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\fancyfoot[L]{\footnotesize\color{softink}\textbf{MuscleOnGLP}\quad getmuscleonglp.com}
\fancyfoot[C]{\footnotesize\color{softink}Educational, not medical advice}
\fancyfoot[R]{\footnotesize\color{softink}\thepage}

\setlength{\parskip}{7pt}
\linespread{1.06}

\begin{document}
\thispagestyle{fancy}

\noindent\colorbox{brand}{\begin{minipage}[t]{\dimexpr\textwidth-2\fboxsep\relax}
\vspace{7pt}
{\color{tint}\footnotesize\bfseries MUSCLEONGLP \textbullet\ MONTHLY RESEARCH REVIEW}\\[5pt]
{\color{white}\LARGE\bfseries __TITLE__}\\[4pt]
{\color{tint}\small __SUBTITLE__}
\vspace{9pt}
\end{minipage}}

\vspace{-2pt}\noindent{\color{bright}\rule{\textwidth}{2.5pt}}

\vspace{14pt}

__BODY__

__REFERENCES__

\end{document}
"""


def render_guide_pdf(text: str, output_path: Path,
                     title: str | None = None, subtitle: str | None = None,
                     references=None) -> Path:
    """Typeset *text* (the "## "-headed guide format) into a PDF at
    *output_path*. *title*/*subtitle* fill the masthead (default to the flagship
    guide's titling for backward compatibility). *references*, if given, is a
    list of (key, title, meta, url) tuples rendered as a linked
    'The Research This Month' section. Raises RuntimeError if the compile fails."""
    title = title or "Preserving Lean Mass on GLP-1 Therapy"
    subtitle = subtitle or "A resistance-training and protein protocol"
    tex_source = (
        _TEX_TEMPLATE
        .replace("__TITLE__", _escape_latex(title))
        .replace("__SUBTITLE__", _escape_latex(subtitle))
        .replace("__BODY__", _body_to_latex(text))
        .replace("__REFERENCES__", _references_to_latex(references))
    )
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        result = runner.run_compile(workdir, tex_source, ENGINE, COMPILE_TIMEOUT_SECONDS)
        if not result.ok:
            raise RuntimeError(f"Guide PDF compile failed: {result.errors or result.log}")
        output_path.write_bytes(result.pdf_bytes)
    return output_path
