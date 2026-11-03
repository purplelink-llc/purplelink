"""DurableDict keeps records that modal.Dict's 7-day inactivity expiry would
drop: an unsubscribe, an unused volume pack, a referral code."""

from conftest import MemVolume
from latextools.durable_dict import DurableDict


def _evict(cache, key):
    # What Modal does to an entry left unread and unwritten for 7 days.
    del cache[key]


def test_optout_survives_dict_eviction():
    cache, vol = {}, MemVolume()
    optout = DurableDict(cache, vol, "lifecycle-optout")
    optout["gone@example.com"] = True
    _evict(cache, "gone@example.com")

    assert optout.get("gone@example.com") is True
    assert cache["gone@example.com"] is True  # put back in the Dict
    assert optout.get("never@example.com") is None
    assert "gone@example.com" in optout
    assert vol.files and all("gone@example.com" not in p for p in vol.files)  # filenames are hashed


def test_only_packs_get_a_durable_copy_and_delete_removes_it():
    def is_pack(v):
        return isinstance(v, dict) and not v.get("expires_at")

    cache, vol = {}, MemVolume()
    tokens = DurableDict(cache, vol, "paper-tokens", keep=is_pack)
    tokens["cs_single"] = {"tokens": ["a"], "expires_at": 123.0}
    tokens["cs_pack"] = {"tokens": ["p1", "p2"], "consumed_tokens": ["p1"], "expires_at": 0}
    assert len(vol.files) == 1

    _evict(cache, "cs_pack")
    assert dict(tokens.items())["cs_pack"]["consumed_tokens"] == ["p1"]

    del tokens["cs_pack"]
    assert not vol.files
    assert tokens.get("cs_pack") is None


def test_backfill_copies_records_written_before_the_volume():
    cache, vol = {"old@example.com": True}, MemVolume()
    optout = DurableDict(cache, vol, "lifecycle-optout")
    assert optout.backfill() == 1
    assert optout.backfill() == 0
    _evict(cache, "old@example.com")
    assert optout.get("old@example.com") is True


def test_app_stores_are_durable():
    import app as backend_app

    for name in ("paper_tokens_dict", "lifecycle_optout_dict", "referral_dict",
                 "customer_lifecycle_dict", "feedback_dict"):
        assert isinstance(getattr(backend_app, name), DurableDict), name
    assert backend_app._is_volume_pack({"expires_at": 0})
    assert not backend_app._is_volume_pack({"expires_at": 1.0})


def test_items_reads_only_records_the_dict_lost():
    cache, vol = {}, MemVolume()
    ledger = DurableDict(cache, vol, "usage-ledger")
    ledger["job_a"] = {"cost_usd": 0.4}
    ledger["job_b"] = {"cost_usd": 0.7}
    _evict(cache, "job_b")

    reads = []
    real_read = vol.read_file
    vol.read_file = lambda path: (reads.append(path), real_read(path))[1]
    assert dict(ledger.items()) == {"job_a": {"cost_usd": 0.4}, "job_b": {"cost_usd": 0.7}}
    assert len(reads) == 1  # job_a came from the Dict, only job_b from the Volume


def test_put_if_absent_respects_an_evicted_claim_and_pop_clears_it():
    cache, vol = {"spend:day": 1.5}, MemVolume()

    class _Cache(dict):
        def put(self, k, v, *, skip_if_exists=False):
            if skip_if_exists and k in self:
                return False
            self[k] = v
            return True

    cache = _Cache(cache)
    claims = DurableDict(cache, vol, "buddy-claims", key_prefix="claim:")
    assert claims.put("claim:x", {"state": "sent"}, skip_if_exists=True)
    assert not claims.put("claim:x", {"state": "sent"}, skip_if_exists=True)
    _evict(cache, "claim:x")
    assert not claims.put("claim:x", {"state": "sent"}, skip_if_exists=True)

    assert dict(claims.items()) == {"claim:x": {"state": "sent"}}   # other keys are not this store's
    claims["spend:day"] = 2.0
    assert len(vol.files) == 1                                       # and get no durable copy

    assert claims.pop("claim:x", None) == {"state": "sent"}
    assert not vol.files
    assert claims.put("claim:x", {"state": "sent"}, skip_if_exists=True)
