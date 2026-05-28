# LaTeX Tools — Plan 2: LaTeX → Word Tool

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Prerequisite:** Plan 1 (`2026-05-28-latex-tools-plan-1-foundation.md`) is complete and deployed — the Modal app, `latextools` package, `site/tools/` pages, shared `tools.js`, and CSS all exist.

**Goal:** Add the third tool — LaTeX → Word — that converts an uploaded `.tex` into a standard double-spaced manuscript `.docx`, with an optional "anonymize" mode.

**Architecture:** Extend the existing Modal image with pandoc + python-docx. Vendor the existing, validated `format_docx.py` into the backend as `latextools/docx_format.py`, adapted so author removal is opt-in (anonymize). A new `convert_to_manuscript` runner runs `pandoc .tex → base.docx`, then the post-processor, and returns `.docx` bytes. A new `POST /convert` endpoint and a `/tools/latex-to-word/` page complete it.

**Tech Stack:** pandoc, python-docx, lxml; existing Modal/FastAPI backend; static HTML/vanilla JS.

**Spec:** `docs/superpowers/specs/2026-05-28-latex-tools-design.md` (§latex-to-word)

**Source of the post-processor:** `/Users/benampel/Library/CloudStorage/OneDrive-Personal/Research/1. In Progress/Other/EJIS_JFC_Commentary/scripts/format_docx.py` — a working, validated script. Its top-level constants (`BODY_FONT="Times New Roman"`, `BODY_SIZE_PT=12`, double spacing, 1-inch US-Letter margins, 0.5" indent, multilevel heading numbering, `Figure N.`/`Table N.` captions, Table Style 2) ARE the standard-manuscript format. Its `.bib`-dependent features (`fix_citations`, `fix_bibliography_field`, `_inject_bibliography_xml`) are already guarded behind an optional `bib_path` argument and are simply not used in the single-file MVP.

---

## File Structure

**Backend:**
- `backend/latextools/docx_format.py` — vendored post-processor (copied from source, one targeted edit for anonymize). Exposes `format_docx(input_path, output_path=None, tex_path=None, anonymize=False)`.
- `backend/latextools/runner.py` — add `convert_to_manuscript(workdir, tex_source, anonymize) -> ConvertResult` (modify).
- `backend/app.py` — add pandoc + python-docx/lxml to the image; add `convert_tex` Modal function + `POST /convert` route (modify).
- `backend/requirements-dev.txt` — add `python-docx`, `lxml` (modify).
- `backend/tests/fixtures/manuscript.tex` — a paper-shaped fixture (title, author, abstract, sections, a figure, a table).
- `backend/tests/test_docx_format.py` — unit tests for the pure string helpers.
- `backend/tests/test_convert_integration.py` — in-image integration tests (pandoc + format).

**Frontend:**
- `site/tools/tools.js` — add `postForDownload` (modify).
- `site/tools/latex-to-word/index.html` — the tool page (create).
- `site/sitemap.xml`, `site/llms.txt` — add the word-tool URL (modify).

---

## Task 1: Extend the Modal image with pandoc + python-docx

**Files:**
- Modify: `backend/app.py`
- Modify: `backend/requirements-dev.txt`

- [ ] **Step 1: Add python-docx and lxml to dev requirements**

Append to `backend/requirements-dev.txt`:
```
python-docx==1.1.2
lxml==5.3.0
```

- [ ] **Step 2: Install the new dev deps**

Run: `cd backend && . .venv/bin/activate && pip install -r requirements-dev.txt`
Expected: python-docx and lxml install successfully.

- [ ] **Step 3: Add pandoc (apt) and python-docx/lxml (pip) to the image**

In `backend/app.py`, modify the `image` definition: add `"pandoc"` to the `.apt_install(...)` list and change the `.pip_install(...)` call to include the docx libs:
```python
    .pip_install(
        "fastapi[standard]==0.115.2",
        "python-docx==1.1.2",
        "lxml==5.3.0",
    )
```
And in `.apt_install(...)`, add `"pandoc",` to the existing list.

- [ ] **Step 4: Verify pandoc is in the rebuilt image**

Add a temporary function to `backend/app.py`:
```python
@app.function(image=image)
def _pandoc_check() -> str:
    import shutil
    assert shutil.which("pandoc"), "pandoc missing"
    import docx  # noqa: F401
    return "pandoc + python-docx present"
```
Run: `cd backend && . .venv/bin/activate && modal run app.py::_pandoc_check`
Expected: prints `pandoc + python-docx present`.

- [ ] **Step 5: Remove the temporary function and commit**

Delete `_pandoc_check` from `backend/app.py`.
```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/app.py backend/requirements-dev.txt
git commit -m "feat(backend): add pandoc and python-docx to the Modal image"
```

---

## Task 2: Vendor the post-processor

**Files:**
- Create: `backend/latextools/docx_format.py`

- [ ] **Step 1: Copy the validated script verbatim into the package**

Run:
```bash
cp "/Users/benampel/Library/CloudStorage/OneDrive-Personal/Research/1. In Progress/Other/EJIS_JFC_Commentary/scripts/format_docx.py" \
   "/Volumes/Extreme SSD/Purplelink LLC/backend/latextools/docx_format.py"
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd backend && . .venv/bin/activate && python -c "from latextools import docx_format; print(hasattr(docx_format, 'format_docx'))"`
Expected: prints `True`.

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/latextools/docx_format.py
git commit -m "feat(backend): vendor docx manuscript post-processor"
```

---

## Task 3: Unit tests for the pure string helpers

**Files:**
- Test: `backend/tests/test_docx_format.py`

These cover the genuinely pure logic (no Document needed): LaTeX→Unicode, author parsing, surname-particle stripping, rendered-citation prediction.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_docx_format.py`:
```python
from latextools import docx_format as f


def test_latex_to_unicode_umlaut_and_quotes():
    assert f._latex_to_unicode(r'Sch\"on') == "Schön"
    assert f._latex_to_unicode("``hi''") == "“hi”"


def test_parse_authors_lastfirst_and_and():
    authors = f._parse_authors("Smith, John and Doe, Jane")
    assert authors == [("Smith", "John"), ("Doe", "Jane")]


def test_parse_authors_corporate_braced():
    assert f._parse_authors("{World Health Organization}") == [
        ("World Health Organization", "")
    ]


def test_cite_surname_strips_particle():
    assert f._cite_surname("vom Brocke") == "Brocke"


def test_rendered_citation_two_authors():
    entry = {"author": "Smith, John and Doe, Jane", "year": "2020"}
    assert f._rendered_citation(entry) == "Smith and Doe 2020"


def test_rendered_citation_four_authors_uses_etal():
    entry = {"author": "A, X and B, Y and C, Z and D, W", "year": "2021"}
    assert f._rendered_citation(entry) == "A et al. 2021"
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_docx_format.py -q`
Expected: 6 passed. (These functions already exist in the vendored file; this locks their behavior before the Task 4 edit.)

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/tests/test_docx_format.py
git commit -m "test(backend): lock pure helpers in docx_format"
```

---

## Task 4: Make author removal opt-in (anonymize)

The vendored `fix_paragraphs` always deletes the `Author` paragraph. For a standard manuscript we KEEP the author by default and only remove it when anonymizing. We thread an `anonymize` flag from `format_docx` into `fix_paragraphs`.

**Files:**
- Modify: `backend/latextools/docx_format.py`
- Test: `backend/tests/test_docx_format.py`

- [ ] **Step 1: Write the failing test (signature contract)**

Append to `backend/tests/test_docx_format.py`:
```python
import inspect


def test_format_docx_accepts_anonymize():
    sig = inspect.signature(f.format_docx)
    assert "anonymize" in sig.parameters
    assert sig.parameters["anonymize"].default is False


def test_fix_paragraphs_accepts_anonymize():
    sig = inspect.signature(f.fix_paragraphs)
    assert "anonymize" in sig.parameters
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_docx_format.py -k anonymize -q`
Expected: FAIL — `anonymize` not in the signatures.

- [ ] **Step 3: Edit `fix_paragraphs` to take `anonymize` and gate Author handling**

In `backend/latextools/docx_format.py`, change the `fix_paragraphs` definition line:
```python
def fix_paragraphs(doc, anonymize=False):
```
Replace the existing `Author` branch:
```python
        # --- Author (remove entirely) ---
        elif style_name == "Author":
            para._element.getparent().remove(para._element)
            counts["author"] += 1
```
with:
```python
        # --- Author: remove if anonymizing, else style as a centered block ---
        elif style_name == "Author":
            if anonymize:
                para._element.getparent().remove(para._element)
            else:
                set_spacing(ppr, line=LINE_SPACING_SINGLE, before=0, after=120)
                set_alignment(ppr, "center")
                clear_first_indent(ppr)
                rpr_a = make_clean_rpr(BODY_FONT, BODY_SIZE_PT, bold=False,
                                       italic=False, color=BLACK)
                for run in para.runs:
                    replace_rpr(run._element, rpr_a)
            counts["author"] += 1
```

- [ ] **Step 4: Edit `format_docx` to take `anonymize` and pass it through**

Change the signature:
```python
def format_docx(input_path, output_path=None, hires_image=None,
                bib_path=None, tex_path=None, anonymize=False):
```
Change the `fix_paragraphs(doc)` call to:
```python
    fix_paragraphs(doc, anonymize=anonymize)
```
Update the `__main__` block to add the flag:
```python
    parser.add_argument("--anonymize", action="store_true",
                        help="Remove the author block (double-blind submission)")
```
and pass `anonymize=args.anonymize` into the `format_docx(...)` call at the bottom.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_docx_format.py -q`
Expected: all pass (8 total).

- [ ] **Step 6: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/latextools/docx_format.py backend/tests/test_docx_format.py
git commit -m "feat(backend): make author removal opt-in via anonymize flag"
```

---

## Task 5: Manuscript fixture + convert runner

**Files:**
- Create: `backend/tests/fixtures/manuscript.tex`
- Modify: `backend/latextools/runner.py`
- Test: `backend/tests/test_convert_integration.py`

- [ ] **Step 1: Create the manuscript fixture**

`backend/tests/fixtures/manuscript.tex`:
```latex
\documentclass{article}
\title{A Standard Manuscript}
\author{Jane Researcher}
\begin{document}
\maketitle
\begin{abstract}
This is the abstract.
\end{abstract}
\textbf{Keywords:} alpha, beta, gamma

\section{Introduction}
Body text referencing Figure 1 and Table 1.

\section{Methods}
\subsection{Design}
More text.

\begin{figure}
\caption{A figure caption.}
\end{figure}

\begin{table}
\caption{A table caption.}
\begin{tabular}{ll}
A & B \\
1 & 2 \\
\end{tabular}
\end{table}

\section*{References}
\end{document}
```

- [ ] **Step 2: Write the failing integration test**

`backend/tests/test_convert_integration.py`:
```python
import shutil
from pathlib import Path

import pytest

from latextools import runner

FIXTURES = Path(__file__).parent / "fixtures"
has_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed (run inside image)"
)


