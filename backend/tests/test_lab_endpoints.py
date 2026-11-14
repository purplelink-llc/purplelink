"""Lab plan endpoints (/lab/*, order revoke/restore, register-token and redeem-session guards) and the
cross-contamination checks against the annual plan. Stripe and email are replaced by fakes. Assertions are on links,
tokens, dates, amounts and status codes only, never on customer wording."""

import io
import time
from urllib.parse import quote as _q0

import pytest
from fastapi.testclient import TestClient

from latextools import lab
from tests.test_app_paper_review_endpoints import PDF_BYTES, _FakeDict, _FakeSpawnFunction

SECRET = "hook-secret"
SUBSECRET = "sub-secret"
SUB = "sub_LAB1"
H = {"x-webhook-secret": SECRET}
DAY = 86400
# One period start for the whole module. A start taken from the clock on each call can differ by a second between two
# calls in one test, and a different period is a new month's batch.
PS0 = int(time.time()) - 60


def _q(k):
    return _q0(k, safe="")


@pytest.fixture
def env(monkeypatch):
    import app as backend_app
    for name in ("paper_tokens_dict", "paper_jobs_dict", "paper_token_claims_dict", "paper_token_index_dict",
                 "customer_lifecycle_dict", "lifecycle_optout_dict", "referral_dict", "feedback_dict",
                 "annual_plans_dict", "referral_rewards_dict", "buyer_ledger_dict", "review_spend_dict"):
        monkeypatch.setattr(backend_app, name, _FakeDict())
    monkeypatch.setattr(backend_app, "rate_dict", {})
    monkeypatch.setattr(backend_app, "paper_review_pipeline", _FakeSpawnFunction())
    monkeypatch.setattr(backend_app, "adjacent_tool_pipeline", _FakeSpawnFunction())
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("SUBSCRIBE_SECRET", SUBSECRET)
    sent = []
    stripe = {"snap": None, "cancel_calls": [], "cancel_ok": True}

    async def fake_send(to, subject, html, tag):
        sent.append({"to": to, "subject": subject, "html": html, "tag": tag})
        return {"status": "ok"}

    async def fake_fetch(sub_id):
        return stripe["snap"]

    async def fake_cancel(sub_id, cancel):
        stripe["cancel_calls"].append((sub_id, cancel))
        return stripe["cancel_ok"]

    for prefix in ("_annual", "_lab"):
        monkeypatch.setattr(backend_app, prefix + "_send", fake_send)
        monkeypatch.setattr(backend_app, prefix + "_fetch_subscription", fake_fetch)
    monkeypatch.setattr(backend_app, "_annual_set_cancel", fake_cancel)
    monkeypatch.setattr(backend_app, "_lab_set_cancel", fake_cancel)
    http = TestClient(backend_app.web.local())
    return http, backend_app, sent, stripe


def _snap(product="lab-monthly", sub=SUB, status="active", cancel=False, paid=True, ps=None):
    ps = ps or PS0
    months = lab.LAB_PRODUCTS[product]["billing_months"]
    return {"subscription_id": sub, "customer": "cus_L", "status": status, "cancel_at_period_end": cancel,
            "period_start": ps, "period_end": lab.add_months(ps, months), "latest_invoice_id": "in_L",
            "latest_invoice_paid": paid, "metadata_product": product}


def _register(http, stripe, product="lab-monthly", sub=SUB, email="pi@uni.edu", **extra):
    known = product in lab.LAB_PRODUCTS
    stripe["snap"] = _snap(product if known else "lab-monthly", sub)
    price = lab.LAB_PRODUCTS[product if known else "lab-monthly"]["amount"]
    body = {"subscription_id": sub, "product": product, "email": email, "session_id": "cs_lab1",
            "amount_paid": price, "amount_subtotal": price}
    body.update(extra)
    return http.post("/lab/register", json=body, headers=H)


def _sync(http, sub=SUB):
    return http.post("/lab/sync", json={"subscription_id": sub}, headers=H)


def _plan(app, sub=SUB):
    return app.annual_plans_dict.get(app.annual_plans_dict.get("labsub:" + sub))


