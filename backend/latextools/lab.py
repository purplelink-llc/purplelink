"""Lab plans (monthly-granted subscription review plans) and the one-time Publication Pack.

backend/app.py holds the HTTP routes and the Stripe calls; everything here is plain Python over dict-like stores, so
tests run it with in-memory dicts and no network. Modelled on annual.py, which this module never changes.

Records
-------
plans[plan_id]            "lab_..." one per subscription (kept in the annual plans dict; annual code only reads "pl_" keys)
plans["labsub:<sub_id>"]  -> plan_id
plans["labgroup:<key>"]   -> plan_id (Lab Plus group link)
paper_tokens[<root>]      the first grant's entry (the Stripe session id, or "lab-<sub_id>" for invoice plans)
paper_tokens[<root>#g<pe>.<j>]  later grants
paper_tokens["fu-rev:<h>"], ["fu-resp:<h>"]  the follow-up entries minted when a plan review is used

Every grant entry carries lab_plan, plan_id, subscription_id, grant_id and term_ends_at, so annual.term_refusal
(which looks the plan up by plan_id) refuses a revoked plan and an expired grant without any lab-specific code.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import secrets
import time
import urllib.parse as _up
from typing import Awaitable, Callable

from . import annual

PLAN_PREFIX = "lab_"
PUBLICATION_PACK = "publication-pack"
PLAN_TOKEN_TTL = 60 * 86400
PLAN_TOKEN_MAX = 400
CARRY_MONTHS = 2                      # a grant is usable for its own month and the next
FOLLOWUP_TTL = 365 * 86400
REHAND_AFTER = 30 * 60
REMINDER_DAYS = (30, 7)
SITE = "https://purplelink.llc"

LAB_PRODUCTS: dict[str, dict] = {
    "lab-monthly":      {"tier": "lab",      "name": "Lab",      "reviews": 20, "billing_months": 1,  "amount": 19900},
    "lab-annual":       {"tier": "lab",      "name": "Lab",      "reviews": 20, "billing_months": 12, "amount": 199000},
    "lab-plus-monthly": {"tier": "lab-plus", "name": "Lab Plus", "reviews": 40, "billing_months": 1,  "amount": 34900},
    "lab-plus-annual":  {"tier": "lab-plus", "name": "Lab Plus", "reviews": 40, "billing_months": 12, "amount": 349000},
}

PACK_AMOUNT = 5900
PACK_PARTS = (
    # (suffix, category, name, amount_cents)
    ("", "paper-review", "Paper Review", 3900),
    ("#revision", "revision-review", "Revision Review", 500),
    ("#draft", "response-draft", "Response letter draft", 2400),
)
PACK_START_PATHS = {
    "revision-review": "/tools/paper-review/revision/upload/",
    "response-draft": "/tools/response-review/draft/upload/",
}
FOLLOWUPS = (
    # (kind, key prefix, category, name, amount_cents, upload path)
    ("revision", "fu-rev:", "revision-review", "Revision Review", 500, "/tools/paper-review/revision/upload/"),
    ("response", "fu-resp:", "response-review", "Response Review", 1200, "/tools/response-review/upload/"),
)


# --------------------------------------------------------------------------------------------------- small helpers

def add_months(ts: int | float, n: int) -> int:
    """`ts` plus n calendar months in UTC, the day clamped to the target month's length. Always computed from the
    anchor, never iteratively, so 31 January plus 1 and plus 2 months are 28 February and 31 March."""
    d = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc)
    m = d.month - 1 + n
    year, month = d.year + m // 12, m % 12 + 1
    nxt = _dt.datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=_dt.timezone.utc)
    last = (nxt - _dt.timedelta(days=1)).day
    return int(d.replace(year=year, month=month, day=min(d.day, last)).timestamp())


def new_plan_id() -> str:
    return PLAN_PREFIX + secrets.token_urlsafe(12)


def new_group_key() -> str:
    return "lg_" + secrets.token_urlsafe(18)


def new_nonce() -> str:
    return secrets.token_urlsafe(6)


def date_label(ts) -> str:
    return annual.date_label(ts)


def start_url(token: str) -> str:
    return f"{SITE}/tools/paper-review/upload/?direct_token={_up.quote(token, safe='')}"


def _keyed_url(path: str, key: str) -> str:
    return f"{SITE}{path}?session_id={_up.quote(key, safe='')}"


def group_url(plan: dict) -> str:
    return f"{SITE}/labs/start/?k={plan['group_key']}" if plan.get("group_key") else ""


# --------------------------------------------------------------------------------------------- plan link token

def sign_plan_token(secret: str, plan_id: str, nonce: str, now: float | None = None) -> str:
    exp = int((now if now is not None else time.time()) + PLAN_TOKEN_TTL)
    sig = hmac.new(secret.encode(), f"lab-plan:{plan_id}:{exp}:{nonce}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{plan_id}.{exp}.{nonce}.{sig}"


def parse_plan_token(secret: str, token: str, now: float | None = None):
    """(plan_id, nonce) for a well-formed, unexpired, correctly signed lab token; otherwise None."""
    if not secret or not isinstance(token, str) or len(token) > PLAN_TOKEN_MAX:
        return None
    parts = token.split(".")
    if len(parts) != 4:
        return None
    plan_id, exp_s, nonce, sig = parts
    if not plan_id.startswith(PLAN_PREFIX) or not exp_s.isdigit():
        return None
    want = hmac.new(secret.encode(), f"lab-plan:{plan_id}:{exp_s}:{nonce}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        return None
    if int(exp_s) < (now if now is not None else time.time()):
        return None
    return plan_id, nonce


def plan_link(secret: str, plan: dict, now: float | None = None) -> str:
    return f"{SITE}/labs/plan/?t=" + sign_plan_token(secret, plan["plan_id"], plan["nonce"], now)


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


def rotate_nonce(store, plan: dict) -> dict:
    plan["nonce"] = new_nonce()
    store.plans[plan["plan_id"]] = plan
    return plan


# ----------------------------------------------------------------------------------------------- Stripe parsing

def snapshot_from_stripe(sub: dict) -> dict:
    """What lab needs from a Stripe subscription (latest_invoice optionally expanded). Unlike annual's snapshot it
    carries period_start: monthly grants inside a yearly period are counted from it."""
    items = ((sub.get("items") or {}).get("data")) or []
    first = items[0] if items and isinstance(items[0], dict) else {}
    period_end = first.get("current_period_end")
    if not isinstance(period_end, int):
        period_end = sub.get("current_period_end")
    period_start = first.get("current_period_start")
    if not isinstance(period_start, int):
        period_start = sub.get("current_period_start")
    inv = sub.get("latest_invoice")
    inv = inv if isinstance(inv, dict) else {}
    cust = sub.get("customer")
    return {
        "subscription_id": sub.get("id"),
        "customer": cust if isinstance(cust, str) else (cust or {}).get("id"),
        "status": sub.get("status"),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "period_start": period_start if isinstance(period_start, int) else None,
        "period_end": period_end if isinstance(period_end, int) else None,
        "latest_invoice_id": inv.get("id") if inv else (sub.get("latest_invoice") if isinstance(sub.get("latest_invoice"), str) else None),
        "latest_invoice_paid": (inv.get("status") == "paid") if inv else None,
        "metadata_product": (sub.get("metadata") or {}).get("product", ""),
    }


def amount_ok(cfg: dict, amount_paid, amount_subtotal) -> bool:
    """Checkout path only: the list price must match and the paid amount may be anything from 0 (a 100% code)
    up to the list price. The invoice path sends neither and always passes."""
    if amount_subtotal is not None:
        if not isinstance(amount_subtotal, int) or amount_subtotal != cfg["amount"]:
            return False
    if amount_paid is not None:
        if not isinstance(amount_paid, int) or not 0 <= amount_paid <= cfg["amount"]:
            return False
    return True


# ---------------------------------------------------------------------------------------------------- plan lookup

def get_plan(plans, plan_id):
    p = plans.get(plan_id) if isinstance(plan_id, str) else None
    return p if isinstance(p, dict) else None


def plan_by_subscription(plans, subscription_id: str):
    if not subscription_id:
        return None
    return get_plan(plans, plans.get("labsub:" + subscription_id))


def plan_by_group(plans, key: str):
    if not isinstance(key, str) or not key:
        return None
    return get_plan(plans, plans.get("labgroup:" + key))


def plan_by_email(plans_items, email_key: str):
    """The live lab plan for an email address (newest first), or None."""
    best = None
    for k, p in plans_items:
        if not isinstance(p, dict) or not str(k).startswith(PLAN_PREFIX):
            continue
        if p.get("email_key") == email_key and not p.get("revoked") and not p.get("ended"):
            if best is None or p.get("created_at", 0) > best.get("created_at", 0):
                best = p
    return best


def plan_state(plan: dict, now: float) -> str:
    if plan.get("revoked"):
        return "revoked"
    if plan.get("ended") or plan.get("period_end", 0) < now:
        return "ended"
    if plan.get("cancel_at_period_end"):
        return "cancelling"
    if plan.get("status") not in (None, "active"):
        return "problem"
    return "active"


# ----------------------------------------------------------------------------------------------------- the plan

def _entry_cfg(reviews: int) -> dict:
    return {"category": "paper-review", "tier": "standard", "qty": reviews,
            "bundled_anonymity": True, "bundled_journal": True}


def _grant_entry(plan: dict, tokens: list[str], gid: str, start: int, now: float) -> dict:
    cfg = LAB_PRODUCTS[plan["product"]]
    return {
        "tokens": tokens,
        "product_key": plan["product"],
        "product_cfg": _entry_cfg(cfg["reviews"]),
        "email": plan["email"],
        "amount_paid": cfg["amount"] // cfg["billing_months"],
        "redeemed": False,
        "consumed_tokens": [],
        "created_at": now,
        "expires_at": 0,
        "term_ends_at": add_months(start, CARRY_MONTHS),
        "plan_id": plan["plan_id"],
        "subscription_id": plan["subscription_id"],
        "lab_plan": True,
        "grant_id": gid,
    }


def register(store, *, subscription_id: str, product: str, email: str, root: str, customer: str, snap: dict,
             gen_token, now: float, canonical_email) -> dict:
    """Create the plan record and its indexes (no tokens yet; `sync` issues the first grant). Idempotent on the
    subscription: a claim, then a re-check of the stored plan. Returns {"ok", "reason", "plan", "created"}."""
    cfg = LAB_PRODUCTS.get(product)
    if cfg is None:
        return {"ok": False, "reason": "unknown_product"}
    existing = plan_by_subscription(store.plans, subscription_id)
    if existing:
        return {"ok": True, "reason": "exists", "plan": existing, "created": False}
    claim_key = f"labreg:{subscription_id}"
    if not store.claims.put(claim_key, now, skip_if_exists=True):
        existing = plan_by_subscription(store.plans, subscription_id)
        if existing:
            return {"ok": True, "reason": "exists", "plan": existing, "created": False}
        return {"ok": False, "reason": "in_progress"}
    try:
        existing = plan_by_subscription(store.plans, subscription_id)
        if existing:
            return {"ok": True, "reason": "exists", "plan": existing, "created": False}
        plan = {
            "plan_id": new_plan_id(),
            "kind": "lab",
            "product": product,
            "tier": cfg["tier"],
            "reviews_per_month": cfg["reviews"],
            "billing_months": cfg["billing_months"],
            "email": email,
            "email_key": (canonical_email(email) or email.strip().lower()) if email else "",
            "subscription_id": subscription_id,
            "customer": customer or snap.get("customer") or "",
            "root": root,
            "status": snap.get("status") or "active",
            "cancel_at_period_end": bool(snap.get("cancel_at_period_end")),
            "period_start": snap.get("period_start"),
            "period_end": snap.get("period_end"),
            "grants": [],
            "nonce": new_nonce(),
            "revoked": False,
            "ended": False,
            "created_at": now,
            "reminders": {},
        }
        if cfg["tier"] == "lab-plus":
            plan["group_key"] = new_group_key()
        store.plans[plan["plan_id"]] = plan
        store.plans["labsub:" + subscription_id] = plan["plan_id"]
        if plan.get("group_key"):
            store.plans["labgroup:" + plan["group_key"]] = plan["plan_id"]
        return {"ok": True, "reason": "registered", "plan": plan, "created": True}
    except Exception:
        try:
            store.claims.pop(claim_key, None)
        except Exception:
            pass
        raise


def _mint_grant(store, plan: dict, gid: str, start: int, gen_token, now: float) -> dict:
    n = LAB_PRODUCTS[plan["product"]]["reviews"]
    key = plan["root"] if not plan["grants"] else f"{plan['root']}#g{gid}"
    toks = [gen_token() for _ in range(n)]
    entry = _grant_entry(plan, toks, gid, start, now)
    store.tokens[key] = entry
    for t in toks:
        store.index[t] = key
    grant = {"id": gid, "key": key, "start": start, "ends": entry["term_ends_at"], "count": n}
    plan["grants"].append(grant)
    store.plans[plan["plan_id"]] = plan
    return {"key": key, "grant": grant, "tokens": toks}


def due_grants(plan: dict, now: float) -> list[tuple[int, int, str]]:
    """(j, due_at, grant id) for every monthly grant of the current paid period that is due and not yet issued.
    A grant whose own term already ended is skipped."""
    ps, pe, months = plan.get("period_start"), plan.get("period_end"), int(plan.get("billing_months") or 1)
    if not isinstance(ps, int) or not isinstance(pe, int):
        return []
    have = {g["id"] for g in plan.get("grants", [])}
    out = []
    for j in range(months):
        due = add_months(ps, j)
        if due > now or due >= pe:
            break
        gid = f"{pe}.{j}"
        if gid in have or add_months(due, CARRY_MONTHS) < now:
            continue
        out.append((j, due, gid))
    return out


def sync(store, snap: dict, *, gen_token, now: float) -> dict:
    """Apply what Stripe says and issue every grant that is due. Idempotent and safe to call from several places
    (webhook, plan page, redeem, daily sweep). Grants need an active subscription and a paid latest invoice.

    Returns {"ok", "reason", "plan", "minted": [{"key","grant","tokens"}], "cancel_flipped": bool, "changed": bool}."""
    plan = plan_by_subscription(store.plans, snap.get("subscription_id"))
    if not plan:
        return {"ok": False, "reason": "unknown_plan", "minted": [], "cancel_flipped": False, "changed": False}
    before = (plan.get("status"), plan.get("cancel_at_period_end"), plan.get("ended"), plan.get("product"),
              plan.get("period_start"), plan.get("period_end"), plan.get("customer"))
    was_cancelling = bool(plan.get("cancel_at_period_end"))
    status = snap.get("status")
    if status:
        plan["status"] = status
    if snap.get("cancel_at_period_end") is not None and not plan.get("revoked"):
        plan["cancel_at_period_end"] = bool(snap["cancel_at_period_end"])
    if status in ("canceled", "incomplete_expired"):
        plan["ended"] = True
    if snap.get("customer") and not plan.get("customer"):
        plan["customer"] = snap["customer"]
    new_product = snap.get("metadata_product")
    if new_product in LAB_PRODUCTS and new_product != plan.get("product"):
        cfg = LAB_PRODUCTS[new_product]          # a mid-period change applies from the next grant
        plan.update(product=new_product, tier=cfg["tier"], reviews_per_month=cfg["reviews"],
                    billing_months=cfg["billing_months"])
        if cfg["tier"] == "lab-plus" and not plan.get("group_key"):
            plan["group_key"] = new_group_key()
            store.plans["labgroup:" + plan["group_key"]] = plan["plan_id"]
    ps, pe = snap.get("period_start"), snap.get("period_end")
    if isinstance(pe, int) and isinstance(ps, int) and pe >= int(plan.get("period_end") or 0):
        plan["period_start"], plan["period_end"] = ps, pe
    changed = before != (plan.get("status"), plan.get("cancel_at_period_end"), plan.get("ended"), plan.get("product"),
                         plan.get("period_start"), plan.get("period_end"), plan.get("customer"))
    if changed:
        store.plans[plan["plan_id"]] = plan
    flipped = bool(plan.get("cancel_at_period_end")) and not was_cancelling and not plan.get("revoked")
    res = {"ok": True, "reason": "synced", "plan": plan, "minted": [], "cancel_flipped": flipped, "changed": changed}
    if plan.get("revoked"):
        res["reason"] = "revoked"
        return res
    if status != "active" or snap.get("latest_invoice_paid") is not True:
        res["reason"] = "not_active" if status != "active" else "unpaid"
        return res
    for j, due, gid in due_grants(plan, now):
        claim_key = f"lab:{plan['subscription_id']}:{plan['period_end']}:{j}"
        if not store.claims.put(claim_key, now, skip_if_exists=True):
            continue
        try:
            plan = get_plan(store.plans, plan["plan_id"]) or plan
            if any(g["id"] == gid for g in plan["grants"]):
                continue
            res["minted"].append(_mint_grant(store, plan, gid, due, gen_token, now))
        except Exception:
            try:
                store.claims.pop(claim_key, None)
            except Exception:
                pass
            raise
    res["plan"] = get_plan(store.plans, plan["plan_id"]) or plan
    return res


def revoke(store, subscription_id: str, reason: str, now: float, dispute_id: str = "") -> dict:
    """A refund or dispute. Only the plan's revoked flag is set (annual.term_refusal enforces it for every grant and
    follow-up). Index rows stay, so restore is trivial. A dispute is remembered by id; a refund is never undone."""
    plan = plan_by_subscription(store.plans, subscription_id)
    if not plan:
        return {"ok": False, "reason": "unknown_plan"}
    if not plan.get("revoked"):
        plan["cancel_before_revoke"] = bool(plan.get("cancel_at_period_end"))
    if reason == "dispute":
        open_ids = list(plan.get("disputes_open") or [])
        if dispute_id and dispute_id not in open_ids:
            open_ids.append(dispute_id)
        plan["disputes_open"] = open_ids
    else:
        plan["refund_revoked"] = True
    plan["revoked"] = True
    plan["revoked_reason"] = reason
    plan["revoked_at"] = now
    plan["cancel_at_period_end"] = True
    plan["nonce"] = new_nonce()
    store.plans[plan["plan_id"]] = plan
    return {"ok": True, "reason": "revoked", "plan": plan}


def restore(store, subscription_id: str, dispute_id: str, now: float) -> dict:
    """A won dispute: undo the revoke it caused, only when disputes alone caused it and this was the last open one."""
    plan = plan_by_subscription(store.plans, subscription_id)
    if not plan:
        return {"ok": False, "reason": "unknown_plan", "restored": False}
    if not plan.get("revoked"):
        return {"ok": True, "reason": "not_revoked", "restored": False}
    if plan.get("refund_revoked") or (plan.get("revoked_reason") != "dispute" and "disputes_open" not in plan):
        return {"ok": True, "reason": "refunded", "restored": False}
    open_ids = [d for d in (plan.get("disputes_open") or []) if d != dispute_id]
    plan["disputes_open"] = open_ids
    if open_ids:
        store.plans[plan["plan_id"]] = plan
        return {"ok": True, "reason": "disputes_still_open", "restored": False}
    plan["revoked"] = False
    plan["restored_at"] = now
    plan["cancel_at_period_end"] = bool(plan.pop("cancel_before_revoke", plan.get("cancel_at_period_end")))
    plan["nonce"] = new_nonce()
    store.plans[plan["plan_id"]] = plan
    return {"ok": True, "reason": "restored", "plan": plan, "restored": True}


# ------------------------------------------------------------------------------------- grants, follow-ups, view

def _live_entry(store, plan: dict, grant: dict, now: float):
    """The grant's stored entry when it can still be used (present, not revoked, term not over), else None."""
    entry = store.tokens.get(grant.get("key"))
    if not isinstance(entry, dict) or entry.get("revoked") or plan.get("revoked"):
        return None
    if (grant.get("ends") or 0) < now:
        return None
    return entry


