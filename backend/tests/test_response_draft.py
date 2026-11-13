"""Response letter drafting (latextools/response_draft.py) and its endpoint, plus the free Revision Review
that comes with a Deep Paper Review (2026-11-13)."""
import asyncio
import time

import pytest

from latextools import response_draft as rd
from latextools import upgrades
from latextools.papercheck import PaperStructure
from tests.test_app_paper_review_endpoints import PDF_BYTES, _FakeDict, client  # noqa: F401

ORIGINAL = ("We surveyed 120 managers about phishing. Trust is measured with five items. "
            "Results show that training reduces clicks.")
REVISED = ORIGINAL + " We now define trust as the willingness to rely on a sender without verifying it."
COMMENTS = "Reviewer 1\n1. The sample is small.\n2. Define trust.\n\nReviewer 2\n1. Cite Smith 2020."


# ---------------------------------------------------------------------------
# verify_item: the rule that no change is claimed unless the revised manuscript shows it
# ---------------------------------------------------------------------------

def _entry(**kw):
    base = {"id": "R1.2", "type": "clarification", "request": "Define trust",
            "passages": ["Trust is measured with five items"], "reply": "Thank you for this comment.",
            "changes": [{"description": "Added a definition of trust.",
                         "revised_quote": "We now define trust as the willingness to rely on a sender"}],
            "disagree": False}
    base.update(kw)
    return base


def test_change_found_only_in_revised_is_verified():
    out = rd.verify_item(_entry(), ORIGINAL, REVISED)
    assert out["changes"][0]["status"] == "verified"
    assert out["passages"] == ["Trust is measured with five items"]
    assert not out["reply"].startswith("[CHECK")


def test_change_without_revised_manuscript_is_a_placeholder():
    out = rd.verify_item(_entry(), ORIGINAL, None)
    assert out["changes"][0]["status"] == "no_revised_manuscript"
    line = rd._change_line(out["changes"][0])
    assert line.startswith("- [PLACEHOLDER:") and "now reads" not in line


def test_change_missing_from_revised_is_not_found():
    out = rd.verify_item(_entry(changes=[{"description": "Added power analysis.",
                                          "revised_quote": "A power analysis shows 120 is enough"}]),
                         ORIGINAL, REVISED)
    assert out["changes"][0]["status"] == "not_found"
    assert out["changes"][0]["quote"] == ""


def test_text_already_in_original_is_not_a_change():
    out = rd.verify_item(_entry(changes=[{"description": "Clarified the sample.",
                                          "revised_quote": "We surveyed 120 managers about phishing"}]),
                         ORIGINAL, REVISED)
    assert out["changes"][0]["status"] == "already_in_original"


def test_invented_passage_is_dropped():
    out = rd.verify_item(_entry(passages=["This sentence is not in the paper at all"]), ORIGINAL, REVISED)
    assert out["passages"] == []


def test_reply_that_claims_a_change_without_evidence_gets_check_marker():
    out = rd.verify_item(_entry(reply="We have added a definition of trust.", changes=[]), ORIGINAL, REVISED)
    assert out["reply"].startswith("[CHECK:")
    ok = rd.verify_item(_entry(reply="We have added a definition of trust."), ORIGINAL, REVISED)
    assert not ok["reply"].startswith("[CHECK")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _items():
    from latextools.response_review import parse_reviewer_block
    return rd.number_items(parse_reviewer_block(COMMENTS))


def test_numbering_is_reviewer_dot_comment():
    assert [it["id"] for it in _items()] == ["R1.1", "R1.2", "R2.1"]


def test_letter_has_every_comment_once_and_placeholders_for_gaps():
    items = _items()
    drafted = {"R1.2": rd.verify_item(_entry(), ORIGINAL, REVISED)}
    letter = rd.render_letter(items, drafted)
    for it in items:
        assert letter.count(f"**Comment {it['id']}.**") == 1
    assert letter.count("[PLACEHOLDER: not drafted.") == 2
    assert "now reads" in letter
    ledger = rd.render_ledger(items, drafted)
    assert ledger.count("\n| R") == 3


# ---------------------------------------------------------------------------
# End to end with a fake model
# ---------------------------------------------------------------------------

