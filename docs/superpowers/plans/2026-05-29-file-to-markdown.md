# File to Markdown Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a server-side "File to Markdown" tool (PDF/DOCX/PPTX/XLSX/HTML/CSV/EPUB → Markdown) powered by Microsoft markitdown, exposed as one Modal endpoint plus one static tool page.

**Architecture:** markitdown is Python, so conversion runs in the existing hardened Modal backend (`backend/app.py`) behind a new `/file-to-markdown` endpoint that reuses the established rate-limit → size-guard → validate → magic-byte → threadpool chain. Conversion logic lives in a small testable `latextools/doc2md.py` helper; validation/signature logic lives in `latextools/core.py`. The frontend is a static page that POSTs the file and renders the returned Markdown text.

**Tech Stack:** Python 3.11, Modal, FastAPI, `markitdown[pdf,docx,pptx,xlsx]`, pytest; static HTML/CSS/JS frontend (no framework, no build step), `API_BASE` from `site/tools/tools.js`.

**Spec:** `docs/superpowers/specs/2026-05-29-file-to-markdown-design.md`

---

## File Structure

- **Modify** `backend/latextools/core.py` — add `MAX_DOC2MD_UPLOAD_BYTES`, `DOC2MD_ALLOWED_EXTENSIONS`, `validate_doc2md_upload()`, `doc2md_signature_ok()`. (Responsibility: input limits + validation.)
- **Create** `backend/latextools/doc2md.py` — `convert_to_markdown(path) -> str` wrapping markitdown offline. (Responsibility: conversion.)
- **Modify** `backend/app.py` — add `markitdown[pdf,docx,pptx,xlsx]` to the image; add `/file-to-markdown` endpoint. (Responsibility: HTTP glue.)
- **Create** `backend/tests/test_file_to_markdown.py` — unit tests for validation/signature + a markitdown-gated conversion test.
- **Create** `site/tools/file-to-markdown/index.html` — the tool page.
- **Modify** `site/tools/index.html` — add a tool-card.
- **Modify** `scripts/cta_pages.py` — add `file-to-markdown` to `TOOL_SLUGS`.
- **Modify** `site/sitemap.xml`, `site/llms.txt` — add entries.
- **Create** `site/assets/og/file-to-markdown.png` — OG image via existing generator.

---

## Task 1: Backend validation + signature helpers

**Files:**
- Modify: `backend/latextools/core.py` (append after the `validate_pdf_upload` block, ~line 115)
- Test: `backend/tests/test_file_to_markdown.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_file_to_markdown.py`:

```python
import pytest

from latextools import core


def test_validate_doc2md_rejects_empty():
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("a.pdf", 0)


def test_validate_doc2md_rejects_oversize():
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("a.pdf", core.MAX_DOC2MD_UPLOAD_BYTES + 1)


def test_validate_doc2md_rejects_bad_extension():
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("a.zip", 1000)
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("a.mp3", 1000)


def test_validate_doc2md_rejects_path_chars():
    with pytest.raises(core.ValidationError):
        core.validate_doc2md_upload("../a.pdf", 1000)


def test_validate_doc2md_accepts_allowed():
    for name in ("a.pdf", "a.docx", "a.pptx", "a.xlsx",
                 "a.html", "a.htm", "a.csv", "a.epub", "A.PDF"):
        core.validate_doc2md_upload(name, 1000)  # must not raise


def test_signature_pdf():
    assert core.doc2md_signature_ok("a.pdf", b"%PDF-1.7\n...")
    assert not core.doc2md_signature_ok("a.pdf", b"NOTPDF")


def test_signature_zip_office():
    assert core.doc2md_signature_ok("a.docx", b"PK\x03\x04rest")
    assert core.doc2md_signature_ok("a.epub", b"PK\x03\x04rest")
    assert not core.doc2md_signature_ok("a.xlsx", b"notazip")


def test_signature_text_passes():
    assert core.doc2md_signature_ok("a.csv", b"col1,col2\n1,2\n")
    assert core.doc2md_signature_ok("a.html", b"<html></html>")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_file_to_markdown.py -v`
