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
        # Paper Review (paid) tool deps
        "pdfplumber>=0.11,<1",
        "pdf2image>=1.17,<2",
        "pillow>=10,<12",
        "pypdf>=4.3,<6",   # PDF annotation rendering
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

# Isolated JVM image for the free PDF-structure tool. The opendataloader-pdf
# PyPI package bundles the CLI JAR (Apache-2.0 v2.x) + LICENSE/NOTICE/
# THIRD_PARTY; we add only a JRE for it to shell out to. Kept separate from
# `image` above so the other free tools' cold starts stay unaffected. Pinned
# >= 2.0 so the core stays Apache-2.0 (pre-2.0 was MPL).
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

# Persistent, low-volume counter store for rate limiting.
rate_dict = modal.Dict.from_name("latextools-rate", create_if_missing=True)

# ---- Paid-tool persistent storage ----------------------------------------
# Single shared token store across all paid products (Paper Review, Cover
# Letter, Anonymity Check, Citation Gap, Revision, Response Review, Volume
# Packs). Each token carries its `product` field so the submit endpoint can
# dispatch correctly. Keys are session_id from Stripe.
#   paper_tokens_dict[session_id]       = { tokens: [token, ...], product, redeemed: bool, ... }
#   paper_jobs_dict[token]              = pipeline progress / result dict
paper_tokens_dict = modal.Dict.from_name("paper-review-tokens", create_if_missing=True)
paper_jobs_dict = modal.Dict.from_name("paper-review-jobs", create_if_missing=True)

# Secrets — create via:
#   modal secret create anthropic-secret      ANTHROPIC_API_KEY="sk-ant-..."
#   modal secret create paper-review-shared   BACKEND_WEBHOOK_SECRET="<random>"
#   modal secret create stripe-secret         STRIPE_SECRET_KEY="sk_live_..."
#   modal secret create resend-secret         RESEND_API_KEY="re_..."
anthropic_secret = modal.Secret.from_name("anthropic-secret")
paper_review_shared_secret = modal.Secret.from_name("paper-review-shared")
stripe_secret = modal.Secret.from_name("stripe-secret")
resend_secret = modal.Secret.from_name("resend-secret")

# Product catalog — single source of truth shared between the webhook
# (which maps Stripe price_id → product), the register-token endpoint
# (which mints the right number of tokens per pack), and the submit
# endpoints (which dispatch to the right pipeline). Each entry can be
# overridden by env vars at deploy time but the keys themselves are
# stable.
PAID_PRODUCTS: dict[str, dict] = {
    # Paper Review tiers. Community-first pricing: target ~25-67% margin
    # rather than 60-85%. Standard now BUNDLES the Anonymity Check for free,
    # consolidating what was a separate "+anonymity" tier.
    "paper-review-standard":    {"category": "paper-review", "tier": "standard", "qty": 1, "amount": 300, "bundled_anonymity": True},
    "paper-review-journal":     {"category": "paper-review", "tier": "standard", "qty": 1, "amount": 500, "bundled_anonymity": True, "bundled_journal": True},
    "paper-review-deep":        {"category": "paper-review", "tier": "deep",     "qty": 1, "amount": 800, "bundled_anonymity": True, "bundled_journal": True},
    # Volume packs (mint N tokens of standard Paper Review). Discounts vs.
    # buying à la carte at $3 each: 5-pack = 20% off, 20-pack = 33% off.
    "paper-review-pack-5":      {"category": "paper-review", "tier": "standard", "qty": 5,  "amount": 1200},
    "paper-review-pack-20":     {"category": "paper-review", "tier": "standard", "qty": 20, "amount": 4000},
    # Auxiliary paid tools — minimum-price ($1) for the small ones, fair-
    # value for the longer pipelines.
    "cover-letter":             {"category": "cover-letter", "qty": 1, "amount": 100},
    "anonymity-check":          {"category": "anonymity-check", "qty": 1, "amount": 100},
    "citation-gap":             {"category": "citation-gap", "qty": 1, "amount": 200},
    "revision-review":          {"category": "revision-review", "qty": 1, "amount": 100},
    "response-review":          {"category": "response-review", "qty": 1, "amount": 400},
}

ALLOWED_ORIGINS = [
    "https://purplelink.llc",
    "https://www.purplelink.llc",
]
# Allow the local dev origin only when explicitly opted in, so production does
# not advertise a cross-origin surface it never needs.
if os.environ.get("ALLOW_LOCAL_CORS") == "1":
    ALLOWED_ORIGINS.append("http://localhost:4200")


