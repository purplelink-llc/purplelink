"""Coverage for the two 2026-10 Paper Review changes:

1. POST /paper-review/preview, the free deterministic check before payment
   (CrossRef mocked at the HTTP transport, so no network).
2. The "review is ready" email carrying the report as an attachment, and
   never the manuscript or the annotated PDF.

Same hermetic approach as test_app_paper_review_endpoints.py: `web.local()`
returns the real FastAPI app and every modal.Dict handle is swapped for an
in-memory fake first.
"""
import base64
import io
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")
pytest.importorskip("pdfplumber")


class _AioBridge:
    def __init__(self, fn):
        self._fn = fn

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)

    async def aio(self, *args, **kwargs):
        return self._fn(*args, **kwargs)


class _FakeDict:
    def __init__(self):
        self._data = {}
        self.put = _AioBridge(self._put)
        self.pop = _AioBridge(self._pop)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def items(self):
        return self._data.items()

    def _put(self, key, value, *, skip_if_exists: bool = False) -> bool:
        if skip_if_exists and key in self._data:
            return False
        self._data[key] = value
        return True

    def _pop(self, key, default=None):
        return self._data.pop(key, default)


class _FakeSpawnFunction:
    def __init__(self):
        self.calls = []
        self.spawn = _AioBridge(self._spawn)

    def _spawn(self, *args, **kwargs):
        self.calls.append((args, kwargs))


_JOB_DICTS = ("paper_tokens_dict", "paper_jobs_dict", "paper_token_claims_dict", "paper_token_index_dict")


@pytest.fixture
def client(monkeypatch):
    import app as backend_app

    for name in _JOB_DICTS + ("customer_lifecycle_dict", "lifecycle_optout_dict", "referral_dict", "feedback_dict"):
        monkeypatch.setattr(backend_app, name, _FakeDict())
    monkeypatch.setattr(backend_app, "rate_dict", {})
    monkeypatch.setattr(backend_app, "paper_review_pipeline", _FakeSpawnFunction())
    monkeypatch.setattr(backend_app, "adjacent_tool_pipeline", _FakeSpawnFunction())
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return TestClient(backend_app.web.local()), backend_app


BODY_LINES = [
    "A Study of Imaginary Quantum Llamas in Deep Networks",
    "Jane Smith",
    "Department of Physics, Example University",
    "jane.smith@example.edu",
    "Abstract",
    "We study how imaginary quantum llamas change the training of deep networks.",
    "The results hold across four datasets and three random seeds in every case.",
    "1 Introduction",
    "In our previous work [2], we showed that llamas improve convergence by a wide margin.",
    "The present paper extends that analysis to larger models and longer schedules.",
    "Code is available at https://github.com/janesmith/llamas for inspection.",
    "Acknowledgments",
    "We thank the llama lab. This work was supported by NSF grant no. 1234567.",
]
REF_LINES = [
    "References",
    "[1] Vaswani, A. (2017). Attention is all you need. Advances in Neural Information Processing Systems.",
    "[2] Smith, J. (2020). Fabricated results in imaginary quantum llamas. Journal of Nothing.",
    "[3] Doe, J. (2019). A real paper about gravity waves. Physics Letters. doi:10.1000/real",
    "[4] Roe, R. (2018). Deep learning for protein folding. Nature Methods. doi:10.1000/wrong",
]


def _manuscript_pdf(author: str = "Jane Smith") -> bytes:
    buf = io.BytesIO()
    c = reportlab_canvas.Canvas(buf, pagesize=(1200, 792))
    if author:
        c.setAuthor(author)
    c.setFont("Helvetica", 10)
    for lines in (BODY_LINES, REF_LINES):
        y = 740
        for line in lines:
            c.drawString(40, y, line)
            y -= 22
        c.showPage()
    c.save()
    return buf.getvalue()


