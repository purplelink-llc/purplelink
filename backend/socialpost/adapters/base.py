"""Shared adapter interface.

    whoami()            -> dict of the authenticated account's identity (read only, never posts)
    check_identity()    -> raises Refused unless it equals the `expected` block in social.json
    validate(item)      -> list of problems specific to this platform
    post(item, dry_run) -> Result(url, id); dry_run builds everything and sends nothing
    verify(url)         -> True when the post is publicly live

Identity is checked inside post() before anything is created. A platform whose `expected` block is empty is refused,
never assumed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ..errors import Disabled, Refused, SocialError
from ..items import Item
from .. import sysutil


@dataclass
class Result:
    url: str | None = None
    id: str | None = None
    dry_run: bool = False
    detail: str = ""


class Adapter:
    name = ""
    # identity keys compared with `expected` (config key -> key in whoami()'s dict)
    identity_keys: dict[str, str] = {}

    def __init__(self, cfg: dict, http=None, secret=None, sleep=time.sleep):
        """cfg is this platform's block of social.json plus the whole config under cfg['_root']."""
        from ..http import Http
        self.cfg = cfg
        self.http = http or Http()
        self._secret = secret or sysutil.keychain_get
        self.sleep = sleep

    # -- secrets
    def secret(self, field: str, required: bool = True) -> str | None:
        v = self._secret(self.name, field)
        if not v and required:
            raise Disabled(f"{self.name}: no `{field}` in the keychain (service purplelink-social-{self.name}); "
                           f"run: social.py setup {self.name}")
        return v

    # -- identity
    def whoami(self) -> dict:
        raise NotImplementedError

    def expected(self) -> dict:
        return self.cfg.get("expected") or {}

    def check_identity(self) -> dict:
        exp = self.expected()
        missing = [k for k in self.identity_keys if not str(exp.get(k, "")).strip()]
        if missing:
            raise Refused(f"{self.name}: config has no expected {', '.join(missing)}; refusing to post to an "
                          f"account nobody named")
        got = self.whoami()
        for key, got_key in self.identity_keys.items():
            if str(got.get(got_key, "")).strip().lower() != str(exp[key]).strip().lower():
                raise Refused(f"{self.name}: signed in as {got.get(got_key)!r}, expected {exp[key]!r} ({key})")
        return got

    # -- posting
    def validate(self, item: Item) -> list[str]:
        return []

    def post(self, item: Item, dry_run: bool = False) -> Result:
        raise NotImplementedError

    def verify(self, url: str) -> bool:
        raise NotImplementedError

    # -- helpers
    def ok(self, resp, what: str):
        if resp.status in (401, 403):
            raise SocialError(f"{self.name}: {what} answered {resp.status} (token expired or permission missing)")
        if resp.status == 429:
            raise SocialError(f"{self.name}: {what} rate limited (429)")
        if resp.status >= 400 or resp.status == 0:
            raise SocialError(f"{self.name}: {what} answered {resp.status}")
        return resp
