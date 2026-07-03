"""Regression coverage for `_reissue_token_on_failure` in backend/app.py.

Charged-without-result gap: `_consume_token` marks a token spent as soon as
`.spawn()` for the pipeline succeeds (see `paper_review_submit` /
`_start_adjacent` in app.py). If the pipeline body itself later raises
(LLM/API outage, PDF parse crash, timeout), the token stays spent and the
job's status becomes "error" — previously with no way back in except
emailing support. `_reissue_token_on_failure` mints a fresh, unconsumed
token and registers it under the same session so the customer can retry
without paying again; both pipeline except-blocks call it and stash the
result on the job dict as `replacement_token`, which `/paper-review/status`
also surfaces.

Unlike test_app_paper_review_endpoints.py, `_reissue_token_on_failure` is a
plain module-level function (not a closure inside `web()`), so it can be
imported and exercised directly against fake Dicts without building the
FastAPI app.
"""

import time

import pytest


class _FakeDict:
    """Same minimal in-memory stand-in used by
    test_app_paper_review_endpoints.py — supports the subset of modal.Dict's
    interface `_reissue_token_on_failure` and `_lookup_token`-style helpers
    use: `.get`, `__getitem__`/`__setitem__`, `.items()`."""

    def __init__(self):
        self._data = {}

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