class _CrossRef:
    """httpx.MockTransport handler standing in for api.crossref.org and
    doi.org. Any other host fails the test: the preview must not talk to
    Anthropic or to a URL taken from the PDF."""

    def __init__(self):
        self.hosts = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        self.hosts.append(host)
        path = request.url.path
        if host == "doi.org":
            return httpx.Response(404)
        assert host == "api.crossref.org", f"unexpected host {host}"
        if path == "/works/10.1000/real":
            return httpx.Response(200, json={"message": {"title": ["A real paper about gravity waves"]}})
        if path == "/works/10.1000/wrong":
            return httpx.Response(200, json={"message": {"title": ["Zebra migration patterns across seasonal savanna corridors"]}})
        if path.startswith("/works/"):
            return httpx.Response(404)
        query = request.url.params.get("query.bibliographic", "").lower()
        if "attention" in query:
            return httpx.Response(200, json={"message": {"items": [{"title": ["Attention is all you need"], "DOI": "10.1/a"}]}})
        return httpx.Response(200, json={"message": {"items": []}})


@pytest.fixture
def crossref(monkeypatch):
    from latextools import preview
    handler = _CrossRef()
    real_make_client = preview.make_client

    def _make_client():
        real_make_client()   # keeps its side effect: httpx request logging off
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(preview, "make_client", _make_client)
    return handler


def _post(http, data: bytes, name: str = "paper.pdf"):
    return http.post("/paper-review/preview", files={"file": (name, io.BytesIO(data), "application/pdf")})


# ---------------------------------------------------------------------------
# /paper-review/preview
# ---------------------------------------------------------------------------

def test_preview_happy_path_counts_and_findings(client, crossref, monkeypatch):
    http, backend_app = client
    from latextools import papercheck

    async def _no_llm(*args, **kwargs):
        raise AssertionError("the free preview must not call Anthropic")

    monkeypatch.setattr(papercheck, "_anthropic_message", _no_llm)
    monkeypatch.setattr(papercheck, "_anthropic_message_once", _no_llm)

    r = _post(http, _manuscript_pdf())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["counts"]["references_found"] == 4
    assert body["counts"]["verified"] == 2
    assert body["counts"]["not_found"] == 1
    assert body["counts"]["doi_mismatches"] == 1
    assert body["counts"]["weak_matches"] == 0

    findings = body["findings"]
    assert 1 <= len(findings) <= 3
    assert all(f["quote"] for f in findings)
    assert findings[0]["type"] == "doi_mismatch"
    assert "protein folding" in findings[0]["quote"]
    assert "Zebra migration" in findings[0]["detail"]
    not_found = [f for f in findings if f["type"] == "reference_not_found"]
    assert not_found and "imaginary quantum llamas" in not_found[0]["quote"]
    anon = [f for f in findings if f["type"] == "anonymity"]
    assert len(anon) == 1 and anon[0]["quote"] == "Author: Jane Smith"
    # More anonymity leftovers exist than the one shown.
    assert body["more"]["anonymity"] >= 3
    assert body["counts"]["anonymity_leftovers"] == body["more"]["anonymity"] + 1
    assert set(body["more"]) == {"reference_not_found", "doi_mismatch", "dead_doi", "weak_match", "anonymity"}

    # Only CrossRef and doi.org were contacted.
    assert set(crossref.hosts) <= {"api.crossref.org", "doi.org"}
    assert "api.anthropic.com" not in crossref.hosts


def test_preview_writes_nothing_to_job_or_token_stores(client, crossref):
    http, backend_app = client
    assert _post(http, _manuscript_pdf()).status_code == 200
    for name in _JOB_DICTS:
        assert getattr(backend_app, name)._data == {}, name
    assert backend_app.paper_review_pipeline.calls == []
    assert backend_app.adjacent_tool_pipeline.calls == []
    # The only writes are rate counters: hashed keys, integer values.
    assert backend_app.rate_dict
    assert all(k.startswith("rl:paper-preview-") and isinstance(v, int)
               for k, v in backend_app.rate_dict.items())
    assert "llama" not in repr(backend_app.rate_dict).lower()


def test_preview_does_not_log_manuscript_text(client, crossref, caplog):
    http, _ = client
    with caplog.at_level("INFO"):
        assert _post(http, _manuscript_pdf()).status_code == 200
    assert any("paper preview:" in rec.getMessage() for rec in caplog.records)
    logged = " ".join(rec.getMessage() for rec in caplog.records).lower()
    for needle in ("llama", "jane", "smith", "example.edu", "vaswani"):
        assert needle not in logged