def _unused(entry: dict) -> list[str]:
    used = set(entry.get("consumed_tokens") or [])
    return [t for t in entry.get("tokens") or [] if t not in used]


def followup_root(entry: dict, token: str) -> str:
    """The token a review's follow-ups are keyed on: a replacement issued after a failed run maps back to the
    original, so a re-run never earns a second pair."""
    return (entry.get("reissued_from") or {}).get(token, token)


def followup_keys(root_token: str) -> dict:
    h = hashlib.sha256(root_token.encode()).hexdigest()[:24]
    return {kind: prefix + h for kind, prefix, *_ in FOLLOWUPS}


def followup_links(keys: dict) -> list[dict]:
    return [{"kind": kind, "name": name, "url": _keyed_url(path, keys[kind])}
            for kind, _p, _c, name, _a, path in FOLLOWUPS]


def mint_followups(store, plan: dict, entry: dict, token: str, gen_token, now: float) -> dict | None:
    """Mint the Revision Review and Response Review that come with a plan review, once per original token.
    Recorded on the plan's grant (the grant entry may be swept long before the 12-month links end), so a repeat call,
    including one for a replacement token, mints nothing new. Returns the keys, or None when it is not a plan entry."""
    if not entry.get("lab_plan") or not entry.get("plan_id"):
        return None
    root_token = followup_root(entry, token)
    keys = followup_keys(root_token)
    grant = next((g for g in plan.get("grants", []) if g.get("id") == entry.get("grant_id")), None)
    if grant is not None and root_token[:8] in (grant.get("fu") or {}):
        return keys
    for kind, prefix, category, name, amount, _path in FOLLOWUPS:
        key = keys[kind]
        cfg = {"category": category, "qty": 1}
        fu = {
            "tokens": [], "product_key": category, "product_cfg": cfg, "email": plan.get("email", ""),
            "amount_paid": amount, "redeemed": False, "consumed_tokens": [], "created_at": now, "expires_at": 0,
            "term_ends_at": int(now + FOLLOWUP_TTL), "plan_id": plan["plan_id"],
            "subscription_id": plan.get("subscription_id", ""), "source": "lab-followup",
        }
        tok = gen_token()
        fu["tokens"] = [tok]
        if store.tokens.put(key, fu, skip_if_exists=True):
            store.index[tok] = key
        else:
            have = store.tokens.get(key)
            if isinstance(have, dict):
                for t in _unused(have):
                    if store.index.get(t) is None:
                        store.index[t] = key
    if grant is not None:
        fresh = get_plan(store.plans, plan["plan_id"]) or plan
        for g in fresh.get("grants", []):
            if g.get("id") == grant["id"]:
                g.setdefault("fu", {})[root_token[:8]] = keys
        store.plans[fresh["plan_id"]] = fresh
    return keys


