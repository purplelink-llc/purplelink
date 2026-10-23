"""Manuscript coherence check: does the paper agree with itself?

Builds a "Paper Bible" (the research questions, hypotheses, construct definitions, theories, samples, key
numbers, claimed and delivered contributions, limitations and citation uses that each section states) and
then checks the sections against one another: a construct defined two ways, an abstract number the results
do not report, a hypothesis stated but never tested, a theory introduced and never used, a contribution
promised in the introduction and not delivered, a research question left unanswered, term drift, a
limitation that contradicts a claim, one source cited for incompatible claims.

Three stages, cheapest first:

  1. Rules (no model): hypothesis and research-question labels across sections, acronyms expanded two
     ways, abstract numbers missing from the body. Runs on its own as the free sample.
  2. Extraction (model, per chunk of sections): the Paper Bible. Every item carries a verbatim quote,
     checked against the text in code; an item whose quote is not found is dropped.
  3. Cross-check (model, on the Bible only) and verification (model, on the full text): findings must
     point at Bible item ids, so every quote in the report comes from a checked item, never from the
     model's free text. The verifier then drops findings the text resolves.

Input: .tex (a tolerant stripper; pandoc fails on many real preambles), .docx (pandoc to markdown) or
.pdf (papercheck.extract_paper). Nothing is stored here: the caller holds the manuscript in memory and
log lines carry counts only.

Feature flags (both off unless set to "1"): COHERENCE_CHECK_ENABLED for the internal endpoint,
COHERENCE_IN_REVIEW to append the report to paid Paper Review results.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from latextools import safety as _safety
from latextools.papercheck import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    _call_json_findings,
    _norm_for_match,
)

logger = logging.getLogger(__name__)

# Extraction is reading, not judging, so it defaults to the cheaper model; the cross-check and the verifier
# decide what the author sees and stay on DEFAULT_MODEL. Both can be moved from the Modal secret.
EXTRACT_MODEL = os.environ.get("COHERENCE_EXTRACT_MODEL", "claude-sonnet-5-5")
CHECK_MODEL = os.environ.get("COHERENCE_CHECK_MODEL", DEFAULT_MODEL)
EFFORT = os.environ.get("COHERENCE_EFFORT", DEFAULT_EFFORT or "") or None

MAX_INPUT_CHARS = 160_000          # about 45k tokens: a long IS paper with tables; appendices are cut first
CHUNK_CHARS = 14_000               # one extraction call; sections are never split across calls
EXTRACT_CONCURRENCY = 4
EXTRACT_MAX_OUTPUT_TOKENS = 16_000
CHECK_MAX_OUTPUT_TOKENS = 16_000
VERIFY_MAX_OUTPUT_TOKENS = 12_000
MAX_QUOTE_WORDS = 25
MAX_FINDINGS = 25
PANDOC_TIMEOUT_SECONDS = 60

CHECK_TYPES = {
    "construct_definition_conflict": "A construct or key term is defined or operationalised in two incompatible ways.",
    "abstract_results_mismatch": "A number or result in the abstract differs from, or is missing in, the body.",
    "hypothesis_untested": "A hypothesis is stated but never tested or reported.",
    "hypothesis_undeclared": "A hypothesis is reported in the results but never stated beforehand.",
    "research_question_unanswered": "A research question is posed but never answered.",
    "theory_unused": "A theory is introduced as a lens but never used to derive, explain or interpret anything.",
    "contribution_undelivered": "A contribution claimed early is not delivered or discussed later.",
    "term_drift": "The same concept is named differently across sections, or one name shifts meaning.",
    "limitation_contradicts_claim": "A limitation undercuts a claim made elsewhere without the claim being qualified.",
    "sample_inconsistency": "Sample size, period or composition is reported differently in different places.",
    "citation_role_conflict": "One source is cited for incompatible claims.",
    "acronym_conflict": "An acronym is expanded two different ways.",
    "label_gap": "A numbered sequence of hypotheses or research questions skips a number.",
}

TYPE_TITLES = {
    "construct_definition_conflict": "A construct is defined two ways",
    "abstract_results_mismatch": "The abstract and the body disagree",
    "hypothesis_untested": "A hypothesis is stated but never reported",
    "hypothesis_undeclared": "A hypothesis is reported but never stated",
    "research_question_unanswered": "A research question is not answered",
    "theory_unused": "A theory is introduced and not used",
    "contribution_undelivered": "A promised contribution is not delivered",
    "term_drift": "A term drifts between sections",
    "limitation_contradicts_claim": "A limitation contradicts a claim",
    "sample_inconsistency": "The sample is described inconsistently",
    "citation_role_conflict": "One source is cited for conflicting claims",
    "acronym_conflict": "An acronym has two expansions",
    "label_gap": "A numbered label is missing",
}

CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def check_enabled() -> bool:
    return os.environ.get("COHERENCE_CHECK_ENABLED", "") == "1"


def in_review_enabled() -> bool:
    return os.environ.get("COHERENCE_IN_REVIEW", "") == "1"


# ---------------------------------------------------------------------------
# Manuscript model
# ---------------------------------------------------------------------------

@dataclass
class Section:
    id: str
    title: str
    level: int
    text: str
    role: str = "other"

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "level": self.level, "role": self.role, "chars": len(self.text)}


@dataclass
class Manuscript:
    title: str = ""
    abstract: str = ""
    sections: list[Section] = field(default_factory=list)
    source_kind: str = ""
    truncated: bool = False

    def body_text(self) -> str:
        return "\n\n".join(s.text for s in self.sections if s.role not in ("abstract", "references"))

    def section(self, sid: str) -> Optional[Section]:
        return next((s for s in self.sections if s.id == sid), None)


# Order matters: the first pattern that matches a title wins.
_ROLE_PATTERNS = [
    ("abstract", r"^abstract$|^summary$"),
    ("references", r"^references?$|bibliograph|works cited|literature cited"),
    ("appendix", r"appendi|supplement|online resource"),
    ("acknowledgements", r"acknowledg"),
    ("limitations", r"limitation|future (research|work|directions)"),
    ("conclusion", r"conclu"),
    ("discussion", r"discussion|implication|contribution|design principle|lessons"),
    ("introduction", r"introduction|^background$|motivation"),
    ("theory", r"theor|hypothes|research model|conceptual|framework|propositions?"),
    ("literature", r"literature|related work|prior (work|research)|research gaps?|background"),
    ("results", r"result|finding|ablation|robustness|benchmark|comparison|experiments? \d|study \d|analysis"),
    ("method", r"method|research design|data|design|procedure|sample|measure|experiment|setup|"
               r"pre-?processing|architecture|operationali|participants|evaluation|implementation"),
]
_EARLY_ROLES = {"introduction", "literature", "theory", "method"}
_LATE_ROLES = {"results", "discussion", "limitations", "conclusion"}
# A subsection takes its parent's role unless its own title names one of these.
_OVERRIDING_ROLES = {"limitations", "theory", "conclusion", "abstract", "references", "appendix"}


def classify_title(title: str) -> str:
    t = re.sub(r"[^a-z0-9 -]+", " ", title.lower()).strip()
    t = re.sub(r"\s+", " ", t)
    for role, pat in _ROLE_PATTERNS:
        if re.search(pat, t):
            return role
    return "other"


def assign_roles(sections: list[Section]) -> None:
    parents: dict[int, str] = {}
    for s in sections:
        own = classify_title(s.title)
        parent_role = next((parents[l] for l in sorted(parents, reverse=True) if l < s.level), None)
        if s.level > 1 and parent_role and parent_role != "other" and own not in _OVERRIDING_ROLES:
            s.role = parent_role
        else:
            s.role = own
        parents = {l: r for l, r in parents.items() if l < s.level}
        parents[s.level] = s.role
    # A "Hypotheses" heading after the results began holds the hypothesis-test table (common in PLS-SEM
    # papers), so it reports results rather than stating hypotheses.
    seen_results = False
    for s in sections:
        if s.role == "results":
            seen_results = True
        elif seen_results and s.role == "theory":
            s.role = "results"


def _number_sections(raw: list[tuple[str, int, str]]) -> list[Section]:
    # Roles are assigned before empty headings are dropped, so the subsections of an empty "Discussion"
    # heading still inherit its role.
    allsecs = [Section(id="", title=t.strip() or "(untitled)", level=l, text=x.strip()) for t, l, x in raw]
    assign_roles(allsecs)
    out = [s for s in allsecs if s.text]
    for i, s in enumerate(out):
        s.id = f"S{i + 1}"
    return out


def _cap(ms: Manuscript) -> Manuscript:
    """Keep the model input bounded: drop references, then cut appendices, then trim from the end."""
    ms.sections = [s for s in ms.sections if s.role != "references"]
    total = sum(len(s.text) for s in ms.sections)
    if total <= MAX_INPUT_CHARS:
        return ms
    ms.truncated = True
    order = {s.id: i for i, s in enumerate(ms.sections)}
    keep: list[Section] = []
    budget = MAX_INPUT_CHARS
    for s in sorted(ms.sections, key=lambda s: (s.role == "appendix", order[s.id])):
        if budget <= 0:
            break
        if len(s.text) > budget:
            s.text = s.text[:budget]
        budget -= len(s.text)
        keep.append(s)
    ms.sections = sorted(keep, key=lambda s: order[s.id])
    return ms


# ---------------------------------------------------------------------------
# Input: LaTeX
# ---------------------------------------------------------------------------

_SECTION_LEVELS = {"part": 1, "chapter": 1, "section": 1, "subsection": 2, "subsubsection": 3}
_CITE_CMDS = ("cite", "citep", "citet", "citealp", "citeauthor", "citeyear", "parencite", "textcite",
              "autocite", "footcite", "nocite", "citeyearpar")
_REF_CMDS = ("ref", "autoref", "cref", "Cref", "eqref", "pageref", "nameref")
# Commands whose arguments are layout or setup, not prose: removed with this many brace groups.
# multicolumn and multirow keep their last argument (the cell text), so it is not counted.
_DROP_CMDS = {
    "label": 1, "vspace": 1, "hspace": 1, "setcounter": 2, "addtocounter": 2, "setlength": 2,
    "includegraphics": 1, "usepackage": 1, "documentclass": 1, "bibliographystyle": 1, "bibliography": 1,
    "newcommand": 2, "renewcommand": 2, "providecommand": 2, "newenvironment": 3, "renewenvironment": 3,
    "newcolumntype": 2, "definecolor": 3, "fontsize": 2, "newtheorem": 2,
    "addbibresource": 1, "input": 1, "include": 1, "graphicspath": 1, "pagestyle": 1, "thispagestyle": 1,
    "multicolumn": 2, "multirow": 2, "cline": 1, "cmidrule": 1, "rule": 2, "resizebox": 2, "scalebox": 1,
    "color": 1, "textcolor": 1, "rowcolor": 1, "cellcolor": 1, "hypersetup": 1, "geometry": 1,
    "linespread": 1, "setstretch": 1, "enlargethispage": 1, "titleformat": 2, "captionsetup": 1,
}
_BARE_CMDS = {
    "hline", "toprule", "midrule", "bottomrule", "centering", "noindent", "newpage", "clearpage", "par",
    "small", "footnotesize", "scriptsize", "large", "Large", "LARGE", "normalsize", "tiny", "huge", "Huge",
    "bfseries", "itshape", "raggedright", "justifying", "doublespacing", "singlespacing", "onehalfspacing",
    "vfill", "hfill", "bigskip", "medskip", "smallskip", "linewidth", "textwidth", "columnwidth",
    "arraybackslash", "tableofcontents", "maketitle", "makeatletter", "makeatother", "selectfont", "appendix",
}
_DROP_ENVS = ("tikzpicture", "comment", "verbatim", "lstlisting", "minted", "thebibliography")


def _read_group(text: str, i: int, open_ch: str = "{", close_ch: str = "}") -> tuple[str, int]:
    """Read a balanced group starting at text[i] == open_ch. Returns (inner, index after the close)."""
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    return text[i + 1:], len(text)


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\n":
        i += 1
    return i


def _strip_comments(src: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in src.split("\n"))


def _find_command_arg(src: str, name: str) -> str:
    m = re.search(r"\\" + name + r"\*?\s*(\[[^\]]*\])?\s*\{", src)
    if not m:
        return ""
    inner, _ = _read_group(src, m.end() - 1)
    return inner


def _env_body(src: str, env: str) -> tuple[str, str]:
    """Return (body of the first `env` environment, src with that environment removed)."""
    m = re.search(r"\\begin\{" + env + r"\}(.*?)\\end\{" + env + r"\}", src, re.S)
    if not m:
        return "", src
    return m.group(1), src[:m.start()] + src[m.end():]


def latex_to_plain(src: str) -> str:
    """Strip LaTeX markup to prose, keeping citations as [cite: keys], cross-references as [ref: label],
    table cells separated by |, list items as lines, and section markers as lines of the form
    NUL<level>NUL<title>. Tolerant by design: an unknown command loses its name and keeps its text."""
    s = src
    for env in _DROP_ENVS:
        s = re.sub(r"\\begin\{" + env + r"\*?\}.*?\\end\{" + env + r"\*?\}", " ", s, flags=re.S)
    s = re.sub(r"\\begin\{(equation|align|gather|multline|eqnarray|displaymath)(\*?)\}.*?\\end\{\1\2\}",
               " [equation] ", s, flags=re.S)
    s = re.sub(r"\\\[.*?\\\]", " [equation] ", s, flags=re.S)
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        m = re.match(r"\\([A-Za-z@]+)(\*?)", s[i:i + 60])
        if not m:
            nxt = s[i + 1:i + 2]
            i += 2
            if nxt == "\\":
                out.append("\n")
                j = _skip_ws(s, i)
                if j < n and s[j] == "[":      # \\[4pt]
                    _, i = _read_group(s, j, "[", "]")
            elif nxt in "%&$#_{}~^":
                out.append(nxt if nxt != "&" else "and")
            elif nxt in ", ;:!":
                out.append(" ")
            continue
        name = m.group(1)
        i += m.end()
        j = _skip_ws(s, i)
        opt = ""
        if j < n and s[j] == "[" and name != "item":
            opt, j = _read_group(s, j, "[", "]")
        if name in _SECTION_LEVELS or name == "paragraph":
            j = _skip_ws(s, j)
            title = ""
            if j < n and s[j] == "{":
                title, j = _read_group(s, j)
            title = latex_to_plain(title).strip()
            if name == "paragraph":
                out.append("\n" + title + " ")
            else:
                out.append(f"\n\x00{_SECTION_LEVELS[name]}\x00{title}\n")
            i = j
        elif name in _CITE_CMDS:
            j = _skip_ws(s, j)
            if j < n and s[j] == "[":
                _, j = _read_group(s, j, "[", "]")
            keys = ""
            if j < n and s[j] == "{":
                keys, j = _read_group(s, j)
            out.append("[cite: " + ", ".join(k.strip() for k in keys.split(",") if k.strip()) + "]")
            i = j
        elif name in _REF_CMDS:
            label = ""
            if j < n and s[j] == "{":
                label, j = _read_group(s, j)
            out.append(f"[ref: {label.strip()}]")
            i = j
        elif name in _DROP_CMDS:
            for _ in range(_DROP_CMDS[name]):
                j = _skip_ws(s, j)
                if j < n and s[j] == "[":          # \newcolumntype{P}[1]{...}
                    _, j = _read_group(s, j, "[", "]")
                    j = _skip_ws(s, j)
                if j < n and s[j] == "{":
                    _, j = _read_group(s, j)
            i = j
        elif name in ("begin", "end"):
            env = ""
            if j < n and s[j] == "{":
                env, j = _read_group(s, j)
            k = _skip_ws(s, j)
            if name == "begin" and k < n and s[k] == "[":      # \begin{table}[htbp]
                _, j = _read_group(s, k, "[", "]")
            if name == "begin" and env.startswith(("tabular", "longtable", "array")):
                # the column spec (and tabularx's width) are not prose
                for _ in range(2 if env.startswith("tabularx") else 1):
                    j = _skip_ws(s, j)
                    if j < n and s[j] == "{":
                        _, j = _read_group(s, j)
            out.append("\n")
            i = j
        elif name == "item":
            out.append("\n- ")
            i = j
        elif name in _BARE_CMDS or name in ("def", "let"):
            i = j
        elif name in ("ldots", "dots", "cdots"):
            out.append("...")
            i = j
        elif name == "times":
            out.append("x")
            i = j
        else:
            # A formatting or unknown command (\textbf, \emph, \caption, \footnote, \url ...): keep its text.
            if name in ("quad", "qquad"):
                out.append(" ")
            if opt:
                i = j
    t = "".join(out)
    t = t.replace("&", " | ").replace("{", "").replace("}", "").replace("~", " ")
    t = t.replace("``", "\u201c").replace("''", "\u201d").replace("$", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def from_latex(src: str) -> Manuscript:
    src = _strip_comments(src)
    title = latex_to_plain(_find_command_arg(src, "title"))
    m = re.search(r"\\begin\{document\}(.*?)(?:\\end\{document\}|$)", src, re.S)
    body = m.group(1) if m else src
    abstract_src, body = _env_body(body, "abstract")
    abstract = latex_to_plain(abstract_src)
    body = re.sub(r"\\appendix\b", lambda _m: "\n\\section{Appendix}\n", body)
    plain = latex_to_plain(body)
    raw: list[tuple[str, int, str]] = []
    if abstract:
        raw.append(("Abstract", 1, abstract))
    parts = re.split(r"\x00(\d)\x00([^\n]*)\n", plain)
    preamble = parts[0].strip()
    if len(preamble) > 400:
        raw.append(("Front matter", 1, preamble))
    for k in range(1, len(parts) - 2, 3):
        raw.append((parts[k + 1], int(parts[k]), parts[k + 2]))
    return _cap(Manuscript(title=title, abstract=abstract, sections=_number_sections(raw), source_kind="tex"))


# ---------------------------------------------------------------------------
# Input: Markdown (from .docx through pandoc) and plain text (from PDF)
# ---------------------------------------------------------------------------

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def from_markdown(md: str, title: str = "", source_kind: str = "docx") -> Manuscript:
    raw: list[tuple[str, int, str]] = []
    cur_title, cur_level, buf = "Front matter", 1, []
    for line in md.split("\n"):
        m = _MD_HEADING_RE.match(line)
        if m:
            raw.append((cur_title, cur_level, "\n".join(buf)))
            cur_title = re.sub(r"[*_`]", "", m.group(2)).strip()
            cur_level, buf = len(m.group(1)), []
        else:
            buf.append(line)
    raw.append((cur_title, cur_level, "\n".join(buf)))
    abstract = next((x.strip() for t, _, x in raw if classify_title(t) == "abstract" and x.strip()), "")
    if not abstract and raw and raw[0][0] == "Front matter":
        # Word abstracts are often a bold "Abstract" paragraph rather than a heading.
        m = re.search(r"(?im)^\W{0,3}abstract\W{0,4}\s*(\S.*?)(?:\n\s*\n|\Z)", raw[0][2], re.S)
        if m:
            abstract = m.group(1).strip()
            if len(abstract) < 200:          # heading on its own line: take the next paragraph
                rest = raw[0][2][m.end():].strip().split("\n\n")
                abstract = (abstract + " " + rest[0]).strip() if rest else abstract
            raw.insert(1, ("Abstract", 1, abstract))
    if not title and raw and raw[0][0] == "Front matter":
        title = next((l.strip("*# ") for l in raw[0][2].split("\n") if l.strip()), "")[:300]
    return _cap(Manuscript(title=title, abstract=abstract, sections=_number_sections(raw), source_kind=source_kind))


_KNOWN_HEADINGS = {
    "abstract", "introduction", "background", "literature review", "related work", "theoretical background",
    "theory", "theoretical framework", "hypotheses", "hypothesis development", "research model",
    "research model and hypotheses", "method", "methods", "methodology", "research design", "research method",
    "data", "data and methods", "materials and methods", "results", "findings", "analysis", "discussion",
    "implications", "theoretical implications", "practical implications", "contributions", "limitations",
    "limitations and future research", "future research", "conclusion", "conclusions", "references",
    "appendix", "acknowledgements", "acknowledgments", "research questions", "research gaps and questions",
}
_NUMBERED_HEADING_RE = re.compile(r"^((?:\d{1,2}\.)*\d{1,2}\.?|[IVX]{1,5}\.)\s+([A-Z][^\n]{2,90})$")


def from_plain_text(text: str, title: str = "", abstract: str = "") -> Manuscript:
    raw: list[tuple[str, int, str]] = []
    if abstract:
        raw.append(("Abstract", 1, abstract))
    cur_title, cur_level, buf = "Front matter", 1, []
    for line in text.split("\n"):
        st = line.strip()
        bare = st.lower().rstrip(":")
        lvl, name = 0, ""
        if bare in _KNOWN_HEADINGS:
            lvl, name = 1, st.rstrip(":")
        elif 3 <= len(st) <= 90 and not st.endswith((".", ",", ";", ":")):
            m = _NUMBERED_HEADING_RE.match(st)
            if (m and len(m.group(2).split()) <= 12 and not re.search(r"\d\s*$|%|\|", m.group(2))
                    and not re.search(r"[a-z]\.\s", m.group(2))):
                num = m.group(1).rstrip(".")
                lvl = num.count(".") + 1 if num[0].isdigit() else 1
                name = m.group(2).strip()
                if name.isupper():
                    name = name.capitalize()
        if lvl:
            raw.append((cur_title, cur_level, "\n".join(buf)))
            cur_title, cur_level, buf = name, lvl, []
        else:
            buf.append(line)
    raw.append((cur_title, cur_level, "\n".join(buf)))
    return _cap(Manuscript(title=title, abstract=abstract, sections=_number_sections(raw), source_kind="pdf"))


MAX_PDF_PAGES = 120
_PDF_ABSTRACT_RE = re.compile(
    r"(?is)(?:^|\n)\s*abstract[\s.:\-\u2013\u2014]*\n?(.{200,4000}?)"
    r"(?=\n\s*(?:(?:1|I)\.?\s+introduction|introduction\n|keywords|key\s*words|index terms|ccs concepts|"
    r"acm reference format|permission to make|acm isbn|\u00a9|copyright)\b)"
)


def pdf_to_text(data: bytes) -> tuple[str, str]:
    """(title, text) from a PDF with pypdf, which keeps two-column pages in reading order better than the
    word-position extractor the main review uses. Lines repeated on many pages (running heads, footers) and
    bare page numbers are removed, and words split across a line break are joined."""
    import io
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ValueError("That PDF is password-protected.")
    pages = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    counts: dict[str, int] = {}
    for pg in pages:
        for line in {l.strip() for l in pg.split("\n") if l.strip()}:
            counts[line] = counts.get(line, 0) + 1
    repeat = max(3, len(pages) // 3)
    cleaned = []
    for pg in pages:
        keep = [l for l in pg.split("\n")
                if not (counts.get(l.strip(), 0) >= repeat and len(l.strip()) < 140)
                and not re.fullmatch(r"\s*(page\s*)?\d{1,4}\s*", l, re.I)]
        cleaned.append("\n".join(keep))
    text = "\n".join(cleaned)
    text = re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)
    meta_title = ""
    try:
        meta_title = (reader.metadata.title or "").strip() if reader.metadata else ""
    except Exception:
        pass
    first = next((l.strip() for l in text.split("\n") if len(l.strip()) > 8), "")
    return (meta_title if len(meta_title) > 8 else first)[:300], text


def from_pdf(data: bytes) -> Manuscript:
    title, text = pdf_to_text(data)
    if len(text.strip()) < 500:
        raise ValueError("No text could be read from that PDF (it may be a scan).")
    abstract = ""
    m = _PDF_ABSTRACT_RE.search(text[:20_000])
    if m:
        abstract = m.group(1).strip()
        text = text[:m.start()] + "\n" + text[m.end(1):]
    return from_plain_text(text, title=title, abstract=abstract)


def _pandoc_docx_to_markdown(data: bytes) -> str:
    from latextools.docx_to_pdf import inspect_docx
    from latextools.safe_exec import minimal_env

    inspect_docx(data)
    with tempfile.TemporaryDirectory() as d:
        workdir = Path(d)
        src = workdir / "manuscript.docx"
        src.write_bytes(data)
        proc = subprocess.run(
            ["pandoc", str(src), "-f", "docx", "-t", "markdown-raw_html-native_divs-native_spans-link_attributes",
             "--sandbox", "--wrap=none"],
            cwd=workdir, capture_output=True, timeout=PANDOC_TIMEOUT_SECONDS, env=minimal_env(workdir),
        )
    if proc.returncode != 0:
        # stderr can echo document text, so only the exit code is logged.
        logger.warning("coherence docx conversion failed rc=%s", proc.returncode)
        raise ValueError("That Word file could not be read.")
    md = proc.stdout.decode("utf-8", "replace")
    return re.sub(r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?", "", md)


def load_manuscript(data: bytes, filename: str) -> Manuscript:
    """Read a .tex, .docx or .pdf manuscript into sections. Raises ValueError on an unreadable file."""
    lower = (filename or "").lower()
    if lower.endswith(".tex"):
        return from_latex(data.decode("utf-8", "replace"))
    if lower.endswith(".docx"):
        return from_markdown(_pandoc_docx_to_markdown(data))
    if lower.endswith(".pdf") or data.startswith(b"%PDF-"):
        return from_pdf(data)
    if lower.endswith((".md", ".txt")):
        return from_markdown(data.decode("utf-8", "replace"), source_kind="text")
    raise ValueError("Upload a .tex, .docx or .pdf manuscript.")


# ---------------------------------------------------------------------------
# Findings and quotes
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    type: str
    title: str
    sections: list[str]                       # section ids
    quotes: list[dict]                        # [{"section": id, "text": <= 25 words}]
    why: str
    fix: str
    confidence: str = "medium"
    source: str = "rule"                      # "rule" or "model"
    key: str = ""                             # dedupe key, e.g. "hypothesis_untested:H3"
    verifier_note: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def trim_quote(text: str, max_words: int = MAX_QUOTE_WORDS) -> str:
    words = re.sub(r"\s+", " ", text).strip().split(" ")
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + " ..."


def _sentence_around(text: str, start: int, end: int, max_words: int = MAX_QUOTE_WORDS) -> str:
    """The sentence holding text[start:end], cut to max_words around the match."""
    left = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start))
    right_candidates = [p for p in (text.find(". ", end), text.find("\n", end)) if p != -1]
    right = min(right_candidates) if right_candidates else len(text)
    sent = re.sub(r"\s+", " ", text[left + 1:right + 1]).strip()
    words = sent.split(" ")
    if len(words) <= max_words:
        return sent
    before = len(re.sub(r"\s+", " ", text[left + 1:start]).split())
    lo = max(0, min(before - max_words // 3, len(words) - max_words))
    return ("... " if lo else "") + " ".join(words[lo:lo + max_words]) + (" ..." if lo + max_words < len(words) else "")


def quote_in_text(quote: str, text: str) -> bool:
    q = _norm_for_match(quote.replace("...", " "))
    return len(q) >= 12 and q in _norm_for_match(text)


# ---------------------------------------------------------------------------
# Stage 1: rules
# ---------------------------------------------------------------------------

_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
             "eighth": 8, "ninth": 9, "tenth": 10}


def _expand_range(a: int, b: int) -> list[int]:
    return list(range(a, b + 1)) if 0 < a < b <= a + 15 else [a, b]


def _label(family: str, num: str) -> str:
    digits = re.match(r"\d+", num).group()
    return f"{family}{int(digits)}{num[len(digits):]}"


def label_mentions(text: str, family: str) -> list[tuple[str, int, int]]:
    """All mentions of hypothesis ("H") or research-question ("RQ") labels in text, as (label, start, end).
    Ranges (H1-H3, RQ1-RQ3), lists (Hypotheses 1 and 2) and ordinals (the second research question) are
    expanded. Labels are normalised to H2, H2a, RQ1."""
    out: list[tuple[str, int, int]] = []
    if family == "H":
        word = r"Hypothes[ie]s"
        # PDF text often glues words ("supportingH10", "H12was"), so a lowercase letter may touch the label
        # on either side; an uppercase letter or digit may not (H2O, H100, SH2). A "p" before it is pH.
        short = r"(?<![A-Z0-9p])H(\d{1,2})([a-z](?![a-z]))?(?![0-9A-Z])"
        rng = r"(?<![A-Z0-9p])H(\d{1,2})[a-z]?\s*(?:-|\u2013|\u2014|to|through)\s*H?(\d{1,2})(?![0-9])"
        ordinal = r"\b(" + "|".join(_ORDINALS) + r")\s+hypothesis\b"
    else:
        word = r"Research\s+Questions?"
        short = r"(?<![A-Z0-9])RQ\s?(\d{1,2})([a-z](?![a-z]))?(?![0-9A-Z])"
        rng = r"(?<![A-Z0-9])RQ\s?(\d{1,2})\s*(?:-|\u2013|\u2014|to|through)\s*(?:RQ\s?)?(\d{1,2})(?![0-9])"
        ordinal = r"\b(" + "|".join(_ORDINALS) + r")\s+research\s+question\b"
    for m in re.finditer(rng, text):
        for k in _expand_range(int(m.group(1)), int(m.group(2))):
            out.append((f"{family}{k}", m.start(), m.end()))
    for m in re.finditer(short, text):
        if family == "H" and m.group(1) == "0":
            continue
        out.append((_label(family, m.group(1) + (m.group(2) or "")), m.start(), m.end()))
    for m in re.finditer(word + r"\s+(\d{1,2}[a-z]?(?:\s*(?:,|and|&|or|-|\u2013|to)\s*\d{1,2}[a-z]?)*)", text, re.I):
        nums = re.findall(r"\d{1,2}[a-z]?", m.group(1))
        if re.search(r"\d\s*(?:-|\u2013|to)\s*\d", m.group(1)) and len(nums) == 2 and all(x.isdigit() for x in nums):
            nums = [str(k) for k in _expand_range(int(nums[0]), int(nums[1]))]
        for num in nums:
            out.append((_label(family, num), m.start(), m.end()))
    for m in re.finditer(ordinal, text, re.I):
        out.append((f"{family}{_ORDINALS[m.group(1).lower()]}", m.start(), m.end()))
    return sorted(out, key=lambda x: x[1])


def _label_base(label: str) -> str:
    return re.sub(r"[a-z]$", "", label)


def _related(a: str, b: str) -> bool:
    """H1 covers H1a and H1a covers H1 (a result reported for the parent or for one child)."""
    return a == b or _label_base(a) == b or _label_base(b) == a


def check_labels(ms: Manuscript, family: str) -> list[Finding]:
    """Hypotheses (family "H") or research questions ("RQ") stated in the early sections that no results,
    discussion or conclusion section mentions, the reverse for hypotheses, and gaps in the numbering."""
    roles = {s.role for s in ms.sections}
    if not (roles & _EARLY_ROLES) or not (roles & _LATE_ROLES):
        return []      # cannot tell where a label is stated versus tested
    mentions: dict[str, list[tuple[Section, int, int]]] = {}
    for s in ms.sections:
        if s.role in ("abstract", "references", "appendix", "other", "acknowledgements"):
            continue
        for label, a, b in label_mentions(s.text, family):
            mentions.setdefault(label, []).append((s, a, b))
    if not mentions:
        return []

    def hit_in(label: str, wanted: set[str]) -> bool:
        return any(sec.role in wanted for other, hits in mentions.items() if _related(other, label)
                   for sec, _, _ in hits)

    findings: list[Finding] = []
    noun = "hypothesis" if family == "H" else "research question"
    late_titles = [s.title for s in ms.sections if s.role in _LATE_ROLES and s.level == 1]
    for label in sorted(mentions, key=lambda x: (int(re.search(r"\d+", x).group()), x)):
        hits = mentions[label]
        first_sec, a, b = hits[0]
        quote = _sentence_around(first_sec.text, a, b)
        if not hit_in(label, _LATE_ROLES):
            ftype = "hypothesis_untested" if family == "H" else "research_question_unanswered"
            findings.append(Finding(
                type=ftype,
                title=f"{label} is stated but no results, discussion or conclusion section mentions it",
                sections=[first_sec.id],
                quotes=[{"section": first_sec.id, "text": quote}],
                why=(f"A reviewer looks for the outcome of every {noun}. When {label} is never named after it is "
                     f"stated, they cannot tell whether it was tested, dropped or answered under another name."),
                fix=(f"Name {label} where it is tested or answered (checked: {', '.join(late_titles[:5])}), "
                     f"or remove it if it was dropped."),
                confidence="medium", source="rule", key=f"{ftype}:{label.lower()}",
            ))
        elif family == "H" and not hit_in(label, _EARLY_ROLES):
            findings.append(Finding(
                type="hypothesis_undeclared",
                title=f"{label} appears in the results but is never stated beforehand",
                sections=[first_sec.id],
                quotes=[{"section": first_sec.id, "text": quote}],
                why="A hypothesis that first appears with its result reads as post hoc.",
                fix=f"State {label} with its rationale in the theory or hypothesis section, or relabel the result.",
                confidence="medium", source="rule", key=f"hypothesis_undeclared:{label.lower()}",
            ))
    nums = sorted({int(re.search(r"\d+", l).group()) for l in mentions})
    if len(nums) >= 2:
        missing = [k for k in range(1, nums[-1] + 1) if k not in nums]
        if 0 < len(missing) <= 3:
            labels = ", ".join(f"{family}{k}" for k in missing)
            findings.append(Finding(
                type="label_gap",
                title=f"The {noun} numbering skips {labels}",
                sections=[], quotes=[],
                why=f"Readers will assume a {noun} was removed and the text not updated.",
                fix=f"Renumber the {noun}s, or restore {labels}.",
                confidence="low", source="rule", key=f"label_gap:{family.lower()}",
            ))
    return findings


_ACRO_DEF_RE = re.compile(
    r"((?:[A-Za-z][\w'\u2019-]*\s+){0,9}[A-Za-z][\w'\u2019-]*)\s*\(\s*([A-Z][A-Za-z0-9&-]*[A-Z0-9])(s?)\s*"
    r"(?:[,;][^()]{0,160})?\)"
)


def _best_long_form(short: str, words: list[str]) -> Optional[str]:
    """Schwartz-Hearst: the shortest run of trailing words whose letters spell the short form in order,
    with the first letter of the short form starting a word."""
    letters = [c.lower() for c in short if c.isalnum()]
    if len(letters) < 2:
        return None
    long = " ".join(words)
    s_idx, l_idx = len(letters) - 1, len(long) - 1
    while s_idx >= 0:
        c = letters[s_idx]
        while l_idx >= 0 and (long[l_idx].lower() != c or (s_idx == 0 and l_idx > 0 and long[l_idx - 1].isalnum())):
            l_idx -= 1
        if l_idx < 0:
            return None
        l_idx -= 1
        s_idx -= 1
    start = long.rfind(" ", 0, l_idx + 1) + 1
    form = long[start:].strip()
    if len(form.split()) > len(letters) + 3:
        return None
    return form


def _norm_expansion(form: str) -> str:
    t = re.sub(r"[-\u2010-\u2015]", " ", form.lower())
    t = re.sub(r"[^a-z0-9 ]", "", t)
    # British and US spellings are one expansion: modelling/modeling, organisation/organization.
    t = re.sub(r"([a-z])\1", r"\1", t)
    t = re.sub(r"is(ation|e|ed|ing)\b", r"iz\1", t)
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in t.split()]
    return " ".join(words)


def check_acronyms(ms: Manuscript) -> list[Finding]:
    defs: dict[str, list[tuple[str, Section, int, int]]] = {}
    for s in ms.sections:
        for m in _ACRO_DEF_RE.finditer(s.text):
            short = m.group(2)
            if sum(1 for c in short if c.isupper()) < 2 or re.fullmatch(r"(RQ|H)\d+[a-z]?", short):
                continue
            form = _best_long_form(short, m.group(1).split())
            if form:
                defs.setdefault(short, []).append((form, s, m.start(), m.end()))
    findings = []
    for short, items in defs.items():
        distinct: dict[str, tuple[str, Section, int, int]] = {}
        for it in items:
            distinct.setdefault(_norm_expansion(it[0]), it)
        # "Large Language Model" and "Language Model" are one definition read with a cut-off: keep only
        # expansions that are not a word-prefix or word-suffix of another.
        keys = [k for k in distinct
                if not any(o != k and (o.endswith(" " + k) or o.startswith(k + " ")) for o in distinct)]
        if len(keys) < 2:
            continue
        picks = [distinct[k] for k in keys[:3]]
        findings.append(Finding(
            type="acronym_conflict",
            title=f"{short} is expanded as " + " and as ".join(f'"{p[0]}"' for p in picks),
            sections=list(dict.fromkeys(p[1].id for p in picks)),
            quotes=[{"section": p[1].id, "text": _sentence_around(p[1].text, p[2], p[3])} for p in picks],
            why="Two expansions make a reader wonder whether two different things are meant.",
            fix=f"Pick one expansion of {short}, define it once at first use, and use the acronym after that.",
            confidence="high", source="rule", key=f"acronym_conflict:{short.lower()}",
        ))
    return findings


_NUM_RE = re.compile(r"(?<![\w.\-/])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w.]\d)(?:\s*(%|percent\b|percentage points?\b))?")


def _numbers(text: str) -> list[tuple[str, bool, int, int]]:
    """(normalised value, is_percent, start, end) for every number in text."""
    return [(m.group(1).replace(",", ""), bool(m.group(2)), m.start(), m.end()) for m in _NUM_RE.finditer(text)]


def _decimals(v: str) -> int:
    return len(v.split(".")[1]) if "." in v else 0


def _found_in_body(val: str, is_pct: bool, body_vals: set[str]) -> bool:
    """True if a body number equals val at val's precision, also as a proportion (92.1% and 0.921)."""
    a = float(val)
    d = _decimals(val)
    targets = [(a, d)]
    if is_pct or a > 1:
        targets.append((a / 100, d + 2))
    if a < 1:
        targets.append((a * 100, max(d - 2, 0)))
    for bv in body_vals:
        b = float(bv)
        for t, dd in targets:
            if round(b, dd) == round(t, dd):
                return True
    return False