# ---------------------------------------------------------------------------
# Paper Review pipeline (paid tool) — heavy multi-Sonnet orchestration.
#
# Lives in its own Modal function so it gets a fatter resource envelope
# (longer timeout, more memory) than the free-tool ASGI app needs. The web()
# function uses .spawn() to fire-and-forget this function; the pipeline
# itself writes progress + final result into paper_jobs_dict, and the
# polling endpoint just reads from that dict.
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    timeout=900,         # 15 min cap — deep tier can take 10+ min
    cpu=2.0,
    memory=4096,
    max_containers=4,
    secrets=[anthropic_secret, resend_secret],
)
def paper_review_pipeline(
    token: str,
    pdf_bytes: bytes,
    domain: str,
    *,
    tier: str = "standard",
    journal_key: str = "",
    anonymity_check: bool = False,
    deliver_email: str = "",
) -> None:
    """Run the full Paper Review pipeline (any tier) and persist to dict."""
    import asyncio as _asyncio
    import time as _time
    import httpx

    from latextools import papercheck, journals, delivery

    journal_pack = journals.JOURNAL_SPECS.get(journal_key) if journal_key else None

    def _persist(progress) -> None:
        d = progress.to_dict()
        if progress.status != "done":
            d["result_md"] = None
            d["result_pdf_b64"] = None
            d["annotated_pdf_b64"] = None
        paper_jobs_dict[token] = d

    async def _run():
        try:
            final = await papercheck.run_review_pipeline(
                pdf_bytes, domain=domain, on_progress=_persist,
                tier=tier,
                journal_pack=journal_pack,
                anonymity_check=anonymity_check,
            )
            paper_jobs_dict[token] = {
                **final,
                "product": "paper-review",
                "status": "done" if final.get("result_md") else "error",
            }
            if deliver_email and final.get("result_md"):
                async with httpx.AsyncClient(timeout=10.0) as ec:
                    await delivery.send_email(
                        ec,
                        to=deliver_email,
                        subject="Your Paper Review is ready",
                        html=delivery.html_review_ready(
                            status_url=f"https://purplelink.llc/tools/paper-review/status/?token={token}",
                            manuscript_title=(final.get("structure_summary") or {}).get("title", ""),
                        ),
                        tags=[{"name": "product", "value": "paper-review"}],
                    )
        except Exception as e:
            logger.exception("paper_review_pipeline failed for token=%s", token[:12])
            paper_jobs_dict[token] = {
                "status": "error",
                "error": f"{type(e).__name__}: {str(e)[:200]}",
                "finished_at": _time.time(),
            }

    _asyncio.run(_run())


@app.function(
    image=image,
    timeout=600,
    cpu=1.0,
    memory=3072,
    max_containers=4,
    secrets=[anthropic_secret, resend_secret],
)
def adjacent_tool_pipeline(
    token: str,
    product: str,
    pdf_bytes: bytes = b"",
    *,
    journal_name: str = "",
    custom_note: str = "",
    original_review_md: str = "",
    reviewer_comments: str = "",
    author_response: str = "",
    abstract_only: str = "",
    title_only: str = "",
    deliver_email: str = "",
) -> None:
    """Single dispatcher for cover-letter, anonymity-check, citation-gap,
    revision-review, response-review jobs. The product field decides which
    pipeline runs; all of them write progress + result into paper_jobs_dict
    keyed by token."""
    import asyncio as _asyncio
    import base64 as _base64
    import time as _time
    import httpx

    from latextools import papercheck, paperreview_extras, response_review, delivery

    def _persist(progress_dict: dict) -> None:
        paper_jobs_dict[token] = progress_dict

    async def _run():
        try:
            if product == "cover-letter":
                # Cover letter uses pasted abstract + journal only — privacy-
                # preserving design (no full PDF retained).
                struct = papercheck.PaperStructure(
                    title=title_only or "",
                    abstract=abstract_only or "",
                )
                paper_jobs_dict[token] = {
                    "status": "running", "progress_pct": 30,
                    "stage": "drafting", "product": product,
                    "started_at": _time.time(),
                }
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
                ) as client:
                    res = await paperreview_extras.run_cover_letter(
                        client, struct, journal_name or "the target journal",
                        custom_note=custom_note,
                    )
                paper_jobs_dict[token] = {
                    "status": "done" if res.get("status") == "ok" else "error",
                    "progress_pct": 100,
                    "stage": "done",
                    "product": product,
                    "result_md": res.get("text", ""),
                    "finished_at": _time.time(),
                }

            elif product in ("anonymity-check", "citation-gap"):
                paper_jobs_dict[token] = {
                    "status": "running", "progress_pct": 15,
                    "stage": "extracting", "product": product,
                    "started_at": _time.time(),
                }
                struct = papercheck.extract_paper(pdf_bytes)
                paper_jobs_dict[token] = {
                    **paper_jobs_dict[token],
                    "progress_pct": 50, "stage": "analysing",
                }
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
                ) as client:
                    if product == "anonymity-check":
                        res = await paperreview_extras.run_anonymity_check(
                            client, struct,
                        )
                        md = _format_anonymity_md(res)
                    else:
                        res = await paperreview_extras.run_citation_gap(client, struct)
                        md = _format_citation_gap_md(res)
                paper_jobs_dict[token] = {
                    "status": "done",
                    "progress_pct": 100,
                    "stage": "done",
                    "product": product,
                    "result_md": md,
                    "raw": res,
                    "finished_at": _time.time(),
                }

            elif product == "revision-review":
                paper_jobs_dict[token] = {
                    "status": "running", "progress_pct": 15,
                    "stage": "extracting", "product": product,
                    "started_at": _time.time(),
                }
                struct = papercheck.extract_paper(pdf_bytes)
                paper_jobs_dict[token] = {
                    **paper_jobs_dict[token],
                    "progress_pct": 50, "stage": "comparing",
                }
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
                ) as client:
                    res = await paperreview_extras.run_revision_review(
                        client, struct, original_review_md or "",
                    )
                paper_jobs_dict[token] = {
                    "status": "done" if res.get("status") == "ok" else "error",
                    "progress_pct": 100,
                    "stage": "done",
                    "product": product,
                    "result_md": res.get("markdown", ""),
                    "finished_at": _time.time(),
                }

            elif product == "response-review":
                def _emit(progress) -> None:
                    paper_jobs_dict[token] = {
                        "status": progress.status,
                        "progress_pct": progress.progress_pct,
                        "stage": progress.stage,
                        "product": product,
                        "started_at": progress.started_at,
                        "result_md": progress.result_md if progress.status == "done" else None,
                    }
                final = await response_review.run_response_review(
                    pdf_bytes, reviewer_comments or "", author_response or "",
                    on_progress=_emit,
                )
                paper_jobs_dict[token] = {
                    **final, "product": product,
                }
            else:
                paper_jobs_dict[token] = {
                    "status": "error",
                    "error": f"unknown_product:{product}",
                    "finished_at": _time.time(),
                }
                return

            if deliver_email:
                async with httpx.AsyncClient(timeout=10.0) as ec:
                    await delivery.send_email(
                        ec, to=deliver_email,
                        subject=f"Your {product.replace('-', ' ').title()} is ready",
                        html=delivery.html_review_ready(
                            status_url=f"https://purplelink.llc/tools/paper-review/status/?token={token}&product={product}",
                        ),
                        tags=[{"name": "product", "value": product}],
                    )
        except Exception as e:
            logger.exception("adjacent_tool_pipeline failed for token=%s product=%s", token[:12], product)
            paper_jobs_dict[token] = {
                "status": "error",
                "error": f"{type(e).__name__}: {str(e)[:200]}",
                "finished_at": _time.time(),
                "product": product,
            }

    _asyncio.run(_run())


