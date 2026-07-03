"""Deterministic, reproducible manuscript checks (no LLM).

Ported from the ModernTex Swift sources (ManuscriptChecks.swift, StatCheckService.swift,
StatMath.swift, ReferenceIntegrityChecker.swift) so the web review pipeline and the native app
share the same ground-truth engines. Every check is a pure function over text (the extracted
manuscript body) or the parsed reference list, so results are reproducible and unit-testable.

These findings are folded into the review report as verified facts the LLM panel cannot override —
statcheck/GRIM recompute p-values and means; the number/text/open-science checks flag arithmetic,
typographic, and reporting-completeness issues.

All checks incorporate the QA-audit hardening that landed in ModernTex: LaTeX comment/verbatim
stripping, high-precision p-value matching (no false positives on pressure/hyperparameters),
acronym extraction that ignores cite/ref keys and honors \\newacronym/\\acro definitions,
same-line-only repeated-word detection, broadened RRID prefixes, and \\nocite handling.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional


# ===========================================================================
# Finding model
# ===========================================================================

@dataclass
class DeterministicFinding:
    kind: str        # "statcheck" | "grim" | "structure" | "numbers" | "openscience" | "text" | "citation"
    severity: str    # "error" | "warning" | "info"
    summary: str
    detail: str

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity,
                "summary": self.summary, "detail": self.detail}


# ===========================================================================
# StatMath — special functions (Numerical Recipes algorithms, pure Python).
# Mirrors StatMath.swift exactly so p-values match the native app.
# ===========================================================================

def _lgamma(x: float) -> float:
    return math.lgamma(x)


def _betacf(x: float, a: float, b: float) -> float:
    eps, fpmin = 3.0e-12, 1.0e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1 / d
    h = d
    for m in range(1, 201):
        m2 = 2 * m
        md = float(m)
        aa = md * (b - md) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1 / d
        h *= d * c
        aa = -(a + md) * (qab + md) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1) < eps:
            break
    return h


def incomplete_beta(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(_lgamma(a + b) - _lgamma(a) - _lgamma(b)
                  + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(x, a, b) / a
    return 1 - bt * _betacf(1 - x, b, a) / b


def _gamma_series(a: float, x: float) -> float:
    ap, s, del_ = a, 1 / a, 1 / a
    for _ in range(300):
        ap += 1
        del_ *= x / ap
        s += del_
        if abs(del_) < abs(s) * 3.0e-12:
            break
    return s * math.exp(-x + a * math.log(x) - _lgamma(a))


def _gamma_cf(a: float, x: float) -> float:
    fpmin, eps = 1.0e-300, 3.0e-12
    b = x + 1 - a
    c = 1 / fpmin
    d = 1 / b
    h = d
    for i in range(1, 300):
        an = -float(i) * (float(i) - a)
        b += 2
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1) < eps:
            break
    return math.exp(-x + a * math.log(x) - _lgamma(a)) * h


def gamma_q(a: float, x: float) -> float:
    if x < 0 or a <= 0:
        return math.nan
    if x == 0:
        return 1.0
    if x < a + 1:
        return 1 - _gamma_series(a, x)
    return _gamma_cf(a, x)


def normal_two_tailed_p(z: float) -> float:
    return math.erfc(abs(z) / 1.4142135623730951)


def t_two_tailed_p(t: float, df: float) -> float:
    if df <= 0:
        return math.nan
    return incomplete_beta(df / (df + t * t), df / 2, 0.5)


def f_upper_p(f: float, df1: float, df2: float) -> float:
    if f <= 0 or df1 <= 0 or df2 <= 0:
        return math.nan
    return incomplete_beta(df2 / (df2 + df1 * f), df2 / 2, df1 / 2)


def chi_square_upper_p(chi2: float, df: float) -> float:
    if chi2 < 0 or df <= 0:
        return math.nan
    return gamma_q(df / 2, chi2 / 2)


def correlation_two_tailed_p(r: float, df: float) -> float:
    if df <= 0 or abs(r) >= 1:
        return 0.0 if abs(r) >= 1 else math.nan
    t = r * math.sqrt(df / (1 - r * r))
    return t_two_tailed_p(t, df)


# ===========================================================================
# Sanitization — strip LaTeX comments + verbatim so prose checks don't fire on
# commented-out markup or code listings (the dominant false-positive source).
# Harmless on extracted PDF text (which has neither), useful on .tex input.
# ===========================================================================

_VERBATIM_ENVS = ("verbatim", "Verbatim", "lstlisting", "minted", "comment", "code")


def sanitize(text: str) -> str:
    t = text
    for env in _VERBATIM_ENVS:
        t = re.sub(r"\\begin\{" + env + r"\*?\}.*?\\end\{" + env + r"\*?\}",
                   " ", t, flags=re.DOTALL)
    # Strip inline/full-line comments: an unescaped % through end of line.
    t = re.sub(r"(?<!\\)%.*", "", t)
    return t


def strip_math_delimiters(s: str) -> str:
    s = re.sub(r"\\[()\[\]]", " ", s)   # \( \) \[ \]
    return s.replace("$", " ")


# ===========================================================================
# statcheck — recompute reported NHST p-values from the test statistic.
# ===========================================================================

_STATCHECK_RE = re.compile(
    r"(χ2|χ²|chi2|chi-square|X2|[tFrzQ])"
    r"\s*(?:\(\s*(\d+(?:\.\d+)?)\s*(?:,\s*(\d+(?:\.\d+)?))?[^)]*\))?"
    r"\s*[=<>]\s*(-?\d*\.?\d+)\s*,?\s*p\s*([=<>])\s*(\d*\.?\d+)",
    re.IGNORECASE,
)


def _norm_double(s: str) -> Optional[float]:
    try:
        return float("0" + s if s.startswith(".") else s)
    except ValueError:
        return None


def _decimal_places(s: str) -> int:
    if "." not in s:
        return 0
    return len(s) - s.index(".") - 1


def _round(x: float, d: int) -> float:
    f = 10.0 ** d
    return round(x * f) / f


def _compute_p(type_raw: str, stat: float, df1: Optional[float], df2: Optional[float]) -> Optional[float]:
    t = type_raw.lower()
    if t == "t":
        return t_two_tailed_p(stat, df1) if df1 is not None else None
    if t == "f":
        return f_upper_p(stat, df1, df2) if (df1 is not None and df2 is not None) else None
    if t == "r":
        return correlation_two_tailed_p(stat, df1) if df1 is not None else None
    if t == "z":
        return normal_two_tailed_p(stat)
    if t == "q":
        return chi_square_upper_p(stat, df1) if df1 is not None else None
    # χ2 / χ² / chi2 / chi-square / X2
    return chi_square_upper_p(stat, df1) if df1 is not None else None


@dataclass
class StatResult:
    raw: str
    reported_p: float
    reported_operator: str
    computed_p: float
    consistent: bool
    decision_error: bool


def statcheck(raw_text: str) -> list[StatResult]:
    text = strip_math_delimiters(sanitize(raw_text))
    out: list[StatResult] = []
    for m in _STATCHECK_RE.finditer(text):
        type_raw = m.group(1)
        df1 = float(m.group(2)) if m.group(2) else None
        df2 = float(m.group(3)) if m.group(3) else None
        stat = _norm_double(m.group(4))
        p_op = m.group(5)
        reported_p = _norm_double(m.group(6))
        if stat is None or reported_p is None:
            continue
        computed = _compute_p(type_raw, stat, df1, df2)
        if computed is None or not math.isfinite(computed):
            continue
        decimals = _decimal_places(m.group(6))
        if p_op == "<":
            consistent = computed < reported_p or _round(computed, max(decimals, 2)) <= reported_p
        elif p_op == ">":
            consistent = computed > reported_p or _round(computed, max(decimals, 2)) >= reported_p
        else:
            consistent = _round(computed, decimals) == _round(reported_p, decimals)
        # significance claimed vs computed at alpha = .05
        if p_op == "<":
            claimed_sig = reported_p <= 0.05
        elif p_op == ">":
            claimed_sig = False
        else:
            claimed_sig = reported_p < 0.05
        decision_error = (claimed_sig != (computed < 0.05)) and not consistent
        out.append(StatResult(raw=m.group(0).strip(), reported_p=reported_p,
                              reported_operator=p_op, computed_p=computed,
                              consistent=consistent, decision_error=decision_error))
    return out


# ===========================================================================
# GRIM — a reported mean of integer items must be achievable as integer/N.
# ===========================================================================

def grim_consistent(mean: float, n: int, items: int = 1, decimals: Optional[int] = None) -> bool:
    if n <= 0 or items <= 0:
        return True
    total_n = float(n * items)
    if decimals is None:
        s = repr(mean)
        decimals = len(s) - s.index(".") - 1 if "." in s else 0
    tol = 0.5 * (10.0 ** -decimals) + 1e-9
    target = mean * total_n
    lo = math.floor(target - tol * total_n)
    hi = math.ceil(target + tol * total_n)
    for t in range(lo, hi + 1):
        if abs(t / total_n - mean) <= tol:
            return True
    return False


# The gap between "M = x.xx" and "n = N" allows short stats-aside tokens
# (SD=, CI, parens/punctuation, up to 2 short "words" of <=4 letters each —
# enough for "SD", "and", "CI" etc.) but rejects runs of ordinary prose.
# This is deliberately NOT an arbitrary-prose wildcard: free-text spans here
# would otherwise be captured verbatim into DeterministicFinding.summary,
# which downstream (papercheck.run_layer_4_rectify) is fed to the L4
# synthesis LLM inside a block explicitly labeled "VERIFIED FACTS that
# override any contradicting panel claim" — an attacker-fillable gap here
# is a direct prompt-injection vector into that trusted context.
_GRIM_GAP = r"(?:[0-9=.,;:()%\-\s]|\b[A-Za-z]{1,4}\b){0,50}?"
_GRIM_MEAN_N = re.compile(r"\bM\s*=\s*(\d+\.\d+)" + _GRIM_GAP + r"\b[nN]\s*=\s*(\d+)\b")
_GRIM_N_MEAN = re.compile(r"\b[nN]\s*=\s*(\d+)" + _GRIM_GAP + r"\bM\s*=\s*(\d+\.\d+)")


@dataclass
class GrimCheck:
    raw: str
    mean: float
    n: int
    consistent: bool


def grim_checks(raw_text: str) -> list[GrimCheck]:
    text = strip_math_delimiters(sanitize(raw_text))
    out: list[GrimCheck] = []
    for m in _GRIM_MEAN_N.finditer(text):
        mean, n = float(m.group(1)), int(m.group(2))
        out.append(GrimCheck(m.group(0).strip(), mean, n, grim_consistent(mean, n)))
    for m in _GRIM_N_MEAN.finditer(text):
        n, mean = int(m.group(1)), float(m.group(2))
        out.append(GrimCheck(m.group(0).strip(), mean, n, grim_consistent(mean, n)))
    return out


# ===========================================================================
# B. Numbers: percentage arithmetic, impossible values
# ===========================================================================

def number_checks(text: str) -> list[DeterministicFinding]:
    out: list[DeterministicFinding] = []
    t = strip_math_delimiters(sanitize(text))

    # "X of Y (Z%)" or "X/Y (Z%)" — verify Z ~= 100*X/Y. `\%` is how a literal percent is written.
    for m in re.finditer(r"(\d+)\s*(?:/|of)\s*(\d+)\s*\(\s*(\d+(?:\.\d+)?)\s*\\?%\s*\)", t):
        x, y, z = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if y <= 0:
            continue
        actual = 100 * x / y
        if abs(actual - z) > 1.0:
            out.append(DeterministicFinding(
                "numbers", "warning", f"Percentage mismatch: {m.group(0)}",
                f"{x:.0f}/{y:.0f} = {actual:.1f}%, not {z:.1f}%."))

    # Impossible p-values. High-precision: lowercase p only, not part of a larger identifier/command,
    # only treat `p = ...` as a point estimate, and only call >1 impossible when written with a decimal.
    for m in re.finditer(r"(?<![\\A-Za-z])p\s*([=<>])\s*(\d*\.?\d+)", t):
        op, raw = m.group(1), m.group(2)
        val = _norm_double(raw)
        if val is None:
            continue
        if op == "=" and val > 1 and "." in raw:
            out.append(DeterministicFinding(
                "numbers", "error", f"Impossible p-value: {m.group(0)}",
                "A probability cannot exceed 1."))
        elif op == "=" and val == 0:
            out.append(DeterministicFinding(
                "numbers", "warning", f"p reported as 0: {m.group(0)}",
                "Report as p < .001 rather than p = 0."))

    # Accuracy > 100%.
    for m in re.finditer(r"accuracy\s*(?:of|reached|=|:)?\s*(\d+(?:\.\d+)?)\s*\\?%", t, re.IGNORECASE):
        if float(m.group(1)) > 100:
            out.append(DeterministicFinding(
                "numbers", "error", f"Accuracy > 100%: {m.group(0)}",
                "Accuracy cannot exceed 100%."))
    return out


# ===========================================================================
# D. Open-science statement presence + RRID
# ===========================================================================

_OPENSCIENCE_SIGNALS = [
    ("data availability", [r"data (are|is) available", r"availability statement", r"osf\.io",
                           r"github\.com", r"zenodo", r"dryad", r"figshare",
                           r"supplementary (data|material)"]),
    ("code availability", [r"code (is|are) available", r"github\.com", r"source code",
                           r"replication (package|code)"]),
    ("ethics / IRB approval", [r"\bIRB\b", r"ethics (committee|approval|board)",
                               r"institutional review board", r"informed consent", r"\bIACUC\b"]),
    ("funding statement", [r"funded by", r"funding", r"\bgrant\b", r"supported by"]),
    ("conflict-of-interest statement", [r"conflict(s)? of interest", r"competing interests",
                                        r"no conflicts", r"declare no"]),
    ("preregistration", [r"prereg", r"pre-?registered", r"aspredicted", r"registration number",
                         r"clinicaltrials\.gov"]),
]


def open_science_checks(raw_text: str) -> list[DeterministicFinding]:
    out: list[DeterministicFinding] = []
    text = sanitize(raw_text)
    for name, patterns in _OPENSCIENCE_SIGNALS:
        present = any(re.search(p, text, re.IGNORECASE) for p in patterns)
        if not present:
            out.append(DeterministicFinding(
                "openscience", "info", f"No {name} detected",
                f"Many venues require an explicit {name}; add one if applicable."))
    # RRID format: a registry prefix, underscore, then an identifier (shape matters, not exact prefix).
    for m in re.finditer(r"RRID:\s*(\S+)", text):
        if not re.match(r"^[A-Za-z]+_[A-Za-z0-9.:-]+$", m.group(1)):
            out.append(DeterministicFinding(
                "openscience", "warning", f"Malformed RRID: {m.group(0)}",
                "Expected form RRID:AB_####, RRID:SCR_####, RRID:Addgene_####, etc."))
    return out


# ===========================================================================
# E. Text: repeated words, undefined acronyms
# ===========================================================================

# LaTeX commands whose brace arguments are identifiers (keys, labels, URLs), NOT prose.
_NON_PROSE_COMMANDS = (
    "cite|citep|citet|citeauthor|citeyear|citeyearpar|parencite|textcite|autocite|footcite|"
    "citealp|citealt|nocite|fullcite|smartcite|supercite|citenum|"
    "ref|eqref|autoref|cref|Cref|labelcref|nameref|namecref|pageref|vref|vpageref|subref|crefrange|Crefrange|"
    "label|gls|Gls|glspl|acs|acl|acf|ac|acrshort|acrlong|url|href|"
    "input|include|includegraphics|bibliography|bibliographystyle|usepackage|documentclass|"
    "newacronym|DeclareAcronym|acro"
)

_COMMON_ACRONYMS = {"AND", "THE", "FOR", "NCA", "OK", "USA", "UK", "EU", "AI", "ML",
                    "II", "III", "IV", "VI", "VII", "PDF", "HTML", "JSON", "API", "URL"}


def text_checks(raw_text: str) -> list[DeterministicFinding]:
    out: list[DeterministicFinding] = []
    sanitized = sanitize(raw_text)

    # Definitions harvested BEFORE stripping command args (which deletes the acronym tokens).
    defined = set(m.group(1).upper() for m in re.finditer(r"\(([A-Z][A-Za-z]{1,5})\)", sanitized))
    for pat in (r"\\newacronym\*?(?:\[[^\]]*\])?\{[^}]*\}\{([A-Za-z]{2,6})\}",
                r"\\(?:DeclareAcronym|acro)\{([A-Za-z]{2,6})\}"):
        for m in re.finditer(pat, sanitized):
            defined.add(m.group(1).upper())

    # Prose with non-prose command args (cite keys, labels, URLs, math) removed.
    prose = strip_math_delimiters(sanitized)
    prose = re.sub(r"\\(?:" + _NON_PROSE_COMMANDS + r")\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})+", " ", prose)

    # Repeated consecutive words ("the the") — same-line only, never across a sentence boundary.
    repeated = set()
    for m in re.finditer(r"\b([a-zA-Z]{2,})[ \t]+\1\b", prose, re.IGNORECASE):
        w = m.group(1).lower()
        if w not in ("that", "had", "very"):
            repeated.add(w)
    for w in sorted(repeated):
        out.append(DeterministicFinding(
            "text", "warning", f"Repeated word: “{w} {w}”", "Likely a typo."))

    # Acronyms used but never defined (parenthetical or glossary-package form).
    acronyms = set(m.group(1) for m in re.finditer(r"\b([A-Z]{2,6})\b", prose))
    undefined = sorted(a for a in (acronyms - defined - _COMMON_ACRONYMS) if len(a) >= 3)
    if undefined:
        out.append(DeterministicFinding(
            "text", "info",
            f"Acronyms used without a parenthetical definition: {', '.join(undefined[:10])}",
            "Define each acronym at first use, e.g. ‘Necessary Condition Analysis (NCA)’."))
    return out


# ===========================================================================
# A. Structure: cross-references, duplicate labels, placeholders, floats.
# Only meaningful on LaTeX source (extracted PDF text has no \ref/\label).
# ===========================================================================

_PLACEHOLDERS = [
    (r"\\todo\b", r"\todo"), (r"\bTODO\b", "TODO"), (r"\bFIXME\b", "FIXME"),
    (r"\bTKTK\b", "TKTK"), (r"\bXXX\b", "XXX"), (r"\[CITATION\]", "[CITATION]"),
    (r"\[ref\]", "[ref]"), (r"(?i)lorem ipsum", "lorem ipsum"),
]


def structure_checks(raw_text: str) -> list[DeterministicFinding]:
    out: list[DeterministicFinding] = []
    text = sanitize(raw_text)

    # Labels + duplicate detection.
    label_counts: dict[str, int] = {}
    for m in re.finditer(r"\\label\{([^}]+)\}", text):
        label_counts[m.group(1)] = label_counts.get(m.group(1), 0) + 1
    labels = set(label_counts)
    for label, count in label_counts.items():
        if count > 1:
            out.append(DeterministicFinding(
                "structure", "error", f"Duplicate \\label{{{label}}} (defined {count}×)",
                "Multiple labels with the same name resolve ambiguously."))

    # References to undefined labels.
    undefined: set[str] = set()
    ref_re = (r"\\(?:eqref|autoref|[cC]ref|labelcref|namecref|nameref|pageref|vpageref|vref|subref|ref)"
              r"\*?\{([^}]+)\}")
    for m in re.finditer(ref_re, text):
        for key in (k.strip() for k in m.group(1).split(",")):
            if key and key not in labels:
                undefined.add(key)
    for m in re.finditer(r"\\[cC]refrange\*?\{([^}]+)\}\{([^}]+)\}", text):
        for key in (m.group(1).strip(), m.group(2).strip()):
            if key and key not in labels:
                undefined.add(key)
    for key in sorted(undefined):
        out.append(DeterministicFinding(
            "structure", "error", f"Reference to undefined label: \\ref{{{key}}}",
            f"No matching \\label{{{key}}} found — this renders as ‘??’."))

    # Placeholders / leftovers.
    for pat, name in _PLACEHOLDERS:
        n = len(re.findall(pat, text))
        if n > 0:
            out.append(DeterministicFinding(
                "structure", "warning", f"Leftover placeholder: {name} ({n}×)",
                "Remove placeholder/TODO text before submission."))

    # Float hygiene: figure/table environments missing \caption or \label.
    for env in ("figure", "table"):
        blocks = re.findall(r"\\begin\{" + env + r"\*?\}(.*?)\\end\{" + env + r"\*?\}", text, re.DOTALL)
        missing_caption = sum(1 for b in blocks if "\\caption" not in b)
        missing_label = sum(1 for b in blocks if "\\label" not in b)
        if missing_caption:
            out.append(DeterministicFinding(
                "structure", "warning", f"{missing_caption} {env}(s) without a \\caption",
                f"Every {env} should have a caption."))
        if missing_label:
            out.append(DeterministicFinding(
                "structure", "info", f"{missing_label} {env}(s) without a \\label",
                f"Add \\label so the {env} can be \\ref'd."))
    return out


# ===========================================================================
# C. Reference integrity — adapted to extracted references (no .tex source).
# Duplicate DOIs, missing fields, implausible years. Cite<->bib reconciliation
# (undefined/orphan) needs raw \cite commands, so it is only run when source is
# supplied via `reference_integrity_source`.
# ===========================================================================

def reference_integrity_from_extracted(references, current_year: int) -> list[DeterministicFinding]:
    """Checks over a list of extracted references (objects/dicts with
    .doi/.year/.title/.authors). Used by the PDF review flow."""
    out: list[DeterministicFinding] = []

    def field(ref, name):
        return getattr(ref, name, None) if not isinstance(ref, dict) else ref.get(name)

    # Duplicate DOIs (same work cited twice).
    doi_idx: dict[str, list[int]] = {}
    for i, ref in enumerate(references):
        doi = (field(ref, "doi") or "").strip().lower()
        if doi:
            doi_idx.setdefault(doi, []).append(i + 1)
    for doi, idxs in doi_idx.items():
        if len(idxs) > 1:
            out.append(DeterministicFinding(
                "citation", "warning",
                f"Duplicate reference (same DOI): entries {', '.join(map(str, idxs))}",
                f"DOI {doi} appears more than once in the bibliography."))

    # Missing fields + implausible years.
    for i, ref in enumerate(references):
        missing = []
        if not (field(ref, "authors") or "").strip():
            missing.append("authors")
        if not (field(ref, "title") or "").strip():
            missing.append("title")
        year_s = (field(ref, "year") or "").strip()
        if not year_s:
            missing.append("year")
        if missing:
            out.append(DeterministicFinding(
                "citation", "info", f"Incomplete reference [{i + 1}]: missing {', '.join(missing)}",
                "Reference may be mis-parsed or genuinely incomplete."))
        if year_s[:4].isdigit():
            y = int(year_s[:4])
            if y < 1500 or y > current_year + 1:
                out.append(DeterministicFinding(
                    "citation", "warning", f"Implausible year in [{i + 1}]: {y}",
                    "Year is in the future or implausibly old."))
    return out


# ===========================================================================
# Aggregators
# ===========================================================================

def _statcheck_findings(body: str) -> list[DeterministicFinding]:
    out: list[DeterministicFinding] = []
    for r in statcheck(body):
        if not r.consistent:
            sev = "error" if r.decision_error else "warning"
            comp = "< .001" if r.computed_p < 0.001 else f"= {r.computed_p:.3f}"
            note = " (significance flips)" if r.decision_error else ""
            out.append(DeterministicFinding(
                "statcheck", sev, r.raw,
                f"Reported p {r.reported_operator} {r.reported_p}; recomputed p {comp}{note}."))
    for g in grim_checks(body):
        if not g.consistent:
            out.append(DeterministicFinding(
                "grim", "warning", g.raw,
                f"GRIM: mean {g.mean} is impossible for n = {g.n} (not a multiple of 1/{g.n})."))
    return out


def all_findings(body: str, references=None, *, current_year: int = 2026,
                 latex_source: bool = False) -> list[DeterministicFinding]:
    """Every deterministic check applicable to the available inputs.

    *body* is the manuscript text (extracted PDF body or .tex source).
    *references* is an optional list of extracted references.
    Set *latex_source=True* when *body* is raw LaTeX so the structure checks
    (undefined \\ref, duplicate \\label, float hygiene) run.
    """
    out: list[DeterministicFinding] = []
    out += _statcheck_findings(body)
    out += number_checks(body)
    out += open_science_checks(body)
    out += text_checks(body)
    if latex_source:
        out += structure_checks(body)
    if references:
        out += reference_integrity_from_extracted(references, current_year)
    return out
