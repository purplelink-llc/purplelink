"""Modal app for the Purplelink citation app: an MCP server for ChatGPT (Apps SDK) and Claude (connectors).

Separate from app.py on purpose. app.py's web function runs on the TeX Live image (large, slow cold start)
with six containers shared by every free tool; this server needs only httpx, bibtexparser and the MCP SDK,
so a slim image keeps cold starts short for chat clients that wait on the call, and a burst of chat traffic
cannot starve the site's tools. It shares the site's rate-limit store (modal.Dict "latextools-rate") under its
own bucket.

Deploy (Ben only, after review):  cd backend && python3 -m modal deploy citation_mcp_app.py
Endpoint: https://ben-ampel--purplelink-citation-mcp-web.modal.run/mcp
Never `modal serve` this for testing: that publishes a temporary public URL. Test locally with
scripts/citation_mcp_local.py (uvicorn on 127.0.0.1).
"""
import datetime
import os

import modal

app = modal.App("purplelink-citation-mcp")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "mcp==1.30.0",
        "httpx==0.27.2",
        "bibtexparser>=1.3,<2",
    )
    .add_local_python_source("latextools")
)

rate_dict = modal.Dict.from_name("latextools-rate", create_if_missing=True)

# OpenAI's domain verification token (Apps dashboard, "Domain verification"). It is not a secret: OpenAI
# fetches it from https://<mcp host>/.well-known/openai-apps-challenge. Paste it here and redeploy.
OPENAI_APPS_CHALLENGE = ""

# ChatGPT and Claude call from shared egress ranges, so this is an abuse guard, not a per-user quota.
DAILY_CALLS_PER_IP = int(os.environ.get("CITATION_MCP_DAILY_CALLS", "600"))


def _rate_check(ip: str) -> bool:
    from latextools import core

    day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    key = core.rate_limit_key(ip, day, bucket="mcp-citations")
    try:
        allowed, _ = core.check_and_increment(rate_dict, key, limit=DAILY_CALLS_PER_IP)
    except Exception:
        return True  # the counter store being down must not take the tools down
    return allowed


@app.function(
    image=image,
    timeout=60,
    cpu=0.5,
    memory=512,
    max_containers=4,
)
@modal.concurrent(max_inputs=16)
@modal.asgi_app()
def web():
    import logging

    from latextools import citation_server

    # Counts only. httpx logs every request URL at INFO, and a Crossref search URL carries the reference text.
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return citation_server.create_app(
        rate_check=_rate_check,
        public=True,
        challenge_token=OPENAI_APPS_CHALLENGE or None,
    )