def _followup_view(store, plan: dict, keys: dict, now: float) -> list[dict]:
    out = []
    for item in followup_links(keys):
        entry = store.tokens.get(keys[item["kind"]])
        if not isinstance(entry, dict):
            used, dead = True, False            # swept after use: never re-minted
        else:
            used = not _unused(entry)
            dead = bool(entry.get("revoked")) or (entry.get("term_ends_at") or 0) < now
        if plan.get("revoked") or dead:
            item["url"] = ""
        out.append({**item, "used": used})
    return out


def next_grant(plan: dict, now: float) -> int | None:
    """When the next monthly batch arrives, or None when none is coming (cancelling, ended, revoked, problem)."""
    if plan_state(plan, now) != "active" and not (plan_state(plan, now) == "cancelling" and plan.get("billing_months", 1) > 1):
        return None
    ps, pe = plan.get("period_start"), plan.get("period_end")
    if not isinstance(pe, int):
        return None
    if isinstance(ps, int):
        for j in range(int(plan.get("billing_months") or 1)):
            due = add_months(ps, j)
            if now < due < pe:
                return due
    return pe if plan_state(plan, now) == "active" else None


def plan_view(store, plan: dict, now: float) -> dict:
    state = plan_state(plan, now)
    grants, total = [], 0
    for g in sorted(plan.get("grants", []), key=lambda x: x.get("start", 0), reverse=True):
        entry = _live_entry(store, plan, g, now)
        expired = (g.get("ends") or 0) < now or not isinstance(store.tokens.get(g.get("key")), dict)
        raw = store.tokens.get(g.get("key"))
        rows = []
        if isinstance(raw, dict):
            used_set = set(raw.get("consumed_tokens") or [])
            for t in raw.get("tokens") or []:
                used = t in used_set
                row = {"short": t[:8], "used": used,
                       "start_url": start_url(t) if (not used and entry is not None) else ""}
                keys = (g.get("fu") or {}).get(t[:8])
                if used and keys:
                    row["followups"] = _followup_view(store, plan, keys, now)
                rows.append(row)
        unused = len(_unused(entry)) if entry is not None else 0
        total += unused
        grants.append({"label": date_label(g["start"]), "valid_until": date_label(g["ends"]), "expired": bool(expired),
                       "count": g.get("count", len(rows)), "unused": unused, "tokens": rows})
    nxt = next_grant(plan, now)
    return {
        "state": state,
        "plan_name": LAB_PRODUCTS.get(plan.get("product"), {}).get("name", "Lab"),
        "tier": plan.get("tier", "lab"),
        "reviews_per_month": plan.get("reviews_per_month", 20),
        "billing": "yearly" if int(plan.get("billing_months") or 1) > 1 else "monthly",
        "date": date_label(plan.get("period_end", 0)),
        "next_grant": date_label(nxt) if nxt else "",
        "unused": 0 if state == "revoked" else total,
        "grants": grants,
        "group_url": group_url(plan) if plan.get("tier") == "lab-plus" else "",
        "customer": plan.get("customer") or "",
    }


