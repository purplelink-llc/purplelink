"""HTTP-level coverage for the /paper-review/* token + billing endpoints
in backend/app.py: register-token, redeem-session, submit, and status.

backend/app.py's routes are closures inside a `@modal.asgi_app()` function
(`web()`), and the module wires several `modal.Dict.from_name(...)` stores
at import time. Those Dicts are lazily hydrated: constructing them is free,
but the first `.get`/`.put`/`[]` on one makes a real network call to
Modal's control plane against whatever credentials are active in
`~/.modal.toml` (including on a dev machine that has a *live* Modal
account, i.e. the same named Dicts used in production). We must not let
tests touch that.

Instead: `modal.Function.local()` runs the decorated function body directly
in-process without deploying/needing Modal auth, so `app.web.local()` hands
back the real FastAPI app with all the real route logic. We monkeypatch the
four module-level `modal.Dict`/`modal.Function` handles the routes close
over (`paper_tokens_dict`, `paper_jobs_dict`, `paper_token_claims_dict`,
`rate_dict`, plus the `.spawn()` entry points on the pipeline functions)
with hermetic in-memory fakes before building the app, so every request
exercises the actual endpoint code with zero network calls.

This covers exactly the security/billing-relevant paths called out as
untested: token expiry, wrong-product rejection, already_used / double
redemption, and malformed request bodies.
"""

import io
import time

import pytest
from fastapi.testclient import TestClient


class _AioBridge:
    """Wraps a sync callable so `<callable>.aio(...)` awaits it, mirroring
    the real Modal client shape where `.get`/`.put`/`.pop`/`.spawn` each
    carry an `.aio` attribute for the async variant."""

    def __init__(self, fn):
        self._fn = fn

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)

    async def aio(self, *args, **kwargs):
        return self._fn(*args, **kwargs)


class _FakeDict:
    """In-memory stand-in for modal.Dict with the subset of the interface
    app.py's routes use: `.get(key, default)`, `__getitem__`, `__setitem__`,
    `__delitem__`, `.items()`, the atomic `.put(key, val,
    skip_if_exists=True)` used by `_claim_token`, `.pop(key)`, and the
    `.put.aio` / `.pop.aio` async variants used by the async request
    handlers."""

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


class _FakeSpawnResult:
    object_id = "fake-call-id"