def _format_anonymity_md(res: dict) -> str:
    """Render the anonymity-check JSON result as a user-facing Markdown
    report. Lives here rather than in paperreview_extras so the module
    stays a pure async helper."""
    leaks = res.get("leaks", []) or []
    if not leaks:
        return (
            "# Anonymity Check\n\n"
            "**Result: no concrete leaks detected.**\n\n"
            "We scanned the manuscript body and abstract for author "
            "names, institution names, funding/grant numbers, IRB or "
            "ethics-board protocol numbers, named software or datasets, "
            "and author-owned URLs. No identifying information was "
            "flagged.\n\n"
            "This does not guarantee a fully blinded submission — please "
            "still review your acknowledgements, figures, and supplementary "
            "materials manually.\n"
        )
    parts = [
        "# Anonymity Check\n",
        f"**Result: {len(leaks)} potential leak"
        f"{'s' if len(leaks) != 1 else ''} detected.**\n",
        "Each item below should be removed or generalised before "
        "double-blind submission.\n",
    ]
    by_cat: dict[str, list] = {}
    for l in leaks:
        cat = l.get("category", "other")
        by_cat.setdefault(cat, []).append(l)
    for cat, items in by_cat.items():
        parts.append(f"\n## {cat.replace('_', ' ').title()}\n")
        for l in items:
            severity = (l.get("severity") or "minor").upper()
            quote = (l.get("quote") or "").replace("\n", " ").strip()[:300]
            where = l.get("where", "")
            fix = l.get("fix", "")
            parts.append(
                f"- **[{severity}]** {where}: \"{quote}\"\n"
                f"  - Fix: {fix}\n"
            )
    return "".join(parts)


def _format_citation_gap_md(res: dict) -> str:
    """Render the citation-gap JSON as user-facing Markdown."""
    gaps = res.get("gaps", []) or []
    if not gaps:
        return (
            "# Citation Gap Analysis\n\n"
            "**Result: no obvious citation gaps detected.**\n\n"
            "The manuscript's reference list appears to cover the canonical "
            "prior work for its scope. Verify against your own field "
            "knowledge before submission — this check is a sanity net, "
            "not an exhaustive literature search.\n"
        )
    parts = [
        "# Citation Gap Analysis\n",
        f"**Result: {len(gaps)} potential gap"
        f"{'s' if len(gaps) != 1 else ''} flagged.**\n",
        "Each entry below is a citation a domain reviewer might expect to "
        "see. Verify each suggestion against your own knowledge before "
        "adding — AI recall can be wrong.\n",
    ]
    for g in gaps:
        gap_type = g.get("gap_type", "qualitative_gap").replace("_", " ").title()
        topic = g.get("topic", "(no topic)")
        desc = g.get("expected_work_description", "")
        authors = g.get("candidate_authors") or []
        title_hint = g.get("candidate_title_hint", "")
        why = g.get("why_it_matters", "")
        where = g.get("where_in_paper", "")
        author_line = ", ".join(authors) if authors else "(unknown)"
        parts.append(
            f"\n### {topic}\n"
            f"- **Type:** {gap_type}\n"
            f"- **Suggested authors:** {author_line}\n"
            f"- **Title hint:** {title_hint or '(unknown)'}\n"
            f"- **What should be cited:** {desc}\n"
            f"- **Why a reviewer would notice:** {why}\n"
            f"- **Section to add it:** {where}\n"
        )
    return "".join(parts)