Expected: FAIL — `AttributeError: module 'latextools.core' has no attribute 'MAX_DOC2MD_UPLOAD_BYTES'` (and `validate_doc2md_upload` / `doc2md_signature_ok`).

- [ ] **Step 3: Implement in `core.py`**

Append after `validate_pdf_upload` (after ~line 115):

```python
MAX_DOC2MD_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB cap for files converted to Markdown

DOC2MD_ALLOWED_EXTENSIONS = (
    ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".csv", ".epub",
)


def validate_doc2md_upload(filename: str, size_bytes: int) -> None:
    """Validate a file-to-markdown upload's name and size. Raises ValidationError."""
    if size_bytes <= 0:
        raise ValidationError("File is empty.")
    if size_bytes > MAX_DOC2MD_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large (max {MAX_DOC2MD_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or filename in ("", ".", ".."):
        raise ValidationError("invalid filename")
    if not filename.lower().endswith(DOC2MD_ALLOWED_EXTENSIONS):
        raise ValidationError(
            "Unsupported file type. Allowed: PDF, DOCX, PPTX, XLSX, HTML, CSV, EPUB."
        )


def doc2md_signature_ok(filename: str, data: bytes) -> bool:
    """Lightweight magic-byte check for binary doc2md formats.

    PDF starts with %PDF-; the ZIP-based Office/EPUB formats start with the
    local-file-header signature PK\\x03\\x04. Text formats (.html/.htm/.csv)
    have no reliable signature and pass.
    """
    name = filename.lower()
    if name.endswith(".pdf"):
        return data[:5] == b"%PDF-"
    if name.endswith((".docx", ".pptx", ".xlsx", ".epub")):
        return data[:4] == b"PK\x03\x04"
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_file_to_markdown.py -v`
Expected: PASS (all validation + signature tests; the gated conversion test added in Task 2 is not present yet).

- [ ] **Step 5: Commit**

```bash
git add backend/latextools/core.py backend/tests/test_file_to_markdown.py
git commit -m "feat(backend): add file-to-markdown upload validation + signature check"
```

---

## Task 2: markitdown conversion helper + dependency

**Files:**
- Create: `backend/latextools/doc2md.py`
- Modify: `backend/app.py` (the image `.pip_install(...)` block, ~lines 26-34)
- Test: `backend/tests/test_file_to_markdown.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_file_to_markdown.py`:

```python
import importlib.util

markitdown_installed = pytest.mark.skipif(
    importlib.util.find_spec("markitdown") is None,
    reason="markitdown not installed (run inside the Modal image)",
)


@markitdown_installed
def test_convert_csv_to_markdown(tmp_path):
    from latextools import doc2md
    p = tmp_path / "t.csv"
    p.write_text("name,score\nAda,99\n", encoding="utf-8")
    md = doc2md.convert_to_markdown(str(p))
    assert "Ada" in md
    assert "score" in md


@markitdown_installed
def test_convert_html_to_markdown(tmp_path):
    from latextools import doc2md
    p = tmp_path / "t.html"
    p.write_text("<h1>Title</h1><p>Body text here.</p>", encoding="utf-8")
    md = doc2md.convert_to_markdown(str(p))
    assert "Title" in md
    assert "Body text here." in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_file_to_markdown.py -v`
Expected: the two new tests are SKIPPED locally (markitdown not installed) — that is the correct "fails to run the implementation" signal here. To actually exercise them, install locally: `pip install 'markitdown[pdf,docx,pptx,xlsx]'` then re-run; they then FAIL with `ModuleNotFoundError: No module named 'latextools.doc2md'`.

- [ ] **Step 3: Create `backend/latextools/doc2md.py`**

