# LaTeX compile app (ChatGPT app and Claude connector): prototype

One MCP server, two read-only tools, built on the compiler behind the free LaTeX to PDF tool and the explanations on the
site's `/latex-errors/` pages. **Built and tested, not deployed, not submitted.** This PR is the prototype, for review.

Why it can pass review: language models write LaTeX constantly but cannot compile it, so they hand users documents
that do not build. This app compiles the document and explains each error in plain language with the fix, so the
assistant can correct its own LaTeX before the user sees it. It is not a thin wrapper around anything the chat
clients do natively.

## Tools

| Tool | What it does |
| --- | --- |
| `compile_latex` | One complete `.tex` document (plus optional `.bib` text) is compiled with TeX Live and latexmk. Returns: a summary; a page-1 PNG; the PDF as an embedded resource (up to 4 MB); every error and warning with line, explanation, fix and a link to the guide page where one exists. Engines: pdflatex, xelatex, lualatex. Limits: 300 KB of source, 45 s. |
| `explain_latex_error` | A pasted error message or whole TeX log gets the same explanations, without compiling. |

Both are `readOnlyHint`, closed-world, no auth. Results end with a link to the free compiler
(`utm_source=latex-app`). There is no ModernTex mention: OpenAI and Anthropic both ban product promotion in tool text.

## What is where

| Piece | Path |
| --- | --- |
| Error and warning explanations (pure Python) | `backend/latextools/compile_explain.py` |
| One compile: limits, bibliography file names, latexmk, page count, preview | `backend/latextools/compile_job.py` |
| MCP surface: tools, schemas, annotations, rate-limit hook, result content | `backend/latextools/compile_server.py` |
| Modal app (slim web function plus a TeX Live compile function) | `backend/compile_mcp_app.py` |
| Run it locally on 127.0.0.1 with this Mac's TeX | `backend/scripts/compile_mcp_local.py` |
| Tests (fake backend, plus one real-TeX test that skips without latexmk) | `backend/tests/test_compile_app.py` |

## Safety

The compile hardening is the site's own:
- latexmk runs with `-no-shell-escape`, a minimal environment, and a process-group kill on timeout (`runner.py`).
- The Modal image appends `texmf.cnf`, setting `openin_any` and `openout_any` to `p`, and the build fails if that
  setting did not take.
- Only the one source file and its bibliography exist in the working folder, and the folder is deleted after the call.
- Bibliography names taken from the document are checked against `^[A-Za-z0-9_-]+$`, so `\bibliography{../x}` cannot
  write outside the folder.
- Source text is never logged, only counts.
- The rate limit is 300 calls per IP per day (bucket `mcp-compile` in the shared `latextools-rate` Dict).
- At most 3 compile containers run at once.

Local runs use this Mac's TeX without the `texmf.cnf` hardening, so only compile your own test documents there.

## Tested

- `pytest tests/test_compile_app.py`: 27 passed. The real-TeX test ran with TinyTeX.
- Full backend suite: 907 passed.
- Over real MCP HTTP against `compile_mcp_local.py`:
  - both tools are listed;
  - a document with `align` compiled to a PDF;
  - a typo'd `\begin{algin}` returned the line number, the explanation, the fix, and the guide link.
- The page-1 PNG needs poppler's `pdftoppm`, which is in the Modal image but not on this Mac, so it was not seen
  locally.

## Before it goes live (Ben)

1. Review this PR.
2. Deploy: `cd backend && python3 -m modal deploy compile_mcp_app.py`. `scripts/deploy.sh --backend` does not cover it.
   The first deploy builds the TeX image, which takes several minutes.
3. Smoke test the deployed endpoint: `/health`, one good compile, one failing compile.
   Check that the PNG preview appears.
4. Add a privacy-policy section like `#citation-app`. It should say that the LaTeX and the `.bib` text are compiled
   and deleted, and that nothing is stored or logged.
5. Listing: same steps as the citation app (docs/products/chatgpt-citation-app.md). It is worth listing both
   together under one developer profile.

## Stop rule

If the app gets fewer than 10 visits tagged `utm_source=latex-app` in the 6 weeks after listing, stop maintaining it.
Log the listing date with `log_change.py`. A paid API is only worth considering above about 100 weekly active users.
