"""LaTeX compile app (MCP server, prototype): error explanations, input limits, bibliography file names, tool
annotations and schemas, result content, and the rate limit. Hermetic: the compile backend is a fake, except the
one integration test at the end, which runs only where latexmk is installed."""
import asyncio
import base64
import shutil

import pytest

from latextools import compile_explain as ce
from latextools import compile_job as cj

mcp_memory = pytest.importorskip("mcp.shared.memory")
from latextools import compile_server as cs  # noqa: E402  (needs the MCP SDK)


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------ explanations


@pytest.mark.parametrize("message,kind", [
    ("Undefined control sequence.", "undefined-control-sequence"),
    ("Missing $ inserted.", "missing-dollar-inserted"),
    ("LaTeX Error: File `tikz-cd.sty' not found.", "file-not-found"),
    ("LaTeX Error: Environment algin undefined.", "environment-undefined"),
    ("Extra alignment tab has been changed to \\cr.", "extra-alignment-tab"),
    ("Misplaced alignment tab character &.", "misplaced-alignment-tab"),
    ("Paragraph ended before \\textbf was complete.", "paragraph-ended-before-complete"),
    ("Too many }'s.", "too-many-closing-braces"),
    ("Package inputenc Error: Unicode character \u2014 (U+2014)", "unicode-character"),
    ("LaTeX Error: Option clash for package xcolor.", "option-clash"),
    ("Double superscript.", "double-script"),
    ("LaTeX Error: Missing \\begin{document}.", "missing-begin-document"),
])
def test_errors_are_recognised(message, kind):
    ex = ce.explain(message)
    assert ex and ex["kind"] == kind
    assert ex["explanation"] and ex["fix"] and "@1@" not in ex["explanation"] + ex["fix"]


def test_captured_names_and_literal_braces_are_filled_in():
    ex = ce.explain("LaTeX Error: File `tikz-cd.sty' not found.")
    assert "tikz-cd.sty" in ex["explanation"]
    assert "\\usepackage[demo]{graphicx}" in ex["fix"]
    ex = ce.explain("LaTeX Error: Environment algin undefined.")
    assert "\\begin{algin}" in ex["explanation"] and "algin" in ex["fix"]
    assert ce.explain("Double subscript.")["fix"] == "Group with braces: x^{2^3} or {x^2}^3."


def test_learn_more_links_only_where_a_site_page_exists():
    assert ce.explain("Undefined control sequence.")["learn_more"].startswith(
        "https://purplelink.llc/latex-errors/undefined-control-sequence/?utm_source=latex-app")
    assert ce.explain("Double superscript.")["learn_more"] is None


def test_unknown_message_is_none_and_explain_any_falls_back_to_warnings():
    assert ce.explain("Something nobody has seen") is None
    assert ce.explain_any("LaTeX Warning: Citation `knuth84' on page 1 undefined")["kind"] == "citation-undefined"


def test_warnings_from_log_dedupes_and_counts_overfull_lines():
    log = "\n".join([
        "LaTeX Warning: Citation `a' on page 1 undefined on input line 5.",
        "LaTeX Warning: Citation `a' on page 1 undefined on input line 5.",
        "LaTeX Warning: Reference `fig:x' on page 2 undefined on input line 9.",
        "Overfull \\hbox (12.0pt too wide) in paragraph at lines 3--4",
        "Overfull \\hbox (3.0pt too wide) in paragraph at lines 7--8",
        "LaTeX Warning: Label(s) may have changed.",
    ])
    kinds = [w["kind"] for w in ce.warnings_from_log(log)]
    assert kinds == ["citation-undefined", "reference-undefined", "overfull-hbox"]
    assert ce.warnings_from_log(log)[-1]["message"] == "2 overfull line(s)"


# ------------------------------------------------------------ input checks


def test_validate_rejects_empty_fragment_unknown_engine_and_oversize():
    good = "\\documentclass{article}\\begin{document}x\\end{document}"
    cj.validate(good, "pdflatex", None)
    for args in [("", "pdflatex", None), ("just text", "pdflatex", None), (good, "context", None), (good, "lualatex", None),
                 ("\\documentclass{article}" + "x" * cj.MAX_SOURCE_CHARS, "pdflatex", None),
                 (good, "pdflatex", "x" * (cj.MAX_BIB_CHARS + 1))]:
        with pytest.raises(cj.InputError):
            cj.validate(*args)