def check_abstract_numbers(ms: Manuscript) -> list[Finding]:
    """Each percentage, decimal or count of 10 or more in the abstract should appear somewhere in the body
    (allowing for rounding and for 92% written as 0.92)."""
    if not ms.abstract:
        return []
    body = ms.body_text()
    if len(body) < 2_000:
        return []
    body_nums = _numbers(body)
    body_vals = {v for v, _, _, _ in body_nums}
    abs_sec = next((s for s in ms.sections if s.role == "abstract"), None)
    findings = []
    seen = set()
    for val, is_pct, a, b in _numbers(ms.abstract):
        f = float(val)
        is_year = "." not in val and 1900 <= f <= 2100 and not is_pct
        if is_year or (f < 10 and "." not in val and not is_pct) or val in seen:
            continue
        seen.add(val)
        if _found_in_body(val, is_pct, body_vals):
            continue
        near = sorted(
            {bv for bv, bp, _, _ in body_nums if bp == is_pct and bv != val and _decimals(bv) == _decimals(val)
             and abs(float(bv) - f) <= max(0.05 * abs(f), 0.5)},
            key=lambda x: abs(float(x) - f),
        )[:2]
        shown = val + ("%" if is_pct else "")
        if near:
            title = f"The abstract reports {shown}; the closest value in the body is " + " or ".join(
                n + ("%" if is_pct else "") for n in near)
            conf = "medium"
        else:
            title = f"The abstract reports {shown}, which appears nowhere in the body"
            conf = "low" if "." not in val and not is_pct else "medium"
        sid = abs_sec.id if abs_sec else ""
        findings.append(Finding(
            type="abstract_results_mismatch", title=title, sections=[sid] if sid else [],
            quotes=[{"section": sid, "text": _sentence_around(ms.abstract, a, b)}],
            why="Reviewers check the abstract's numbers against the tables first. A number they cannot find, "
                "or one that differs, suggests a stale abstract.",
            fix=f"Make the abstract's {shown} match the value reported in the results, or report it in the body.",
            confidence=conf, source="rule", key=f"abstract_results_mismatch:{val}",
        ))
    return findings[:8]