def _fake_pipeline(monkeypatch, *, answers, panel_fail=False):
    structures = {b"orig": PaperStructure(title="T", abstract="A", body=ORIGINAL),
                  b"rev": PaperStructure(title="T", abstract="A", body=REVISED)}
    monkeypatch.setattr(rd, "extract_paper", lambda data: structures[data])
    monkeypatch.setattr(rd, "_coherence_notes", lambda data: ("", []))
    calls = []

    async def fake_call(client, *, system, user_content, max_tokens, model):
        calls.append({"system": system, "user": user_content, "max_tokens": max_tokens})
        return answers, "ok"

    seen = {}

    async def fake_panel(client, structure, parsed, letter, *, persona_note="", on_panel_done=None):
        seen.update(structure=structure, letter=letter, note=persona_note)
        if panel_fail:
            raise rd.PanelSynthesisError("boom")
        return {"skeptical": [], "tone": [], "editor": [], "md": "# Response Letter Review\n\nPanel says fine.",
                "truncated": False}

    monkeypatch.setattr(rd, "_call_json_findings", fake_call)
    monkeypatch.setattr(rd, "run_panel_and_synthesis", fake_panel)
    return calls, seen


def test_run_with_revised_manuscript(monkeypatch):
    answers = [
        _entry(id="R1.1", reply="We agree the sample is modest. [PLACEHOLDER: add the power analysis.]",
               changes=[]),
        _entry(),
        _entry(id="R9.9"),                      # not asked for: dropped
        _entry(id="R1.2", reply="duplicate"),   # repeated: first wins
    ]
    calls, seen = _fake_pipeline(monkeypatch, answers=answers)
    stages = []
    out = asyncio.run(rd.run_response_draft(b"orig", COMMENTS, "We added a definition.", revised_pdf_bytes=b"rev",
                                            on_progress=lambda p: stages.append(p.stage)))
    assert out["status"] == "done"
    assert out["items_parsed"] == 3 and out["items_drafted"] == 2 and out["changes_verified"] == 1
    md = out["result_md"]
    assert md.startswith("# Response Letter Draft")
    assert "This is a draft for you to edit" in md
    assert "duplicate" not in md and "R9.9" not in md
    assert md.count("**Comment R2.1.**") == 1 and "[PLACEHOLDER: not drafted." in md
    assert "Panel says fine." in md
    assert seen["structure"].body == REVISED and seen["note"] == rd.PANEL_DRAFT_NOTE
    assert stages[0] == "extracting" and stages[-1] == "done"
    assert len(calls) == 1 and calls[0]["system"] == rd._DRAFT_SYSTEM


def test_run_without_revised_manuscript_claims_no_change(monkeypatch):
    _fake_pipeline(monkeypatch, answers=[_entry(), _entry(id="R1.1", changes=[])])
    out = asyncio.run(rd.run_response_draft(b"orig", COMMENTS))
    assert out["status"] == "done" and out["changes_verified"] == 0
    assert "now reads" not in out["result_md"]
    assert "No revised manuscript was uploaded" in out["result_md"]


def test_panel_failure_still_delivers_the_draft(monkeypatch):
    _fake_pipeline(monkeypatch, answers=[_entry()], panel_fail=True)
    out = asyncio.run(rd.run_response_draft(b"orig", COMMENTS, revised_pdf_bytes=b"rev"))
    assert out["status"] == "done"
    assert "could not be completed" in out["result_md"] and "## Draft letter" in out["result_md"]


def test_no_drafts_back_is_an_error(monkeypatch):
    _fake_pipeline(monkeypatch, answers=[])
    out = asyncio.run(rd.run_response_draft(b"orig", COMMENTS))
    assert out == {"status": "error", "error": "drafting_failed"}


def test_unparseable_comments_is_an_error(monkeypatch):
    _fake_pipeline(monkeypatch, answers=[])
    out = asyncio.run(rd.run_response_draft(b"orig", "   "))
    assert out["error"] == "no_reviewer_comments_parsed"


def test_long_letters_are_split_into_batches(monkeypatch):
    many = "Reviewer 1\n" + "\n".join(f"{i}. Comment number {i} asks for more detail." for i in range(1, 24))
    calls, _ = _fake_pipeline(monkeypatch, answers=[_entry(id="R1.1")])
    monkeypatch.setattr(rd, "estimate_input_tokens", lambda *a, **k: 0)   # skip the cache prewarm
    asyncio.run(rd.run_response_draft(b"orig", many))
    assert len(calls) == 3


# ---------------------------------------------------------------------------
# Cost: one run must stay well under the $24 price, and the pipeline enforces the ceiling
# ---------------------------------------------------------------------------

def test_worst_case_cost_is_well_under_price():
    assert rd.worst_case_cost_usd() < 24 * 0.6
    assert rd.typical_cost_usd() < 3