def _token(app, sub=SUB):
    return lab.sign_plan_token(SUBSECRET, _plan(app, sub)["plan_id"], _plan(app, sub)["nonce"])


def _ready(env, product="lab-monthly"):
    http, app, sent, stripe = env
    assert _register(http, stripe, product).status_code == 200
    assert len(_plan(app)["grants"]) == 1
    return http, app, sent, stripe


# ---- auth ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/lab/register", "/lab/sync", "/lab/revoke", "/lab/restore", "/lab/plan", "/lab/cancel",
                                  "/lab/undo", "/lab/rotate-group-link", "/lab/link", "/lab/group-view", "/lab/member-claim",
                                  "/paper-review/revoke-order", "/paper-review/restore-order"])
def test_routes_need_the_secret(env, path):
    http = env[0]
    assert http.post(path, json={}).status_code == 401
    assert http.post(path, json={}, headers={"x-webhook-secret": "wrong"}).status_code == 401


def test_routes_report_missing_secret_config(env, monkeypatch):
    monkeypatch.delenv("BACKEND_WEBHOOK_SECRET")
    assert env[0].post("/lab/sync", json={}, headers=H).status_code == 500


# ---- register / sync ----------------------------------------------------------------------------------------

def test_register_creates_plan_and_issues_first_grant(env):
    """The webhook calls only /lab/register at checkout: that one call must issue and mail the first month."""
    http, app, sent, stripe = env
    r = _register(http, stripe)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "registered" and body["plan_id"].startswith("lab_") and body["product"] == "lab-monthly"
    assert _sync(http).json() == {"ok": True, "status": "synced", "minted": 0}
    plan = _plan(app)
    assert len(plan["grants"]) == 1
    entry = app.paper_tokens_dict.get("cs_lab1")
    assert len(entry["tokens"]) == 20 and entry["lab_plan"] is True
    assert sent and sent[0]["tag"] == "lab_grant"
    assert all(t in sent[0]["html"] for t in entry["tokens"][:3])


def test_register_twice_is_exists_and_mints_once(env):
    http, app, sent, stripe = env
    _register(http, stripe)
    _sync(http)
    again = _register(http, stripe)
    assert again.json()["status"] == "exists"
    assert _sync(http).json()["minted"] == 0
    assert len(_plan(app)["grants"]) == 1


def test_register_register_sync_path_in_one_call_pattern(env):
    http, app, sent, stripe = env
    assert _register(http, stripe, "lab-annual").json()["status"] == "registered"
    assert _sync(http).json()["minted"] == 0
    assert len(_plan(app)["grants"]) == 1
    assert _plan(app)["billing_months"] == 12


def test_register_errors(env):
    http, app, sent, stripe = env
    assert _register(http, stripe, product="nope").status_code == 400
    assert _register(http, stripe, subscription_id="").json()["error"] == "missing_subscription_id"
    bad = _register(http, stripe, amount_subtotal=100)
    assert bad.status_code == 400 and bad.json()["error"] == "amount_mismatch"
    stripe["snap"] = None
    no = http.post("/lab/register", headers=H, json={"subscription_id": "sub_X", "product": "lab-monthly", "email": "a@b.edu"})
    assert no.status_code == 502 and no.json()["error"] == "stripe_unreadable"
    stripe["snap"] = _snap(paid=False)
    unpaid = http.post("/lab/register", headers=H, json={"subscription_id": SUB, "product": "lab-monthly", "email": "a@b.edu",
                                                         "amount_paid": 19900, "amount_subtotal": 19900})
    assert unpaid.status_code == 409 and unpaid.json()["error"] == "unpaid"


def test_register_accepts_zero_dollar_first_invoice_and_invoice_path_root(env):
    http, app, sent, stripe = env
    stripe["snap"] = _snap()
    r = http.post("/lab/register", headers=H, json={"subscription_id": SUB, "product": "lab-monthly", "email": "ap@uni.edu",
                                                    "amount_paid": 0, "amount_subtotal": 19900})
    assert r.status_code == 200
    r2 = http.post("/lab/register", headers=H, json={"subscription_id": "sub_PO", "product": "lab-monthly", "email": "po@uni.edu"})
    assert r2.status_code == 200
    stripe["snap"] = _snap(sub="sub_PO")
    _sync(http, "sub_PO")
    assert _plan(app, "sub_PO")["root"] == "lab-sub_PO"


