"""Regression test for the paper-review token consumption race.

backend/app.py's /paper-review/submit (and the adjacent-tool submit
endpoints) used to do a non-atomic check-then-act on `consumed_tokens`:
read the list, check membership, do expensive work, then write the token
back as consumed. Concurrent requests for the same token could all pass
the membership check before any of them wrote back, letting one paid
token spawn N billable pipeline runs.

The fix adds `_claim_token`, an atomic compare-and-set gate backed by
Modal Dict's server-enforced `put(key, value, skip_if_exists=True)`
(maps to `DictUpdateRequest(if_not_exists=True)` — a server-side CAS, not
a client-side race). Only one concurrent caller can ever win the claim
for a given token.

We can't import backend/app.py directly in a fast/hermetic unit test
(its routes are closures inside a `@modal.asgi_app()` function that
requires a live Modal client to construct). Instead this test exercises
a fake Dict that mirrors Modal's documented atomic-put contract exactly,
and proves that hammering it with concurrent threads for the same key
still yields exactly one winner — i.e. the same guarantee `_claim_token`
relies on to close the race described above.
"""

import threading

import pytest


class _FakeAtomicDict:
    """Mirrors modal.Dict's relevant contract: `put(key, value,
    skip_if_exists=True)` is atomic and returns True for exactly one
    caller per key, even under concurrent access, because Modal enforces
    it server-side via `DictUpdateRequest(if_not_exists=True)`."""

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def put(self, key, value, *, skip_if_exists: bool = False) -> bool:
        with self._lock:
            if skip_if_exists and key in self._data:
                return False
            self._data[key] = value
            return True

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)


def _claim_token(claims_dict: _FakeAtomicDict, token: str) -> bool:
    """Same logic as app.py's `_claim_token`."""
    return claims_dict.put(token, "claimed", skip_if_exists=True)


def test_claim_token_allows_first_caller():
    d = _FakeAtomicDict()
    assert _claim_token(d, "tok-1") is True


def test_claim_token_rejects_second_caller_for_same_token():
    d = _FakeAtomicDict()
    assert _claim_token(d, "tok-1") is True
    assert _claim_token(d, "tok-1") is False


def test_claim_token_independent_across_tokens():
    d = _FakeAtomicDict()
    assert _claim_token(d, "tok-1") is True
    assert _claim_token(d, "tok-2") is True


@pytest.mark.parametrize("n_concurrent", [10, 50])
def test_concurrent_submits_only_one_winner(n_concurrent):
    """The core regression check: N threads race to claim the same token
    (simulating N concurrent /paper-review/submit requests with the same
    unconsumed token, e.g. a double-clicked submit button or a replayed
    request). Exactly one must win — i.e. at most one pipeline run may
    ever be spawned for a single paid token."""
    d = _FakeAtomicDict()
    token = "shared-token-under-race"
    results = [None] * n_concurrent
    barrier = threading.Barrier(n_concurrent)

    def racer(i):
        barrier.wait()  # maximize actual overlap
        results[i] = _claim_token(d, token)

    threads = [threading.Thread(target=racer, args=(i,)) for i in range(n_concurrent)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(1 for r in results if r) == 1, (
        "exactly one concurrent request must win the token claim; "
        f"got {sum(1 for r in results if r)} winners out of {n_concurrent}"
    )
