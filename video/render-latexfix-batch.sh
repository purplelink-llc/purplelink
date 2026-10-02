#!/bin/zsh
# zsh render-latexfix-batch.sh <slug> [<slug> ...] : renders the given LaTeX error shorts strictly one after the
# other (never in parallel), appending a summary of each to .cache/latexfix-batch.log and continuing past failures.
export PATH="$HOME/.nvm/versions/node/v26.2.0/bin:$PATH"
cd "$(dirname "$0")" || exit 1
mkdir -p .cache
LOG=.cache/latexfix-batch.log
for s in "$@"; do
  if node build-latexfix.mjs "$s" --skip-narrate > ".cache/$s-build.out" 2>&1; then
    grep -E "beats|narration [0-9]|WARN|render|poster|total:" ".cache/$s-build.out" >> "$LOG" 2>/dev/null
    echo "== done $s" >> "$LOG"
  else
    tail -5 ".cache/$s-build.out" >> "$LOG" 2>/dev/null
    echo "== FAILED $s" >> "$LOG"
  fi
done
echo ALLDONE >> "$LOG"
