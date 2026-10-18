"""X (Twitter) API v2. Pay-per-use only; disabled unless config has enabled and paid_posting_ok, and the keychain
has an OAuth 2.0 user token (scopes tweet.read tweet.write users.read media.write offline.access)."""
from __future__ import annotations

import mimetypes

from ..errors import Ambiguous, Disabled, SocialError
from ..http import multipart
from ..items import Item, image_path
from .base import Adapter, Result

API = "https://api.x.com"


class X(Adapter):
    name = "x"
    identity_keys = {"user_id": "id", "username": "username"}

    def _guard(self) -> None:
        if not self.cfg.get("paid_posting_ok"):
            raise Disabled("x: posting is pay-per-use; set paid_posting_ok to true in social.json after buying credits")

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.secret('access_token')}"}

    def refresh(self) -> None:
        """Exchange the refresh token for a new pair and store both. X rotates refresh tokens."""
        from .. import sysutil
        form = {"grant_type": "refresh_token", "refresh_token": self.secret("refresh_token"),
                "client_id": self.secret("client_id")}
        headers = {}
        sec = self.secret("client_secret", required=False)
        if sec:
            import base64
            headers["Authorization"] = "Basic " + base64.b64encode(f"{form['client_id']}:{sec}".encode()).decode()
        r = self.ok(self.http.request("POST", f"{API}/2/oauth2/token", headers, form=form), "token refresh")
        j = r.json() or {}
        if not j.get("access_token") or not j.get("refresh_token"):
            raise SocialError("x: refresh answered without new tokens")
        sysutil.keychain_set("x", "access_token", j["access_token"])
        sysutil.keychain_set("x", "refresh_token", j["refresh_token"])

    def _call(self, method: str, url: str, **kw):
        extra = kw.pop("headers", {})
        r = self.http.request(method, url, {**self._auth(), **extra}, **kw)
        if r.status == 401 and self.secret("refresh_token", required=False):
            self.refresh()
            r = self.http.request(method, url, {**self._auth(), **extra}, **kw)
        return r

    def whoami(self) -> dict:
        r = self.ok(self._call("GET", f"{API}/2/users/me"), "users/me")
        d = (r.json() or {}).get("data") or {}
        return {"id": d.get("id"), "username": d.get("username")}

    def post(self, item: Item, dry_run: bool = False) -> Result:
        text = item.render("x")
        images = item.images_for("x")
        if dry_run:
            return Result(dry_run=True, detail=f"{len(text)} chars, {len(images)} images")
        self._guard()
        who = self.check_identity()
        ids = [self._upload(item, im) for im in images]
        body: dict = {"text": text}
        if ids:
            body["media"] = {"media_ids": ids}
        r = self._call("POST", f"{API}/2/tweets", json_body=body)
        if r.status == 0 or r.status >= 500:
            raise Ambiguous(f"x: create post answered {r.status}; the post may be live, check the account")
        self.ok(r, "create post")
        d = (r.json() or {}).get("data") or {}
        if not d.get("id"):
            raise Ambiguous("x: create post answered 2xx without an id; the post may be live, check the account")
        return Result(url=f"https://x.com/{who['username']}/status/{d['id']}", id=str(d["id"]))

    def _upload(self, item: Item, im: dict) -> str:
        f = image_path(item, im)
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        data, ct = multipart({"media_category": "tweet_image", "media_type": ctype},
                             {"media": (f.name, f.read_bytes(), ctype)})
        r = self.ok(self._call("POST", f"{API}/2/media/upload", headers={"Content-Type": ct}, data=data),
                    "media upload")
        j = r.json() or {}
        mid = (j.get("data") or {}).get("id") or j.get("id")
        if not mid:
            raise SocialError("x: media upload answered without an id")
        meta = {"id": str(mid), "metadata": {"alt_text": {"text": str(im["alt"])}}}
        self.ok(self._call("POST", f"{API}/2/media/metadata", json_body=meta), "alt text")
        return str(mid)

    def verify(self, url: str) -> bool:
        tid = url.rstrip("/").rsplit("/", 1)[-1]
        r = self._call("GET", f"{API}/2/tweets/{tid}")
        return r.status == 200 and ((r.json() or {}).get("data") or {}).get("id") == tid