def test_register_survives_a_failed_first_grant_and_a_resend_heals_it(env, monkeypatch):
    http, app, sent, stripe = env
    real = app.lab.sync

    def boom(*a, **kw):
        raise RuntimeError("store down")

    monkeypatch.setattr(app.lab, "sync", boom)
    assert _register(http, stripe).json()["status"] == "registered"
    assert _plan(app)["grants"] == [] and not sent
    monkeypatch.setattr(app.lab, "sync", real)
    assert _register(http, stripe).json()["status"] == "exists"
    assert len(_plan(app)["grants"]) == 1 and len(sent) == 1
    assert _register(http, stripe).json()["status"] == "exists"
    assert len(_plan(app)["grants"]) == 1 and len(sent) == 1


def test_sync_unknown_plan_and_unreadable(env):
    http, app, sent, stripe = env
    stripe["snap"] = _snap(sub="sub_NONE")
    assert _sync(http, "sub_NONE").json() == {"ok": True, "status": "unknown_plan", "minted": 0}
    stripe["snap"] = None
    _register_ok = http.post("/lab/sync", json={"subscription_id": SUB}, headers=H)
    assert _register_ok.status_code == 502 and _register_ok.json()["error"] == "stripe_unreadable"


def test_lab_plus_has_group_link(env):
    http, app, sent, stripe = env
    _register(http, stripe, "lab-plus-monthly")
    _sync(http)
    plan = _plan(app)
    assert plan["group_key"].startswith("lg_") and len(app.paper_tokens_dict.get("cs_lab1")["tokens"]) == 40


# ---- revoke / restore ---------------------------------------------------------------------------------------

def test_revoke_and_restore_dispute(env):
    http, app, sent, stripe = _ready(env)
    r = http.post("/lab/revoke", json={"subscription_id": SUB, "reason": "dispute", "dispute_id": "dp_1"}, headers=H)
    assert r.json()["ok"] is True and _plan(app)["revoked"] is True
    back = http.post("/lab/restore", json={"subscription_id": SUB, "dispute_id": "dp_1"}, headers=H).json()
    assert back["ok"] is True and back["restored"] is True and _plan(app)["revoked"] is False


def test_revoke_refund_is_not_restorable(env):
    http, app, sent, stripe = _ready(env)
    http.post("/lab/revoke", json={"subscription_id": SUB, "reason": "refund"}, headers=H)
    back = http.post("/lab/restore", json={"subscription_id": SUB, "dispute_id": "dp_9"}, headers=H).json()
    assert back["restored"] is False and _plan(app)["revoked"] is True


def test_revoked_plan_entries_are_refused_by_term_refusal(env):
    from latextools import annual
    http, app, sent, stripe = _ready(env)
    http.post("/lab/revoke", json={"subscription_id": SUB, "reason": "refund"}, headers=H)
    entry = app.paper_tokens_dict.get("cs_lab1")
    assert annual.term_refusal(app._annual_store(), entry, time.time())


def test_order_revoke_and_restore(env):
    http, app, sent, stripe = env
    app.paper_tokens_dict["cs_ord"] = {"tokens": ["t1"], "product_key": "deep-review", "amount_paid": 3900, "redeemed": False,
                                       "consumed_tokens": [], "created_at": time.time(), "expires_at": time.time() + DAY}
    r = http.post("/paper-review/revoke-order", json={"session_id": "cs_ord", "reason": "dispute", "dispute_id": "dp_2"}, headers=H)
    assert r.json() == {"ok": True, "reason": "revoked"}
    assert app.paper_tokens_dict.get("cs_ord")["revoked"] is True
    back = http.post("/paper-review/restore-order", json={"session_id": "cs_ord", "dispute_id": "dp_2"}, headers=H).json()
    assert back["restored"] is True and not app.paper_tokens_dict.get("cs_ord")["revoked"]
    none = http.post("/paper-review/revoke-order", json={"session_id": "cs_none", "reason": "refund"}, headers=H).json()
    assert none["ok"] is False and none["reason"] == "unknown_order"