def available(store, plan: dict, claims, now: float) -> int:
    """Unused reviews in live batches that a group member could be handed right now."""
    if plan_state(plan, now) not in ("active", "cancelling"):
        return 0
    n = 0
    for g in plan.get("grants", []):
        entry = _live_entry(store, plan, g, now)
        if entry is None:
            continue
        for t in _unused(entry):
            hand = claims.get("labhand:" + t)
            if hand is None or now - float(hand) >= REHAND_AFTER:
                n += 1
    return n


def member_claim(store, plan: dict, now: float) -> str | None:
    """A review token for a Lab Plus group member, or None. Pass one: a never-handed unused token from the oldest
    live batch first (atomic claim `labhand:<token>`). Pass two: re-hand a hand older than 30 minutes (atomic claim
    `labrehand:<token>:<old hand time>`, so two members never get the same stale token)."""
    live = []
    for g in sorted(plan.get("grants", []), key=lambda x: x.get("start", 0)):
        entry = _live_entry(store, plan, g, now)
        if entry is not None:
            live.append(entry)
    for entry in live:
        for t in _unused(entry):
            if store.claims.put("labhand:" + t, now, skip_if_exists=True):
                return t
    for entry in live:
        for t in _unused(entry):
            old = store.claims.get("labhand:" + t)
            if old is None or now - float(old) < REHAND_AFTER:
                continue
            if store.claims.put(f"labrehand:{t}:{old}", now, skip_if_exists=True):
                store.claims["labhand:" + t] = now
                return t
    return None


