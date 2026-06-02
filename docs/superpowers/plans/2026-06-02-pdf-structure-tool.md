# PDF to Structured Data — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a free `/tools/pdf-structure/` tool that turns an uploaded PDF into reading-order Markdown + RAG-ready JSON, powered by OpenDataLoader-PDF (Apache-2.0) running in an isolated JVM Modal function.

**Architecture:** A dedicated Modal function (`pdf_structure_run`) bakes a Temurin JRE + the pinned OpenDataLoader CLI JAR into its own image and shells out to `java -jar …`. The existing `web()` ASGI app gains a synchronous `POST /pdf-structure` endpoint that validates the upload, calls `pdf_structure_run.remote()`, and returns `{markdown, json, summary}`. A new static page renders the result with tabbed Markdown/JSON, download, and copy. Nothing is persisted.

**Tech Stack:** Modal (Python), OpenDataLoader-PDF CLI (Java 17 / Temurin JRE headless), FastAPI (existing `web()`), vanilla JS frontend reusing `tools.js`, strict CSP, OKLCH theme tokens.

---

## Spec reference

Design: `docs/superpowers/specs/2026-06-02-pdf-structure-tool-design.md`
License audit: `docs/opendataloader-license-audit.md`

Reused existing patterns (read these before starting):
- `backend/app.py` — `web()` (line ~462), `_enforce_rate_limit`, `_too_large`, the `pdf_structure_run`-style dedicated function (`paper_review_pipeline` at the top of the file is the template for a dedicated `@app.function` with its own image), the `/file-to-markdown` endpoint (template for a validate→threadpool→JSON flow).
- `backend/latextools/core.py` — `validate_pdf_upload`, `MAX_PDF_UPLOAD_BYTES`.
- `site/tools/tools.js` — `API_BASE`, `wireDropzone`, `escapeHtml`.
- `site/tools/paper-review/status.js` — the hardened `renderMarkdown()` (escape-first, strips invisible Unicode, no raw HTML/img/link). We copy its approach.
- `site/tools/bib-validator/index.html` + `.css` — template for a JSON-returning tool page (tabs, result area, download buttons).

---

## File structure

- **Create** `backend/latextools/pdf_structure.py` — pure-ish helper: build the
  `java` argv, parse OpenDataLoader output dir into `{markdown, json, summary}`,
  compute the summary. No Modal imports (unit-testable).
- **Modify** `backend/app.py` — add `opendataloader_image`, the
  `pdf_structure_run` `@app.function`, and the `POST /pdf-structure` endpoint.
- **Create** `backend/tests/test_pdf_structure.py` — unit tests for argv builder
  + summary computation (pure logic; no JVM needed).
- **Create** `site/tools/pdf-structure/index.html` — tool page.
- **Create** `site/tools/pdf-structure/pdf-structure.css` — theme-token styles.
- **Create** `site/tools/pdf-structure/pdf-structure.js` — UI controller.
- **Modify** `site/tools/index.html` — add tool card + JSON-LD ItemList entry.
- **Modify** `site/sitemap.xml` — add the URL.
- **Modify** `site/llms.txt` — add the tool entry.
- **Create** `site/tools/pdf-structure/ATTRIBUTION.md` (and link it from the page) — Apache-2.0 + NOTICE + third-party attributions.

---

## Task 0: Verify OpenDataLoader interface — RESOLVED (2026-06-02)

Findings (verified against the upstream repo):

- **Version/license:** latest release **v2.4.7, Apache-2.0** (releases ≥ 2.0
  are Apache-2.0). Use it.
- **Install:** `pip install opendataloader-pdf`. The PyPI package **bundles
  the CLI JAR** (`<pkg>/jar/opendataloader-pdf-cli.jar`) plus `LICENSE`,
  `NOTICE`, and `THIRD_PARTY`. So the Modal image needs only the Python
  package + a JRE (Java 11+; use 17). **No manual JAR download.**
- **API:** `opendataloader_pdf.convert(...)` (the `run()` function is
  deprecated). Relevant kwargs:
  - `input_path: str` — PDF file or folder.
  - `output_folder: str` — where outputs are written (defaults to input
    folder). **It WRITES files; it does not return content.**
  - `generate_markdown: bool = False` — set **True** for the `.md`.
  - JSON is **on by default** (`no_json: bool = False`); leave it on.
  - `password`, `keep_line_breaks`, `use_struct_tree` (off), etc. — leave
    defaults.
  - It shells out to `java`; raises `FileNotFoundError` if `java` missing
    and `subprocess.CalledProcessError` on non-zero exit.