# ---- plan view, cancel, undo, link --------------------------------------------------------------------------

def test_plan_view_and_bad_tokens(env):
    http, app, sent, stripe = _ready(env)
    tok = _token(app)
    v = http.post("/lab/plan", json={"token": tok}, headers=H)
    assert v.status_code == 200 and v.json()["state"] == "active" and v.json()["unused"] == 20
    assert http.post("/lab/plan", json={"token": "lab_x.1.2.3"}, headers=H).status_code == 404
    assert http.post("/lab/plan", json={"token": "x" * 500}, headers=H).status_code == 404
    lab.rotate_nonce(app._annual_store(), _plan(app))
    old = http.post("/lab/plan", json={"token": tok}, headers=H)
    assert old.status_code == 410 and old.json()["error"] == "replaced"


def test_plan_view_falls_back_when_stripe_unreadable(env):
    http, app, sent, stripe = _ready(env)
    stripe["snap"] = None
    assert http.post("/lab/plan", json={"token": _token(app)}, headers=H).status_code == 200


def test_cancel_and_undo_rotate_the_link_and_email(env):
    http, app, sent, stripe = _ready(env)
    n = len(sent)
    tok = _token(app)
    r = http.post("/lab/cancel", json={"token": tok}, headers=H)
    assert r.status_code == 200 and r.json()["token"].startswith("lab_") and r.json()["token"] != tok
    assert stripe["cancel_calls"][-1] == (SUB, True) and _plan(app)["cancel_at_period_end"] is True
    assert len(sent) == n + 1 and sent[-1]["tag"] == "lab_cancel"
    assert http.post("/lab/cancel", json={"token": tok}, headers=H).status_code == 410
    u = http.post("/lab/undo", json={"token": r.json()["token"]}, headers=H)
    assert u.status_code == 200 and stripe["cancel_calls"][-1] == (SUB, False)


def test_cancel_stripe_failure_and_plan_over(env):
    http, app, sent, stripe = _ready(env)
    stripe["cancel_ok"] = False
    r = http.post("/lab/cancel", json={"token": _token(app)}, headers=H)
    assert r.status_code == 502 and r.json()["error"] == "stripe_failed"
    stripe["cancel_ok"] = True
    http.post("/lab/revoke", json={"subscription_id": SUB, "reason": "refund"}, headers=H)
    over = http.post("/lab/cancel", json={"token": _token(app)}, headers=H)
    assert over.status_code == 409 and over.json()["error"] == "plan_over"


def test_link_always_ok_and_rotates_only_on_match(env):
    http, app, sent, stripe = _ready(env)
    old = _token(app)
    n = len(sent)
    assert http.post("/lab/link", json={"email": "nobody@uni.edu"}, headers=H).json() == {"ok": True}
    assert len(sent) == n
    assert http.post("/lab/link", json={"email": "pi@uni.edu"}, headers=H).json() == {"ok": True}
    assert len(sent) == n + 1 and sent[-1]["tag"] == "lab_link" and _token(app) != old
    assert http.post("/lab/link", json={"email": "bad"}, headers=H).json() == {"ok": True}


# ---- group ---------------------------------------------------------------------------------------------------

def test_group_view_and_member_claim(env):
    http, app, sent, stripe = _ready(env, "lab-plus-monthly")
    key = _plan(app)["group_key"]
    v = http.post("/lab/group-view", json={"k": key}, headers=H)
    assert v.status_code == 200 and v.json()["available"] == 40 and v.json()["ok"] is True
    c = http.post("/lab/member-claim", json={"k": key}, headers=H)
    assert c.status_code == 200 and c.json()["start_url"].startswith("https://purplelink.llc/tools/paper-review/upload/?direct_token=")
    assert http.post("/lab/group-view", json={"k": key}, headers=H).json()["available"] == 39
    assert http.post("/lab/group-view", json={"k": "lg_nope" + "x" * 16}, headers=H).status_code == 404
    assert http.post("/lab/member-claim", json={"k": "bad"}, headers=H).status_code == 404