@has_pandoc
def test_convert_returns_docx(tmp_path):
    tex = (FIXTURES / "manuscript.tex").read_text()
    result = runner.convert_to_manuscript(tmp_path, tex, anonymize=False)
    assert result.ok is True
    # .docx is a zip; magic bytes "PK"
    assert result.docx_bytes[:2] == b"PK"


@has_pandoc
def test_convert_anonymize_removes_author(tmp_path):
    import io
    from docx import Document

    tex = (FIXTURES / "manuscript.tex").read_text()
    anon = runner.convert_to_manuscript(tmp_path, tex, anonymize=True)
    named = runner.convert_to_manuscript(tmp_path, tex, anonymize=False)
    anon_text = "\n".join(p.text for p in Document(io.BytesIO(anon.docx_bytes)).paragraphs)
    named_text = "\n".join(p.text for p in Document(io.BytesIO(named.docx_bytes)).paragraphs)
    assert "Jane Researcher" in named_text
    assert "Jane Researcher" not in anon_text
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_convert_integration.py -q`
Expected: FAIL with `AttributeError: module 'latextools.runner' has no attribute 'convert_to_manuscript'` (or skipped if pandoc absent locally — the import error still surfaces and must be fixed).

- [ ] **Step 4: Implement the convert runner**

Append to `backend/latextools/runner.py`:
```python
@dataclass
class ConvertResult:
    ok: bool
    docx_bytes: bytes | None
    error: str = ""


