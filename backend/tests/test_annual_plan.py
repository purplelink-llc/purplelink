"""Paper Review annual plan (Part D): register, renew once, revoke, term refusal, status, cancel and undo,
plan link, reminders, referral reward. Stripe and email are replaced by fakes: nothing here touches the network."""

import asyncio
import io
import time

import pytest
from fastapi.testclient import TestClient

from tests.test_app_paper_review_endpoints import PDF_BYTES, _FakeDict, _FakeSpawnFunction

SECRET = "hook-secret"
SUB = "sub_TEST1"
DAY = 86400


@pytest.fixture
def env(monkeypatch):
    import app as backend_app
    for name in ("paper_tokens_dict", "paper_jobs_dict", "paper_token_claims_dict", "paper_token_index_dict",
                 "customer_lifecycle_dict", "lifecycle_optout_dict", "referral_dict", "feedback_dict",
                 "annual_plans_dict"):
        monkeypatch.setattr(backend_app, name, _FakeDict())
    monkeypatch.setattr(backend_app, "rate_dict", {})
    monkeypatch.setattr(backend_app, "paper_review_pipeline", _FakeSpawnFunction())
    monkeypatch.setattr(backend_app, "adjacent_tool_pipeline", _FakeSpawnFunction())
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("SUBSCRIBE_SECRET", "sub-secret")
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

    monkeypatch.setattr(backend_app, "_annual_send", fake_send)
    monkeypatch.setattr(backend_app, "_annual_fetch_subscription", fake_fetch)
    monkeypatch.setattr(backend_app, "_annual_set_cancel", fake_cancel)
    http = TestClient(backend_app.web.local())
    return http, backend_app, sent, stripe


H = {"x-webhook-secret": SECRET}


def _snap(period_end, status="active", cancel=False, paid=True, sub=SUB):
    return {"subscription_id": sub, "status": status, "cancel_at_period_end": cancel, "period_end": period_end,
            "latest_invoice_id": "in_1", "latest_invoice_paid": paid, "customer": "cus_1", "metadata_product": "paper-review-annual"}


def _register(http, session="cs_a1", email="buyer@uni.edu", period_end=None, **extra):
    body = {"session_id": session, "email": email, "amount_paid": 7900, "amount_subtotal": 7900,
            "product": "paper-review-annual", "subscription_id": SUB, "term_ends_at": period_end or int(time.time() + 365 * DAY),
            "customer": "cus_1", "card_fingerprint": "fp_buyer"}
    body.update(extra)
    return http.post("/paper-review/register-token", json=body, headers=H)


def _plan(backend_app):
    return backend_app.annual_plans_dict.get(backend_app.annual_plans_dict.get("sub:" + SUB))


def _token(backend_app):
    from latextools import annual
    return annual.sign_plan_token("sub-secret", _plan(backend_app)["plan_id"], _plan(backend_app)["nonce"])


# ---- register ----------------------------------------------------------------------------------------------

def test_register_mints_twelve_and_emails_plan_without_lifecycle(env):
    http, app, sent, _ = env
    r = _register(http)
    assert r.status_code == 200 and len(r.json()["tokens"]) == 12
    entry = app.paper_tokens_dict.get("cs_a1")
    assert entry["term_ends_at"] and entry["expires_at"] == 0 and entry["plan_id"]
    assert app.customer_lifecycle_dict.get("cs_a1") is None          # no lifecycle seeding
    assert len(sent) == 1 and sent[0]["tag"] == "annual_welcome"
    assert "reply to this message with the word cancel" in sent[0]["html"]
    assert "/tools/paper-review/plan/?t=pl_" in sent[0]["html"]


def test_register_rejects_missing_subscription_and_bad_amount(env):
    http, app, _, _ = env
    assert _register(http, subscription_id="").status_code == 400
    bad = http.post("/paper-review/register-token", headers=H, json={
        "session_id": "cs_x", "email": "a@b.edu", "amount_paid": 7900, "amount_subtotal": 5000,
        "product": "paper-review-annual", "subscription_id": SUB, "term_ends_at": int(time.time() + DAY)})
    assert bad.status_code == 400 and bad.json()["error"] == "amount_mismatch"


