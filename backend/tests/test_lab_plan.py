"""Lab plans and the Publication Pack, module level (latextools/lab.py): grants, tokens, follow-ups, group claims,
revoke and restore, order revoke, the daily sweep, and that annual plans and lab plans never touch each other.
No network, no Modal: stores are in-memory fakes. Assertions are on links, tokens, dates, counts and keys, never wording."""

import asyncio
import itertools
from types import SimpleNamespace

import pytest

from latextools import annual, lab
from tests.test_app_paper_review_endpoints import _FakeDict

SECRET = "sub-secret"
DAY = 86400
PS = 1_800_000_000          # a fixed "period start" (UTC, mid January 2027)
NOW = PS + 60


def canon(e):
    return (e or "").strip().lower()


def new_store():
    return SimpleNamespace(plans=_FakeDict(), tokens=_FakeDict(), index=_FakeDict(), claims=_FakeDict(), referred=_FakeDict())


def counter(prefix):
    c = itertools.count(1)
    return lambda: f"{prefix}{next(c):04d}tokenpad"


def snap(ps=PS, pe=None, status="active", cancel=False, paid=True, sub="sub_L1", product="lab-monthly", months=1):
    pe = pe if pe is not None else lab.add_months(ps, months)
    return {"subscription_id": sub, "customer": "cus_1", "status": status, "cancel_at_period_end": cancel,
            "period_start": ps, "period_end": pe, "latest_invoice_id": "in_1", "latest_invoice_paid": paid,
            "metadata_product": product}


def make_plan(store, product="lab-monthly", sub="sub_L1", root="cs_lab1", email="lead@example.com", sn=None, now=NOW):
    months = lab.LAB_PRODUCTS[product]["billing_months"]
    sn = sn or snap(sub=sub, product=product, months=months)
    r = lab.register(store, subscription_id=sub, product=product, email=email, root=root, customer="cus_1", snap=sn,
                     gen_token=counter("t"), now=now, canonical_email=canon)
    assert r["ok"], r
    res = lab.sync(store, sn, gen_token=counter("g" + sub[-2:]), now=now)
    return lab.get_plan(store.plans, r["plan"]["plan_id"]), res


# ------------------------------------------------------------------------------------------------ dates

def test_add_months_clamps_and_anchors():
    jan31 = 1_801_353_600            # 2027-01-31 00:00 UTC
    assert lab.date_label(lab.add_months(jan31, 1)) == "28 February 2027"
    assert lab.date_label(lab.add_months(jan31, 2)) == "31 March 2027"
    assert lab.date_label(lab.add_months(jan31, 12)) == "31 January 2028"
    assert lab.date_label(lab.add_months(1_798_761_600, 1)) == "1 February 2027"   # 1 Jan 2027 + 1
    assert lab.add_months(1_811_000_000, 0) == 1_811_000_000


# ------------------------------------------------------------------------------------------- plan token

def test_plan_token_roundtrip_replaced_and_limits():
    store = new_store()
    plan, _ = make_plan(store)
    tok = lab.sign_plan_token(SECRET, plan["plan_id"], plan["nonce"], NOW)
    assert tok.startswith("lab_") and len(tok) <= 400 and tok.count(".") == 3
    got, why = lab.plan_for_token(store.plans, SECRET, tok, NOW)
    assert why is None and got["plan_id"] == plan["plan_id"]
    assert lab.plan_for_token(store.plans, SECRET, tok, NOW + 61 * DAY)[1] == "invalid"
    assert lab.plan_for_token(store.plans, SECRET, tok[:-1] + ("0" if tok[-1] != "0" else "1"), NOW)[1] == "invalid"
    assert lab.plan_for_token(store.plans, "other", tok, NOW)[1] == "invalid"
    assert lab.plan_for_token(store.plans, SECRET, "x" * 401, NOW)[1] == "invalid"
    lab.rotate_nonce(store, plan)
    assert lab.plan_for_token(store.plans, SECRET, tok, NOW)[1] == "replaced"


# ------------------------------------------------------------------------------------------------ grants

