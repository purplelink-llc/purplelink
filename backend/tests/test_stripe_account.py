"""Two-account Stripe switch (stripe_account.py) and the app.py call sites that use it."""
import asyncio

import pytest

import stripe_account as sa

OLD, NEW = "sk_test_old", "sk_test_new"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (sa.OLD_KEY_ENV, sa.NEW_KEY_ENV, sa.FLAG_ENV):
        monkeypatch.delenv(name, raising=False)


class Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = str(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeClient:
    """Records (method, url, bearer-or-basic key, kwargs); answers by key from `by_key`."""

    def __init__(self, by_key):
        self.by_key = by_key
        self.calls = []

    async def _do(self, method, url, **kw):
        key = (kw.get("headers") or {}).get("Authorization", "").removeprefix("Bearer ") or (kw.get("auth") or ("",))[0]
        self.calls.append((method, url, key, kw))
        return self.by_key[key]

    async def get(self, url, **kw):
        return await self._do("GET", url, **kw)

    async def post(self, url, **kw):
        return await self._do("POST", url, **kw)


def run(coro):
    return asyncio.run(coro)


def test_unset_new_vars_means_old_key_only(monkeypatch):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    assert not sa.new_account_active()
    assert sa.checkout_secret_key() == OLD
    assert sa.lookup_keys() == [OLD]


def test_flag_without_new_key_is_inactive(monkeypatch):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.FLAG_ENV, "on")
    assert not sa.new_account_active()
    assert sa.checkout_secret_key() == OLD


def test_new_key_without_flag_keeps_old_for_checkout_but_looks_up_both(monkeypatch):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    assert sa.checkout_secret_key() == OLD
    assert sa.lookup_keys() == [NEW, OLD]


@pytest.mark.parametrize("flag", ["on", "1", "true", "ALL", "yes"])
def test_flag_on_uses_new_key_for_checkout(monkeypatch, flag):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    monkeypatch.setenv(sa.FLAG_ENV, flag)
    assert sa.new_account_active()
    assert sa.checkout_secret_key() == NEW


def test_lookup_keys_dedupes_and_drops_empty(monkeypatch):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, OLD)
    assert sa.lookup_keys() == [OLD]
    monkeypatch.delenv(sa.OLD_KEY_ENV)
    monkeypatch.setenv(sa.NEW_KEY_ENV, "  ")
    assert sa.lookup_keys() == []


def test_fetch_any_old_only_makes_one_identical_request(monkeypatch):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    c = FakeClient({OLD: Resp(200, {"id": "cs_1"})})
    resp, key = run(sa.fetch_any(c, "GET", "https://api.stripe.com/v1/checkout/sessions/cs_1", params={"a": "b"}))
    assert key == OLD and resp.json() == {"id": "cs_1"}
    assert [(m, u, k, kw["params"]) for m, u, k, kw in c.calls] == [
        ("GET", "https://api.stripe.com/v1/checkout/sessions/cs_1", OLD, {"a": "b"})]


def test_fetch_any_falls_through_404_to_other_key(monkeypatch):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    c = FakeClient({NEW: Resp(404), OLD: Resp(200, {"id": "sub_1"})})
    resp, key = run(sa.fetch_any(c, "POST", "https://api.stripe.com/v1/subscriptions/sub_1", data={"x": "1"}))
    assert key == OLD and resp.status_code == 200
    assert [k for _, _, k, _ in c.calls] == [NEW, OLD]
    assert all(kw["data"] == {"x": "1"} for *_, kw in c.calls)


@pytest.mark.parametrize("status", [401, 403])
def test_fetch_any_falls_through_rejected_key(monkeypatch, status):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    c = FakeClient({NEW: Resp(status), OLD: Resp(200)})
    assert run(sa.fetch_any(c, "GET", "u"))[1] == OLD


def test_fetch_any_does_not_fall_through_server_errors(monkeypatch):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    c = FakeClient({NEW: Resp(500), OLD: Resp(200)})
    resp, key = run(sa.fetch_any(c, "GET", "u"))
    assert resp.status_code == 500 and key is None and len(c.calls) == 1