def rotate_group(store, plan: dict) -> dict:
    """Replace the group link: the old key stops resolving. Lab Plus only (the caller checks the tier)."""
    old = plan.get("group_key")
    if old:
        try:
            del store.plans["labgroup:" + old]
        except Exception:
            pass
    plan["group_key"] = new_group_key()
    store.plans["labgroup:" + plan["group_key"]] = plan["plan_id"]
    store.plans[plan["plan_id"]] = plan
    return plan


# ------------------------------------------------------------------------------------------ Publication Pack

def pack_keys(session_id: str) -> list[str]:
    return [session_id + suffix for suffix, *_ in PACK_PARTS]


def mint_pack(store, *, session_id: str, email: str, amount_paid: int, gen_token, now: float) -> dict:
    """Three single-use entries under one root: a Deep review, a Revision Review and a response letter draft. None
    expire. The root lists its siblings; each carries its component price as amount_paid. The root's product_key stays
    the pack's, so no review-spend row is recorded and the free Revision Review after a Deep review is not earned."""
    out = {}
    for suffix, category, name, cents in PACK_PARTS:
        key = session_id + suffix
        tok = gen_token()
        cfg = ({"category": "paper-review", "tier": "deep", "qty": 1, "bundled_anonymity": True, "bundled_journal": True}
               if category == "paper-review" else {"category": category, "qty": 1})
        entry = {
            "tokens": [tok], "product_key": PUBLICATION_PACK, "product_cfg": cfg, "email": email,
            "amount_paid": cents, "redeemed": False, "consumed_tokens": [], "created_at": now, "expires_at": 0,
        }
        if not suffix:
            entry["pack_siblings"] = pack_keys(session_id)[1:]
            entry["pack_amount_paid"] = amount_paid
        store.tokens[key] = entry
        store.index[tok] = key
        out[key] = {"token": tok, "category": category, "name": name}
    return out


