"""Plain-language explanations for LaTeX errors and warnings.

Used by the LaTeX compile app (compile_server.py) for every error a compile returns, and on its own by the
explain_latex_error tool for a message someone pastes. Pure Python, no TeX needed. Where purplelink.llc has a
guide page for an error (site/latex-errors/<slug>/), the explanation links to it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

SITE = "https://purplelink.llc"
UTM = "?utm_source=latex-app&utm_medium=app&utm_campaign=compile"


@dataclass(frozen=True)
class Rule:
    slug: str
    pattern: re.Pattern
    title: str
    explanation: str
    fix: str
    has_page: bool = False


def _r(slug, pattern, title, explanation, fix, has_page=False) -> Rule:
    return Rule(slug, re.compile(pattern, re.IGNORECASE), title, explanation, fix, has_page)


# Ordered: the first match wins, so specific patterns come before general ones. "@1@" is replaced with the
# first captured group (a file, environment or key name); braces are literal LaTeX.
RULES: list[Rule] = [
    _r("file-not-found", r"File [`'\"]?([^'`\"]+?)['\"]? not found",
       "File not found",
       "LaTeX could not find the file @1@. A .sty or .cls name means a package or document class that is not "
       "installed. Any other name is a file the document reads (an image, an \\input chapter, a .bib) that is not "
       "available.",
       "Check the spelling of the name. For a missing package, look for an installed alternative. This compiler "
       "receives one .tex file and an optional bibliography, so remove \\includegraphics and \\input of other files, "
       "or use \\usepackage[demo]{graphicx} to draw boxes in place of images.",
       has_page=True),
    _r("environment-undefined", r"Environment (\S+?) undefined",
       "Environment undefined",
       "\\begin{@1@} names an environment that no loaded package defines. It is usually a typo, or the "
       "package that provides it (for example amsmath for align) is not loaded.",
       "Check the spelling, or add the \\usepackage line for the package that defines @1@.",
       has_page=True),
    _r("missing-begin-document", r"Missing \\begin\{document\}",
       "Missing \\begin{document}",
       "Text or a stray character appears before \\begin{document}, where only setup commands may go, or the "
       "line \\begin{document} is missing.",
       "Move any text below \\begin{document}, and check the preamble for a stray character or a command typed "
       "without its backslash.",
       has_page=True),
    _r("missing-dollar-inserted", r"Missing \$ inserted",
       "Missing $ inserted",
       "A symbol that only works in math mode (^, _, \\alpha, \\sum) is used in ordinary text, or a math "
       "expression was opened and not closed.",
       "Wrap the expression in $...$. In ordinary text, write an underscore as \\_ and a caret as \\^{}.",
       has_page=True),
    _r("extra-alignment-tab", r"Extra alignment tab has been changed",
       "Extra alignment tab",
       "A table row has more & separators than the column specification allows, so it has too many cells.",
       "Count the columns in \\begin{tabular}{...} and the & in each row: a row with n columns has n-1 of them.",
       has_page=True),
    _r("misplaced-alignment-tab", r"Misplaced alignment tab character",
       "Misplaced alignment tab &",
       "An & appears outside a table or alignment, where LaTeX does not expect a column separator.",
       "In ordinary text, write \\& for an ampersand.",
       has_page=True),
    _r("paragraph-ended-before-complete", r"Paragraph ended before (\S+?) was complete",
       "Paragraph ended before a command was complete",
       "The argument of @1@ contains a blank line, which LaTeX reads as a paragraph break inside it. Usually a "
       "closing } is missing.",
       "Find the { that opens the argument of @1@ and add its closing }, or remove the blank line inside it.",
       has_page=True),
    _r("runaway-argument", r"Runaway argument",
       "Runaway argument",
       "A command's argument was opened with { and never closed, so LaTeX read on until it gave up.",
       "Look just before the reported line for a { without its matching }.",
       has_page=True),
    _r("too-many-closing-braces", r"Too many \}'?s",
       "Too many closing braces",
       "There is a } with no { to match it.",
       "Remove the extra }, or add the { it was meant to close.",
       has_page=True),
    _r("unicode-character", r"Unicode character (.+?) not set up for use with LaTeX|Package inputenc Error",
       "Unicode character not supported",
       "The document contains a character (often a smart quote, a dash pasted from a word processor, or a "
       "non-Latin letter) that pdfLaTeX cannot typeset with the loaded fonts.",
       "Compile with engine xelatex, which handles Unicode, or replace the character with its LaTeX form."),
    _r("option-clash", r"Option clash for package (\S+)",
       "Option clash",
       "The package @1@ is loaded twice with different options, or the document class loads it first with other "
       "options.",
       "Load @1@ once, with all the options together, or pass them earlier with \\PassOptionsToPackage."),
    _r("double-script", r"Double (?:superscript|subscript)",
       "Double superscript or subscript",
       "Two ^ or two _ apply to the same base, as in x^2^3, which LaTeX cannot read.",
       "Group with braces: x^{2^3} or {x^2}^3."),
    _r("missing-brace-inserted", r"Missing \} inserted",
       "Missing } inserted",
       "A group or math expression was closed in the wrong place, often a $ or } inside a command argument.",
       "Check the braces and $ signs on the reported line and the line above it."),
    _r("preamble-only", r"Can be used only in preamble",
       "Command only allowed in the preamble",
       "A command such as \\usepackage appears after \\begin{document}.",
       "Move the command above \\begin{document}."),
    _r("undefined-control-sequence", r"Undefined control sequence",
       "Undefined control sequence",
       "A command on this line is not defined. It is usually a typo (\\begn for \\begin), or a command from a "
       "package that is not loaded.",
       "Check the spelling of the commands on the line. If it is spelled correctly, add the \\usepackage line for "
       "the package that defines it.",
       has_page=True),
    _r("emergency-stop", r"Emergency stop",
       "Emergency stop",
       "LaTeX stopped at the first error. The real cause is the error reported just before this one.",
       "Fix the earlier error and compile again."),
]

WARNING_RULES: list[Rule] = [
    _r("citation-undefined", r"Citation [`']([^']+)' (?:on page \S+ )?undefined",
       "Citation undefined",
       "\\cite{@1@} has no matching entry in the bibliography, so it prints as [?].",
       "Pass the .bib contents in the bibliography parameter, and check that the key @1@ is spelled the same in "
       "both places.",
       has_page=True),
    _r("reference-undefined", r"Reference [`']([^']+)' (?:on page \S+ )?undefined",
       "Reference undefined",
       "\\ref{@1@} points to a \\label that does not exist, so it prints as ??.",
       "Add \\label{@1@} after the figure, table or section, or fix the spelling in \\ref."),
    _r("overfull-hbox", r"Overfull \\hbox",
       "Overfull hbox",
       "A line is wider than the text block and sticks into the margin, usually because of a long word, URL or "
       "table that LaTeX cannot break. The PDF is still produced.",
       "Rephrase, allow a break (for URLs, \\usepackage{xurl}), or shrink the table.",
       has_page=True),
]


def _fill(text: str, m: re.Match) -> str:
    groups = [g for g in m.groups() if g is not None]
    return text.replace("@1@", groups[0].strip() if groups else "it")


def learn_more(rule: Rule) -> Optional[str]:
    return f"{SITE}/latex-errors/{rule.slug}/{UTM}" if rule.has_page else None


def explain(message: str, warnings: bool = False) -> Optional[dict]:
    """Explanation for one error (or, with warnings=True, warning) message; None when nothing matches."""
    for rule in (WARNING_RULES if warnings else RULES):
        m = rule.pattern.search(message or "")
        if m:
            return {
                "kind": rule.slug,
                "title": rule.title,
                "explanation": _fill(rule.explanation, m),
                "fix": _fill(rule.fix, m),
                "learn_more": learn_more(rule),
            }
    return None


def explain_any(message: str) -> Optional[dict]:
    """Errors first, then warnings: for a pasted message whose kind is unknown."""
    return explain(message) or explain(message, warnings=True)


_WARNING_LINE = re.compile(r"^(?:LaTeX|Package \w+) Warning: (.+)$|^(Overfull \\hbox.*)$")


def warnings_from_log(log: str, limit: int = 20) -> list[dict]:
    """Distinct explained warnings from a TeX log (undefined citations and references, overfull lines)."""
    out: list[dict] = []
    seen: set[str] = set()
    overfull = 0
    for raw in (log or "").splitlines():
        m = _WARNING_LINE.match(raw.strip())
        if not m:
            continue
        msg = (m.group(1) or m.group(2) or "").strip()
        if msg.startswith("Overfull"):
            overfull += 1
            continue
        ex = explain(msg, warnings=True)
        if ex and msg not in seen:
            seen.add(msg)
            out.append({"message": msg, **ex})
        if len(out) >= limit:
            break
    if overfull:
        ex = explain("Overfull \\hbox", warnings=True)
        out.append({"message": f"{overfull} overfull line(s)", **ex})
    return out