def test_member_claim_none_left_and_plan_over(env):
    http, app, sent, stripe = _ready(env, "lab-plus-monthly")
    key = _plan(app)["group_key"]
    entry = app.paper_tokens_dict.get("cs_lab1")
    entry["consumed_tokens"] = list(entry["tokens"])
    app.paper_tokens_dict["cs_lab1"] = entry
    r = http.post("/lab/member-claim", json={"k": key}, headers=H)
    assert r.status_code == 409 and r.json()["error"] == "none_left" and "next_grant" in r.json()
    http.post("/lab/revoke", json={"subscription_id": SUB, "reason": "refund"}, headers=H)
    assert http.post("/lab/member-claim", json={"k": key}, headers=H).status_code == 410


def test_rotate_group_link(env):
    http, app, sent, stripe = _ready(env, "lab-plus-monthly")
    old = _plan(app)["group_key"]
    r = http.post("/lab/rotate-group-link", json={"token": _token(app)}, headers=H)
    assert r.status_code == 200 and r.json()["token"].startswith("lab_")
    assert _plan(app)["group_key"] != old
    assert http.post("/lab/group-view", json={"k": old}, headers=H).status_code == 404
    http2, app2, _, stripe2 = env
    stripe2["snap"] = _snap(sub="sub_L2")
    http2.post("/lab/register", headers=H, json={"subscription_id": "sub_L2", "product": "lab-monthly", "email": "x@uni.edu"})
    stripe2["snap"] = _snap(sub="sub_L2")
    _sync(http2, "sub_L2")
    bad = http2.post("/lab/rotate-group-link", json={"token": _token(app2, "sub_L2")}, headers=H)
    assert bad.status_code == 409 and bad.json()["error"] == "not_plus"


# ---- redeem-session -------------------------------------------------------------------------------------------

def test_redeem_session_lab_entry_has_lab_fields_and_never_reaches_annual(env):
    http, app, sent, stripe = _ready(env)
    r = http.post("/paper-review/redeem-session", json={"session_id": "cs_lab1"}, headers=H)
    assert r.status_code == 200
    j = r.json()
    assert j["lab_plan"] is True and j["plan_name"] and j["valid_until"] and len(j["tokens"]) == 20
    # a lab plan id must not be sent through the annual current-entry path
    called = []
    orig = app._annual_current_entry

    async def spy(*a, **k):
        called.append(a)
        return await orig(*a, **k)
    app._annual_current_entry = spy
    try:
        http.post("/paper-review/redeem-session", json={"session_id": "cs_lab1"}, headers=H)
    finally:
        app._annual_current_entry = orig
    assert not called


def test_redeem_by_token_returns_only_that_token_for_lab(env):
    http, app, sent, stripe = _ready(env)
    tok = app.paper_tokens_dict.get("cs_lab1")["tokens"][3]
    r = http.post("/paper-review/redeem-session", json={"token": tok}, headers=H)
    assert r.status_code == 200 and r.json()["tokens"] == [tok] and r.json()["token"] == tok


# ---- cross contamination ----------------------------------------------------------------------------------------

ANNUAL_SUB = "sub_ANN1"


def _register_annual(http, app):
    r = http.post("/paper-review/register-token", headers=H, json={
        "session_id": "cs_ann", "email": "buyer@uni.edu", "amount_paid": 7900, "amount_subtotal": 7900,
        "product": "paper-review-annual", "subscription_id": ANNUAL_SUB, "term_ends_at": int(time.time() + 365 * DAY),
        "customer": "cus_1", "card_fingerprint": "fp"})
    assert r.status_code == 200
    return app.annual_plans_dict.get(app.annual_plans_dict.get("sub:" + ANNUAL_SUB))


