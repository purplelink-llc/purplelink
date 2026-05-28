# LaTeX Tools — Plan 1: Foundation + Compile Tools

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a live `/tools/` section on purplelink.llc with two working tools — LaTeX→PDF compile and LaTeX diff — backed by a security-hardened Modal serverless service.

**Architecture:** A Python backend (`backend/`) deployed to Modal: one pinned Docker image with TeX Live + latexmk + latexdiff, pure-logic modules that are unit-tested without the TeX toolchain, and a FastAPI ASGI app exposing `POST /compile` and `POST /diff` with CORS, per-IP rate limiting (Modal Dict), and zero file retention. A static frontend (`site/tools/`) of vanilla-JS pages matching the existing site, calling the Modal endpoints via `fetch`.

**Tech Stack:** Python 3.11, Modal, FastAPI, pytest; TeX Live (pdfLaTeX/XeLaTeX), latexmk, latexdiff; static HTML/CSS/vanilla JS; Netlify.

**Spec:** `docs/superpowers/specs/2026-05-28-latex-tools-design.md`

---

## File Structure

**Backend (new, repo root `backend/`):**
- `backend/latextools/__init__.py` — package marker.
- `backend/latextools/core.py` — pure, TeX-free logic: upload validation, latexmk/latexdiff command building, log parsing, diff-legend injection, rate-limit accounting. Unit-tested directly.
- `backend/latextools/runner.py` — subprocess execution of latexmk/latexdiff in a working dir (the only module that needs the TeX toolchain).
- `backend/app.py` — Modal app: image definition, the compile/diff Modal functions, the FastAPI ASGI endpoint, rate limiting via `modal.Dict`.
- `backend/texmf.cnf` — TeX hardening config baked into the image.
- `backend/requirements-dev.txt` — local test deps (pytest, fastapi).
- `backend/pytest.ini` — pytest config.
- `backend/tests/conftest.py` — fixture paths.
- `backend/tests/fixtures/*.tex` — sample documents (clean, error, security probes).
- `backend/tests/test_core.py` — unit tests for `core.py`.
- `backend/tests/test_runner_integration.py` — integration tests (skipped unless `latexmk` present).
- `backend/README.md` — deploy/run instructions.

**Frontend (new, under `site/`):**
- `site/tools/index.html` — hub page (three cards).
- `site/tools/latex-to-pdf/index.html` — compile tool page.
- `site/tools/latex-diff/index.html` — diff tool page.
- `site/tools/tools.js` — shared upload/fetch/result logic for tool pages.
- `site/styles.css` — append tools-section CSS (modify).

**Frontend (modify existing):**
- All 14 pages containing the primary nav — add a "Tools" link.
- `site/netlify.toml` — add `connect-src` for the Modal endpoint.
- `site/sitemap.xml` — add the four new URLs.
- `site/llms.txt` — add a Tools section.

**Config constant used throughout:** the Modal endpoint base URL is written **once** in `site/tools/tools.js` as `const API_BASE = "https://ben-ampel--purplelink-latextools-web.modal.run";` and referenced by all pages. The exact subdomain is produced by `modal deploy` in Task 9 — Task 13 updates this constant and the CSP with the real value.

---

## Task 1: Backend project scaffold + pure validation logic

**Files:**
- Create: `backend/latextools/__init__.py`
- Create: `backend/latextools/core.py`
- Create: `backend/requirements-dev.txt`
- Create: `backend/pytest.ini`
- Test: `backend/tests/test_core.py`

- [ ] **Step 1: Create the dev dependency and pytest config files**

`backend/requirements-dev.txt`:
```
pytest==8.3.3
fastapi==0.115.2
```

`backend/pytest.ini` (the `pythonpath = .` line puts `backend/` on sys.path so `from latextools import core` resolves; do NOT create `tests/__init__.py` — `tests/` must stay a non-package so `conftest.py` fixtures are discovered):
```ini
[pytest]
testpaths = tests
python_files = test_*.py
pythonpath = .
```

`backend/latextools/__init__.py`: (empty file)

- [ ] **Step 2: Create the dev environment and confirm pytest runs**

Run:
```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt && pytest -q
```
Expected: pytest collects 0 items and exits 0 ("no tests ran").

- [ ] **Step 3: Write the failing test for upload validation**

`backend/tests/test_core.py`:
```python
import pytest
from latextools import core


def test_validate_upload_accepts_tex():
    core.validate_upload("paper.tex", 1024)  # should not raise


def test_validate_upload_rejects_wrong_extension():
    with pytest.raises(core.ValidationError, match="must be a .tex file"):
        core.validate_upload("paper.pdf", 1024)


def test_validate_upload_rejects_too_large():
    with pytest.raises(core.ValidationError, match="too large"):
        core.validate_upload("paper.tex", core.MAX_UPLOAD_BYTES + 1)


def test_validate_upload_rejects_empty():
    with pytest.raises(core.ValidationError, match="empty"):
        core.validate_upload("paper.tex", 0)


def test_validate_upload_rejects_path_traversal_name():
    with pytest.raises(core.ValidationError, match="invalid filename"):
        core.validate_upload("../../etc/passwd.tex", 10)
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -q`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError: module 'latextools.core' has no attribute 'validate_upload'`.

- [ ] **Step 5: Implement validation in core.py**

`backend/latextools/core.py`:
```python
"""Pure, dependency-free logic for the LaTeX tools backend.

Nothing in this module shells out or imports Modal/TeX. It is unit-tested
directly so the security-critical decisions (validation, command building,
log parsing) have fast, deterministic coverage.
"""
from __future__ import annotations

import os
import re

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB hard cap (matches spec)


class ValidationError(Exception):
    """Raised when an uploaded file fails a safety/format check."""