def pack_groups(store, session_id: str, root_entry: dict | None = None) -> list[dict]:
    """The three parts as [{category, name, url, used}] for the success page. A part that is no longer stored counts
    as used. Works when the root's own token is already used."""
    groups = []
    for suffix, category, name, _cents in PACK_PARTS:
        key = session_id + suffix
        entry = root_entry if (not suffix and root_entry is not None) else store.tokens.get(key)
        if not isinstance(entry, dict):
            groups.append({"category": category, "name": name, "url": "", "used": True})
            continue
        toks = entry.get("tokens") or []
        used = not _unused(entry)
        url = ""
        if toks and not entry.get("revoked"):
            url = start_url(toks[0]) if category == "paper-review" else _keyed_url(PACK_START_PATHS[category], key)
        groups.append({"category": category, "name": name, "url": url, "used": used})
    return groups


def pack_has_live_sibling(store, root_entry: dict) -> bool:
    return any(isinstance(store.tokens.get(k), dict) for k in (root_entry.get("pack_siblings") or []))


def _order_keys(session_id: str) -> list[str]:
    return [session_id + s for s in ("", "#revision", "#draft")]


def revoke_order(store, session_id: str, reason: str, now: float, dispute_id: str = "") -> dict:
    """A refund or dispute on a one-time order: mark the entry and its pack siblings revoked. Siblings are addressed by
    their fixed keys, so this still reaches them after the root has been swept."""
    found = 0
    for key in _order_keys(session_id):
        entry = store.tokens.get(key)
        if not isinstance(entry, dict):
            continue
        found += 1
        if reason == "dispute":
            ids = list(entry.get("disputes_open") or [])
            if dispute_id and dispute_id not in ids:
                ids.append(dispute_id)
            entry["disputes_open"] = ids
        else:
            entry["refund_revoked"] = True
        entry["revoked"] = True
        entry["revoked_reason"] = reason
        entry["revoked_at"] = now
        store.tokens[key] = entry
    if not found:
        return {"ok": False, "reason": "unknown_order"}
    return {"ok": True, "reason": "revoked"}


