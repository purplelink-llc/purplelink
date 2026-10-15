#!/usr/bin/env python3
"""Generate the benchmark documents. Output is deterministic (fixed seed).

Run from this folder: python3 generate.py
All generated text is written for this benchmark (CC0). Body text comes from
the lipsum package at compile time; bibliography entries are synthetic.
"""
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
rnd = random.Random(20261014)

FIRST = ["Ana", "Ben", "Chen", "Dara", "Eli", "Farid", "Gita", "Hugo", "Iris", "Jun",
         "Kofi", "Lena", "Mara", "Noor", "Omar", "Pia", "Quinn", "Rosa", "Sami", "Tara"]
LAST = ["Abbott", "Banerjee", "Castillo", "Dubois", "Eriksen", "Fofana", "Grant", "Haddad",
        "Ito", "Jovanovic", "Kowalski", "Lindqvist", "Moreau", "Nakamura", "Okafor",
        "Petrov", "Quispe", "Rinaldi", "Santos", "Tanaka"]
WORDS = ["adaptive", "sampling", "network", "estimation", "robust", "kernel", "latent",
         "structure", "inference", "learning", "graph", "temporal", "spatial", "causal",
         "ranking", "retrieval", "privacy", "detection", "calibration", "forecasting"]
JOURNALS = ["Journal of Synthetic Results", "Transactions on Example Data",
            "Annals of Placeholder Studies", "Review of Benchmark Methods"]


def bib(n):
    out = []
    for i in range(1, n + 1):
        au = " and ".join(f"{rnd.choice(LAST)}, {rnd.choice(FIRST)}" for _ in range(rnd.randint(1, 4)))
        title = " ".join(rnd.sample(WORDS, 4)).capitalize()
        year = rnd.randint(1998, 2025)
        if i % 3 == 0:
            out.append(f"@inproceedings{{ref{i:03d},\n  author = {{{au}}},\n  title = {{{title}}},\n"
                       f"  booktitle = {{Proceedings of the Synthetic Conference {year}}},\n  year = {{{year}}},\n"
                       f"  pages = {{{i}--{i + 9}}},\n}}\n")
        else:
            out.append(f"@article{{ref{i:03d},\n  author = {{{au}}},\n  title = {{{title}}},\n"
                       f"  journaltitle = {{{rnd.choice(JOURNALS)}}},\n  year = {{{year}}},\n"
                       f"  volume = {{{rnd.randint(1, 40)}}},\n  number = {{{rnd.randint(1, 6)}}},\n"
                       f"  pages = {{{i}--{i + 14}}},\n}}\n")
    return "\n".join(out)


PREAMBLE_ENGINE = r"""\usepackage{iftex}
\ifPDFTeX
  \usepackage[T1]{fontenc}
  \usepackage[utf8]{inputenc}
  \usepackage{lmodern}
\else
  \usepackage{fontspec}
\fi
"""


def w(path, text):
    p = HERE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


# ---------------------------------------------------------------- article
w("docs/article/main.tex", r"""\documentclass[11pt]{article}
""" + PREAMBLE_ENGINE + r"""\usepackage{amsmath}
\usepackage{booktabs}
\usepackage{lipsum}
\usepackage{hyperref}
\title{A short article for the compile benchmark}
\author{Purplelink LLC}
\date{October 2026}
\begin{document}
\maketitle
\begin{abstract}\lipsum[1]\end{abstract}
\section{Introduction}
\lipsum[2-5]
\input{edit}
\section{Method}
\lipsum[6-8]
\begin{equation}
  \hat{\theta} = \arg\min_{\theta} \sum_{i=1}^{n} \ell(y_i, f_\theta(x_i)) + \lambda \lVert\theta\rVert_2^2
\end{equation}
\lipsum[9-10]
\section{Results}
\begin{table}[h]
\centering
\begin{tabular}{lrr}
\toprule
Method & Accuracy & Time (s)\\
\midrule
Baseline & 0.81 & 12\\
Proposed & 0.86 & 15\\
\bottomrule
\end{tabular}
\caption{Synthetic results.}
\end{table}
\lipsum[11-16]
\end{document}
""")
w("docs/article/edit.tex", "Edit marker: alpha.\n")

# ---------------------------------------------------------------- thesis
w("docs/thesis/refs.bib", bib(150))
chapters = []
for c in range(1, 9):
    figs = []
    for f in range(1, 4):
        k = rnd.randint(4, 9)
        pts = " ".join(f"({i},{rnd.randint(1, 9)})" for i in range(k))
        figs.append(rf"""\begin{{figure}}[ht]
\centering
\begin{{tikzpicture}}[scale=0.8]
  \draw[->] (0,0) -- ({k},0) node[right]{{$x$}};
  \draw[->] (0,0) -- (0,10) node[above]{{$y$}};
  \draw[thick,blue!60!black] plot[smooth,mark=*] coordinates {{{pts}}};
  \foreach \i in {{0,...,{k - 1}}} \draw (\i,0.1) -- (\i,-0.1);
\end{{tikzpicture}}
\caption{{Synthetic series {c}.{f}.}}\label{{fig:{c}-{f}}}
\end{{figure}}""")
    cites = " ".join(
        f"\\textcite{{ref{rnd.randint(1, 150):03d}}} and \\parencite{{ref{rnd.randint(1, 150):03d},ref{rnd.randint(1, 150):03d}}} report related results. "
        for _ in range(3))
    body = f"""\\chapter{{Chapter {c} on synthetic material}}\\label{{ch:{c}}}
\\section{{Background}}
\\lipsum[{c}-{c + 7}]
{cites}
\\section{{Analysis}}
\\lipsum[{c + 8}-{c + 13}]
{figs[0]}
\\begin{{equation}}\\label{{eq:{c}}}
  \\mathcal{{L}}_{c}(\\theta) = \\sum_{{i=1}}^{{n}} \\log p(y_i \\mid x_i, \\theta) - \\frac{{1}}{{2}}\\lVert\\theta\\rVert^2
\\end{{equation}}
\\lipsum[{c + 14}-{c + 19}]
{figs[1]}
\\section{{Discussion}}
\\lipsum[{c + 20}-{c + 25}]
{figs[2]}
\\lipsum[{c + 26}-{c + 29}]
\\lipsum[{c + 30}-{c + 37}] See Figure~\\ref{{fig:{c}-1}} and Equation~\\ref{{eq:{c}}}.
"""
    w(f"docs/thesis/chapter{c}.tex", body)
    chapters.append(f"\\include{{chapter{c}}}")