- **No OCR / hybrid / picture-description in `convert()`** — those are
  hybrid-server-only options (separate `[hybrid]` extra + a started server).
  Default `convert()` is deterministic, local, content-safety ON. Exactly v1.
- **Output files:** one `*.md` and one `*.json` written into `output_folder`.
- **Real JSON shape (from `samples/json/lorem.json`):**
  - Root is a dict with keys: `"file name"`, **`"number of pages"` (int)**,
    `"author"`, `"title"`, `"creation date"`, `"modification date"`, and
    **`"kids"` (list)**.
  - `"kids"` is a **recursive** tree of blocks. Each block has: `"type"`
    (values seen: `heading`, `paragraph`; others include `table`, `image`/
    `figure`, `formula`, `caption`, `list`), `"id"`, `"page number"`,
    `"bounding box"`, and **`"content"`** (the text; may itself be a string
    or nested), and may contain its own `"kids"`.
  - So `summarize()` must read `"number of pages"` for the page count and
    **walk `"kids"` recursively**, counting `type`s and summing words from
    `"content"`.

These facts are baked into Tasks 1 and 2 below. No guessing remains.

---

## Task 1: Pure helper — argv builder + output parser + summary

**Files:**
- Create: `backend/latextools/pdf_structure.py`
- Test: `backend/tests/test_pdf_structure.py`

- [ ] **Step 1: Write failing tests** (against the REAL JSON shape from Task 0).

```python
# backend/tests/test_pdf_structure.py
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from latextools import pdf_structure as ps


def test_safe_convert_kwargs_markdown_on_no_ocr_or_hybrid():
    kw = ps.safe_convert_kwargs("/in/input.pdf", "/out")
    assert kw["input_path"] == "/in/input.pdf"
    assert kw["output_folder"] == "/out"
    assert kw["generate_markdown"] is True
    # v1 must NEVER enable OCR, hybrid, or picture description
    blob = " ".join(str(k).lower() for k in kw)
    assert "ocr" not in blob
    assert "hybrid" not in blob
    assert "picture" not in blob


def test_summarize_real_shape_recursive():
    # Mirrors samples/json/lorem.json: root has "number of pages" + recursive "kids".
    doc = {
        "file name": "x.pdf",
        "number of pages": 3,
        "kids": [
            {"type": "heading", "content": "Intro"},
            {"type": "paragraph", "content": "hello world foo bar"},
            {"type": "table", "kids": [
                {"type": "paragraph", "content": "cell one"},
            ]},
            {"type": "image", "content": "Figure 1 caption"},
            {"type": "table"},
        ],
    }
    s = ps.summarize(doc)
    assert s["pages"] == 3
    assert s["tables"] == 2          # both "table" blocks, incl. the nested-parent one
    assert s["figures"] == 1         # "image"
    assert s["words"] >= 6           # counts content recursively (incl. nested cell)


def test_summarize_tolerates_missing_fields():
    assert ps.summarize({}) == {"pages": 0, "tables": 0, "figures": 0, "words": 0}


def test_parse_output_dir_reads_md_and_json():
    files = {"out.md": "# Title\n\ntext", "out.json": '{"number of pages": 1, "kids": []}'}
    res = ps.parse_output_dir("/out", read_text=lambda n: files[n], list_files=lambda _: list(files))
    assert res["markdown"].startswith("# Title")
    assert res["json"]["number of pages"] == 1
    assert res["summary"]["pages"] == 1
```

- [ ] **Step 2: Run tests, verify they fail.**

Run: `cd backend && python3 -m pytest tests/test_pdf_structure.py -v`
Expected: FAIL (`module 'latextools.pdf_structure' has no attribute …`).

- [ ] **Step 3: Implement `pdf_structure.py`.**