def validate_upload(filename: str, size_bytes: int) -> None:
    """Validate an uploaded LaTeX file's name and size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    base = os.path.basename(filename)
    if base != filename or base in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not base.lower().endswith(".tex"):
        raise ValidationError("File must be a .tex file.")
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -q`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/latextools/__init__.py backend/latextools/core.py \
  backend/requirements-dev.txt backend/pytest.ini backend/tests/test_core.py
git commit -m "feat(backend): scaffold latextools package with upload validation"
```

---

## Task 2: latexmk command builder (engine selection + hardening flags)

**Files:**
- Modify: `backend/latextools/core.py`
- Test: `backend/tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_core.py`:
```python
def test_latexmk_command_pdflatex_default():
    cmd = core.build_latexmk_command("pdflatex", "main")
    assert cmd[0] == "latexmk"
    assert "-pdf" in cmd
    assert "-interaction=nonstopmode" in cmd
    assert "-no-shell-escape" in cmd
    assert cmd[-1] == "main.tex"


def test_latexmk_command_xelatex():
    cmd = core.build_latexmk_command("xelatex", "main")
    assert "-xelatex" in cmd
    assert "-pdf" not in cmd
    assert "-no-shell-escape" in cmd


def test_latexmk_command_rejects_unknown_engine():
    with pytest.raises(core.ValidationError, match="unsupported engine"):
        core.build_latexmk_command("lualatex", "main")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -k latexmk_command -q`
Expected: FAIL with `AttributeError: ... has no attribute 'build_latexmk_command'`.

- [ ] **Step 3: Implement the command builder**

Append to `backend/latextools/core.py`:
```python
# Engine name -> latexmk engine flag. LuaLaTeX deliberately excluded (spec §RCE).
_ENGINE_FLAGS = {
    "pdflatex": "-pdf",
    "xelatex": "-xelatex",
}


def build_latexmk_command(engine: str, jobname: str) -> list[str]:
    """Build the latexmk argv for a hardened single-file compile.

    -no-shell-escape disables \\write18. File-read/write confinement is set
    via texmf.cnf (openin_any/openout_any=p) baked into the image.
    """
    flag = _ENGINE_FLAGS.get(engine)
    if flag is None:
        raise ValidationError(f"unsupported engine: {engine}")
    return [
        "latexmk",
        flag,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-no-shell-escape",
        "-file-line-error",
        f"{jobname}.tex",
    ]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -k latexmk_command -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/latextools/core.py backend/tests/test_core.py
git commit -m "feat(backend): add hardened latexmk command builder"
```

---

## Task 3: LaTeX log parser (plain-language diagnostics)

**Files:**
- Modify: `backend/latextools/core.py`
- Test: `backend/tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_core.py`:
```python
SAMPLE_LOG = r"""
This is pdfTeX, Version 3.141592653
(./main.tex
LaTeX Font Info: ...
main.tex:12: Undefined control sequence.
l.12 \badcommand
                 here
main.tex:40: Missing $ inserted.
Output written on main.pdf (2 pages).
"""


def test_parse_latex_log_extracts_errors():
    errors = core.parse_latex_log(SAMPLE_LOG)
    assert len(errors) == 2
    assert errors[0]["line"] == 12
    assert "Undefined control sequence" in errors[0]["message"]
    assert errors[1]["line"] == 40


def test_parse_latex_log_no_errors_returns_empty():
    assert core.parse_latex_log("Output written on main.pdf (1 page).") == []


def test_parse_latex_log_truncates_to_cap():
    big = "\n".join(f"main.tex:{i}: Error number {i}." for i in range(1, 50))
    errors = core.parse_latex_log(big)
    assert len(errors) == core.MAX_REPORTED_ERRORS
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -k parse_latex_log -q`
Expected: FAIL with `AttributeError: ... 'parse_latex_log'`.

- [ ] **Step 3: Implement the parser**

Append to `backend/latextools/core.py`:
```python
MAX_REPORTED_ERRORS = 20

# With -file-line-error, errors look like:  main.tex:12: Undefined control sequence.
_FILE_LINE_ERROR = re.compile(r"^(?P<file>[^:\n]+\.tex):(?P<line>\d+):\s*(?P<msg>.+)$")


def parse_latex_log(log_text: str) -> list[dict]:
    """Extract structured errors from a latexmk/pdflatex log.

    Returns a list of {"file", "line", "message"} dicts, capped at
    MAX_REPORTED_ERRORS. Returns [] when no errors are found.
    """
    errors: list[dict] = []
    for raw in log_text.splitlines():
        m = _FILE_LINE_ERROR.match(raw.strip())
        if not m:
            continue
        errors.append(
            {
                "file": m.group("file"),
                "line": int(m.group("line")),
                "message": m.group("msg").strip(),
            }
        )
        if len(errors) >= MAX_REPORTED_ERRORS:
            break
    return errors
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -k parse_latex_log -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/latextools/core.py backend/tests/test_core.py
git commit -m "feat(backend): add LaTeX log parser for diagnostics"
```

---

## Task 4: latexdiff command builder + diff-legend injection

**Files:**
- Modify: `backend/latextools/core.py`
- Test: `backend/tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_core.py`:
```python
def test_latexdiff_command_has_safe_defaults():
    cmd = core.build_latexdiff_command("old.tex", "new.tex")
    assert cmd[0] == "latexdiff"
    assert "--type=UNDERLINE" in cmd
    # tabular treated as opaque to avoid "Missing \\cr" table corruption
    assert any("PICTUREENV" in a and "tabular" in a for a in cmd)
    assert cmd[-2:] == ["old.tex", "new.tex"]


def test_inject_diff_legend_after_maketitle():
    src = r"\begin{document}" "\n" r"\maketitle" "\n" r"Body" "\n" r"\end{document}"
    out = core.inject_diff_legend(src)
    assert r"\maketitle" in out
    assert "How to read this revision diff" in out
    assert out.index("How to read") > out.index(r"\maketitle")


def test_inject_diff_legend_noop_without_maketitle():
    src = r"\begin{document}" "\n" r"Body" "\n" r"\end{document}"
    assert core.inject_diff_legend(src) == src
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -k "latexdiff_command or diff_legend" -q`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Implement both functions**

Append to `backend/latextools/core.py`:
```python
_PICTUREENV = r"PICTUREENV=(?:picture|DIFnomarkup|tabular)[\w\d*@]*"

_DIFF_LEGEND = (
    r"\fbox{\parbox{0.9\linewidth}{\textbf{How to read this revision diff:} "
    r"\textcolor{blue}{\uwave{blue underlined text}} was added; "
    r"\textcolor{red}{\sout{red struck-through text}} was deleted. "
    r"Changes inside tables are shown in final form only.}}"
)


def build_latexdiff_command(old_name: str, new_name: str) -> list[str]:
    """Build the latexdiff argv with table-safe defaults (spec §latex-diff)."""
    return [
        "latexdiff",
        "--type=UNDERLINE",
        f"--config={_PICTUREENV}",
        old_name,
        new_name,
    ]


def inject_diff_legend(diff_tex: str) -> str:
    r"""Insert a 'how to read this diff' box immediately after \maketitle.

    No-op if the document has no \maketitle.
    """
    marker = r"\maketitle"
    idx = diff_tex.find(marker)
    if idx == -1:
        return diff_tex
    insert_at = idx + len(marker)
    return diff_tex[:insert_at] + "\n" + _DIFF_LEGEND + "\n" + diff_tex[insert_at:]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -k "latexdiff_command or diff_legend" -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/latextools/core.py backend/tests/test_core.py
git commit -m "feat(backend): add latexdiff command builder and legend injection"
```

---

## Task 5: Per-IP rate-limit accounting (pure)

**Files:**
- Modify: `backend/latextools/core.py`
- Test: `backend/tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_core.py`:
```python
def test_rate_limit_key_is_stable_and_hashed():
    k1 = core.rate_limit_key("203.0.113.7", day="2026-05-28")
    k2 = core.rate_limit_key("203.0.113.7", day="2026-05-28")
    assert k1 == k2
    assert "203.0.113.7" not in k1  # raw IP never stored
    assert k1.startswith("rl:2026-05-28:")


def test_rate_limit_check_allows_under_limit():
    store = {}
    for i in range(core.DAILY_LIMIT):
        allowed, remaining = core.check_and_increment(store, "k")
        assert allowed is True
    assert remaining == 0


def test_rate_limit_check_blocks_over_limit():
    store = {}
    for _ in range(core.DAILY_LIMIT):
        core.check_and_increment(store, "k")
    allowed, remaining = core.check_and_increment(store, "k")
    assert allowed is False
    assert remaining == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -k rate_limit -q`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Implement rate-limit logic**

Append to `backend/latextools/core.py`:
```python
import hashlib

DAILY_LIMIT = 25  # compiles per IP per UTC day


def rate_limit_key(ip: str, day: str) -> str:
    """Build a daily, hashed rate-limit key. Raw IP is never persisted."""
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
    return f"rl:{day}:{digest}"


def check_and_increment(store, key: str) -> tuple[bool, int]:
    """Increment the counter for *key* in a dict-like *store*.

    Returns (allowed, remaining). When the prior count is already at
    DAILY_LIMIT, returns (False, 0) and does not increment further.
    *store* is any object supporting .get(key, default) and item assignment
    (a plain dict in tests, a modal.Dict in production).
    """
    current = store.get(key, 0)
    if current >= DAILY_LIMIT:
        return False, 0
    store[key] = current + 1
    return True, DAILY_LIMIT - (current + 1)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_core.py -k rate_limit -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/latextools/core.py backend/tests/test_core.py
git commit -m "feat(backend): add per-IP daily rate-limit accounting"
```

---

## Task 6: Test fixtures + subprocess runner

**Files:**
- Create: `backend/tests/fixtures/clean.tex`
- Create: `backend/tests/fixtures/error.tex`
- Create: `backend/tests/fixtures/shell_escape.tex`
- Create: `backend/tests/fixtures/read_passwd.tex`
- Create: `backend/tests/fixtures/infinite_loop.tex`
- Create: `backend/tests/conftest.py`
- Create: `backend/latextools/runner.py`
- Test: `backend/tests/test_runner_integration.py`

- [ ] **Step 1: Create the fixture files**

`backend/tests/fixtures/clean.tex`:
```latex
\documentclass{article}
\begin{document}
\title{Test} \maketitle
Hello world.
\end{document}
```

`backend/tests/fixtures/error.tex`:
```latex
\documentclass{article}
\begin{document}
\badcommand
\end{document}
```

`backend/tests/fixtures/shell_escape.tex`:
```latex
\documentclass{article}
\begin{document}
\immediate\write18{touch /tmp/pwned_by_latex}
ok
\end{document}
```

`backend/tests/fixtures/read_passwd.tex`:
```latex
\documentclass{article}
\begin{document}
\input{/etc/passwd}
\end{document}
```

`backend/tests/fixtures/infinite_loop.tex`:
```latex
\documentclass{article}
\begin{document}
\def\loopx{\loopx}\loopx
\end{document}
```

- [ ] **Step 2: Create conftest with a shared fixtures fixture**

`backend/tests/conftest.py` (only provides a pytest fixture; test files define their own constants/markers to avoid cross-module imports):
```python
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 3: Write the failing integration test**

`backend/tests/test_runner_integration.py` (defines `FIXTURES` and the skip marker locally — no import from conftest):
```python
import shutil
from pathlib import Path

import pytest

from latextools import runner

FIXTURES = Path(__file__).parent / "fixtures"
has_latexmk = pytest.mark.skipif(
    shutil.which("latexmk") is None,
    reason="latexmk not installed (run inside the Modal image)",
)


@has_latexmk
def test_compile_clean_doc_returns_pdf(tmp_path):
    tex = (FIXTURES / "clean.tex").read_text()
    result = runner.run_compile(tmp_path, tex, engine="pdflatex", timeout=60)
    assert result.ok is True
    assert result.pdf_bytes[:4] == b"%PDF"
    assert result.errors == []


@has_latexmk
def test_compile_error_doc_reports_errors(tmp_path):
    tex = (FIXTURES / "error.tex").read_text()
    result = runner.run_compile(tmp_path, tex, engine="pdflatex", timeout=60)
    assert result.ok is False
    assert result.pdf_bytes is None
    assert any("Undefined control sequence" in e["message"] for e in result.errors)


@has_latexmk
def test_shell_escape_is_blocked(tmp_path):
    tex = (FIXTURES / "shell_escape.tex").read_text()
    runner.run_compile(tmp_path, tex, engine="pdflatex", timeout=60)
    assert not Path("/tmp/pwned_by_latex").exists()


@has_latexmk
def test_infinite_loop_times_out(tmp_path):
    tex = (FIXTURES / "infinite_loop.tex").read_text()
    result = runner.run_compile(tmp_path, tex, engine="pdflatex", timeout=5)
    assert result.ok is False
    assert result.timed_out is True
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_runner_integration.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'latextools.runner'` (or all-skipped if latexmk absent locally — in that case the failure is the import error, which still must be fixed).

- [ ] **Step 5: Implement the runner**

`backend/latextools/runner.py`:
```python
"""Subprocess execution of latexmk / latexdiff in a working directory.

This is the only module that requires the TeX toolchain, so it is covered
by integration tests that skip when latexmk is unavailable.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from latextools import core


@dataclass
class CompileResult:
    ok: bool
    pdf_bytes: bytes | None
    errors: list[dict]
    log: str
    timed_out: bool = False


def run_compile(
    workdir: Path, tex_source: str, engine: str, timeout: int
) -> CompileResult:
    """Write *tex_source* to workdir/main.tex and compile it with latexmk."""
    core.build_latexmk_command(engine, "main")  # validates engine early
    tex_path = Path(workdir) / "main.tex"
    tex_path.write_text(tex_source, encoding="utf-8")
    cmd = core.build_latexmk_command(engine, "main")

    try:
        proc = subprocess.run(
            cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, [], "", timed_out=True)

    log_path = Path(workdir) / "main.log"
    log = log_path.read_text(errors="replace") if log_path.exists() else proc.stdout
    pdf_path = Path(workdir) / "main.pdf"

    if proc.returncode == 0 and pdf_path.exists():
        return CompileResult(True, pdf_path.read_bytes(), [], log)
    return CompileResult(False, None, core.parse_latex_log(log), log)


def run_diff(
    workdir: Path,
    old_source: str,
    new_source: str,
    engine: str,
    timeout: int,
    add_legend: bool,
) -> CompileResult:
    """Run latexdiff(old,new) -> main.tex, then compile it."""
    (Path(workdir) / "old.tex").write_text(old_source, encoding="utf-8")
    (Path(workdir) / "new.tex").write_text(new_source, encoding="utf-8")
    diff_cmd = core.build_latexdiff_command("old.tex", "new.tex")
    try:
        diff_proc = subprocess.run(
            diff_cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, [], "", timed_out=True)
    if diff_proc.returncode != 0:
        return CompileResult(
            False, None, [{"file": "latexdiff", "line": 0, "message": diff_proc.stderr.strip()[:500]}], diff_proc.stderr
        )

    diff_tex = diff_proc.stdout
    if add_legend:
        diff_tex = core.inject_diff_legend(diff_tex)
    return run_compile(workdir, diff_tex, engine, timeout)
```

- [ ] **Step 6: Run the test to verify it passes (or skips cleanly)**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_runner_integration.py -q`
Expected: with latexmk absent locally → "4 skipped". The import now resolves, so there is no error. (Full pass is verified inside the image in Task 8.)

- [ ] **Step 7: Run the whole unit suite**

Run: `cd backend && . .venv/bin/activate && pytest -q`
Expected: all `test_core.py` tests pass; integration tests skipped.

- [ ] **Step 8: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/tests/fixtures backend/tests/conftest.py \
  backend/latextools/runner.py backend/tests/test_runner_integration.py
git commit -m "feat(backend): add subprocess runner and security/integration fixtures"
```

---

## Task 7: TeX hardening config

**Files:**
- Create: `backend/texmf.cnf`

- [ ] **Step 1: Create the hardening config**

`backend/texmf.cnf`:
```
% Appended to the image's texmf config to confine untrusted compiles.
% Paranoid file access: reads/writes limited to CWD + texmf trees; no
% absolute or parent paths; no piped input/output.
shell_escape = f
openin_any = p
openout_any = p
```

- [ ] **Step 2: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/texmf.cnf
git commit -m "feat(backend): add paranoid texmf hardening config"
```

(The image build in Task 8 appends this to the system texmf.cnf and verifies enforcement.)

---

## Task 8: Modal image definition + in-image test run

**Files:**
- Create: `backend/app.py` (image only in this task)

- [ ] **Step 1: Define the Modal app and image**

`backend/app.py`:
```python
"""Modal app for the purplelink LaTeX tools backend."""
from __future__ import annotations

import modal

app = modal.App("purplelink-latextools")

# Pinned TeX Live + toolchain image. tag pinned for reproducibility.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "texlive-latex-recommended",
        "texlive-latex-extra",
        "texlive-fonts-recommended",
        "texlive-xetex",
        "latexmk",
        "latexdiff",
        "biber",
    )
    .pip_install("fastapi[standard]==0.115.2")
    # Append hardening config to the system texmf.cnf.
    .add_local_file(
        "texmf.cnf", "/usr/local/share/texmf-hardening.cnf", copy=True
    )
    .run_commands(
        "cat /usr/local/share/texmf-hardening.cnf >> "
        "$(kpsewhich -var-value=TEXMFLOCAL)/web2c/texmf.cnf 2>/dev/null || "
        "cat /usr/local/share/texmf-hardening.cnf >> /etc/texmf/texmf.cnf"
    )
    # Bundle our package into the image for in-container imports.
    .add_local_python_source("latextools")
)
```

- [ ] **Step 2: Verify the image builds and the toolchain + hardening are present**

Run:
```bash
cd backend && . .venv/bin/activate && pip install modal && modal setup  # one-time auth, opens browser
modal run app.py::_smoke 2>/dev/null || true
```
Then add a temporary smoke function and run it. Append to `backend/app.py`:
```python
@app.function(image=image)
def _smoke() -> str:
    import shutil
    import subprocess

    assert shutil.which("latexmk"), "latexmk missing"
    assert shutil.which("latexdiff"), "latexdiff missing"
    assert shutil.which("xelatex"), "xelatex missing"
    out = subprocess.run(
        ["kpsewhich", "-var-value=openin_any"], capture_output=True, text=True
    )
    return f"openin_any={out.stdout.strip()}"
```

Run: `cd backend && . .venv/bin/activate && modal run app.py::_smoke`
Expected: prints `openin_any=p` (confirms hardening applied) and no assertion error.

- [ ] **Step 3: Run the integration tests inside the image**

Add a temporary test-runner function. Append to `backend/app.py`:
```python
@app.function(image=image)
def _run_integration_tests() -> str:
    import subprocess

    r = subprocess.run(
        ["python", "-m", "pytest", "tests/test_runner_integration.py", "-q",
         "-o", "cache_dir=/tmp/pc"],
        cwd="/root", capture_output=True, text=True,
    )
    return r.stdout + r.stderr
```
Note: for this to find the tests, add `.add_local_dir("tests", "/root/tests", copy=True)` and `.workdir("/root")` to the image chain temporarily, or run the assertions inline. Simpler: replace the body with direct calls:
```python
@app.function(image=image)
def _run_integration_tests() -> dict:
    import tempfile
    from pathlib import Path
    from latextools import runner

    results = {}
    clean = r"\documentclass{article}\begin{document}Hi\end{document}"
    with tempfile.TemporaryDirectory() as d:
        res = runner.run_compile(Path(d), clean, "pdflatex", 60)
        results["clean_ok"] = res.ok and res.pdf_bytes[:4] == b"%PDF"
    shell = (r"\documentclass{article}\begin{document}"
             r"\immediate\write18{touch /tmp/pwned}ok\end{document}")
    with tempfile.TemporaryDirectory() as d:
        runner.run_compile(Path(d), shell, "pdflatex", 60)
        results["shell_escape_blocked"] = not Path("/tmp/pwned").exists()
    loop = (r"\documentclass{article}\begin{document}"
            r"\def\x{\x}\x\end{document}")
    with tempfile.TemporaryDirectory() as d:
        res = runner.run_compile(Path(d), loop, "pdflatex", 5)
        results["loop_times_out"] = res.timed_out
    return results
```

Run: `cd backend && . .venv/bin/activate && modal run app.py::_run_integration_tests`
Expected: `{'clean_ok': True, 'shell_escape_blocked': True, 'loop_times_out': True}`.

- [ ] **Step 4: Remove the temporary smoke/test functions**

Delete `_smoke` and `_run_integration_tests` from `backend/app.py` (they were verification scaffolding).

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/app.py
git commit -m "feat(backend): define hardened Modal TeX Live image"
```

---

## Task 9: Modal functions + FastAPI endpoints (compile + diff)

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: Add the rate-limit Dict, compile/diff Modal functions, and the ASGI app**

Append to `backend/app.py`:
```python
import datetime

from latextools import core

# Persistent, low-volume counter store for rate limiting.
rate_dict = modal.Dict.from_name("latextools-rate", create_if_missing=True)

ALLOWED_ORIGINS = [
    "https://purplelink.llc",
    "https://www.purplelink.llc",
    "http://localhost:4200",  # local dev serve
]

_COMPILE_KW = dict(
    image=image,
    timeout=90,          # wall-clock; per-compile latexmk gets 60s (below)
    cpu=1.0,
    memory=2048,
    max_containers=4,    # global concurrency cap (spec §cost)
)


@app.function(**_COMPILE_KW)
def compile_tex(tex_source: str, engine: str) -> dict:
    """Compile a single .tex; return {ok, pdf (bytes)|None, errors, timed_out}."""
    import tempfile
    from pathlib import Path
    from latextools import runner

    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        res = runner.run_compile(Path(d), tex_source, engine, timeout=60)
    return {
        "ok": res.ok,
        "pdf": res.pdf_bytes,
        "errors": res.errors,
        "timed_out": res.timed_out,
    }


@app.function(**_COMPILE_KW)
def diff_tex(old_source: str, new_source: str, engine: str, add_legend: bool) -> dict:
    import tempfile
    from pathlib import Path
    from latextools import runner

    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        res = runner.run_diff(
            Path(d), old_source, new_source, engine, timeout=60, add_legend=add_legend
        )
    return {
        "ok": res.ok,
        "pdf": res.pdf_bytes,
        "errors": res.errors,
        "timed_out": res.timed_out,
    }


@app.function(image=image)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, File, Form, Request, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response

    api = FastAPI()
    api.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["*"],
    )

    def _client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "0.0.0.0")

    def _enforce_rate_limit(request: Request):
        day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        key = core.rate_limit_key(_client_ip(request), day)
        allowed, _ = core.check_and_increment(rate_dict, key)
        return allowed

    async def _read_tex(upload: UploadFile) -> str:
        data = await upload.read()
        core.validate_upload(upload.filename or "", len(data))
        return data.decode("utf-8", errors="replace")

    def _pdf_response(pdf: bytes, filename: str) -> Response:
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @api.post("/compile")
    async def compile_endpoint(
        request: Request,
        file: UploadFile = File(...),
        engine: str = Form("pdflatex"),
    ):
        if not _enforce_rate_limit(request):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            tex = await _read_tex(file)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        result = compile_tex.remote(tex, engine)
        if result["timed_out"]:
            return JSONResponse({"error": "timeout"}, status_code=422)
        if not result["ok"]:
            return JSONResponse({"error": "compile", "errors": result["errors"]}, status_code=422)
        return _pdf_response(result["pdf"], "compiled.pdf")

    @api.post("/diff")
    async def diff_endpoint(
        request: Request,
        old: UploadFile = File(...),
        new: UploadFile = File(...),
        engine: str = Form("pdflatex"),
        legend: str = Form("false"),
    ):
        if not _enforce_rate_limit(request):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            old_tex = await _read_tex(old)
            new_tex = await _read_tex(new)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        result = diff_tex.remote(old_tex, new_tex, engine, legend == "true")
        if result["timed_out"]:
            return JSONResponse({"error": "timeout"}, status_code=422)
        if not result["ok"]:
            return JSONResponse({"error": "compile", "errors": result["errors"]}, status_code=422)
        return _pdf_response(result["pdf"], "diff.pdf")

    return api