@app.function(
    image=opendataloader_image,
    timeout=120,
    cpu=2.0,
    memory=3072,
    max_containers=4,
)
def pdf_structure_run(pdf_bytes: bytes) -> dict:
    """Run OpenDataLoader (default local mode) on a PDF and return
    {markdown, json, summary}. Ephemeral: writes into a temp dir deleted on
    return. No OCR / hybrid / model. Nothing is retained."""
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

        def _list(_):
            return [str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file()]

        def _read_rel(rel):
            return (out_dir / rel).read_text(encoding="utf-8", errors="replace")

        result = pdf_structure.parse_output_dir(out_dir, _read_rel, _list)
        if not result["markdown"] and not result["json"]:
            return {"error": "empty"}
        return result


@app.function(
    image=image,
    timeout=150,
    cpu=1.0,
    memory=2048,
    max_containers=6,
    # Web function needs: shared webhook secret (verify webhook calls),
    # Stripe key (invoice generation endpoint), Resend key (volume-pack
    # token email + invoice email). Anthropic key is NOT mounted here;
    # only the heavy pipelines need it.
    secrets=[paper_review_shared_secret, stripe_secret, resend_secret],
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def web():
    import io
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

    # ------------------------------------------------------------------
    # /pdf-structure — free PDF-to-Structured-Data tool. Runs OpenDataLoader
    # (Apache-2.0, local mode) in an isolated JVM function and returns
    # reading-order Markdown + RAG-ready JSON. Nothing is retained.
    # ------------------------------------------------------------------
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
            return JSONResponse(
                {"error": "convert", "detail": "This PDF took too long to process. Try a smaller or simpler file."},
                status_code=422,
            )
        if err in ("parse", "empty"):
            return JSONResponse(
                {"error": "convert", "detail": "No structured content could be extracted from this PDF."},
                status_code=422,
            )
        if err:
            return JSONResponse(
                {"error": "convert", "detail": "Couldn't process this PDF."},
                status_code=422,
            )

        return JSONResponse(
            {
                "markdown": result.get("markdown", ""),
                "structured": result.get("json", {}),
                "summary": result.get("summary", {}),
            },
            headers={"X-Content-Type-Options": "nosniff"},
        )

    # ------------------------------------------------------------------
    # /word-stats — free Document Insights tool. Extracts plain text from
    # an uploaded document and (for academic papers) splices it into named
    # sections. ALL statistics are computed client-side; this endpoint only
    # does the format-to-text conversion the browser can't. Retains nothing.
    # ------------------------------------------------------------------
    @api.post("/word-stats")
    async def word_stats_endpoint(
        request: Request,
        file: UploadFile = File(...),
    ):
        if not _enforce_rate_limit(request, "word-stats"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_DOC2MD_UPLOAD_BYTES):
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        filename = file.filename or ""
        data = await file.read()
        try:
            core.validate_wordstats_upload(filename, len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        name_lc = filename.lower()
        is_pdf = name_lc.endswith(".pdf")
        is_plaintext = name_lc.endswith(core.WORDSTATS_PLAINTEXT_EXTENSIONS)

        # Magic-byte check for binary formats (plain-text formats skip it).
        if not is_plaintext and not core.doc2md_signature_ok(filename, data):
            # doc2md_signature_ok only knows the doc2md set; for .rtf/.odt we
            # do a lighter check (.odt is a zip; .rtf starts with "{\rtf").
            ok = True
            if name_lc.endswith(".odt"):
                ok = data[:4] == b"PK\x03\x04"
            elif name_lc.endswith(".rtf"):
                ok = data[:5] == b"{\\rtf"
            elif name_lc.endswith(core.DOC2MD_ALLOWED_EXTENSIONS):
                ok = False  # doc2md_signature_ok already said no
            if not ok:
                return JSONResponse(
                    {"error": "invalid", "detail": "File contents do not match its type."},
                    status_code=400,
                )

        from latextools import doc2md, papercheck

        def _extract():
            # Plain-text formats: decode directly (fast, no conversion).
            if is_plaintext:
                return data.decode("utf-8", errors="replace")
            # Everything else → markitdown / pdfplumber via doc2md.
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                suffix = Path(filename).suffix.lower()
                in_path = Path(d) / f"input{suffix}"
                in_path.write_bytes(data)
                return doc2md.convert_to_markdown(str(in_path))

        try:
            text = await run_in_threadpool(_extract)
        except Exception:
            logger.exception("word-stats extraction failed")
            return JSONResponse(
                {"error": "convert", "detail": "Couldn't read this file."},
                status_code=422,
            )
        if not text or not text.strip():
            return JSONResponse(
                {"error": "convert", "detail": "No text could be extracted from this file."},
                status_code=422,
            )

        # Academic section splice (best-effort). For PDFs we can also count
        # pages; for everything else page_count is null.
        sections = papercheck.splice_text_sections(text)
        # "academic" if we found at least two distinct narrative/structural
        # sections beyond the catch-all body.
        structural = [k for k in sections if k not in ("body", "figure_captions")]
        kind = "academic" if len(structural) >= 2 else "plain"

        page_count = None
        if is_pdf:
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    page_count = len(pdf.pages)
            except Exception:
                page_count = None

        return JSONResponse(
            {
                "text": text,
                "kind": kind,
                "page_count": page_count,
                "sections": sections if kind == "academic" else None,
                "filename": filename,
            },
            headers={"X-Content-Type-Options": "nosniff"},
        )

    # ------------------------------------------------------------------
    # /paper-review/* — paid AI red-team manuscript review
    #
    # Flow:
    #   1. User pays via Stripe Checkout (Netlify Function).
    #   2. Stripe webhook (Netlify Function) calls /register-token here
    #      with the session_id and the freshly-minted job token.
    #   3. User is redirected to /tools/paper-review/upload/?session_id=…,
    #      which calls /redeem-session to get the job token.
    #   4. UI POSTs PDF + domain to /submit with the token. We .spawn() the
    #      heavy pipeline and immediately return.
    #   5. UI polls /status?token=… until status == "done".
    #   6. On first successful retrieval of result_md, the entry is deleted
    #      so we hold zero copies of the review on our infrastructure.
    # ------------------------------------------------------------------

    import secrets as _secrets_module
    import time as _time_module

    PAPER_TOKEN_TTL_SECONDS = 7 * 24 * 3600   # 7 days to redeem after pay
    PAPER_JOB_TTL_SECONDS = 24 * 3600          # 24h before stale jobs expire

    def _gen_token() -> str:
        return _secrets_module.token_urlsafe(32)

    @api.post("/paper-review/register-token")
    async def paper_review_register_token(request: Request):
        """Internal webhook target — called by the Netlify Stripe webhook
        after a successful Checkout payment. Header-authenticated only.

        Payload:
          { session_id, email, amount_paid, product, extras: {...} }

        Volume packs mint multiple tokens; everything else mints one. All
        tokens for a session are stored under the same session_id key so
        the buyer can retrieve them all if needed.
        """
        provided = request.headers.get("x-webhook-secret", "")
        expected = os.environ.get("BACKEND_WEBHOOK_SECRET", "")
        if not expected:
            return JSONResponse(
                {"error": "misconfigured", "detail": "backend secret not set"},
                status_code=500,
            )
        import hmac as _hmac
        if not _hmac.compare_digest(provided, expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_json"}, status_code=400)

        session_id = (payload or {}).get("session_id", "")
        email = (payload or {}).get("email", "")
        amount_paid = (payload or {}).get("amount_paid", 0)
        product_key = (payload or {}).get("product", "paper-review-standard")
        if not session_id or not isinstance(session_id, str) or len(session_id) > 200:
            return JSONResponse({"error": "missing_session_id"}, status_code=400)

        product_cfg = PAID_PRODUCTS.get(product_key)
        if not product_cfg:
            return JSONResponse(
                {"error": "unknown_product", "detail": product_key},
                status_code=400,
            )

        # Idempotent: re-registering the same session_id returns the same tokens.
        existing = paper_tokens_dict.get(session_id)
        if existing and isinstance(existing, dict):
            return JSONResponse({
                "tokens": existing.get("tokens", []),
                "product": existing.get("product_key"),
                "status": "exists",
            })

        qty = int(product_cfg.get("qty", 1))
        tokens = [_gen_token() for _ in range(qty)]
        entry = {
            "tokens": tokens,
            "product_key": product_key,
            "product_cfg": product_cfg,
            "email": email[:200] if isinstance(email, str) else "",
            "amount_paid": int(amount_paid) if isinstance(amount_paid, int) else 0,
            "redeemed": False,
            "consumed_tokens": [],   # tokens that have been used
            "created_at": _time_module.time(),
            "expires_at": _time_module.time() + PAPER_TOKEN_TTL_SECONDS,
        }
        paper_tokens_dict[session_id] = entry

        # Volume-pack tokens: email them all immediately
        if qty > 1 and entry["email"]:
            try:
                from latextools import delivery as _delivery
                import httpx as _httpx
                async with _httpx.AsyncClient(timeout=10.0) as _ec:
                    await _delivery.send_email(
                        _ec,
                        to=entry["email"],
                        subject=f"Your {qty}-pack of Paper Reviews",
                        html=_delivery.html_volume_pack_tokens(tokens=tokens, pack_size=qty),
                        tags=[{"name": "product", "value": product_key}],
                    )
            except Exception:
                logger.exception("volume pack email send failed")

        return JSONResponse({
            "tokens": tokens,
            "product": product_key,
            "qty": qty,
            "status": "registered",
        })

    @api.post("/paper-review/redeem-session")
    async def paper_review_redeem_session(request: Request):
        """Exchange a Stripe session_id for the job token(s).

        Returns the first unconsumed token for single-purchase products,
        or the full list for volume packs. Marks the session as redeemed.
        """
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_json"}, status_code=400)
        session_id = (payload or {}).get("session_id", "")
        if not session_id or not isinstance(session_id, str) or len(session_id) > 200:
            return JSONResponse({"error": "missing_session_id"}, status_code=400)

        entry = paper_tokens_dict.get(session_id)
        if not entry or not isinstance(entry, dict):
            return JSONResponse({"error": "pending"}, status_code=404)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            return JSONResponse({"error": "expired"}, status_code=410)

        tokens: list[str] = entry.get("tokens") or []
        consumed = set(entry.get("consumed_tokens") or [])
        unused = [t for t in tokens if t not in consumed]
        if not unused:
            return JSONResponse({"error": "all_used"}, status_code=409)

        if not entry.get("redeemed"):
            entry["redeemed"] = True
            paper_tokens_dict[session_id] = entry

        product_key = entry.get("product_key", "paper-review-standard")
        product_cfg = entry.get("product_cfg") or PAID_PRODUCTS.get(product_key, {})

        return JSONResponse({
            "token": unused[0],
            "tokens": tokens,           # full list (for volume packs)
            "unused_tokens": unused,
            "product": product_key,
            "category": product_cfg.get("category", "paper-review"),
            "tier": product_cfg.get("tier", "standard"),
            "bundled_anonymity": product_cfg.get("bundled_anonymity", False),
            "bundled_journal": product_cfg.get("bundled_journal", False),
            "qty": product_cfg.get("qty", 1),
            "status": "ok",
        })

    def _lookup_token(token: str):
        """Find the tokens entry containing this token. Returns
        (session_id, entry) or (None, None). For volume packs the entry
        contains many tokens — we still return the same entry."""
        if not token or not isinstance(token, str) or len(token) > 200:
            return None, None
        for session_id, entry in list(paper_tokens_dict.items()):
            if not isinstance(entry, dict):
                continue
            if token in (entry.get("tokens") or []):
                return session_id, entry
        return None, None

    def _consume_token(token: str, session_id: str, entry: dict) -> None:
        """Mark a single token within a session entry as consumed."""
        consumed = list(entry.get("consumed_tokens") or [])
        if token not in consumed:
            consumed.append(token)
        entry["consumed_tokens"] = consumed
        entry["last_consumed_at"] = _time_module.time()
        paper_tokens_dict[session_id] = entry

    @api.post("/paper-review/submit")
    async def paper_review_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        domain: str = Form("general"),
        journal_key: str = Form(""),
        anonymity_check: str = Form("false"),
        email: str = Form(""),
    ):
        """Validate the token + PDF and spawn the Paper Review pipeline.

        The tier / bundled options are inferred from the token's product
        config (set at register-token time based on which Stripe price the
        customer paid). The submit form can additionally request an
        anonymity scan on its own, supply a journal_key for compliance, or
        provide an email for completion notification.
        """
        if not _enforce_rate_limit(request, "paper-review"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )

        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            return JSONResponse({"error": "expired"}, status_code=410)

        product_cfg = entry.get("product_cfg") or {}
        if product_cfg.get("category", "paper-review") != "paper-review":
            return JSONResponse(
                {"error": "wrong_product",
                 "detail": "This token is for a different product."},
                status_code=400,
            )

        data = await file.read()
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse(
                {"error": "invalid", "detail": "File is not a valid PDF."},
                status_code=400,
            )

        if domain not in (
            "general", "machine_learning", "biomedicine",
            "psychology_social", "chemistry_materials",
            "nca",  # AI-SCoRe: SCoRe checklist evaluation for NCA studies
        ):
            domain = "general"

        # Tier comes from the product config (set at purchase time).
        tier = product_cfg.get("tier", "standard")
        do_anonymity = (
            anonymity_check == "true" or bool(product_cfg.get("bundled_anonymity"))
        )
        chosen_journal = ""
        if product_cfg.get("bundled_journal"):
            from latextools import journals as _jnl
            if journal_key and journal_key in _jnl.JOURNAL_SPECS:
                chosen_journal = journal_key

        # Initialise the jobs_dict entry so the UI can poll immediately.
        paper_jobs_dict[token] = {
            "status": "queued",
            "stage": "queued",
            "progress_pct": 0,
            "started_at": _time_module.time(),
            "finished_at": None,
            "error": None,
            "result_md": None,
            "result_pdf_b64": None,
            "annotated_pdf_b64": None,
            "layer_status": {},
            "tier": tier,
            "product": "paper-review",
        }

        _consume_token(token, session_id, entry)

        paper_review_pipeline.spawn(
            token, data, domain,
            tier=tier,
            journal_key=chosen_journal,
            anonymity_check=do_anonymity,
            deliver_email=email if email and "@" in email and len(email) <= 254 else "",
        )

        return JSONResponse({
            "token": token,
            "tier": tier,
            "anonymity_check": do_anonymity,
            "journal_key": chosen_journal,
            "status_url": f"/paper-review/status?token={token}",
        })

    # --- AI-SCoRe (NCA) dedicated endpoint -------------------------------------
    # Thin alias over the review pipeline's `nca` domain. Reuses all token / billing /
    # job-status plumbing; the only difference is the domain is fixed to AI-SCoRe.
    @api.post("/score/submit")
    async def aiscore_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        email: str = Form(""),
    ):
        return await paper_review_submit(
            request, token=token, file=file, domain="nca", email=email,
        )

    @api.get("/score/status")
    async def aiscore_status(request: Request, token: str):
        return await paper_review_status(request, token=token)

    @api.get("/paper-review/status")
    async def paper_review_status(request: Request, token: str):
        if not token or not isinstance(token, str) or len(token) > 200:
            return JSONResponse({"error": "invalid_token"}, status_code=400)
        entry = paper_jobs_dict.get(token)
        if not entry or not isinstance(entry, dict):
            return JSONResponse({"error": "unknown_token"}, status_code=404)

        status = entry.get("status", "running")
        if status == "done" and entry.get("result_md"):
            # First successful retrieval of a completed review — delete
            # the record so we don't retain the review text on our infra.
            payload = {
                "status": "done",
                "progress_pct": 100,
                "stage": "done",
                "product": entry.get("product", "paper-review"),
                "tier": entry.get("tier", "standard"),
                "result_md": entry.get("result_md", ""),
                "annotated_pdf_b64": entry.get("annotated_pdf_b64"),
                "structure_summary": entry.get("structure_summary", {}),
                "l1_summary": entry.get("l1_summary"),
                "l2_summary": entry.get("l2_summary"),
                "l3_summary": entry.get("l3_summary"),
                "compliance_result": entry.get("compliance_result"),
                "anonymity_result": entry.get("anonymity_result"),
                "deterministic_findings": entry.get("deterministic_findings"),
                "_note": "This result has been deleted from server storage. Save it now.",
            }
            try:
                del paper_jobs_dict[token]
            except KeyError:
                pass
            return JSONResponse({k: v for k, v in payload.items() if v is not None or k in ("annotated_pdf_b64",)})

        return JSONResponse({
            "status": status,
            "progress_pct": entry.get("progress_pct", 0),
            "stage": entry.get("stage", "running"),
            "product": entry.get("product", "paper-review"),
            "tier": entry.get("tier", "standard"),
            "error": entry.get("error"),
            "layer_status": entry.get("layer_status", {}),
        })

    # ------------------------------------------------------------------
    # /paper-review/journals — list journal compliance specs for a domain
    # ------------------------------------------------------------------
    @api.get("/paper-review/journals")
    async def paper_review_journals(request: Request, domain: str = "general"):
        from latextools import journals as _jnl
        return JSONResponse({
            "journals": _jnl.list_journals_for_domain(domain),
        })

    # ------------------------------------------------------------------
    # Adjacent paid-tool submit endpoints. Each validates the token,
    # confirms the product matches, and spawns the dispatcher.
    # ------------------------------------------------------------------
    def _start_adjacent(token: str, session_id: str, entry: dict, *,
                        product: str, spawn_kwargs: dict) -> None:
        paper_jobs_dict[token] = {
            "status": "queued", "stage": "queued",
            "progress_pct": 0, "started_at": _time_module.time(),
            "product": product, "result_md": None,
        }
        _consume_token(token, session_id, entry)
        adjacent_tool_pipeline.spawn(token, product, **spawn_kwargs)

    @api.post("/cover-letter/submit")
    async def cover_letter_submit(
        request: Request,
        token: str = Form(...),
        title: str = Form(""),
        abstract: str = Form(...),
        journal_name: str = Form(...),
        custom_note: str = Form(""),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "cover-letter"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if (entry.get("product_cfg") or {}).get("category") != "cover-letter":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        abstract = (abstract or "").strip()
        if not abstract or len(abstract) > 5000:
            return JSONResponse(
                {"error": "invalid", "detail": "Abstract is required and must be ≤ 5000 chars."},
                status_code=400,
            )
        if not journal_name or len(journal_name) > 300:
            return JSONResponse({"error": "invalid", "detail": "Journal name required."}, status_code=400)
        _start_adjacent(token, session_id, entry, product="cover-letter", spawn_kwargs={
            "title_only": (title or "")[:300],
            "abstract_only": abstract,
            "journal_name": journal_name,
            "custom_note": (custom_note or "")[:1000],
            "deliver_email": email if email and "@" in email else "",
        })
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    @api.post("/anonymity-check/submit")
    async def anonymity_check_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "anonymity-check"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if (entry.get("product_cfg") or {}).get("category") != "anonymity-check":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        data = await file.read()
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)
        _start_adjacent(token, session_id, entry, product="anonymity-check", spawn_kwargs={
            "pdf_bytes": data,
            "deliver_email": email if email and "@" in email else "",
        })
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    @api.post("/citation-gap/submit")
    async def citation_gap_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "citation-gap"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if (entry.get("product_cfg") or {}).get("category") != "citation-gap":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        data = await file.read()
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)
        _start_adjacent(token, session_id, entry, product="citation-gap", spawn_kwargs={
            "pdf_bytes": data,
            "deliver_email": email if email and "@" in email else "",
        })
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    @api.post("/revision-review/submit")
    async def revision_review_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        original_review_md: str = Form(...),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "revision-review"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if (entry.get("product_cfg") or {}).get("category") != "revision-review":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        if not original_review_md or len(original_review_md) > 120_000:
            return JSONResponse({"error": "invalid", "detail": "Original review required (≤ 120k chars)."}, status_code=400)
        data = await file.read()
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)
        _start_adjacent(token, session_id, entry, product="revision-review", spawn_kwargs={
            "pdf_bytes": data,
            "original_review_md": original_review_md,
            "deliver_email": email if email and "@" in email else "",
        })
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    @api.post("/response-review/submit")
    async def response_review_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        reviewer_comments: str = Form(...),
        author_response: str = Form(...),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "response-review"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if (entry.get("product_cfg") or {}).get("category") != "response-review":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        if not reviewer_comments or len(reviewer_comments) > 60_000:
            return JSONResponse({"error": "invalid", "detail": "Reviewer comments required (≤ 60k)."}, status_code=400)
        if not author_response or len(author_response) > 60_000:
            return JSONResponse({"error": "invalid", "detail": "Author response required (≤ 60k)."}, status_code=400)
        data = await file.read()
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)
        _start_adjacent(token, session_id, entry, product="response-review", spawn_kwargs={
            "pdf_bytes": data,
            "reviewer_comments": reviewer_comments,
            "author_response": author_response,
            "deliver_email": email if email and "@" in email else "",
        })
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    # ------------------------------------------------------------------
    # /paper-review/invoice — generate Stripe invoice for a session
    # ------------------------------------------------------------------
    @api.post("/paper-review/invoice")
    async def paper_review_invoice(request: Request):
        """Use the Stripe Invoices API to create + finalise a PDF invoice
        for a past Checkout session, then email the hosted-invoice URL via
        Resend. The caller provides the Stripe session_id and (optionally)
        an institutional tax-ID line to append."""
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_json"}, status_code=400)
        session_id = (payload or {}).get("session_id", "")
        tax_id_line = (payload or {}).get("tax_id_line", "")[:200]
        if not session_id or not isinstance(session_id, str):
            return JSONResponse({"error": "missing_session_id"}, status_code=400)

        # We require the session_id be one we have on record
        token_entry = paper_tokens_dict.get(session_id)
        if not token_entry:
            return JSONResponse({"error": "unknown_session"}, status_code=404)

        stripe_key = os.environ.get("STRIPE_SECRET_KEY")
        if not stripe_key:
            return JSONResponse(
                {"error": "misconfigured", "detail": "STRIPE_SECRET_KEY not set on web function."},
                status_code=500,
            )

        import httpx as _httpx
        import urllib.parse as _ulp

        # Look up the Checkout Session to find customer + amount
        async with _httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    f"https://api.stripe.com/v1/checkout/sessions/{_ulp.quote(session_id, safe='')}",
                    headers={"Authorization": f"Bearer {stripe_key}"},
                )
                if resp.status_code != 200:
                    return JSONResponse(
                        {"error": "stripe_lookup_failed", "detail": resp.text[:300]},
                        status_code=502,
                    )
                session = resp.json()
            except Exception as e:
                return JSONResponse({"error": "stripe_unreachable", "detail": str(e)[:200]}, status_code=502)

            customer = session.get("customer")
            customer_email = (
                (session.get("customer_details") or {}).get("email")
                or session.get("customer_email")
                or token_entry.get("email", "")
            )
            amount_total = session.get("amount_total", 0)
            currency = session.get("currency", "usd")

            # If there's no customer object on the session, create one
            if not customer:
                cust_resp = await client.post(
                    "https://api.stripe.com/v1/customers",
                    headers={"Authorization": f"Bearer {stripe_key}"},
                    data={"email": customer_email or "ben@purplelink.llc"},
                )
                if cust_resp.status_code >= 300:
                    return JSONResponse(
                        {"error": "stripe_customer_failed", "detail": cust_resp.text[:300]},
                        status_code=502,
                    )
                customer = cust_resp.json().get("id")

            # Create a draft invoice tied to the customer
            inv_resp = await client.post(
                "https://api.stripe.com/v1/invoices",
                headers={"Authorization": f"Bearer {stripe_key}"},
                data={
                    "customer": customer,
                    "collection_method": "send_invoice",
                    "days_until_due": "30",
                    "description": f"Purplelink Paper Review — receipt for Stripe session {session_id[-8:]}",
                    "footer": (
                        tax_id_line + ("\n" if tax_id_line else "") +
                        "Purplelink LLC, 8735 Dunwoody Place #12398, Atlanta, GA 30350, USA."
                    ),
                },
            )
            if inv_resp.status_code >= 300:
                return JSONResponse(
                    {"error": "stripe_invoice_failed", "detail": inv_resp.text[:300]},
                    status_code=502,
                )
            invoice = inv_resp.json()
            invoice_id = invoice.get("id")

            # Add a line item
            item_resp = await client.post(
                "https://api.stripe.com/v1/invoiceitems",
                headers={"Authorization": f"Bearer {stripe_key}"},
                data={
                    "customer": customer,
                    "invoice": invoice_id,
                    "amount": str(amount_total),
                    "currency": currency,
                    "description": f"AI Paper Review (Stripe session {session_id[-8:]})",
                },
            )
            if item_resp.status_code >= 300:
                return JSONResponse(
                    {"error": "stripe_invoice_item_failed", "detail": item_resp.text[:300]},
                    status_code=502,
                )

            # Finalise
            final_resp = await client.post(
                f"https://api.stripe.com/v1/invoices/{invoice_id}/finalize",
                headers={"Authorization": f"Bearer {stripe_key}"},
                data={"auto_advance": "false"},
            )
            if final_resp.status_code >= 300:
                return JSONResponse(
                    {"error": "stripe_finalize_failed", "detail": final_resp.text[:300]},
                    status_code=502,
                )
            finalised = final_resp.json()

            invoice_pdf = finalised.get("invoice_pdf")
            hosted_invoice_url = finalised.get("hosted_invoice_url")

            # Email it
            if customer_email and invoice_pdf:
                from latextools import delivery as _delivery
                try:
                    await _delivery.send_email(
                        client,
                        to=customer_email,
                        subject="Your Purplelink invoice",
                        html=_delivery.html_invoice_ready(
                            invoice_url=invoice_pdf,
                            amount_cents=amount_total,
                        ),
                        tags=[{"name": "type", "value": "invoice"}],
                    )
                except Exception:
                    logger.exception("invoice email failed")

        return JSONResponse({
            "status": "ok",
            "invoice_pdf": invoice_pdf,
            "hosted_invoice_url": hosted_invoice_url,
            "amount": amount_total,
        })

    return api
