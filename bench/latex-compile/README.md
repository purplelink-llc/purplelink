# LaTeX compile benchmark

Wall-clock and CPU compile times for four synthetic documents, measured with `latexmk`
on one Mac. The write-up is at https://purplelink.llc/guides/latex-compile-time-benchmark-mac/.

## Documents

| Folder | What it is | Bibliography |
|---|---|---|
| `docs/article` | 5-page article, equations, one table | none |
| `docs/thesis` | 98-page report class, 8 chapters, 24 TikZ figures, 150 synthetic references | biblatex + biber |
| `docs/beamer` | 40-slide Beamer deck, one small TikZ diagram per slide | none |
| `docs/pgfplots` | 7-page paper, 12 pgfplots line plots and 2 surface plots | none |

All documents were written for this benchmark and are released under CC0.
Body text comes from the `lipsum` package at compile time. The bibliography
entries are made up. `generate.py` regenerates every file deterministically.

## Run it

```
bash run.sh            # 5 runs per cell, writes results.csv
bash run.sh 3 out.csv  # 3 runs, custom output file
python3 summarize.py results.csv
```

Needs `latexmk`, `pdflatex`, `lualatex`, `xelatex`, `biber` and `python3` on
`PATH`. The script copies each document into a temporary folder under this
directory, so the sources are never modified, and removes that folder when it
finishes.

## Method

For each document and engine:

1. One build that is not timed (fills font caches).
2. Cold: remove all auxiliary files (`latexmk -C`), then time a full `latexmk` build. Repeated N times.
3. Warm: change one line in `edit.tex`, keep the auxiliary files, then time the `latexmk` rebuild. Repeated N times.

Time is wall-clock seconds around the whole `latexmk` call, so it includes
every pass and, for the thesis, biber. Nothing else was deliberately running
during the measurement, but the Mac was not otherwise idle-controlled.

The engines are `pdflatex`, `lualatex` and `xelatex`. The documents load
`fontspec` (Latin Modern, the default) under LuaLaTeX and XeLaTeX and
`lmodern` under pdfLaTeX.
