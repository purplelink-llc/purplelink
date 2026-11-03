"""A modal.Dict front with a durable copy on a modal.Volume.

Modal's Dict reference: "An individual Dict entry will expire after 7 days of
inactivity (no reads or writes)." Every Dict this backend uses was created
after the 2025-05-20 cutoff, so that rule applies to all of them. Some records
must outlive it: a lifecycle unsubscribe lasts forever (CAN-SPAM), a volume
pack's tokens are sold as never expiring, a referral code must keep crediting
its owner, a lifecycle entry must remember which emails were already sent, the
cost ledger and customer feedback are kept for good, and a Buddy free-check
claim is "one per inbox" for good.

DurableDict keeps the Dict as a fast cache and writes each kept record to the
Volume as one small JSON file. A read that misses the Dict falls back to the
Volume and puts the record back in the Dict, so an evicted record comes back on
its next use. Only the plain dict interface the app uses is offered: get,
[] get/set/delete, `in`, items, keys, pop, and the atomic
put(..., skip_if_exists=True) claim.
"""

import hashlib
import io
import json
import logging

logger = logging.getLogger(__name__)

_MISSING = object()


def _keep_all(_value) -> bool:
    return True


def _is_not_found(exc: Exception) -> bool:
    # Volume.read_file raises FileNotFoundError, listdir NotFoundError, and
    # remove_file InvalidError("No such file or directory.") (modal 1.x).
    if isinstance(exc, FileNotFoundError) or type(exc).__name__ == "NotFoundError":
        return True
    return type(exc).__name__ == "InvalidError" and "no such file" in str(exc).lower()


class DurableDict:
    def __init__(self, cache, volume, prefix: str, keep=_keep_all, key_prefix: str = ""):
        """`cache` is the modal.Dict, `volume` the modal.Volume, `prefix` the
        folder for this store's files, and `keep(value)` says whether a value
        needs the durable copy (e.g. only packs among paper tokens). With
        `key_prefix`, only keys starting with it are this store's (e.g. the
        `claim:` keys of a Dict that also holds short-lived keys)."""
        self._cache = cache
        self._volume = volume
        self._prefix = prefix.strip("/")
        self._keep = keep
        self._key_prefix = key_prefix

    def _ours(self, key) -> bool:
        return str(key).startswith(self._key_prefix)

    def _kept(self, key, value) -> bool:
        return self._ours(key) and self._keep(value)

    def _path(self, key) -> str:
        digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        return f"{self._prefix}/{digest}.json"

    def _read(self, path: str):
        try:
            raw = b"".join(self._volume.read_file(path))
        except Exception as exc:
            if not _is_not_found(exc):
                logger.exception("durable read failed for %s", path)
            return _MISSING
        try:
            return json.loads(raw)
        except ValueError:
            logger.error("durable record %s is not JSON", path)
            return _MISSING

    def _load(self, key):
        record = self._read(self._path(key))
        if record is _MISSING or record.get("key") != key:
            return _MISSING
        return record["value"]

    def _save(self, key, value) -> None:
        try:
            data = json.dumps({"key": key, "value": value}).encode("utf-8")
            with self._volume.batch_upload(force=True) as batch:
                batch.put_file(io.BytesIO(data), self._path(key))
        except Exception:
            logger.exception("durable write failed for %s/%s", self._prefix, str(key)[:12])

    def _drop(self, key) -> bool:
        try:
            self._volume.remove_file(self._path(key))
            return True
        except Exception as exc:
            if not _is_not_found(exc):
                logger.exception("durable delete failed for %s/%s", self._prefix, str(key)[:12])
            return False

    def get(self, key, default=None):
        value = self._cache.get(key, _MISSING)
        if value is not _MISSING or not self._ours(key):
            return default if value is _MISSING else value
        value = self._load(key)
        if value is _MISSING:
            return default
        try:
            self._cache[key] = value
        except Exception:
            logger.exception("re-caching durable record failed for %s/%s", self._prefix, str(key)[:12])
        return value

    def __getitem__(self, key):
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def __contains__(self, key) -> bool:
        return self.get(key, _MISSING) is not _MISSING

    def __setitem__(self, key, value) -> None:
        self._cache[key] = value
        # A value that needs no copy never had one (a key keeps its kind: a
        # pack stays a pack), so there is nothing to remove for it.
        if self._kept(key, value):
            self._save(key, value)

    def put(self, key, value, *, skip_if_exists: bool = False) -> bool:
        """modal.Dict.put. With skip_if_exists the Dict's atomic put-if-absent
        still decides between two racing callers; a durable copy left by an
        evicted entry counts as existing, so an old claim stays claimed."""
        if skip_if_exists:
            if self._ours(key) and self._load(key) is not _MISSING:
                return False
            if not self._cache.put(key, value, skip_if_exists=True):
                return False
        else:
            self._cache.put(key, value)
        if self._kept(key, value):
            self._save(key, value)
        return True

    def pop(self, key, default=_MISSING):
        durable = self._load(key) if self._ours(key) else _MISSING
        if durable is not _MISSING:
            self._drop(key)
        value = self._cache.pop(key, _MISSING)
        if value is _MISSING:
            value = durable
        if value is _MISSING:
            if default is _MISSING:
                raise KeyError(key)
            return default
        return value

    def __delitem__(self, key) -> None:
        removed = self._drop(key) if self._ours(key) else False
        try:
            del self._cache[key]
            removed = True
        except KeyError:
            pass
        if not removed:
            raise KeyError(key)

    def items(self) -> list:
        """Dict entries plus durable records the Dict has lost."""
        out = [(k, v) for k, v in self._cache.items() if self._ours(k)]
        seen = {k for k, _ in out}
        cached_paths = {self._path(k) for k in seen}
        try:
            entries = self._volume.listdir(self._prefix)
        except Exception as exc:
            if not _is_not_found(exc):
                logger.exception("durable listing failed for %s", self._prefix)
            entries = []
        for entry in entries:
            if entry.path in cached_paths:
                continue  # the Dict already gave this record; skip the read
            record = self._read(entry.path)
            if record is _MISSING or record.get("key") in seen:
                continue
            out.append((record["key"], record["value"]))
            seen.add(record["key"])
        return out

    def keys(self) -> list:
        return [k for k, _ in self.items()]

    def backfill(self) -> int:
        """Copy kept Dict entries that have no durable file yet: records
        written before this class existed, or whose durable write failed.
        Returns how many were copied."""
        try:
            present = {entry.path for entry in self._volume.listdir(self._prefix)}
        except Exception as exc:
            if not _is_not_found(exc):
                logger.exception("durable listing failed for %s", self._prefix)
                return 0
            present = set()
        copied = 0
        for key, value in list(self._cache.items()):
            if self._kept(key, value) and self._path(key) not in present:
                self._save(key, value)
                copied += 1
        return copied
