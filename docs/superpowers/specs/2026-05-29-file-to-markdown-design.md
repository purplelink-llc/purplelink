# File to Markdown Tool — Design Spec

**Date:** 2026-05-29
**Status:** Approved (design); pending spec review → implementation plan
**Author:** Purplelink LLC (with Claude)

## Goal

Add a "File to Markdown" tool to the Purplelink tool repository that converts
common document formats (PDF, Word, PowerPoint, Excel, HTML, CSV, EPUB) to
Markdown, powered by Microsoft's [markitdown](https://github.com/microsoft/markitdown)
library. It is the inverse of the existing Markdown→PDF/Word tool.

This is the first of two requested integrations. The second, the
[eigenpal/docx-editor](https://github.com/eigenpal/docx-editor) in-browser
`.docx` editor, is intentionally deferred to its own separate spec because it
is a client-side JS/ProseMirror component with a different (build-step)
integration shape.

## Scope

**In scope (input formats):** PDF, DOCX, PPTX, XLSX, HTML/HTM, CSV, EPUB.
All run fully offline with no API keys.

**Out of scope (by design):**
- Audio transcription and YouTube URLs (require network calls and/or API keys
  — break the offline/privacy posture).
- ZIP archive extraction (widens the security surface).
- Image OCR (extra heavy dependencies; deferred — could be a future option).
- LLM-based image captioning (requires external API keys).

## Architecture

markitdown is a Python library, so conversion runs **server-side** in the
existing hardened Modal backend (`backend/app.py`), exactly like the
`pdf-compress` and `markdown-convert` endpoints. The frontend is a static
tool page that POSTs the file and renders the returned Markdown. No new
infrastructure, no new service — one new endpoint + one new page.

This mirrors the established precedent: `pdf-tools` and `markdown-to-pdf`
already upload files to the Modal backend for server-side processing.

### Units

1. **`latextools/core.py`** — add upload-size constant + validator
   (single responsibility: input validation / limits).
2. **`backend/app.py`** — add the `/file-to-markdown` endpoint
   (single responsibility: HTTP handling + orchestration of markitdown).
3. **`site/tools/file-to-markdown/index.html`** — the static tool page
   (single responsibility: UI + fetch wiring).
4. Shared integration: tools grid entry, sitemap entry, llms.txt entry,
   ModernTex CTA block, OG image.

## Component 1 — Backend endpoint

**File:** `backend/app.py` (new endpoint inside the existing `web()` ASGI app).

- Route: `@api.post("/file-to-markdown")`.
- Signature: `(request: Request, file: UploadFile = File(...))`.
- Safety chain (identical pattern to existing endpoints):
  1. `_enforce_rate_limit(request, "file-to-markdown")` → 429 on limit.
  2. `_too_large(request, core.MAX_DOC2MD_UPLOAD_BYTES)` → 400 on oversize.
  3. `core.validate_doc2md_upload(filename, len(data))` → 400 on bad
     extension / size. Extension allowlist:
     `.pdf .docx .pptx .xlsx .html .htm .csv .epub`.
  4. Magic-byte sniff: `%PDF-` for `.pdf`; `PK\x03\x04` for the ZIP-based
     formats (`.docx .pptx .xlsx .epub`); text formats (`.html .htm .csv`)
     skip the binary signature check.
  5. `run_in_threadpool(_do)` with a `tempfile.TemporaryDirectory(dir="/tmp")`
     workdir and a hard timeout; structured JSON errors on failure/timeout.
- Conversion: instantiate `MarkItDown(enable_plugins=False)` with **no LLM
  client**, write the upload to a temp path, and call `convert(local_path)`
  with a **file path only — never a URL**. This makes the network / YouTube /
  URI-fetch / SSRF code paths unreachable by construction.
- Response: JSON `{ "markdown": "<text>", "filename": "<original>" }` with
  `X-Content-Type-Options: nosniff`. (Text out, not a file download.)
- Error contract (matches existing endpoints):
  - `{"error":"rate_limited"}` 429
  - `{"error":"invalid","detail":"..."}` 400
  - `{"error":"convert","detail":"..."}` 422 (conversion failed/timed out)

**Image dependencies:** add `markitdown[pdf,docx,pptx,xlsx]` to the Modal
image `.pip_install(...)`. HTML, CSV, and EPUB support is in markitdown core
(no extra needed). Pin a specific markitdown version.

**Constants/validator (`latextools/core.py`):**
- `MAX_DOC2MD_UPLOAD_BYTES = 20 * 1024 * 1024` (20 MB, matches PDF).
- `validate_doc2md_upload(filename, size)` → raises `core.ValidationError`
  with a user-facing message on disallowed extension or oversize.

## Component 2 — Frontend page

**File:** `site/tools/file-to-markdown/index.html` (follows the existing tool
template, e.g. `pdf-tools`/`markdown-to-pdf`).

- Hero (title + one-line description), file picker (drag-or-click) constrained
  to the allowlisted extensions via `accept=`.
- "Convert" button → `fetch(MODAL_BASE + "/file-to-markdown", {method:"POST",
  body: FormData})`; loading state during request.
- Result: a `<textarea>` (read-only) showing the Markdown, with **Copy** and
  **Download .md** buttons. Inline error messaging for 400/422/429.
- Full SEO: title/meta/canonical, OG + Twitter card, JSON-LD
  `SoftwareApplication` + `BreadcrumbList`, theme-color.
- Includes the ModernTex CTA block (passes `verify_moderntex_cta.py`
  invariants — add slug to `scripts/cta_pages.py`).
- Privacy copy: "Files are converted on our server and never stored — the
  upload is deleted right after conversion."

**Shared integration:**
- Add card to `site/tools/index.html` tools grid (+ `tools.js` if it drives
  the grid).
- Add `<url>` entry to `site/sitemap.xml`.
- Add entry to `site/llms.txt`.
- Generate an OG image (`site/assets/og/file-to-markdown.png`) via the
  existing OG generator template.

## Data flow

1. User selects a file in the browser.
2. Browser POSTs `multipart/form-data` (the file) to the Modal endpoint.
3. Endpoint validates (rate, size, extension, magic bytes), writes to a
   tempdir, runs markitdown in a threadpool with a timeout.
4. Endpoint returns JSON with the Markdown text; tempdir is deleted.
5. Browser renders the Markdown in a textarea; user copies or downloads `.md`.

## Error handling

- Oversize / disallowed extension / corrupt signature → 400 with a clear
  inline message.
- Conversion failure or timeout → 422 ("Couldn't convert this file").
- Rate limit → 429 ("Too many conversions, try again later").
- Network error in the browser → inline "couldn't reach the converter" message.

## Security & privacy

- **Offline by construction:** only file converters are reachable; no URL is
  ever passed to markitdown, so no network egress / SSRF / YouTube path.
- **No plugins, no LLM:** `enable_plugins=False`, no model client.
- **Bounded resources:** 20 MB cap + the container's existing memory (2048 MB)
  and per-request timeout bound ZIP-based parsing (zip-bomb / decompression
  risk for DOCX/PPTX/XLSX/EPUB).
- **CORS:** unchanged — already locked to `https://purplelink.llc`
  (+ localhost only when `ALLOW_LOCAL_CORS=1`).
- **Nothing stored:** tempdir auto-deleted; no persistence.
- **XML parsing risk:** the Office/EPUB parsers (python-docx, openpyxl,
  python-pptx, ebooklib) do not resolve external entities by default;
  verify during implementation and pin versions.

## Testing

**Backend** (new `backend/tests/test_file_to_markdown.py`, mirroring
`test_convert_integration.py`):
- Known DOCX → expected Markdown substrings (headings/lists).
- Known PDF → expected text substring.
- Known CSV → Markdown table output.
- Oversize upload → 400.
- Disallowed extension (e.g. `.zip`, `.mp3`) → 400.
- Corrupt/empty file with valid extension → 422.
- (Where feasible) rate-limit path → 429.

**Frontend:**
- Manual verify in the local preview: upload one of each supported type,
  confirm Markdown renders, Copy works, Download produces a `.md` file.
- Existing checks: HTML parses; `verify_moderntex_cta.py` passes; the page
  appears in tools grid / sitemap / llms.txt.

## License & attribution

markitdown is published by Microsoft under the **MIT License** (confirm the
exact license text in the repo during implementation and record attribution
in a NOTICE/credits location consistent with the repo's conventions).

## Open questions / future

- Image OCR could be added later as an opt-in (heavier offline deps).
- If conversion latency for large PDFs is high, consider surfacing a progress
  hint; not required for v1.
