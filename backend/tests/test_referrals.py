"""Referrals for every product (latextools/referrals.py): the ledger, pending rewards, every reward rule, and the
daily loop. In-memory dicts and fake Stripe/email: nothing here touches the network."""

import asyncio
from types import SimpleNamespace

from latextools import referrals as R

DAY = 86400
T0 = 1_800_000_000.0


def canon(e):
    return (e or "").strip().lower()


def _store():
    return SimpleNamespace(rewards={}, ledger={}, tokens={}, index={})


def _pending(store, *, session="cs_friend", referrer="ref@x.com", referred="friend@y.com", paid=1999,
             product="moderntex", now=T0):
    R.record_purchase(store.ledger, canon(referred), session, now)
    return R.make_pending(store.rewards, session_id=session, referrer_email=referrer, referred_email=referred,
                          product=product, paid_cents=paid, now=now, canonical_email=canon)


def _sweep(store, *, now, charges=None, opted=()):
    charges = charges or {}
    sent = []

    async def fetch(sid):
        return charges.get(sid, {"refunded": False, "disputed": False, "fingerprint": ""})

    async def send(**kw):
        sent.append(kw)
        return {"status": "ok"}

    tokens = iter(f"tok{i}" for i in range(100))
    out = asyncio.run(R.run_sweep(store, now=now, canonical_email=canon, gen_token=lambda: next(tokens),
                                  fetch_charge=fetch, referral_code_for=lambda e: "abcdef0123", send_email=send,
                                  opted_out=lambda e: e in opted))
    return out, sent


def test_ledger_keeps_the_oldest_order_first():
    led = {}
    R.record_purchase(led, "a@b.com", "cs_new", T0)
    R.record_purchase(led, "a@b.com", "cs_old", T0 - 100 * DAY)   # backfill arrives later
    R.record_purchase(led, "a@b.com", "cs_new", T0)                # webhook retry
    assert led["a@b.com"]["first_session"] == "cs_old"
    assert led["a@b.com"]["sessions"] == ["cs_new", "cs_old"]


def test_make_pending_refuses_self_small_and_subscriptions():
    rw = {}
    kw = dict(session_id="cs_1", referrer_email="a@b.com", now=T0, canonical_email=canon)
    assert R.make_pending(rw, referred_email="A@B.com", product="moderntex", paid_cents=1999, **kw) == "same_email"
    assert R.make_pending(rw, referred_email="c@d.com", product="cover-letter", paid_cents=160, **kw) == "below_minimum"
    assert R.make_pending(rw, referred_email="c@d.com", product="paper-review-annual", paid_cents=7900,
                          **kw) == "subscription"
    assert rw == {}
    assert R.make_pending(rw, referred_email="c@d.com", product="moderntex", paid_cents=1599, **kw) == "pending"
    assert R.make_pending(rw, referred_email="c@d.com", product="moderntex", paid_cents=1599, **kw) == "exists"
    assert rw["rw:cs_1"]["due_at"] == T0 + 14 * DAY


def test_reward_waits_fourteen_days_then_pays_one_standard_token():
    s = _store()
    assert _pending(s) == "pending"
    out, sent = _sweep(s, now=T0 + 13 * DAY)
    assert out["paid"] == 0 and out["waiting"] == 1 and not sent
    out, sent = _sweep(s, now=T0 + 14 * DAY + 1)
    assert out["paid"] == 1
    entry = s.tokens["referral-cs_friend"]
    assert entry["product_key"] == "paper-review-standard" and entry["expires_at"] == 0
    assert entry["tokens"] == ["tok0"] and s.index["tok0"] == "referral-cs_friend"
    assert s.rewards["referred:friend@y.com"] == "cs_friend"
    assert len(sent) == 1 and sent[0]["to"] == "ref@x.com" and "direct_token=tok0" in sent[0]["html"]
    # a second pass pays nothing more
    out, _ = _sweep(s, now=T0 + 20 * DAY)
    assert out["paid"] == 0 and len(s.tokens) == 1


