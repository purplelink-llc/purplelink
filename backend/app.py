"""Modal app for the purplelink LaTeX tools backend."""
from __future__ import annotations

import datetime

import modal

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
    )
    .pip_install("fastapi[standard]==0.115.2")
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
    "http://localhost:4200",
]

_COMPILE_KW = dict(
    image=image,
    timeout=90,
    cpu=1.0,
    memory=2048,
    max_containers=4,
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
        return (
            fwd.split(",")[0].strip()
            if fwd
            else (request.client.host if request.client else "0.0.0.0")
        )

    def _enforce_rate_limit(request: Request) -> bool:
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
            return JSONResponse(
                {"error": "compile", "errors": result["errors"]}, status_code=422
            )
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
            return JSONResponse(
                {"error": "compile", "errors": result["errors"]}, status_code=422
            )
        return _pdf_response(result["pdf"], "diff.pdf")

    return api
