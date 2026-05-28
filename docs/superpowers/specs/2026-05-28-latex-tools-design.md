# LaTeX Web Tools Section — Design Spec

**Date:** 2026-05-28
**Status:** Approved design — ready for implementation planning
**Author:** Ben Ampel (with Claude)

## Goal

Add a hosted web-tools section to purplelink.llc offering three free LaTeX utilities for academics:

1. **latex-to-pdf** — upload a `.tex` file, get a compiled PDF.
2. **latex-to-word** — upload a `.tex` file, get a standard double-spaced manuscript `.docx`.
3. **latex-diff** — upload two `.tex` files (old + new), get a `latexdiff` comparison PDF.

## Audience & positioning

- **Public and open** — anyone, no login. Maximizes reach and SEO.
- **Zero file retention** — uploaded files exist only in an ephemeral container during processing, then vanish. Output streams back in the HTTP response; nothing is written to durable storage or logs. This "your files never touch our disk" promise is a genuine selling point for academics handling unpublished manuscripts and is advertised on each page.
- **Ad-ready but ad-free at launch** — the structure (dedicated pages with real content) supports ads later if traffic justifies it, but no ads ship in v1.

## Architecture

Two cleanly separated halves.

### Frontend (Netlify, static)

Vanilla JS, matching the existing `site.js` pattern (no framework). Pages:

- `/tools/` — hub landing page; three cards linking to the tools.
- `/tools/latex-to-pdf/`
- `/tools/latex-to-word/`
- `/tools/latex-diff/`

Each tool page: a drag-and-drop upload zone, tool options, a Run button, and a result area (inline preview where applicable + download button). Each page also carries written intro / how-to / FAQ content for SEO and (future) legitimate ad placement. "Tools" is added to the sitewide top nav.

The frontend calls the backend endpoints directly via `fetch`. **Required infra change:** the Netlify CSP in `netlify.toml` currently permits no external connections; a `connect-src` entry for the Modal endpoint domain must be added.

### Backend (Modal)

One Modal app, one pinned Docker image with the full toolchain baked in: TeX Live (pdfLaTeX + XeLaTeX engines), `latexmk`, `latexdiff`, `biber`/`bibtex`, `pandoc`, and `python-docx` + `lxml` (for the Word post-processor). Three web endpoints:

- `POST /compile` → `application/pdf`
- `POST /convert` → `.docx`
- `POST /diff` → `application/pdf`

Each endpoint runs the heavy work inside a Modal function with strict resource and security limits (below). Modal is chosen for: scale-to-zero ($0 idle, per-second billing when active — right for unpredictable free-tool traffic), ephemeral container isolation (critical for untrusted input), and a single versioned image definition.

Each tool is a self-contained unit (own page, own endpoint) sharing the one Docker image.

## Compilation engine

Each PDF endpoint uses `latexmk` inside the container, which auto-runs the pdflatex→bibtex/biber→pdflatex×2 sequence so multi-pass documents and bibliographies work without manual orchestration. A compiler dropdown on each relevant page selects the engine via latexmk flags:

- **pdfLaTeX** (default)
- **XeLaTeX**

**LuaLaTeX is intentionally excluded from the MVP** (see Security § RCE).

## Security model

Public untrusted LaTeX is dangerous (Turing-complete; known RCE, file-disclosure, and DoS vectors). Defense in depth:

### Remote code execution
- **`\write18` (shell-escape):** disabled via `-no-shell-escape` **and** `shell_escape = f` in `texmf.cnf` (belt + suspenders; "restricted" escape has had bypasses).
- **`\directlua` (LuaLaTeX):** embeds an in-process Lua interpreter with `os.execute`/`io.*` that **bypasses `-no-shell-escape`**. Mitigation: LuaLaTeX is excluded from the MVP. If ever added, run `luatex --safer`.
- **Pipe input** (`\input{|cmd}`): blocked by no-shell-escape + `openin_any = p`.

### File disclosure
- `\input{/etc/passwd}`, `\include`, `\openin`, `\lstinputlisting`, `\verbatiminput`: restricted via `openin_any = p` and `openout_any = p` (paranoid — confines file access to the working dir + system texmf trees, blocks absolute/`../` paths).
- Container is empty and ephemeral — no secrets or other users' files exist to read.

### Denial of service
- **Infinite loops / memory bombs:** hard wall-clock timeout (~60s, SIGKILL) + container CPU/memory caps (OOM-kill).
- **Disk fill:** tmpfs working dir with a size cap + output size cap.
- **Compute amplification:** bounded by timeout, CPU cap, and rate limit.
- Single-file MVP eliminates zip-bomb risk.

### Cost / "wallet" attack
A scripted flood of compiles could run up the Modal bill. CORS does **not** prevent this (browser-enforced only). Real defenses:
- Per-IP daily rate limit (hashed IP, daily TTL, via Modal Dict).
- Global concurrency cap on the Modal app.
- **A hard Modal spend limit + budget alert** (required setup step) bounds worst case.
- Hooks left for hCaptcha / proof-of-work if actively abused (not in MVP).

