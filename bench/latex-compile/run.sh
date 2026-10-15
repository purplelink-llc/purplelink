#!/usr/bin/env bash
# Reproducible LaTeX compile benchmark. Usage: bash run.sh [runs] [output.csv]
# Builds each document with each engine through latexmk: one discarded warm-up
# build, then N cold builds (aux files removed) and N warm rebuilds (one-line
# edit, aux files kept). Wall time per build goes to the CSV.
set -euo pipefail

RUNS="${1:-5}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${2:-$HERE/results.csv}"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT";; esac
DOCS=(${DOCS:-article thesis beamer pgfplots})
ENGINES=(pdflatex lualatex xelatex)

for tool in latexmk pdflatex lualatex xelatex biber python3; do
  command -v "$tool" >/dev/null || { echo "missing $tool; install TeX Live or MacTeX first" >&2; exit 1; }
done

WORK="$(mktemp -d "$HERE/.work.XXXXXX")"
[ -d "$WORK" ] || { echo "no work dir" >&2; exit 1; }
trap 'rm -rf "${WORK:?}"' EXIT

flag() { case "$1" in pdflatex) echo -pdf;; lualatex) echo -lualatex;; xelatex) echo -xelatex;; esac; }

# Called before each cell (document, engine, cold or warm). Waits until the 1-minute load average is below the core count, for at most
# 10 minutes. Sets WAITED to "no" (already quiet), "yes" (waited, then quiet)
# or "gave_up" (still busy after 10 minutes, measured anyway). Never touches
# other processes.
NCPU="$(sysctl -n hw.ncpu)"
quiet() {
  local i=0 l
  WAITED=no
  while :; do
    l="$(sysctl -n vm.loadavg | awk '{print int($2)}')"
    if [ "$l" -lt "$NCPU" ]; then return 0; fi
    WAITED=yes
    if [ "$i" -ge 120 ]; then WAITED=gave_up; return 0; fi
    sleep 5; i=$((i + 1))
  done
}

# Prints wall-clock seconds and CPU seconds (user+sys) for one latexmk run in
# the current directory. CPU time moves much less than wall time when other
# processes compete for the cores.
build() {
  python3 - "$@" <<'PY'
import resource, subprocess, sys, time
t = time.perf_counter()
cmd = ["latexmk", sys.argv[1], "-interaction=nonstopmode", "-halt-on-error", "main.tex"]
r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
dt = time.perf_counter() - t
if r.returncode != 0:
    sys.stderr.write("build failed, retrying once\n")
    t = time.perf_counter()
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dt = time.perf_counter() - t
    if r.returncode != 0:
        sys.exit("build failed twice")
c = resource.getrusage(resource.RUSAGE_CHILDREN)
print(f"{dt:.3f} {c.ru_utime + c.ru_stime:.3f}")
PY
}

{
  echo "# machine: $(sysctl -n machdep.cpu.brand_string), $(( $(sysctl -n hw.memsize) / 1073741824 )) GB, macOS $(sw_vers -productVersion)"
  echo "# $(pdflatex --version | head -1); $(latexmk -v | grep -m1 -i 'latexmk, john')"
  echo "# runs per cell: $RUNS; date: $(date +%Y-%m-%d)"
  echo "doc,engine,mode,run,seconds,cpu_seconds,pages,load1,waited"
} > "$OUT"

for doc in "${DOCS[@]}"; do
  for eng in "${ENGINES[@]}"; do
    dir="$WORK/$doc-$eng"
    mkdir -p "$dir"
    cp -R "$HERE/docs/$doc/." "$dir/"
    cd "$dir"
    f="$(flag "$eng")"
    build "$f" >/dev/null                      # warm-up, discarded (font caches)
    pages="$(grep -a -o '([0-9]* pages' main.log | tail -1 | tr -dc '0-9')"
    quiet
    for i in $(seq 1 "$RUNS"); do
      latexmk -C >/dev/null 2>&1
      t="$(build "$f")"
      printf '%s,%s,cold,%s,%s,%s,%s,%s\n' "$doc" "$eng" "$i" "${t// /,}" "$pages" "$(sysctl -n vm.loadavg | awk '{print $2}')" "$WAITED" >> "$OUT"
    done
    quiet
    for i in $(seq 1 "$RUNS"); do
      printf 'Edit marker: run %s.\n' "$i" > edit.tex
      t="$(build "$f")"
      printf '%s,%s,warm,%s,%s,%s,%s,%s\n' "$doc" "$eng" "$i" "${t// /,}" "$pages" "$(sysctl -n vm.loadavg | awk '{print $2}')" "$WAITED" >> "$OUT"
    done
    cd "$HERE"
    echo "done $doc $eng" >&2
  done
done
echo "wrote $OUT" >&2