def test_preview_rejects_non_pdf(client, crossref):
    http, _ = client
    r = _post(http, b"PK\x03\x04 not a pdf at all", name="paper.pdf")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid"
    r = _post(http, _manuscript_pdf(), name="paper.docx")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid"
    assert crossref.hosts == []


def test_preview_rejects_oversize(client, crossref, monkeypatch):
    http, _ = client
    from latextools import core
    monkeypatch.setattr(core, "MAX_PAPER_UPLOAD_BYTES", 1024)
    r = _post(http, b"%PDF-1.4\n" + b"x" * 4096)
    assert r.status_code == 400
    assert r.json() == {"error": "invalid", "detail": "File is too large (max 20 MB)."}
    assert crossref.hosts == []


def test_preview_unreadable_pdf_is_a_clear_error(client, crossref):
    http, _ = client
    r = _post(http, b"%PDF-1.4\n%fake pdf content\n%%EOF")
    assert r.status_code == 422
    assert r.json()["error"] in ("unreadable", "failed")
    assert r.json()["detail"]


def test_preview_hourly_rate_limit(client, crossref):
    http, backend_app = client
    for _ in range(backend_app.PREVIEW_HOURLY_LIMIT):
        assert _post(http, b"not a pdf").status_code == 400
    r = _post(http, _manuscript_pdf())
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"
    assert "hour" in r.json()["detail"]
    assert crossref.hosts == []


def test_preview_daily_and_global_limits(client, crossref, monkeypatch):
    http, backend_app = client
    monkeypatch.setattr(backend_app, "PREVIEW_HOURLY_LIMIT", 100)
    monkeypatch.setattr(backend_app, "PREVIEW_DAILY_LIMIT", 2)
    for _ in range(2):
        assert _post(http, b"not a pdf").status_code == 400
    r = _post(http, b"not a pdf")
    assert r.status_code == 429 and "today" in r.json()["detail"]

    monkeypatch.setattr(backend_app, "PREVIEW_DAILY_LIMIT", 100)
    monkeypatch.setattr(backend_app, "PREVIEW_GLOBAL_DAILY_LIMIT", 2)
    r = _post(http, b"not a pdf")
    assert r.status_code == 429 and "everyone" in r.json()["detail"]


def test_preview_fails_closed_when_rate_store_is_down(client, crossref, monkeypatch):
    http, backend_app = client

    class _Down:
        def get(self, *a, **k):
            raise RuntimeError("modal dict unreachable")

    monkeypatch.setattr(backend_app, "rate_dict", _Down())
    r = _post(http, _manuscript_pdf())
    assert r.status_code == 503
    assert r.json()["error"] == "unavailable"
    assert crossref.hosts == []