```

- [ ] **Step 2: Deploy and capture the endpoint URL**

Run: `cd backend && . .venv/bin/activate && modal deploy app.py`
Expected: deploy succeeds and prints a URL for the `web` ASGI app, e.g.
`https://ben-ampel--purplelink-latextools-web.modal.run`
**Record this URL** — it is needed in Tasks 10 and 13.

- [ ] **Step 3: Smoke-test the live compile endpoint**

Run (substitute the recorded URL):
```bash
cd backend
printf '\\documentclass{article}\\begin{document}Hello\\end{document}' > /tmp/h.tex
curl -s -o /tmp/out.pdf -w "%{http_code} %{content_type}\n" \
  -F "file=@/tmp/h.tex" -F "engine=pdflatex" \
  https://ben-ampel--purplelink-latextools-web.modal.run/compile
head -c 4 /tmp/out.pdf; echo
```
Expected: `200 application/pdf` and the file begins with `%PDF`.

- [ ] **Step 4: Smoke-test an error returns structured JSON**

Run:
```bash
printf '\\documentclass{article}\\begin{document}\\badcmd\\end{document}' > /tmp/e.tex
curl -s -w "\n%{http_code}\n" -F "file=@/tmp/e.tex" \
  https://ben-ampel--purplelink-latextools-web.modal.run/compile
```
Expected: HTTP `422` and JSON containing `"errors"` with an "Undefined control sequence" message.

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/app.py
git commit -m "feat(backend): add compile/diff Modal functions and FastAPI endpoints"
```

---

## Task 10: Backend README

**Files:**
- Create: `backend/README.md`

- [ ] **Step 1: Write the README**

`backend/README.md`:
```markdown
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
```

- [ ] **Step 2: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/README.md
git commit -m "docs(backend): add backend README"
```

