"""Modal app for the purplelink LaTeX tools backend."""
import datetime
import logging
import os

import modal

logger = logging.getLogger(__name__)

from latextools import core

app = modal.App("purplelink-latextools")

# Pinned TeX Live + toolchain image.
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
        "pandoc",
    )
    .apt_install("poppler-utils")
    .apt_install("ghostscript")
    .pip_install(
        "fastapi[standard]==0.115.2",
        "python-docx==1.1.2",
        "lxml==5.3.0",
        "bibtexparser>=1.3,<2",
        "httpx==0.27.2",
        "markitdown[pdf,docx,pptx,xlsx]==0.1.6",
    )
    # Append paranoid hardening to the texmf config via the Debian texmf.d
    # mechanism, then verify it took effect at build time (fail the build if not).
    .add_local_file("texmf.cnf", "/etc/texmf/texmf.d/99-hardening.cnf", copy=True)
    .run_commands(
        "update-texmf",
        "test \"$(kpsewhich -var-value=openin_any)\" = p",
        "test \"$(kpsewhich -var-value=shell_escape)\" = f",
    )
    .add_local_python_source("latextools")
)

# Persistent, low-volume counter store for rate limiting.
rate_dict = modal.Dict.from_name("latextools-rate", create_if_missing=True)

ALLOWED_ORIGINS = [
    "https://purplelink.llc",
    "https://www.purplelink.llc",
]
# Allow the local dev origin only when explicitly opted in, so production does
# not advertise a cross-origin surface it never needs.
if os.environ.get("ALLOW_LOCAL_CORS") == "1":
    ALLOWED_ORIGINS.append("http://localhost:4200")