def test_preview_cors_is_limited_to_purplelink(client):
    http, _ = client
    headers = {"Access-Control-Request-Method": "POST"}
    ok = http.options("/paper-review/preview", headers={**headers, "Origin": "https://purplelink.llc"})
    assert ok.headers.get("access-control-allow-origin") == "https://purplelink.llc"
    bad = http.options("/paper-review/preview", headers={**headers, "Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


# ---------------------------------------------------------------------------
# preview internals
# ---------------------------------------------------------------------------

def test_anonymity_scan_kinds_and_pages():
    from latextools import preview
    pages = [
        (1, "A Title\nDepartment of Physics, Example University\njane@example.edu\nAbstract\nText."),
        (3, "In our previous work [12], we showed X.\nOur earlier study was fine.\nAcknowledgments\nWe thank Bob.\n"
            "This research was funded by the ERC under grant agreement 99.\nSee github.com/jane/repo."),
    ]
    found = preview.anonymity_scan(pages, "Jane Smith")
    kinds = {f["kind"]: f for f in found}
    assert set(kinds) == {"metadata_author", "institution", "email", "self_citation",
                          "acknowledgments", "funding", "repository"}
    assert kinds["institution"]["page"] == 1
    assert kinds["email"]["quote"] == "jane@example.edu"
    assert kinds["self_citation"]["page"] == 3 and "[12]" in kinds["self_citation"]["quote"]
    # "Our earlier study" has no citation marker, so it is not flagged.
    assert sum(1 for f in found if f["kind"] == "self_citation") == 1


def test_anonymity_scan_clean_manuscript_and_generic_author():
    from latextools import preview
    assert preview.anonymity_scan([(1, "A Title\nAnonymous Authors\nAbstract\nPrior work [3] showed X.")], "") == []
    assert preview._metadata_author(_manuscript_pdf(author="Anonymous")) == ""
    assert preview._metadata_author(_manuscript_pdf(author="Jane Smith")) == "Jane Smith"
    assert preview._metadata_author(b"not a pdf") == ""


def test_title_in_reference_survives_pdf_text_damage():
    from latextools import preview
    title = "Attention is all you need"
    assert preview.title_in_reference(title, "Vaswani,A.(2017).Attentionisallyouneed.NeurIPS.") == 1.0
    assert preview.title_in_reference(title, "Vaswani (2017). Atten-\ntion is all you need.") == 1.0
    assert preview.title_in_reference(title, "Roe (2018). Deep learning for protein folding.") < 0.35


def test_body_pages_stop_at_reference_heading():
    from latextools import preview
    pages = [(1, "Intro text\nmore"), (2, "Discussion\nReferences\n[1] a@b.org cited"), (3, "[2] more refs")]
    body = preview._body_pages(pages)
    assert [p for p, _ in body] == [1, 2]
    assert "a@b.org" not in body[1][1]


def test_check_limits_and_increment_only_counts_allowed_requests():
    from latextools import core
    store = {}
    limits = [("h", 2), ("d", 3)]
    assert core.check_limits_and_increment(store, limits) is None
    assert core.check_limits_and_increment(store, limits) is None
    assert core.check_limits_and_increment(store, limits) == 0
    assert store == {"h": 2, "d": 2}   # the blocked call burned nothing
    assert core.check_and_increment({}, "k", limit=1) == (True, 0)
    assert core.check_and_increment({"k": 1}, "k", limit=1) == (False, 0)


# ---------------------------------------------------------------------------
# Report attached to the "review is ready" email
# ---------------------------------------------------------------------------

MANUSCRIPT_BYTES = b"%PDF-1.4\n%the manuscript itself\n%%EOF"
ANNOTATED_BYTES = b"%PDF-1.4\n%annotated copy holding the manuscript pages\n%%EOF"
REPORT_BYTES = b"%PDF-1.4\n%the review report\n%%EOF"
REPORT_MD = "# Review\n\nFinding one quotes the text."


def _run_pipeline(monkeypatch, final_extra: dict, *, rendered=None):
    import app as backend_app
    from latextools import delivery, papercheck, report_pdf

    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "referral_dict", _FakeDict())
    monkeypatch.setenv("SUBSCRIBE_SECRET", "test-secret")
    sent = {}

    async def _fake_run(pdf_bytes, domain, on_progress=None, **kwargs):
        return {"status": "done", "result_md": REPORT_MD,
                "annotated_pdf_b64": base64.b64encode(ANNOTATED_BYTES).decode(),
                "structure_summary": {"title": "A Great Paper"}, **final_extra}

    async def _capture(client, **kwargs):
        sent.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(papercheck, "run_review_pipeline", _fake_run)
    monkeypatch.setattr(delivery, "send_email", _capture)
    monkeypatch.setattr(report_pdf, "render_report_pdf", lambda md: rendered)
    backend_app.paper_review_pipeline.local(
        "tok-attach", MANUSCRIPT_BYTES, "general", tier="standard", deliver_email="buyer@example.com",
    )
    return sent


def _assert_never_the_manuscript(attachments):
    forbidden = {MANUSCRIPT_BYTES, ANNOTATED_BYTES}
    for att in attachments:
        raw = att["content"] if isinstance(att["content"], bytes) else base64.b64decode(att["content"])
        assert raw not in forbidden
        assert b"manuscript" not in raw


def test_ready_email_attaches_the_report_pdf_only(monkeypatch):
    sent = _run_pipeline(monkeypatch, {"result_pdf_b64": base64.b64encode(REPORT_BYTES).decode()})
    atts = sent["attachments"]
    # The PDF, then the Markdown the Revision Review tool asks for later.
    assert [a["filename"] for a in atts] == ["paper-review-report.pdf", "report.md"]
    assert base64.b64decode(atts[0]["content"]) == REPORT_BYTES
    _assert_never_the_manuscript(atts)
    assert sent["to"] == "buyer@example.com"
    assert "The report is attached." in sent["html"]
    assert "deleted 30 minutes after you first open the result, or after 24 hours." in " ".join(sent["html"].split())


def test_ready_email_renders_the_pdf_when_the_pipeline_has_none(monkeypatch):
    sent = _run_pipeline(monkeypatch, {}, rendered=REPORT_BYTES)
    atts = sent["attachments"]
    assert [a["filename"] for a in atts] == ["paper-review-report.pdf", "report.md"]
    assert base64.b64decode(atts[0]["content"]) == REPORT_BYTES
    _assert_never_the_manuscript(atts)


def test_ready_email_falls_back_to_markdown_report(monkeypatch):
    sent = _run_pipeline(monkeypatch, {"result_pdf_b64": None}, rendered=None)
    atts = sent["attachments"]
    assert [a["filename"] for a in atts] == ["report.md"]
    assert base64.b64decode(atts[0]["content"]).decode().startswith(REPORT_MD)
    _assert_never_the_manuscript(atts)
    assert "The report is attached." in sent["html"]


def test_ready_email_skips_an_oversize_attachment_and_says_so(monkeypatch):
    from latextools import delivery
    monkeypatch.setattr(delivery, "MAX_REPORT_ATTACHMENT_B64_BYTES", 8)
    sent = _run_pipeline(monkeypatch, {"result_pdf_b64": base64.b64encode(REPORT_BYTES).decode()})
    assert not sent["attachments"]
    assert "too large to attach" in sent["html"]
    assert "The report is attached." not in sent["html"]


def test_attachment_cap_is_under_resends_limit():
    from latextools import delivery
    assert delivery.RESEND_MAX_EMAIL_BYTES == 40 * 1024 * 1024
    assert delivery.MAX_REPORT_ATTACHMENT_B64_BYTES < delivery.RESEND_MAX_EMAIL_BYTES
    assert delivery.build_report_attachment() == ([], "none")


def test_adjacent_tool_ready_email_keeps_save_a_copy_wording():
    from latextools import delivery
    html = delivery.html_review_ready(status_url="https://x/s", amount_cents=200, product="cover-letter")
    assert "save a copy" in html
    assert "attached" not in html


def _seed_token(backend_app, token="tok-mail", session_id="sess-mail"):
    import time
    cfg = backend_app.PAID_PRODUCTS["paper-review-standard"]
    backend_app.paper_tokens_dict[session_id] = {
        "tokens": [token], "product_key": "paper-review-standard", "product_cfg": cfg,
        "email": "receipt@example.com", "amount_paid": cfg["amount"], "redeemed": False,
        "consumed_tokens": [], "created_at": time.time(), "expires_at": time.time() + 3600,
    }
    backend_app.paper_token_index_dict[token] = session_id
    return token


def test_submit_sends_report_to_stripe_receipt_address_by_default(client):
    http, backend_app = client
    token = _seed_token(backend_app)
    r = http.post("/paper-review/submit", data={"token": token},
                  files={"file": ("paper.pdf", io.BytesIO(MANUSCRIPT_BYTES), "application/pdf")})
    assert r.status_code == 200, r.text
    _, kwargs = backend_app.paper_review_pipeline.calls[0]
    assert kwargs["deliver_email"] == "receipt@example.com"


def test_submit_prefers_the_address_typed_at_upload(client):
    http, backend_app = client
    token = _seed_token(backend_app)
    r = http.post("/paper-review/submit", data={"token": token, "email": "other@example.org"},
                  files={"file": ("paper.pdf", io.BytesIO(MANUSCRIPT_BYTES), "application/pdf")})
    assert r.status_code == 200, r.text
    _, kwargs = backend_app.paper_review_pipeline.calls[0]
    assert kwargs["deliver_email"] == "other@example.org"


def test_pack_token_never_falls_back_to_the_buyers_address(client):
    """A PI buys a pack and hands tokens to students: a student's report must
    not be emailed to the PI unless the student typed an address."""
    import time
    http, backend_app = client
    cfg = backend_app.PAID_PRODUCTS["paper-review-pack-5"]
    backend_app.paper_tokens_dict["sess-pack"] = {
        "tokens": ["tok-p1", "tok-p2", "tok-p3", "tok-p4", "tok-p5"], "product_key": "paper-review-pack-5",
        "product_cfg": cfg, "email": "pi@example.edu", "amount_paid": cfg["amount"], "redeemed": False,
        "consumed_tokens": [], "created_at": time.time(), "expires_at": time.time() + 3600,
    }
    backend_app.paper_token_index_dict["tok-p1"] = "sess-pack"
    r = http.post("/paper-review/submit", data={"token": "tok-p1"},
                  files={"file": ("paper.pdf", io.BytesIO(MANUSCRIPT_BYTES), "application/pdf")})
    assert r.status_code == 200, r.text
    _, kwargs = backend_app.paper_review_pipeline.calls[-1]
    assert kwargs["deliver_email"] == ""


# ---------------------------------------------------------------------------
# report_pdf
# ---------------------------------------------------------------------------

def test_report_pdf_uses_gfm_and_no_shell_escape(monkeypatch):
    from latextools import report_pdf
    calls = []

    def _fake_run(cmd, cwd=None, **kwargs):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        with open(out, "wb") as fh:
            fh.write(REPORT_BYTES)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(report_pdf.subprocess, "run", _fake_run)
    assert report_pdf.render_report_pdf("# Hi \\input{/etc/passwd} $x$") == REPORT_BYTES
    cmd = calls[0]
    assert cmd[cmd.index("-f") + 1] == "gfm"
    assert "--pdf-engine-opt=-no-shell-escape" in cmd
    assert "--pdf-engine=xelatex" in cmd


def test_report_pdf_falls_back_then_gives_up(monkeypatch):
    from latextools import report_pdf
    engines = []

    def _fail(cmd, cwd=None, **kwargs):
        engines.append([c for c in cmd if c.startswith("--pdf-engine=")][0])
        return subprocess.CompletedProcess(cmd, 1, "", "boom")

    monkeypatch.setattr(report_pdf.subprocess, "run", _fail)
    assert report_pdf.render_report_pdf("# Hi \u03c7\u00b2 \u2265 3") is None
    assert engines == ["--pdf-engine=xelatex", "--pdf-engine=pdflatex"]
    assert report_pdf.render_report_pdf("") is None
    assert report_pdf._ascii_safe("\u03c7\u00b2 \u2265 3 \u4e2d") == "chi^2 >= 3 ?"

    def _missing(cmd, cwd=None, **kwargs):
        raise OSError("pandoc not installed")

    monkeypatch.setattr(report_pdf.subprocess, "run", _missing)
    assert report_pdf.render_report_pdf("# Hi") is None


def test_pick_leads_with_reference_problems_and_caps_anonymity_at_one():
    from latextools import preview
    refs = [{"type": "reference_not_found", "label": "r", "quote": f"ref {i}", "page": None, "detail": "", "_score": 50} for i in range(3)]
    anon = [{"type": "anonymity", "kind": "email", "label": "a", "quote": f"a{i}@x.edu", "page": 1, "detail": "", "_score": 99} for i in range(3)]
    shown = preview._pick(refs + anon)
    assert len(shown) == 3
    assert [f["type"] for f in shown].count("anonymity") == 1
    assert shown[0]["type"] != "anonymity"


def test_pick_shows_three_anonymity_items_when_references_are_clean():
    from latextools import preview
    anon = [{"type": "anonymity", "kind": "email", "label": "a", "quote": f"a{i}@x.edu", "page": 1, "detail": "", "_score": 60} for i in range(4)]
    assert len(preview._pick(anon)) == 3


def test_symbols_xelatex_would_drop_are_spelled_out():
    from latextools import report_pdf
    out = report_pdf._symbol_safe("p ≤ 0.05, n ≥ 24, x̄₁ − x̄₂, δ̂ ✓ ✗ ⚠ → ok")
    assert "p <= 0.05" in out and "n >= 24" in out
    assert "_1" in out and "_2" in out and "delta" in out
    assert "[ok]" in out and "[x]" in out and "[!]" in out
    assert "→" in out  # the arrow has a glyph and is left alone
