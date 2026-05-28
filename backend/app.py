"""Modal app for the purplelink LaTeX tools backend."""
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
        "pandoc",
    )
    .pip_install(
        "fastapi[standard]==0.115.2",
        "python-docx==1.1.2",
        "lxml==5.3.0",
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
    "http://localhost:4200",
]


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

    def _result_or_error(res) -> Response:
        if res.timed_out:
            return JSONResponse({"error": "timeout"}, status_code=422)
        if not res.ok:
            return JSONResponse(
                {"error": "compile", "errors": res.errors}, status_code=422
            )
        return None

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

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                return runner.run_compile(Path(d), tex, engine, timeout=60)

        res = await run_in_threadpool(_do)
        return _result_or_error(res) or _pdf_response(res.pdf_bytes, "compiled.pdf")

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

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                return runner.run_diff(
                    Path(d), old_tex, new_tex, engine, timeout=60,
                    add_legend=(legend == "true"),
                )

        res = await run_in_threadpool(_do)
        return _result_or_error(res) or _pdf_response(res.pdf_bytes, "diff.pdf")

    return api