def rule_findings(ms: Manuscript) -> list[Finding]:
    return check_labels(ms, "H") + check_labels(ms, "RQ") + check_acronyms(ms) + check_abstract_numbers(ms)


# ---------------------------------------------------------------------------
# Stage 2: Paper Bible extraction
# ---------------------------------------------------------------------------

BIBLE_KINDS = {
    "research_question": "a research question the paper poses (label: RQ1 ... if the paper numbers them)",
    "rq_answer": "a passage that answers a research question (label: the RQ it answers)",
    "hypothesis": "a hypothesis or proposition as stated (label: H1, P2 ...)",
    "hypothesis_result": "a reported test outcome for a hypothesis (label: the hypothesis; text: supported or not)",
    "construct_definition": "a definition or operationalisation of a construct or key term (label: the term)",
    "theory": "a named theory, framework or kernel theory introduced as a lens (label: its name)",
    "theory_use": "a passage that uses a named theory to derive, explain or interpret (label: the theory)",
    "sample": "sample size, data source, period or composition (label: what is described, e.g. 'survey N')",
    "key_number": "a headline quantitative result (label: the metric; text: the value and what it refers to)",
    "contribution_claimed": "a contribution the paper promises, usually in the introduction (label: short name)",
    "contribution_delivered": "a passage that delivers or discusses a contribution (label: the same short name)",
    "limitation": "a stated limitation (label: short name)",
    "claim": "a strong claim of effect, generality, causality or novelty (label: short name)",
    "citation_use": "a cited source used to support a specific claim central to the argument "
                    "(label: the citation key or author-year)",
}