class _FakeSpawnFunction:
    """Stand-in for a modal.Function; records calls to `.spawn()` instead
    of dispatching a real remote container. Exposes `.spawn.aio` too, since
    the async request handlers call the async variant."""

    def __init__(self):
        self.calls = []
        self.spawn = _AioBridge(self._spawn)

    def _spawn(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _FakeSpawnResult()


@pytest.fixture
def client(monkeypatch):
    import app as backend_app

    monkeypatch.setattr(backend_app, "paper_tokens_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "paper_token_claims_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "paper_token_index_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "rate_dict", {})
    monkeypatch.setattr(backend_app, "customer_lifecycle_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "lifecycle_optout_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "referral_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "paper_review_pipeline", _FakeSpawnFunction())
    monkeypatch.setattr(backend_app, "adjacent_tool_pipeline", _FakeSpawnFunction())

    fastapi_app = backend_app.web.local()
    return TestClient(fastapi_app), backend_app


def _register(backend_app, *, product_key="paper-review-standard", session_id="sess-1"):
    """Directly seed a paper_tokens_dict entry the way register-token would,
    bypassing the webhook-secret auth (that auth path itself is trivial and
    not the focus of this coverage)."""
    product_cfg = backend_app.PAID_PRODUCTS[product_key]
    token = "tok-" + session_id
    entry = {
        "tokens": [token],
        "product_key": product_key,
        "product_cfg": product_cfg,
        "email": "buyer@example.com",
        "amount_paid": product_cfg.get("amount", 0),
        "redeemed": False,
        "consumed_tokens": [],
        "created_at": time.time(),
        "expires_at": time.time() + 7 * 24 * 3600,
    }
    backend_app.paper_tokens_dict[session_id] = entry
    return token


PDF_BYTES = b"%PDF-1.4\n%fake pdf content for tests\n%%EOF"


# ---------------------------------------------------------------------------
# register-token
# ---------------------------------------------------------------------------

def test_register_token_requires_webhook_secret(client, monkeypatch):
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    r = http.post(
        "/paper-review/register-token",
        json={"session_id": "s1", "product": "paper-review-standard"},
        headers={"x-webhook-secret": "wrong-secret"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"


def test_register_token_rejects_unknown_product(client, monkeypatch):
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    r = http.post(
        "/paper-review/register-token",
        json={"session_id": "s1", "product": "not-a-real-product"},
        headers={"x-webhook-secret": "correct-secret"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "unknown_product"


def test_register_token_mints_and_is_idempotent(client, monkeypatch):
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    headers = {"x-webhook-secret": "correct-secret"}
    payload = {
        "session_id": "s1",
        "product": "paper-review-standard",
        "email": "a@b.com",
        "amount_paid": backend_app.PAID_PRODUCTS["paper-review-standard"]["amount"],
    }

    r1 = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["status"] == "registered"
    assert len(body1["tokens"]) == 1

    # Re-registering the same session_id must return the same tokens, not mint new ones.
    r2 = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["status"] == "exists"
    assert body2["tokens"] == body1["tokens"]


def test_register_token_credits_valid_edu_referral(client, monkeypatch):
    """A .edu buyer using a live referral code (registered by an earlier
    purchaser's completed review — see paper_review_pipeline._run) should
    trigger _credit_referral. We don't hit real Stripe/Resend here — just
    assert the crediting path is invoked with the right two emails."""
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    headers = {"x-webhook-secret": "correct-secret"}

    referrer_email = "referrer@example.com"
    code = backend_app._paper_referral_code(referrer_email)
    backend_app.referral_dict[code] = referrer_email

    calls = []
    async def _fake_credit(referrer, referee):
        calls.append((referrer, referee))
    monkeypatch.setattr(backend_app, "_credit_referral", _fake_credit)

    payload = {
        "session_id": "s-edu-referral",
        "product": "paper-review-standard",
        "email": "student@school.edu",
        "amount_paid": backend_app.PAID_PRODUCTS["paper-review-standard"]["amount"],
        "referral_code": code,
    }
    r = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r.status_code == 200
    assert calls == [(referrer_email, "student@school.edu")]


def test_register_token_skips_credit_for_non_edu_email(client, monkeypatch):
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    headers = {"x-webhook-secret": "correct-secret"}

    referrer_email = "referrer@example.com"
    code = backend_app._paper_referral_code(referrer_email)
    backend_app.referral_dict[code] = referrer_email

    calls = []
    async def _fake_credit(referrer, referee):
        calls.append((referrer, referee))
    monkeypatch.setattr(backend_app, "_credit_referral", _fake_credit)

    payload = {
        "session_id": "s-non-edu",
        "product": "paper-review-standard",
        "email": "buyer@gmail.com",
        "amount_paid": backend_app.PAID_PRODUCTS["paper-review-standard"]["amount"],
        "referral_code": code,
    }
    r = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r.status_code == 200
    assert calls == []


def test_register_token_skips_credit_for_unknown_referral_code(client, monkeypatch):
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    headers = {"x-webhook-secret": "correct-secret"}

    calls = []
    async def _fake_credit(referrer, referee):
        calls.append((referrer, referee))
    monkeypatch.setattr(backend_app, "_credit_referral", _fake_credit)

    payload = {
        "session_id": "s-unknown-code",
        "product": "paper-review-standard",
        "email": "student@school.edu",
        "amount_paid": backend_app.PAID_PRODUCTS["paper-review-standard"]["amount"],
        "referral_code": "not-a-real-code",
    }
    r = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r.status_code == 200
    assert calls == []


def test_register_token_skips_credit_for_self_referral(client, monkeypatch):
    """A buyer can't credit themselves by reusing their own code."""
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    headers = {"x-webhook-secret": "correct-secret"}

    same_email = "person@school.edu"
    code = backend_app._paper_referral_code(same_email)
    backend_app.referral_dict[code] = same_email

    calls = []
    async def _fake_credit(referrer, referee):
        calls.append((referrer, referee))
    monkeypatch.setattr(backend_app, "_credit_referral", _fake_credit)

    payload = {
        "session_id": "s-self-referral",
        "product": "paper-review-standard",
        "email": same_email,
        "amount_paid": backend_app.PAID_PRODUCTS["paper-review-standard"]["amount"],
        "referral_code": code,
    }
    r = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r.status_code == 200
    assert calls == []


def test_register_token_rejects_amount_mismatch(client, monkeypatch):
    """Defense-in-depth: if the Netlify Stripe webhook ever mismaps a
    price_id to the wrong product_key (e.g. sends the 5-pack's product_key
    with the 20-pack's charged amount, or vice versa), register-token must
    refuse to mint tokens rather than silently minting the wrong quantity."""
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    headers = {"x-webhook-secret": "correct-secret"}
    payload = {
        "session_id": "s-mismatch",
        "product": "paper-review-pack-5",
        "email": "a@b.com",
        # Actual charge for the 20-pack, but product_key claims the 5-pack.
        "amount_paid": backend_app.PAID_PRODUCTS["paper-review-pack-20"]["amount"],
    }

    r = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r.status_code == 400
    assert r.json()["error"] == "amount_mismatch"
    assert "s-mismatch" not in backend_app.paper_tokens_dict._data


def test_register_token_rejects_out_of_bounds_qty(client, monkeypatch):
    """Defense-in-depth: PAID_PRODUCTS qty is static today (1, 5, or 20), but
    the catalog comment notes entries can be overridden by env vars at
    deploy time. If a misconfigured override ever pushed qty past
    MAX_PACK_QTY, register-token must refuse to mint/email that many tokens
    rather than doing it unbounded inside the webhook handler."""
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    headers = {"x-webhook-secret": "correct-secret"}

    bogus_qty = backend_app.MAX_PACK_QTY + 1
    bogus_cfg = dict(backend_app.PAID_PRODUCTS["paper-review-pack-20"])
    bogus_cfg["qty"] = bogus_qty
    monkeypatch.setitem(backend_app.PAID_PRODUCTS, "paper-review-pack-20", bogus_cfg)

    payload = {
        "session_id": "s-huge-pack",
        "product": "paper-review-pack-20",
        "email": "a@b.com",
        "amount_paid": bogus_cfg["amount"],
    }

    r = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r.status_code == 500
    assert r.json()["error"] == "invalid_product_qty"
    assert "s-huge-pack" not in backend_app.paper_tokens_dict._data


# ---------------------------------------------------------------------------
# redeem-session
# ---------------------------------------------------------------------------

def test_redeem_session_unknown_session_is_pending(client):
    http, backend_app = client
    r = http.post("/paper-review/redeem-session", json={"session_id": "does-not-exist"})
    assert r.status_code == 404
    assert r.json()["error"] == "pending"


def test_redeem_session_expired(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-expired")
    entry = backend_app.paper_tokens_dict["s-expired"]
    entry["expires_at"] = time.time() - 1
    backend_app.paper_tokens_dict["s-expired"] = entry

    r = http.post("/paper-review/redeem-session", json={"session_id": "s-expired"})
    assert r.status_code == 410
    assert r.json()["error"] == "expired"


def test_redeem_session_expired_entry_is_purged_not_left_for_modal_ttl(client):
    """The app must actively delete logically-expired entries from
    paper_tokens_dict / paper_token_index_dict on its own clock, rather
    than relying on modal.Dict's independent inactivity-based eviction
    (which resets on any read/write and can't be trusted to match
    `expires_at`). Regression test for the TTL-enforcement gap."""
    http, backend_app = client
    token = _register(backend_app, session_id="s-expired-purge")
    backend_app.paper_token_index_dict[token] = "s-expired-purge"
    entry = backend_app.paper_tokens_dict["s-expired-purge"]
    entry["expires_at"] = time.time() - 1
    backend_app.paper_tokens_dict["s-expired-purge"] = entry

    r = http.post("/paper-review/redeem-session", json={"session_id": "s-expired-purge"})
    assert r.status_code == 410

    assert backend_app.paper_tokens_dict.get("s-expired-purge") is None
    assert backend_app.paper_token_index_dict.get(token) is None


def test_sweep_expired_paper_tokens_purges_untouched_entries(client):
    """Entries whose expires_at has passed must be purged by the scheduled
    sweep even when no one ever hits /redeem-session or /submit for them
    (the reactive checks there can't help if the buyer never comes back).
    Regression test for the missing-cron TTL-enforcement gap."""
    http, backend_app = client

    expired_token = _register(backend_app, session_id="s-sweep-expired")
    backend_app.paper_token_index_dict[expired_token] = "s-sweep-expired"
    entry = backend_app.paper_tokens_dict["s-sweep-expired"]
    entry["expires_at"] = time.time() - 1
    backend_app.paper_tokens_dict["s-sweep-expired"] = entry

    live_token = _register(backend_app, session_id="s-sweep-live")
    backend_app.paper_token_index_dict[live_token] = "s-sweep-live"

    purged = backend_app.sweep_expired_paper_tokens.local()

    assert purged == 1
    assert backend_app.paper_tokens_dict.get("s-sweep-expired") is None
    assert backend_app.paper_token_index_dict.get(expired_token) is None
    # Unexpired entries are left alone.
    assert backend_app.paper_tokens_dict.get("s-sweep-live") is not None
    assert backend_app.paper_token_index_dict.get(live_token) == "s-sweep-live"


def test_sweep_stale_paper_jobs_purges_error_and_unpolled_entries(client):
    """paper_jobs_dict entries older than PAPER_JOB_TTL_SECONDS must be
    purged by the scheduled sweep even when they never reach the
    status=='done' + result_md retrieval path in /paper-review/status
    (pipeline error, or the buyer simply never polls again). Regression
    test for the missing-cron TTL-enforcement gap on job entries."""
    http, backend_app = client

    stale_cutoff = time.time() - backend_app.PAPER_JOB_TTL_SECONDS - 1

    # A job that ended in status == "error" (pipeline exception) — never
    # cleaned up by the "done" branch in /paper-review/status.
    backend_app.paper_jobs_dict["tok-stale-error"] = {
        "status": "error", "stage": "error", "progress_pct": 0,
        "started_at": stale_cutoff, "product": "paper-review",
        "error": "boom",
    }
    # A job that's still nominally "running"/"queued" because the buyer
    # never polled it to completion.
    backend_app.paper_jobs_dict["tok-stale-unpolled"] = {
        "status": "queued", "stage": "queued", "progress_pct": 0,
        "started_at": stale_cutoff, "product": "paper-review",
    }
    # A fresh, still-in-flight job must be left alone.
    backend_app.paper_jobs_dict["tok-fresh-running"] = {
        "status": "running", "stage": "reviewing", "progress_pct": 40,
        "started_at": time.time(), "product": "paper-review",
    }
    # A fresh "done" job (e.g. buyer hasn't polled the result yet) must
    # also be left alone even though it's already completed.
    backend_app.paper_jobs_dict["tok-fresh-done"] = {
        "status": "done", "stage": "done", "progress_pct": 100,
        "started_at": time.time(), "product": "paper-review",
        "result_md": "# Review",
    }

    purged = backend_app.sweep_stale_paper_jobs.local()

    assert purged == 2
    assert backend_app.paper_jobs_dict.get("tok-stale-error") is None
    assert backend_app.paper_jobs_dict.get("tok-stale-unpolled") is None
    assert backend_app.paper_jobs_dict.get("tok-fresh-running") is not None
    assert backend_app.paper_jobs_dict.get("tok-fresh-done") is not None


def test_sweep_stale_paper_jobs_purges_delivered_entries_past_grace_window(client):
    """A job that was delivered (delivered_at set) but never polled again
    must be purged once PAPER_RESULT_GRACE_SECONDS has elapsed since
    delivery — not left to sit for the full PAPER_JOB_TTL_SECONDS."""
    http, backend_app = client

    old_start = time.time() - backend_app.PAPER_JOB_TTL_SECONDS - 1
    stale_delivery = time.time() - backend_app.PAPER_RESULT_GRACE_SECONDS - 1

    # Delivered long ago (past grace window) but started recently enough
    # that the old started_at-only TTL check would have left it alone.
    backend_app.paper_jobs_dict["tok-delivered-stale"] = {
        "status": "done", "stage": "done", "progress_pct": 100,
        "started_at": time.time(), "product": "paper-review",
        "result_md": "# Review", "delivered_at": stale_delivery,
    }
    # Delivered recently — must be left alone even though started_at is old.
    backend_app.paper_jobs_dict["tok-delivered-fresh"] = {
        "status": "done", "stage": "done", "progress_pct": 100,
        "started_at": old_start, "product": "paper-review",
        "result_md": "# Review", "delivered_at": time.time(),
    }

    purged = backend_app.sweep_stale_paper_jobs.local()

    assert purged == 1
    assert backend_app.paper_jobs_dict.get("tok-delivered-stale") is None
    assert backend_app.paper_jobs_dict.get("tok-delivered-fresh") is not None


def test_submit_expired_token_entry_is_purged(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-expired-submit-purge")
    entry = backend_app.paper_tokens_dict["s-expired-submit-purge"]
    entry["expires_at"] = time.time() - 1
    backend_app.paper_tokens_dict["s-expired-submit-purge"] = entry

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 410
    assert r.json()["error"] == "expired"
    assert backend_app.paper_tokens_dict.get("s-expired-submit-purge") is None


def test_redeem_session_all_used(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-used")
    entry = backend_app.paper_tokens_dict["s-used"]
    entry["consumed_tokens"] = [token]
    backend_app.paper_tokens_dict["s-used"] = entry

    r = http.post("/paper-review/redeem-session", json={"session_id": "s-used"})
    assert r.status_code == 409
    assert r.json()["error"] == "all_used"


def test_redeem_session_ok(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-ok")

    r = http.post("/paper-review/redeem-session", json={"session_id": "s-ok"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"] == token
    assert body["status"] == "ok"
    assert backend_app.paper_tokens_dict["s-ok"]["redeemed"] is True


def test_redeem_session_by_token_ok(client):
    """Regression test: the pack success page's "Use this token" link
    (site/tools/paper-review/packs/success.js) sends a saved token, not the
    original Stripe session_id, to /tools/paper-review/upload/. The upload
    page's redeem call must be able to look the entry up by that token
    alone so a returning volume-pack buyer can self-serve a second (or
    third...) review without re-running checkout."""
    http, backend_app = client
    tokens = _register_volume_pack(backend_app, session_id="s-pack-direct", qty=5)
    second_token = tokens[1]

    r = http.post("/paper-review/redeem-session", json={"token": second_token})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert second_token in body["unused_tokens"]
    assert backend_app.paper_tokens_dict["s-pack-direct"]["redeemed"] is True


def test_redeem_session_by_token_already_used(client):
    http, backend_app = client
    tokens = _register_volume_pack(backend_app, session_id="s-pack-used", qty=5)
    used_token = tokens[0]
    entry = backend_app.paper_tokens_dict["s-pack-used"]
    entry["consumed_tokens"] = [used_token]
    backend_app.paper_tokens_dict["s-pack-used"] = entry

    r = http.post("/paper-review/redeem-session", json={"token": used_token})
    assert r.status_code == 409
    assert r.json()["error"] == "already_used"


def test_redeem_session_by_unknown_token_is_pending(client):
    http, backend_app = client
    r = http.post("/paper-review/redeem-session", json={"token": "does-not-exist"})
    assert r.status_code == 404
    assert r.json()["error"] == "pending"


def test_redeem_session_missing_both_session_id_and_token(client):
    http, backend_app = client
    r = http.post("/paper-review/redeem-session", json={})
    assert r.status_code == 400
    assert r.json()["error"] == "missing_session_id"


def test_redeem_session_is_rate_limited(client):
    """Regression test: /paper-review/redeem-session must be throttled
    per-IP like the other endpoints (_enforce_rate_limit), so a script
    can't hammer it guessing/brute-forcing session_id values indefinitely."""
    http, backend_app = client

    for _ in range(backend_app.core.DAILY_LIMIT):
        r = http.post("/paper-review/redeem-session", json={"session_id": "does-not-exist"})
        assert r.status_code == 404  # still under the cap; normal "pending" response

    r = http.post("/paper-review/redeem-session", json={"session_id": "does-not-exist"})
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"


# ---------------------------------------------------------------------------
# invoice
# ---------------------------------------------------------------------------

def test_invoice_is_rate_limited(client):
    """Regression test: /paper-review/invoice must be throttled per-IP like
    every other paid POST endpoint (_enforce_rate_limit). Each call chains
    several Stripe API requests plus an email send, so an unthrottled loop
    replaying a known/leaked session_id could generate unlimited real
    invoices and burn Stripe API quota shared with the checkout/webhook
    flow."""
    http, backend_app = client

    for _ in range(backend_app.core.DAILY_LIMIT):
        r = http.post(
            "/paper-review/invoice",
            json={"session_id": "does-not-exist", "token": "tok-does-not-exist"},
        )
        assert r.status_code == 404  # still under the cap; normal "unknown_session" response

    r = http.post(
        "/paper-review/invoice",
        json={"session_id": "does-not-exist", "token": "tok-does-not-exist"},
    )
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"


def test_invoice_requires_token_field(client):
    """IDOR regression: session_id alone must not be sufficient to fetch a
    billing invoice. session_id is embedded in the post-checkout success URL
    (?session_id=...) and can leak via browser history/Referer/screenshots,
    so the endpoint must additionally require proof of possession of the
    associated job token, like every submit/redeem endpoint does."""
    http, backend_app = client
    _register(backend_app, session_id="sess-invoice-1")

    r = http.post("/paper-review/invoice", json={"session_id": "sess-invoice-1"})
    assert r.status_code == 400
    assert r.json()["error"] == "missing_token"


def test_invoice_rejects_session_id_with_wrong_or_unknown_token(client):
    """IDOR regression: an attacker who only knows a leaked session_id (and
    not the real job token) must be rejected, not granted the invoice."""
    http, backend_app = client
    _register(backend_app, session_id="sess-invoice-2")

    r = http.post(
        "/paper-review/invoice",
        json={"session_id": "sess-invoice-2", "token": "not-the-real-token"},
    )
    assert r.status_code == 403
    assert r.json()["error"] == "invalid_token"


def test_invoice_stripe_lookup_failure_does_not_leak_raw_stripe_body(client, monkeypatch):
    """Regression test: when the Stripe Checkout Session lookup fails,
    the endpoint must not echo Stripe's raw response body (which can
    contain internal error codes/messages not meant for end users) back
    to an unauthenticated caller. It should log the detail server-side
    and return only a generic error code."""
    http, backend_app = client

    session_id = "sess-leak-check"
    token = _register(backend_app, session_id=session_id)

    secret_looking_body = (
        '{"error": {"message": "No such customer: \'cus_SECRETSQUIRREL123\' '
        'internal_trace_id=abc-super-secret-456", "type": "invalid_request_error"}}'
    )

    class _FakeStripeResp:
        status_code = 400
        text = secret_looking_body

        def json(self):
            import json as _json
            return _json.loads(self.text)

    class _FakeStripeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, *args, **kwargs):
            return _FakeStripeResp()

        async def post(self, *args, **kwargs):
            return _FakeStripeResp()

    monkeypatch.setitem(backend_app.os.environ, "STRIPE_SECRET_KEY", "sk_test_fake")

    import httpx as real_httpx
    monkeypatch.setattr(real_httpx, "AsyncClient", lambda *a, **kw: _FakeStripeClient())

    import logging
    caplog_records = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record):
            caplog_records.append(record.getMessage())

    handler = _CaptureHandler()
    backend_app.logger.addHandler(handler)
    try:
        r = http.post("/paper-review/invoice", json={"session_id": session_id, "token": token})
    finally:
        backend_app.logger.removeHandler(handler)

    assert r.status_code == 502
    body = r.json()
    assert body == {"error": "stripe_lookup_failed"}
    assert "SECRETSQUIRREL123" not in r.text
    assert "internal_trace_id" not in r.text

    # The raw Stripe detail should still be captured server-side for debugging.
    assert any("SECRETSQUIRREL123" in msg for msg in caplog_records)


# ---------------------------------------------------------------------------
# journals
# ---------------------------------------------------------------------------

def test_journals_is_rate_limited(client):
    """Regression test: /paper-review/journals must be throttled per-IP
    like every other paper-review endpoint (_enforce_rate_limit), for
    consistency even though it only serves static in-memory data."""
    http, backend_app = client

    for _ in range(backend_app.core.DAILY_LIMIT):
        r = http.get("/paper-review/journals", params={"domain": "general"})
        assert r.status_code == 200
        assert "journals" in r.json()

    r = http.get("/paper-review/journals", params={"domain": "general"})
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"


# ---------------------------------------------------------------------------
# submit
# ---------------------------------------------------------------------------

def test_submit_unknown_token(client):
    http, backend_app = client
    r = http.post(
        "/paper-review/submit",
        data={"token": "no-such-token", "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 404
    assert r.json()["error"] == "unknown_token"


def test_submit_already_used_token(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-already-used")
    entry = backend_app.paper_tokens_dict["s-already-used"]
    entry["consumed_tokens"] = [token]
    backend_app.paper_tokens_dict["s-already-used"] = entry

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 409
    assert r.json()["error"] == "already_used"
    # Must not have spawned a billable pipeline run.
    assert backend_app.paper_review_pipeline.calls == []


def test_submit_expired_token(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-expired-submit")
    entry = backend_app.paper_tokens_dict["s-expired-submit"]
    entry["expires_at"] = time.time() - 1
    backend_app.paper_tokens_dict["s-expired-submit"] = entry

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 410
    assert r.json()["error"] == "expired"
    assert backend_app.paper_review_pipeline.calls == []


def test_submit_wrong_product_token_rejected(client):
    """A token minted for an adjacent tool (e.g. cover-letter) must not be
    usable against the paper-review submit endpoint."""
    http, backend_app = client
    token = _register(backend_app, product_key="cover-letter", session_id="s-wrong-product")

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "wrong_product"
    assert backend_app.paper_review_pipeline.calls == []


def test_score_submit_rejects_non_paper_review_token(client):
    """Regression test for the confirmed cross-product defect: /score/submit
    (AI-SCoRe) delegated straight into paper_review_submit, whose only
    category gate used a permissive default (`.get('category',
    'paper-review')`), so a token registered for an unrelated category (e.g.
    cover-letter) with a missing/mismatched category would not be reliably
    rejected. /score/submit must enforce its own explicit category check."""
    http, backend_app = client
    token = _register(backend_app, product_key="cover-letter", session_id="s-score-wrong-product")

    r = http.post(
        "/score/submit",
        data={"token": token},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "wrong_product"
    assert backend_app.paper_review_pipeline.calls == []


def test_score_submit_accepts_paper_review_token(client):
    """Baseline: a genuine paper-review token (today's only category sold for
    AI-SCoRe) is still usable on /score/submit and is dispatched with the
    'nca' domain."""
    http, backend_app = client
    token = _register(backend_app, session_id="s-score-ok")

    r = http.post(
        "/score/submit",
        data={"token": token},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 200
    assert len(backend_app.paper_review_pipeline.calls) == 1
    args, kwargs = backend_app.paper_review_pipeline.calls[0]
    assert args[2] == "nca"  # domain positional arg


def test_submit_rejects_non_pdf_body(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-not-pdf")

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(b"not a pdf at all"), "application/pdf")},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid"
    assert backend_app.paper_review_pipeline.calls == []
    # Token must remain unconsumed after a rejected upload.
    assert token not in (backend_app.paper_tokens_dict["s-not-pdf"].get("consumed_tokens") or [])


def test_submit_malformed_multipart_missing_file(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-malformed")

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        # no `file` part at all
    )
    assert r.status_code == 422  # FastAPI/Pydantic request validation error
    assert backend_app.paper_review_pipeline.calls == []


def _register_volume_pack(backend_app, *, session_id="sess-pack", qty=5,
                           product_key="paper-review-pack-5"):
    """Seed a paper_tokens_dict entry the way register-token would for a
    volume pack: one shared entry dict holding many tokens."""
    product_cfg = dict(backend_app.PAID_PRODUCTS[product_key])
    tokens = [f"tok-{session_id}-{i}" for i in range(qty)]
    entry = {
        "tokens": tokens,
        "product_key": product_key,
        "product_cfg": product_cfg,
        "email": "buyer@example.com",
        "amount_paid": product_cfg.get("amount", 0),
        "redeemed": False,
        "consumed_tokens": [],
        "created_at": time.time(),
        "expires_at": time.time() + 7 * 24 * 3600,
    }
    backend_app.paper_tokens_dict[session_id] = entry
    return tokens


def test_submit_concurrent_pack_tokens_both_recorded_no_overwrite(client, monkeypatch):
    """Regression test for the volume-pack whole-entry overwrite race.

    For 5-pack/20-pack purchases, all tokens share one `paper_tokens_dict`
    entry. Two different tokens from the same pack redeemed "concurrently"
    (e.g. two students submitting within the same second, from different
    devices) must both end up recorded in `consumed_tokens` — a naive
    read-modify-write on the whole entry would let the later write clobber
    the earlier one's bookkeeping (and, via `test_submit_already_used_token`,
    let the clobbered token be resubmitted / double-spent).

    We drive this through the real `/paper-review/submit` route (not by
    calling the closure directly, since `_consume_token` is private to the
    `web()` closure) and force the interleaving that causes the bug: both
    requests' `_lookup_token` calls return a snapshot of the entry taken
    *before* either request's `_consume_token` write lands.
    """
    http, backend_app = client
    tokens = _register_volume_pack(backend_app, session_id="sess-race", qty=5)
    tok_a, tok_b = tokens[0], tokens[1]

    # `_lookup_token`/`_consume_token` are private closures inside app.py's
    # `web()` and can't be monkeypatched directly, so we force the race at
    # the Dict layer they both read/write through: the *first* read of
    # "sess-race" per simulated request (i.e. each request's `_lookup_token`
    # call, which happens once near the top of `/paper-review/submit`,
    # before any writes) returns a frozen pre-race snapshot — exactly as if
    # both HTTP requests' initial reads happened before either request's
    # `_consume_token` write landed. Subsequent reads (e.g. the re-fetch
    # inside a fixed `_consume_token`) see live data, same as a real
    # Modal Dict would once a write has actually landed. `__setitem__`
    # writes through to real storage so we can assert on final state.
    import copy as _copy
    real_dict = backend_app.paper_tokens_dict
    stale_snapshot = dict(real_dict.get("sess-race"))
    stale_reads_remaining = [2]  # one per concurrent "request"

    class _StaleReadDict:
        def _maybe_stale(self, key):
            if key == "sess-race" and stale_reads_remaining[0] > 0:
                stale_reads_remaining[0] -= 1
                # Deep-copy so each simulated concurrent read gets its own
                # independent `consumed_tokens` list, not a shared reference.
                return _copy.deepcopy(stale_snapshot)
            return None

        def get(self, key, default=None):
            stale = self._maybe_stale(key)
            if stale is not None:
                return stale
            return real_dict.get(key, default)

        def __getitem__(self, key):
            return real_dict[key]

        def __setitem__(self, key, value):
            real_dict[key] = value

        def __delitem__(self, key):
            del real_dict[key]

        def items(self):
            out = []
            for k, v in real_dict.items():
                if k == "sess-race":
                    stale = self._maybe_stale(k)
                    out.append((k, stale if stale is not None else v))
                else:
                    out.append((k, v))
            return out

        def put(self, key, value, *, skip_if_exists=False):
            return real_dict.put(key, value, skip_if_exists=skip_if_exists)

    monkeypatch.setattr(backend_app, "paper_tokens_dict", _StaleReadDict())

    r_a = http.post(
        "/paper-review/submit",
        data={"token": tok_a, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    r_b = http.post(
        "/paper-review/submit",
        data={"token": tok_b, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )

    assert r_a.status_code == 200
    assert r_b.status_code == 200
    # Both pipeline runs were legitimately distinct tokens, so both spawn.
    assert len(backend_app.paper_review_pipeline.calls) == 2

    final_consumed = set(real_dict["sess-race"]["consumed_tokens"])
    assert final_consumed == {tok_a, tok_b}, (
        "both concurrently-consumed pack tokens must be recorded even though "
        f"each request read a stale pre-race entry snapshot; got {final_consumed}"
    )


def test_submit_success_spawns_pipeline_and_consumes_token(client):
    http, backend_app = client
    token = _register(backend_app, session_id="s-success")

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"] == token
    assert body["status_url"] == f"/paper-review/status?token={token}"

    assert len(backend_app.paper_review_pipeline.calls) == 1
    assert token in backend_app.paper_tokens_dict["s-success"]["consumed_tokens"]

    # A second submit with the same token must now be rejected.
    r2 = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r2.status_code == 409
    assert r2.json()["error"] == "already_used"
    assert len(backend_app.paper_review_pipeline.calls) == 1  # still just the one spawn


def test_submit_spawn_failure_does_not_consume_token(client, monkeypatch):
    """If `paper_review_pipeline.spawn()` raises (e.g. Modal control-plane
    error, container pool exhausted), the customer's token must NOT be
    marked consumed and must remain resubmittable — otherwise a paid
    credit is silently burned with no pipeline ever having run."""
    http, backend_app = client
    token = _register(backend_app, session_id="s-spawn-fail")

    def _boom(*args, **kwargs):
        raise RuntimeError("modal control-plane unavailable")

    monkeypatch.setattr(backend_app.paper_review_pipeline, "spawn", _AioBridge(_boom))

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 500
    assert r.json()["error"] == "spawn_failed"

    # Token must not be recorded as consumed.
    assert token not in (backend_app.paper_tokens_dict["s-spawn-fail"].get("consumed_tokens") or [])
    # The stuck 'queued' job entry must be rolled back, not left dangling.
    assert backend_app.paper_jobs_dict.get(token) is None
    # The CAS claim must be released so a retry isn't rejected as already_used.
    assert backend_app.paper_token_claims_dict.get(token) is None

    # Restore a working spawn and confirm the token can now be resubmitted
    # successfully (this is the whole point of releasing the claim).
    monkeypatch.setattr(backend_app, "paper_review_pipeline", _FakeSpawnFunction())
    r2 = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r2.status_code == 200
    assert len(backend_app.paper_review_pipeline.calls) == 1
    assert token in backend_app.paper_tokens_dict["s-spawn-fail"]["consumed_tokens"]


def _register_cover_letter(backend_app, *, session_id="sess-cl"):
    product_cfg = backend_app.PAID_PRODUCTS["cover-letter"]
    token = "tok-" + session_id
    entry = {
        "tokens": [token],
        "product_key": "cover-letter",
        "product_cfg": product_cfg,
        "email": "buyer@example.com",
        "amount_paid": product_cfg.get("amount", 0),
        "redeemed": False,
        "consumed_tokens": [],
        "created_at": time.time(),
        "expires_at": time.time() + 7 * 24 * 3600,
    }
    backend_app.paper_tokens_dict[session_id] = entry
    return token


def test_cover_letter_submit_rejects_gibberish_abstract(client):
    """Regression test for the confirmed defect: cover_letter_submit only
    checked non-empty/<=5000 chars, so keyboard-mash or placeholder text
    (e.g. "asdf asdf asdf") passed validation and burned the paid charge on
    a low-quality LLM output. Garbage input must be rejected with 400
    before the pipeline is spawned or the token consumed."""
    http, backend_app = client
    token = _register_cover_letter(backend_app, session_id="s-adj-gibberish")

    r = http.post(
        "/cover-letter/submit",
        data={"token": token, "abstract": "asdf asdf asdf asdf asdf asdf", "journal_name": "JAIS"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid"
    assert len(backend_app.adjacent_tool_pipeline.calls) == 0
    assert token not in (backend_app.paper_tokens_dict["s-adj-gibberish"].get("consumed_tokens") or [])

    # A real abstract on the same token should still succeed afterwards.
    r2 = http.post(
        "/cover-letter/submit",
        data={
            "token": token,
            "abstract": "This paper investigates how information systems research can improve manuscript quality through automated review tooling and structured feedback loops.",
            "journal_name": "JAIS",
        },
    )
    assert r2.status_code == 200
    assert len(backend_app.adjacent_tool_pipeline.calls) == 1


def test_adjacent_submit_success_spawns_pipeline_and_consumes_token(client):
    """Baseline: a healthy /cover-letter/submit spawns the adjacent-tool
    pipeline exactly once and marks the token consumed."""
    http, backend_app = client
    token = _register_cover_letter(backend_app, session_id="s-adj-success")

    r = http.post(
        "/cover-letter/submit",
        data={"token": token, "abstract": "This paper investigates how information systems research can improve manuscript quality through automated review tooling and structured feedback loops.", "journal_name": "JAIS"},
    )
    assert r.status_code == 200
    assert len(backend_app.adjacent_tool_pipeline.calls) == 1
    assert token in backend_app.paper_tokens_dict["s-adj-success"]["consumed_tokens"]

    r2 = http.post(
        "/cover-letter/submit",
        data={"token": token, "abstract": "This paper investigates how information systems research can improve manuscript quality through automated review tooling and structured feedback loops.", "journal_name": "JAIS"},
    )
    assert r2.status_code == 409
    assert r2.json()["error"] == "already_used"
    assert len(backend_app.adjacent_tool_pipeline.calls) == 1


def test_adjacent_submit_spawn_failure_does_not_consume_token(client, monkeypatch):
    """Regression test for the confirmed defect: _start_adjacent used to call
    _consume_token() before adjacent_tool_pipeline.spawn() ran, so a token
    was burned even when the pipeline never started (e.g. a transient Modal
    control-plane error). If `.spawn()` raises, the token must NOT be
    recorded as consumed, the stuck 'queued' job entry and the CAS claim
    must both be rolled back, and the token must remain resubmittable —
    otherwise the customer's only recourse is emailing for a manual refund."""
    http, backend_app = client
    token = _register_cover_letter(backend_app, session_id="s-adj-spawn-fail")

    def _boom(*args, **kwargs):
        raise RuntimeError("modal control-plane unavailable")

    monkeypatch.setattr(backend_app.adjacent_tool_pipeline, "spawn", _AioBridge(_boom))

    r = http.post(
        "/cover-letter/submit",
        data={"token": token, "abstract": "This paper investigates how information systems research can improve manuscript quality through automated review tooling and structured feedback loops.", "journal_name": "JAIS"},
    )
    assert r.status_code == 500
    assert r.json()["error"] == "spawn_failed"

    # Token must not be recorded as consumed.
    assert token not in (backend_app.paper_tokens_dict["s-adj-spawn-fail"].get("consumed_tokens") or [])
    # The stuck 'queued' job entry must be rolled back, not left dangling.
    assert backend_app.paper_jobs_dict.get(token) is None
    # The CAS claim must be released so a retry isn't rejected as already_used.
    assert backend_app.paper_token_claims_dict.get(token) is None

    # Restore a working spawn and confirm the token can now be resubmitted
    # successfully (this is the whole point of releasing the claim).
    monkeypatch.setattr(backend_app, "adjacent_tool_pipeline", _FakeSpawnFunction())
    r2 = http.post(
        "/cover-letter/submit",
        data={"token": token, "abstract": "This paper investigates how information systems research can improve manuscript quality through automated review tooling and structured feedback loops.", "journal_name": "JAIS"},
    )
    assert r2.status_code == 200
    assert len(backend_app.adjacent_tool_pipeline.calls) == 1
    assert token in backend_app.paper_tokens_dict["s-adj-spawn-fail"]["consumed_tokens"]


def test_adjacent_submit_expired_token_rejected(client):
    """Regression test for the confirmed defect: the adjacent-tool submit
    endpoints (cover-letter, anonymity-check, citation-gap, revision-review,
    response-review) never checked `expires_at`, unlike paper_review_submit
    and redeem-session. A technically-expired token (past the 7-day TTL)
    must be rejected with 410 and must never reach _start_adjacent, even
    though the daily sweep_expired_paper_tokens cron hasn't purged it yet."""
    http, backend_app = client
    token = _register_cover_letter(backend_app, session_id="s-adj-expired")
    entry = backend_app.paper_tokens_dict["s-adj-expired"]
    entry["expires_at"] = time.time() - 1
    backend_app.paper_tokens_dict["s-adj-expired"] = entry

    r = http.post(
        "/cover-letter/submit",
        data={
            "token": token,
            "abstract": "This paper investigates how information systems research can improve manuscript quality through automated review tooling and structured feedback loops.",
            "journal_name": "JAIS",
        },
    )
    assert r.status_code == 410
    assert r.json()["error"] == "expired"
    assert len(backend_app.adjacent_tool_pipeline.calls) == 0
    # The now-expired entry must be actively purged, mirroring paper_review_submit.
    assert backend_app.paper_tokens_dict.get("s-adj-expired") is None


def test_register_token_populates_reverse_index(client, monkeypatch):
    """/register-token must populate paper_token_index_dict so `_lookup_token`
    (used by submit/status) is an O(1) get instead of a full scan of
    paper_tokens_dict."""
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "correct-secret")
    headers = {"x-webhook-secret": "correct-secret"}
    payload = {
        "session_id": "s-index",
        "product": "paper-review-standard",
        "email": "a@b.com",
        "amount_paid": backend_app.PAID_PRODUCTS["paper-review-standard"]["amount"],
    }

    r = http.post("/paper-review/register-token", json=payload, headers=headers)
    assert r.status_code == 200
    token = r.json()["tokens"][0]

    assert backend_app.paper_token_index_dict.get(token) == "s-index"


def test_submit_finds_token_via_reverse_index(client, monkeypatch):
    """When the reverse index has an entry, submit must resolve the token
    through it (not just via the linear-scan fallback)."""
    http, backend_app = client
    token = _register(backend_app, session_id="s-index-lookup")
    backend_app.paper_token_index_dict["tok-s-index-lookup"] = "s-index-lookup"

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 200
    assert len(backend_app.paper_review_pipeline.calls) == 1


def test_submit_falls_back_and_backfills_index_for_preexisting_entry(client):
    """Tokens seeded directly into paper_tokens_dict without going through
    /register-token (e.g. pre-migration entries) have no reverse-index
    record yet. `_lookup_token` must still find them via the linear-scan
    fallback, and should backfill the index for next time."""
    http, backend_app = client
    token = _register(backend_app, session_id="s-no-index")
    assert backend_app.paper_token_index_dict.get(token) is None  # not indexed yet

    r = http.post(
        "/paper-review/submit",
        data={"token": token, "domain": "general"},
        files={"file": ("paper.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 200
    assert backend_app.paper_token_index_dict.get(token) == "s-no-index"


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_unknown_token(client):
    http, backend_app = client
    r = http.get("/paper-review/status", params={"token": "no-such-job"})
    assert r.status_code == 404
    assert r.json()["error"] == "unknown_token"


def test_status_invalid_token_too_long(client):
    http, backend_app = client
    r = http.get("/paper-review/status", params={"token": "x" * 500})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_token"


def test_status_running_job(client):
    http, backend_app = client
    backend_app.paper_jobs_dict["tok-running"] = {
        "status": "running", "stage": "l2", "progress_pct": 40,
        "product": "paper-review", "tier": "standard", "error": None,
        "layer_status": {"l1": "done"},
    }
    r = http.get("/paper-review/status", params={"token": "tok-running"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["progress_pct"] == 40


def test_status_done_job_survives_first_read(client):
    """On first successful retrieval of a completed review, the server
    keeps the job record (stamped with delivered_at) instead of deleting
    it immediately, so a dropped response / refresh / second tab can still
    retrieve the same result within the grace window."""
    http, backend_app = client
    backend_app.paper_jobs_dict["tok-done"] = {
        "status": "done", "result_md": "# Review\n\nfindings...",
        "product": "paper-review", "tier": "standard",
    }
    r = http.get("/paper-review/status", params={"token": "tok-done"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["result_md"] == "# Review\n\nfindings..."

    # Record must still be present, now stamped as delivered.
    entry = backend_app.paper_jobs_dict.get("tok-done")
    assert entry is not None
    assert entry.get("delivered_at")

    # A second poll (refresh, duplicate tab, retry) within the grace
    # window must still get the full result back.
    r2 = http.get("/paper-review/status", params={"token": "tok-done"})
    assert r2.status_code == 200
    assert r2.json()["result_md"] == "# Review\n\nfindings..."


def test_status_done_job_includes_session_id_for_invoice_button(client):
    """The status page's "Get invoice for reimbursement" button only renders
    when the done payload carries session_id — and session_id is deliberately
    never present in the status page URL (see upload.js), so the backend
    must resolve it server-side from the token via the reverse index and
    include it in the completed-job payload, or the button is unreachable."""
    http, backend_app = client
    token = _register(backend_app, session_id="s-for-invoice")
    backend_app.paper_token_index_dict[token] = "s-for-invoice"
    backend_app.paper_jobs_dict[token] = {
        "status": "done", "result_md": "# Review\n\nfindings...",
        "product": "paper-review", "tier": "standard",
    }
    r = http.get("/paper-review/status", params={"token": token})
    assert r.status_code == 200
    assert r.json()["session_id"] == "s-for-invoice"


def test_status_done_job_omits_session_id_when_unresolvable(client):
    """If the token has no resolvable session (e.g. purged/legacy record),
    the done payload must simply omit session_id rather than error — the
    frontend treats a missing session_id as "no invoice button"."""
    http, backend_app = client
    backend_app.paper_jobs_dict["tok-orphan"] = {
        "status": "done", "result_md": "# Review\n\nfindings...",
        "product": "paper-review", "tier": "standard",
    }
    r = http.get("/paper-review/status", params={"token": "tok-orphan"})
    assert r.status_code == 200
    assert "session_id" not in r.json()


def test_status_done_job_purged_after_grace_window_elapses(client):
    """Once PAPER_RESULT_GRACE_SECONDS has elapsed since delivery, the next
    poll must no longer return the result and the record must be purged."""
    http, backend_app = client
    backend_app.paper_jobs_dict["tok-stale-delivered"] = {
        "status": "done", "result_md": "# Review\n\nfindings...",
        "product": "paper-review", "tier": "standard",
        "delivered_at": time.time() - backend_app.PAPER_RESULT_GRACE_SECONDS - 1,
    }
    r = http.get("/paper-review/status", params={"token": "tok-stale-delivered"})
    assert r.status_code == 404
    assert r.json()["error"] == "unknown_token"
    assert backend_app.paper_jobs_dict.get("tok-stale-delivered") is None


def test_status_done_job_concurrent_polls_both_get_result(client):
    """Two concurrent GET /paper-review/status polls for the same token
    (double-tab, client retry, or a deliberate race) must both receive the
    full review payload — neither should lose the result to the other."""
    import asyncio

    http, backend_app = client
    backend_app.paper_jobs_dict["tok-race"] = {
        "status": "done", "result_md": "# Review\n\nsecret findings...",
        "product": "paper-review", "tier": "standard",
    }

    async def _call():
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=http.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/paper-review/status", params={"token": "tok-race"})
            return resp.status_code, resp.json()

    async def _run():
        return await asyncio.gather(_call(), _call())

    results = asyncio.run(_run())
    assert [r[0] for r in results] == [200, 200], (
        f"Both concurrent polls must get the result, not race each other out: {results}"
    )
    for _, body in results:
        assert body["result_md"] == "# Review\n\nsecret findings..."


# ---------------------------------------------------------------------------
# referral footer + code registration
# ---------------------------------------------------------------------------

def test_paper_referral_code_is_deterministic_and_namespaced(monkeypatch):
    import app as backend_app
    monkeypatch.setenv("SUBSCRIBE_SECRET", "test-secret")

    code1 = backend_app._paper_referral_code("a@b.com")
    code2 = backend_app._paper_referral_code("a@b.com")
    code3 = backend_app._paper_referral_code("different@b.com")
    assert code1 == code2
    assert code1 != code3
    assert len(code1) == 10


def test_referral_footer_contains_working_link(monkeypatch):
    import app as backend_app
    monkeypatch.setenv("SUBSCRIBE_SECRET", "test-secret")

    footer = backend_app._referral_footer_md("a@b.com")
    code = backend_app._paper_referral_code("a@b.com")
    assert f"?ref={code}" in footer
    assert "purplelink.llc/tools/paper-review/" in footer


def test_paper_review_pipeline_appends_referral_footer_and_registers_code(monkeypatch):
    import app as backend_app
    from latextools import papercheck
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "referral_dict", _FakeDict())
    monkeypatch.setenv("SUBSCRIBE_SECRET", "test-secret")

    async def _fake_run_review_pipeline(pdf_bytes, domain, on_progress=None, **kwargs):
        return {"status": "done", "result_md": "# Review\n\nfindings...",
                "structure_summary": {"title": "A Great Paper"}}

    async def _noop_send_email(*args, **kwargs):
        return {"status": "ok"}

    from latextools import delivery
    monkeypatch.setattr(papercheck, "run_review_pipeline", _fake_run_review_pipeline)
    monkeypatch.setattr(delivery, "send_email", _noop_send_email)

    token = "tok-referral-footer"
    backend_app.paper_review_pipeline.local(
        token, PDF_BYTES, "cs", tier="standard", deliver_email="buyer@example.com",
    )

    entry = backend_app.paper_jobs_dict.get(token)
    code = backend_app._paper_referral_code("buyer@example.com")
    assert f"?ref={code}" in entry["result_md"]
    assert backend_app.referral_dict.get(code) == "buyer@example.com"


# ---------------------------------------------------------------------------
# delivery-email failure must not clobber an already-persisted result
#
# paper_review_pipeline / adjacent_tool_pipeline write the finished result to
# paper_jobs_dict *before* attempting the optional confirmation email. If
# that email send raises, it must not overwrite the already-paid-for,
# already-computed result with a bare status="error" record (the job's only
# copy, since /paper-review/status deletes on first read).
# ---------------------------------------------------------------------------

def test_paper_review_pipeline_email_failure_preserves_done_result(monkeypatch):
    import app as backend_app
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())

    from latextools import papercheck, delivery

    async def _fake_run_review_pipeline(pdf_bytes, domain, on_progress=None, **kwargs):
        return {
            "status": "done",
            "result_md": "# Review\n\nfindings...",
            "structure_summary": {"title": "A Great Paper"},
        }

    async def _boom_send_email(*args, **kwargs):
        raise RuntimeError("resend unreachable")

    monkeypatch.setattr(papercheck, "run_review_pipeline", _fake_run_review_pipeline)
    monkeypatch.setattr(delivery, "send_email", _boom_send_email)

    token = "tok-email-fail"
    backend_app.paper_review_pipeline.local(
        token, PDF_BYTES, "cs", tier="standard", deliver_email="buyer@example.com",
    )

    entry = backend_app.paper_jobs_dict.get(token)
    assert entry is not None
    assert entry["status"] == "done"
    # result_md now has the referral footer appended (see
    # _referral_footer_md) — assert on the original content being intact
    # rather than an exact match against the pre-footer literal.
    assert entry["result_md"].startswith("# Review\n\nfindings...")


def test_adjacent_tool_pipeline_email_failure_preserves_done_result(monkeypatch):
    import app as backend_app
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())

    from latextools import paperreview_extras, delivery

    async def _fake_run_cover_letter(client_, struct, journal_name, custom_note=""):
        return {"status": "ok", "text": "Dear Editor,\n\n..."}

    async def _boom_send_email(*args, **kwargs):
        raise RuntimeError("resend unreachable")

    monkeypatch.setattr(paperreview_extras, "run_cover_letter", _fake_run_cover_letter)
    monkeypatch.setattr(delivery, "send_email", _boom_send_email)

    token = "tok-cover-letter-email-fail"
    backend_app.adjacent_tool_pipeline.local(
        token, "cover-letter",
        title_only="A Great Paper", abstract_only="We show that...",
        journal_name="Journal of Things", deliver_email="buyer@example.com",
    )

    entry = backend_app.paper_jobs_dict.get(token)
    assert entry is not None
    assert entry["status"] == "done"
    assert entry["result_md"] == "Dear Editor,\n\n..."


# ---------------------------------------------------------------------------
# send_email() returns a {"status": "ok"|"skipped"|"error", ...} dict and
# does NOT raise for expected failure modes (missing API key, invalid
# recipient, upstream HTTP error). Callers must inspect that return value
# and log a warning -- otherwise delivery can be silently broken (e.g. no
# RESEND_API_KEY in the Modal env) with zero visibility in logs/alerts.
# ---------------------------------------------------------------------------

def test_paper_review_pipeline_logs_warning_when_email_not_sent(monkeypatch, caplog):
    import app as backend_app
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())

    from latextools import papercheck, delivery

    async def _fake_run_review_pipeline(pdf_bytes, domain, on_progress=None, **kwargs):
        return {
            "status": "done",
            "result_md": "# Review\n\nfindings...",
            "structure_summary": {"title": "A Great Paper"},
        }

    async def _skipped_send_email(*args, **kwargs):
        return {"status": "skipped", "reason": "no_api_key"}

    monkeypatch.setattr(papercheck, "run_review_pipeline", _fake_run_review_pipeline)
    monkeypatch.setattr(delivery, "send_email", _skipped_send_email)

    token = "tok-email-skipped"
    with caplog.at_level("WARNING"):
        backend_app.paper_review_pipeline.local(
            token, PDF_BYTES, "cs", tier="standard", deliver_email="buyer@example.com",
        )

    entry = backend_app.paper_jobs_dict.get(token)
    assert entry["status"] == "done"
    assert any(
        "delivery email not sent" in r.message and "skipped" in r.message
        for r in caplog.records
    )


def test_adjacent_tool_pipeline_logs_warning_when_email_not_sent(monkeypatch, caplog):
    import app as backend_app
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())

    from latextools import paperreview_extras, delivery

    async def _fake_run_cover_letter(client_, struct, journal_name, custom_note=""):
        return {"status": "ok", "text": "Dear Editor,\n\n..."}

    async def _error_send_email(*args, **kwargs):
        return {"status": "error", "reason": "invalid_email"}

    monkeypatch.setattr(paperreview_extras, "run_cover_letter", _fake_run_cover_letter)
    monkeypatch.setattr(delivery, "send_email", _error_send_email)

    token = "tok-cover-letter-email-skipped"
    with caplog.at_level("WARNING"):
        backend_app.adjacent_tool_pipeline.local(
            token, "cover-letter",
            title_only="A Great Paper", abstract_only="We show that...",
            journal_name="Journal of Things", deliver_email="buyer@example.com",
        )

    entry = backend_app.paper_jobs_dict.get(token)
    assert entry["status"] == "done"
    assert any(
        "delivery email not sent" in r.message and "error" in r.message
        for r in caplog.records
    )