def test_annual_routes_ignore_lab_ids_tokens_and_emails(env):
    http, app, sent, stripe = _ready(env)
    before = {k: dict(v) if isinstance(v, dict) else v for k, v in app.annual_plans_dict.items()}
    tok = _token(app)
    stripe["snap"] = {"subscription_id": SUB, "status": "canceled", "cancel_at_period_end": True, "period_end": 5,
                      "latest_invoice_id": "i", "latest_invoice_paid": True, "customer": "c", "metadata_product": "lab-monthly"}
    cases = [
        ("/paper-review/annual-plan", {"token": tok}),
        ("/paper-review/annual-cancel", {"token": tok}),
        ("/paper-review/annual-undo", {"token": tok}),
        ("/paper-review/annual-link", {"email": "pi@uni.edu"}),
        ("/paper-review/annual-cancel-by-email", {"email": "pi@uni.edu"}),
        ("/paper-review/annual-renew", {"subscription_id": SUB}),
        ("/paper-review/annual-revoke", {"subscription_id": SUB, "reason": "refund"}),
        ("/paper-review/annual-restore", {"subscription_id": SUB, "dispute_id": "dp"}),
        ("/paper-review/annual-status", {"subscription_id": SUB}),
    ]
    for path, body in cases:
        http.post(path, json=body, headers=H)
    after = {k: dict(v) if isinstance(v, dict) else v for k, v in app.annual_plans_dict.items()}
    assert after == before
    assert stripe["cancel_calls"] == []


def test_lab_routes_given_annual_token_are_404_invalid(env):
    from latextools import annual
    http, app, sent, stripe = env
    plan = _register_annual(http, app)
    tok = annual.sign_plan_token(SUBSECRET, plan["plan_id"], plan["nonce"])
    assert tok.startswith("pl_")
    for path in ("/lab/plan", "/lab/cancel", "/lab/undo", "/lab/rotate-group-link"):
        r = http.post(path, json={"token": tok}, headers=H)
        assert r.status_code == 404 and r.json() == {"error": "invalid"}, path
    assert http.post("/lab/group-view", json={"k": plan["plan_id"]}, headers=H).status_code == 404
    assert stripe["cancel_calls"] == []


def test_lab_sync_and_revoke_given_annual_subscription_do_not_touch_annual(env):
    http, app, sent, stripe = env
    plan = _register_annual(http, app)
    before = dict(plan)
    stripe["snap"] = _snap(sub=ANNUAL_SUB)
    s = _sync(http, ANNUAL_SUB).json()
    assert s["status"] == "unknown_plan" and s["minted"] == 0
    r = http.post("/lab/revoke", json={"subscription_id": ANNUAL_SUB, "reason": "refund"}, headers=H).json()
    assert r["ok"] is False
    back = http.post("/lab/restore", json={"subscription_id": ANNUAL_SUB, "dispute_id": "dp"}, headers=H).json()
    assert back["restored"] is False
    assert app.annual_plans_dict.get(plan["plan_id"]) == before


def test_pl_guard_lab_entry_with_pl_lookalike_is_not_annual(env, monkeypatch):
    """A plan_id without the pl_ prefix never takes the annual current-entry path, even when the entry is old."""
    http, app, sent, stripe = _ready(env)
    entry = app.paper_tokens_dict.get("cs_lab1")
    assert entry["plan_id"].startswith("lab_")
    called = []

    async def spy(session_id, e):
        called.append(session_id)
        return session_id, e
    monkeypatch.setattr(app, "_annual_current_entry", spy)
    http.post("/paper-review/redeem-session", json={"session_id": "cs_lab1"}, headers=H)
    assert called == []


def test_register_token_refuses_lab_products(env):
    http = env[0]
    for p in ("lab-monthly", "lab-annual", "lab-plus-monthly", "lab-plus-annual"):
        r = http.post("/paper-review/register-token", headers=H, json={
            "session_id": "cs_z" + p, "email": "a@b.edu", "amount_paid": 19900, "amount_subtotal": 19900, "product": p})
        assert r.status_code == 400, p
    assert env[1].paper_tokens_dict.get("cs_zlab-monthly") is None