def test_register_is_idempotent_and_first_grant_sits_at_the_root():
    store = new_store()
    plan, res = make_plan(store)
    assert [m["key"] for m in res["minted"]] == ["cs_lab1"]
    again = lab.register(store, subscription_id="sub_L1", product="lab-monthly", email="x@y.z", root="cs_other",
                         customer="", snap=snap(), gen_token=counter("z"), now=NOW, canonical_email=canon)
    assert again["reason"] == "exists" and again["plan"]["plan_id"] == plan["plan_id"] and not again["created"]
    entry = store.tokens.get("cs_lab1")
    assert len(entry["tokens"]) == 20 and entry["lab_plan"] is True and entry["plan_id"] == plan["plan_id"]
    assert entry["expires_at"] == 0 and entry["term_ends_at"] == lab.add_months(PS, 2)
    assert entry["product_cfg"] == {"category": "paper-review", "tier": "standard", "qty": 20,
                                    "bundled_anonymity": True, "bundled_journal": True}
    assert entry["amount_paid"] == 19900
    assert all(store.index.get(t) == "cs_lab1" for t in entry["tokens"])
    assert plan["grants"][0]["count"] == 20 and plan["grants"][0]["key"] == "cs_lab1"
    assert store.plans.get("labsub:sub_L1") == plan["plan_id"]
    assert plan["plan_id"].startswith("lab_") and "group_key" not in plan


def test_register_claim_blocks_a_concurrent_second_creator():
    store = new_store()
    store.claims.put("labreg:sub_Z", NOW, skip_if_exists=True)
    r = lab.register(store, subscription_id="sub_Z", product="lab-monthly", email="a@b.c", root="r", customer="",
                     snap=snap(sub="sub_Z"), gen_token=counter("t"), now=NOW, canonical_email=canon)
    assert r["ok"] is False and r["reason"] == "in_progress"
    assert lab.plan_by_subscription(store.plans, "sub_Z") is None