def test_order_ceiling_for_response_draft_is_the_price(monkeypatch):
    import app as backend_app
    assert backend_app.PAID_PRODUCTS["response-draft"]["amount"] == 2400
    monkeypatch.delenv("ORDER_COST_CEILING_FACTOR", raising=False)
    assert backend_app._order_cost_ceiling("response-draft") == pytest.approx(24.0)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def _register(backend_app, product_key, session_id):
    cfg = backend_app.PAID_PRODUCTS[product_key]
    token = "tok-" + session_id
    backend_app.paper_tokens_dict[session_id] = {
        "tokens": [token], "product_key": product_key, "product_cfg": cfg, "email": "buyer@example.com",
        "amount_paid": cfg["amount"], "redeemed": False, "consumed_tokens": [], "created_at": time.time(),
        "expires_at": time.time() + 7 * 86400,
    }
    backend_app.paper_token_index_dict[token] = session_id
    return token


def _post_draft(http, token, *, revised=True):
    files = {"file": ("paper.pdf", PDF_BYTES, "application/pdf")}
    if revised:
        files["revised_file"] = ("revised.pdf", PDF_BYTES, "application/pdf")
    return http.post("/response-review/draft/submit", files=files,
                     data={"token": token, "reviewer_comments": COMMENTS, "author_notes": "notes"})


def test_draft_submit_spawns_with_both_files(client):  # noqa: F811
    http, backend_app = client
    token = _register(backend_app, "response-draft", "s-draft")
    r = _post_draft(http, token)
    assert r.status_code == 200, r.text
    (args, kwargs), = backend_app.adjacent_tool_pipeline.calls
    assert "response-draft" in args or kwargs.get("product") == "response-draft"
    assert kwargs["revised_pdf_bytes"] == PDF_BYTES and kwargs["author_notes"] == "notes"


def test_draft_submit_revised_file_is_optional(client):  # noqa: F811
    http, backend_app = client
    token = _register(backend_app, "response-draft", "s-draft-norev")
    r = _post_draft(http, token, revised=False)
    assert r.status_code == 200, r.text
    (_, kwargs), = backend_app.adjacent_tool_pipeline.calls
    assert kwargs["revised_pdf_bytes"] == b""


def test_critique_token_cannot_start_a_draft(client):  # noqa: F811
    http, backend_app = client
    token = _register(backend_app, "response-review", "s-critique")
    r = _post_draft(http, token)
    assert r.status_code == 400 and r.json()["error"] == "wrong_product"
    assert backend_app.adjacent_tool_pipeline.calls == []


def test_draft_token_cannot_start_a_critique(client):  # noqa: F811
    http, backend_app = client
    token = _register(backend_app, "response-draft", "s-draft-2")
    r = http.post("/response-review/submit", files={"file": ("p.pdf", PDF_BYTES, "application/pdf")},
                  data={"token": token, "reviewer_comments": COMMENTS, "author_response": "x"})
    assert r.status_code == 400 and r.json()["error"] == "wrong_product"


def test_draft_submit_unknown_token(client):  # noqa: F811
    http, _ = client
    assert _post_draft(http, "nope").json()["error"] == "unknown_token"


def test_draft_submit_rejects_non_pdf_revised(client):  # noqa: F811
    http, backend_app = client
    token = _register(backend_app, "response-draft", "s-draft-bad")
    r = http.post("/response-review/draft/submit",
                  files={"file": ("paper.pdf", PDF_BYTES, "application/pdf"),
                         "revised_file": ("revised.pdf", b"not a pdf", "application/pdf")},
                  data={"token": token, "reviewer_comments": COMMENTS})
    assert r.status_code == 400
    assert backend_app.adjacent_tool_pipeline.calls == []


def test_ready_email_knows_the_draft():
    from latextools import delivery
    assert "response-draft" in delivery._READY_NAMES and "response-draft" in delivery._READY_NEXT


# ---------------------------------------------------------------------------
# Free Revision Review after a Deep review
# ---------------------------------------------------------------------------

DAY = 86400


def test_eligibility_rules():
    now = 1_000_000_000.0
    rows = [
        {"session": "deep-new", "product": "paper-review-deep", "amount_paid": 1500, "at": now - 2 * DAY},
        {"session": "deep-old", "product": "paper-review-deep", "amount_paid": 1500, "at": now - 31 * DAY},
        {"session": "deep-free", "product": "paper-review-deep", "amount_paid": 0, "at": now - DAY},
        {"session": "std", "product": "paper-review-standard", "amount_paid": 900, "at": now - DAY},
        {"session": "deep-mid", "product": "paper-review-deep", "amount_paid": 1500, "at": now - 10 * DAY},
    ]
    assert upgrades.free_revision_sessions(rows, now) == ["deep-new", "deep-mid"]