def test_fetch_any_all_404_returns_last_response(monkeypatch):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    c = FakeClient({NEW: Resp(404), OLD: Resp(404)})
    resp, key = run(sa.fetch_any(c, "GET", "u"))
    assert resp.status_code == 404 and key is None and len(c.calls) == 2


def test_fetch_any_without_any_key_raises():
    with pytest.raises(RuntimeError):
        run(sa.fetch_any(FakeClient({}), "GET", "u"))


# ---- app.py call sites ------------------------------------------------------

@pytest.fixture
def backend_app():
    import app
    return app


def test_mint_referral_code_old_key_by_default(monkeypatch, backend_app):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    c = FakeClient({OLD: Resp(200, {"code": "REFER-X"})})
    assert run(backend_app._mint_referral_promo_code(c, "a@b.edu")) == "REFER-X"
    assert [(m, k) for m, _, k, _ in c.calls] == [("POST", OLD)]
    assert c.calls[0][1] == "https://api.stripe.com/v1/promotion_codes"
    assert c.calls[0][3]["data"]["promotion[coupon]"] == "purplelink-referral-2usd"


def test_mint_referral_code_new_key_when_flag_on(monkeypatch, backend_app):
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    monkeypatch.setenv(sa.FLAG_ENV, "on")
    c = FakeClient({NEW: Resp(200, {"code": "REFER-Y"}), OLD: Resp(500)})
    assert run(backend_app._mint_referral_promo_code(c, "a@b.edu")) == "REFER-Y"
    assert [k for _, _, k, _ in c.calls] == [NEW]


def test_referral_fetch_charge_falls_through_to_old_account(monkeypatch, backend_app):
    import httpx
    from latextools import referrals
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    monkeypatch.setattr(referrals, "charge_state", lambda body: {"seen": body["id"]})
    client = FakeClient({NEW: Resp(404), OLD: Resp(200, {"id": "cs_old"})})

    class Ctx:
        async def __aenter__(self):
            return client

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: Ctx())
    assert run(backend_app._referral_fetch_charge("cs_old")) == {"seen": "cs_old"}
    assert [k for _, _, k, _ in client.calls] == [NEW, OLD]


def test_annual_fetch_subscription_unset_new_is_old_only(monkeypatch, backend_app):
    import httpx
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setattr(backend_app.annual, "snapshot_from_stripe", lambda body: body)
    client = FakeClient({OLD: Resp(200, {"id": "sub_1"})})

    class Ctx:
        async def __aenter__(self):
            return client

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: Ctx())
    assert run(backend_app._annual_fetch_subscription("sub_1")) == {"id": "sub_1"}
    assert [(m, k, kw["params"]) for m, _, k, kw in client.calls] == [("GET", OLD, {"expand[]": "latest_invoice"})]


def test_annual_calls_return_empty_when_no_key(backend_app):
    assert run(backend_app._annual_fetch_subscription("sub_1")) is None
    assert run(backend_app._annual_set_cancel("sub_1", True)) is False


def test_backfill_lists_every_account_and_merges(monkeypatch, backend_app):
    import httpx
    monkeypatch.setenv(sa.OLD_KEY_ENV, OLD)
    monkeypatch.setenv(sa.NEW_KEY_ENV, NEW)
    pages = {
        NEW: {"data": [], "has_more": False},   # wrong/empty account still answers 200
        OLD: {"data": [{"id": "cs_1", "payment_status": "paid", "amount_total": 500, "created": 1,
                        "customer_details": {"email": "a@b.com"}}], "has_more": False},
    }
    seen = []

    class C:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None, headers=None):
            key = headers["Authorization"].removeprefix("Bearer ")
            seen.append(key)
            return Resp(200, pages[key])

    ledger = {}
    recorded = []
    from latextools import referrals
    monkeypatch.setattr(httpx, "Client", C)
    monkeypatch.setattr(referrals, "record_purchase", lambda d, canon, sid, ts: recorded.append((canon, sid)))
    monkeypatch.setattr(backend_app, "buyer_ledger_dict", ledger)
    out = backend_app.backfill_buyer_ledger.local()
    assert seen == [NEW, OLD]
    assert recorded == [("a@b.com", "cs_1")]
    assert out["sessions"] == 1 and out["pages"] == 2
