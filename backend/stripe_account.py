"""Two Stripe accounts during the move off the Buy Me a Coffee-controlled account.

Python twin of netlify/lib/stripe-account.mjs (design: docs/products/stripe-migration-2026-11.md).

The old account keeps every past buyer, so STRIPE_SECRET_KEY stays set. The new, directly controlled account is added
beside it through two env vars, both unset by default:

    STRIPE_SECRET_KEY_NEW   sk_... of the new account
    STRIPE_NEW_ACCOUNT      on / 1 / true / all / yes: new Checkout Sessions and promo codes go to the new account
                            (only effective while STRIPE_SECRET_KEY_NEW is also set)

With both unset every helper returns exactly what the code did before: the old key alone.
Reading an object through the wrong account's key is a 404 from Stripe (or 401/403 for a rejected key), which is how
lookups fall through. LIST calls answer 200 with empty rows under the wrong account, so callers iterate lookup_keys()
and merge instead of falling through.

Modal images must copy this file: `.add_local_python_source("stripe_account")`.
"""
from __future__ import annotations

import os

OLD_KEY_ENV = "STRIPE_SECRET_KEY"
NEW_KEY_ENV = "STRIPE_SECRET_KEY_NEW"
FLAG_ENV = "STRIPE_NEW_ACCOUNT"

_ON = {"on", "1", "true", "all", "yes"}
_FALL_THROUGH = (401, 403, 404)


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def new_account_active() -> bool:
    """True when new Checkout Sessions/promos go to the new account: the flag is on and the new key is present."""
    return _env(FLAG_ENV).lower() in _ON and bool(_env(NEW_KEY_ENV))


def checkout_secret_key() -> str:
    """The key of the account checkout runs on. The old key (possibly empty) unless the new account is active."""
    return _env(NEW_KEY_ENV) if new_account_active() else _env(OLD_KEY_ENV)


def lookup_keys() -> list[str]:
    """Every key that may know a given object, newest account first. Just the old key while no new key is set."""
    keys: list[str] = []
    for k in (_env(NEW_KEY_ENV), _env(OLD_KEY_ENV)):
        if k and k not in keys:
            keys.append(k)
    return keys


async def fetch_any(client, method: str, url: str, **kwargs):
    """GET/POST a Stripe URL with each account's key until one answers 2xx.

    `client` is an httpx.AsyncClient; kwargs (params, data, headers, timeout) pass through and the Authorization
    header is set per key. A 401/403/404 falls through to the next key; any other status is returned at once. Returns
    (response, key): the first ok response with its key, else the last response with None. Raises the last network
    error only when every attempt raised, and RuntimeError when no key is set.
    """
    keys = lookup_keys()
    if not keys:
        raise RuntimeError("no Stripe key is set")
    call = client.get if method.upper() == "GET" else client.post
    last = None
    last_err = None
    for key in keys:
        headers = {**(kwargs.get("headers") or {}), "Authorization": f"Bearer {key}"}
        try:
            resp = await call(url, **{**kwargs, "headers": headers})
        except Exception as err:  # noqa: BLE001 - try the next key, re-raise below if all fail
            last_err = err
            continue
        if 200 <= resp.status_code < 300:
            return resp, key
        last = resp
        if resp.status_code not in _FALL_THROUGH:
            return resp, None
    if last is not None:
        return last, None
    raise last_err


def fetch_any_sync(client, method: str, url: str, **kwargs):
    """Synchronous twin of fetch_any for httpx.Client callers."""
    keys = lookup_keys()
    if not keys:
        raise RuntimeError("no Stripe key is set")
    call = client.get if method.upper() == "GET" else client.post
    last = None
    last_err = None
    for key in keys:
        headers = {**(kwargs.get("headers") or {}), "Authorization": f"Bearer {key}"}
        try:
            resp = call(url, **{**kwargs, "headers": headers})
        except Exception as err:  # noqa: BLE001
            last_err = err
            continue
        if 200 <= resp.status_code < 300:
            return resp, key
        last = resp
        if resp.status_code not in _FALL_THROUGH:
            return resp, None
    if last is not None:
        return last, None
    raise last_err