```python
"""Pure helpers for the free PDF-to-Structured-Data tool.

Resolved interface (Task 0, OpenDataLoader-PDF v2.4.7, Apache-2.0):
  - Install: `pip install opendataloader-pdf` (bundles the CLI JAR + LICENSE/
    NOTICE/THIRD_PARTY). Needs a JRE (Java 17) on PATH.
  - Run: opendataloader_pdf.convert(input_path=..., output_folder=...,
    generate_markdown=True). JSON is on by default. It WRITES files; default
    mode is deterministic-local (NO OCR / hybrid / picture description).
  - Output JSON root: {"number of pages": int, "kids": [ ...recursive blocks ]};
    each block has "type" (heading/paragraph/table/image/figure/...) and
    "content" (text), and may have its own "kids".

This module has no Modal/JVM imports so it stays unit-testable. The actual
convert() call + temp-dir lifecycle lives in app.py's pdf_structure_run.
"""
from __future__ import annotations

import json as _json
import re

_WORD = re.compile(r"\b\w+\b")


def safe_convert_kwargs(input_path: str, output_folder: str) -> dict:
    """Kwargs for opendataloader_pdf.convert() — Markdown + (default) JSON,
    and explicitly NO OCR / hybrid / picture-description (those are
    hybrid-server options absent from convert() anyway; we assert it in
    tests as a guard against future scope creep)."""
    return {
        "input_path": input_path,
        "output_folder": output_folder,
        "generate_markdown": True,
        # JSON stays on (no_json defaults False). No hybrid/OCR keys passed.
    }


def _walk(node, on_block):
    """Depth-first walk over the recursive 'kids' tree, calling on_block(dict)
    for every block dict encountered."""
    if isinstance(node, dict):
        on_block(node)
        kids = node.get("kids")
        if isinstance(kids, list):
            for k in kids:
                _walk(k, on_block)
    elif isinstance(node, list):
        for k in node:
            _walk(k, on_block)


def summarize(doc: dict) -> dict:
    """Compute {pages, tables, figures, words} from the OpenDataLoader JSON."""
    if not isinstance(doc, dict):
        return {"pages": 0, "tables": 0, "figures": 0, "words": 0}
    n_pages = int(doc.get("number of pages") or 0)
    counts = {"tables": 0, "figures": 0, "words": 0}

    def on_block(b):
        t = str(b.get("type") or "").lower()
        if "table" in t:
            counts["tables"] += 1
        elif "image" in t or "figure" in t or "picture" in t:
            counts["figures"] += 1
        content = b.get("content")
        if isinstance(content, str):
            counts["words"] += len(_WORD.findall(content))

    for kid in (doc.get("kids") or []):
        _walk(kid, on_block)
    return {"pages": n_pages, **counts}


def parse_output_dir(out_dir, read_text, list_files) -> dict:
    """Given injected IO (read_text(name)->str, list_files(dir)->[names]),
    return {markdown, json, summary}. Injected IO keeps this pure/testable."""
    md = ""
    structured = {}
    for name in list_files(out_dir):
        low = name.lower()
        if low.endswith(".md") or low.endswith(".markdown"):
            md = read_text(name)
        elif low.endswith(".json"):
            try:
                structured = _json.loads(read_text(name))
            except Exception:
                structured = {}
    return {"markdown": md, "json": structured, "summary": summarize(structured)}
```

- [ ] **Step 4: Run tests, verify pass.**