### Response & isolation
- **XSS via logs:** LaTeX `.log` output contains attacker-controlled text; every character is HTML-escaped before being rendered in the tool page's error panel.
- **Output PDFs:** served `Content-Disposition: attachment` with `X-Content-Type-Options: nosniff`; never rendered executably on our origin.
- Container runs **non-root**, read-only root filesystem except tmpfs `/work`, **network egress blocked**.
- **Input validation:** `.tex` extension, size cap (~5 MB) enforced client- and server-side.

### Supply chain
- Pin the base image, TeX Live version, pandoc, and latexdiff for reproducible, deliberate rebuilds.

## Data flow (compile example)

1. User drops `paper.tex` on `/tools/latex-to-pdf/`; JS validates extension + size, reads engine choice.
2. `fetch` POSTs `multipart/form-data` to Modal `/compile`.
3. Modal spins an ephemeral container, writes the file to tmpfs `/work`, runs `latexmk` with the hardening flags.
4. **Success:** PDF streams back as the response body → JS shows an inline preview + download button. Nothing stored.
5. **Failure:** backend parses the `.log`, extracts `!`-prefixed error lines with line numbers, returns them as JSON; the frontend shows a readable, HTML-escaped diagnostic panel (echoing ModernTex's "plain-language diagnostics" brand value).

### Error states (all tools)
- Compilation error → readable diagnostic panel (escaped log excerpt + line numbers).
- Timeout → "Compilation took too long (>60s) — your document may have an infinite loop or be too large for the free tool."
- Rate limit → "You've reached the daily limit. Try again tomorrow."
- Bad file → caught client-side before upload.

## Per-tool details

### latex-to-pdf
`latexmk` + engine dropdown (pdfLaTeX/XeLaTeX). The core tool.

### latex-diff
Two uploads (old + new). Runs `latexdiff` with safe defaults baked in:
- `--type=UNDERLINE` (blue underline = added, red strikethrough = deleted).
- `--config="PICTUREENV=(?:picture|DIFnomarkup|tabular)[\w\d*@]*"` — treats tables as opaque blocks, preventing the common `Missing \cr` table-corruption crash. **Caveat surfaced in UI:** changes *inside* tables are shown in final state only, not marked.
- Then compiles the diff with `latexmk`.
- Optional checkbox: "add a legend explaining the colors" — auto-injects a "how to read this revision diff" box after `\maketitle`.
- Advanced flags (`--append-textcmd`, `--append-safecmd`) deferred — template-specific.

### latex-to-word
Pipeline: `pandoc paper.tex → base.docx` → **standard-manuscript post-processor** → final `.docx`.

The post-processor is a generalized version of the existing `format_docx.py` (in the EJIS_JFC_Commentary project). It produces **one universal standard manuscript format** — not journal-specific presets:

- Times New Roman 12pt body; Arial 10pt tables/figures.
- Double-spaced body, single-spaced headings/captions/tables.
- 1-inch margins, US Letter.
- 0.5" first-line indent; fully justified body.
- Auto multilevel heading numbering (1 / 1.1 / 1.1.1); References, Acknowledgments, Appendix unnumbered (with page break before References).
- `Figure N.` / `Table N.` caption prefixes, Arial 10pt, glued to their object via `keepNext`.
- Clean horizontal-rule table styling ("Table Style 2": top rule, thick header bottom rule, thin row rules, no vertical borders).
- All Word theme font/color references stripped (explicit values only).
- Keyword paragraph injected from the `.tex` source after the abstract.

**Options:**
- "Anonymize (remove author block)" checkbox — for double-blind submission. The script already supports author removal.

**Caveats:**
- Pandoc handles standard LaTeX well; complex custom macros/packages degrade. Honest expectations set on the page.
- **Native, editable Word bibliography** (parsing `.bib` into Word citation sources) requires the `.bib` file, which the single-file MVP cannot accept. **Deferred to the ZIP-upload phase.** v1 single-file gives full body formatting + a pandoc-rendered static reference list.

## Scope & decomposition

Cohesive feature ("the Tools section"), but large. One design spec (this document), split into **two implementation plans**, each shipping working software:

- **Plan 1 — Foundation + compile tools:** Modal infra (Docker image, security hardening, per-IP rate limit, budget cap), `latex-to-pdf`, `latex-diff`, the `/tools/` hub, top-nav entry, per-page SEO content, and the `netlify.toml` CSP change. Delivers a live, useful two-tool section.
- **Plan 2 — Word tool:** pandoc + the generalized standard-manuscript post-processor (refactored from `format_docx.py`), plus the anonymize option.

### Explicitly out of scope (future, separate spec)
- ZIP / multi-file project upload (resolving `.bib`, `.sty`/`.cls`, figures, `\input` chapters).
- Native editable Word bibliography (depends on ZIP phase).
- LuaLaTeX support.
- Journal-specific formatting presets.
- Ads.

## Testing

- **Backend (pytest):** `.tex` fixtures — clean doc, doc with bibliography, doc that errors, plus **security fixtures** (`\write18`, `\input{/etc/passwd}`, infinite-loop bomb, oversized file) that must all be safely blocked or killed. Word: fixtures asserting output styles (font, spacing, heading numbering, captions) via `python-docx` inspection.
- **Frontend (webapp-testing / Playwright):** upload → run → download → error display against a local serve.

## Cost

Modal scale-to-zero = $0 idle. Only active compiles bill, capped by the per-IP daily limit and a hard Modal budget. Expected to stay within Modal's free credit (~$30/mo) for a long time.
