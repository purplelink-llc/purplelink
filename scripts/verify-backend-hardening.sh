#!/usr/bin/env bash
# Live check of the pandoc confinement (docs: backend/latextools/texflatten.py).
# Run it against the deployed Modal web function after `python3 -m modal deploy`.
# It sends about 9 requests, so it fits inside the 25-per-day limit of /convert
# only once a day from one address; the other endpoints have their own counters.
#
#   bash scripts/verify-backend-hardening.sh [BASE_URL]
#
# Needs: curl, zip, unzip. Prints PASS or FAIL per check; exits 1 if any failed.
set -u
BASE="${1:-https://ben-ampel--purplelink-latextools-web.modal.run}"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
fail=0
pass() { echo "PASS  $1"; }
bad()  { echo "FAIL  $1"; fail=1; }

docx_text() { unzip -p "$1" word/document.xml 2>/dev/null; }

# --- project 1: main.tex + sub.tex + refs.bib + a figure ---------------------
mkdir "$W/p1" && cd "$W/p1"
cat > main.tex <<'T'
\documentclass{article}
\begin{document}
\title{Probe}\author{A. Author}\maketitle
\section{One}
Body text with a citation \cite{k1}.
\input{sub}
\includegraphics[width=2cm]{fig.png}
\bibliographystyle{plain}
\bibliography{refs}
\end{document}
T
printf 'SUBFILE_MARKER_OK in the sub file.\n' > sub.tex
cat > refs.bib <<'T'
@article{k1, author={Doe, Jane}, title={BIBTITLE_MARKER}, journal={Journal}, year={2020}}
T
# 1x1 PNG
printf 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==' | base64 -d > fig.png
zip -q ../p1.zip main.tex sub.tex refs.bib fig.png
cd "$W"

code=$(curl -s -o r1.docx -w '%{http_code}' -F "file=@p1.zip" "$BASE/convert")
if [ "$code" = 200 ]; then pass "relative \\input in a ZIP converts (HTTP 200)"; else bad "project ZIP convert returned HTTP $code"; fi
docx_text r1.docx | grep -q SUBFILE_MARKER_OK && pass "SUBFILE_MARKER_OK is in the docx" || bad "SUBFILE_MARKER_OK missing from the docx"
docx_text r1.docx | grep -q BIBTITLE_MARKER && pass "citation and bibliography from refs.bib (citeproc) work" || bad "bibliography entry missing (citeproc or --bibliography broke)"
unzip -l r1.docx 2>/dev/null | grep -q 'word/media/' && pass "figure is embedded (word/media present)" || bad "figure not embedded"

# --- project 2: absolute and traversal includes must produce nothing ---------
mkdir "$W/p2" && cd "$W/p2"
cat > main.tex <<'T'
\documentclass{article}
\begin{document}
START_MARKER
\input{/etc/os-release}
\input{/proc/self/environ}
\input{../../etc/passwd}
\includegraphics{/etc/os-release}
END_MARKER
\end{document}
T
zip -q ../p2.zip main.tex; cd "$W"
code=$(curl -s -o r2.docx -w '%{http_code}' -F "file=@p2.zip" "$BASE/convert")
if [ "$code" = 200 ]; then
  t=$(docx_text r2.docx)
  echo "$t" | grep -q START_MARKER && pass "document still converts" || bad "document body missing"
  if echo "$t" | grep -qiE 'PRETTY_NAME|debian|root:x|STRIPE|RESEND|SUBSCRIBE_SECRET'; then bad "file or environment content leaked into the docx"; else pass "absolute and ../ includes produced nothing (no os-release, passwd or environment text)"; fi
else bad "p2 convert returned HTTP $code (expected 200 with the includes removed)"; fi

# --- single .tex upload with an absolute include ------------------------------
printf '\\documentclass{article}\\begin{document}SINGLE_OK \\input{/etc/os-release}\\end{document}\n' > single.tex
code=$(curl -s -o r3.docx -w '%{http_code}' -F "file=@single.tex" "$BASE/convert")
if [ "$code" = 200 ] && docx_text r3.docx | grep -q SINGLE_OK && ! docx_text r3.docx | grep -qi PRETTY_NAME; then pass "single .tex with absolute include: converts, nothing leaked"; else bad "single .tex check (HTTP $code)"; fi

# --- markdown-convert: docx with a local and a remote image --------------------
printf '# Title\n\nMD_OK\n\n![a](/etc/os-release)\n\n![b](http://127.0.0.1:9/x.png)\n' > t.md
code=$(curl -s -o m.docx -w '%{http_code}' -F "file=@t.md" -F target=docx "$BASE/markdown-convert")
if [ "$code" = 200 ] && docx_text m.docx | grep -q MD_OK && ! unzip -l m.docx | grep -q 'word/media/'; then pass "markdown to docx works, no local or remote image embedded"; else bad "markdown to docx (HTTP $code)"; fi
code=$(curl -s -o m.pdf -w '%{http_code}' -F "file=@t.md" -F target=pdf "$BASE/markdown-convert")
if [ "$code" = 200 ] && head -c 5 m.pdf | grep -q '%PDF-'; then pass "markdown to pdf works"; else bad "markdown to pdf (HTTP $code)"; fi

# --- word-to-latex using the first docx as input -------------------------------
code=$(curl -s -o w.tex -w '%{http_code}' -F "file=@r1.docx" "$BASE/word-to-latex")
if [ "$code" = 200 ] && grep -q 'SUBFILE.\{0,2\}MARKER.\{0,2\}OK' w.tex; then pass "word to latex works"; else bad "word to latex (HTTP $code)"; fi

echo
if [ "$fail" = 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit "$fail"
