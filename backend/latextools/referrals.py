"""Referrals for every product (docs/designs/buyer-revenue-program.md, part 2; Ben, 2026-11-05).

Every buyer gets a link, https://purplelink.llc/?ref=<code>, where <code> is `_paper_referral_code(email)` in
app.py (the same code the Paper Review report footer has always carried). A friend who buys through it gets 20% off
(the Stripe coupon `purplelink-friend-20`, applied by netlify/functions/checkout.mjs). Fourteen days after a
referred sale the referrer gets one free Standard Paper Review, if every rule in `decide` holds.

Plain Python over dict-like stores, like annual.py, so tests run it with in-memory dicts and no network.

Records
-------
ledger[<canonical email>]   {first_paid_at, first_session, sessions[]}: every paid order since this shipped, plus the
                            one-off backfill of earlier Stripe sessions. "First purchase" is read from here.
rewards["rw:<session_id>"]  one pending reward per referred order
rewards["referred:<canon>"] the order (or annual plan) that already earned a reward for this referred buyer; checked
                            here and by annual.reward_decision, so one person never pays out twice
rewards["by:<canon>"]       timestamps of rewards paid to this referrer (cap: 20 in 365 days)
"""

from __future__ import annotations

import re
from typing import Awaitable, Callable

FRIEND_PERCENT = 20
FRIEND_COUPON = "purplelink-friend-20"
MIN_REWARD_PAID_CENTS = 1500
REWARD_DELAY = 14 * 86400
REWARD_CAP = 20
REWARD_WINDOW = 365 * 86400
GIVE_UP_AFTER = 30 * 86400          # a sale Stripe cannot be read for this long after it was due is dropped
MAX_LEDGER_SESSIONS = 10
CODE_RE = re.compile(r"^[0-9a-f]{10}$")
SITE_LINK = "https://purplelink.llc/?ref={code}"

# Subscriptions never earn a Standard token (the annual plan pays its own reward in annual.py).
NO_REWARD_PRODUCTS = frozenset({
    "paper-review-annual", "vitae-plus-monthly", "vitae-plus-annual", "live-scholar", "live-funding",
    "digest-monthly", "digest-annual",
})

REWARD_CFG = {"category": "paper-review", "tier": "standard", "qty": 1, "bundled_anonymity": True}


def link_for(code: str) -> str:
    return SITE_LINK.format(code=code) if code else ""


def _canon(canonical_email, email: str) -> str:
    email = (email or "").strip()
    try:
        c = canonical_email(email)
    except Exception:
        c = None
    return c or email.lower()


# ------------------------------------------------------------------------------------------------------ ledger

def record_purchase(ledger, canon: str, session_id: str, paid_at: float) -> dict:
    """Add a paid order to the buyer's ledger entry. Idempotent per session; an older order (backfill) becomes the
    first one."""
    if not canon or not session_id:
        return {}
    entry = ledger.get(canon)
    if not isinstance(entry, dict):
        entry = {"first_paid_at": paid_at, "first_session": session_id, "sessions": []}
    sessions = list(entry.get("sessions") or [])
    if session_id not in sessions:
        sessions.append(session_id)
    if paid_at < float(entry.get("first_paid_at") or paid_at) or entry.get("first_session") == session_id:
        entry["first_paid_at"] = paid_at
        entry["first_session"] = session_id
    entry["sessions"] = sessions[-MAX_LEDGER_SESSIONS:]
    ledger[canon] = entry
    return entry


# ----------------------------------------------------------------------------------------------------- pending

def make_pending(rewards, *, session_id: str, referrer_email: str, referred_email: str, product: str,
                 paid_cents: int, now: float, canonical_email) -> str:
    """Record a referred order for the daily loop. Returns "pending", or why nothing was recorded."""
    if product in NO_REWARD_PRODUCTS:
        return "subscription"
    if not isinstance(paid_cents, int) or paid_cents < MIN_REWARD_PAID_CENTS:
        return "below_minimum"
    if not referrer_email or not referred_email:
        return "no_email"
    if _canon(canonical_email, referrer_email) == _canon(canonical_email, referred_email):
        return "same_email"
    key = f"rw:{session_id}"
    if isinstance(rewards.get(key), dict):
        return "exists"
    rewards[key] = {
        "session_id": session_id, "referrer_email": referrer_email[:200], "referred_email": referred_email[:200],
        "product": product, "paid_cents": paid_cents, "created_at": now, "due_at": now + REWARD_DELAY,
        "state": "pending",
    }
    return "pending"


def _recent(stamps, now: float) -> int:
    return sum(1 for t in (stamps or []) if isinstance(t, (int, float)) and now - t < REWARD_WINDOW)


def decide(rewards, ledger, item: dict, *, now: float, canonical_email, charge: dict | None,
           referrer_fingerprints: set[str]) -> tuple[str, str]:
    """("pay"|"wait"|"reject", reason). `charge` is the referred order's Stripe state ({refunded, disputed,
    fingerprint}) or None when Stripe could not be read."""
    if not isinstance(item, dict) or item.get("state") != "pending":
        return "reject", "no_pending_reward"
    if now < float(item.get("due_at") or 0):
        return "wait", "not_due"
    if charge is None:
        if now > float(item.get("due_at") or 0) + GIVE_UP_AFTER:
            return "reject", "stripe_unreadable"
        return "wait", "stripe_unreadable"
    if charge.get("refunded") or charge.get("disputed"):
        return "reject", "refunded_or_disputed"
    if int(item.get("paid_cents") or 0) < MIN_REWARD_PAID_CENTS:
        return "reject", "below_minimum"
    a = _canon(canonical_email, item.get("referred_email", ""))
    b = _canon(canonical_email, item.get("referrer_email", ""))
    if not a or a == b:
        return "reject", "same_email"
    first = ledger.get(a)
    if not isinstance(first, dict) or first.get("first_session") != item.get("session_id"):
        return "reject", "not_first_purchase"
    fp = charge.get("fingerprint") or ""
    if fp and fp in referrer_fingerprints:
        return "reject", "same_card"
    if rewards.get(f"referred:{a}"):
        return "reject", "already_rewarded"
    if _recent(rewards.get(f"by:{b}"), now) >= REWARD_CAP:
        return "reject", "referrer_cap"
    return "pay", "ok"


