"""MCP server for the Purplelink citation app (ChatGPT Apps SDK and Claude connectors).

Three read-only tools over streamable HTTP, stateless, no login, nothing stored.
Reference text is sent to Crossref and Semantic Scholar and nowhere else, and is
never logged: only counts are.

The lookup logic lives in citation_check.py; this module is the MCP surface:
tool definitions, schemas, annotations, the per-IP rate limit, and the text each
result carries. Build the ASGI app with create_app().
"""
from __future__ import annotations

import logging
import os
from typing import Annotated, Any, Callable, Optional

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from latextools import citation_check as cc

log = logging.getLogger("citation_mcp")
# httpx logs every request URL at INFO, and our URLs carry the reference text. Keep them out of the logs.
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

UTM = "?utm_source=chatgpt-app&utm_medium=app&utm_campaign=citations"
SITE = "https://purplelink.llc"
LINK_REFERENCES = f"{SITE}/tools/bib-validator/{UTM}"
LINK_RETRACTIONS = f"{SITE}/tools/retraction-check/{UTM}"
LINK_BIBTEX = f"{SITE}/tools/bib-builder/{UTM}"

# Per-IP daily cap on tool calls. ChatGPT calls arrive from OpenAI's shared egress
# addresses, so this is a abuse guard, not a per-user quota: keep it generous.
DAILY_CALLS_PER_IP = int(os.environ.get("CITATION_MCP_DAILY_CALLS", "600"))

# The optional ModernTex / Paper Review line is OFF by default. OpenAI's submission
# guidelines prohibit upgrade prompts and advertising in plugins; see
# docs/products/chatgpt-citation-app.md before turning it on.
PRODUCT_NOTES = os.environ.get("CITATION_APP_PRODUCT_NOTES") == "1"

# Replaced by create_app(): (client_ip) -> allowed?
_rate_check: Callable[[str], bool] = lambda ip: True
# Replaced in tests: () -> httpx.AsyncClient
_client_factory: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0))

NOAUTH = {"securitySchemes": [{"type": "noauth"}]}
def _read_only(title: str) -> ToolAnnotations:
    """Read-only, open-world annotations. The title is repeated in annotations.title, which the Claude directory
    reads for its listing (the top-level tool title alone draws a review suggestion)."""
    return ToolAnnotations(title=title, readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)



# ------------------------------------------------------------ output schemas


class Mismatch(BaseModel):
    field: str
    cited: str
    found: str


class Notice(BaseModel):
    type: str
    doi: str
    date: str
    url: str


class ReferenceResult(BaseModel):
    index: int
    key: Optional[str] = None
    reference: str
    status: str = Field(description="found | needs_review | likely_hallucinated | not_found | lookup_failed | lookup_incomplete")
    match_score: Optional[float] = None
    matched_doi: Optional[str] = None
    matched_title: Optional[str] = None
    matched_source: Optional[str] = None
    mismatches: list[Mismatch]
    retraction_status: str = Field(description="none | corrected | expression_of_concern | retracted | unknown")
    retraction_notices: list[Notice]
    notes: list[str]


class ReferenceSummary(BaseModel):
    total: int
    found: int
    needs_review: int
    likely_hallucinated: int
    not_found: int
    lookup_failed: int
    retracted: int
    expression_of_concern: int
    corrected: int


class CheckReferencesOutput(BaseModel):
    summary: ReferenceSummary
    results: list[ReferenceResult]
    notes: list[str]


class DoiRetraction(BaseModel):
    doi: str
    status: str = Field(description="none | corrected | expression_of_concern | retracted | not_in_crossref | lookup_failed")
    title: Optional[str] = None
    notices: list[Notice]
    note: str


class CheckRetractionsOutput(BaseModel):
    summary: dict[str, int]
    dois: list[DoiRetraction]
    references_without_doi: list[ReferenceResult]
    notes: list[str]


class BibtexItem(BaseModel):
    doi: str
    status: str = Field(description="ok | not_found | error")
    bibtex: Optional[str] = None


class DoiToBibtexOutput(BaseModel):
    entries: list[BibtexItem]
    bibtex: str
    notes: list[str]


# ------------------------------------------------------------------- helpers