```python
"""Convert documents to Markdown using Microsoft markitdown.

Offline only: plugins are disabled and no LLM client is configured, so only
the built-in file converters run. Callers must pass a local file path, never a
URL, which keeps markitdown's network/URI converters (YouTube, http fetch)
unreachable.
"""
from markitdown import MarkItDown

_converter = MarkItDown(enable_plugins=False)


def convert_to_markdown(path: str) -> str:
    """Convert a local file to Markdown text. Raises on failure."""
    result = _converter.convert(path)
    # markitdown exposes `.markdown` in recent versions and keeps
    # `.text_content` for backward compatibility; prefer whichever exists.
    return getattr(result, "markdown", None) or result.text_content
```

- [ ] **Step 4: Add the dependency to the Modal image**

In `backend/app.py`, extend the existing `.pip_install(...)` call (currently ~lines 26-34) by adding the markitdown line. The block becomes:

```python
    .pip_install(
        "fastapi[standard]==0.115.2",
        "python-docx==1.1.2",
        "lxml==5.3.0",
        "bibtexparser>=1.3,<2",
        "httpx==0.27.2",
        "markitdown[pdf,docx,pptx,xlsx]==0.1.1",
    )
```

(Confirm the latest stable `markitdown` version at implementation time and pin it; `0.1.1` shown as the expected pin. HTML/CSV/EPUB support is in core — no extra needed.)

- [ ] **Step 5: Verify the helper inside the image**

