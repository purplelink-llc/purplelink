"""Mastodon: official API. Scopes: write:statuses write:media read:accounts. Token in keychain `access_token`."""
from __future__ import annotations

import mimetypes
from urllib.parse import urlsplit

from ..errors import Ambiguous, Disabled, SocialError
from ..http import multipart
from ..items import Item, image_path
from .base import Adapter, Result


class Mastodon(Adapter):
    name = "mastodon"
    identity_keys = {"acct": "acct"}

    @property
    def base(self) -> str:
        inst = (self.cfg.get("instance") or "").rstrip("/")
        if not inst.startswith("https://"):
            raise Disabled("mastodon: `instance` must be an https URL in social.json")
        return inst

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.secret('access_token')}"}

    def whoami(self) -> dict:
        r = self.ok(self.http.request("GET", f"{self.base}/api/v1/accounts/verify_credentials", self._auth()),
                    "verify_credentials")
        j = r.json() or {}
        host = urlsplit(self.base).hostname
        return {"acct": f"{j.get('acct', '')}@{host}".lower() if "@" not in j.get("acct", "") else j["acct"],
                "id": j.get("id"), "bot": j.get("bot")}

    def check_identity(self) -> dict:
        # `expected.acct` may be written as "user" or "user@host"; both mean the account on the configured instance
        exp = dict(self.expected())
        host = urlsplit(self.base).hostname
        a = str(exp.get("acct", "")).lstrip("@")
        if a and "@" not in a:
            a = f"{a}@{host}"
        self.cfg = {**self.cfg, "expected": {**exp, "acct": a}}
        return super().check_identity()

    def post(self, item: Item, dry_run: bool = False) -> Result:
        text = item.render("mastodon")
        images = item.images_for("mastodon")
        if dry_run:
            return Result(dry_run=True, detail=f"{len(text)} chars, {len(images)} images")
        self.check_identity()
        media_ids = [self._upload(item, im) for im in images]
        body = {"status": text, "visibility": "public", "language": "en"}
        if media_ids:
            body["media_ids"] = media_ids
        h = {**self._auth(), "Idempotency-Key": f"{item.id}-mastodon"}
        r = self.ok(self.http.request("POST", f"{self.base}/api/v1/statuses", h, json_body=body), "post status")
        j = r.json() or {}
        if not j.get("id") or not j.get("url"):
            raise Ambiguous("mastodon: the post answered without an id or url; check the account")
        return Result(url=j["url"], id=str(j["id"]))

    def _upload(self, item: Item, im: dict) -> str:
        f = image_path(item, im)
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        data, ct = multipart({"description": str(im["alt"])}, {"file": (f.name, f.read_bytes(), ctype)})
        r = self.http.request("POST", f"{self.base}/api/v2/media", {**self._auth(), "Content-Type": ct}, data=data)
        self.ok(r, "media upload")
        j = r.json() or {}
        mid = j.get("id")
        if not mid:
            raise SocialError("mastodon: media upload answered without an id")
        if r.status == 202 or not j.get("url"):
            for _ in range(30):
                g = self.http.request("GET", f"{self.base}/api/v1/media/{mid}", self._auth())
                if g.status == 200:
                    break
                if g.status != 206:
                    raise SocialError(f"mastodon: media processing answered {g.status}")
                self.sleep(2)
            else:
                raise SocialError("mastodon: media still processing after 60 s")
        return str(mid)

    def verify(self, url: str) -> bool:
        sid = url.rstrip("/").rsplit("/", 1)[-1]
        r = self.http.request("GET", f"{self.base}/api/v1/statuses/{sid}")
        return r.status == 200 and (r.json() or {}).get("id") == sid