def test_bib_filenames_follow_the_document_and_never_leave_the_folder():
    assert cj.bib_filenames("no bibliography here") == ["refs.bib"]
    assert cj.bib_filenames("\\bibliography{main,extra}") == ["main.bib", "extra.bib"]
    assert cj.bib_filenames("\\addbibresource[label=x]{lib.bib}") == ["lib.bib"]
    assert cj.bib_filenames("\\bibliography{../../etc/passwd,/abs/path,a.b,ok}") == ["ok.bib"]


# ------------------------------------------------------------------ server

PDF = b"%PDF-1.5 fake"
PNG = b"\x89PNG fake"


def ok_result(**kw):
    base = {"ok": True, "timed_out": False, "engine": "pdflatex", "pages": 2, "errors": [], "warnings": [],
            "pdf": PDF, "pdf_bytes": len(PDF), "pdf_omitted": False, "preview_png": PNG, "log_tail": ""}
    base.update(kw)
    return base


@pytest.fixture
def server(monkeypatch):
    calls = []

    async def backend(source, engine, bibliography):
        calls.append((engine, bibliography))
        return ok_result(engine=engine)
    monkeypatch.setattr(cs, "_compile_backend", backend)
    monkeypatch.setattr(cs, "_rate_check", lambda ip: True)
    srv = cs.build_server()
    srv.calls = calls
    return srv


def call(server, tool, args):
    async def go():
        async with mcp_memory.create_connected_server_and_client_session(server._mcp_server) as s:
            return await s.call_tool(tool, args)
    return run(go())


DOC = "\\documentclass{article}\\begin{document}Hi\\end{document}"


def test_tools_have_annotations_titles_schemas_and_no_auth_scheme(server):
    async def go():
        async with mcp_memory.create_connected_server_and_client_session(server._mcp_server) as s:
            return (await s.list_tools()).tools
    tools = {t.name: t for t in run(go())}
    assert set(tools) == {"compile_latex", "explain_latex_error"}
    for t in tools.values():
        a = t.annotations
        assert a.readOnlyHint is True and a.destructiveHint is False and a.openWorldHint is False
        assert t.title and len(t.description) > 80
        assert t.inputSchema["type"] == "object" and t.outputSchema["type"] == "object"
        assert t.meta["securitySchemes"] == [{"type": "noauth"}]
        assert a.title == t.title  # the directory reads annotations.title
        # store rules: no product promotion in tool text
        assert "ModernTex" not in t.description and "Paper Review" not in t.description
    props = tools["compile_latex"].inputSchema["properties"]
    assert props["source"]["maxLength"] == cj.MAX_SOURCE_CHARS
    assert props["engine"]["enum"] == ["pdflatex", "xelatex"]


def test_compile_success_returns_text_preview_image_and_pdf(server):
    res = call(server, "compile_latex", {"source": DOC, "engine": "xelatex", "bibliography": "@misc{a,title={A}}"})
    assert not res.isError
    kinds = [c.type for c in res.content]
    assert kinds == ["text", "image", "resource"]
    assert "Compiled with xelatex: 2 pages." in res.content[0].text
    assert base64.b64decode(res.content[1].data) == PNG
    assert res.content[2].resource.mimeType == "application/pdf"
    assert base64.b64decode(res.content[2].resource.blob) == PDF
    s = res.structuredContent
    assert s["ok"] is True and s["pdf_included"] is True and s["pages"] == 2
    assert server.calls == [("xelatex", "@misc{a,title={A}}")]