---

## Task 11: Tools-section CSS

**Files:**
- Modify: `site/styles.css`

- [ ] **Step 1: Append the tools CSS**

Append to `site/styles.css`:
```css
/* ── Tools section ─────────────────────────────────── */
.tools-hero { max-width: 820px; margin: 0 auto; padding: 56px 24px 8px; text-align: center; }
.tools-grid {
  max-width: 1040px; margin: 0 auto; padding: 24px;
  display: grid; gap: 20px; grid-template-columns: repeat(3, 1fr);
}
@media (max-width: 820px) { .tools-grid { grid-template-columns: 1fr; } }
.tool-card {
  display: block; padding: 24px; border: 1px solid var(--line);
  border-radius: 14px; background: var(--panel); text-decoration: none;
  color: var(--ink); transition: transform .2s, box-shadow .2s, border-color .2s;
}
.tool-card:hover {
  transform: translateY(-3px); border-color: var(--purple-dim);
  box-shadow: 0 8px 28px oklch(50% 0.24 310 / 0.10);
}
.tool-card .tool-emoji { font-size: 30px; }
.tool-card h3 { font-family: var(--font-display); margin: 10px 0 6px; }
.tool-card p { color: var(--muted); margin: 0; font-size: 0.95rem; }

.tool-app { max-width: 820px; margin: 0 auto; padding: 24px; }
.dropzone {
  border: 2px dashed var(--line); border-radius: 14px; padding: 40px 24px;
  text-align: center; background: var(--purple-xlight); cursor: pointer;
  transition: border-color .2s, background .2s;
}
.dropzone.dragover { border-color: var(--purple); background: var(--purple-light); }
.dropzone input[type=file] { display: none; }
.tool-options { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin: 20px 0; }
.tool-options label { font-size: 0.95rem; color: var(--ink); }
.tool-options select { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; font: inherit; }
.tool-status { margin: 16px 0; min-height: 1.5em; color: var(--muted); }
.tool-error {
  border: 1px solid oklch(60% 0.18 25); border-radius: 10px; padding: 16px;
  background: oklch(96% 0.04 25); color: oklch(35% 0.16 25); white-space: pre-wrap;
  font-family: ui-monospace, monospace; font-size: 0.85rem;
}
.tool-result iframe { width: 100%; height: 600px; border: 1px solid var(--line); border-radius: 10px; }
.tool-privacy { font-size: 0.85rem; color: var(--muted); text-align: center; margin-top: 8px; }
.tool-faq { max-width: 820px; margin: 32px auto; padding: 0 24px; }
.tool-faq details { border-bottom: 1px solid var(--line); padding: 14px 0; }
.tool-faq summary { cursor: pointer; font-weight: 600; }
.tool-faq .faq-body { color: var(--muted); padding-top: 8px; }
```