def _client_ip(ctx: Context | None) -> str:
    try:
        req = ctx.request_context.request  # type: ignore[union-attr]
        fwd = req.headers.get("x-forwarded-for", "")
        peer = req.client.host if req.client else None
    except Exception:
        return "0.0.0.0"
    from latextools import core
    return core.client_ip_from_forwarded(fwd, peer)


async def _guard(ctx: Context | None) -> None:
    # The production check talks to a modal.Dict over the network; keep it off the event loop.
    import anyio
    allowed = await anyio.to_thread.run_sync(_rate_check, _client_ip(ctx))
    if not allowed:
        raise ToolError("Rate limit reached for today from this network. Try again tomorrow, or use the free tool at "
                        f"{SITE}/tools/bib-validator/{UTM}")


def _footer(link: str, note: str = "") -> str:
    lines = [f"Full free tool: {link}"]
    if PRODUCT_NOTES and note:
        lines.append(note)
    return "\n".join(lines)


NOTE_MODERNTEX = "ModernTex, a Mac LaTeX editor, autocompletes citations from your .bib file."
NOTE_PAPER_REVIEW = "Paper Review checks a whole manuscript, including its citations, before submission."


def _result(text: str, structured: dict) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)], structuredContent=structured)


def _line(r: dict) -> str:
    label = r["key"] or f"#{r['index']}"
    bits = [f"{label}: {r['status'].replace('_', ' ')}"]
    if r["matched_title"] and r["status"] != "found":
        bits.append(f'closest: "{r["matched_title"][:90]}"')
    if r["matched_doi"]:
        bits.append(f"doi {r['matched_doi']}")
    for m in r["mismatches"]:
        bits.append(f"{m['field']} differs (cited {m['cited'][:40]}, found {m['found'][:40]})")
    if r["retraction_status"] in ("retracted", "expression_of_concern", "corrected"):
        n = r["retraction_notices"][0] if r["retraction_notices"] else None
        bits.append(r["retraction_status"].replace("_", " ").upper() + (f" ({n['url']})" if n and n["url"] else ""))
    return "- " + "; ".join(bits)


# --------------------------------------------------------------------- server