# ------------------------------------------------------------------------------------------------------- email

_CSS = ("font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.55; "
        "color: #222; max-width: 560px; margin: 0 auto; padding: 24px;")
_BTN = ("display: inline-block; background: #7c3aed; color: #fff; padding: 10px 18px; border-radius: 6px; "
        "text-decoration: none; font-weight: 600;")


def html_reward(*, token: str, link: str) -> str:
    url = f"https://purplelink.llc/tools/paper-review/upload/?direct_token={token}"
    return (f'<div style="{_CSS}"><h2 style="color: #6d28d9;">A free Paper Review, thanks to your referral</h2>'
            f'<p>Someone made their first Purplelink purchase through your link. Here is one Standard Paper Review '
            f'(with the anonymity check). It does not expire.</p>'
            f'<p><a href="{url}" style="{_BTN}">Use my free review</a></p>'
            f'<p style="font-family: monospace; font-size: 13px;">{token}</p>'
            f'<p>Your link, if you want to share it again: <a href="{link}">{link}</a>. A friend gets 20% off their '
            f'first order.</p>'
            f'<hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">'
            f'<p style="color: #888; font-size: 0.85em;">Sent by Purplelink LLC.</p></div>')


# -------------------------------------------------------------------------------------------------- daily loop

async def run_sweep(store, *, now: float, canonical_email, gen_token: Callable[[], str],
                    fetch_charge: Callable[[str], Awaitable[dict | None]],
                    referral_code_for: Callable[[str], str],
                    send_email: Callable[..., Awaitable[dict]],
                    opted_out: Callable[[str], bool]) -> dict:
    """Pay due referral rewards. `store` has rewards, ledger, tokens and index. A reward is marked paid before its
    token is minted: a crash in between skips one reward rather than paying twice."""
    out = {"paid": 0, "rejected": 0, "waiting": 0, "not_emailed": 0}
    for key, item in list(store.rewards.items()):
        if not str(key).startswith("rw:") or not isinstance(item, dict) or item.get("state") != "pending":
            continue
        if now < float(item.get("due_at") or 0):
            out["waiting"] += 1
            continue
        charge = await fetch_charge(item["session_id"])
        fps: set[str] = set()
        b = _canon(canonical_email, item.get("referrer_email", ""))
        if charge is not None and charge.get("fingerprint"):
            for sid in (store.ledger.get(b) or {}).get("sessions", []) if isinstance(store.ledger.get(b), dict) else []:
                ref_charge = await fetch_charge(sid)
                if ref_charge and ref_charge.get("fingerprint"):
                    fps.add(ref_charge["fingerprint"])
        verdict, why = decide(store.rewards, store.ledger, item, now=now, canonical_email=canonical_email,
                              charge=charge, referrer_fingerprints=fps)
        if verdict == "wait":
            out["waiting"] += 1
            continue
        if verdict == "reject":
            item["state"] = "rejected"
            item["reason"] = why
            store.rewards[key] = item
            out["rejected"] += 1
            continue
        a = _canon(canonical_email, item.get("referred_email", ""))
        item["state"] = "paid"
        item["paid_at"] = now
        store.rewards[key] = item
        store.rewards[f"referred:{a}"] = item["session_id"]
        stamps = [t for t in (store.rewards.get(f"by:{b}") or []) if isinstance(t, (int, float)) and now - t < REWARD_WINDOW]
        store.rewards[f"by:{b}"] = stamps + [now]
        token = gen_token()
        reward_key = f"referral-{item['session_id']}"
        store.tokens[reward_key] = {
            "tokens": [token], "product_key": "paper-review-standard", "product_cfg": REWARD_CFG,
            "email": item["referrer_email"], "amount_paid": 0, "redeemed": False, "consumed_tokens": [],
            "created_at": now, "expires_at": 0, "source": "referral", "referred_session": item["session_id"],
        }
        store.index[token] = reward_key
        out["paid"] += 1
        if opted_out(item["referrer_email"]):
            out["not_emailed"] += 1
            continue
        await send_email(to=item["referrer_email"], subject="A free Paper Review from your referral",
                         html=html_reward(token=token, link=link_for(referral_code_for(item["referrer_email"]))),
                         tag="referral_reward")
    return out


def charge_state(session: dict | None) -> dict | None:
    """Reduce a Checkout Session (expanded payment_intent.latest_charge) to what `decide` needs."""
    if not isinstance(session, dict):
        return None
    pi = session.get("payment_intent")
    ch = pi.get("latest_charge") if isinstance(pi, dict) else None
    if not isinstance(ch, dict):
        # Paid sessions always have a charge; a $0 order has none and never reaches the loop (paid_cents floor).
        return {"refunded": False, "disputed": False, "fingerprint": ""}
    card = ((ch.get("payment_method_details") or {}).get("card") or {})
    return {
        "refunded": bool(ch.get("refunded")) or int(ch.get("amount_refunded") or 0) > 0,
        "disputed": bool(ch.get("disputed")),
        "fingerprint": card.get("fingerprint") or "",
    }
