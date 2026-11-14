"""Publication Pack ($59, one-time): register-token mints three entries, redeem-session returns the three links, the
keep-alive guard, and order revoke/restore. Assertions are on keys, links, tokens and amounts, not wording."""

import time

import pytest
from fastapi.testclient import TestClient

from latextools import lab
from tests.test_app_paper_review_endpoints import _FakeDict, _FakeSpawnFunction

SECRET = "hook-secret"
H = {"x-webhook-secret": SECRET}
DAY = 86400


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
    monkeypatch.setenv("SUBSCRIBE_SECRET", "sub-secret")
    sent = []

    async def fake_send(to, subject, html, tag):
        sent.append({"to": to, "subject": subject, "html": html, "tag": tag})
        return {"status": "ok"}

    for n in ("_annual_send", "_lab_send"):
        monkeypatch.setattr(backend_app, n, fake_send)
    # register-token sends through delivery.send_email directly; capture it too
    from latextools import delivery

    async def fake_delivery_send(client, *, to, subject, html, **kw):
        sent.append({"to": to, "subject": subject, "html": html, "tag": "delivery"})
        return {"status": "ok"}
    monkeypatch.setattr(delivery, "send_email", fake_delivery_send)
    return TestClient(backend_app.web.local()), backend_app, sent


def _buy(http, sid="cs_pack1", **extra):
    body = {"session_id": sid, "email": "pi@uni.edu", "amount_paid": 5900, "amount_subtotal": 5900, "product": "publication-pack"}
    body.update(extra)
    return http.post("/paper-review/register-token", json=body, headers=H)


def test_catalog_entry(env):
    app = env[1]
    cfg = app.PAID_PRODUCTS["publication-pack"]
    assert cfg["amount"] == 5900 and cfg["qty"] == 1 and cfg["tier"] == "deep"
    assert app.PAID_PRODUCTS["lab-annual"]["amount"] == 199000 and app.PAID_PRODUCTS["lab-plus-monthly"]["qty"] == 40


def test_register_mints_three_entries(env):
    http, app, sent = env
    r = _buy(http)
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "registered" and j["product"] == "publication-pack" and j["qty"] == 1
    assert len(j["tokens"]) == 3
    root = app.paper_tokens_dict.get("cs_pack1")
    assert root["amount_paid"] == 3900 and root["pack_amount_paid"] == 5900 and root["expires_at"] == 0
    assert app.paper_tokens_dict.get("cs_pack1#revision")["amount_paid"] == 500
    assert app.paper_tokens_dict.get("cs_pack1#draft")["amount_paid"] == 2400
    assert root["product_key"] == "publication-pack"
    assert len(sent) == 1 and sent[0]["to"] == "pi@uni.edu"
    assert "cs_pack1" in sent[0]["html"] or "direct_token=" in sent[0]["html"]


def test_register_is_idempotent(env):
    http, app, sent = env
    first = _buy(http).json()["tokens"]
    again = _buy(http)
    # the existing session lookup answers: the root token only, and nothing is minted or emailed twice
    assert again.json()["status"] == "exists" and again.json()["tokens"] == [first[0]]
    assert len(sent) == 1 and len(first) == 3


def test_register_rejects_wrong_amount(env):
    http, app, sent = env
    r = _buy(http, amount_subtotal=3900)
    assert r.status_code == 400 and r.json()["error"] == "amount_mismatch"
    assert app.paper_tokens_dict.get("cs_pack1") is None


def test_redeem_groups_has_three_links_even_when_root_used(env):
    http, app, sent = env
    _buy(http)
    r = http.post("/paper-review/redeem-session", json={"session_id": "cs_pack1", "want_groups": True}, headers=H)
    assert r.status_code == 200
    groups = r.json()["groups"]
    assert [g["category"] for g in groups][0] == "paper-review" and len(groups) == 3
    assert all(g["url"] and g["used"] is False for g in groups)
    root = app.paper_tokens_dict.get("cs_pack1")
    root["consumed_tokens"] = list(root["tokens"])
    app.paper_tokens_dict["cs_pack1"] = root
    r2 = http.post("/paper-review/redeem-session", json={"session_id": "cs_pack1", "want_groups": True}, headers=H)
    assert r2.status_code == 200 and r2.json()["groups"][0]["used"] is True and len(r2.json()["groups"]) == 3


def test_redeem_without_groups_unchanged_shape(env):
    http, app, sent = env
    _buy(http)
    r = http.post("/paper-review/redeem-session", json={"session_id": "cs_pack1"}, headers=H)
    assert r.status_code == 200 and "groups" not in r.json() and len(r.json()["tokens"]) == 1


def test_keep_alive_guard_keeps_root_while_sibling_lives(env):
    http, app, sent = env
    _buy(http)
    root = app.paper_tokens_dict.get("cs_pack1")
    root["consumed_tokens"] = list(root["tokens"])
    root["created_at"] = time.time() - 60 * DAY
    app.paper_tokens_dict["cs_pack1"] = root
    app._keep_pack_alive("cs_pack1", root, time.time())
    assert app.paper_tokens_dict.get("cs_pack1") is not None
    for k in ("cs_pack1#revision", "cs_pack1#draft"):
        del app.paper_tokens_dict[k]
    app._keep_pack_alive("cs_pack1", root, time.time())
    assert app.paper_tokens_dict.get("cs_pack1") is None


def test_order_revoke_reaches_all_three_and_restore(env):
    http, app, sent = env
    _buy(http)
    r = http.post("/paper-review/revoke-order", json={"session_id": "cs_pack1", "reason": "dispute", "dispute_id": "dp_1"}, headers=H)
    assert r.json()["ok"] is True
    for k in ("cs_pack1", "cs_pack1#revision", "cs_pack1#draft"):
        assert app.paper_tokens_dict.get(k)["revoked"] is True
    back = http.post("/paper-review/restore-order", json={"session_id": "cs_pack1", "dispute_id": "dp_1"}, headers=H).json()
    assert back["restored"] is True and not app.paper_tokens_dict.get("cs_pack1#draft")["revoked"]


def test_refunded_order_stays_revoked(env):
    http, app, sent = env
    _buy(http)
    http.post("/paper-review/revoke-order", json={"session_id": "cs_pack1", "reason": "refund"}, headers=H)
    back = http.post("/paper-review/restore-order", json={"session_id": "cs_pack1", "dispute_id": "dp_x"}, headers=H).json()
    assert back["restored"] is False and app.paper_tokens_dict.get("cs_pack1")["revoked"] is True