def test_register_is_idempotent_on_the_session(env):
    http, app, sent, _ = env
    first = _register(http).json()["tokens"]
    again = _register(http)
    assert again.json()["status"] == "exists" and again.json()["tokens"] == first
    assert len(sent) == 1


def test_annual_buyer_gets_no_edu_referral_credit(env):
    http, app, _, _ = env
    app.referral_dict["CODE1"] = "friend@uni.edu"
    credited = []

    async def fake_credit(*a, **k):
        credited.append(a)
    app._credit_referral = fake_credit
    _register(http, referral_code="CODE1")
    assert credited == []
    assert _plan(app)["referral"]["state"] == "pending"


# ---- renewal ------------------------------------------------------------------------------------------------

def test_double_renew_mints_once(env):
    http, app, sent, stripe = env
    _register(http)
    old_end = _plan(app)["period_end"]
    stripe["snap"] = _snap(old_end + 365 * DAY)
    r1 = http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H)
    r2 = http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H)
    assert r1.json()["minted"] is True and r2.json()["minted"] is False
    plan = _plan(app)
    assert len(plan["periods"]) == 2
    renewed = [m for m in sent if m["tag"] == "annual_renewed"]
    assert len(renewed) == 1
    new_entry = app.paper_tokens_dict.get(plan["period_key"])
    assert len(new_entry["tokens"]) == 12 and new_entry["term_ends_at"] == old_end + 365 * DAY


def test_concurrent_claim_loser_mints_nothing(env):
    """The atomic claim is what two simultaneous callers race on: with the claim already held, no second mint."""
    http, app, _, stripe = env
    _register(http)
    end = _plan(app)["period_end"] + 365 * DAY
    app.paper_token_claims_dict.put(f"annual:{SUB}:{end}", 1)
    stripe["snap"] = _snap(end)
    r = http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H)
    assert r.json()["minted"] is False and len(_plan(app)["periods"]) == 1


def test_renew_requires_active_and_paid(env):
    http, app, _, stripe = env
    _register(http)
    end = _plan(app)["period_end"] + 365 * DAY
    stripe["snap"] = _snap(end, status="past_due")
    assert http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H).json()["minted"] is False
    stripe["snap"] = _snap(end, paid=False)
    assert http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H).json()["minted"] is False
    assert len(_plan(app)["periods"]) == 1


def test_renew_unreadable_stripe_is_502_so_webhook_retries(env):
    http, app, _, stripe = env
    _register(http)
    stripe["snap"] = None
    assert http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H).status_code == 502


def test_renew_requires_secret(env):
    http, *_ = env
    assert http.post("/paper-review/annual-renew", json={"subscription_id": SUB}).status_code == 401