_EXTRACT_SYSTEM_CORE = """You are building a Paper Bible: a precise record of what each section of an academic
manuscript states, so that the sections can later be checked against each other. You are reading, not
reviewing: record what the text says, never what it should say, and never judge quality.

The manuscript chunk is split into sections, each opened by a line like [[S4 | Results > Experiment 2]].

Record items of these kinds:
{kinds}

Rules:
- Every item must carry "quote": 5 to 25 consecutive words copied exactly from that section (same words,
  same order). An item whose quote cannot be found in the text is discarded.
- "section" is the id (S4) of the section the quote comes from.
- "label" is short and consistent across the paper: reuse the paper's own labels (H2, RQ1) and its own term
  for a construct, so the same thing gets the same label in every section.
- "text" is your own summary of the item in at most 30 words. For key_number and sample include the value.
- Record every research question, hypothesis, hypothesis result, construct definition, theory, sample
  description, claimed and delivered contribution, and limitation. For key_number, claim and citation_use,
  keep only the ones central to the argument: at most 12 key_number, 10 claim and 10 citation_use items per
  chunk.
- Skip tables of contents, reference lists and figure placeholders.

Output ONLY a JSON array of objects:
[{{"section": "S4", "kind": "hypothesis", "label": "H2", "text": "...", "quote": "..."}}]
"""