w("docs/thesis/edit.tex", "Edit marker: alpha.\n")
w("docs/thesis/main.tex", r"""\documentclass[11pt,openany]{report}
""" + PREAMBLE_ENGINE + r"""\usepackage{amsmath}
\usepackage{lipsum}
\usepackage{tikz}
\usepackage[style=authoryear,backend=biber]{biblatex}
\addbibresource{refs.bib}
\usepackage{hyperref}
\title{A synthetic thesis for the compile benchmark}
\author{Purplelink LLC}
\date{October 2026}
\begin{document}
\maketitle
\tableofcontents
\listoffigures
\chapter*{Preface}
\input{edit}
\lipsum[1-2]
""" + "\n".join(chapters) + r"""
\printbibliography[heading=bibintoc]
\end{document}
""")

# ---------------------------------------------------------------- beamer
slides = []
for s in range(1, 41):
    n = rnd.randint(3, 6)
    nodes = "\n".join(
        rf"  \node[draw,rounded corners,fill=blue!{rnd.randint(5, 25)}] (n{i}) at ({i * 2.0:.1f},{rnd.choice([0, 1, -1])}) {{Step {i}}};"
        for i in range(n))
    edges = "\n".join(rf"  \draw[->] (n{i}) -- (n{i + 1});" for i in range(n - 1))
    slides.append(rf"""\begin{{frame}}{{Slide {s}: synthetic topic}}
\begin{{itemize}}
  \item \lipsum[{(s % 20) + 1}][1]
  \item \lipsum[{(s % 20) + 2}][2]
\end{{itemize}}
\begin{{center}}
\begin{{tikzpicture}}[scale=0.6, transform shape]
{nodes}
{edges}
\end{{tikzpicture}}
\end{{center}}
\end{{frame}}""")
w("docs/beamer/edit.tex", "Edit marker: alpha.\n")
w("docs/beamer/main.tex", r"""\documentclass[aspectratio=169]{beamer}
""" + PREAMBLE_ENGINE + r"""\usepackage{lipsum}
\usepackage{tikz}
\usetheme{Madrid}
\title{A 40-slide deck for the compile benchmark}
\author{Purplelink LLC}
\date{October 2026}
\begin{document}
\begin{frame}\titlepage\end{frame}
\begin{frame}{Outline}\input{edit}\tableofcontents\end{frame}
\section{Slides}
""" + "\n".join(slides) + r"""
\end{document}
""")

# ---------------------------------------------------------------- pgfplots
plots = []
for p in range(1, 13):
    a, b = rnd.randint(1, 5), rnd.randint(1, 5)
    plots.append(rf"""\begin{{figure}}[ht]
\centering
\begin{{tikzpicture}}
\begin{{axis}}[width=0.85\linewidth,height=6cm,xlabel={{$x$}},ylabel={{$f(x)$}},grid=major,legend pos=north west]
\addplot[blue,thick,domain=0:10,samples=400] {{sin(deg(x*{a}))*exp(-x/{b + 3})}};
\addplot[red,thick,domain=0:10,samples=400] {{cos(deg(x*{b}))/(1+x/{a})}};
\legend{{$f_{{{p}}}$,$g_{{{p}}}$}}
\end{{axis}}
\end{{tikzpicture}}
\caption{{Synthetic curves {p}.}}
\end{{figure}}""")
surf = r"""\begin{figure}[ht]
\centering
\begin{tikzpicture}
\begin{axis}[view={60}{30},width=0.9\linewidth,height=8cm,colormap/viridis]
\addplot3[surf,domain=-2:2,samples=35] {exp(-x^2-y^2)*cos(deg(3*x))};
\end{axis}
\end{tikzpicture}
\caption{A 35 by 35 surface.}
\end{figure}"""
w("docs/pgfplots/edit.tex", "Edit marker: alpha.\n")
w("docs/pgfplots/main.tex", r"""\documentclass[11pt]{article}
""" + PREAMBLE_ENGINE + r"""\usepackage{amsmath}
\usepackage{lipsum}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usepackage[margin=1in]{geometry}
\title{A plot-heavy paper for the compile benchmark}
\author{Purplelink LLC}
\date{October 2026}
\begin{document}
\maketitle
\input{edit}
\lipsum[1-3]
""" + "\n\\lipsum[4]\n".join(plots) + "\n" + surf + "\n" + surf.replace("35", "30") + r"""
\lipsum[5-8]
\end{document}
""")
print("generated")