Run: `cd backend && python3 -m pytest tests/test_pdf_structure.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit.**

```bash
git add backend/latextools/pdf_structure.py backend/tests/test_pdf_structure.py
git commit -m "feat(pdf-structure): pure CLI-argv + output-parse + summary helpers"
```

---

## Task 2: Dedicated JVM Modal function + image

**Files:**
- Modify: `backend/app.py` (add image + function near the other `@app.function` defs, after `paper_review_pipeline`)

- [ ] **Step 1: Define the OpenDataLoader image.** Add near the top-level image defs in `app.py` (NOT inside `web()`; separate image so the shared `image` used by `web()` stays lean). Uses the PyPI package, which bundles the CLI JAR + LICENSE/NOTICE/THIRD_PARTY; only a JRE is added:

```python
# Isolated JVM image for the free PDF-structure tool. The opendataloader-pdf
# PyPI package bundles the CLI JAR (Apache-2.0 v2.x); we add a JRE for it to
# shell out to. Kept separate from `image` so other free tools' cold starts
# are unaffected. Pin a version >= 2.0 so the core stays Apache-2.0.
opendataloader_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("openjdk-17-jre-headless")
    .pip_install("opendataloader-pdf>=2.4,<3")
    .run_commands(
        "java -version",
        # Fail the build loudly if the bundled JAR is missing.
        "python -c \"import opendataloader_pdf, glob, os; "
        "p=os.path.dirname(opendataloader_pdf.__file__); "
        "assert glob.glob(os.path.join(p,'jar','*.jar')), 'bundled JAR missing'\"",
    )
    .add_local_python_source("latextools")
)
```

> If the exact `opendataloader_pdf.__file__`/`jar/` path differs at runtime,
> the build assertion will surface it; adjust the glob to the real bundled
> path. Do NOT install the `[hybrid]` extra (that pulls OCR/model deps).

- [ ] **Step 2: Add the function.** After `paper_review_pipeline` in `app.py`:

```python
@app.function(
    image=opendataloader_image,
    timeout=120,
    cpu=2.0,
    memory=3072,
    max_containers=4,
)
def pdf_structure_run(pdf_bytes: bytes) -> dict:
    """Run OpenDataLoader (default local mode) on a PDF and return
    {markdown, json, summary}. Ephemeral: writes into a temp dir that is
    deleted on return. No OCR / hybrid / model. Nothing is retained."""
    import subprocess
    import tempfile
    from pathlib import Path

    import opendataloader_pdf
    from latextools import pdf_structure

    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        workdir = Path(d)
        in_pdf = workdir / "input.pdf"
        out_dir = workdir / "out"
        out_dir.mkdir()
        in_pdf.write_bytes(pdf_bytes)

        kwargs = pdf_structure.safe_convert_kwargs(str(in_pdf), str(out_dir))
        try:
            opendataloader_pdf.convert(**kwargs)
        except subprocess.TimeoutExpired:
            return {"error": "timeout"}
        except subprocess.CalledProcessError as e:
            return {"error": "parse", "detail": (getattr(e, "stderr", "") or "")[:500]}
        except FileNotFoundError:
            return {"error": "parse", "detail": "java runtime not found"}
        except Exception as e:  # noqa: BLE001 — surface as a generic parse failure
            return {"error": "parse", "detail": f"{type(e).__name__}: {str(e)[:200]}"}

        def _read(name):
            return (out_dir / name).read_text(encoding="utf-8", errors="replace")

        def _list(_):
            # outputs may be written into a subfolder; search recursively
            return [str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file()]

        # parse_output_dir expects read_text(name) to resolve against out_dir:
        def _read_rel(rel):
            return (out_dir / rel).read_text(encoding="utf-8", errors="replace")

        result = pdf_structure.parse_output_dir(out_dir, _read_rel, _list)
        if not result["markdown"] and not result["json"]:
            return {"error": "empty"}
        return result
```

> Note: OpenDataLoader may write outputs into a per-file subfolder of
> `output_folder`. The recursive `_list` + relative-path `_read_rel` handle
> both flat and nested layouts. Confirm in the Task 7 smoke test and tighten
> if needed.

- [ ] **Step 3: Syntax check.**

Run: `cd backend && python3 -c "import ast; ast.parse(open('app.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit.**

```bash
git add backend/app.py
git commit -m "feat(pdf-structure): dedicated JVM Modal function + isolated image"
```

---

## Task 3: `POST /pdf-structure` endpoint

**Files:**
- Modify: `backend/app.py` (inside `web()`, after the `/file-to-markdown` endpoint, before the `/paper-review/*` block)

- [ ] **Step 1: Add the endpoint.**

```python
    @api.post("/pdf-structure")
    async def pdf_structure_endpoint(
        request: Request,
        file: UploadFile = File(...),
    ):
        if not _enforce_rate_limit(request, "pdf-structure"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PDF_UPLOAD_BYTES):
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        data = await file.read()
        try:
            core.validate_pdf_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse(
                {"error": "invalid", "detail": "File is not a valid PDF."},
                status_code=400,
            )

        try:
            result = await run_in_threadpool(lambda: pdf_structure_run.remote(data))
        except Exception:
            logger.exception("pdf-structure run failed")
            return JSONResponse(
                {"error": "convert", "detail": "Couldn't process this PDF."},
                status_code=422,
            )

        err = result.get("error") if isinstance(result, dict) else "convert"
        if err == "timeout":
            return JSONResponse({"error": "convert", "detail": "This PDF took too long to process. Try a smaller or simpler file."}, status_code=422)
        if err in ("parse", "empty"):
            return JSONResponse({"error": "convert", "detail": "No structured content could be extracted from this PDF."}, status_code=422)
        if err:
            return JSONResponse({"error": "convert", "detail": "Couldn't process this PDF."}, status_code=422)

        return JSONResponse(
            {
                "markdown": result.get("markdown", ""),
                "structured": result.get("json", {}),
                "summary": result.get("summary", {}),
            },
            headers={"X-Content-Type-Options": "nosniff"},
        )
```