def test_refund_or_dispute_rejects():
    for state in ({"refunded": True}, {"disputed": True}):
        s = _store()
        _pending(s)
        out, sent = _sweep(s, now=T0 + 15 * DAY, charges={"cs_friend": {**state, "fingerprint": ""}})
        assert out["rejected"] == 1 and not s.tokens and not sent
        assert s.rewards["rw:cs_friend"]["reason"] == "refunded_or_disputed"


def test_unreadable_stripe_waits_then_gives_up():
    s = _store()
    _pending(s)

    async def none(_sid):
        return None
    item = s.rewards["rw:cs_friend"]
    v = R.decide(s.rewards, s.ledger, item, now=T0 + 15 * DAY, canonical_email=canon, charge=None,
                 referrer_fingerprints=set())
    assert v == ("wait", "stripe_unreadable")
    v = R.decide(s.rewards, s.ledger, item, now=T0 + 45 * DAY, canonical_email=canon, charge=None,
                 referrer_fingerprints=set())
    assert v == ("reject", "stripe_unreadable")


def test_not_first_purchase_rejects():
    s = _store()
    R.record_purchase(s.ledger, "friend@y.com", "cs_earlier", T0 - 50 * DAY)
    _pending(s)
    out, _ = _sweep(s, now=T0 + 15 * DAY)
    assert out["rejected"] == 1 and s.rewards["rw:cs_friend"]["reason"] == "not_first_purchase"


def test_same_card_as_referrer_rejects():
    s = _store()
    R.record_purchase(s.ledger, "ref@x.com", "cs_ref", T0 - 10 * DAY)
    _pending(s)
    charges = {"cs_friend": {"refunded": False, "disputed": False, "fingerprint": "fpA"},
               "cs_ref": {"refunded": False, "disputed": False, "fingerprint": "fpA"}}
    out, _ = _sweep(s, now=T0 + 15 * DAY, charges=charges)
    assert out["rejected"] == 1 and s.rewards["rw:cs_friend"]["reason"] == "same_card"


def test_one_reward_per_referred_buyer_including_annual():
    s = _store()
    _pending(s)
    s.rewards["referred:friend@y.com"] = "pl_annualplan"     # already paid out by the annual plan's reward
    out, _ = _sweep(s, now=T0 + 15 * DAY)
    assert out["rejected"] == 1 and s.rewards["rw:cs_friend"]["reason"] == "already_rewarded"


def test_referrer_cap_twenty_a_year():
    s = _store()
    s.rewards["by:ref@x.com"] = [T0 - i * DAY for i in range(20)]
    _pending(s)
    out, _ = _sweep(s, now=T0 + 15 * DAY)
    assert s.rewards["rw:cs_friend"]["reason"] == "referrer_cap"


def test_opted_out_referrer_gets_token_but_no_email():
    s = _store()
    _pending(s)
    out, sent = _sweep(s, now=T0 + 15 * DAY, opted={"ref@x.com"})
    assert out["paid"] == 1 and out["not_emailed"] == 1 and not sent and s.tokens


def test_charge_state_reads_refund_dispute_and_card():
    sess = {"payment_intent": {"latest_charge": {"refunded": False, "amount_refunded": 500, "disputed": False,
                                                 "payment_method_details": {"card": {"fingerprint": "fpZ"}}}}}
    assert R.charge_state(sess) == {"refunded": True, "disputed": False, "fingerprint": "fpZ"}
    assert R.charge_state(None) is None


def test_annual_reward_respects_the_shared_key():
    from latextools import annual
    plan = {"email": "friend@y.com", "amount_paid": annual.PLAN_PRICE_CENTS,
            "referral": {"state": "pending", "due_at": 0, "paid_cents": annual.PLAN_PRICE_CENTS,
                         "referrer_email": "ref@x.com"}}
    store = SimpleNamespace(plans={}, referred={"referred:friend@y.com": "cs_friend"})
    assert annual.reward_decision(store, plan, canon, T0) == ("reject", "already_rewarded")
    store.referred = {}
    assert annual.reward_decision(store, plan, canon, T0) == ("pay", "ok")