def restore_order(store, session_id: str, dispute_id: str, now: float) -> dict:
    """A won dispute: lift a dispute-only revoke once the last open dispute is closed. Never after a refund."""
    found, restored = 0, False
    for key in _order_keys(session_id):
        entry = store.tokens.get(key)
        if not isinstance(entry, dict):
            continue
        found += 1
        if not entry.get("revoked") or entry.get("refund_revoked") or "disputes_open" not in entry:
            continue
        ids = [d for d in entry.get("disputes_open") or [] if d != dispute_id]
        entry["disputes_open"] = ids
        if not ids:
            entry["revoked"] = False
            entry["restored_at"] = now
            restored = True
        store.tokens[key] = entry
    if not found:
        return {"ok": False, "reason": "unknown_order", "restored": False}
    return {"ok": True, "reason": "restored" if restored else "unchanged", "restored": restored}


# ------------------------------------------------------------------------------------------------------ emails

def _wrap(inner: str) -> str:
    # COPY: neutral footer for lab emails
    return (f'<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.55; color: #1a1a1a; '
            f'max-width: 600px;">{inner}<hr><p style="color: #888; font-size: 0.85em;">Purplelink LLC</p></div>')


def _rows(tokens: list[str]) -> str:
    return "".join(f'<li><a href="{start_url(t)}">{t[:8]}</a></li>' for t in tokens)


def html_grant(*, plan_name: str, tokens: list[str], valid_until: str, link: str, group: str, first: bool) -> str:
    # COPY: lab grant email heading
    head = "Your plan is active" if first else "Your reviews for this month"
    # COPY: lab grant email body
    body = (f"{len(tokens)} reviews are ready on {plan_name}. They can be used until {valid_until}. "
            "Each one comes with a Revision Review and a Response Review for that paper.")
    # COPY: lab grant email plan link label
    plan_line = f'<p><a href="{link}">Open your plan page</a></p>'
    # COPY: lab grant email group line
    grp = f'<p>Group link: <a href="{group}">{group}</a></p>' if group else ""
    return _wrap(f"<h2>{head}</h2><p>{body}</p><ol>{_rows(tokens)}</ol>{plan_line}{grp}")


def html_reminder(*, days: int, end_label: str, unused: int, link: str) -> str:
    # COPY: lab renewal reminder
    return _wrap(f'<h2>Your plan renews in {days} days</h2><p>Renewal date: {end_label}. Reviews unused: {unused}.</p>'
                 f'<p><a href="{link}">Open your plan page</a></p>')


def html_cancel_confirmation(*, end_label: str, link: str, undone: bool) -> str:
    # COPY: lab cancel and undo confirmation
    line = (f"Renewal is back on. Next renewal: {end_label}." if undone
            else f"Renewal is off. The plan runs until {end_label}.")
    return _wrap(f'<h2>{"Renewal on" if undone else "Renewal off"}</h2><p>{line}</p>'
                 f'<p><a href="{link}">Open your plan page</a></p>')