- [ ] **Step 2: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/styles.css
git commit -m "feat(tools): add tools-section styles"
```

---

## Task 12: Shared tool JS

**Files:**
- Create: `site/tools/tools.js`

- [ ] **Step 1: Write the shared client logic**

`site/tools/tools.js`:
```javascript
// Shared client logic for purplelink LaTeX tool pages.
// The Modal endpoint base is defined ONCE here.
const API_BASE = "https://ben-ampel--purplelink-latextools-web.modal.run";
const MAX_BYTES = 5 * 1024 * 1024;

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// Wire a dropzone+file input to a hidden chosen-file store.
function wireDropzone(zoneId, inputId, onFile) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; onFile(input.files[0]); }
  });
  input.addEventListener("change", () => { if (input.files.length) onFile(input.files[0]); });
}

function validClientSide(file, statusEl) {
  if (!file.name.toLowerCase().endsWith(".tex")) { statusEl.textContent = "Please choose a .tex file."; return false; }
  if (file.size > MAX_BYTES) { statusEl.textContent = "File is too large (max 5 MB)."; return false; }
  if (file.size === 0) { statusEl.textContent = "That file is empty."; return false; }
  return true;
}

function renderError(resultEl, status, payload) {
  if (status === 429) { resultEl.innerHTML = '<div class="tool-error">You\'ve reached the daily limit. Please try again tomorrow.</div>'; return; }
  if (payload && payload.error === "timeout") { resultEl.innerHTML = '<div class="tool-error">Compilation took too long (over 60s). Your document may have an infinite loop or be too large for the free tool.</div>'; return; }
  if (payload && payload.errors && payload.errors.length) {
    const lines = payload.errors.map((e) => `Line ${e.line}: ${escapeHtml(e.message)}`).join("\n");
    resultEl.innerHTML = `<div class="tool-error">Compilation failed:\n${lines}</div>`;
    return;
  }
  const detail = payload && payload.detail ? escapeHtml(payload.detail) : "Something went wrong. Please try again.";
  resultEl.innerHTML = `<div class="tool-error">${detail}</div>`;
}