- [ ] **Step 2: Syntax check + confirm endpoint wired.**

Run:
```bash
cd backend && python3 -c "
import ast
t=ast.parse(open('app.py').read()); eps=[]
for n in ast.walk(t):
    if isinstance(n,(ast.AsyncFunctionDef,ast.FunctionDef)):
        for d in n.decorator_list:
            if isinstance(d,ast.Call) and getattr(d.func,'attr','') in ('post','get') and d.args and isinstance(d.args[0],ast.Constant):
                eps.append(d.args[0].value)
print('/pdf-structure' in eps)"
```
Expected: `True`

- [ ] **Step 3: Commit.**

```bash
git add backend/app.py
git commit -m "feat(pdf-structure): add POST /pdf-structure endpoint"
```

---

## Task 4: Frontend — page, CSS, controller

**Files:**
- Create: `site/tools/pdf-structure/index.html`
- Create: `site/tools/pdf-structure/pdf-structure.css`
- Create: `site/tools/pdf-structure/pdf-structure.js`

- [ ] **Step 1: Create `index.html`.** Copy the structure of
  `site/tools/bib-validator/index.html` (topbar, hero, tool-app, how-to, FAQ,
  moderntex CTA, related-tools, footer). Set:
  - `<title>PDF to Structured Data - Markdown & JSON for AI/RAG | Purplelink</title>`
  - canonical/OG/twitter URLs `https://purplelink.llc/tools/pdf-structure/`
  - JSON-LD `@graph`: `WebApplication` (name "PDF to Structured Data",
    `applicationCategory` "UtilitiesApplication", `offers` price "0",
    featureList: reading-order Markdown, table extraction, math as LaTeX,
    figure captions, RAG-ready JSON, files never stored), `FAQPage` (3 Qs:
    what formats / is it stored / how is it different from File-to-Markdown),
    `BreadcrumbList`.
  - `<link rel="stylesheet" href="/styles.css">`, then
    `<link rel="stylesheet" href="/tools/pdf-structure/pdf-structure.css">`,
    `<script src="/site.js" defer></script>`.
  - Body of `.tool-app`:

```html
<div class="tool-app">
  <div class="dropzone" id="dropzone" aria-label="Upload a PDF">
    <input type="file" id="file" accept=".pdf">
    <p>Drag a <code>.pdf</code> here, or click to choose. Max 20 MB.</p>
    <p id="filename" class="tool-privacy"></p>
  </div>
  <div class="tool-options" style="margin-top:0.75rem">
    <button type="button" class="btn btn-primary" id="run" disabled>Extract structure</button>
  </div>
  <p class="tool-status" id="status" aria-live="polite"></p>

  <div id="ps-summary" class="ps-summary" hidden></div>
  <div id="ps-result" class="ps-result" hidden>
    <div class="ps-tabs" role="tablist" aria-label="Output format">
      <button type="button" id="tab-md" role="tab" aria-selected="true" aria-controls="pane-md">Markdown</button>
      <button type="button" id="tab-json" role="tab" aria-selected="false" aria-controls="pane-json">JSON</button>
    </div>
    <div id="pane-md" role="tabpanel" aria-labelledby="tab-md">
      <div class="ps-actions">
        <button type="button" class="btn btn-secondary" id="dl-md">Download .md</button>
        <button type="button" class="btn btn-secondary" id="copy-md">Copy</button>
      </div>
      <article id="md-out" class="ps-md"></article>
    </div>
    <div id="pane-json" role="tabpanel" aria-labelledby="tab-json" hidden>
      <div class="ps-actions">
        <button type="button" class="btn btn-secondary" id="dl-json">Download .json</button>
        <button type="button" class="btn btn-secondary" id="copy-json">Copy</button>
      </div>
      <pre class="ps-json"><code id="json-out"></code></pre>
    </div>
  </div>

  <p class="tool-privacy">Your PDF is processed in memory and discarded immediately — nothing is stored. Extraction runs on a hosted engine (<a href="/tools/pdf-structure/ATTRIBUTION.md">OpenDataLoader, Apache-2.0</a>); your document never leaves our infrastructure.</p>
</div>
<script src="/tools/tools.js" defer></script>
<script src="/tools/pdf-structure/pdf-structure.js" defer></script>
```