def html_link(*, link: str) -> str:
    # COPY: lab plan link email
    return _wrap(f'<h2>Your plan link</h2><p>This link replaces any earlier one.</p><p><a href="{link}">Open my plan</a></p>')


def html_pack_links(*, groups: list[dict]) -> str:
    # COPY: publication pack email
    items = "".join(f'<li><a href="{g["url"]}">{g["name"]}</a></li>' for g in groups if g.get("url"))
    return _wrap(f"<h2>Your Publication Pack</h2><p>Three links. Each works once and does not expire.</p><ol>{items}</ol>")


# ------------------------------------------------------------------------------------------------ notifications

async def notify(store, res: dict, *, send_email: Callable[..., Awaitable[dict]], secret: str, now: float) -> dict:
    """Send the emails a sync call earned: one per new grant, and a confirmation when renewal was switched off in
    the billing portal. Never raises; returns counts."""
    out = {"grants": 0, "cancel": 0, "errors": 0}
    plan = res.get("plan")
    if not plan or not plan.get("email"):
        return out
    link = plan_link(secret, plan, now)
    name = LAB_PRODUCTS.get(plan.get("product"), {}).get("name", "Lab")
    for m in res.get("minted", []):
        first = m["key"] == plan.get("root")
        try:
            # COPY: lab grant subjects
            subj = "Your plan is active" if first else "Your reviews for this month"
            r = await send_email(to=plan["email"], subject=subj,
                                 html=html_grant(plan_name=name, tokens=m["tokens"], valid_until=date_label(m["grant"]["ends"]),
                                                 link=link, group=group_url(plan), first=first),
                                 tag="lab_grant")
            out["grants" if (r or {}).get("status") == "ok" else "errors"] += 1
        except Exception:
            out["errors"] += 1
    if res.get("cancel_flipped"):
        try:
            # COPY: lab cancel subject
            subj = "Renewal off"
            r = await send_email(to=plan["email"], subject=subj,
                                 html=html_cancel_confirmation(end_label=date_label(plan["period_end"]), link=link, undone=False),
                                 tag="lab_cancel")
            out["cancel" if (r or {}).get("status") == "ok" else "errors"] += 1
        except Exception:
            out["errors"] += 1
    return out


# ------------------------------------------------------------------------------------------------- daily loop

async def run_sweep(store, *, now: float, secret: str, gen_token,
                    fetch_subscription: Callable[[str], Awaitable[dict | None]],
                    send_email: Callable[..., Awaitable[dict]]) -> dict:
    """One daily pass over lab plans only (keys starting "lab_"; never pl_, sub:, reward:, labsub: or labgroup:).
    Re-read each live subscription from Stripe (never send blind), record a portal cancel, issue due grants, and send
    the 30 and 7 day reminder once per period to yearly plans only."""
    out = {"reminded": 0, "minted": 0, "errors": 0, "plans": 0}
    for key, plan in list(store.plans.items()):
        if not str(key).startswith(PLAN_PREFIX) or not isinstance(plan, dict):
            continue
        if plan.get("revoked") or plan.get("ended"):
            continue
        out["plans"] += 1
        try:
            snap = await fetch_subscription(plan["subscription_id"])
        except Exception:
            snap = None
        if not snap:
            out["errors"] += 1
            continue
        try:
            res = sync(store, snap, gen_token=gen_token, now=now)
        except Exception:
            out["errors"] += 1
            continue
        out["minted"] += len(res.get("minted", []))
        await notify(store, res, send_email=send_email, secret=secret, now=now)
        plan = res.get("plan") or plan
        if int(plan.get("billing_months") or 1) < 12 or plan_state(plan, now) != "active":
            continue
        days_left = (plan["period_end"] - now) / 86400
        if days_left <= 0:
            continue
        marks = plan.setdefault("reminders", {}).setdefault(str(plan["period_end"]), {})
        want = 7 if (days_left <= 7 and not marks.get("7")) else (30 if (7 < days_left <= 30 and not marks.get("30")) else None)
        if want is None or not plan.get("email"):
            continue
        days = max(1, round(days_left)) if want == 7 else 30
        unused = sum(len(_unused(e)) for g in plan.get("grants", []) for e in [_live_entry(store, plan, g, now)] if e)
        try:
            # COPY: lab reminder subject
            subj = f"Your plan renews in {days} days"
            r = await send_email(to=plan["email"], subject=subj,
                                 html=html_reminder(days=days, end_label=date_label(plan["period_end"]), unused=unused,
                                                    link=plan_link(secret, plan, now)),
                                 tag="lab_reminder_%d" % want)
        except Exception:
            r = {}
        if (r or {}).get("status") == "ok":
            marks[str(want)] = now
            if want == 7:
                marks.setdefault("30", "skipped")
            store.plans[plan["plan_id"]] = plan
            out["reminded"] += 1
        else:
            out["errors"] += 1
    return out