def test_sync_twice_mints_once_and_a_failed_mint_can_retry(monkeypatch):
    store = new_store()
    plan, res = make_plan(store)
    again = lab.sync(store, snap(), gen_token=counter("q"), now=NOW + 5)
    assert again["minted"] == [] and len(store.plans.get(plan["plan_id"])["grants"]) == 1

    store2 = new_store()
    sn = snap(sub="sub_L2")
    lab.register(store2, subscription_id="sub_L2", product="lab-monthly", email="a@b.c", root="r2", customer="",
                 snap=sn, gen_token=counter("t"), now=NOW, canonical_email=canon)
    real = lab._mint_grant
    monkeypatch.setattr(lab, "_mint_grant", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        lab.sync(store2, sn, gen_token=counter("q"), now=NOW)
    monkeypatch.setattr(lab, "_mint_grant", real)
    assert len(lab.sync(store2, sn, gen_token=counter("q"), now=NOW)["minted"]) == 1


def test_yearly_plan_grants_monthly_inside_the_paid_year():
    store = new_store()
    sn = snap(product="lab-annual", months=12)
    plan, res = make_plan(store, product="lab-annual", sn=sn)
    assert len(res["minted"]) == 1 and plan["billing_months"] == 12
    later = lab.add_months(PS, 1) + 5
    res2 = lab.sync(store, sn, gen_token=counter("m"), now=later)
    pe = sn["period_end"]
    assert [m["key"] for m in res2["minted"]] == [f"cs_lab1#g{pe}.1"]
    assert res2["minted"][0]["grant"]["start"] == lab.add_months(PS, 1)
    assert lab.sync(store, sn, gen_token=counter("m"), now=later + 10)["minted"] == []
    # two months on: only month 2 is new (month 0 and 1 already issued)
    res3 = lab.sync(store, sn, gen_token=counter("n"), now=lab.add_months(PS, 2) + 5)
    assert [g["id"] for g in (m["grant"] for m in res3["minted"])] == [f"{pe}.2"]


def test_a_missed_month_is_not_minted_after_its_own_term_is_over():
    store = new_store()
    sn = snap(product="lab-annual", months=12)
    lab.register(store, subscription_id="sub_L1", product="lab-annual", email="a@b.c", root="r", customer="",
                 snap=sn, gen_token=counter("t"), now=NOW, canonical_email=canon)
    res = lab.sync(store, sn, gen_token=counter("g"), now=lab.add_months(PS, 5) + 10)
    ids = [m["grant"]["id"] for m in res["minted"]]
    pe = sn["period_end"]
    assert ids == [f"{pe}.4", f"{pe}.5"]          # months 0 to 3 ended more than two months ago


@pytest.mark.parametrize("kw", [dict(status="past_due"), dict(paid=False), dict(paid=None)])
def test_no_grant_unless_active_and_paid(kw):
    store = new_store()
    sn = snap(**kw)
    lab.register(store, subscription_id="sub_L1", product="lab-monthly", email="a@b.c", root="r", customer="",
                 snap=sn, gen_token=counter("t"), now=NOW, canonical_email=canon)
    assert lab.sync(store, sn, gen_token=counter("g"), now=NOW)["minted"] == []


def test_zero_dollar_first_invoice_is_accepted():
    cfg = lab.LAB_PRODUCTS["lab-monthly"]
    assert lab.amount_ok(cfg, 0, 19900) and lab.amount_ok(cfg, 19900, 19900) and lab.amount_ok(cfg, None, None)
    assert not lab.amount_ok(cfg, 19901, 19900) and not lab.amount_ok(cfg, 100, 100) and not lab.amount_ok(cfg, -1, 19900)
    store = new_store()
    plan, res = make_plan(store)
    assert len(res["minted"]) == 1


def test_next_month_grant_is_issued_on_the_new_period_and_old_one_stays_usable():
    store = new_store()
    plan, _ = make_plan(store)
    sn2 = snap(ps=lab.add_months(PS, 1), months=1)
    res = lab.sync(store, sn2, gen_token=counter("p"), now=lab.add_months(PS, 1) + 30)
    assert len(res["minted"]) == 1 and res["minted"][0]["key"].startswith("cs_lab1#g")
    first = store.tokens.get("cs_lab1")
    assert first["term_ends_at"] == lab.add_months(PS, 2) > lab.add_months(PS, 1) + 30      # carry-over month
    assert all(store.index.get(t) == "cs_lab1" for t in first["tokens"])                    # still resolves


def test_mid_period_upgrade_applies_from_the_next_grant():
    store = new_store()
    plan, _ = make_plan(store)
    sn2 = snap(ps=lab.add_months(PS, 1), product="lab-plus-monthly", months=1)
    res = lab.sync(store, sn2, gen_token=counter("u"), now=lab.add_months(PS, 1) + 30)
    p = lab.get_plan(store.plans, plan["plan_id"])
    assert p["product"] == "lab-plus-monthly" and p["tier"] == "lab-plus" and p["reviews_per_month"] == 40
    assert p["group_key"].startswith("lg_") and store.plans.get("labgroup:" + p["group_key"]) == p["plan_id"]
    assert len(res["minted"][0]["tokens"]) == 40
    assert len(store.tokens.get("cs_lab1")["tokens"]) == 20                                  # earlier grant untouched


def test_cancel_flip_is_reported_once():
    store = new_store()
    plan, _ = make_plan(store)
    r1 = lab.sync(store, snap(cancel=True), gen_token=counter("c"), now=NOW + 10)
    r2 = lab.sync(store, snap(cancel=True), gen_token=counter("c"), now=NOW + 20)
    assert r1["cancel_flipped"] is True and r2["cancel_flipped"] is False
    assert lab.plan_state(lab.get_plan(store.plans, plan["plan_id"]), NOW + 30) == "cancelling"


# ----------------------------------------------------------------------------------------- revoke / restore

def test_revoke_sets_the_flag_only_and_annual_term_refusal_enforces_it():
    store = new_store()
    plan, _ = make_plan(store)
    entry = store.tokens.get("cs_lab1")
    assert annual.term_refusal(store, entry, NOW) is None
    assert lab.revoke(store, "sub_L1", "refund", NOW)["ok"] is True
    assert annual.term_refusal(store, entry, NOW) == "revoked"
    assert store.index.get(entry["tokens"][0]) == "cs_lab1"          # index rows stay
    assert lab.restore(store, "sub_L1", "dp_x", NOW)["reason"] == "refunded"
    assert lab.revoke(store, "nope", "refund", NOW)["reason"] == "unknown_plan"


def test_dispute_revoke_restore_with_two_open_disputes():
    store = new_store()
    plan, _ = make_plan(store)
    lab.revoke(store, "sub_L1", "dispute", NOW, "dp_1")
    lab.revoke(store, "sub_L1", "dispute", NOW, "dp_2")
    assert lab.restore(store, "sub_L1", "dp_1", NOW)["reason"] == "disputes_still_open"
    res = lab.restore(store, "sub_L1", "dp_2", NOW)
    assert res["restored"] is True
    assert annual.term_refusal(store, store.tokens.get("cs_lab1"), NOW) is None
    assert lab.restore(store, "sub_L1", "dp_2", NOW)["restored"] is False
    assert lab.restore(store, "unknown", "dp_2", NOW)["ok"] is False


def test_expired_grant_is_refused_after_its_term():
    store = new_store()
    plan, _ = make_plan(store)
    assert annual.term_refusal(store, store.tokens.get("cs_lab1"), lab.add_months(PS, 2) + 1) == "expired"


# --------------------------------------------------------------------------------------------- plan view

def test_plan_view_shape_counts_and_follow_ups():
    store = new_store()
    plan, _ = make_plan(store)
    entry = store.tokens.get("cs_lab1")
    used = entry["tokens"][0]
    entry["consumed_tokens"] = [used]
    store.tokens["cs_lab1"] = entry
    entry["lab_plan"] = True
    keys = lab.mint_followups(store, lab.get_plan(store.plans, plan["plan_id"]), entry, used, counter("f"), NOW)
    assert set(keys) == {"revision", "response"} and keys["revision"].startswith("fu-rev:")
    view = lab.plan_view(store, lab.get_plan(store.plans, plan["plan_id"]), NOW)
    assert view["state"] == "active" and view["plan_name"] == "Lab" and view["tier"] == "lab"
    assert view["reviews_per_month"] == 20 and view["billing"] == "monthly" and view["group_url"] == ""
    assert view["unused"] == 19 and view["customer"] == "cus_1"
    assert view["date"] == lab.date_label(lab.add_months(PS, 1)) and view["next_grant"] == view["date"]
    g = view["grants"][0]
    assert g["count"] == 20 and g["unused"] == 19 and g["expired"] is False and len(g["tokens"]) == 20
    row = g["tokens"][0]
    assert row["short"] == used[:8] and row["used"] is True and row["start_url"] == ""
    assert [f["kind"] for f in row["followups"]] == ["revision", "response"]
    assert row["followups"][0]["url"].startswith("https://purplelink.llc/tools/paper-review/revision/upload/?session_id=fu-rev%3A")
    assert row["followups"][1]["url"].startswith("https://purplelink.llc/tools/response-review/upload/?session_id=fu-resp%3A")
    assert all(f["used"] is False for f in row["followups"])
    other = g["tokens"][1]
    assert other["used"] is False and other["start_url"] == lab.start_url(entry["tokens"][1]) and "followups" not in other


def test_plan_view_uses_stored_count_after_a_reissue_and_survives_a_swept_entry():
    store = new_store()
    plan, _ = make_plan(store)
    entry = store.tokens.get("cs_lab1")
    entry["tokens"].append("replacementtoken0000")
    entry["consumed_tokens"] = [entry["tokens"][0]]
    store.tokens["cs_lab1"] = entry
    v = lab.plan_view(store, plan, NOW)
    assert v["grants"][0]["count"] == 20 and len(v["grants"][0]["tokens"]) == 21
    del store.tokens["cs_lab1"]
    v2 = lab.plan_view(store, plan, NOW)
    assert v2["grants"][0]["expired"] is True and v2["grants"][0]["unused"] == 0 and v2["unused"] == 0
    assert v2["grants"][0]["count"] == 20


def test_plan_view_states_and_next_grant():
    store = new_store()
    plan, _ = make_plan(store, product="lab-annual", sn=snap(product="lab-annual", months=12))
    assert lab.plan_view(store, plan, NOW)["billing"] == "yearly"
    assert lab.next_grant(plan, NOW) == lab.add_months(PS, 1)
    plan["cancel_at_period_end"] = True
    assert lab.plan_state(plan, NOW) == "cancelling" and lab.next_grant(plan, NOW) == lab.add_months(PS, 1)
    assert lab.next_grant(plan, lab.add_months(PS, 11) + 5 * DAY) is None
    plan["cancel_at_period_end"] = False
    plan["status"] = "past_due"
    assert lab.plan_state(plan, NOW) == "problem" and lab.next_grant(plan, NOW) is None
    plan["revoked"] = True
    assert lab.plan_state(plan, NOW) == "revoked" and lab.plan_view(store, plan, NOW)["unused"] == 0
    plan["revoked"], plan["status"] = False, "active"
    assert lab.plan_state(plan, plan["period_end"] + 1) == "ended"


# --------------------------------------------------------------------------------------------- follow-ups

def test_followups_are_idempotent_and_keyed_on_the_original_token():
    store = new_store()
    plan, _ = make_plan(store)
    entry = store.tokens.get("cs_lab1")
    t0 = entry["tokens"][0]
    gen = counter("f")
    k1 = lab.mint_followups(store, plan, entry, t0, gen, NOW)
    fu = store.tokens.get(k1["revision"])
    assert fu["category"] if "category" in fu else fu["product_cfg"]["category"] == "revision-review"
    assert fu["product_cfg"]["category"] == "revision-review" and fu["amount_paid"] == 500 and fu["expires_at"] == 0
    assert fu["term_ends_at"] == int(NOW + 365 * DAY) and fu["plan_id"] == plan["plan_id"] and fu["source"] == "lab-followup"
    resp = store.tokens.get(k1["response"])
    assert resp["product_cfg"]["category"] == "response-review" and resp["amount_paid"] == 1200
    assert store.index.get(fu["tokens"][0]) == k1["revision"]
    before = dict(fu)
    k2 = lab.mint_followups(store, lab.get_plan(store.plans, plan["plan_id"]), entry, t0, gen, NOW + 5)
    assert k2 == k1 and store.tokens.get(k1["revision"])["tokens"] == before["tokens"]
    # a replacement token for the same review maps back and earns nothing new
    entry["reissued_from"] = {"newtok": t0}
    k3 = lab.mint_followups(store, lab.get_plan(store.plans, plan["plan_id"]), entry, "newtok", gen, NOW + 9)
    assert k3 == k1
    # follow-ups of a revoked plan are refused
    lab.revoke(store, "sub_L1", "refund", NOW)
    assert annual.term_refusal(store, store.tokens.get(k1["revision"]), NOW) == "revoked"
    # not a plan entry: nothing
    assert lab.mint_followups(store, plan, {"tokens": ["a"]}, "a", gen, NOW) is None


def test_a_swept_used_followup_reads_as_used_and_is_never_reminted():
    store = new_store()
    plan, _ = make_plan(store)
    entry = store.tokens.get("cs_lab1")
    t0 = entry["tokens"][0]
    entry["consumed_tokens"] = [t0]
    keys = lab.mint_followups(store, plan, entry, t0, counter("f"), NOW)
    del store.tokens[keys["revision"]]
    plan = lab.get_plan(store.plans, plan["plan_id"])
    row = lab.plan_view(store, plan, NOW)["grants"][0]["tokens"][0]
    assert row["followups"][0]["used"] is True
    assert lab.mint_followups(store, plan, entry, t0, counter("x"), NOW + 99) == keys
    assert store.tokens.get(keys["revision"]) is None


# ------------------------------------------------------------------------------------------ group link

def test_member_claim_order_rehand_and_none_left():
    store = new_store()
    plan, _ = make_plan(store, product="lab-plus-monthly", sub="sub_P1", root="cs_plus",
                        sn=snap(sub="sub_P1", product="lab-plus-monthly", months=1))
    assert plan["group_key"].startswith("lg_") and lab.plan_by_group(store.plans, plan["group_key"])["plan_id"] == plan["plan_id"]
    entry = store.tokens.get("cs_plus")
    toks = entry["tokens"]
    assert len(toks) == 40 and lab.available(store, plan, store.claims, NOW) == 40
    got = [lab.member_claim(store, plan, NOW + i) for i in range(40)]
    assert got == toks                                    # never handed twice, oldest first
    assert lab.member_claim(store, plan, NOW + 100) is None
    assert lab.available(store, plan, store.claims, NOW + 100) == 0
    later = NOW + 31 * 60
    assert lab.available(store, plan, store.claims, later) == 40
    again = lab.member_claim(store, plan, later)
    assert again == toks[0]
    assert lab.member_claim(store, plan, later + 1) == toks[1]      # a re-hand is claimed once only
    entry["consumed_tokens"] = [toks[2]]
    store.tokens["cs_plus"] = entry
    assert lab.member_claim(store, plan, later + 2) != toks[2]


def test_member_claim_prefers_the_oldest_live_batch_and_skips_expired_ones():
    store = new_store()
    sn = snap(product="lab-plus-annual", sub="sub_P2", months=12)
    plan, _ = make_plan(store, product="lab-plus-annual", sub="sub_P2", root="cs_p2", sn=sn)
    res = lab.sync(store, sn, gen_token=counter("m"), now=lab.add_months(PS, 1) + 5)
    old = store.tokens.get("cs_p2")["tokens"]
    plan = lab.get_plan(store.plans, plan["plan_id"])
    assert lab.member_claim(store, plan, lab.add_months(PS, 1) + 6) == old[0]
    far = lab.add_months(PS, 2) + 5          # first batch's term ended
    new = res["minted"][0]["tokens"]
    assert lab.member_claim(store, plan, far) == new[0]


def test_rotate_group_replaces_the_key():
    store = new_store()
    plan, _ = make_plan(store, product="lab-plus-monthly", sub="sub_P1", root="cs_plus",
                        sn=snap(sub="sub_P1", product="lab-plus-monthly", months=1))
    old = plan["group_key"]
    lab.rotate_group(store, plan)
    assert plan["group_key"] != old and lab.plan_by_group(store.plans, old) is None
    assert lab.plan_by_group(store.plans, plan["group_key"])["plan_id"] == plan["plan_id"]
    assert lab.plan_view(store, plan, NOW)["group_url"] == f"https://purplelink.llc/labs/start/?k={plan['group_key']}"


# -------------------------------------------------------------------------------------- Publication Pack

def test_pack_mint_groups_and_order_revoke_reach_siblings_after_the_root_is_gone():
    store = new_store()
    out = lab.mint_pack(store, session_id="cs_pack", email="a@b.c", amount_paid=5900, gen_token=counter("k"), now=NOW)
    assert list(out) == ["cs_pack", "cs_pack#revision", "cs_pack#draft"]
    root = store.tokens.get("cs_pack")
    assert root["product_key"] == "publication-pack" and root["product_cfg"]["tier"] == "deep"
    assert root["amount_paid"] == 3900 and root["expires_at"] == 0 and root["pack_siblings"] == ["cs_pack#revision", "cs_pack#draft"]
    assert store.tokens.get("cs_pack#revision")["amount_paid"] == 500
    assert store.tokens.get("cs_pack#draft")["product_cfg"]["category"] == "response-draft"
    assert store.tokens.get("cs_pack#draft")["amount_paid"] == 2400
    assert lab.pack_has_live_sibling(store, root)
    groups = lab.pack_groups(store, "cs_pack", root)
    assert [g["category"] for g in groups] == ["paper-review", "revision-review", "response-draft"]
    assert groups[0]["url"] == lab.start_url(root["tokens"][0]) and not any(g["used"] for g in groups)
    assert groups[2]["url"] == "https://purplelink.llc/tools/response-review/draft/upload/?session_id=cs_pack%23draft"
    root["consumed_tokens"] = list(root["tokens"])
    store.tokens["cs_pack"] = root
    groups = lab.pack_groups(store, "cs_pack", root)
    assert groups[0]["used"] is True and groups[1]["used"] is False and groups[1]["url"]
    # root swept, siblings remain
    del store.tokens["cs_pack"]
    assert lab.revoke_order(store, "cs_pack", "dispute", NOW, "dp_1")["ok"] is True
    assert store.tokens.get("cs_pack#revision")["revoked"] is True and store.tokens.get("cs_pack#draft")["revoked"] is True
    assert lab.restore_order(store, "cs_pack", "dp_1", NOW)["restored"] is True
    assert store.tokens.get("cs_pack#revision")["revoked"] is False
    lab.revoke_order(store, "cs_pack", "refund", NOW)
    assert lab.restore_order(store, "cs_pack", "dp_1", NOW)["restored"] is False
    assert store.tokens.get("cs_pack#draft")["revoked"] is True


def test_order_revoke_unknown_and_single_entry_orders():
    store = new_store()
    assert lab.revoke_order(store, "nothing", "refund", NOW) == {"ok": False, "reason": "unknown_order"}
    assert lab.restore_order(store, "nothing", "d", NOW)["ok"] is False
    store.tokens["cs_one"] = {"tokens": ["a"], "product_cfg": {"category": "paper-review"}}
    assert lab.revoke_order(store, "cs_one", "dispute", NOW, "dp_9")["ok"] is True
    assert annual.term_refusal(store, store.tokens.get("cs_one"), NOW) == "revoked"
    lab.restore_order(store, "cs_one", "dp_9", NOW)
    assert annual.term_refusal(store, store.tokens.get("cs_one"), NOW) is None


# ----------------------------------------------------------------------------------- cross-contamination

def make_annual(store, sub="sub_A1", root="cs_ann", email="ann@example.com", period_end=None, now=NOW):
    cfg = {"category": "paper-review", "tier": "standard", "qty": 12, "bundled_anonymity": True, "bundled_journal": True}
    plan, toks = annual.create_plan(store, root_session=root, email=email, subscription_id=sub, customer="cus_a",
                                    period_end=period_end or now + 365 * DAY, amount_paid=7900, cfg=cfg,
                                    gen_token=counter("a"), now=now, canonical_email=canon)
    return plan, toks


def test_annual_lookups_find_nothing_for_lab_plans_and_lab_tokens():
    store = new_store()
    plan, _ = make_plan(store, email="Lead@Example.com")
    assert annual.plan_by_subscription(store.plans, "sub_L1") is None
    assert annual.plan_by_email(store.plans.items(), "lead@example.com") is None
    tok = lab.sign_plan_token(SECRET, plan["plan_id"], plan["nonce"], NOW)
    assert annual.parse_plan_token(SECRET, tok, NOW) is None
    assert annual.plan_for_token(store.plans, SECRET, tok, NOW) == (None, "invalid")
    assert lab.plan_by_email(store.plans.items(), "lead@example.com")["plan_id"] == plan["plan_id"]


def test_lab_lookups_reject_annual_tokens_and_leave_annual_plans_alone():
    store = new_store()
    aplan, _ = make_annual(store)
    lplan, _ = make_plan(store)
    atok = annual.sign_plan_token(SECRET, aplan["plan_id"], aplan["nonce"], NOW)
    assert atok.startswith("pl_") and lab.parse_plan_token(SECRET, atok, NOW) is None
    assert lab.plan_for_token(store.plans, SECRET, atok, NOW) == (None, "invalid")
    assert lab.plan_by_email(store.plans.items(), "ann@example.com") is None
    before = dict(store.plans.items()), dict(store.tokens.items())
    sn = snap(sub="sub_A1", ps=PS, pe=PS + 365 * DAY, product="lab-monthly")
    assert lab.sync(store, sn, gen_token=counter("x"), now=NOW)["reason"] == "unknown_plan"
    assert lab.revoke(store, "sub_A1", "refund", NOW)["reason"] == "unknown_plan"
    assert lab.restore(store, "sub_A1", "dp", NOW)["ok"] is False
    assert (dict(store.plans.items()), dict(store.tokens.items())) == before


def test_sweeps_skip_each_others_keys():
    store = new_store()
    make_annual(store, period_end=NOW + 5 * DAY)
    make_plan(store)
    store.plans["reward:x@y.z:2027"] = 2
    fetched_annual, fetched_lab, sent = [], [], []

    async def fa(sub):
        fetched_annual.append(sub)
        return {"subscription_id": sub, "status": "active", "cancel_at_period_end": False,
                "period_end": NOW + 5 * DAY, "latest_invoice_paid": True, "customer": "cus_a"}

    async def fl(sub):
        fetched_lab.append(sub)
        return snap(sub=sub)

    async def send(**kw):
        sent.append(kw)
        return {"status": "ok"}

    async def on_renewed(res):
        pass

    asyncio.run(annual.run_sweep(store, now=NOW, secret=SECRET, cfg={}, gen_token=counter("a"), canonical_email=canon,
                                 fetch_subscription=fa, send_email=send, on_renewed=on_renewed))
    out = asyncio.run(lab.run_sweep(store, now=NOW + 10, secret=SECRET, gen_token=counter("l"),
                                    fetch_subscription=fl, send_email=send))
    assert fetched_annual == ["sub_A1"] and fetched_lab == ["sub_L1"] and out["plans"] == 1


def test_annual_scenario_is_identical_with_and_without_lab_plans(monkeypatch):
    def scenario(with_lab):
        ids, nonces = itertools.count(1), itertools.count(1)
        monkeypatch.setattr(annual, "new_plan_id", lambda: f"pl_fixed{next(ids)}")
        monkeypatch.setattr(annual, "new_nonce", lambda: f"n{next(nonces)}")
        store = new_store()
        if with_lab:
            make_plan(store)
            make_plan(store, product="lab-plus-annual", sub="sub_P9", root="cs_p9",
                      sn=snap(sub="sub_P9", product="lab-plus-annual", months=12))
        plan, _ = make_annual(store, period_end=NOW + 5 * DAY)
        sent = []

        async def fetch(sub):
            return {"subscription_id": sub, "status": "active", "cancel_at_period_end": False,
                    "period_end": NOW + 5 * DAY, "latest_invoice_paid": True, "customer": "cus_a"}

        async def send(**kw):
            sent.append((kw["to"], kw["tag"]))
            return {"status": "ok"}

        async def on_renewed(res):
            pass

        renew = annual.renew(store, {"subscription_id": "sub_A1", "status": "active", "latest_invoice_paid": True,
                                     "period_end": NOW + 400 * DAY, "cancel_at_period_end": False},
                             cfg=plan and {"category": "paper-review", "qty": 12}, gen_token=counter("r"), now=NOW + 1)
        out = asyncio.run(annual.run_sweep(store, now=NOW, secret=SECRET, cfg={}, gen_token=counter("s"),
                                           canonical_email=canon, fetch_subscription=fetch, send_email=send,
                                           on_renewed=on_renewed))
        keep = lambda k: str(k).startswith(("pl_", "sub:", "reward:", "cs_ann"))
        return ({k: v for k, v in store.plans.items() if keep(k)}, {k: v for k, v in store.tokens.items() if keep(k)},
                {k: v for k, v in store.index.items() if str(v).startswith("cs_ann")}, renew["reason"], out, sent)

    assert scenario(False) == scenario(True)


# ------------------------------------------------------------------------------------------------- sweep

def test_sweep_reminds_yearly_plans_once_and_never_monthly_ones():
    store = new_store()
    sent = []
    sn_y = snap(product="lab-annual", sub="sub_Y", ps=PS, pe=PS + 20 * DAY)
    make_plan(store, product="lab-annual", sub="sub_Y", root="cs_y", sn=sn_y)
    make_plan(store, sub="sub_M", root="cs_m", sn=snap(sub="sub_M", ps=PS, pe=PS + 20 * DAY))

    async def fetch(sub):
        return snap(product="lab-annual", sub=sub, ps=PS, pe=PS + 20 * DAY) if sub == "sub_Y" else snap(sub=sub, ps=PS, pe=PS + 20 * DAY)

    async def send(**kw):
        sent.append(kw)
        return {"status": "ok"}

    out = asyncio.run(lab.run_sweep(store, now=NOW + 10, secret=SECRET, gen_token=counter("w"), fetch_subscription=fetch, send_email=send))
    assert out["reminded"] == 1 and [m["tag"] for m in sent] == ["lab_reminder_30"]
    assert "lab_" in sent[0]["html"] and "/labs/plan/?t=lab_" in sent[0]["html"]
    out2 = asyncio.run(lab.run_sweep(store, now=NOW + 20, secret=SECRET, gen_token=counter("w"), fetch_subscription=fetch, send_email=send))
    assert out2["reminded"] == 0 and len(sent) == 1
    out3 = asyncio.run(lab.run_sweep(store, now=PS + 15 * DAY, secret=SECRET, gen_token=counter("w"), fetch_subscription=fetch, send_email=send))
    assert out3["reminded"] == 1 and sent[-1]["tag"] == "lab_reminder_7"


def test_sweep_does_not_send_blind_when_stripe_is_unreadable():
    store = new_store()
    make_plan(store)
    sent = []

    async def fetch(sub):
        return None

    async def send(**kw):
        sent.append(kw)
        return {"status": "ok"}

    out = asyncio.run(lab.run_sweep(store, now=NOW, secret=SECRET, gen_token=counter("w"), fetch_subscription=fetch, send_email=send))
    assert out["errors"] == 1 and sent == []


def test_sweep_issues_due_grants_and_mails_them_and_a_portal_cancel_once():
    store = new_store()
    sn = snap(product="lab-annual", months=12)
    make_plan(store, product="lab-annual", sn=sn)
    sent = []
    state = {"cancel": False}

    async def fetch(sub):
        return snap(product="lab-annual", months=12, cancel=state["cancel"])

    async def send(**kw):
        sent.append(kw)
        return {"status": "ok"}

    t = lab.add_months(PS, 1) + 100
    out = asyncio.run(lab.run_sweep(store, now=t, secret=SECRET, gen_token=counter("w"), fetch_subscription=fetch, send_email=send))
    assert out["minted"] == 1 and [m["tag"] for m in sent] == ["lab_grant"]
    assert len([x for x in sent[0]["html"].split("direct_token=")]) - 1 == 20
    state["cancel"] = True
    asyncio.run(lab.run_sweep(store, now=t + 5, secret=SECRET, gen_token=counter("w"), fetch_subscription=fetch, send_email=send))
    asyncio.run(lab.run_sweep(store, now=t + 6, secret=SECRET, gen_token=counter("w"), fetch_subscription=fetch, send_email=send))
    assert [m["tag"] for m in sent].count("lab_cancel") == 1


def test_lab_emails_carry_links_and_placeholders_only():
    toks = ["tokA", "tokB"]
    h = lab.html_grant(plan_name="Lab", tokens=toks, valid_until="1 March 2027", link="https://purplelink.llc/labs/plan/?t=x",
                       group="https://purplelink.llc/labs/start/?k=lg_abc", first=True)
    assert "direct_token=tokA" in h and "direct_token=tokB" in h and "/labs/plan/?t=x" in h and "/labs/start/?k=lg_abc" in h
    assert "annual" not in h.lower() and "$79" not in h and "REPLY" not in h
    p = lab.html_pack_links(groups=[{"name": "A", "url": "https://u/1"}, {"name": "B", "url": ""}])
    assert "https://u/1" in p and "7 day" not in p