@app.function(image=image, timeout=150, cpu=1.0, memory=2048, max_containers=6)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def web():
    import tempfile
    from pathlib import Path

    from fastapi import FastAPI, File, Form, Request, UploadFile
    from fastapi.concurrency import run_in_threadpool
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response

    from latextools import runner

    api = FastAPI()
    api.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["*"],
    )

    def _client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        peer = request.client.host if request.client else None
        return core.client_ip_from_forwarded(fwd, peer)

    def _enforce_rate_limit(request: Request, bucket: str) -> bool:
        day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        key = core.rate_limit_key(_client_ip(request), day, bucket=bucket)
        allowed, _ = core.check_and_increment(rate_dict, key)
        return allowed

    def _too_large(request: Request, max_bytes: int) -> bool:
        """True when the declared Content-Length already exceeds the cap.

        Rejects oversized uploads before they are read into memory. The
        per-endpoint size validators remain the authoritative check (a client
        can omit or understate Content-Length); this is an early-out only.
        """
        raw = request.headers.get("content-length")
        if not raw:
            return False
        try:
            return int(raw) > max_bytes
        except ValueError:
            return False

    async def _read_upload(upload: UploadFile) -> tuple[str | None, bytes | None]:
        """Return (tex_source, zip_bytes); exactly one is non-None."""
        data = await upload.read()
        fname = upload.filename or ""
        if fname.lower().endswith(".zip"):
            core.validate_zip_upload(fname, len(data))
            return None, data
        core.validate_upload(fname, len(data))
        return data.decode("utf-8", errors="replace"), None

    def _pdf_response(pdf: bytes, filename: str) -> Response:
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    def _result_or_error(res) -> Response:
        if res.timed_out:
            return JSONResponse({"error": "timeout"}, status_code=422)
        if not res.ok:
            return JSONResponse(
                {"error": "compile", "errors": res.errors,
                 "log": res.log[:50_000]},
                status_code=422,
            )
        return None

    @api.post("/compile")
    async def compile_endpoint(
        request: Request,
        file: UploadFile = File(...),
        engine: str = Form("pdflatex"),
    ):
        if not _enforce_rate_limit(request, "compile"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            tex, zip_bytes = await _read_upload(file)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                if zip_bytes is not None:
                    core.extract_project_zip(zip_bytes, workdir)
                    return runner.run_compile(workdir, None, engine, timeout=120)
                return runner.run_compile(workdir, tex, engine, timeout=60)

        try:
            res = await run_in_threadpool(_do)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        return _result_or_error(res) or _pdf_response(res.pdf_bytes, "compiled.pdf")

    @api.post("/diff")
    async def diff_endpoint(
        request: Request,
        old: UploadFile = File(...),
        new: UploadFile = File(...),
        engine: str = Form("pdflatex"),
        legend: str = Form("false"),
    ):
        if not _enforce_rate_limit(request, "diff"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            old_tex, old_zip = await _read_upload(old)
            new_tex, new_zip = await _read_upload(new)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)

                # Set up assets and new.tex.  If new is a project ZIP, extract
                # it so its figures/styles are available for compilation; copy
                # its main.tex to new.tex.
                if new_zip is not None:
                    core.extract_project_zip(new_zip, workdir)
                    new_main = (workdir / "main.tex").read_text(encoding="utf-8")
                    (workdir / "new.tex").write_text(new_main, encoding="utf-8")
                    effective_new = None   # already written
                else:
                    effective_new = new_tex

                # Set up old.tex.  If old is a project ZIP, extract to a
                # temporary subdir and pull out just main.tex.
                if old_zip is not None:
                    old_dir = workdir / "_old"
                    old_dir.mkdir()
                    core.extract_project_zip(old_zip, old_dir)
                    old_main = (old_dir / "main.tex").read_text(encoding="utf-8")
                    (workdir / "old.tex").write_text(old_main, encoding="utf-8")
                    effective_old = None  # already written
                else:
                    effective_old = old_tex

                return runner.run_diff(
                    workdir, effective_old, effective_new, engine, timeout=120,
                    add_legend=(legend == "true"),
                )

        try:
            res = await run_in_threadpool(_do)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        return _result_or_error(res) or _pdf_response(res.pdf_bytes, "diff.pdf")

    _DOCX_MIME = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    @api.post("/convert")
    async def convert_endpoint(
        request: Request,
        file: UploadFile = File(...),
        anonymize: str = Form("false"),
        style: str = Form("manuscript"),
    ):
        if not _enforce_rate_limit(request, "convert"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if style not in ("manuscript", "preprint"):
            style = "manuscript"
        try:
            tex, zip_bytes = await _read_upload(file)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                if zip_bytes is not None:
                    core.extract_project_zip(zip_bytes, workdir)
                    return runner.convert_to_manuscript(
                        workdir, None, anonymize=(anonymize == "true"), style=style
                    )
                return runner.convert_to_manuscript(
                    workdir, tex, anonymize=(anonymize == "true"), style=style
                )

        try:
            res = await run_in_threadpool(_do)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not res.ok:
            return JSONResponse(
                {"error": "convert", "detail": res.error}, status_code=422
            )
        filename = "preprint.docx" if style == "preprint" else "manuscript.docx"
        return Response(
            content=res.docx_bytes,
            media_type=_DOCX_MIME,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # Shared async helpers for bib fetching
    # ------------------------------------------------------------------

    async def _fetch_doi_bib(client, doi: str) -> dict:
        """Fetch BibTeX for a DOI via CrossRef content negotiation."""
        from urllib.parse import quote as _urlquote
        encoded_doi = _urlquote(doi, safe="")
        try:
            resp = await client.get(
                f"https://api.crossref.org/works/{encoded_doi}/transform/application/x-bibtex",
                headers={
                    "User-Agent": "purplelink-bib-builder/1.0 (mailto:ben@purplelink.llc)",
                    "Accept": "application/x-bibtex",
                },
            )
            if resp.status_code == 404:
                return {"id": doi, "type": "doi", "status": "not_found", "bib": None}
            if resp.status_code != 200:
                return {"id": doi, "type": "doi", "status": "error", "bib": None}
            bib = resp.text.strip()
            return {"id": doi, "type": "doi", "status": "ok", "bib": bib}
        except Exception:
            return {"id": doi, "type": "doi", "status": "error", "bib": None}

    async def _fetch_arxiv_bib(client, arxiv_id: str) -> dict:
        """Fetch metadata for an arXiv ID and format as BibTeX."""
        from latextools.bibbuilder import format_arxiv_bib
        try:
            resp = await client.get(
                "https://export.arxiv.org/api/query",
                params={"id_list": arxiv_id, "max_results": "1"},
            )
            if resp.status_code != 200:
                return {"id": arxiv_id, "type": "arxiv", "status": "error", "bib": None}
            bib = format_arxiv_bib(arxiv_id, resp.text)
            if bib is None:
                return {"id": arxiv_id, "type": "arxiv", "status": "not_found", "bib": None}
            return {"id": arxiv_id, "type": "arxiv", "status": "ok", "bib": bib}
        except Exception:
            return {"id": arxiv_id, "type": "arxiv", "status": "error", "bib": None}

    # ------------------------------------------------------------------
    # /word-to-latex — convert .docx to a LaTeX starting point
    # ------------------------------------------------------------------

    @api.post("/word-to-latex")
    async def word_to_latex_endpoint(
        request: Request,
        file: UploadFile = File(...),
    ):
        if not _enforce_rate_limit(request, "word-to-latex"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_DOCX_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 5 MB)."}, status_code=400)
        data = await file.read()
        try:
            core.validate_docx_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        import subprocess as _sp

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                docx_path = workdir / "input.docx"
                tex_path = workdir / "output.tex"
                docx_path.write_bytes(data)
                proc = _sp.run(
                    ["pandoc", str(docx_path), "-o", str(tex_path),
                     "--wrap=none", "--standalone"],
                    cwd=workdir, capture_output=True, text=True, timeout=60,
                )
                if proc.returncode != 0 or not tex_path.exists():
                    return None, proc.stderr.strip()[:500] or "pandoc failed"
                return tex_path.read_text(encoding="utf-8", errors="replace"), None

        try:
            tex_content, err = await run_in_threadpool(_do)
        except _sp.TimeoutExpired:
            return JSONResponse({"error": "convert", "detail": "Conversion timed out."}, status_code=422)
        except (OSError, RuntimeError) as e:
            return JSONResponse({"error": "convert", "detail": "Conversion failed."}, status_code=422)
        if err:
            return JSONResponse({"error": "convert", "detail": err}, status_code=422)
        return Response(
            content=tex_content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="converted.tex"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # /render-equation — compile LaTeX math to a PNG image
    # ------------------------------------------------------------------

    @api.post("/render-equation")
    async def render_equation_endpoint(
        request: Request,
        equation: str = Form(...),
        mode: str = Form("display"),
        dpi: int = Form(300),
    ):
        if not _enforce_rate_limit(request, "render-equation"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        equation = equation.strip()
        if not equation:
            return JSONResponse({"error": "invalid", "detail": "Equation is empty."}, status_code=400)
        if len(equation) > 2000:
            return JSONResponse({"error": "invalid", "detail": "Equation is too long (max 2000 chars)."}, status_code=400)
        import re as _re
        _UNSAFE_LATEX = _re.compile(
            r'\\(input|include|openin|openout|read|write|catcode|def|let|newcommand|renewcommand)\b',
            _re.IGNORECASE,
        )
        if _UNSAFE_LATEX.search(equation):
            return JSONResponse({"error": "invalid", "detail": "Equation contains disallowed LaTeX commands."}, status_code=400)
        dpi = max(72, min(dpi, 600))
        if mode not in ("display", "inline"):
            mode = "display"

        math_body = f"\\[{equation}\\]" if mode == "display" else f"${equation}$"
        tex_src = (
            "\\documentclass[border=6pt,preview]{standalone}\n"
            "\\usepackage{amsmath}\n"
            "\\usepackage{amssymb}\n"
            "\\usepackage{amsfonts}\n"
            "\\begin{document}\n"
            f"{math_body}\n"
            "\\end{document}\n"
        )

        import subprocess as _sp

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                (workdir / "eq.tex").write_text(tex_src, encoding="utf-8")
                # Compile with pdflatex
                proc = _sp.run(
                    ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                     "-no-shell-escape", "eq.tex"],
                    cwd=workdir, capture_output=True, text=True, timeout=30,
                )
                pdf_path = workdir / "eq.pdf"
                if proc.returncode != 0 or not pdf_path.exists():
                    log = (workdir / "eq.log").read_text(errors="replace") if (workdir / "eq.log").exists() else proc.stdout
                    # Extract first error line for a useful message
                    for line in log.splitlines():
                        if line.startswith("!"):
                            return None, line[1:].strip()[:200]
                    return None, "Equation could not be rendered — check your LaTeX syntax."
                # Convert PDF to PNG with pdftoppm
                png_stem = workdir / "eq"
                conv = _sp.run(
                    ["pdftoppm", "-png", "-r", str(dpi), "-singlefile",
                     str(pdf_path), str(png_stem)],
                    cwd=workdir, capture_output=True, timeout=15,
                )
                png_path = workdir / "eq.png"
                if conv.returncode != 0 or not png_path.exists():
                    stderr = conv.stderr.strip()[:200] if conv.stderr else ""
                    return None, f"Image conversion failed.{(' ' + stderr) if stderr else ''}"
                return png_path.read_bytes(), None

        try:
            png_bytes, err = await run_in_threadpool(_do)
        except _sp.TimeoutExpired:
            return JSONResponse({"error": "render", "detail": "Rendering timed out — equation may be too complex."}, status_code=422)
        except Exception as e:
            return JSONResponse({"error": "render", "detail": "An error occurred during rendering."}, status_code=422)
        if err:
            return JSONResponse({"error": "render", "detail": err}, status_code=422)
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": 'attachment; filename="equation.png"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # /bib-from-ids — build a .bib file from DOIs and arXiv IDs
    # ------------------------------------------------------------------

    @api.post("/bib-from-ids")
    async def bib_from_ids_endpoint(
        request: Request,
        ids: str = Form(...),
    ):
        import asyncio
        import httpx
        from latextools.bibbuilder import parse_ids

        if not _enforce_rate_limit(request, "bib-from-ids"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)

        parsed = parse_ids(ids)
        if not parsed:
            return JSONResponse({"error": "invalid", "detail": "No valid DOIs or arXiv IDs found."}, status_code=400)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        ) as client:
            coros = []
            for kind, clean_id in parsed:
                if kind == "doi":
                    coros.append(_fetch_doi_bib(client, clean_id))
                else:
                    coros.append(_fetch_arxiv_bib(client, clean_id))
            results = await asyncio.gather(*coros, return_exceptions=True)

        entries = []
        for (kind, clean_id), r in zip(parsed, results):
            if isinstance(r, Exception):
                entries.append({"id": clean_id, "type": kind, "status": "error", "bib": None})
            else:
                entries.append(r)

        combined = "\n\n".join(e["bib"] for e in entries if e.get("bib"))
        return JSONResponse({"entries": entries, "combined_bib": combined})

    # ------------------------------------------------------------------
    # /validate-bib — layered BibTeX validator
    # ------------------------------------------------------------------

    async def _doi_check(client, r) -> None:
        if not r.doi:
            return
        try:
            resp = await client.head(
                f"https://doi.org/{r.doi}", follow_redirects=True
            )
            r.doi_ok = resp.status_code < 400
            r.doi_status = resp.status_code
        except Exception:
            pass  # network failure → leave doi_ok as None

    async def _crossref_check(client, r) -> None:
        from latextools.bibcheck import author_similarity, title_similarity
        if not r.title:
            return
        params = {
            "query.bibliographic": r.title[:200],
            "query.author": r.author[:100] if r.author else "",
            "rows": "1",
            # Pull everything we need for both verification *and* the
            # corrected-bib output in a single round trip.
            "select": "title,DOI,author,issued,container-title,page,volume,issue,publisher",
            "mailto": "ben@purplelink.llc",
        }
        try:
            resp = await client.get(
                "https://api.crossref.org/works", params=params,
                headers={"User-Agent": "purplelink-bib-validator/1.0 (mailto:ben@purplelink.llc)"},
            )
            if resp.status_code != 200:
                return
            items = resp.json().get("message", {}).get("items", [])
            if not items:
                r.crossref_confidence = 0.0
                return
            item = items[0]
            found_title = (item.get("title") or [""])[0]
            r.crossref_confidence = title_similarity(r.title, found_title)
            r.crossref_title = found_title
            r.crossref_doi = item.get("DOI", "")

            # Authors: CrossRef returns [{given, family, ...}, ...].
            authors_raw = item.get("author") or []
            r.crossref_authors = [
                _crossref_author_string(a) for a in authors_raw if a
            ] or None

            # Year is the first element of issued.date-parts[0].
            issued = item.get("issued") or {}
            parts = (issued.get("date-parts") or [[]])[0]
            if parts and isinstance(parts[0], int):
                r.crossref_year = parts[0]

            # Container title (journal/booktitle) is a list — take the first.
            ct = item.get("container-title") or []
            if ct:
                r.crossref_journal = ct[0]
            r.crossref_volume = item.get("volume") or None
            r.crossref_issue = item.get("issue") or None
            r.crossref_pages = item.get("page") or None
            r.crossref_publisher = item.get("publisher") or None

            # Author comparison (only meaningful when title actually matched).
            if r.author and r.crossref_authors:
                score = author_similarity(r.author, r.crossref_authors)
                if r.author_match is None or score > r.author_match:
                    r.author_match = score
        except Exception:
            pass

    async def _s2_check(client, r) -> None:
        from latextools.bibcheck import author_similarity, title_similarity
        if not r.title:
            return
        params = {
            "query": r.title[:200],
            "fields": "title,authors,year,venue",
            "limit": "1",
        }
        try:
            resp = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params=params,
            )
            if resp.status_code != 200:
                return
            papers = resp.json().get("data", [])
            if not papers:
                r.s2_confidence = 0.0
                return
            found = papers[0]
            found_title = found.get("title", "")
            r.s2_confidence = title_similarity(r.title, found_title)
            r.s2_title = found_title
            r.s2_year = found.get("year")
            authors = found.get("authors") or []
            r.s2_authors = [a.get("name", "") for a in authors if a.get("name")] or None

            if r.author and r.s2_authors:
                score = author_similarity(r.author, r.s2_authors)
                # Prefer the higher of CrossRef / S2 author scores
                if r.author_match is None or score > r.author_match:
                    r.author_match = score
        except Exception:
            pass

    def _crossref_author_string(author: dict) -> str:
        """Render a CrossRef author object as "Family, Given" if possible."""
        family = (author.get("family") or "").strip()
        given = (author.get("given") or "").strip()
        name = (author.get("name") or "").strip()  # corporate / single-string author
        if family and given:
            return f"{family}, {given}"
        if family:
            return family
        return name

    @api.post("/validate-bib")
    async def validate_bib_endpoint(
        request: Request,
        file: UploadFile = File(...),
        check_doi: str = Form("false"),
        check_crossref: str = Form("false"),
        check_s2: str = Form("false"),
    ):
        import asyncio
        import httpx
        from latextools import bibcheck

        if not _enforce_rate_limit(request, "validate-bib"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_BIB_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 2 MB)."}, status_code=400)
        data = await file.read()
        try:
            core.validate_bib_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        bib_text = data.decode("utf-8", errors="replace")
        results = bibcheck.parse_bib(bib_text)

        do_doi = check_doi == "true"
        do_crossref = check_crossref == "true"
        do_s2 = check_s2 == "true"

        if do_doi or do_crossref or do_s2:
            net = results[: bibcheck.MAX_NETWORK_ENTRIES]
            async with httpx.AsyncClient(timeout=10.0) as client:
                coros = []
                for r in net:
                    if do_doi:
                        coros.append(_doi_check(client, r))
                    if do_crossref:
                        coros.append(_crossref_check(client, r))
                    if do_s2:
                        coros.append(_s2_check(client, r))
                await asyncio.gather(*coros, return_exceptions=True)

        return JSONResponse({
            "entries": [r.to_dict() for r in results],
            "summary": bibcheck.summarize(results),
            "annotated_bib": bibcheck.annotate_bib(bib_text, results),
            "corrected_bib": bibcheck.correct_bib(bib_text, results),
        })

    # ------------------------------------------------------------------
    # /markdown-convert — convert Markdown to PDF or Word via pandoc
    # ------------------------------------------------------------------

    @api.post("/markdown-convert")
    async def markdown_convert_endpoint(
        request: Request,
        text: str = Form(""),
        file: UploadFile = File(None),
        target: str = Form("pdf"),
    ):
        if not _enforce_rate_limit(request, "markdown-convert"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_MD_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "Markdown is too large (max 2 MB)."}, status_code=400)
        if target not in ("pdf", "docx"):
            target = "pdf"

        if file is not None and (file.filename or ""):
            data = await file.read()
            try:
                core.validate_md_upload(file.filename or "", len(data))
            except core.ValidationError as e:
                return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
            md_source = data.decode("utf-8", errors="replace")
        else:
            md_source = text
            if len(md_source.encode("utf-8")) > core.MAX_MD_UPLOAD_BYTES:
                return JSONResponse({"error": "invalid", "detail": "Markdown is too large (max 2 MB)."}, status_code=400)

        if not md_source.strip():
            return JSONResponse({"error": "invalid", "detail": "No Markdown content provided."}, status_code=400)

        import subprocess as _sp

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                md_path = workdir / "input.md"
                out_path = workdir / f"output.{target}"
                md_path.write_text(md_source, encoding="utf-8")
                cmd = ["pandoc", str(md_path), "-o", str(out_path),
                       "--standalone", "--wrap=none"]
                if target == "pdf":
                    # Pandoc passes raw LaTeX in the Markdown straight through to
                    # pdflatex, so this path is only as safe as the engine's
                    # confinement. Two layers enforce that: the image bakes
                    # openin_any=p / shell_escape=f into texmf.cnf (verified at
                    # build, see image .run_commands above), and we pass
                    # -no-shell-escape explicitly here so \write18 fails closed
                    # even if the global default ever regresses. Absolute/parent
                    # \input/\openin are blocked by openin_any=p.
                    cmd += ["--pdf-engine=pdflatex",
                            "--pdf-engine-opt=-no-shell-escape"]
                proc = _sp.run(
                    cmd, cwd=workdir, capture_output=True, text=True, timeout=90,
                )
                if proc.returncode != 0 or not out_path.exists():
                    return None, proc.stderr.strip()[:500] or "pandoc failed"
                return out_path.read_bytes(), None

        try:
            out_bytes, err = await run_in_threadpool(_do)
        except _sp.TimeoutExpired:
            return JSONResponse({"error": "convert", "detail": "Conversion timed out."}, status_code=422)
        except (OSError, RuntimeError):
            return JSONResponse({"error": "convert", "detail": "Conversion failed."}, status_code=422)
        if err:
            return JSONResponse({"error": "convert", "detail": err}, status_code=422)

        if target == "pdf":
            return _pdf_response(out_bytes, "converted.pdf")
        return Response(
            content=out_bytes,
            media_type=_DOCX_MIME,
            headers={
                "Content-Disposition": 'attachment; filename="converted.docx"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # /pdf-compress — shrink a PDF with Ghostscript
    # ------------------------------------------------------------------

    _GS_LEVELS = {
        "screen": "/screen",
        "ebook": "/ebook",
        "printer": "/printer",
        "prepress": "/prepress",
    }

    @api.post("/pdf-compress")
    async def pdf_compress_endpoint(
        request: Request,
        file: UploadFile = File(...),
        level: str = Form("ebook"),
    ):
        if not _enforce_rate_limit(request, "pdf-compress"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PDF_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 20 MB)."}, status_code=400)
        gs_setting = _GS_LEVELS.get(level, "/ebook")
        data = await file.read()
        try:
            core.validate_pdf_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)

        import subprocess as _sp

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                in_path = workdir / "input.pdf"
                out_path = workdir / "output.pdf"
                in_path.write_bytes(data)
                proc = _sp.run(
                    ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                     f"-dPDFSETTINGS={gs_setting}", "-dNOPAUSE", "-dQUIET",
                     "-dBATCH", "-dSAFER", f"-sOutputFile={out_path}", str(in_path)],
                    cwd=workdir, capture_output=True, text=True, timeout=90,
                )
                if proc.returncode != 0 or not out_path.exists():
                    return None, None, proc.stderr.strip()[:500] or "ghostscript failed"
                return out_path.read_bytes(), len(data), None

        try:
            out_bytes, original_size, err = await run_in_threadpool(_do)
        except _sp.TimeoutExpired:
            return JSONResponse({"error": "compress", "detail": "Compression timed out."}, status_code=422)
        except (OSError, RuntimeError):
            return JSONResponse({"error": "compress", "detail": "Compression failed."}, status_code=422)
        if err:
            return JSONResponse({"error": "compress", "detail": err}, status_code=422)

        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="compressed.pdf"',
                "X-Content-Type-Options": "nosniff",
                "X-Original-Size": str(original_size),
                "X-Compressed-Size": str(len(out_bytes)),
                "Access-Control-Expose-Headers": "X-Original-Size, X-Compressed-Size",
            },
        )

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

        from latextools import doc2md

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                suffix = Path(filename).suffix.lower()
                in_path = Path(d) / f"input{suffix}"
                in_path.write_bytes(data)
                return doc2md.convert_to_markdown(str(in_path))

        try:
            md = await run_in_threadpool(_do)
        except Exception:
            # markitdown raises a variety of parser errors; the container's
            # request timeout bounds any pathological/slow input.
            logger.exception("file-to-markdown conversion failed")
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

    return api
