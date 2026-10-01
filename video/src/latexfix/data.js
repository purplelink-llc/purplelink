// Content for the "fix this LaTeX error" shorts. Every string is copied from the matching page under
// site/latex-errors/<slug>/ (minimal example, log excerpt, fix); check-latexfix.mjs asserts that against the HTML.
// log: the first lines of the page's log excerpt. mark: what to highlight in the log once it has been typed.
// stages: what the second panel shows over time (source file, then the corrected source or the build commands).
//   at: beat index whose narration start anchors the stage, plus `cue` (spoken word prefix) or `dt` seconds.
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
};
