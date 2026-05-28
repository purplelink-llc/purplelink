# Purplelink LaTeX Tools — Backend

Modal serverless backend: TeX Live compile, latexdiff. Zero file retention.

## Local dev
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest -q            # unit tests (latexmk-free)

## Modal
    pip install modal && modal setup          # one-time auth
    modal run app.py::<fn>                     # ad-hoc
    modal deploy app.py                        # deploy web endpoints

## Endpoints (ASGI app `web`)
- POST /compile  — fields: file (.tex), engine=pdflatex|xelatex → application/pdf
- POST /diff     — fields: old (.tex), new (.tex), engine, legend=true|false → application/pdf

## Security
- `-no-shell-escape` + texmf `shell_escape=f`, `openin_any=p`, `openout_any=p`
- 60s per-compile timeout, cpu=1, memory=2048, max_containers=4
- Per-IP daily limit (DAILY_LIMIT in latextools/core.py)
- LuaLaTeX intentionally unsupported

## Budget
Workspace budget capped at $30 (= free credit) in the Modal dashboard.
