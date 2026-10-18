"""MCP server for the Purplelink LaTeX compile app (ChatGPT Apps SDK and Claude connectors). Prototype.

Two tools over streamable HTTP, stateless, no login, nothing stored:
  compile_latex        one .tex document (+ optional .bib text) -> PDF, a page-1 preview, and every error and
                       warning explained in plain language with a fix
  explain_latex_error  a pasted error message or log -> the same explanations, without compiling

The compile itself runs elsewhere (compile_job.py on the TeX Live image, see compile_mcp_app.py); this module is
the MCP surface: tool definitions, schemas, annotations, the per-IP rate limit, and the text each result carries.
Source text is never logged, only counts. Build the ASGI app with create_app().
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Annotated, Any, Awaitable, Callable, Literal, Optional

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import (BlobResourceContents, CallToolResult, EmbeddedResource, ImageContent, TextContent,
                       ToolAnnotations)
from pydantic import BaseModel, Field

from latextools import compile_explain, compile_job, core

log = logging.getLogger("compile_mcp")

UTM = "?utm_source=latex-app&utm_medium=app&utm_campaign=compile"
SITE = "https://purplelink.llc"
LINK_COMPILE = f"{SITE}/tools/latex-to-pdf/{UTM}"
LINK_ERRORS = f"{SITE}/latex-errors/{UTM}"

# ChatGPT and Claude call from shared egress ranges, so this is an abuse guard, not a per-user quota.
DAILY_CALLS_PER_IP = int(os.environ.get("COMPILE_MCP_DAILY_CALLS", "300"))

# Replaced by create_app(): (client_ip) -> allowed?
_rate_check: Callable[[str], bool] = lambda ip: True


async def _local_backend(source: str, engine: str, bibliography: Optional[str]) -> dict:
    """Compile in this process (needs TeX on PATH). Production passes a Modal-backed function instead."""
    import anyio
    return await anyio.to_thread.run_sync(compile_job.compile_document, source, engine, bibliography)

# Replaced by create_app(): async (source, engine, bibliography) -> compile_job.compile_document()'s dict.
_compile_backend: Callable[[str, str, Optional[str]], Awaitable[dict]] = _local_backend

NOAUTH = {"securitySchemes": [{"type": "noauth"}]}
COMPILE_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                                      openWorldHint=False)
EXPLAIN_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                                      openWorldHint=False)


# ------------------------------------------------------------ output schemas


class ExplainedIssue(BaseModel):
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    kind: Optional[str] = Field(None, description="Short error id, for example undefined-control-sequence; null if unrecognised.")
    title: Optional[str] = None
    explanation: Optional[str] = None
    fix: Optional[str] = None
    learn_more: Optional[str] = None


class CompileOutput(BaseModel):
    ok: bool = Field(description="True when a PDF was produced.")
    timed_out: bool
    engine: str
    pages: Optional[int] = None
    pdf_bytes: int = Field(description="Size of the PDF in bytes, 0 when none was produced.")
    pdf_included: bool = Field(description="True when the PDF is attached to this result as an embedded resource.")
    errors: list[ExplainedIssue]
    warnings: list[ExplainedIssue]
    log_tail: str = Field(description="The end of the TeX log when the compile failed without a recognised error.")


class ExplainOutput(BaseModel):
    matched: bool
    issues: list[ExplainedIssue]


# ------------------------------------------------------------------- helpers


def _client_ip(ctx: Context | None) -> str:
    try:
        req = ctx.request_context.request  # type: ignore[union-attr]
        fwd = req.headers.get("x-forwarded-for", "")
        peer = req.client.host if req.client else None
    except Exception:
        return "0.0.0.0"
    return core.client_ip_from_forwarded(fwd, peer)


async def _guard(ctx: Context | None) -> None:
    # The production check talks to a modal.Dict over the network; keep it off the event loop.
    import anyio
    allowed = await anyio.to_thread.run_sync(_rate_check, _client_ip(ctx))
    if not allowed:
        raise ToolError(f"Rate limit reached for today from this network. Try again tomorrow, or use the free tool at {LINK_COMPILE}")


def _issue_line(i: dict) -> str:
    where = f"line {i['line']}: " if i.get("line") else ""
    head = f"- {where}{i.get('message', '').strip()}"
    if i.get("explanation"):
        head += f"\n  What it means: {i['explanation']}\n  Fix: {i['fix']}"
        if i.get("learn_more"):
            head += f"\n  More: {i['learn_more']}"
    return head


def _clean(issues: list[dict]) -> list[dict]:
    keys = ExplainedIssue.model_fields.keys()
    return [{k: v for k, v in i.items() if k in keys} for i in issues]


# --------------------------------------------------------------------- server


def build_server(public: bool = False) -> FastMCP:
    """public=False: a local run, with the SDK's DNS-rebinding guard limited to loopback hosts and origins.
    public=True (the deployed server): the guard is off, as in citation_server.py (a public, unauthenticated
    server has nothing for it to protect, and an origin allow-list could only break real clients)."""
    if not public:
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
        )
    else:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp = FastMCP(
        "purplelink-latex",
        instructions=(
            "Compiles LaTeX to PDF and explains LaTeX errors in plain language. Use compile_latex to check that a "
            "document you or the user wrote actually builds, and to get the PDF; use explain_latex_error when the "
            "user pastes an error message or log. Report errors with their fix, and recompile after fixing."
        ),
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )

    @mcp.tool(
        name="compile_latex",
        title="Compile LaTeX to PDF",
        description=(
            "Compile one complete LaTeX document (from \\documentclass to \\end{document}) with TeX Live and latexmk, "
            "and return the PDF, an image of page 1, and every error or warning explained in plain language with a "
            "fix and the line number. Optionally pass the contents of a .bib file as bibliography; it is saved under "
            "the name the document uses (\\bibliography{refs} or \\addbibresource{refs.bib}). Engines: pdflatex "
            "(default), xelatex or lualatex (use these for Unicode text or system fonts). Limits: "
            f"{compile_job.MAX_SOURCE_CHARS // 1000} KB of source, {compile_job.COMPILE_TIMEOUT} seconds. Only the one "
            "file and its bibliography are available, so \\includegraphics of image files and \\input of other "
            "files will fail; shell escape is off. Use after writing or editing LaTeX to confirm it builds before "
            "giving it to the user. Nothing is stored."
        ),
        annotations=COMPILE_ANNOTATIONS,
        meta=NOAUTH,
    )
    async def compile_latex(
        source: Annotated[str, Field(min_length=1, max_length=compile_job.MAX_SOURCE_CHARS,
                                     description="The complete .tex document.")],
        ctx: Context,
        engine: Annotated[Literal["pdflatex", "xelatex", "lualatex"], Field(description="TeX engine.")] = "pdflatex",
        bibliography: Annotated[Optional[str], Field(max_length=compile_job.MAX_BIB_CHARS,
                                                     description="Optional: the text of the .bib file the document cites.")] = None,
    ) -> Annotated[CallToolResult, CompileOutput]:
        await _guard(ctx)
        try:
            compile_job.validate(source, engine, bibliography)
        except compile_job.InputError as e:
            raise ToolError(str(e))
        try:
            res = await _compile_backend(source, engine, bibliography)
        except compile_job.InputError as e:
            raise ToolError(str(e))
        except Exception:
            log.exception("compile backend failed")
            raise ToolError("The compiler could not run just now. Try again in a minute.")

        errors, warnings = _clean(res.get("errors", [])), _clean(res.get("warnings", []))
        pdf: Optional[bytes] = res.get("pdf")
        log.info("compile_latex engine=%s ok=%s timed_out=%s errors=%d warnings=%d pages=%s bytes=%d",
                 engine, res.get("ok"), res.get("timed_out"), len(errors), len(warnings), res.get("pages"),
                 res.get("pdf_bytes", 0))

        if res.get("timed_out"):
            head = (f"The compile did not finish within {compile_job.COMPILE_TIMEOUT} seconds. The document may loop "
                    "(for example a macro that calls itself) or be too large for this tool.")
        elif res.get("ok"):
            pages = res.get("pages")
            head = f"Compiled with {engine}: {pages} page{'s' if pages != 1 else ''}." if pages else f"Compiled with {engine}."
            if res.get("pdf_omitted"):
                head += f" The PDF is {res.get('pdf_bytes', 0) // 1000} KB, too large to attach here."
        else:
            head = f"The compile with {engine} failed: {len(errors)} error{'s' if len(errors) != 1 else ''}."
        parts = [head]
        if errors:
            parts.append("Errors (LaTeX stops at the first one, so fix it and compile again):\n" + "\n".join(_issue_line(e) for e in errors[:10]))
        if warnings:
            parts.append("Warnings:\n" + "\n".join(_issue_line(w) for w in warnings[:10]))
        if not res.get("ok") and not errors and res.get("log_tail"):
            parts.append("End of the TeX log:\n" + res["log_tail"][-1500:])
        parts.append(f"Free online compiler: {LINK_COMPILE}")
        text = "\n\n".join(parts)

        content: list[Any] = [TextContent(type="text", text=text)]
        if res.get("preview_png"):
            content.append(ImageContent(type="image", mimeType="image/png",
                                        data=base64.b64encode(res["preview_png"]).decode("ascii")))
        if pdf:
            digest = hashlib.sha256(pdf).hexdigest()[:16]
            content.append(EmbeddedResource(type="resource", resource=BlobResourceContents(
                uri=f"purplelink-latex://compiled/{digest}.pdf", mimeType="application/pdf",
                blob=base64.b64encode(pdf).decode("ascii"))))
        structured = CompileOutput(
            ok=bool(res.get("ok")), timed_out=bool(res.get("timed_out")), engine=engine, pages=res.get("pages"),
            pdf_bytes=int(res.get("pdf_bytes") or 0), pdf_included=bool(pdf), errors=errors, warnings=warnings,
            log_tail=res.get("log_tail", "") if not res.get("ok") and not errors else "",
        ).model_dump()
        return CallToolResult(content=content, structuredContent=structured, isError=False)

    @mcp.tool(
        name="explain_latex_error",
        title="Explain a LaTeX error",
        description=(
            "Explain a LaTeX error or warning in plain language and say how to fix it, without compiling. Accepts one "
            "message (for example 'Undefined control sequence' or 'Missing $ inserted') or a pasted TeX log, from "
            "which every error and warning is explained. Use when the user pastes an error from Overleaf, TeXShop or "
            "a terminal. Nothing is stored."
        ),
        annotations=EXPLAIN_ANNOTATIONS,
        meta=NOAUTH,
    )
    async def explain_latex_error(
        message: Annotated[str, Field(min_length=1, max_length=60_000, description="An error message or a TeX log.")],
        ctx: Context,
    ) -> Annotated[CallToolResult, ExplainOutput]:
        await _guard(ctx)
        issues: list[dict] = []
        for e in core.parse_latex_log(message):
            if e["message"].startswith("==> Fatal error occurred"):
                continue
            issues.append({**e, **(compile_explain.explain(e["message"]) or {})})
        issues += compile_explain.warnings_from_log(message)
        if not issues:
            ex = compile_explain.explain_any(message)
            issues = [{"message": message.strip()[:300], **ex}] if ex else []
        issues = _clean(issues)
        matched = any(i.get("kind") for i in issues)
        log.info("explain_latex_error issues=%d matched=%s", len(issues), matched)
        if matched:
            text = "\n".join(_issue_line(i) for i in issues[:15])
        else:
            text = ("This message is not one of the errors this tool recognises. LaTeX usually reports the real cause "
                    "on the first line that starts with '!' or 'file:line:', so paste that line, or the whole log. "
                    f"Common errors are explained at {LINK_ERRORS}")
        return CallToolResult(content=[TextContent(type="text", text=text)],
                              structuredContent=ExplainOutput(matched=matched, issues=issues).model_dump())

    return mcp


def create_app(rate_check: Callable[[str], bool] | None = None, public: bool = False,
               compile_backend: Callable[[str, str, Optional[str]], Awaitable[dict]] | None = None,
               challenge_token: str | None = None) -> Any:
    """ASGI app: the MCP endpoint at /mcp, a health route, and (optionally) the OpenAI domain challenge."""
    global _rate_check, _compile_backend
    if rate_check is not None:
        _rate_check = rate_check
    if compile_backend is not None:
        _compile_backend = compile_backend
    mcp = build_server(public)
    app = mcp.streamable_http_app()

    from starlette.responses import JSONResponse, PlainTextResponse
    from starlette.routing import Route

    async def health(_request):
        return JSONResponse({"ok": True, "service": "purplelink-latex"})

    app.router.routes.append(Route("/health", health))
    if challenge_token:
        async def challenge(_request):
            return PlainTextResponse(challenge_token)
        app.router.routes.append(Route("/.well-known/openai-apps-challenge", challenge))
    return app
