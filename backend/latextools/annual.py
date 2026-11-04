"""Paper Review annual plan ("A year of reviews"): plan records, tokens, renewal, reminders, referral reward.

Design: docs/designs/paper-review-growth.md, Part D. backend/app.py holds the HTTP routes and the Stripe calls;
everything here is plain Python over dict-like stores, so tests run it with in-memory dicts and no network.

Records
-------
plans[plan_id]            one per subscription: who, which subscription, the current period, the link nonce, cancel
                          state, the periods minted so far, reminder markers, and any pending referral reward.
plans["sub:<sub_id>"]     -> plan_id (reverse index)
plans["reward:<key>:<yr>"]-> count of referral rewards paid to that referrer this year
paper_tokens[<root>]      the first period's entry (the Stripe session id is the key, as for every purchase)
paper_tokens[<root>#<end>] one entry per renewal, 12 tokens each
Every entry carries plan_id, subscription_id and term_ends_at. app.py refuses a token whose entry is past its
term, revoked, or whose plan is revoked (see `term_refusal`).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import secrets
import time
from typing import Any, Awaitable, Callable

ANNUAL_PRODUCT = "paper-review-annual"
PLAN_REVIEWS = 12
PLAN_PRICE_CENTS = 7900
PLAN_TOKEN_TTL = 60 * 86400
REWARD_REVIEWS = 6
REWARD_DELAY = 14 * 86400
REWARDS_PER_REFERRER_YEAR = 5
REMINDER_DAYS = (30, 7)

REWARD_CFG = {
    "category": "paper-review", "tier": "standard", "qty": REWARD_REVIEWS,
    "bundled_anonymity": True, "bundled_journal": True,
}


# --------------------------------------------------------------------------------------------- plan link token

def new_plan_id() -> str:
    return "pl_" + secrets.token_urlsafe(12)


def new_nonce() -> str:
    return secrets.token_urlsafe(6)


def sign_plan_token(secret: str, plan_id: str, nonce: str, now: float | None = None) -> str:
    """`<plan_id>.<expiry>.<nonce>.<sig>`. It names the plan and nothing about the buyer, and it can only cancel or
    undo that plan. Expires after 60 days and stops working when the plan's nonce is rotated."""
    exp = int((now if now is not None else time.time()) + PLAN_TOKEN_TTL)
    sig = hmac.new(secret.encode(), f"annual-plan:{plan_id}:{exp}:{nonce}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{plan_id}.{exp}.{nonce}.{sig}"


def parse_plan_token(secret: str, token: str, now: float | None = None):
    """(plan_id, nonce) for a well-formed, unexpired, correctly signed token; otherwise None."""
    if not secret or not isinstance(token, str) or len(token) > 200:
        return None
    parts = token.split(".")
    if len(parts) != 4:
        return None
    plan_id, exp_s, nonce, sig = parts
    if not plan_id.startswith("pl_") or not exp_s.isdigit():
        return None
    want = hmac.new(secret.encode(), f"annual-plan:{plan_id}:{exp_s}:{nonce}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        return None
    if int(exp_s) < (now if now is not None else time.time()):
        return None
    return plan_id, nonce


def plan_link(secret: str, plan: dict, now: float | None = None) -> str:
    return "https://purplelink.llc/tools/paper-review/plan/?t=" + sign_plan_token(secret, plan["plan_id"], plan["nonce"], now)


def plan_for_token(plans, secret: str, token: str, now: float | None = None):
    """(plan, reason). reason is None when the token is good, else "invalid" or "replaced"."""
    parsed = parse_plan_token(secret, token, now)
    if not parsed:
        return None, "invalid"
    plan = plans.get(parsed[0])
    if not isinstance(plan, dict):
        return None, "invalid"
    if parsed[1] != plan.get("nonce"):
        return None, "replaced"
    return plan, None


# ----------------------------------------------------------------------------------------------- Stripe parsing

def snapshot_from_stripe(sub: dict) -> dict:
    """What we need from a Stripe subscription object (optionally with latest_invoice expanded).
    The period end lives on the subscription item in current API versions and on the subscription in older ones."""
    items = ((sub.get("items") or {}).get("data")) or []
    period_end = None
    if items and isinstance(items[0], dict):
        period_end = items[0].get("current_period_end")
    if not isinstance(period_end, int):
        period_end = sub.get("current_period_end")
    inv = sub.get("latest_invoice")
    inv = inv if isinstance(inv, dict) else {}
    return {
        "subscription_id": sub.get("id"),
        "customer": sub.get("customer") if isinstance(sub.get("customer"), str) else (sub.get("customer") or {}).get("id"),
        "status": sub.get("status"),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "period_end": period_end if isinstance(period_end, int) else None,
        "latest_invoice_id": inv.get("id") if inv else (sub.get("latest_invoice") if isinstance(sub.get("latest_invoice"), str) else None),
        "latest_invoice_paid": (inv.get("status") == "paid") if inv else None,
        "metadata_product": (sub.get("metadata") or {}).get("product", ""),
    }


# ---------------------------------------------------------------------------------------------------- the plan

def get_plan(plans, plan_id: str):
    p = plans.get(plan_id)
    return p if isinstance(p, dict) else None


def plan_by_subscription(plans, subscription_id: str):
    if not subscription_id:
        return None
    pid = plans.get("sub:" + subscription_id)
    return get_plan(plans, pid) if isinstance(pid, str) else None


def plan_by_email(plans_items, email_key: str):
    """The live plan for an email address (newest first), or None."""
    best = None
    for k, p in plans_items:
        if not isinstance(p, dict) or not str(k).startswith("pl_"):
            continue
        if p.get("email_key") == email_key and not p.get("revoked") and not p.get("ended"):
            if best is None or p.get("created_at", 0) > best.get("created_at", 0):
                best = p
    return best


def _entry_base(cfg: dict, plan: dict, tokens: list[str], period_end: int, now: float) -> dict:
    return {
        "tokens": tokens,
        "product_key": ANNUAL_PRODUCT,
        "product_cfg": cfg,
        "email": plan["email"],
        "amount_paid": PLAN_PRICE_CENTS,
        "redeemed": False,
        "consumed_tokens": [],
        "created_at": now,
        "expires_at": 0,                 # kept on the Volume; the term below is what ends it
        "term_ends_at": period_end,
        "plan_id": plan["plan_id"],
        "subscription_id": plan["subscription_id"],
        "period_end": period_end,
    }


def _mint(tokens_dict, index_dict, key: str, entry: dict, gen_token) -> list[str]:
    toks = [gen_token() for _ in range(PLAN_REVIEWS)]
    entry["tokens"] = toks
    tokens_dict[key] = entry
    for t in toks:
        index_dict[t] = key
    return toks


def create_plan(store, *, root_session: str, email: str, subscription_id: str, customer: str, period_end: int,
                amount_paid: int, cfg: dict, gen_token, now: float, canonical_email, referral: dict | None = None,
                card_fingerprint: str = "", invoice_id: str = "") -> tuple[dict, list[str]]:
    """First purchase: the plan record, the sub index, and 12 tokens in the root entry."""
    plan = {
        "plan_id": new_plan_id(),
        "root_session": root_session,
        "subscription_id": subscription_id,
        "customer": customer,
        "email": email,
        "email_key": (canonical_email(email) or email.strip().lower()),
        "period_end": period_end,
        "period_key": root_session,
        "nonce": new_nonce(),
        "status": "active",
        "cancel_at_period_end": False,
        "ended": False,
        "revoked": False,
        "created_at": now,
        "amount_paid": amount_paid,
        "card_fingerprint": card_fingerprint or "",
        "first_invoice_id": invoice_id or "",
        "periods": [{"key": root_session, "period_end": period_end, "minted_at": now}],
        "reminders": {},
    }
    if referral:
        plan["referral"] = referral
    entry = _entry_base(cfg, plan, [], period_end, now)
    toks = _mint(store.tokens, store.index, root_session, entry, gen_token)
    store.plans[plan["plan_id"]] = plan
    store.plans["sub:" + subscription_id] = plan["plan_id"]
    return plan, toks


def unused_tokens(store, plan: dict) -> list[str]:
    entry = store.tokens.get(plan.get("period_key"))
    if not isinstance(entry, dict):
        return []
    used = set(entry.get("consumed_tokens") or [])
    return [t for t in entry.get("tokens") or [] if t not in used]


def renew(store, snap: dict, *, cfg: dict, gen_token, now: float) -> dict:
    """Grant a new year when Stripe says the subscription is active, its latest invoice is paid and its period end is
    later than the one we hold. Idempotent: two callers mint once (a claim on subscription + period end, then a
    re-check against the plan's own period list, because the claim store may forget after its 7-day idle expiry).

    Returns {"ok": bool, "reason": str, "minted": bool, "plan": plan, "tokens": [...]}."""
    plan = plan_by_subscription(store.plans, snap.get("subscription_id"))
    if not plan:
        return {"ok": False, "reason": "unknown_plan", "minted": False}
    if plan.get("revoked"):
        return {"ok": False, "reason": "revoked", "minted": False, "plan": plan}
    if snap.get("status") != "active":
        return {"ok": False, "reason": "not_active", "minted": False, "plan": plan}
    if snap.get("latest_invoice_paid") is not True:
        return {"ok": False, "reason": "unpaid", "minted": False, "plan": plan}
    period_end = snap.get("period_end")
    if not isinstance(period_end, int) or period_end <= int(plan.get("period_end") or 0):
        return {"ok": True, "reason": "already_current", "minted": False, "plan": plan}
    claim_key = f"annual:{snap['subscription_id']}:{period_end}"
    if not store.claims.put(claim_key, now, skip_if_exists=True):
        return {"ok": True, "reason": "claimed", "minted": False, "plan": plan}
    try:
        plan = get_plan(store.plans, plan["plan_id"]) or plan
        if any(p.get("period_end") == period_end for p in plan.get("periods", [])):
            return {"ok": True, "reason": "already_current", "minted": False, "plan": plan}
        old_key = plan.get("period_key")
        old = store.tokens.get(old_key)
        if isinstance(old, dict):
            old["term_ends_at"] = min(old.get("term_ends_at") or now, now)   # last year's entry is over from here
            store.tokens[old_key] = old
            for t in old.get("tokens") or []:
                try:
                    del store.index[t]      # last period's unused tokens stop resolving
                except Exception:
                    pass
        key = f"{plan['root_session']}#{period_end}"
        entry = _entry_base(cfg, plan, [], period_end, now)
        toks = _mint(store.tokens, store.index, key, entry, gen_token)
        plan["periods"].append({"key": key, "period_end": period_end, "minted_at": now})
        plan["period_key"] = key
        plan["period_end"] = period_end
        plan["nonce"] = new_nonce()
        plan["status"] = "active"
        plan["cancel_at_period_end"] = bool(snap.get("cancel_at_period_end"))
        plan["last_invoice_id"] = snap.get("latest_invoice_id") or ""
        store.plans[plan["plan_id"]] = plan
        return {"ok": True, "reason": "renewed", "minted": True, "plan": plan, "tokens": toks}
    except Exception:
        try:
            store.claims.pop(claim_key, None)     # let a retry mint
        except Exception:
            pass
        raise


def apply_status(store, snap: dict) -> dict:
    """Record what Stripe says about the subscription (portal cancel or undo, past_due, ended).
    A past_due or unpaid status grants nothing: it only records the status. Returns {"plan", "changed"}."""
    plan = plan_by_subscription(store.plans, snap.get("subscription_id"))
    if not plan:
        return {"plan": None, "changed": False}
    before = (plan.get("status"), plan.get("cancel_at_period_end"), plan.get("ended"))
    status = snap.get("status")
    if status:
        plan["status"] = status
    if snap.get("cancel_at_period_end") is not None:
        plan["cancel_at_period_end"] = bool(snap["cancel_at_period_end"])
    if status in ("canceled", "incomplete_expired"):
        plan["ended"] = True
    if (plan.get("status"), plan.get("cancel_at_period_end"), plan.get("ended")) != before:
        plan["nonce"] = new_nonce() if plan.get("nonce") and snap.get("rotate") else plan["nonce"]
        store.plans[plan["plan_id"]] = plan
        return {"plan": plan, "changed": True}
    return {"plan": plan, "changed": False}


def revoke(store, subscription_id: str, reason: str, now: float) -> dict:
    """A refund or dispute: mark the plan and every period entry revoked, and drop their tokens from the index."""
    plan = plan_by_subscription(store.plans, subscription_id)
    if not plan:
        return {"ok": False, "reason": "unknown_plan"}
    plan["revoked"] = True
    plan["revoked_reason"] = reason
    plan["revoked_at"] = now
    plan["cancel_at_period_end"] = True
    plan["nonce"] = new_nonce()
    store.plans[plan["plan_id"]] = plan
    dropped = 0
    for p in plan.get("periods", []):
        entry = store.tokens.get(p["key"])
        if not isinstance(entry, dict):
            continue
        entry["revoked"] = True
        store.tokens[p["key"]] = entry
        consumed = set(entry.get("consumed_tokens") or [])
        for t in entry.get("tokens") or []:
            if t in consumed:
                continue
            try:
                del store.index[t]
                dropped += 1
            except Exception:
                pass
    return {"ok": True, "reason": "revoked", "plan": plan, "dropped": dropped}


def term_refusal(store, entry: dict, now: float):
    """None when the entry may be used; ("revoked"|"expired") when its plan term has ended or it was revoked.
    Plain purchases (no plan_id, no term_ends_at) are never refused here."""
    if not isinstance(entry, dict):
        return None
    if entry.get("revoked"):
        return "revoked"
    plan_id = entry.get("plan_id")
    if plan_id:
        plan = store.plans.get(plan_id)
        if isinstance(plan, dict) and plan.get("revoked"):
            return "revoked"
    term = entry.get("term_ends_at")
    if term and term < now:
        return "expired"
    return None


# ------------------------------------------------------------------------------------------------- view + dates

def date_label(ts: int | float) -> str:
    d = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc)
    return f"{d.day} {d.strftime('%B %Y')}"


def plan_view(store, plan: dict, now: float) -> dict:
    if plan.get("revoked"):
        state = "revoked"
    elif plan.get("ended") or plan.get("period_end", 0) < now:
        state = "ended"
    elif plan.get("cancel_at_period_end"):
        state = "cancelling"
    elif plan.get("status") not in (None, "active"):
        state = "problem"
    else:
        state = "active"
    return {
        "state": state,
        "date": date_label(plan.get("period_end", 0)),
        "amount": "$79",
        "unused": 0 if state in ("revoked", "ended") else len(unused_tokens(store, plan)),
        "total": PLAN_REVIEWS,
    }


# ------------------------------------------------------------------------------------------- referral reward

def referral_block(code: str, referrer_email: str, paid_cents: int, now: float) -> dict:
    return {"code": code, "referrer_email": referrer_email, "paid_cents": paid_cents,
            "due_at": now + REWARD_DELAY, "state": "pending"}


def reward_decision(store, plan: dict, canonical_email, now: float) -> tuple[str, str]:
    """("pay"|"wait"|"reject", reason) for a plan's pending referral reward."""
    ref = plan.get("referral")
    if not isinstance(ref, dict) or ref.get("state") != "pending":
        return "reject", "no_pending_reward"
    if now < ref.get("due_at", 0):
        return "wait", "not_due"
    if plan.get("revoked"):
        return "reject", "refunded_or_disputed"
    if ref.get("paid_cents") != PLAN_PRICE_CENTS or plan.get("amount_paid") != PLAN_PRICE_CENTS:
        return "reject", "not_full_price"
    a = canonical_email(plan.get("email", "")) or plan.get("email", "").lower()
    b = canonical_email(ref.get("referrer_email", "")) or ref.get("referrer_email", "").lower()
    if not a or a == b:
        return "reject", "same_email"
    fp = plan.get("card_fingerprint")
    if fp:
        for k, p in store.plans.items():
            if str(k).startswith("pl_") and isinstance(p, dict) and p.get("email_key") == b and p.get("card_fingerprint") == fp:
                return "reject", "same_card"
    year = _dt.datetime.fromtimestamp(now, _dt.timezone.utc).year
    if int(store.plans.get(f"reward:{b}:{year}", 0) or 0) >= REWARDS_PER_REFERRER_YEAR:
        return "reject", "referrer_cap"
    return "pay", "ok"


# ------------------------------------------------------------------------------------------------------ emails

_CSS = ("font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.55; "
        "color: #1a1a1a; max-width: 600px;")
_BTN = ("display: inline-block; background: #7c3aed; color: #fff; padding: 10px 18px; border-radius: 6px; "
        "text-decoration: none; font-weight: 600;")
REPLY_CANCEL = "To cancel by email instead, reply to this message with the word cancel."


def _wrap(inner: str) -> str:
    return (f'<div style="{_CSS}">{inner}<hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">'
            f'<p style="color: #888; font-size: 0.85em;">Sent by Purplelink LLC. {REPLY_CANCEL}</p></div>')


def html_plan_welcome(*, tokens: list[str], end_label: str, link: str, renewed: bool) -> str:
    rows = "".join(
        f'<tr><td style="padding:6px 10px;border:1px solid #eee;font-family:monospace;font-size:13px;">{t}</td>'
        f'<td style="padding:6px 10px;border:1px solid #eee;">'
        f'<a href="https://purplelink.llc/tools/paper-review/upload/?direct_token={t}">Use this one</a></td></tr>'
        for t in tokens
    )
    head = "Your plan has renewed" if renewed else "Your year of reviews"
    lead = ("Your plan renewed and $79 was charged. Here are this year's 12 reviews." if renewed
            else "Thanks for subscribing. Here are your 12 Journal reviews for the year.")
    return _wrap(
        f'<h2 style="color: #6d28d9;">{head}</h2><p>{lead} Each one includes the journal check and the anonymity '
        f'check. They are good until {end_label}; unused reviews do not carry over.</p>'
        f'<table style="border-collapse: collapse; margin: 12px 0; font-size: 0.9em;">{rows}</table>'
        f'<p>The plan renews on {end_label} at $79 until you cancel. You can cancel in one click, and we email you '
        f'30 and 7 days before each renewal.</p>'
        f'<p><a href="{link}" style="{_BTN}">Manage or cancel the plan</a></p>')


def html_plan_reminder(*, days: int, end_label: str, unused: int, link: str) -> str:
    return _wrap(
        f'<h2 style="color: #6d28d9;">Your plan renews in {days} days</h2>'
        f'<p>Your year of reviews renews on {end_label} and $79 will be charged then. You have {unused} of 12 reviews '
        f'unused; they end with the year and do not carry over.</p>'
        f'<p>If you renew and then change your mind, email ben@purplelink.llc within 14 days of the charge, before '
        f'using any of that year\'s reviews, and we will refund it.</p>'
        f'<p><a href="{link}" style="{_BTN}">Cancel renewal</a></p>'
        f'<p>It is one click and nothing is charged after that. You keep your remaining reviews until {end_label}.</p>')


def html_plan_cancel_confirmation(*, end_label: str, link: str, undone: bool) -> str:
    if undone:
        return _wrap(
            f'<h2 style="color: #6d28d9;">Renewal restored</h2>'
            f'<p>Your plan will renew on {end_label} at $79, as before.</p>'
            f'<p><a href="{link}" style="{_BTN}">Cancel renewal</a></p>')
    return _wrap(
        f'<h2 style="color: #6d28d9;">Renewal cancelled</h2>'
        f'<p>Your plan will not renew. You keep your remaining reviews until {end_label}, and nothing more will be '
        f'charged.</p><p>Changed your mind? You can undo this until {end_label}.</p>'
        f'<p><a href="{link}" style="{_BTN}">Undo the cancellation</a></p>')


def html_plan_link(*, link: str) -> str:
    return _wrap(
        f'<h2 style="color: #6d28d9;">Your plan link</h2><p>Use this link to see when your plan renews or to cancel '
        f'it. It works for 60 days and replaces any earlier plan link.</p>'
        f'<p><a href="{link}" style="{_BTN}">Open my plan</a></p>')


def html_referral_reward(*, tokens: list[str]) -> str:
    rows = "".join(
        f'<tr><td style="padding:6px 10px;border:1px solid #eee;font-family:monospace;font-size:13px;">{t}</td>'
        f'<td style="padding:6px 10px;border:1px solid #eee;">'
        f'<a href="https://purplelink.llc/tools/paper-review/upload/?direct_token={t}">Use this one</a></td></tr>'
        for t in tokens
    )
    return (f'<div style="{_CSS}"><h2 style="color: #6d28d9;">6 Journal reviews, thanks to your referral</h2>'
            f'<p>Someone bought a year of reviews with your referral code. Here are 6 Journal reviews, with the '
            f'journal check and the anonymity check included. They do not expire.</p>'
            f'<table style="border-collapse: collapse; margin: 12px 0; font-size: 0.9em;">{rows}</table>'
            f'<hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">'
            f'<p style="color: #888; font-size: 0.85em;">Sent by Purplelink LLC.</p></div>')


# ------------------------------------------------------------------------------------------------- daily loop

async def run_sweep(store, *, now: float, secret: str, cfg: dict, gen_token, canonical_email,
                    fetch_subscription: Callable[[str], Awaitable[dict | None]],
                    send_email: Callable[..., Awaitable[dict]],
                    on_renewed: Callable[[dict], Awaitable[None]]) -> dict:
    """One daily pass. For every live plan: re-read the subscription from Stripe (never send blind), pick up a renewal
    we missed, record a portal cancel, and send the 30 or 7 day reminder once per period. Then pay due referral
    rewards. Reminders go to opted-out addresses too: they are about a charge."""
    out = {"reminded": 0, "renewed": 0, "skipped_cancelled": 0, "rewards": 0, "reward_rejected": 0, "errors": 0}
    for key, plan in list(store.plans.items()):
        if not str(key).startswith("pl_") or not isinstance(plan, dict):
            continue
        if plan.get("revoked") or plan.get("ended"):
            continue
        try:
            snap = await fetch_subscription(plan["subscription_id"])
        except Exception:
            snap = None
        if not snap:
            out["errors"] += 1          # no blind send: try again tomorrow
            continue
        apply_status(store, snap)
        plan = get_plan(store.plans, plan["plan_id"]) or plan
        if snap.get("status") == "active" and isinstance(snap.get("period_end"), int) and snap["period_end"] > plan["period_end"]:
            res = renew(store, snap, cfg=cfg, gen_token=gen_token, now=now)
            if res.get("minted"):
                out["renewed"] += 1
                await on_renewed(res)
            continue
        if plan.get("ended") or plan.get("cancel_at_period_end") or snap.get("status") != "active":
            out["skipped_cancelled"] += 1
            continue
        days_left = (plan["period_end"] - now) / 86400
        if days_left <= 0:
            continue
        marks = plan.setdefault("reminders", {}).setdefault(str(plan["period_end"]), {})
        want = None
        if days_left <= 7 and not marks.get("7"):
            want = 7
        elif 7 < days_left <= 30 and not marks.get("30"):
            want = 30
        if want is None:
            continue
        link = plan_link(secret, plan, now)
        res = await send_email(
            to=plan["email"], subject=f"Your plan renews in {max(1, round(days_left)) if want == 7 else 30} days: $79",
            html=html_plan_reminder(days=(max(1, round(days_left)) if want == 7 else 30), end_label=date_label(plan["period_end"]),
                                    unused=len(unused_tokens(store, plan)), link=link),
            tag="annual_reminder_%d" % want)
        if res.get("status") == "ok":
            marks[str(want)] = now
            if want == 7:
                marks.setdefault("30", "skipped")
            store.plans[plan["plan_id"]] = plan
            out["reminded"] += 1
        else:
            out["errors"] += 1
    # Referral rewards
    for key, plan in list(store.plans.items()):
        if not str(key).startswith("pl_") or not isinstance(plan, dict):
            continue
        ref = plan.get("referral")
        if not isinstance(ref, dict) or ref.get("state") != "pending":
            continue
        verdict, why = reward_decision(store, plan, canonical_email, now)
        if verdict == "wait":
            continue
        if verdict == "reject":
            ref["state"] = "rejected"
            ref["reason"] = why
            store.plans[plan["plan_id"]] = plan
            out["reward_rejected"] += 1
            continue
        b = canonical_email(ref["referrer_email"]) or ref["referrer_email"].lower()
        year = _dt.datetime.fromtimestamp(now, _dt.timezone.utc).year
        ref["state"] = "paid"            # set first: a crash after this skips a reward rather than paying twice
        ref["paid_at"] = now
        store.plans[plan["plan_id"]] = plan
        store.plans[f"reward:{b}:{year}"] = int(store.plans.get(f"reward:{b}:{year}", 0) or 0) + 1
        reward_key = f"reward-{plan['plan_id']}"
        entry = {
            "tokens": [], "product_key": "paper-review-journal", "product_cfg": REWARD_CFG,
            "email": ref["referrer_email"], "amount_paid": 0, "redeemed": False, "consumed_tokens": [],
            "created_at": now, "expires_at": 0, "source": "annual-referral", "referred_plan": plan["plan_id"],
        }
        toks = [gen_token() for _ in range(REWARD_REVIEWS)]
        entry["tokens"] = toks
        store.tokens[reward_key] = entry
        for t in toks:
            store.index[t] = reward_key
        await send_email(to=ref["referrer_email"], subject="6 Journal reviews from your referral",
                         html=html_referral_reward(tokens=toks), tag="annual_referral_reward")
        out["rewards"] += 1
    return out