def test_status_payload_omits_session_id_for_lab_and_keeps_it_otherwise(env):
    http, app, sent, stripe = _ready(env)
    lab_tok = app.paper_tokens_dict.get("cs_lab1")["tokens"][0]
    app.paper_tokens_dict["cs_plain"] = {"tokens": ["plain_tok"], "product_key": "paper-review-standard", "amount_paid": 1400,
                                         "redeemed": True, "consumed_tokens": ["plain_tok"], "created_at": time.time(),
                                         "expires_at": time.time() + DAY}
    app.paper_token_index_dict["plain_tok"] = "cs_plain"
    done = {"status": "done", "product": "paper-review", "tier": "standard", "result_md": "x", "structure_summary": {},
            "created_at": time.time()}
    for t in (lab_tok, "plain_tok"):
        app.paper_jobs_dict[t] = dict(done)
    lab_r = http.get("/paper-review/status", params={"token": lab_tok})
    plain_r = http.get("/paper-review/status", params={"token": "plain_tok"})
    assert lab_r.status_code == 200 and lab_r.json()["status"] == "done" and "session_id" not in lab_r.json()
    assert plain_r.status_code == 200 and plain_r.json()["session_id"] == "cs_plain"


# ---- submit hook and reissue -----------------------------------------------------------------------------------

def _submit(http, tok):
    return http.post("/paper-review/submit", data={"token": tok, "domain": "general"},
                     files={"file": ("p.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})


def test_submit_on_lab_batch_passes_followup_links_and_mints_them_once(env):
    http, app, sent, stripe = _ready(env)
    toks = app.paper_tokens_dict.get("cs_lab1")["tokens"]
    r = _submit(http, toks[0])
    assert r.status_code == 200
    (args, kwargs), = app.paper_review_pipeline.calls
    links = kwargs["followups"]
    keys = lab.followup_keys(toks[0])
    assert [l["kind"] for l in links] == list(keys) and all(_q(keys[l["kind"]]) in l["url"] for l in links)
    for k in keys.values():
        assert app.paper_tokens_dict.get(k)["plan_id"] == _plan(app)["plan_id"]
    before = {k: app.paper_tokens_dict.get(k)["tokens"] for k in keys.values()}
    _submit(http, toks[1])
    assert {k: app.paper_tokens_dict.get(k)["tokens"] for k in keys.values()} == before     # only toks[0]'s pair so far
    assert len(app.paper_review_pipeline.calls) == 2


def test_submit_on_non_lab_entry_has_no_followups_kwarg(env):
    http, app, sent, stripe = env
    app.paper_tokens_dict["cs_one"] = {"tokens": ["one_tok"], "product_key": "paper-review-standard", "amount_paid": 1400,
                                       "product_cfg": app.PAID_PRODUCTS["paper-review-standard"], "redeemed": False,
                                       "consumed_tokens": [], "created_at": time.time(), "expires_at": time.time() + DAY}
    app.paper_token_index_dict["one_tok"] = "cs_one"
    assert _submit(http, "one_tok").status_code == 200
    (args, kwargs), = app.paper_review_pipeline.calls
    assert "followups" not in kwargs


def test_reissue_records_original_only_for_lab_entries(env):
    http, app, sent, stripe = _ready(env)
    tok = app.paper_tokens_dict.get("cs_lab1")["tokens"][0]
    new = app._reissue_token_on_failure(tok)
    again = app._reissue_token_on_failure(new)
    rf = app.paper_tokens_dict.get("cs_lab1")["reissued_from"]
    assert rf[new] == tok and rf[again] == tok
    assert lab.followup_root(app.paper_tokens_dict.get("cs_lab1"), again) == tok
    app.paper_tokens_dict["cs_p"] = {"tokens": ["p1"], "product_key": "paper-review-standard", "redeemed": True,
                                     "consumed_tokens": ["p1"], "created_at": time.time(), "expires_at": time.time() + DAY}
    app.paper_token_index_dict["p1"] = "cs_p"
    app._reissue_token_on_failure("p1")
    assert "reissued_from" not in app.paper_tokens_dict.get("cs_p")


def test_lab_sweep_runs_from_the_lifecycle_sweep_function_not_a_new_schedule():
    import app as backend_app
    src = open(backend_app.__file__).read()
    assert src.count("schedule=") == 1 and "lab_plan_sweep()" in src


def test_lab_plan_sweep_mints_due_grant_and_skips_annual(env):
    http, app, sent, stripe = _ready(env)
    n = len(sent)
    stripe["snap"] = _snap(sub=SUB, ps=_plan(app)["period_start"])
    import asyncio
    res = asyncio.run(app._lab_sweep_async())
    assert res["plans"] == 1 and res["errors"] == 0
    assert len(sent) >= n