EXTRACT_SYSTEM = _safety.SAFETY_PREAMBLE + "\n\n" + _EXTRACT_SYSTEM_CORE.format(
    kinds="\n".join(f"- {k}: {v}" for k, v in BIBLE_KINDS.items())
)


def _section_header(ms: Manuscript, s: Section) -> str:
    """[[S7 | Results > Experiment 2]]: the id plus the breadcrumb of parent titles."""
    idx = ms.sections.index(s)
    crumbs = [s.title]
    lvl = s.level
    for prev in reversed(ms.sections[:idx]):
        if prev.level < lvl:
            crumbs.insert(0, prev.title)
            lvl = prev.level
    return f"[[{s.id} | {' > '.join(crumbs)}]]"


def chunk_sections(ms: Manuscript, max_chars: int = CHUNK_CHARS) -> list[list[Section]]:
    chunks: list[list[Section]] = []
    cur: list[Section] = []
    size = 0
    for s in ms.sections:
        if s.role in ("references", "acknowledgements") or not s.text.strip():
            continue
        if cur and size + len(s.text) > max_chars:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(s)
        size += len(s.text)
    if cur:
        chunks.append(cur)
    return chunks


def _chunk_text(ms: Manuscript, chunk: list[Section]) -> str:
    return "\n\n".join(_section_header(ms, s) + "\n" + s.text for s in chunk)


