// Content for the "fix this LaTeX error" shorts. Every string is copied from the matching page under
// site/latex-errors/<slug>/ (minimal example, log excerpt, fix); check-latexfix.mjs asserts that against the HTML.
// log: the first lines of the page's log excerpt. mark: what to highlight in the log once it has been typed.
// stages: what the second panel shows over time (source file, then the corrected source or the build commands).
//   at: beat index whose narration start anchors the stage, plus `cue` (spoken word prefix) or `dt` seconds.
//   lines: "file" means the minimal example (`file`); `start` is the first line number shown.
// cps: typing speed for long excerpts. size16: code px in 16:9 when the panels would not fit at 36.
// derived: lines not quoted verbatim on the page (the example with the page's stated fix applied).
const SRC = "main.tex";

export const ERRORS = {
  "undefined-control-sequence": {
    name: "Undefined control sequence",
    log: [
      "! Undefined control sequence.",
      "l.3 The effect is \\textbf{large} and \\emhp",
      "                                          {robust} across samples.",
    ],
    mark: { line: 1, token: "\\emhp", beat: 1, cue: "command" },
    stages: [
      {
        title: SRC, gutter: true, beat: 1, dt: 0,
        lines: ["\\documentclass{article}", "\\begin{document}", "The effect is \\textbf{large} and \\emhp{robust} across samples.", "\\end{document}"],
        hi: { line: 2, token: "\\emhp", kind: "bad", beat: 1, cue: "command" },
      },
      {
        title: SRC, gutter: true, beat: 2, cue: "emph",
        lines: ["\\documentclass{article}", "\\begin{document}", "The effect is \\textbf{large} and \\emph{robust} across samples.", "\\end{document}"],
        hi: { line: 2, token: "\\emph", kind: "good" },
      },
    ],
    // The page states the fix in prose ("\\emhp, a typo for \\emph"); the corrected line is the example with that one change.
    derived: ["The effect is \\textbf{large} and \\emph{robust} across samples."],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "missing-dollar-inserted": {
    name: "Missing $ inserted",
    log: [
      "! Missing $ inserted.",
      "<inserted text>",
      "                $",
      "l.3 The results are saved in output_",
      "                                    final.csv for each run.",
    ],
    mark: { line: 3, token: "_", last: true, beat: 1, cue: "underscore" },
    stages: [
      {
        title: SRC, gutter: true, beat: 1, dt: 0,
        lines: ["\\documentclass{article}", "\\begin{document}", "The results are saved in output_final.csv for each run.", "\\end{document}"],
        hi: { line: 2, token: "output_final.csv", kind: "bad", beat: 1, cue: "underscore" },
      },
      {
        title: SRC, gutter: true, beat: 2, cue: "backslash",
        lines: ["\\documentclass{article}", "\\begin{document}", "The results are saved in output\\_final.csv for each run.", "\\end{document}"],
        hi: { line: 2, token: "output\\_final.csv", kind: "good" },
      },
    ],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "citation-undefined": {
    name: "Citation undefined",
    warning: true,
    log: ["LaTeX Warning: Citation `smith2024' on page 1 undefined on input line 3.", "No file main.bbl."],
    mark: { line: 1, token: "No file main.bbl.", beat: 1, cue: "clue" },
    stages: [
      {
        title: SRC, gutter: true, beat: 1, dt: 0,
        lines: ["\\documentclass{article}", "\\begin{document}", "Earlier work \\cite{smith2024} found the same pattern.", "\\bibliographystyle{plain}", "\\bibliography{refs}", "\\end{document}"],
        hi: { line: 2, token: "\\cite{smith2024}", kind: "note", beat: 1, dt: 0.5 },
      },
      {
        title: "Terminal", gutter: false, beat: 1, cue: "bibtex", lead: 0.5,
        label: "Before",
        lines: ["pdflatex main"],
        hi: { line: 0, token: "pdflatex main", kind: "bad" },
      },
      {
        title: "Terminal", gutter: false, beat: 2, dt: 0.3,
        label: "After",
        lines: ["pdflatex main && bibtex main", "pdflatex main && pdflatex main"],
        hi: { line: 0, token: "bibtex main", kind: "good", alsoLine: 1 },
      },
    ],
    ok: { head: "Compiles", sub: "No undefined references." },
  },
  "environment-undefined": {
    name: "Environment theorem undefined",
    cps: 60,
    size16: 34,
    file: ["\\documentclass{article}", "\\begin{document}", "\\begin{theorem}", "Every bounded sequence has a convergent subsequence.", "\\end{theorem}", "\\end{document}"],
    log: [
      "! LaTeX Error: Environment theorem undefined.",
      "See the LaTeX manual or LaTeX Companion for explanation.",
      "Type  H <return>  for immediate help.",
      " ...",
      "l.3 \\begin{theorem}",
    ],
    mark: { line: 4, token: "\\begin{theorem}", beat: 1, cue: "line" },
    stages: [
      { title: SRC, gutter: true, beat: 1, dt: 0, lines: "file", hi: { line: 2, token: "\\begin{theorem}", kind: "bad", beat: 1, cue: "begin" } },
      { title: SRC, gutter: false, beat: 2, cue: "declare", label: "After", lines: ["\\newtheorem{theorem}{Theorem} % in the preamble", "\\begin{theorem}"], hi: { line: 0, token: "\\newtheorem{theorem}{Theorem}", kind: "good" } },
    ],
    // The page gives the fix in prose ("declared with \\newtheorem in the preamble") and shows the lemma case in code.
    derived: ["\\newtheorem{theorem}{Theorem} % in the preamble"],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "extra-alignment-tab": {
    name: "Extra alignment tab has been changed to \\cr",
    size16: 34,
    file: ["\\documentclass{article}", "\\begin{document}", "\\begin{tabular}{ll}", "Model & Accuracy & F1 \\\\", "Baseline & 0.81 & 0.77 \\\\", "\\end{tabular}", "\\end{document}"],
    log: ["! Extra alignment tab has been changed to \\cr.", "<recently read> \\endtemplate", "l.4 Model & Accuracy &", "                       F1 \\\\"],
    mark: { line: 2, token: "&", last: true, beat: 1, cue: "ampersand" },
    stages: [
      { title: SRC, gutter: true, beat: 1, dt: 0, lines: "file", hi: { line: 3, token: "&", last: true, kind: "bad", beat: 1, cue: "three" } },
      { title: SRC, gutter: true, beat: 2, cue: "add", lines: ["\\documentclass{article}", "\\begin{document}", "\\begin{tabular}{lll}", "Model & Accuracy & F1 \\\\", "Baseline & 0.81 & 0.77 \\\\", "\\end{tabular}", "\\end{document}"], hi: { line: 2, token: "{lll}", kind: "good" } },
    ],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "file-not-found": {
    name: "File `graphicsx.sty' not found",
    file: ["\\documentclass{article}", "\\usepackage{graphicsx}", "\\begin{document}", "A figure goes here.", "\\end{document}"],
    log: ["! LaTeX Error: File `graphicsx.sty' not found.", "Type X to quit or <RETURN> to proceed,", "or enter new name. (Default extension: sty)", "Enter file name:", "! Emergency stop."],
    mark: { line: 0, token: "graphicsx.sty", beat: 1, cue: "names" },
    stages: [
      { title: SRC, gutter: true, beat: 1, dt: 0, lines: "file", hi: { line: 1, token: "graphicsx", kind: "bad", beat: 1, cue: "typo" } },
      { title: SRC, gutter: true, beat: 2, cue: "fix", lines: ["\\documentclass{article}", "\\usepackage{graphicx}", "\\begin{document}", "A figure goes here.", "\\end{document}"], hi: { line: 1, token: "graphicx", kind: "good" } },
    ],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "misplaced-alignment-tab": {
    name: "Misplaced alignment tab character &",
    file: ["\\documentclass{article}", "\\begin{document}", "This follows Smith & Jones (2024).", "\\end{document}"],
    log: ["! Misplaced alignment tab character &.", "l.3 This follows Smith &", "                         Jones (2024)."],
    mark: { line: 1, token: "&", last: true, beat: 1, cue: "ampersand" },
    stages: [
      { title: SRC, gutter: true, beat: 1, dt: 0, lines: "file", hi: { line: 2, token: "&", kind: "bad", beat: 1, cue: "outside" } },
      { title: SRC, gutter: true, beat: 2, cue: "type", lines: ["\\documentclass{article}", "\\begin{document}", "This follows Smith \\& Jones (2024).", "\\end{document}"], hi: { line: 2, token: "\\&", kind: "good" } },
    ],
    // The page states the fix as "type \\&"; the corrected line is the example with that one change.
    derived: ["This follows Smith \\& Jones (2024)."],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "missing-begin-document": {
    name: "Missing \\begin{document}",
    file: ["\\documentclass{article}", "\\usepackage{amsmath}", "Draft of the introduction.", "\\begin{document}", "Body text.", "\\end{document}"],
    log: ["! LaTeX Error: Missing \\begin{document}.", " ...", "l.3 D", "     raft of the introduction."],
    mark: { line: 2, token: "D", last: true, beat: 1, cue: "d" },
    stages: [
      { title: SRC, gutter: true, beat: 1, dt: 0, lines: "file", hi: { line: 2, token: "Draft of the introduction.", kind: "bad", beat: 1, cue: "text" } },
      { title: SRC, gutter: true, beat: 2, cue: "comment", lines: ["\\documentclass{article}", "\\usepackage{amsmath}", "% Draft of the introduction.", "\\begin{document}", "Body text.", "\\end{document}"], hi: { line: 2, token: "% Draft of the introduction.", kind: "good" } },
    ],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "overfull-hbox": {
    name: "Overfull \\hbox",
    warning: true,
    cps: 95,
    file: ["\\documentclass{article}", "\\begin{document}", "The replication files are available from the project repository at", "\\texttt{https://example.org/research/replication-archive/2026/final-dataset-v2.tar.gz}", "for anyone who wants to rerun the analysis.", "\\end{document}"],
    log: [
      "Overfull \\hbox (345.63582pt too wide) in paragraph at lines 3--6",
      "[]\\OT1/cmr/m/n/10 The repli-ca-tion files are avail-able from the project repos-i-tory at \\OT1/cmtt/m/n/10 https://example.org/research/replication-archive/2026/final-dataset-v2.tar.gz",
      " []",
    ],
    mark: { line: 0, token: "345.63582pt too wide", beat: 1, cue: "345" },
    stages: [
      { title: SRC, gutter: true, start: 3, beat: 1, dt: 0, lines: ["The replication files are available from the project repository at", "\\texttt{https://example.org/research/replication-archive/2026/final-dataset-v2.tar.gz}", "for anyone who wants to rerun the analysis."], hi: { line: 1, token: "\\texttt{https://example.org/research/replication-archive/2026/final-dataset-v2.tar.gz}", kind: "note", beat: 1, cue: "text" } },
      { title: SRC, gutter: false, beat: 2, cue: "load", label: "After", lines: ["\\usepackage{xurl} % in the preamble", "\\url{https://example.org/research/replication-archive/2026/final-dataset-v2.tar.gz}"], hi: { line: 0, token: "\\usepackage{xurl}", kind: "good", alsoLine: 1 } },
    ],
    ok: { head: "Compiles", sub: "No overfull boxes." },
  },
  "paragraph-ended-before-complete": {
    name: "Paragraph ended before \\label was complete",
    size16: 32,
    file: ["\\documentclass{article}", "\\begin{document}", "\\section{Methods}\\label{sec:methods", "", "We use two samples.", "\\end{document}"],
    log: ["Runaway argument?", "{sec:methods", "! Paragraph ended before \\label was complete.", "<to be read again>", "                   \\par", "l.4"],
    mark: { line: 1, token: "{sec:methods", beat: 1, cue: "collected" },
    stages: [
      { title: SRC, gutter: true, beat: 1, dt: 0, lines: "file", hi: { line: 2, token: "\\label{sec:methods", kind: "bad", beat: 1, cue: "brace" } },
      { title: SRC, gutter: true, beat: 2, cue: "close", lines: ["\\documentclass{article}", "\\begin{document}", "\\section{Methods}\\label{sec:methods}", "", "We use two samples.", "\\end{document}"], hi: { line: 2, token: "\\label{sec:methods}", kind: "good" } },
    ],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "runaway-argument": {
    name: "Runaway argument",
    cps: 70,
    size16: 32,
    file: ["\\documentclass{article}", "\\begin{document}", "\\section{Related work", "", "Prior studies report mixed results.", "\\end{document}"],
    log: ["Runaway argument?", "{Related work \\par Prior studies report mixed results. \\end {document\\ETC.", "! File ended while scanning use of \\@xdblarg.", "<inserted text>", "                \\par", "<*> main.tex"],
    mark: { line: 1, token: "{Related work", beat: 1, cue: "swallowed" },
    stages: [
      { title: SRC, gutter: true, beat: 1, dt: 0, lines: "file", hi: { line: 2, token: "\\section{Related work", kind: "bad", beat: 1, cue: "never" } },
      { title: SRC, gutter: true, beat: 2, cue: "close", lines: ["\\documentclass{article}", "\\begin{document}", "\\section{Related work}", "", "Prior studies report mixed results.", "\\end{document}"], hi: { line: 2, token: "\\section{Related work}", kind: "good" } },
    ],
    // The page states the fix in prose ("a closing brace is missing"); the corrected line is the example with the brace added.
    derived: ["\\section{Related work}"],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
  "too-many-closing-braces": {
    name: "Too many }'s",
    file: ["\\documentclass{article}", "\\begin{document}", "The term \\emph{endogeneity}} is defined in Section 2.", "\\end{document}"],
    log: ["! Too many }'s.", "<recently read> }", "l.3 The term \\emph{endogeneity}}", "                                 is defined in Section 2.", "You've closed more groups than you opened."],
    mark: { line: 2, token: "}", last: true, beat: 1, cue: "second" },
    stages: [
      { title: SRC, gutter: true, beat: 1, dt: 0, lines: "file", hi: { line: 2, token: "\\emph{endogeneity}}", kind: "bad", beat: 1, cue: "partner" } },
      { title: SRC, gutter: true, beat: 2, cue: "delete", lines: ["\\documentclass{article}", "\\begin{document}", "The term \\emph{endogeneity} is defined in Section 2.", "\\end{document}"], hi: { line: 2, token: "\\emph{endogeneity}", kind: "good" } },
    ],
    // The page's fix removes the extra brace; the corrected line is the example with that one change.
    derived: ["The term \\emph{endogeneity} is defined in Section 2."],
    ok: { head: "Compiles", sub: "No errors in the log." },
  },
};

for (const E of Object.values(ERRORS)) for (const st of E.stages) if (st.lines === "file") st.lines = E.file;
