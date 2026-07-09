"""Typeset the red-teamed guide text into a PDF via the existing LaTeX
toolchain. This repo has no WeasyPrint/reportlab dependency, so a one-off
guide reuses the same latexmk-subprocess path the manuscript tools already
rely on (backend/latextools/runner.py)."""
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
}


def _escape_latex(text: str) -> str:
    return "".join(_LATEX_SPECIAL_CHARS.get(ch, ch) for ch in text)


def _body_to_latex(text: str) -> str:
    """Convert the guide's "## Heading" plain-text format into LaTeX,
    escaping everything else. Blank lines become paragraph breaks."""
    lines = []
    for line in text.splitlines():
        if line.startswith("## "):
            lines.append(f"\\section*{{{_escape_latex(line[3:].strip())}}}")
        elif line.strip() == "":
            lines.append("")
        else:
            lines.append(_escape_latex(line))
    return "\n".join(lines)


_TEX_TEMPLATE = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=1in]{geometry}
\usepackage{parskip}
\title{Preserving Lean Mass on GLP-1 Therapy}
\author{MuscleOnGLP}
\date{}
\begin{document}
\maketitle
%s
\end{document}
"""


def render_guide_pdf(text: str, output_path: Path) -> Path:
    """Typeset *text* (the "## "-headed guide format) into a PDF at
    *output_path*. Raises RuntimeError if the LaTeX compile fails."""
    tex_source = _TEX_TEMPLATE % _body_to_latex(text)
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        result = runner.run_compile(workdir, tex_source, ENGINE, COMPILE_TIMEOUT_SECONDS)
        if not result.ok:
            raise RuntimeError(f"Guide PDF compile failed: {result.errors or result.log}")
        output_path.write_bytes(result.pdf_bytes)
    return output_path