def accept_items(raw_items: list, ms: Manuscript, allowed_sections: list[str]) -> tuple[list[dict], int]:
    """Keep the extracted items whose quote is verbatim in the named section (or, failing that, in another
    section of the same chunk, which then becomes the item's section). Returns (items, n_dropped)."""
    kept, dropped = [], 0
    for it in raw_items:
        if not isinstance(it, dict):
            dropped += 1
            continue
        kind = str(it.get("kind", "")).strip()
        quote = str(it.get("quote", "")).strip()
        sid = str(it.get("section", "")).strip()
        if kind not in BIBLE_KINDS or not quote:
            dropped += 1
            continue
        sec = ms.section(sid) if sid in allowed_sections else None
        if not (sec and quote_in_text(quote, sec.text)):
            sec = next((ms.section(o) for o in allowed_sections if quote_in_text(quote, ms.section(o).text)), None)
        if sec is None:
            dropped += 1
            continue
        kept.append({
            "section": sec.id,
            "kind": kind,
            "label": str(it.get("label", "")).strip()[:80],
            "text": str(it.get("text", "")).strip()[:300],
            "quote": trim_quote(quote),
        })
    return kept, dropped


async def extract_bible(client, ms: Manuscript, *, model: str = EXTRACT_MODEL, message_fn=None) -> dict:
    sem = asyncio.Semaphore(EXTRACT_CONCURRENCY)
    chunks = chunk_sections(ms)

    async def one(chunk: list[Section]) -> tuple[list[dict], int, str]:
        text = _safety.sanitize_user_text(_chunk_text(ms, chunk), max_len=CHUNK_CHARS * 4,
                                          field_name="coherence_chunk").text
        user = (
            (_safety.wrap_user_content(ms.title, "manuscript_title") + "\n\n" if ms.title else "")
            + _safety.wrap_user_content(text, "manuscript_body")
            + "\n\nBuild the Paper Bible items for these sections and output the JSON array now."
        )
        async with sem:
            items, status = await _call_json_findings(
                client, system=EXTRACT_SYSTEM, user_content=[{"type": "text", "text": user}],
                max_tokens=EXTRACT_MAX_OUTPUT_TOKENS, model=model, effort=EFFORT, message_fn=message_fn,
            )
        kept, dropped = accept_items(items, ms, [s.id for s in chunk])
        return kept, dropped, status

    results = await asyncio.gather(*(one(c) for c in chunks), return_exceptions=True)
    items: list[dict] = []
    dropped = 0
    statuses = []
    for r in results:
        if isinstance(r, BaseException):
            logger.warning("coherence extraction chunk failed: %s", type(r).__name__)
            statuses.append("error")
            continue
        items.extend(r[0])
        dropped += r[1]
        statuses.append(r[2])
    for k, it in enumerate(items):
        it["id"] = f"B{k + 1}"
    return {"items": items, "n_dropped_unquoted": dropped, "chunk_status": statuses, "n_chunks": len(chunks)}