- [ ] **Step 2: Create `pdf-structure.css`** (theme tokens, both modes):

```css
/* PDF to Structured Data — page styles. External file (CSP style-src 'self'). */
.ps-summary { display:flex; flex-wrap:wrap; gap:1rem; margin:1.25rem 0 0.5rem; font-size:.9rem; color:var(--muted); }
.ps-summary strong { color:var(--ink); font-variant-numeric:tabular-nums; }
.ps-tabs { display:flex; gap:.5rem; margin:1.25rem 0 .6rem; }
.ps-tabs button { background:transparent; border:1px solid var(--line); color:var(--muted); padding:.35rem .85rem; border-radius:8px; font:inherit; font-size:.85rem; cursor:pointer; }
.ps-tabs button[aria-selected="true"] { background:color-mix(in oklch, var(--purple) 14%, transparent); border-color:color-mix(in oklch, var(--purple) 55%, transparent); color:var(--ink); font-weight:600; }
.ps-actions { display:flex; gap:.6rem; margin-bottom:.6rem; flex-wrap:wrap; }
.ps-md { line-height:1.6; color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:1rem 1.2rem; max-height:32rem; overflow:auto; background:var(--panel); }
.ps-md h1,.ps-md h2,.ps-md h3 { font-family:"Fraunces",Georgia,serif; }
.ps-md table { border-collapse:collapse; width:100%; font-size:.9rem; }
.ps-md th,.ps-md td { border:1px solid var(--line); padding:.35rem .6rem; text-align:left; }
.ps-json { background:#0f0f17; color:#e3e3ea; border:1px solid color-mix(in oklch, var(--ink) 20%, transparent); border-radius:8px; padding:.8rem 1rem; font-size:.78rem; line-height:1.5; max-height:32rem; overflow:auto; white-space:pre; }
```

- [ ] **Step 3: Create `pdf-structure.js`.** Reuse `wireDropzone`,
  `escapeHtml`, `API_BASE`. Copy the hardened `renderMarkdown()` from
  `site/tools/paper-review/status.js` verbatim (escape-first, strip invisible
  Unicode, no raw HTML / `<img>` / `<a>`). Controller:

```js
(function () {
  var chosen = null, lastMd = "", lastJson = "";
  var fileEl = document.getElementById("file");
  var nameEl = document.getElementById("filename");
  var runBtn = document.getElementById("run");
  var statusEl = document.getElementById("status");
  var summaryEl = document.getElementById("ps-summary");
  var resultEl = document.getElementById("ps-result");
  var mdOut = document.getElementById("md-out");
  var jsonOut = document.getElementById("json-out");
  var tabMd = document.getElementById("tab-md"), tabJson = document.getElementById("tab-json");
  var paneMd = document.getElementById("pane-md"), paneJson = document.getElementById("pane-json");

  function renderMarkdown(md){ /* PASTE the hardened renderer from status.js */ }

  wireDropzone("dropzone", "file", function (f) {
    if (!f.name.toLowerCase().endsWith(".pdf")) { statusEl.textContent="Please choose a PDF."; return; }
    if (f.size === 0) { statusEl.textContent="That file is empty."; return; }
    if (f.size > 20*1024*1024) { statusEl.textContent="File is too large (max 20 MB)."; return; }
    chosen = f; nameEl.textContent = f.name + " (" + Math.round(f.size/1024) + " KB)"; statusEl.textContent=""; runBtn.disabled=false;
  });

  function setTab(which){ var md=which==="md"; tabMd.setAttribute("aria-selected",md?"true":"false"); tabJson.setAttribute("aria-selected",md?"false":"true"); paneMd.hidden=!md; paneJson.hidden=md; }
  tabMd.addEventListener("click", function(){ setTab("md"); });
  tabJson.addEventListener("click", function(){ setTab("json"); });

  function dl(text, name, mime){ var b=new Blob([text],{type:mime}); var u=URL.createObjectURL(b); var a=document.createElement("a"); a.href=u; a.download=name; a.click(); URL.revokeObjectURL(u); }
  function copy(btn, text){ navigator.clipboard.writeText(text).then(function(){ var o=btn.textContent; btn.textContent="Copied!"; setTimeout(function(){btn.textContent=o;},2000); }); }
  document.getElementById("dl-md").addEventListener("click", function(){ dl(lastMd, "structured.md", "text/markdown"); });
  document.getElementById("dl-json").addEventListener("click", function(){ dl(lastJson, "structured.json", "application/json"); });
  document.getElementById("copy-md").addEventListener("click", function(e){ copy(e.target, lastMd); });
  document.getElementById("copy-json").addEventListener("click", function(e){ copy(e.target, lastJson); });

  runBtn.addEventListener("click", function () {
    if (!chosen) return;
    runBtn.disabled = true;
    statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Extracting… this can take a few seconds.';
    resultEl.hidden = true; summaryEl.hidden = true;
    var fd = new FormData(); fd.append("file", chosen, chosen.name);
    fetch(API_BASE + "/pdf-structure", { method:"POST", body:fd })
      .then(function(r){ if(!r.ok) return r.json().then(function(p){ throw p; }); return r.json(); })
      .then(function(data){
        statusEl.textContent = "Done.";
        lastMd = data.markdown || "";
        lastJson = JSON.stringify(data.structured || {}, null, 2);
        mdOut.innerHTML = renderMarkdown(lastMd);
        jsonOut.textContent = lastJson;
        var s = data.summary || {};
        summaryEl.innerHTML = "<span><strong>"+(s.pages||0)+"</strong> pages</span>" +
          "<span><strong>"+(s.tables||0)+"</strong> tables</span>" +
          "<span><strong>"+(s.figures||0)+"</strong> figures</span>" +
          "<span><strong>"+(s.words||0).toLocaleString()+"</strong> words</span>";
        summaryEl.hidden = false; resultEl.hidden = false; setTab("md");
        runBtn.disabled = false;
      })
      .catch(function(err){
        statusEl.textContent = "";
        var msg = (err && err.detail) ? escapeHtml(err.detail) : (err && err.error==="rate_limited" ? "You've reached the daily limit. Try again tomorrow." : "Something went wrong. Please try again.");
        resultEl.hidden = true; summaryEl.hidden = true;
        statusEl.innerHTML = '<span class="bib-err">'+msg+'</span>';
        runBtn.disabled = false;
      });
  });
})();
```

- [ ] **Step 4: Syntax check JS.**

Run: `node --check site/tools/pdf-structure/pdf-structure.js && echo OK`
Expected: `OK` (after pasting the real `renderMarkdown` body).

- [ ] **Step 5: Commit.**

```bash
git add site/tools/pdf-structure/
git commit -m "feat(pdf-structure): tool page, styles, controller"
```

---

## Task 5: Attribution file

**Files:**
- Create: `site/tools/pdf-structure/ATTRIBUTION.md`

- [ ] **Step 1: Write the attribution.**

```markdown
# PDF to Structured Data — third-party attributions

This tool's extraction engine is **OpenDataLoader-PDF**, © Hancom, Inc.,
licensed under the Apache License 2.0. It bundles Apache PDFBox (Apache-2.0)
and veraPDF components (used under the Mozilla Public License 2.0).

- OpenDataLoader-PDF: https://github.com/opendataloader-project/opendataloader-pdf (Apache-2.0)
- Apache PDFBox: https://pdfbox.apache.org/ (Apache-2.0)
- veraPDF: https://verapdf.org/ (MPL-2.0)

Full Apache-2.0 license text: https://www.apache.org/licenses/LICENSE-2.0

Purplelink LLC does not claim endorsement by, or affiliation with, any of
the above projects. We retain no copies of uploaded documents.
```

- [ ] **Step 2: Commit.**

```bash
git add site/tools/pdf-structure/ATTRIBUTION.md
git commit -m "docs(pdf-structure): third-party attributions"
```

---

## Task 6: Wire the tool into the site (index, sitemap, llms.txt)

**Files:**
- Modify: `site/tools/index.html`
- Modify: `site/sitemap.xml`
- Modify: `site/llms.txt`

- [ ] **Step 1: Add a tool card** to `site/tools/index.html` in the
  "Convert between formats" `.tools-grid` (after the File-to-Markdown card):

```html
<a class="tool-card" href="/tools/pdf-structure/">
  <h3>PDF to Structured Data</h3>
  <p>Turn a PDF into reading-order Markdown and RAG-ready JSON — tables, math as LaTeX, and figure captions preserved.</p>
</a>
```