function showPdf(resultEl, blob, downloadName) {
  const url = URL.createObjectURL(blob);
  resultEl.innerHTML =
    `<a class="btn btn-primary" href="${url}" download="${downloadName}">Download ${downloadName}</a>` +
    `<div style="margin-top:14px"><iframe title="PDF preview" src="${url}"></iframe></div>`;
}

// POST a FormData to API_BASE+path; on PDF success call showPdf, else renderError.
async function postForPdf(path, formData, statusEl, resultEl, downloadName) {
  statusEl.textContent = "Working… this can take up to a minute.";
  resultEl.innerHTML = "";
  try {
    const resp = await fetch(API_BASE + path, { method: "POST", body: formData });
    const ctype = resp.headers.get("content-type") || "";
    if (resp.ok && ctype.includes("application/pdf")) {
      const blob = await resp.blob();
      statusEl.textContent = "Done.";
      showPdf(resultEl, blob, downloadName);
    } else {
      let payload = null;
      try { payload = await resp.json(); } catch (_) {}
      statusEl.textContent = "";
      renderError(resultEl, resp.status, payload);
    }
  } catch (_) {
    statusEl.textContent = "";
    resultEl.innerHTML = '<div class="tool-error">Network error. Please check your connection and try again.</div>';
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/tools/tools.js
git commit -m "feat(tools): add shared tool client logic"
```

---

## Task 13: Tools hub page

**Files:**
- Create: `site/tools/index.html`

- [ ] **Step 1: Create the hub page**

`site/tools/index.html` (head/topbar/footer copied verbatim from the pattern in `site/moderntex/index.html`, with the nav including the new Tools link added in Task 16; body content below):
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>Free LaTeX Tools — Compile, Convert, Diff | Purplelink LLC</title>
    <meta name="description" content="Free online LaTeX tools for academics: compile .tex to PDF, convert LaTeX to a Word manuscript, and generate a latexdiff comparison PDF. Your files are never stored.">
    <link rel="canonical" href="https://purplelink.llc/tools/">
    <meta property="og:title" content="Free LaTeX Tools — Compile, Convert, Diff">
    <meta property="og:description" content="Compile LaTeX to PDF, convert to Word, and diff two versions — free, in your browser. Zero file retention.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://purplelink.llc/tools/">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/tools/">Tools</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <a class="back-link" href="/">← Home</a>

    <main id="main-content">
      <div class="tools-hero">
        <p class="eyebrow">Free web tools</p>
        <h1>LaTeX tools for academics</h1>
        <p>Compile, convert, and compare LaTeX documents right in your browser. No account, no install. <strong>Your files are processed in memory and never stored.</strong></p>
      </div>

      <div class="tools-grid">
        <a class="tool-card" href="/tools/latex-to-pdf/">
          <span class="tool-emoji" aria-hidden="true">📄</span>
          <h3>LaTeX → PDF</h3>
          <p>Upload a .tex file and get a compiled PDF. pdfLaTeX or XeLaTeX.</p>
        </a>
        <a class="tool-card" href="/tools/latex-to-word/">
          <span class="tool-emoji" aria-hidden="true">📝</span>
          <h3>LaTeX → Word</h3>
          <p>Convert a .tex paper into a standard double-spaced Word manuscript.</p>
        </a>
        <a class="tool-card" href="/tools/latex-diff/">
          <span class="tool-emoji" aria-hidden="true">🔀</span>
          <h3>LaTeX Diff</h3>
          <p>Upload two versions and get a tracked-changes comparison PDF.</p>
        </a>
      </div>
    </main>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>
  </body>
</html>
```

Note: the `/tools/latex-to-word/` card links to the page built in Plan 2. Until Plan 2 ships, that link 404s — acceptable, or omit the middle card and add it in Plan 2 Task 1. Implementer: keep the card; Plan 2 is the immediate next plan.

- [ ] **Step 2: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/tools/index.html
git commit -m "feat(tools): add tools hub page"
```

---

## Task 14: LaTeX → PDF tool page

**Files:**
- Create: `site/tools/latex-to-pdf/index.html`

- [ ] **Step 1: Create the page**

`site/tools/latex-to-pdf/index.html` — same head/topbar/footer shell as Task 13 (update `<title>`, `<meta name=description>`, and canonical to `https://purplelink.llc/tools/latex-to-pdf/`; title: `Compile LaTeX to PDF Online — Free | Purplelink LLC`; description: `Free online LaTeX compiler. Upload a .tex file and download a PDF, compiled with pdfLaTeX or XeLaTeX. Files are never stored.`). Body `<main>`:
```html
    <main id="main-content">
      <a class="back-link" href="/tools/">← All tools</a>
      <div class="tools-hero">
        <p class="eyebrow">Free web tool</p>
        <h1>Compile LaTeX to PDF</h1>
        <p>Upload a self-contained <code>.tex</code> file and download a compiled PDF. <strong>Your file is processed in memory and never stored.</strong></p>
      </div>

      <div class="tool-app">
        <div class="dropzone" id="dropzone">
          <input type="file" id="file" accept=".tex">
          <p>Drag a <code>.tex</code> file here, or click to choose. Max 5 MB.</p>
          <p id="filename" class="tool-privacy"></p>
        </div>
        <div class="tool-options">
          <label>Engine:
            <select id="engine">
              <option value="pdflatex">pdfLaTeX</option>
              <option value="xelatex">XeLaTeX</option>
            </select>
          </label>
          <button class="btn btn-primary" id="run" disabled>Compile to PDF</button>
        </div>
        <p class="tool-status" id="status"></p>
        <div class="tool-result" id="result"></div>
        <p class="tool-privacy">Single self-contained .tex only (no .bib/figures yet). Files are never written to disk.</p>
      </div>

      <section class="tool-faq">
        <h2>About this tool</h2>
        <p>This is a free online LaTeX compiler. It runs <code>latexmk</code> with your chosen engine, handling the multi-pass build automatically. It's designed for quick checks of a single self-contained document.</p>
        <details><summary>Are my files stored?</summary><div class="faq-body">No. Your file is compiled in an ephemeral container and discarded immediately. Nothing is written to durable storage or logs.</div></details>
        <details><summary>Why did my document fail to compile?</summary><div class="faq-body">The tool accepts a single self-contained .tex file. Documents needing separate .bib, .sty, or image files won't find them yet — multi-file projects are coming. Compilation errors are shown with line numbers.</div></details>
        <details><summary>Which engines are supported?</summary><div class="faq-body">pdfLaTeX and XeLaTeX. LuaLaTeX is not supported for security reasons.</div></details>
      </section>

      <script src="/tools/tools.js"></script>
      <script>
        (function () {
          let chosen = null;
          const statusEl = document.getElementById("status");
          const resultEl = document.getElementById("result");
          const runBtn = document.getElementById("run");
          const nameEl = document.getElementById("filename");
          wireDropzone("dropzone", "file", function (f) {
            if (!validClientSide(f, statusEl)) { chosen = null; runBtn.disabled = true; return; }
            chosen = f; nameEl.textContent = f.name; statusEl.textContent = ""; runBtn.disabled = false;
          });
          runBtn.addEventListener("click", function () {
            if (!chosen) return;
            const fd = new FormData();
            fd.append("file", chosen);
            fd.append("engine", document.getElementById("engine").value);
            postForPdf("/compile", fd, statusEl, resultEl, "compiled.pdf");
          });
        })();
      </script>
    </main>
```

- [ ] **Step 2: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/tools/latex-to-pdf/index.html
git commit -m "feat(tools): add LaTeX to PDF tool page"
```

---

## Task 15: LaTeX Diff tool page

**Files:**
- Create: `site/tools/latex-diff/index.html`

- [ ] **Step 1: Create the page**

`site/tools/latex-diff/index.html` — same shell (canonical `https://purplelink.llc/tools/latex-diff/`; title `LaTeX Diff Online — Compare Two Versions | Purplelink LLC`; description `Free online latexdiff tool. Upload an old and new .tex file and download a PDF with additions and deletions marked. Files are never stored.`). Body `<main>`:
```html
    <main id="main-content">
      <a class="back-link" href="/tools/">← All tools</a>
      <div class="tools-hero">
        <p class="eyebrow">Free web tool</p>
        <h1>Compare two LaTeX versions</h1>
        <p>Upload the old and new <code>.tex</code> files to get a PDF with additions and deletions marked (powered by <code>latexdiff</code>). <strong>Your files are never stored.</strong></p>
      </div>

      <div class="tool-app">
        <div class="dropzone" id="dz-old">
          <input type="file" id="file-old" accept=".tex">
          <p><strong>Old version</strong> — drag a .tex here or click. Max 5 MB.</p>
          <p id="name-old" class="tool-privacy"></p>
        </div>
        <div class="dropzone" id="dz-new" style="margin-top:16px">
          <input type="file" id="file-new" accept=".tex">
          <p><strong>New version</strong> — drag a .tex here or click. Max 5 MB.</p>
          <p id="name-new" class="tool-privacy"></p>
        </div>
        <div class="tool-options">
          <label>Engine:
            <select id="engine">
              <option value="pdflatex">pdfLaTeX</option>
              <option value="xelatex">XeLaTeX</option>
            </select>
          </label>
          <label><input type="checkbox" id="legend"> Add a legend explaining the colors</label>
          <button class="btn btn-primary" id="run" disabled>Generate diff PDF</button>
        </div>
        <p class="tool-status" id="status"></p>
        <div class="tool-result" id="result"></div>
        <p class="tool-privacy">Changes inside tables are shown in final form only (not marked). Files are never written to disk.</p>
      </div>

      <section class="tool-faq">
        <h2>About this tool</h2>
        <p>This runs <code>latexdiff</code> with table-safe defaults, then compiles the result. Added text is blue and underlined; deleted text is red and struck through.</p>
        <details><summary>Are my files stored?</summary><div class="faq-body">No. Both files are processed in an ephemeral container and discarded immediately.</div></details>
        <details><summary>Why aren't changes inside my tables marked?</summary><div class="faq-body">Tables are treated as opaque blocks to prevent column-alignment corruption. Edited tables appear in their final form only.</div></details>
      </section>

      <script src="/tools/tools.js"></script>
      <script>
        (function () {
          let oldF = null, newF = null;
          const statusEl = document.getElementById("status");
          const resultEl = document.getElementById("result");
          const runBtn = document.getElementById("run");
          function refresh() { runBtn.disabled = !(oldF && newF); }
          wireDropzone("dz-old", "file-old", function (f) {
            if (!validClientSide(f, statusEl)) { oldF = null; refresh(); return; }
            oldF = f; document.getElementById("name-old").textContent = f.name; statusEl.textContent = ""; refresh();
          });
          wireDropzone("dz-new", "file-new", function (f) {
            if (!validClientSide(f, statusEl)) { newF = null; refresh(); return; }
            newF = f; document.getElementById("name-new").textContent = f.name; statusEl.textContent = ""; refresh();
          });
          runBtn.addEventListener("click", function () {
            if (!(oldF && newF)) return;
            const fd = new FormData();
            fd.append("old", oldF);
            fd.append("new", newF);
            fd.append("engine", document.getElementById("engine").value);
            fd.append("legend", document.getElementById("legend").checked ? "true" : "false");
            postForPdf("/diff", fd, statusEl, resultEl, "diff.pdf");
          });
        })();
      </script>
    </main>
```

- [ ] **Step 2: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/tools/latex-diff/index.html
git commit -m "feat(tools): add LaTeX diff tool page"
```

---

## Task 16: Sitewide nav "Tools" link

**Files:**
- Modify (14): `site/index.html`, `site/404.html`, `site/about/index.html`, `site/blog/index.html`, `site/blog/starting-purplelink/index.html`, `site/blog/the-latex-editor-academics-want/index.html`, `site/blog/what-globepin-does-differently/index.html`, `site/blog/why-haea-is-on-device/index.html`, `site/changelog/index.html`, `site/globepin/index.html`, `site/haea/index.html`, `site/moderntex/index.html`, `site/press/index.html`, `site/privacy/index.html`

- [ ] **Step 1: Insert the Tools link after the Products link in every nav**

The Products link differs between the homepage (`href="#projects"`) and subpages (`href="/#projects"`). Run two targeted replacements:

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC/site"
# Homepage variant
perl -0pi -e 's{(<a href="#projects">Products</a>)}{$1\n        <a href="/tools/">Tools</a>}' index.html
# Subpage variant (all other files)
for f in 404.html about/index.html blog/index.html \
  blog/starting-purplelink/index.html blog/the-latex-editor-academics-want/index.html \
  blog/what-globepin-does-differently/index.html blog/why-haea-is-on-device/index.html \
  changelog/index.html globepin/index.html haea/index.html moderntex/index.html \
  press/index.html privacy/index.html; do
  perl -0pi -e 's{(<a href="/#projects">Products</a>)}{$1\n        <a href="/tools/">Tools</a>}' "$f"
done
```

- [ ] **Step 2: Verify every page now has exactly one Tools link**

Run:
```bash
cd "/Volumes/Extreme SSD/Purplelink LLC/site"
grep -rc 'href="/tools/">Tools<' --include="*.html" . | grep -v ':1$' || echo "all pages have exactly one Tools link"
```
Expected: prints `all pages have exactly one Tools link` (no file reports 0 or 2+). The three `site/tools/*` pages already include the link from Tasks 13–15, so they will also report 1.

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/*.html site/**/index.html
git commit -m "feat(tools): add Tools link to sitewide navigation"
```

---

## Task 17: CSP, sitemap, llms.txt

**Files:**
- Modify: `site/netlify.toml`
- Modify: `site/sitemap.xml`
- Modify: `site/llms.txt`

- [ ] **Step 1: Add connect-src for the Modal endpoint to the CSP**

In `site/netlify.toml`, replace the existing `Content-Security-Policy` line with one that adds `connect-src` (substitute the recorded Modal origin):
```
    Content-Security-Policy = "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; script-src 'self' 'unsafe-inline'; connect-src 'self' https://ben-ampel--purplelink-latextools-web.modal.run; frame-src 'self' blob:; object-src 'self' blob:"
```
Note: `frame-src/object-src blob:` allows the inline PDF preview iframe (blob URL).

- [ ] **Step 2: Add the four URLs to the sitemap**

In `site/sitemap.xml`, add before `</urlset>`:
```xml
  <url><loc>https://purplelink.llc/tools/</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>https://purplelink.llc/tools/latex-to-pdf/</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://purplelink.llc/tools/latex-diff/</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
```
(The `/tools/latex-to-word/` URL is added by Plan 2.)

- [ ] **Step 3: Add a Tools section to llms.txt**

Append to `site/llms.txt`:
```
## Tools (free web tools)
- LaTeX to PDF: https://purplelink.llc/tools/latex-to-pdf/ — compile a .tex file to PDF (pdfLaTeX/XeLaTeX), files never stored.
- LaTeX Diff: https://purplelink.llc/tools/latex-diff/ — compare two .tex versions, output a marked-up PDF via latexdiff.
- Tools hub: https://purplelink.llc/tools/
```

- [ ] **Step 4: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/netlify.toml site/sitemap.xml site/llms.txt
git commit -m "feat(tools): allow Modal endpoint in CSP; add tools to sitemap and llms.txt"
```

---

## Task 18: End-to-end frontend verification (Playwright)

**Files:**
- Create: `backend/tests/test_frontend_e2e.py` (Playwright; lives with backend tests for convenience)

**Sub-skill:** Use the `webapp-testing` skill for serving + Playwright patterns.

- [ ] **Step 1: Write the e2e test**

`backend/tests/test_frontend_e2e.py`:
```python
"""End-to-end: serve site/ locally, drive the PDF tool against the live Modal endpoint.

Requires: pip install playwright && playwright install chromium
Run only when explicitly enabled (hits the live endpoint):
    RUN_E2E=1 pytest backend/tests/test_frontend_e2e.py -q
"""
import os
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("RUN_E2E") != "1", reason="set RUN_E2E=1")

SITE = Path(__file__).resolve().parents[2] / "site"


@pytest.fixture
def server():
    proc = subprocess.Popen(
        ["python", "-m", "http.server", "4200", "--directory", str(SITE)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    yield "http://localhost:4200"
    proc.terminate()


def test_compile_pdf_end_to_end(server, tmp_path):
    from playwright.sync_api import sync_playwright

    tex = tmp_path / "h.tex"
    tex.write_text(r"\documentclass{article}\begin{document}Hello e2e\end{document}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{server}/tools/latex-to-pdf/")
        page.set_input_files("#file", str(tex))
        page.click("#run")
        # Wait for either a download link or an error panel.
        page.wait_for_selector("a[download='compiled.pdf'], .tool-error", timeout=90000)
        assert page.query_selector("a[download='compiled.pdf']") is not None
        browser.close()
```

- [ ] **Step 2: Run the e2e test against the deployed endpoint**

Run:
```bash
cd backend && . .venv/bin/activate && pip install playwright && playwright install chromium
RUN_E2E=1 pytest tests/test_frontend_e2e.py -q
```
Expected: 1 passed (the page uploads, compiles via Modal, and renders a download link).

- [ ] **Step 3: Manually verify the diff page and error path in a browser**

Using the `webapp-testing` skill (or a manual serve at `http://localhost:4200`):
- `/tools/latex-diff/` — upload two slightly different `.tex` files → a diff PDF renders.
- `/tools/latex-to-pdf/` — upload a `.tex` with `\badcmd` → a readable, HTML-escaped error panel shows with a line number (no script execution).

- [ ] **Step 4: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/tests/test_frontend_e2e.py
git commit -m "test(tools): add end-to-end Playwright test for compile flow"
```

---

## Task 19: Deploy to production

- [ ] **Step 1: Confirm the Modal budget cap is set**

In the Modal dashboard (Usage & Billing), confirm the workspace budget is **$30** (already configured). This bounds worst-case cost.

- [ ] **Step 2: Deploy the site to Netlify**

Run:
```bash
cd "/Volumes/Extreme SSD/Purplelink LLC/site" && netlify deploy --prod
```
Expected: deploy completes; production URL returned.

- [ ] **Step 3: Verify the live pages and a live compile over HTTPS**

Run:
```bash
curl -sI https://purplelink.llc/tools/ | head -1
curl -sI https://purplelink.llc/tools/latex-to-pdf/ | head -1
curl -sI https://purplelink.llc/tools/latex-diff/ | head -1
```
Expected: each returns `HTTP/2 200`.

Then in a browser at `https://purplelink.llc/tools/latex-to-pdf/`, upload a small `.tex` and confirm a PDF downloads (validates the production CSP allows the Modal `connect-src`).

- [ ] **Step 4: Final commit (if any uncommitted changes remain)**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git status
# commit anything outstanding from verification fixes
```

---

## Done criteria (Plan 1)

- `/tools/`, `/tools/latex-to-pdf/`, `/tools/latex-diff/` live on purplelink.llc and reachable from the sitewide nav.
- Uploading a `.tex` returns a PDF; a broken `.tex` returns a readable line-numbered error; two `.tex` files return a diff PDF.
- Security fixtures (shell-escape, /etc/passwd read, infinite loop, oversized file) are all blocked/killed (verified in Task 8).
- Per-IP daily limit and the $30 Modal budget cap are active.
- All unit tests pass; integration + e2e verified.