@pytest.fixture
def backend_app(monkeypatch):
    import app as backend_app

    monkeypatch.setattr(backend_app, "paper_tokens_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "paper_token_index_dict", _FakeDict())
    return backend_app


def _seed(backend_app, *, session_id="sess-1", token="tok-original", consumed=None):
    entry = {
        "tokens": [token],
        "product_key": "paper-review-standard",
        "product_cfg": backend_app.PAID_PRODUCTS["paper-review-standard"],
        "email": "buyer@example.com",
        "amount_paid": 900,
        "redeemed": True,
        "consumed_tokens": consumed or [token],
        "created_at": time.time(),
        "expires_at": time.time() + 7 * 24 * 3600,
    }
    backend_app.paper_tokens_dict[session_id] = entry
    backend_app.paper_token_index_dict[token] = session_id
    return entry


def test_reissues_a_new_token_distinct_from_original(backend_app):
    _seed(backend_app)
    new_token = backend_app._reissue_token_on_failure("tok-original")

    assert new_token is not None
    assert new_token != "tok-original"


def test_new_token_is_registered_and_redeemable(backend_app):
    _seed(backend_app)
    new_token = backend_app._reissue_token_on_failure("tok-original")

    entry = backend_app.paper_tokens_dict["sess-1"]
    assert new_token in entry["tokens"]
    # Crucially: NOT in consumed_tokens, so /paper-review/submit will accept it.
    assert new_token not in (entry.get("consumed_tokens") or [])
    # Reverse index updated so _lookup_token(new_token) resolves it in O(1).
    assert backend_app.paper_token_index_dict.get(new_token) == "sess-1"


def test_original_consumed_token_is_left_untouched(backend_app):
    entry = _seed(backend_app)
    backend_app._reissue_token_on_failure("tok-original")

    updated = backend_app.paper_tokens_dict["sess-1"]
    assert "tok-original" in updated["tokens"]
    assert "tok-original" in updated["consumed_tokens"]


def test_unknown_token_returns_none_without_raising(backend_app):
    # No session seeded at all — simulates a token whose session record was
    # already purged (e.g. expired sweep) by the time the pipeline crashes.
    assert backend_app._reissue_token_on_failure("tok-does-not-exist") is None


def test_falls_back_to_linear_scan_when_index_missing(backend_app):
    """Mirrors _lookup_token's own fallback: older entries registered before
    the reverse index existed should still resolve via a full scan of
    paper_tokens_dict."""
    _seed(backend_app)
    # Simulate a missing/stale reverse-index entry.
    del backend_app.paper_token_index_dict["tok-original"]

    new_token = backend_app._reissue_token_on_failure("tok-original")

    assert new_token is not None
    assert new_token in backend_app.paper_tokens_dict["sess-1"]["tokens"]


def test_dict_failure_is_swallowed_and_returns_none(backend_app, monkeypatch):
    """Reissue must never raise out of a pipeline's except-block — a
    secondary failure here must not mask or replace the original error
    status already being written for the job."""
    _seed(backend_app)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("modal control-plane hiccup")

    monkeypatch.setattr(backend_app.paper_token_index_dict, "get", _boom)

    assert backend_app._reissue_token_on_failure("tok-original") is None


# ---------------------------------------------------------------------------
# End-to-end through the real pipeline bodies (not just the helper in
# isolation): a mid-pipeline crash after the token was already consumed by
# /submit must land a `replacement_token` on the job's error entry.
# Mirrors the `.local()` pattern used by the email-failure tests in
# test_app_paper_review_endpoints.py.
# ---------------------------------------------------------------------------

PDF_BYTES = b"%PDF-1.4\n%fake pdf content for tests\n%%EOF"


def test_paper_review_pipeline_crash_reissues_token(backend_app, monkeypatch):
    from latextools import papercheck

    def _boom_run_review_pipeline(*args, **kwargs):
        # Mirrors the real leak vector: httpx.HTTPStatusError.__str__()
        # embeds the upstream request URL and raw vendor error body.
        raise RuntimeError(
            "Server error '529 ' for url 'https://api.anthropic.com/v1/messages'\n"
            "For more information check: https://httpstatuses.com/529"
        )

    monkeypatch.setattr(papercheck, "run_review_pipeline", _boom_run_review_pipeline)
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    _seed(backend_app, session_id="sess-crash", token="tok-crash")

    backend_app.paper_review_pipeline.local(
        "tok-crash", PDF_BYTES, "cs", tier="standard",
    )

    entry = backend_app.paper_jobs_dict.get("tok-crash")
    assert entry is not None
    assert entry["status"] == "error"
    replacement = entry.get("replacement_token")
    assert replacement is not None
    assert replacement != "tok-crash"

    # The replacement must actually be redeemable: registered, not consumed.
    session_entry = backend_app.paper_tokens_dict["sess-crash"]
    assert replacement in session_entry["tokens"]
    assert replacement not in (session_entry.get("consumed_tokens") or [])

    # Regression: the raw exception text (upstream URL, vendor error body,
    # class name) must never be stored in the job's "error" field, since
    # /paper-review/status returns that field verbatim to any token holder.
    error_value = entry.get("error")
    assert error_value == "pipeline_failed"
    assert "anthropic.com" not in error_value
    assert "RuntimeError" not in error_value
    assert "529" not in error_value


def test_adjacent_tool_pipeline_crash_reissues_token(backend_app, monkeypatch):
    from latextools import papercheck

    def _boom_extract_paper(*args, **kwargs):
        # Includes a plausible internal file path to make sure that kind of
        # detail doesn't leak either.
        raise RuntimeError("PDF parse crash at /tmp/tmpABC123/input.pdf")

    monkeypatch.setattr(papercheck, "extract_paper", _boom_extract_paper)
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    _seed(backend_app, session_id="sess-crash-2", token="tok-crash-2")

    backend_app.adjacent_tool_pipeline.local(
        "tok-crash-2", "anonymity-check", pdf_bytes=PDF_BYTES,
    )

    entry = backend_app.paper_jobs_dict.get("tok-crash-2")
    assert entry is not None
    assert entry["status"] == "error"
    replacement = entry.get("replacement_token")
    assert replacement is not None
    assert replacement != "tok-crash-2"

    session_entry = backend_app.paper_tokens_dict["sess-crash-2"]
    assert replacement in session_entry["tokens"]
    assert replacement not in (session_entry.get("consumed_tokens") or [])

    # Regression: same leak vector as the paper-review pipeline above, but
    # through /score/status's shared code path (adjacent_tool_pipeline).
    error_value = entry.get("error")
    assert error_value == "pipeline_failed"
    assert "/tmp/" not in error_value
    assert "RuntimeError" not in error_value


# ---------------------------------------------------------------------------
# Soft-error path: run_review_pipeline / run_aiscore / paperreview_extras can
# all return a normal dict with status="error" (extraction_failed,
# empty_manuscript, L4-synthesis-failure, analysis_failed) WITHOUT raising.
# Before this fix, only the except-Exception crash path reissued a token;
# a customer hitting one of these soft failures got a spent token and no
# result, with no replacement_token surfaced by /paper-review/status.
# ---------------------------------------------------------------------------

def test_paper_review_pipeline_soft_error_reissues_token(backend_app, monkeypatch):
    """run_review_pipeline returns normally with status="error" (e.g.
    extraction_failed) -- no exception raised -- and a replacement token
    must still be minted."""
    from latextools import papercheck

    async def _soft_error_run_review_pipeline(*args, **kwargs):
        return {
            "status": "error",
            "error": "extraction_failed: ValueError",
            "result_md": None,
            "finished_at": time.time(),
        }

    monkeypatch.setattr(papercheck, "run_review_pipeline", _soft_error_run_review_pipeline)
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    _seed(backend_app, session_id="sess-soft", token="tok-soft")

    backend_app.paper_review_pipeline.local(
        "tok-soft", PDF_BYTES, "cs", tier="standard",
    )

    entry = backend_app.paper_jobs_dict.get("tok-soft")
    assert entry is not None
    assert entry["status"] == "error"
    replacement = entry.get("replacement_token")
    assert replacement is not None
    assert replacement != "tok-soft"

    session_entry = backend_app.paper_tokens_dict["sess-soft"]
    assert replacement in session_entry["tokens"]
    assert replacement not in (session_entry.get("consumed_tokens") or [])


def test_paper_review_pipeline_done_does_not_reissue_token(backend_app, monkeypatch):
    """Sanity check: a normal successful run must NOT mint a replacement
    token (would otherwise let customers double-dip on a single payment)."""
    from latextools import papercheck

    async def _ok_run_review_pipeline(*args, **kwargs):
        return {
            "status": "done",
            "result_md": "# Review\n\nLooks good.",
            "finished_at": time.time(),
        }

    monkeypatch.setattr(papercheck, "run_review_pipeline", _ok_run_review_pipeline)
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    _seed(backend_app, session_id="sess-ok", token="tok-ok")

    backend_app.paper_review_pipeline.local(
        "tok-ok", PDF_BYTES, "cs", tier="standard",
    )

    entry = backend_app.paper_jobs_dict.get("tok-ok")
    assert entry is not None
    assert entry["status"] == "done"
    assert entry.get("replacement_token") is None

    session_entry = backend_app.paper_tokens_dict["sess-ok"]
    assert session_entry["tokens"] == ["tok-ok"]


def test_adjacent_tool_pipeline_soft_error_reissues_token(backend_app, monkeypatch):
    """anonymity-check runs to completion but paperreview_extras reports
    status != "ok" (e.g. LLM returned unparseable JSON) -- no exception --
    and a replacement token must still be minted."""
    from latextools import papercheck, paperreview_extras

    monkeypatch.setattr(papercheck, "extract_paper", lambda *a, **k: papercheck.PaperStructure())

    async def _failed_anonymity_check(*args, **kwargs):
        return {"status": "error", "leaks": []}

    monkeypatch.setattr(paperreview_extras, "run_anonymity_check", _failed_anonymity_check)
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    _seed(backend_app, session_id="sess-soft-2", token="tok-soft-2")

    backend_app.adjacent_tool_pipeline.local(
        "tok-soft-2", "anonymity-check", pdf_bytes=PDF_BYTES,
    )

    entry = backend_app.paper_jobs_dict.get("tok-soft-2")
    assert entry is not None
    assert entry["status"] == "error"
    replacement = entry.get("replacement_token")
    assert replacement is not None
    assert replacement != "tok-soft-2"

    session_entry = backend_app.paper_tokens_dict["sess-soft-2"]
    assert replacement in session_entry["tokens"]
    assert replacement not in (session_entry.get("consumed_tokens") or [])