def test_renewal_retires_last_years_unused_tokens(env):
    http, app, _, stripe = env
    toks = _register(http).json()["tokens"]
    stripe["snap"] = _snap(_plan(app)["period_end"] + 365 * DAY)
    http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H)
    assert app.paper_token_index_dict.get(toks[0]) is None
    r = http.post("/paper-review/submit", data={"token": toks[0], "domain": "general"},
                  files={"file": ("p.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})
    assert r.status_code == 410 or r.status_code == 404


# ---- term and revoked refusal ---------------------------------------------------------------------------------

def _submit(http, tok):
    return http.post("/paper-review/submit", data={"token": tok, "domain": "general"},
                     files={"file": ("p.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})


def test_expired_term_is_refused_at_redeem_and_submit(env):
    http, app, _, stripe = env
    toks = _register(http).json()["tokens"]
    entry = app.paper_tokens_dict.get("cs_a1")
    entry["term_ends_at"] = time.time() - 10
    app.paper_tokens_dict["cs_a1"] = entry
    plan = _plan(app)
    plan["period_end"] = time.time() - 10
    app.annual_plans_dict[plan["plan_id"]] = plan
    stripe["snap"] = None      # Stripe cannot confirm a renewal
    r = http.post("/paper-review/redeem-session", json={"session_id": "cs_a1"})
    assert r.status_code == 410 and r.json()["error"] == "expired"
    r = http.post("/paper-review/redeem-session", json={"token": toks[0]})
    assert r.status_code == 410
    assert _submit(http, toks[0]).status_code == 410


def test_redeem_session_follows_the_current_year_after_renewal(env):
    http, app, _, stripe = env
    _register(http)
    stripe["snap"] = _snap(_plan(app)["period_end"] + 365 * DAY)
    http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H)
    new_tokens = app.paper_tokens_dict.get(_plan(app)["period_key"])["tokens"]
    r = http.post("/paper-review/redeem-session", json={"session_id": "cs_a1"})
    assert r.status_code == 200 and r.json()["tokens"] == new_tokens


def test_lazy_path_renews_when_webhook_was_missed(env):
    http, app, _, stripe = env
    _register(http)
    old_end = _plan(app)["period_end"]
    entry = app.paper_tokens_dict.get("cs_a1")
    entry["term_ends_at"] = time.time() - 5
    app.paper_tokens_dict["cs_a1"] = entry
    plan = _plan(app)
    plan["period_end"] = time.time() - 5
    app.annual_plans_dict[plan["plan_id"]] = plan
    stripe["snap"] = _snap(old_end + 365 * DAY)
    r = http.post("/paper-review/redeem-session", json={"session_id": "cs_a1"})
    assert r.status_code == 200, r.json()
    assert len(_plan(app)["periods"]) == 2


def test_refund_then_revoke_refuses_everything(env):
    http, app, _, stripe = env
    toks = _register(http).json()["tokens"]
    r = http.post("/paper-review/annual-revoke", json={"subscription_id": SUB, "reason": "refund"}, headers=H)
    assert r.json()["ok"] is True and r.json()["dropped"] == 12
    assert _plan(app)["revoked"] is True
    assert http.post("/paper-review/redeem-session", json={"session_id": "cs_a1"}).json()["error"] == "revoked"
    assert http.post("/paper-review/redeem-session", json={"token": toks[0]}).status_code == 410
    s = _submit(http, toks[0])
    assert s.status_code == 410 and s.json()["error"] == "revoked"
    # a later renewal does not revive a revoked plan
    stripe["snap"] = _snap(_plan(app)["period_end"] + 365 * DAY)
    assert http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H).json()["minted"] is False


def test_revoke_unknown_subscription_is_not_ok(env):
    http, *_ = env
    r = http.post("/paper-review/annual-revoke", json={"subscription_id": "sub_nope"}, headers=H)
    assert r.json()["ok"] is False



def _revoke(http, reason, dispute_id=""):
    body = {"subscription_id": SUB, "reason": reason}
    if dispute_id:
        body["dispute_id"] = dispute_id
    return http.post("/paper-review/annual-revoke", json=body, headers=H)


def _restore(http, dispute_id):
    return http.post("/paper-review/annual-restore", json={"subscription_id": SUB, "dispute_id": dispute_id}, headers=H)


def test_won_dispute_restores_the_plan_and_its_unused_reviews(env):
    http, app, _, _ = env
    toks = _register(http).json()["tokens"]
    _revoke(http, "dispute", "dp_1")
    assert http.post("/paper-review/redeem-session", json={"token": toks[0]}).status_code == 410
    r = _restore(http, "dp_1").json()
    assert r == {"ok": True, "reason": "restored", "restored": 12}
    assert _plan(app)["revoked"] is False and _plan(app)["cancel_at_period_end"] is False
    assert http.post("/paper-review/redeem-session", json={"token": toks[0]}).status_code == 200
    # a repeat of the same webhook changes nothing
    assert _restore(http, "dp_1").json()["reason"] == "not_revoked"


def test_won_dispute_never_undoes_a_refund(env):
    http, app, _, _ = env
    _register(http)
    _revoke(http, "dispute", "dp_1")
    _revoke(http, "refund")
    assert _restore(http, "dp_1").json()["reason"] == "refunded"
    assert _plan(app)["revoked"] is True


def test_plan_stays_revoked_while_another_dispute_is_open(env):
    http, app, _, _ = env
    _register(http)
    _revoke(http, "dispute", "dp_1")
    _revoke(http, "dispute", "dp_2")
    assert _restore(http, "dp_1").json()["reason"] == "disputes_still_open"
    assert _plan(app)["revoked"] is True
    assert _restore(http, "dp_2").json()["reason"] == "restored"


def test_restore_keeps_a_cancel_made_before_the_dispute(env):
    http, app, _, _ = env
    _register(http)
    _status(http, status="active", cancel_at_period_end=True)
    _revoke(http, "dispute", "dp_1")
    _restore(http, "dp_1")
    assert _plan(app)["cancel_at_period_end"] is True


def test_restore_needs_the_secret(env):
    http, *_ = env
    _register(http)
    assert http.post("/paper-review/annual-restore", json={"subscription_id": SUB, "dispute_id": "dp_1"}).status_code == 401
    assert http.post("/paper-review/annual-restore", json={"dispute_id": "dp_1"}, headers=H).status_code == 400

def test_ordinary_purchases_are_not_affected(env):
    from latextools import annual
    _, app, _, _ = env
    assert annual.term_refusal(app._annual_store(), {"expires_at": 0, "tokens": ["a"]}, time.time()) is None


# ---- subscription.updated -> annual-status ------------------------------------------------------------------

def _status(http, **kw):
    body = {"subscription_id": SUB}
    body.update(kw)
    return http.post("/paper-review/annual-status", json=body, headers=H)


def test_portal_cancel_marks_the_plan_and_undo_clears_it(env):
    http, app, _, _ = env
    _register(http)
    assert _status(http, status="active", cancel_at_period_end=True).json()["changed"] is True
    assert _plan(app)["cancel_at_period_end"] is True
    _status(http, status="active", cancel_at_period_end=False)
    assert _plan(app)["cancel_at_period_end"] is False


def test_status_for_unknown_subscription_is_ignored(env):
    http, *_ = env
    r = http.post("/paper-review/annual-status", headers=H, json={"subscription_id": "sub_other", "status": "active", "cancel_at_period_end": True})
    assert r.json() == {"ok": False, "changed": False}


def test_past_due_grants_nothing(env):
    http, app, _, stripe = env
    _register(http)
    before = _plan(app)["period_end"]
    _status(http, status="past_due", cancel_at_period_end=False)
    plan = _plan(app)
    assert plan["status"] == "past_due" and plan["period_end"] == before and len(plan["periods"]) == 1
    stripe["snap"] = _snap(before + 365 * DAY, status="past_due")
    assert http.post("/paper-review/annual-renew", json={"subscription_id": SUB}, headers=H).json()["minted"] is False


def test_deleted_status_ends_the_plan(env):
    http, app, _, _ = env
    _register(http)
    _status(http, status="canceled")
    from latextools import annual
    assert annual.plan_view(app._annual_store(), _plan(app), time.time())["state"] == "ended"


# ---- plan page: token, cancel, undo, link ------------------------------------------------------------------

def test_plan_read_changes_nothing(env):
    http, app, sent, stripe = env
    _register(http)
    stripe["snap"] = _snap(_plan(app)["period_end"])
    n = len(sent)
    r = http.post("/paper-review/annual-plan", json={"token": _token(app)}, headers=H)
    assert r.status_code == 200 and r.json()["state"] == "active" and r.json()["unused"] == 12
    assert _plan(app)["cancel_at_period_end"] is False and stripe["cancel_calls"] == [] and len(sent) == n


def test_plan_read_picks_up_a_portal_cancel_from_stripe(env):
    http, app, _, stripe = env
    _register(http)
    stripe["snap"] = _snap(_plan(app)["period_end"], cancel=True)
    r = http.post("/paper-review/annual-plan", json={"token": _token(app)}, headers=H)
    assert r.json()["state"] == "cancelling"


def test_bad_or_expired_token_is_refused(env):
    from latextools import annual
    http, app, *_ = env
    _register(http)
    assert http.post("/paper-review/annual-plan", json={"token": "junk"}, headers=H).status_code == 404
    old = annual.sign_plan_token("sub-secret", _plan(app)["plan_id"], _plan(app)["nonce"], now=time.time() - 61 * DAY)
    assert http.post("/paper-review/annual-plan", json={"token": old}, headers=H).status_code == 404
    forged = annual.sign_plan_token("other-secret", _plan(app)["plan_id"], _plan(app)["nonce"])
    assert http.post("/paper-review/annual-plan", json={"token": forged}, headers=H).status_code == 404


def test_cancel_rotates_nonce_emails_and_undo_restores(env):
    http, app, sent, stripe = env
    _register(http)
    stripe["snap"] = _snap(_plan(app)["period_end"])
    tok = _token(app)
    r = http.post("/paper-review/annual-cancel", json={"token": tok}, headers=H)
    assert r.status_code == 200 and r.json()["state"] == "cancelling"
    assert stripe["cancel_calls"] == [(SUB, True)]
    assert sent[-1]["tag"] == "annual_cancel" and "Undo the cancellation" in sent[-1]["html"]
    # the old link is replaced
    assert http.post("/paper-review/annual-plan", json={"token": tok}, headers=H).status_code == 410
    new = r.json()["token"]
    u = http.post("/paper-review/annual-undo", json={"token": new}, headers=H)
    assert u.status_code == 200 and u.json()["state"] == "active"
    assert stripe["cancel_calls"][-1] == (SUB, False)
    assert sent[-1]["tag"] == "annual_undo"


def test_cancel_failure_at_stripe_changes_nothing(env):
    http, app, sent, stripe = env
    _register(http)
    stripe["cancel_ok"] = False
    n = len(sent)
    r = http.post("/paper-review/annual-cancel", json={"token": _token(app)}, headers=H)
    assert r.status_code == 502 and _plan(app)["cancel_at_period_end"] is False and len(sent) == n


def test_cancel_a_revoked_plan_is_refused(env):
    http, app, *_ = env
    _register(http)
    tok = _token(app)
    http.post("/paper-review/annual-revoke", json={"subscription_id": SUB}, headers=H)
    # revoke rotates the nonce, so the old link is replaced
    assert http.post("/paper-review/annual-cancel", json={"token": tok}, headers=H).status_code == 410


def test_operator_cancel_by_email_matches_and_confirms(env):
    http, app, sent, stripe = env
    _register(http, email="Buyer+x@uni.edu")
    stripe["snap"] = _snap(_plan(app)["period_end"])
    tok = _token(app)
    miss = http.post("/paper-review/annual-cancel-by-email", json={"email": "nobody@x.org"}, headers=H)
    assert miss.status_code == 200 and miss.json() == {"matched": False} and stripe["cancel_calls"] == []
    r = http.post("/paper-review/annual-cancel-by-email", json={"email": "buyer@uni.edu"}, headers=H)
    assert r.status_code == 200 and r.json()["matched"] is True and r.json()["already"] is False
    assert stripe["cancel_calls"] == [(SUB, True)] and _plan(app)["cancel_at_period_end"] is True
    assert sent[-1]["tag"] == "annual_cancel" and "Undo the cancellation" in sent[-1]["html"]
    assert http.post("/paper-review/annual-plan", json={"token": tok}, headers=H).status_code == 410
    again = http.post("/paper-review/annual-cancel-by-email", json={"email": "buyer@uni.edu"}, headers=H)
    assert again.json()["already"] is True and len(stripe["cancel_calls"]) == 1


def test_operator_cancel_by_email_needs_the_secret(env):
    http, *_ = env
    _register(http)
    assert http.post("/paper-review/annual-cancel-by-email", json={"email": "buyer@uni.edu"}).status_code == 401
    assert http.post("/paper-review/annual-cancel-by-email", json={"email": "nope"}, headers=H).status_code == 400


def test_link_request_is_enumeration_safe_and_rotates(env):
    http, app, sent, _ = env
    _register(http, email="Buyer+x@uni.edu")
    tok = _token(app)
    unknown = http.post("/paper-review/annual-link", json={"email": "nobody@x.org"}, headers=H)
    known = http.post("/paper-review/annual-link", json={"email": "buyer@uni.edu"}, headers=H)
    assert unknown.json() == known.json() == {"ok": True}
    assert [m["tag"] for m in sent].count("annual_link") == 1
    assert http.post("/paper-review/annual-plan", json={"token": tok}, headers=H).status_code == 410


# ---- reminders ----------------------------------------------------------------------------------------------

def _sweep(app, now=None):
    return asyncio.run(app._annual_sweep_async()) if now is None else None


def test_reminders_30_then_7_once_each(env):
    http, app, sent, stripe = env
    _register(http)
    plan = _plan(app)
    plan["period_end"] = int(time.time() + 29 * DAY)
    app.annual_plans_dict[plan["plan_id"]] = plan
    stripe["snap"] = _snap(plan["period_end"])
    asyncio.run(app._annual_sweep_async())
    asyncio.run(app._annual_sweep_async())
    assert [m["tag"] for m in sent].count("annual_reminder_30") == 1
    plan = _plan(app)
    plan["period_end"] = int(time.time() + 6 * DAY)
    app.annual_plans_dict[plan["plan_id"]] = plan
    stripe["snap"] = _snap(plan["period_end"])
    asyncio.run(app._annual_sweep_async())
    asyncio.run(app._annual_sweep_async())
    assert [m["tag"] for m in sent].count("annual_reminder_7") == 1


def test_reminder_skips_cancelled_plans(env):
    http, app, sent, stripe = env
    _register(http)
    plan = _plan(app)
    plan["period_end"] = int(time.time() + 20 * DAY)
    plan["cancel_at_period_end"] = True
    app.annual_plans_dict[plan["plan_id"]] = plan
    stripe["snap"] = _snap(plan["period_end"], cancel=True)
    out = asyncio.run(app._annual_sweep_async())
    assert not [m for m in sent if m["tag"].startswith("annual_reminder")] and out["skipped_cancelled"] == 1


def test_reminder_rereads_stripe_and_skips_a_portal_cancel_we_missed(env):
    http, app, sent, stripe = env
    _register(http)
    plan = _plan(app)
    plan["period_end"] = int(time.time() + 20 * DAY)
    app.annual_plans_dict[plan["plan_id"]] = plan
    stripe["snap"] = _snap(plan["period_end"], cancel=True)       # stored plan says not cancelled; Stripe says it is
    asyncio.run(app._annual_sweep_async())
    assert not [m for m in sent if m["tag"].startswith("annual_reminder")]


def test_reminder_does_not_send_blind_when_stripe_is_down(env):
    http, app, sent, stripe = env
    _register(http)
    plan = _plan(app)
    plan["period_end"] = int(time.time() + 20 * DAY)
    app.annual_plans_dict[plan["plan_id"]] = plan
    stripe["snap"] = None
    out = asyncio.run(app._annual_sweep_async())
    assert out["errors"] == 1 and not [m for m in sent if m["tag"].startswith("annual_reminder")]


def test_reminder_goes_to_marketing_opt_outs(env):
    http, app, sent, stripe = env
    _register(http)
    app.lifecycle_optout_dict["buyer@uni.edu"] = True
    plan = _plan(app)
    plan["period_end"] = int(time.time() + 20 * DAY)
    app.annual_plans_dict[plan["plan_id"]] = plan
    stripe["snap"] = _snap(plan["period_end"])
    asyncio.run(app._annual_sweep_async())
    assert [m["tag"] for m in sent].count("annual_reminder_30") == 1
    html = [m for m in sent if m["tag"] == "annual_reminder_30"][0]["html"]
    assert "Cancel renewal" in html and "reply to this message with the word cancel" in html


def test_sweep_picks_up_a_missed_renewal(env):
    http, app, sent, stripe = env
    _register(http)
    stripe["snap"] = _snap(_plan(app)["period_end"] + 365 * DAY)
    out = asyncio.run(app._annual_sweep_async())
    assert out["renewed"] == 1 and len(_plan(app)["periods"]) == 2


# ---- referral reward ----------------------------------------------------------------------------------------

def _referred(http, app, *, email="buyer@uni.edu", fp="fp_buyer", paid=7900, referrer="friend@other.edu", code="C1"):
    app.referral_dict[code] = referrer
    r = _register(http, email=email, card_fingerprint=fp, referral_code=code, amount_paid=paid,
                  amount_subtotal=7900)
    assert r.status_code == 200
    plan = _plan(app)
    return plan


def _run_due(app, plan, days=15, stripe=None):
    now = time.time() + days * DAY
    from latextools import annual
    sent = []

    async def send(**kw):
        sent.append(kw)
        return {"status": "ok"}

    async def fetch(_):
        return None

    async def renewed(_):
        pass
    out = asyncio.run(annual.run_sweep(
        app._annual_store(), now=now, secret="sub-secret", cfg=app.PAID_PRODUCTS["paper-review-annual"],
        gen_token=app._annual_gen_token, canonical_email=app._buddy_canonical_email,
        fetch_subscription=fetch, send_email=send, on_renewed=renewed))
    return out, sent


def test_referral_reward_pays_six_after_fourteen_days(env):
    http, app, _, _ = env
    plan = _referred(http, app)
    out, sent = _run_due(app, plan, days=10)
    assert out["rewards"] == 0 and _plan(app)["referral"]["state"] == "pending"      # not due yet
    out, sent = _run_due(app, plan, days=15)
    assert out["rewards"] == 1 and _plan(app)["referral"]["state"] == "paid"
    entry = app.paper_tokens_dict.get("reward-" + plan["plan_id"])
    assert len(entry["tokens"]) == 6 and entry["product_cfg"]["bundled_journal"] and entry["expires_at"] == 0
    assert sent[0]["to"] == "friend@other.edu"
    out2, _ = _run_due(app, plan, days=16)
    assert out2["rewards"] == 0                                                         # one reward per referred buyer


@pytest.mark.parametrize("label,kwargs", [
    ("same email modulo dots and tags", {"email": "b.uyer+x@gmail.com", "referrer": "buyer@gmail.com"}),
    ("same card", {"fp": "fp_ref"}),
    ("100 percent promo", {"paid": 0}),
])
def test_referral_reward_rejected(env, label, kwargs):
    http, app, _, _ = env
    if label == "same card":
        ref_plan_sub = "sub_REF"
        app.referral_dict["C0"] = "x@y.org"
        http.post("/paper-review/register-token", headers=H, json={
            "session_id": "cs_ref", "email": "friend@other.edu", "amount_paid": 7900, "amount_subtotal": 7900,
            "product": "paper-review-annual", "subscription_id": ref_plan_sub, "term_ends_at": int(time.time() + 300 * DAY),
            "card_fingerprint": "fp_ref"})
    plan = _referred(http, app, **kwargs)
    out, sent = _run_due(app, plan, days=15)
    assert out["rewards"] == 0 and out["reward_rejected"] >= 1
    assert _plan(app)["referral"]["state"] == "rejected" and sent == []


def test_referral_reward_rejected_when_refunded(env):
    http, app, _, _ = env
    plan = _referred(http, app)
    http.post("/paper-review/annual-revoke", json={"subscription_id": SUB, "reason": "dispute"}, headers=H)
    out, _ = _run_due(app, plan, days=15)
    assert out["rewards"] == 0 and _plan(app)["referral"]["reason"] == "refunded_or_disputed"


def test_referral_cap_five_per_referrer_per_year(env):
    from latextools import annual
    http, app, _, _ = env
    plan = _referred(http, app)
    import datetime
    year = datetime.datetime.fromtimestamp(time.time() + 15 * DAY, datetime.timezone.utc).year
    app.annual_plans_dict[f"reward:friend@other.edu:{year}"] = 5
    out, _ = _run_due(app, plan, days=15)
    assert out["rewards"] == 0 and _plan(app)["referral"]["reason"] == "referrer_cap"


def test_unknown_referral_code_makes_no_pending_reward(env):
    http, app, _, _ = env
    _register(http, referral_code="NOPE")
    assert "referral" not in _plan(app)