def convert_to_manuscript(
    workdir: Path, tex_source: str, anonymize: bool
) -> ConvertResult:
    """pandoc(.tex) -> base.docx, then apply the manuscript post-processor.

    Single-file MVP: no .bib, so native Word citations are skipped (the
    post-processor guards that internally). tex_path is passed so keyword
    injection and cross-references work.
    """
    from latextools import docx_format

    work = Path(workdir)
    tex_path = work / "main.tex"
    base_docx = work / "base.docx"
    out_docx = work / "manuscript.docx"
    tex_path.write_text(tex_source, encoding="utf-8")

    try:
        proc = subprocess.run(
            ["pandoc", str(tex_path), "-o", str(base_docx)],
            cwd=workdir, capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return ConvertResult(False, None, "Conversion timed out.")
    if proc.returncode != 0 or not base_docx.exists():
        return ConvertResult(False, None, proc.stderr.strip()[:500] or "pandoc failed")

    docx_format.format_docx(
        str(base_docx), str(out_docx), tex_path=str(tex_path), anonymize=anonymize
    )
    return ConvertResult(True, out_docx.read_bytes())
```

- [ ] **Step 5: Run the integration tests in the image**

Add a temporary function to `backend/app.py`:
```python
@app.function(image=image)
def _convert_check() -> dict:
    import io
    import tempfile
    from pathlib import Path
    from docx import Document
    from latextools import runner

    tex = (r"\documentclass{article}\title{T}\author{Jane Researcher}"
           r"\begin{document}\maketitle\section{Intro}Hello.\end{document}")
    out = {}
    with tempfile.TemporaryDirectory() as d:
        named = runner.convert_to_manuscript(Path(d), tex, anonymize=False)
        out["ok"] = named.ok and named.docx_bytes[:2] == b"PK"
        txt = "\n".join(p.text for p in Document(io.BytesIO(named.docx_bytes)).paragraphs)
        out["has_author"] = "Jane Researcher" in txt
    with tempfile.TemporaryDirectory() as d:
        anon = runner.convert_to_manuscript(Path(d), tex, anonymize=True)
        txt = "\n".join(p.text for p in Document(io.BytesIO(anon.docx_bytes)).paragraphs)
        out["anon_removes_author"] = "Jane Researcher" not in txt
    return out
```
Run: `cd backend && . .venv/bin/activate && modal run app.py::_convert_check`
Expected: `{'ok': True, 'has_author': True, 'anon_removes_author': True}`.

- [ ] **Step 6: Remove the temporary function and commit**

Delete `_convert_check` from `backend/app.py`.
```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/latextools/runner.py backend/tests/fixtures/manuscript.tex \
  backend/tests/test_convert_integration.py
git commit -m "feat(backend): add pandoc->manuscript convert runner"
```

---

## Task 6: convert Modal function + /convert endpoint

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: Add the convert Modal function**

In `backend/app.py`, after `diff_tex`, add:
```python
@app.function(**_COMPILE_KW)
def convert_tex(tex_source: str, anonymize: bool) -> dict:
    import tempfile
    from pathlib import Path
    from latextools import runner

    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        res = runner.convert_to_manuscript(Path(d), tex_source, anonymize)
    return {"ok": res.ok, "docx": res.docx_bytes, "error": res.error}
```

- [ ] **Step 2: Add the /convert route inside the `web()` ASGI app**

Inside `web()`, after the `/diff` route and before `return api`, add:
```python
    _DOCX_MIME = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    @api.post("/convert")
    async def convert_endpoint(
        request: Request,
        file: UploadFile = File(...),
        anonymize: str = Form("false"),
    ):
        if not _enforce_rate_limit(request):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            tex = await _read_tex(file)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        result = convert_tex.remote(tex, anonymize == "true")
        if not result["ok"]:
            return JSONResponse(
                {"error": "convert", "detail": result["error"]}, status_code=422
            )
        return Response(
            content=result["docx"],
            media_type=_DOCX_MIME,
            headers={
                "Content-Disposition": 'attachment; filename="manuscript.docx"',
                "X-Content-Type-Options": "nosniff",
            },
        )
```

- [ ] **Step 3: Deploy and smoke-test the convert endpoint**

Run:
```bash
cd backend && . .venv/bin/activate && modal deploy app.py
printf '\\documentclass{article}\\title{T}\\author{Jane Researcher}\\begin{document}\\maketitle\\section{Intro}Hi.\\end{document}' > /tmp/m.tex
curl -s -o /tmp/out.docx -w "%{http_code} %{content_type}\n" \
  -F "file=@/tmp/m.tex" -F "anonymize=false" \
  https://ben-ampel--purplelink-latextools-web.modal.run/convert
head -c 2 /tmp/out.docx; echo
```
Expected: `200 application/vnd.openxmlformats-officedocument.wordprocessingml.document` and the file starts with `PK`.

- [ ] **Step 4: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/app.py
git commit -m "feat(backend): add convert Modal function and /convert endpoint"
```

---

## Task 7: Frontend — download helper + word tool page

**Files:**
- Modify: `site/tools/tools.js`
- Create: `site/tools/latex-to-word/index.html`

- [ ] **Step 1: Add a download-only response helper to tools.js**

Append to `site/tools/tools.js`:
```javascript
// POST a FormData; on a file response, offer a download link (no preview).
async function postForDownload(path, formData, statusEl, resultEl, downloadName, mime) {
  statusEl.textContent = "Working… this can take up to a minute.";
  resultEl.innerHTML = "";
  try {
    const resp = await fetch(API_BASE + path, { method: "POST", body: formData });
    const ctype = resp.headers.get("content-type") || "";
    if (resp.ok && ctype.includes(mime)) {
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      statusEl.textContent = "Done.";
      resultEl.innerHTML =
        `<a class="btn btn-primary" href="${url}" download="${downloadName}">Download ${downloadName}</a>`;
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

- [ ] **Step 2: Create the word tool page**

`site/tools/latex-to-word/index.html` — same head/topbar/footer shell as the Plan 1 tool pages (canonical `https://purplelink.llc/tools/latex-to-word/`; title `Convert LaTeX to Word Online — Free | Purplelink LLC`; description `Free online LaTeX to Word converter. Upload a .tex file and download a standard double-spaced manuscript .docx. Files are never stored.`). Body `<main>`:
```html
    <main id="main-content">
      <a class="back-link" href="/tools/">← All tools</a>
      <div class="tools-hero">
        <p class="eyebrow">Free web tool</p>
        <h1>Convert LaTeX to Word</h1>
        <p>Upload a <code>.tex</code> paper and download a standard double-spaced manuscript <code>.docx</code> — Times New Roman 12pt, numbered headings, formatted figures and tables. <strong>Your file is never stored.</strong></p>
      </div>

      <div class="tool-app">
        <div class="dropzone" id="dropzone">
          <input type="file" id="file" accept=".tex">
          <p>Drag a <code>.tex</code> file here, or click to choose. Max 5 MB.</p>
          <p id="filename" class="tool-privacy"></p>
        </div>
        <div class="tool-options">
          <label><input type="checkbox" id="anonymize"> Anonymize (remove author block)</label>
          <button class="btn btn-primary" id="run" disabled>Convert to Word</button>
        </div>
        <p class="tool-status" id="status"></p>
        <div class="tool-result" id="result"></div>
        <p class="tool-privacy">Single self-contained .tex only. Complex custom macros may not convert perfectly. Files are never written to disk.</p>
      </div>

      <section class="tool-faq">
        <h2>About this tool</h2>
        <p>This converts your LaTeX to a Word document using pandoc, then reformats it to a standard double-spaced manuscript: Times New Roman 12pt body, 1-inch margins, multilevel-numbered headings, and "Figure N." / "Table N." captions.</p>
        <details><summary>Are my files stored?</summary><div class="faq-body">No. Your file is converted in an ephemeral container and discarded immediately.</div></details>
        <details><summary>Will my citations become editable Word references?</summary><div class="faq-body">Not yet. Native, editable Word citations need your .bib file, which this single-file tool doesn't accept. For now the reference list is rendered as static text. Multi-file project support is planned.</div></details>
        <details><summary>What does "anonymize" do?</summary><div class="faq-body">It removes the author block for double-blind submission. Leave it unchecked to keep your author line.</div></details>
        <details><summary>Why doesn't my custom formatting carry over?</summary><div class="faq-body">Pandoc handles standard LaTeX well, but heavily customized macros and packages may degrade. The tool targets a clean, standard manuscript layout.</div></details>
      </section>

      <script src="/tools/tools.js"></script>
      <script>
        (function () {
          let chosen = null;
          const statusEl = document.getElementById("status");
          const resultEl = document.getElementById("result");
          const runBtn = document.getElementById("run");
          const nameEl = document.getElementById("filename");
          const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
          wireDropzone("dropzone", "file", function (f) {
            if (!validClientSide(f, statusEl)) { chosen = null; runBtn.disabled = true; return; }
            chosen = f; nameEl.textContent = f.name; statusEl.textContent = ""; runBtn.disabled = false;
          });
          runBtn.addEventListener("click", function () {
            if (!chosen) return;
            const fd = new FormData();
            fd.append("file", chosen);
            fd.append("anonymize", document.getElementById("anonymize").checked ? "true" : "false");
            postForDownload("/convert", fd, statusEl, resultEl, "manuscript.docx", DOCX_MIME);
          });
        })();
      </script>
    </main>
```

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/tools/tools.js site/tools/latex-to-word/index.html
git commit -m "feat(tools): add LaTeX to Word tool page"
```

---

## Task 8: Sitemap + llms.txt

**Files:**
- Modify: `site/sitemap.xml`
- Modify: `site/llms.txt`

- [ ] **Step 1: Add the word-tool URL to the sitemap**

In `site/sitemap.xml`, add before `</urlset>`:
```xml
  <url><loc>https://purplelink.llc/tools/latex-to-word/</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
```

- [ ] **Step 2: Add the word tool to llms.txt**

In `site/llms.txt`, under the `## Tools` section added in Plan 1, add:
```
- LaTeX to Word: https://purplelink.llc/tools/latex-to-word/ — convert a .tex paper to a standard double-spaced Word manuscript, optional anonymize, files never stored.
```

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add site/sitemap.xml site/llms.txt
git commit -m "feat(tools): add latex-to-word to sitemap and llms.txt"
```

---

## Task 9: End-to-end verification + production deploy

**Files:**
- Modify: `backend/tests/test_frontend_e2e.py`

**Sub-skill:** Use the `webapp-testing` skill for serving + Playwright patterns.

- [ ] **Step 1: Add an e2e test for the word tool**

Append to `backend/tests/test_frontend_e2e.py`:
```python
def test_convert_word_end_to_end(server, tmp_path):
    from playwright.sync_api import sync_playwright

    tex = tmp_path / "m.tex"
    tex.write_text(
        r"\documentclass{article}\title{T}\author{Jane}"
        r"\begin{document}\maketitle\section{Intro}Hi.\end{document}"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{server}/tools/latex-to-word/")
        page.set_input_files("#file", str(tex))
        page.click("#run")
        page.wait_for_selector("a[download='manuscript.docx'], .tool-error", timeout=90000)
        assert page.query_selector("a[download='manuscript.docx']") is not None
        browser.close()
```

- [ ] **Step 2: Run the e2e test against the deployed endpoint**

Run:
```bash
cd backend && . .venv/bin/activate
RUN_E2E=1 pytest tests/test_frontend_e2e.py -k convert_word -q
```
Expected: 1 passed.

- [ ] **Step 3: Run the full unit suite**

Run: `cd backend && . .venv/bin/activate && pytest -q`
Expected: all unit tests pass; pandoc/latexmk integration tests skip locally.

- [ ] **Step 4: Deploy the site**

Run: `cd "/Volumes/Extreme SSD/Purplelink LLC/site" && netlify deploy --prod`
Expected: deploy completes.

- [ ] **Step 5: Verify the live page and a real conversion**

Run:
```bash
curl -sI https://purplelink.llc/tools/latex-to-word/ | head -1
```
Expected: `HTTP/2 200`.

Then in a browser at `https://purplelink.llc/tools/latex-to-word/`: upload a small `.tex`, convert, open the downloaded `.docx`, and confirm it is double-spaced with Times New Roman body and numbered headings. Toggle "Anonymize" and confirm the author line disappears.

- [ ] **Step 6: Final commit (if needed)**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC"
git add backend/tests/test_frontend_e2e.py
git commit -m "test(tools): add end-to-end test for LaTeX to Word"
```

---

## Done criteria (Plan 2)

- `/tools/latex-to-word/` is live and reachable from the hub and nav.
- Uploading a `.tex` returns a standard double-spaced manuscript `.docx` (TNR 12pt body, numbered headings, `Figure N.`/`Table N.` captions).
- The "Anonymize" checkbox removes the author block; unchecked keeps it.
- Conversion failures return a readable error; nothing is stored.
- All unit tests pass; integration + e2e verified.