def build_server(public: bool = False) -> FastMCP:
    """public=False: a local run, with the SDK's DNS-rebinding guard limited to loopback hosts and origins.
    public=True (the deployed server): the guard is off. It protects servers on a user's own machine from hostile web
    pages; a public, unauthenticated, read-only server has nothing for it to protect, and the Origin headers
    ChatGPT and Claude send are not documented, so an origin allow-list could only break real clients."""
    if not public:
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
        )
    else:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp = FastMCP(
        "purplelink-citations",
        instructions=(
            "Checks academic references against Crossref and Semantic Scholar. Use check_references to verify that "
            "cited papers exist and match, check_retractions for retraction status of DOIs, and doi_to_bibtex to get "
            "BibTeX entries. Results are lookups against public indexes; report them as such."
        ),
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )

    @mcp.tool(
        name="check_references",
        title="Check references exist and match",
        description=(
            "Verify that academic references are real. Accepts a BibTeX string or a pasted plain-text reference list "
            f"(up to {cc.MAX_ENTRIES} entries, {cc.MAX_INPUT_BYTES // 1000} KB). Each entry is looked up in Crossref, then "
            "Semantic Scholar. Returns per entry: found, needs_review, likely_hallucinated (closest published title is a "
            "poor match), not_found or lookup_failed; the matched DOI and title; mismatched year, authors or venue; and "
            "whether the work is retracted, has an expression of concern, or has a correction. Use when a user wants "
            "to check a bibliography, or doubts that a citation (for example one a language model wrote) exists. "
            "Read-only; nothing is stored."
        ),
        annotations=_read_only("Check references exist and match"),
        meta=NOAUTH,
    )
    async def check_references(
        references: Annotated[str, Field(min_length=1, max_length=cc.MAX_INPUT_BYTES,
                                         description="BibTeX entries, or one reference per line or blank-line-separated paragraph, each with a year.")],
        ctx: Context,
    ) -> Annotated[CallToolResult, CheckReferencesOutput]:
        await _guard(ctx)
        try:
            refs, notes = cc.parse_references(references)
        except cc.InputError as e:
            raise ToolError(str(e))
        async with _client_factory() as client:
            results = await cc.check_references(client, refs)
        summary = cc.summarize_references(results)
        log.info("check_references entries=%d found=%d flagged=%d", summary["total"], summary["found"],
                 summary["likely_hallucinated"] + summary["not_found"] + summary["retracted"])
        if summary["lookup_failed"]:
            notes.append(f"{summary['lookup_failed']} entries could not be looked up (Crossref or time limit). Send them again.")
        flagged = [r for r in results if r["status"] != "found" or r["mismatches"] or r["retraction_status"] in ("retracted", "expression_of_concern", "corrected")]
        head = (f"Checked {summary['total']} references: {summary['found']} found, {summary['needs_review']} need review, "
                f"{summary['likely_hallucinated']} likely hallucinated, {summary['not_found']} not found, "
                f"{summary['lookup_failed']} not looked up. Retracted: {summary['retracted']}, "
                f"expression of concern: {summary['expression_of_concern']}, corrected: {summary['corrected']}.")
        body = "\n".join(_line(r) for r in flagged[:60])
        if len(flagged) > 60:
            body += f"\n(and {len(flagged) - 60} more in the structured results)"
        text = "\n".join(x for x in [head, body, " ".join(notes), "A found match means a published paper with that title exists, not that it supports the claim it is cited for.", _footer(LINK_REFERENCES, NOTE_MODERNTEX)] if x)
        return _result(text, {"summary": summary, "results": results, "notes": notes})

    @mcp.tool(
        name="check_retractions",
        title="Check DOIs for retractions",
        description=(
            "Look up the retraction, correction and expression-of-concern status of papers in Crossref, which carries "
            "Retraction Watch data. Accepts a list of DOIs, or a BibTeX string or reference list (DOIs are extracted; "
            f"up to {cc.MAX_TITLE_LOOKUPS_RETRACTION} references without a DOI are matched by title). Returns status per DOI "
            "with a link to the notice. Use before citing a paper, or when a user asks whether a paper was retracted. "
            "A clear result is not a guarantee: a very recent retraction may not be in Crossref yet. Read-only; nothing is stored."
        ),
        annotations=_read_only("Check DOIs for retractions"),
        meta=NOAUTH,
    )
    async def check_retractions(
        ctx: Context,
        dois: Annotated[Optional[list[Annotated[str, Field(max_length=200)]]], Field(max_length=cc.MAX_DOIS, description="DOIs, bare or as doi.org links.")] = None,
        references: Annotated[Optional[str], Field(max_length=cc.MAX_INPUT_BYTES, description="Alternative to dois: BibTeX or a reference list.")] = None,
    ) -> Annotated[CallToolResult, CheckRetractionsOutput]:
        await _guard(ctx)
        if not dois and not references:
            raise ToolError("Provide dois, or references (BibTeX or a reference list).")
        notes: list[str] = []
        wanted: list[str] = []
        titleless: list[cc.Reference] = []
        if dois:
            try:
                wanted, n = cc.clean_doi_list(dois, cc.MAX_DOIS)
            except cc.InputError:
                if not references:
                    raise ToolError("No valid DOIs found. A DOI looks like 10.1038/nature14539.")
                n = ["None of the DOIs in the dois list were valid."]
            notes += n
        if references:
            try:
                cc._check_size(references)
            except cc.InputError as e:
                raise ToolError(str(e))
            seen = {d.lower() for d in wanted}
            for d in cc.extract_dois(references):
                if d.lower() not in seen and len(wanted) < cc.MAX_DOIS:
                    seen.add(d.lower())
                    wanted.append(d)
            try:
                refs, _ = cc.parse_references(references)
            except cc.InputError:
                refs = []
            titleless = [r for r in refs if not r.doi]
            if len(titleless) > cc.MAX_TITLE_LOOKUPS_RETRACTION:
                notes.append(f"{len(titleless) - cc.MAX_TITLE_LOOKUPS_RETRACTION} references without a DOI were not looked up: "
                             f"only {cc.MAX_TITLE_LOOKUPS_RETRACTION} title lookups run per call.")
                titleless = titleless[:cc.MAX_TITLE_LOOKUPS_RETRACTION]
        if not wanted and not titleless:
            raise ToolError("No DOIs or checkable references found in the input.")
        async with _client_factory() as client:
            doi_results = await cc.retractions_for_dois(client, wanted) if wanted else []
            ref_results = await cc.check_references(client, titleless) if titleless else []
        counts: dict[str, int] = {}
        for r in doi_results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        for r in ref_results:
            k = r["retraction_status"]
            counts[k] = counts.get(k, 0) + 1
        log.info("check_retractions dois=%d refs=%d retracted=%d", len(doi_results), len(ref_results), counts.get("retracted", 0))
        lines = []
        for r in doi_results:
            if r["status"] in ("none",):
                continue
            n = r["notices"][0] if r["notices"] else None
            lines.append(f"- {r['doi']}: {r['status'].replace('_', ' ')}" + (f" ({n['type']}, {n['date'] or 'date unknown'}, {n['url']})" if n else "") + (f" {r['note']}" if r["note"] else ""))
        for r in ref_results:
            if r["retraction_status"] in ("retracted", "expression_of_concern", "corrected") or r["status"] in ("not_found", "lookup_failed", "lookup_incomplete"):
                lines.append(_line(r))
        head = (f"Checked {len(doi_results)} DOIs and {len(ref_results)} references without a DOI. "
                + ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in sorted(counts.items())) + ".")
        text = "\n".join(x for x in [head, "\n".join(lines[:80]), " ".join(notes), _footer(LINK_RETRACTIONS, NOTE_PAPER_REVIEW)] if x)
        return _result(text, {"summary": counts, "dois": doi_results, "references_without_doi": ref_results, "notes": notes})

    @mcp.tool(
        name="doi_to_bibtex",
        title="Get BibTeX for DOIs",
        description=(
            f"Return BibTeX entries for up to {cc.MAX_BIBTEX_DOIS} DOIs, fetched from Crossref content negotiation. "
            "Use when a user has DOIs (bare or doi.org links) and wants .bib entries to paste into a LaTeX project. "
            "Entries are Crossref's own; check capitalisation and fields before submitting. Read-only; nothing is stored."
        ),
        annotations=_read_only("Get BibTeX for DOIs"),
        meta=NOAUTH,
    )
    async def doi_to_bibtex(
        dois: Annotated[list[Annotated[str, Field(max_length=200)]], Field(min_length=1, max_length=cc.MAX_BIBTEX_DOIS,
                                                                          description="DOIs, bare or as doi.org links.")],
        ctx: Context,
    ) -> Annotated[CallToolResult, DoiToBibtexOutput]:
        await _guard(ctx)
        try:
            clean, notes = cc.clean_doi_list(dois, cc.MAX_BIBTEX_DOIS)
        except cc.InputError as e:
            raise ToolError(str(e))
        async with _client_factory() as client:
            entries = await cc.bibtex_for_dois(client, clean)
        ok = [e for e in entries if e["status"] == "ok"]
        log.info("doi_to_bibtex dois=%d ok=%d", len(entries), len(ok))
        bib = "\n\n".join(e["bibtex"] for e in ok)
        failed = [e["doi"] for e in entries if e["status"] != "ok"]
        if failed:
            notes.append("No BibTeX for: " + ", ".join(failed) + ". They may be mistyped or registered with another agency.")
        text = "\n".join(x for x in [f"BibTeX for {len(ok)} of {len(entries)} DOIs.", bib, " ".join(notes), _footer(LINK_BIBTEX, NOTE_MODERNTEX)] if x)
        return _result(text, {"entries": entries, "bibtex": bib, "notes": notes})

    return mcp


def create_app(rate_check: Callable[[str], bool] | None = None, public: bool = False,
               challenge_token: str | None = None) -> Any:
    """ASGI app: the MCP endpoint at /mcp, a health route, and (optionally) the OpenAI domain challenge."""
    global _rate_check
    if rate_check is not None:
        _rate_check = rate_check
    mcp = build_server(public)
    app = mcp.streamable_http_app()

    from starlette.responses import JSONResponse, PlainTextResponse
    from starlette.routing import Route

    async def health(_request):
        return JSONResponse({"ok": True, "service": "purplelink-citations"})

    app.router.routes.append(Route("/health", health))
    if challenge_token:
        async def challenge(_request):
            return PlainTextResponse(challenge_token)
        app.router.routes.append(Route("/.well-known/openai-apps-challenge", challenge))
    return app