def test_compile_failure_explains_each_error_and_attaches_no_pdf(server, monkeypatch):
    async def failing(source, engine, bibliography):
        err = {"file": "main.tex", "line": 4, "message": "Undefined control sequence.",
               **ce.explain("Undefined control sequence.")}
        return ok_result(ok=False, pdf=None, pdf_bytes=0, preview_png=None, pages=None, errors=[err])
    monkeypatch.setattr(cs, "_compile_backend", failing)
    res = call(server, "compile_latex", {"source": DOC})
    assert not res.isError and [c.type for c in res.content] == ["text"]
    text = res.content[0].text
    assert "failed: 1 error." in text and "line 4: Undefined control sequence." in text
    assert "What it means:" in text and "/latex-errors/undefined-control-sequence/" in text
    assert res.structuredContent["errors"][0]["kind"] == "undefined-control-sequence"
    assert res.structuredContent["pdf_included"] is False


def test_compile_timeout_and_oversize_pdf_are_reported(server, monkeypatch):
    async def slow(*a):
        return ok_result(ok=False, timed_out=True, pdf=None, pdf_bytes=0, preview_png=None)
    monkeypatch.setattr(cs, "_compile_backend", slow)
    assert "did not finish within" in call(server, "compile_latex", {"source": DOC}).content[0].text

    async def big(*a):
        return ok_result(pdf=None, pdf_bytes=9_000_000, pdf_omitted=True)
    monkeypatch.setattr(cs, "_compile_backend", big)
    res = call(server, "compile_latex", {"source": DOC})
    assert "too large to attach" in res.content[0].text
    assert [c.type for c in res.content] == ["text", "image"]


def test_compile_rejects_fragments_before_calling_the_backend(server):
    res = call(server, "compile_latex", {"source": "E = mc^2"})
    assert res.isError and "\\documentclass" in res.content[0].text
    assert server.calls == []


def test_backend_crash_is_a_short_tool_error(server, monkeypatch):
    async def boom(*a):
        raise RuntimeError("container died: /secret/path")
    monkeypatch.setattr(cs, "_compile_backend", boom)
    res = call(server, "compile_latex", {"source": DOC})
    assert res.isError and "could not run just now" in res.content[0].text
    assert "/secret/path" not in res.content[0].text


def test_rate_limit_blocks_both_tools(server, monkeypatch):
    monkeypatch.setattr(cs, "_rate_check", lambda ip: False)
    for tool, args in [("compile_latex", {"source": DOC}), ("explain_latex_error", {"message": "Missing $ inserted."})]:
        res = call(server, tool, args)
        assert res.isError and "Rate limit reached" in res.content[0].text
    assert server.calls == []


def test_explain_tool_handles_one_message_a_log_and_unknown_text(server):
    res = call(server, "explain_latex_error", {"message": "! Missing $ inserted."})
    assert res.structuredContent["matched"] is True
    assert res.structuredContent["issues"][0]["kind"] == "missing-dollar-inserted"

    log = ("./main.tex:12: Undefined control sequence.\n"
           "./main.tex:12: ==> Fatal error occurred, no output PDF file produced!\n"
           "LaTeX Warning: Citation `x' on page 1 undefined on input line 3.\n")
    issues = call(server, "explain_latex_error", {"message": log}).structuredContent["issues"]
    assert [i["kind"] for i in issues] == ["undefined-control-sequence", "citation-undefined"]
    assert issues[0]["line"] == 12

    res = call(server, "explain_latex_error", {"message": "my computer is slow"})
    assert res.structuredContent == {"matched": False, "issues": []}
    assert "paste that line" in res.content[0].text


# ------------------------------------------------------------- integration


@pytest.mark.skipif(not shutil.which("latexmk"), reason="needs a TeX installation")
def test_real_compile_with_bibliography_and_a_real_error():
    good = cj.compile_document(
        "\\documentclass{article}\\begin{document}See \\cite{k}.\\bibliographystyle{plain}"
        "\\bibliography{refs}\\end{document}",
        bibliography="@book{k, author={D. Knuth}, title={The TeXbook}, year={1984}, publisher={AW}}")
    assert good["ok"] and good["pages"] == 1 and good["pdf"].startswith(b"%PDF")
    assert not [w for w in good["warnings"] if w["kind"] == "citation-undefined"]

    bad = cj.compile_document("\\documentclass{article}\\begin{document}\nIt costs 5_000.\n\\end{document}")
    assert not bad["ok"] and bad["pdf"] is None
    assert [e["kind"] for e in bad["errors"]] == ["missing-dollar-inserted"]
    assert bad["errors"][0]["line"] == 2