def bible_counts(items: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for it in items:
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Stage 3: cross-section check and verification
# ---------------------------------------------------------------------------

_CHECK_SYSTEM_CORE = """You check an academic manuscript for internal coherence: places where its sections
disagree with each other. You do not see the manuscript itself, only its Paper Bible: items extracted from
each section, each with an id (B12), the section it came from (with the section's role), a kind, a label,
a summary and a verbatim quote. Some issues were already found by deterministic rules; do not repeat them.

Look for these types of issue:
{types}

Rules:
- Every finding must cite the Bible items that show it in "item_ids". A conflict cites at least two items
  from different places. An absence (a hypothesis with no result, a contribution never delivered, a research
  question never answered, a theory never used) cites the item that states it; report an absence only when
  no item of the matching kind and meaning exists anywhere, and say in "why" what you looked for.
- Labels may be worded differently between sections; match by meaning (the contribution "a new dataset" is
  delivered by "we release the corpus").
- Report disagreements a careful reviewer would raise. Not stylistic preferences, not analyses the paper
  never promised, not judgements of the research's quality.
- "title": one plain sentence naming the problem. "why": why a reviewer would care, at most 40 words.
  "fix": a specific edit the author can make, at most 40 words. "confidence": high (the items plainly
  conflict), medium (likely, though context might resolve it), low (worth a look).
- At most {max_findings} findings. Fewer, surer findings are better than many weak ones.

Output ONLY a JSON array:
[{{"type": "construct_definition_conflict", "item_ids": ["B3", "B41"], "title": "...", "why": "...",
   "fix": "...", "confidence": "medium"}}]
"""

CHECK_SYSTEM = _safety.SAFETY_PREAMBLE + "\n\n" + _CHECK_SYSTEM_CORE.format(
    types="\n".join(f"- {k}: {v}" for k, v in CHECK_TYPES.items() if k not in ("acronym_conflict", "label_gap")),
    max_findings=MAX_FINDINGS,
)

_VERIFY_SYSTEM_CORE = """You are the last check before a coherence report reaches an author. You see the
full manuscript text (sections opened by lines like [[S4 | Results]]) and a numbered list of candidate
findings, each with the quotes it rests on. For every finding decide whether it holds up against the whole
text.

Drop a finding when:
- the text resolves it: the hypothesis is reported (perhaps in a table, or under another label), the
  research question is answered, the contribution is delivered, the two definitions are compatible or one
  is explicitly a refinement, the abstract number appears in another form, the limitation is acknowledged
  where the claim is made;
- it rests on a misreading of a quote, or on text from a table of contents, caption list or reference list;
- it is a matter of style or taste rather than the paper disagreeing with itself.

Keep it when a careful reviewer reading the whole paper would still raise it. Be strict: the author pays for
precision, and one false alarm costs more trust than one missed issue.

Output ONLY a JSON array with one object per finding, in the same order:
[{"n": 1, "verdict": "keep", "confidence": "high", "note": "<at most 30 words: why>"}]
where verdict is "keep" or "drop" and confidence is "high", "medium" or "low".
"""

VERIFY_SYSTEM = _safety.SAFETY_PREAMBLE + "\n\n" + _VERIFY_SYSTEM_CORE


def _bible_for_prompt(ms: Manuscript, items: list[dict]) -> str:
    sec_info = {s.id: f"{s.title} ({s.role})" for s in ms.sections}
    rows = [{"id": it["id"], "section": f"{it['section']} {sec_info.get(it['section'], '')}",
             "kind": it["kind"], "label": it["label"], "text": it["text"], "quote": it["quote"]}
            for it in items]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def findings_from_model(raw: list, items: list[dict]) -> list[Finding]:
    """Turn the cross-check's reply into findings. A finding that names no real Bible item is dropped, and
    its quotes always come from the cited items (already verified verbatim), never from the reply."""
    by_id = {it["id"]: it for it in items}
    out = []
    for f in raw:
        if not isinstance(f, dict):
            continue
        ftype = str(f.get("type", "")).strip()
        ids = [i for i in (f.get("item_ids") or []) if isinstance(i, str) and i in by_id]
        if ftype not in CHECK_TYPES or not ids:
            continue
        cited, seen = [], set()
        for i in ids:
            q = _norm_for_match(by_id[i]["quote"])
            if q not in seen:           # two items can carry the same span
                seen.add(q)
                cited.append(by_id[i])
        cited = cited[:4]
        conf = str(f.get("confidence", "medium")).lower()
        out.append(Finding(
            type=ftype,
            title=str(f.get("title", "")).strip()[:300] or TYPE_TITLES[ftype],
            sections=list(dict.fromkeys(it["section"] for it in cited)),
            quotes=[{"section": it["section"], "text": it["quote"]} for it in cited],
            why=str(f.get("why", "")).strip()[:500],
            fix=str(f.get("fix", "")).strip()[:500],
            confidence=conf if conf in CONFIDENCE_ORDER else "medium",
            source="model",
            key=f"{ftype}:" + ",".join(sorted(it["label"].lower() for it in cited)),
        ))
    return out[:MAX_FINDINGS]


def dedupe(rule: list[Finding], model: list[Finding]) -> list[Finding]:
    """A model finding of the same type that names a label a rule finding already covers is the same issue."""
    covered = {(f.type, f.key.split(":", 1)[1]) for f in rule if ":" in f.key}
    out = list(rule)
    for f in model:
        labels = f.key.split(":", 1)[1].split(",") if ":" in f.key else []
        if any((f.type, l) in covered for l in labels):
            continue
        out.append(f)
    return out


async def cross_check(client, ms: Manuscript, items: list[dict], rules: list[Finding], *,
                      model: str = CHECK_MODEL, message_fn=None) -> tuple[list[Finding], str]:
    if not items:
        return [], "empty"
    rule_lines = "\n".join(f"- {f.type}: {f.title}" for f in rules) or "(none)"
    user = (
        _safety.wrap_user_content(_bible_for_prompt(ms, items), "paper_bible") + "\n\n"
        + _safety.wrap_user_content(rule_lines, "deterministic_checks") + "\n\n"
        + "Check the Paper Bible for coherence issues and output the JSON array now."
    )
    raw, status = await _call_json_findings(
        client, system=CHECK_SYSTEM, user_content=[{"type": "text", "text": user}],
        max_tokens=CHECK_MAX_OUTPUT_TOKENS, model=model, effort=EFFORT, message_fn=message_fn,
    )
    return findings_from_model(raw, items), status


def full_text_for_prompt(ms: Manuscript) -> str:
    return "\n\n".join(_section_header(ms, s) + "\n" + s.text
                       for s in ms.sections if s.role not in ("references", "acknowledgements"))


async def verify(client, ms: Manuscript, findings: list[Finding], *,
                 model: str = CHECK_MODEL, message_fn=None) -> tuple[list[Finding], list[Finding], str]:
    """Returns (kept, dropped, status). If the verifier's reply is unreadable every finding is kept and marked
    unverified, rather than the report silently losing its findings."""
    if not findings:
        return [], [], "empty"
    listing = "\n\n".join(
        f"{k + 1}. [{f.type}] {f.title}\n"
        + "\n".join(f"   quote ({q['section'] or 'abstract'}): \"{q['text']}\"" for q in f.quotes)
        + (f"\n   why: {f.why}" if f.why else "")
        for k, f in enumerate(findings)
    )
    text = _safety.sanitize_user_text(full_text_for_prompt(ms), max_len=MAX_INPUT_CHARS + 20_000,
                                      field_name="coherence_verify").text
    user_content = [
        {"type": "text", "text": _safety.wrap_user_content(text, "manuscript_body")},
        {"type": "text", "text": _safety.wrap_user_content(listing, "coherence_findings")
         + "\n\nJudge each finding against the full text and output the JSON array now."},
    ]
    raw, status = await _call_json_findings(
        client, system=VERIFY_SYSTEM, user_content=user_content,
        max_tokens=VERIFY_MAX_OUTPUT_TOKENS, model=model, effort=EFFORT, message_fn=message_fn,
    )
    if status == "unparsed":
        for f in findings:
            f.verifier_note = "not verified (the verification step returned no readable answer)"
        return findings, [], status
    verdicts = {}
    for v in raw:
        try:
            verdicts[int(v.get("n"))] = v
        except (TypeError, ValueError, AttributeError):
            continue
    kept, dropped = [], []
    for k, f in enumerate(findings):
        v = verdicts.get(k + 1)
        if v is None:
            f.verifier_note = "not verified"
            kept.append(f)
            continue
        f.verifier_note = str(v.get("note", "")).strip()[:300]
        conf = str(v.get("confidence", "")).lower()
        if conf in CONFIDENCE_ORDER:
            f.confidence = conf
        (dropped if str(v.get("verdict", "")).lower() == "drop" else kept).append(f)
    return kept, dropped, status


# ---------------------------------------------------------------------------
# Orchestration and report
# ---------------------------------------------------------------------------

def _sorted(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (CONFIDENCE_ORDER.get(f.confidence, 3), f.source != "rule"))


async def run_coherence_check(ms: Manuscript, *, client=None, use_model: bool = True, verify_findings: bool = True,
                              message_fn=None) -> dict:
    """Run the check. With use_model=False only the rules run (no network, no cost): the free sample."""
    rules = rule_findings(ms)
    report: dict = {
        "version": 1,
        "title": ms.title,
        "source_kind": ms.source_kind,
        "truncated": ms.truncated,
        "sections": [s.to_dict() for s in ms.sections],
        "mode": "full" if use_model else "rules_only",
        "status": {},
        "bible": {"items": [], "counts": {}},
        "findings": [],
        "dropped": [],
    }
    if not use_model:
        report["findings"] = [f.to_dict() for f in _sorted(rules)]
        return report

    own_client = client is None
    if own_client:
        import httpx
        client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=600.0, write=10.0, pool=10.0))
    try:
        bible = await extract_bible(client, ms, message_fn=message_fn)
        items = bible["items"]
        report["bible"] = {"items": items, "counts": bible_counts(items),
                           "n_dropped_unquoted": bible["n_dropped_unquoted"]}
        report["status"]["extract"] = bible["chunk_status"]
        try:
            model_findings, st = await cross_check(client, ms, items, rules, message_fn=message_fn)
        except Exception as e:
            logger.warning("coherence cross-check failed: %s", type(e).__name__)
            model_findings, st = [], "error"
        report["status"]["check"] = st
        merged = dedupe(rules, model_findings)
        kept, dropped = merged, []
        if verify_findings and merged:
            try:
                kept, dropped, vst = await verify(client, ms, merged, message_fn=message_fn)
            except Exception as e:
                logger.warning("coherence verification failed: %s", type(e).__name__)
                vst = "error"
                for f in kept:
                    f.verifier_note = "not verified"
            report["status"]["verify"] = vst
        report["findings"] = [f.to_dict() for f in _sorted(kept)]
        report["dropped"] = [f.to_dict() for f in dropped]
    finally:
        if own_client:
            await client.aclose()
    logger.info("coherence check: %d sections, %d bible items, %d findings, %d dropped",
                len(ms.sections), len(report["bible"]["items"]), len(report["findings"]), len(report["dropped"]))
    return report