def test_one_claim_per_deep_purchase():
    now = 1_000_000_000.0
    store = _FakeDict()
    rows = [{"session": "d1", "product": "paper-review-deep", "amount_paid": 1500, "at": now - DAY}]
    assert upgrades.claim_free_revision(store, rows, now, {"at": now}) == "d1"
    assert upgrades.claim_free_revision(store, rows, now, {"at": now}) is None


def _seed_deep(backend_app, email, *, days_ago=1, session="cs_deep_1", amount=1500):
    from latextools import buddy
    at = time.time() - days_ago * DAY
    backend_app.review_spend_dict[buddy.canonical_email(email)] = {"purchases": [
        {"session": session, "product": "paper-review-deep", "amount_paid": amount, "at": at}]}
    backend_app.paper_tokens_dict[session] = {"email": email, "product_key": "paper-review-deep"}


@pytest.fixture
def sent(monkeypatch):
    from latextools import delivery
    out = []

    async def fake_send(client, **kw):
        out.append(kw)
        return {"status": "ok"}

    monkeypatch.setattr(delivery, "send_email", fake_send)
    return out


def test_free_claim_emails_a_link_and_never_returns_the_token(client, sent):  # noqa: F811
    http, backend_app = client
    _seed_deep(backend_app, "first.last@gmail.com")
    r = http.post("/revision-review/free-claim", json={"email": "FirstLast+x@gmail.com"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert "tok" not in r.text.lower()
    assert len(sent) == 1 and sent[0]["to"] == "first.last@gmail.com"
    free = [(k, v) for k, v in backend_app.paper_tokens_dict.items() if k.startswith("deep-free-revision:")]
    assert len(free) == 1
    sid, entry = free[0]
    assert entry["amount_paid"] == 0 and entry["product_cfg"]["category"] == "revision-review"
    assert entry["source"] == "deep-free-revision" and entry["deep_session"] == "cs_deep_1"
    assert entry["expires_at"] > time.time() + 28 * DAY   # Deep bought 1 day ago: link lasts to day 30
    assert backend_app.paper_token_index_dict[entry["tokens"][0]] == sid
    assert "/tools/paper-review/revision/upload/?session_id=" in sent[0]["html"]
    assert "within 7 days" not in sent[0]["html"] and ", until " in sent[0]["html"]
    # Second claim for the same Deep purchase: same generic answer, no second email, no second token.
    r2 = http.post("/revision-review/free-claim", json={"email": "first.last@gmail.com"})
    assert r2.json() == r.json() and len(sent) == 1


@pytest.mark.parametrize("days_ago,amount", [(31, 1500), (1, 0)])
def test_free_claim_ineligible_gets_same_answer_and_no_email(client, sent, days_ago, amount):  # noqa: F811
    http, backend_app = client
    _seed_deep(backend_app, "a@example.com", days_ago=days_ago, amount=amount)
    r = http.post("/revision-review/free-claim", json={"email": "a@example.com"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert sent == []
    assert not any(k.startswith("deep-free-revision:") for k, _ in backend_app.paper_tokens_dict.items())


def test_free_claim_standard_only_is_ineligible(client, sent):  # noqa: F811
    http, backend_app = client
    from latextools import buddy
    backend_app.review_spend_dict[buddy.canonical_email("s@example.com")] = {"purchases": [
        {"session": "cs_std", "product": "paper-review-standard", "amount_paid": 900, "at": time.time()}]}
    http.post("/revision-review/free-claim", json={"email": "s@example.com"})
    assert sent == []


def test_free_claim_failed_email_releases_the_claim(client, monkeypatch):  # noqa: F811
    http, backend_app = client
    from latextools import delivery
    _seed_deep(backend_app, "b@example.com")

    async def fail(client, **kw):
        return {"status": "error"}

    monkeypatch.setattr(delivery, "send_email", fail)
    r = http.post("/revision-review/free-claim", json={"email": "b@example.com"})
    assert r.status_code == 502
    assert not any(k.startswith("deep-free-revision:") for k, _ in backend_app.paper_tokens_dict.items())
    assert backend_app.review_spend_dict.get("free-revision:cs_deep_1") is None


def test_free_claim_rejects_bad_email(client, sent):  # noqa: F811
    http, _ = client
    assert http.post("/revision-review/free-claim", json={"email": "nope"}).status_code == 400


def test_free_revision_is_not_sent_a_still_waiting_reminder():
    import app as backend_app
    now = time.time()
    entry = {"email": "a@example.com", "source": "deep-free-revision", "created_at": now - 3 * DAY,
             "expires_at": now + 4 * DAY, "consumed_tokens": []}
    assert backend_app._purchases_waiting([("deep-free-revision:x", entry)], now) == []


# ---------------------------------------------------------------------------
# The real adjacent_tool_pipeline body for response-draft (run with .local(), model calls faked)
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline_app(monkeypatch):
    import app as backend_app
    for name in ("paper_jobs_dict", "paper_tokens_dict", "paper_token_index_dict", "usage_ledger_dict"):
        monkeypatch.setattr(backend_app, name, _FakeDict())
    token = "tok-pipe"
    backend_app.paper_tokens_dict["s-pipe"] = {
        "tokens": [token], "product_key": "response-draft",
        "product_cfg": backend_app.PAID_PRODUCTS["response-draft"], "email": "buyer@example.com",
        "amount_paid": 2400, "redeemed": True, "consumed_tokens": [token], "created_at": time.time(),
        "expires_at": time.time() + 7 * DAY,
    }
    backend_app.paper_token_index_dict[token] = "s-pipe"
    return backend_app, token


def _run_pipeline(backend_app, token):
    backend_app.adjacent_tool_pipeline.local(
        token, "response-draft", pdf_bytes=PDF_BYTES, revised_pdf_bytes=PDF_BYTES,
        reviewer_comments=COMMENTS, author_notes="n", deliver_email="buyer@example.com")
    return backend_app.paper_jobs_dict.get(token)


def test_pipeline_done_stores_result_and_emails(pipeline_app, sent, monkeypatch):
    backend_app, token = pipeline_app
    seen = {}

    async def fake_run(pdf, comments, notes="", *, revised_pdf_bytes=None, on_progress=None):
        seen.update(revised=revised_pdf_bytes, comments=comments, notes=notes)
        return {"status": "done", "result_md": "# Response Letter Draft\n\nok", "progress_pct": 100}

    monkeypatch.setattr(rd, "run_response_draft", fake_run)
    job = _run_pipeline(backend_app, token)
    assert job["status"] == "done" and job["product"] == "response-draft"
    assert job["result_md"].startswith("# Response Letter Draft")
    assert seen == {"revised": PDF_BYTES, "comments": COMMENTS, "notes": "n"}
    assert len(sent) == 1 and "response letter draft" in sent[0]["subject"]
    assert "replacement_token" not in job


def test_pipeline_soft_error_reissues_the_token(pipeline_app, sent, monkeypatch):
    backend_app, token = pipeline_app

    async def fake_run(*a, **k):
        return {"status": "error", "error": "drafting_failed"}

    monkeypatch.setattr(rd, "run_response_draft", fake_run)
    job = _run_pipeline(backend_app, token)
    assert job["status"] == "error" and job["replacement_token"]
    assert job["replacement_token"] in backend_app.paper_tokens_dict["s-pipe"]["tokens"]


def test_pipeline_cost_ceiling_ends_in_a_reissued_token(pipeline_app, sent, monkeypatch):
    backend_app, token = pipeline_app
    from latextools import papercheck

    async def fake_run(*a, **k):
        raise papercheck.CostCeilingExceeded("over the order ceiling")

    monkeypatch.setattr(rd, "run_response_draft", fake_run)
    job = _run_pipeline(backend_app, token)
    assert job["status"] == "error" and job["error"] == "pipeline_failed" and job["replacement_token"]
    assert "ceiling" not in job["error"]


def test_free_claim_after_a_real_deep_registration(client, sent, monkeypatch):  # noqa: F811
    """No hand-seeded spend row: register-token writes it, the claim reads it."""
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    r = http.post("/paper-review/register-token", headers={"x-webhook-secret": "correct-secret"},
                  json={"session_id": "cs_real_deep", "product": "paper-review-deep", "email": "Real.Buyer@example.com",
                        "amount_paid": backend_app.PAID_PRODUCTS["paper-review-deep"]["amount"]})
    assert r.status_code == 200, r.text
    sent.clear()   # the purchase email
    r = http.post("/revision-review/free-claim", json={"email": "real.buyer@example.com"})
    assert r.status_code == 200
    assert len(sent) == 1 and sent[0]["to"] == "Real.Buyer@example.com"