- [ ] **Step 2: Add it to the page's JSON-LD `ItemList`** (bump positions as
  needed) with name "PDF to Structured Data", url
  `https://purplelink.llc/tools/pdf-structure/`.

- [ ] **Step 3: Add the sitemap entry** to `site/sitemap.xml` (next to the
  other `/tools/*` URLs):

```xml
  <url>
    <loc>https://purplelink.llc/tools/pdf-structure/</loc>
    <lastmod>2026-06-02</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
```

- [ ] **Step 4: Add the llms.txt entry** under the free-tools list in
  `site/llms.txt`:

```
- PDF to Structured Data: https://purplelink.llc/tools/pdf-structure/ — convert a PDF to reading-order Markdown and RAG-ready JSON (tables, math as LaTeX, figure captions), powered by OpenDataLoader (Apache-2.0), files never stored.
```

- [ ] **Step 5: Commit.**

```bash
git add site/tools/index.html site/sitemap.xml site/llms.txt
git commit -m "feat(pdf-structure): list tool in index, sitemap, llms.txt"
```

---

## Task 7: Verification

**Files:** none (verification only).

- [ ] **Step 1: Unit tests pass.**

Run: `cd backend && python3 -m pytest tests/test_pdf_structure.py -v`
Expected: PASS.

- [ ] **Step 2: Backend smoke test against the JVM function.** Deploy to a
  Modal dev environment (or run ephemerally) and exercise the function on a
  real academic PDF:

```bash
cd backend && modal run app.py::pdf_structure_run --pdf-bytes "$(: use a small test; or add a temporary __main__ entry that reads a local sample.pdf)"
```
Simpler: add a throwaway local entrypoint or call `pdf_structure_run.remote()` from `modal run`. Assert the returned dict has non-empty `markdown` and a `summary` with `pages >= 1`. Confirm no files persist (the temp dir is inside the container and gone on return).

- [ ] **Step 3: Endpoint smoke test (after `modal deploy`).**

```bash
curl -s -X POST "https://ben-ampel--purplelink-latextools-web.modal.run/pdf-structure" -F "file=@sample.pdf" | python3 -m json.tool | head -30
# Expect: {"markdown": "...", "structured": {...}, "summary": {...}}
curl -s -o /dev/null -w "%{http_code}\n" -X POST ".../pdf-structure" -F "file=@notapdf.txt"   # expect 400
```

- [ ] **Step 4: Frontend in browser (preview, both modes).** Start the
  preview, open `/tools/pdf-structure/`, upload a PDF, confirm: summary line,
  Markdown tab renders (tables visible), JSON tab shows formatted JSON,
  download + copy work. Check `prefers-color-scheme` light AND dark.
  Confirm zero CSP violations in the console. Confirm only an upload request
  fires (no third-party calls).

- [ ] **Step 5: Confirm sitemap/llms entries + node check all JS.**

Run: `node --check site/tools/pdf-structure/pdf-structure.js && grep -c pdf-structure site/sitemap.xml site/llms.txt site/tools/index.html`
Expected: `OK` + non-zero counts in each file.

- [ ] **Step 6: Deploy.**

```bash
bash scripts/deploy.sh --backend --message "Add free PDF-to-Structured-Data tool (OpenDataLoader, Apache-2.0)"
```

---

## Self-review notes (author)

- **Spec coverage:** v1 Markdown+JSON (Tasks 1,3,4) ✓; dedicated JVM function
  (Task 2) ✓; synchronous (Task 3 `.remote()` in threadpool) ✓; new separate
  tool (Task 4/6, File-to-Markdown untouched) ✓; license/attribution (Task 5,
  audit referenced) ✓; CLI-flags-unknown resolved first (Task 0) ✓;
  verification incl. nothing-persisted (Task 7) ✓.
- **Out of scope** (OCR/vision/PDF-UA/paid) — `build_argv` test asserts OCR +
  vision are never enabled.
- **Open dependency:** Task 0 outputs (real flags, JAR coords, JSON key names)
  feed Tasks 1–2; the plan flags every spot to update with real values.
- **Type consistency:** endpoint returns `{markdown, structured, summary}`;
  the JS reads `data.markdown` / `data.structured` / `data.summary` — matched.
  Backend function returns `{markdown, json, summary}`; the endpoint maps
  `json → structured` deliberately (to avoid the JS reserved-ish key) — noted.
```