Run: `cd backend && modal run app.py::web --help` is not a test; instead smoke-test the helper in the image with a throwaway Modal function OR install locally and run:
`pip install 'markitdown[pdf,docx,pptx,xlsx]' && python -m pytest tests/test_file_to_markdown.py -v`
Expected: `test_convert_csv_to_markdown` and `test_convert_html_to_markdown` PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/latextools/doc2md.py backend/app.py backend/tests/test_file_to_markdown.py
git commit -m "feat(backend): add markitdown doc2md helper + image dependency"
```

---

## Task 3: `/file-to-markdown` endpoint

**Files:**
- Modify: `backend/app.py` (insert a new endpoint after `pdf_compress_endpoint`, before the function's closing)

- [ ] **Step 1: Add the endpoint**

In `backend/app.py`, inside `web()`, after the `/pdf-compress` endpoint, add:

```python
    # ------------------------------------------------------------------
    # /file-to-markdown — convert PDF/Office/HTML/CSV/EPUB to Markdown
    # ------------------------------------------------------------------
    @api.post("/file-to-markdown")
    async def file_to_markdown_endpoint(
        request: Request,
        file: UploadFile = File(...),
    ):
        if not _enforce_rate_limit(request, "file-to-markdown"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_DOC2MD_UPLOAD_BYTES):
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        filename = file.filename or ""
        data = await file.read()
        try:
            core.validate_doc2md_upload(filename, len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not core.doc2md_signature_ok(filename, data):
            return JSONResponse(
                {"error": "invalid", "detail": "File contents do not match its type."},
                status_code=400,
            )

        import os.path

        from latextools import doc2md

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                suffix = os.path.splitext(filename)[1].lower()
                in_path = Path(d) / f"input{suffix}"
                in_path.write_bytes(data)
                return doc2md.convert_to_markdown(str(in_path))

        try:
            md = await run_in_threadpool(_do)
        except Exception:
            # markitdown raises a variety of parser errors; the container's
            # request timeout bounds any pathological/slow input.
            return JSONResponse(
                {"error": "convert", "detail": "Couldn't convert this file."},
                status_code=422,
            )
        if not md or not md.strip():
            return JSONResponse(
                {"error": "convert", "detail": "No text could be extracted from this file."},
                status_code=422,
            )
        return JSONResponse(
            {"markdown": md, "filename": filename},
            headers={"X-Content-Type-Options": "nosniff"},
        )
```

- [ ] **Step 2: Deploy to a Modal dev/serve target and smoke test**

Run: `cd backend && modal serve app.py`
Then in another shell, against the printed serve URL `$U`:

```bash
printf 'name,score\nAda,99\n' > /tmp/t.csv
curl -s -X POST "$U/file-to-markdown" -F "file=@/tmp/t.csv" | head -c 300
```
Expected: JSON containing `"markdown"` with `Ada` and `score` in it.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$U/file-to-markdown" -F "file=@/tmp/t.csv;type=application/zip;filename=t.zip"
```
Expected: `400` (disallowed extension).

- [ ] **Step 3: Commit**

```bash
git add backend/app.py
git commit -m "feat(backend): add /file-to-markdown endpoint"
```

---

## Task 4: Frontend tool page

**Files:**
- Create: `site/tools/file-to-markdown/index.html`

- [ ] **Step 1: Create the page**

Create `site/tools/file-to-markdown/index.html`. Base it on `site/tools/markdown-to-pdf/index.html` (closest analog — text result side) and `site/tools/pdf-tools/index.html` (file upload + API_BASE). It MUST include: the standard `<head>` (charset, viewport, robots, title, description, canonical, OG + Twitter card pointing at `/assets/og/file-to-markdown.png`, JSON-LD `SoftwareApplication` + `BreadcrumbList`, theme-color, font preconnect/link, `/styles.css`), the standard topbar nav, and footer. The body's tool app:

```html
    <main id="main-content">
      <a class="back-link" href="/tools/">← All tools</a>
      <div class="tool-hero">
        <h1>File to Markdown</h1>
        <p>Upload a PDF, Word, PowerPoint, Excel, HTML, CSV, or EPUB file and get clean Markdown. Converted on our server with Microsoft markitdown and never stored.</p>
      </div>

      <div class="tool-app">
        <div class="dropzone" id="drop" aria-label="Choose a file to convert">
          <input type="file" id="file"
                 accept=".pdf,.docx,.pptx,.xlsx,.html,.htm,.csv,.epub">
          <p>Drop a file here or click to choose</p>
          <p id="filename" class="tool-privacy"></p>
        </div>
        <div class="tool-options">
          <button class="btn btn-primary" id="run" disabled>Convert to Markdown</button>
        </div>
        <p class="tool-status" id="status" aria-live="polite"></p>

        <div id="result-wrap" hidden>
          <label for="result" class="visually-hidden">Markdown result</label>
          <textarea id="result" class="md-textarea" readonly aria-label="Markdown result"></textarea>
          <div class="tool-options">
            <button class="btn btn-ghost" id="copy">Copy Markdown</button>
            <button class="btn btn-ghost" id="download">Download .md</button>
          </div>
        </div>
        <p class="tool-privacy">Files are converted on our server and deleted right after — nothing is stored.</p>
      </div>

      <nav class="tool-related" aria-label="Related tools">
        <h2>Related tools</h2>
        <ul>
          <li><a href="/tools/markdown-to-pdf/">Markdown to PDF / Word →</a></li>
          <li><a href="/tools/word-to-latex/">Word to LaTeX →</a></li>
          <li><a href="/tools/pdf-tools/">PDF tools →</a></li>
        </ul>
      </nav>
    </main>
```

Reuse the `.md-textarea` style from `markdown-to-pdf` (copy the `<style>` rule into this page's head, or rely on `/styles.css` if the class is already global — check `site/styles.css` for `.md-textarea`; if absent, inline the same rule used in `markdown-to-pdf`).

Inline script before `</body>` (`tools.js` provides `API_BASE`; include `<script src="/tools/tools.js"></script>` first if the page needs it, matching how `pdf-tools` loads it):

```html
    <script src="/tools/tools.js"></script>
    <script>
      (function () {
        const fileInput = document.getElementById("file");
        const runBtn = document.getElementById("run");
        const statusEl = document.getElementById("status");
        const resultWrap = document.getElementById("result-wrap");
        const resultEl = document.getElementById("result");
        const filenameEl = document.getElementById("filename");
        let chosen = null;

        fileInput.addEventListener("change", function () {
          chosen = fileInput.files[0] || null;
          filenameEl.textContent = chosen ? chosen.name : "";
          runBtn.disabled = !chosen;
        });

        runBtn.addEventListener("click", async function () {
          if (!chosen) return;
          runBtn.disabled = true;
          statusEl.textContent = "Converting…";
          resultWrap.hidden = true;
          const fd = new FormData();
          fd.append("file", chosen);
          try {
            const resp = await fetch(API_BASE + "/file-to-markdown", { method: "POST", body: fd });
            if (!resp.ok) {
              let detail = "Conversion failed.";
              try { detail = (await resp.json()).detail || detail; } catch (e) {}
              if (resp.status === 429) detail = "Too many conversions right now. Try again in a bit.";
              statusEl.textContent = detail;
              runBtn.disabled = false;
              return;
            }
            const json = await resp.json();
            resultEl.value = json.markdown || "";
            resultWrap.hidden = false;
            statusEl.textContent = "Done.";
          } catch (e) {
            statusEl.textContent = "Couldn't reach the converter. Check your connection and try again.";
          } finally {
            runBtn.disabled = false;
          }
        });

        document.getElementById("copy").addEventListener("click", async function () {
          try {
            await navigator.clipboard.writeText(resultEl.value);
            statusEl.textContent = "Copied to clipboard.";
          } catch (e) {
            resultEl.select();
            statusEl.textContent = "Press Cmd/Ctrl+C to copy.";
          }
        });

        document.getElementById("download").addEventListener("click", function () {
          const base = (chosen && chosen.name ? chosen.name.replace(/\.[^.]+$/, "") : "converted");
          const blob = new Blob([resultEl.value], { type: "text/markdown" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = base + ".md";
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
        });
      })();
    </script>
```

- [ ] **Step 2: Verify it renders**

Run: `npx serve -l 4200 site` (or the existing `purplelink-site` preview), open `http://localhost:4200/tools/file-to-markdown/`.
Expected: page renders with the dropzone, disabled Convert button that enables on file pick. (End-to-end conversion needs the backend from Tasks 1-3 deployed; test that in Task 6.)

- [ ] **Step 3: Commit**

```bash
git add site/tools/file-to-markdown/index.html
git commit -m "feat(site): add File to Markdown tool page"
```

---

## Task 5: Shared integration (grid, CTA, sitemap, llms.txt, OG)

**Files:**
- Modify: `site/tools/index.html`, `scripts/cta_pages.py`, `site/sitemap.xml`, `site/llms.txt`
- Create: `site/assets/og/file-to-markdown.png`

- [ ] **Step 1: Add the tools-grid card**

In `site/tools/index.html`, add alongside the other `tool-card` anchors (place near `markdown-to-pdf` / `pdf-tools`):

```html
        <a class="tool-card" href="/tools/file-to-markdown/">
          <span class="tool-emoji" aria-hidden="true">📝</span>
          <h3>File → Markdown</h3>
          <p>Convert PDF, Word, PowerPoint, Excel, HTML, or CSV to clean Markdown. Nothing stored.</p>
        </a>
```

- [ ] **Step 2: Register the page for the ModernTex CTA**

In `scripts/cta_pages.py`, add `"file-to-markdown"` to the `TOOL_SLUGS` list (keep alphabetical-ish ordering consistent with the file).

- [ ] **Step 3: Insert the CTA block and verify**

Run:
```bash
python3 scripts/insert_moderntex_cta.py
python3 scripts/verify_moderntex_cta.py
```
Expected: insert reports the new page changed (others skipped); verify prints `OK: all 20 pages have a correct, unique ModernTex CTA block`.

(The Task 4 page intentionally ships WITHOUT a `<!-- moderntex-cta -->` marker so the inserter does not treat it as already-done. The inserter adds both the marker and the waitlist block immediately before the `<nav class="tool-related">` anchor. If `verify` reports 0 markers, confirm the anchor line is present and exactly matches `      <nav class="tool-related"`.)

- [ ] **Step 4: Add sitemap entry**

In `site/sitemap.xml`, add (matching the existing one-line format, today's date):

```xml
  <url><loc>https://purplelink.llc/tools/file-to-markdown/</loc><lastmod>2026-05-29</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>
```

- [ ] **Step 5: Add llms.txt entry**

In `site/llms.txt`, add under the tools list (match the existing dash-bullet format):

```
- File to Markdown: https://purplelink.llc/tools/file-to-markdown/ - convert PDF, Word, PowerPoint, Excel, HTML, CSV, or EPUB to Markdown, files never stored.
```

- [ ] **Step 6: Generate the OG image**

Use the existing OG generator (see `site/assets/og/_gen.html` and how prior tool OG PNGs were produced — task history "Build OG image generator template / Render tool OG images"). Produce `site/assets/og/file-to-markdown.png` (1200×630) with the tool title, matching the other tool cards. Confirm the page's `og:image` / `twitter:image` paths point to it.

- [ ] **Step 7: Commit**

```bash
git add site/tools/index.html scripts/cta_pages.py site/tools/file-to-markdown/index.html site/sitemap.xml site/llms.txt site/assets/og/file-to-markdown.png
git commit -m "feat(site): wire File to Markdown into grid, CTA, sitemap, llms.txt, OG"
```

---

## Task 6: Full verification + deploy (gated on user approval)

**Files:** none (verification + deploy)

- [ ] **Step 1: Backend tests**

Run: `cd backend && python -m pytest tests/test_file_to_markdown.py -v`
Expected: validation/signature tests PASS; conversion tests PASS if markitdown installed locally, else SKIPPED.

- [ ] **Step 2: HTML well-formedness + CTA invariants**

Run:
```bash
python3 - <<'PY'
import glob, html.parser
class P(html.parser.HTMLParser): pass
bad=0
for f in glob.glob('site/**/*.html', recursive=True):
    try: P().feed(open(f, encoding='utf-8').read())
    except Exception as e: print('FAIL', f, e); bad+=1
print('parse failures:', bad)
PY
python3 scripts/verify_moderntex_cta.py
```
Expected: `parse failures: 0`; CTA verify OK for all 20 pages.

- [ ] **Step 3: Deploy backend (only after user approval)**

Run: `cd backend && modal deploy app.py`
Expected: deploy succeeds; `/file-to-markdown` live at the `purplelink-latextools-web` URL.

- [ ] **Step 4: End-to-end smoke against production**

With the deployed `API_BASE`, upload a real DOCX and PDF via the live page (`https://purplelink.llc/tools/file-to-markdown/` after the site deploy, or local preview pointed at the deployed API). Confirm Markdown renders, Copy works, Download yields a `.md` file.

- [ ] **Step 5: Deploy site (only after user approval)**

Run: `netlify deploy --dir=site --prod`
Expected: deploy live; verify the new tool page and its sitemap entry resolve.

- [ ] **Step 6: Final commit (if any uncommitted verification fixes)**

```bash
git add -p   # stage only intended files; never use git add -A
git commit -m "chore: file-to-markdown verification fixes"
```

---

## Notes for the implementer

- **Never** use `git add -A`; stage specific files only. Never commit `.claude/`, `Legal/`, `Social Media/`, or secrets.
- The deploy steps (Task 6, Steps 3 & 5) are **gated** — do not deploy without explicit user approval, even though the plan lists them.
- Privacy is a hard brand constraint: do not add analytics/tracking/cookies to the page.
- markitdown license: confirm MIT in the upstream repo and record attribution consistent with the repo's existing conventions.
