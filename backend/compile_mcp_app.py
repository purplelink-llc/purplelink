"""Modal app for the Purplelink LaTeX compile app (prototype): an MCP server for ChatGPT (Apps SDK) and Claude.

Two functions, as in citation_mcp_app.py's reasoning:
  web      slim image (MCP SDK only), answers MCP requests, cheap and quick to start
  compile  TeX Live image with the site's hardening (texmf.cnf openin_any/openout_any = p, shell escape off,
           checked at build time); called by web for each compile_latex request, so only compiles pay the
           large image's cold start, and a burst of chat traffic cannot starve the site's own tools (app.py)
It shares the site's rate-limit store (modal.Dict "latextools-rate") under its own bucket.

Deploy (Ben only, after review):  cd backend && python3 -m modal deploy compile_mcp_app.py
Endpoint: https://ben-ampel--purplelink-latex-mcp-web.modal.run/mcp
Never `modal serve` this for testing: that publishes a temporary public URL. Test locally with
scripts/compile_mcp_local.py (uvicorn on 127.0.0.1, compiling with this Mac's TeX).
"""
import datetime
import os

import modal

app = modal.App("purplelink-latex-mcp")

web_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("mcp==1.30.0")
    .add_local_python_source("latextools")
)

tex_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "texlive-latex-recommended",
        "texlive-latex-extra",
        "texlive-fonts-recommended",
        "texlive-science",
        "texlive-bibtex-extra",
        "texlive-xetex",
        "texlive-luatex",
        "latexmk",
        "biber",
        "poppler-utils",
    )
    # Same paranoid hardening as app.py's image, verified at build time (the build fails if it did not take).
    .add_local_file("texmf.cnf", "/etc/texmf/texmf.d/99-hardening.cnf", copy=True)
    .run_commands(
        "update-texmf",
        "test \"$(kpsewhich -var-value=openin_any)\" = p",
        "test \"$(kpsewhich -var-value=shell_escape)\" = f",
    )
    .add_local_python_source("latextools")
)

rate_dict = modal.Dict.from_name("latextools-rate", create_if_missing=True)

# OpenAI's domain verification token (Apps dashboard, "Domain verification"). Not a secret. Paste and redeploy.
OPENAI_APPS_CHALLENGE = ""

DAILY_CALLS_PER_IP = int(os.environ.get("COMPILE_MCP_DAILY_CALLS", "300"))


def _rate_check(ip: str) -> bool:
    from latextools import core

    day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    key = core.rate_limit_key(ip, day, bucket="mcp-compile")
    try:
        allowed, _ = core.check_and_increment(rate_dict, key, limit=DAILY_CALLS_PER_IP)
    except Exception:
        return True  # the counter store being down must not take the tools down
    return allowed


@app.function(image=tex_image, timeout=90, cpu=1.0, memory=1024, max_containers=3)
def compile_tex(source: str, engine: str, bibliography: str | None) -> dict:
    from latextools import compile_job

    return compile_job.compile_document(source, engine, bibliography)


@app.function(image=web_image, timeout=120, cpu=0.25, memory=256, max_containers=2)
@modal.concurrent(max_inputs=16)
@modal.asgi_app()
def web():
    import logging

    from latextools import compile_job, compile_server

    logging.basicConfig(level=logging.INFO)

    async def backend(source: str, engine: str, bibliography: str | None) -> dict:
        try:
            return await compile_tex.remote.aio(source, engine, bibliography)
        except compile_job.InputError:
            raise
        except modal.exception.RemoteError as e:
            raise compile_job.InputError(str(e).splitlines()[-1][:300])

    return compile_server.create_app(
        rate_check=_rate_check,
        public=True,
        compile_backend=backend,
        challenge_token=OPENAI_APPS_CHALLENGE or None,
    )