_BIBLE_HEADINGS = [
    ("research_question", "Research questions"),
    ("hypothesis", "Hypotheses"),
    ("construct_definition", "Construct definitions"),
    ("theory", "Theories"),
    ("sample", "Sample and data"),
    ("contribution_claimed", "Contributions claimed"),
    ("limitation", "Limitations"),
]


def render_markdown(report: dict) -> str:
    sec_title = {s["id"]: s["title"] for s in report.get("sections", [])}
    findings = report.get("findings", [])
    lines = ["## Coherence Check", ""]
    if report.get("mode") == "rules_only":
        lines += ["This sample runs the rule-based checks only (hypothesis and question labels, acronyms, "
                  "abstract numbers). The full check also reads every section into a Paper Bible and compares "
                  "them.", ""]
    if not findings:
        lines.append("No disagreements between sections were found.")
    else:
        lines.append(f"{len(findings)} place{'s' if len(findings) != 1 else ''} where the manuscript may disagree "
                     "with itself, surest first. Each quote is copied from your text.")
    if report.get("truncated"):
        lines += ["", "_The manuscript was longer than the check reads at once, so its end was not read._"]
    for k, f in enumerate(findings, 1):
        where = ", ".join(sec_title.get(s, s) for s in f.get("sections", [])) or "whole manuscript"
        lines += ["", f"### {k}. {f['title']}", "",
                  f"{TYPE_TITLES.get(f['type'], f['type'])} · {where} · confidence: {f['confidence']}", ""]
        for q in f.get("quotes", []):
            lines += [f"> \u201c{q['text']}\u201d ({sec_title.get(q.get('section', ''), 'Abstract')})", ""]
        if f.get("why"):
            lines += [f"**Why it matters.** {f['why']}", ""]
        if f.get("fix"):
            lines.append(f"**Suggested fix.** {f['fix']}")
    items = report.get("bible", {}).get("items", [])
    if items:
        lines += ["", "### Paper Bible", "",
                  "What each section states, as read for this check. Use it to confirm the paper says what you "
                  "meant it to say."]
        for kind, heading in _BIBLE_HEADINGS:
            rows = [it for it in items if it["kind"] == kind]
            if not rows:
                continue
            lines += ["", f"**{heading}**", ""]
            for it in rows[:20]:
                label = f"{it['label']}: " if it.get("label") else ""
                lines.append(f"- {label}{it['text']} ({sec_title.get(it['section'], it['section'])})")
    return "\n".join(lines).rstrip() + "\n"
