"""Threads: official API (graph.threads.net). Permissions threads_basic + threads_content_publish.

Flow: create a container (TEXT or IMAGE; a carousel is child containers then a CAROUSEL container), wait until it is
FINISHED, publish, then read the permalink. Images must be public URLs: see media.py. The long-lived token
(60 days) is in the keychain as `access_token`; `social.py refresh threads` renews it. Credentials travel in the
Authorization header or a POST body, never in a URL.
"""
from __future__ import annotations

from .. import media, sysutil
from ..errors import Ambiguous, SocialError
from ..items import Item, image_path
from .base import Adapter, Result

API = "https://graph.threads.net/v1.0"


class Threads(Adapter):
    name = "threads"
    identity_keys = {"user_id": "id", "username": "username"}

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.secret('access_token')}"}

    def whoami(self) -> dict:
        r = self.ok(self.http.request("GET", f"{API}/me?fields=id,username", self._auth()), "me")
        j = r.json() or {}
        return {"id": j.get("id"), "username": j.get("username")}

    def refresh(self) -> None:
        """Renew the long-lived token (allowed once it is 24 hours old and before it expires)."""
        tok = self.secret("access_token")
        url = "https://graph.threads.net/refresh_access_token"
        r = self.http.request("POST", url, form={"grant_type": "th_refresh_token", "access_token": tok})
        if r.status >= 400:
            r = self.http.request("GET", f"{url}?grant_type=th_refresh_token", self._auth())
        self.ok(r, "token refresh")
        new = (r.json() or {}).get("access_token")
        if not new:
            raise SocialError("threads: refresh answered without a token")
        sysutil.keychain_set("threads", "access_token", new)

    def _create(self, uid: str, params: dict) -> str:
        r = self.ok(self.http.request("POST", f"{API}/{uid}/threads", self._auth(), form=params), "create container")
        cid = (r.json() or {}).get("id")
        if not cid:
            raise SocialError("threads: container answered without an id")
        return str(cid)

    def _wait(self, cid: str) -> None:
        for _ in range(24):
            r = self.ok(self.http.request("GET", f"{API}/{cid}?fields=status,error_message", self._auth()), "container status")
            st = (r.json() or {}).get("status")
            if st in ("FINISHED", "PUBLISHED"):
                return
            if st in ("ERROR", "EXPIRED"):
                raise SocialError(f"threads: container {st}: {(r.json() or {}).get('error_message', '')[:200]}")
            self.sleep(5)
        raise SocialError("threads: container not ready after 2 minutes")

    def post(self, item: Item, dry_run: bool = False) -> Result:
        text = item.render("threads")
        images = item.images_for("threads")
        if dry_run:
            return Result(dry_run=True, detail=f"{len(text)} chars, {len(images)} images")
        who = self.check_identity()
        uid = who["id"]
        cfg = self.cfg["_root"]
        urls = [media.ensure_hosted(cfg, image_path(item, im), self.http) for im in images]
        if not images:
            cid = self._create(uid, {"media_type": "TEXT", "text": text})
        elif len(images) == 1:
            cid = self._create(uid, {"media_type": "IMAGE", "image_url": urls[0], "text": text,
                                     "alt_text": str(images[0]["alt"])})
        else:
            kids = []
            for u, im in zip(urls, images):
                kid = self._create(uid, {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true",
                                         "alt_text": str(im["alt"])})
                self._wait(kid)
                kids.append(kid)
            cid = self._create(uid, {"media_type": "CAROUSEL", "children": ",".join(kids), "text": text})
        self._wait(cid)
        self.check_identity()  # again, right before it becomes public
        r = self.http.request("POST", f"{API}/{uid}/threads_publish", self._auth(), form={"creation_id": cid})
        if r.status == 0 or r.status >= 500:
            raise Ambiguous(f"threads: publish answered {r.status}; the post may be live, check the account")
        self.ok(r, "publish")
        mid = (r.json() or {}).get("id")
        if not mid:
            raise Ambiguous("threads: publish answered 2xx without an id; the post may be live, check the account")
        # From here the post is public. Nothing below may raise: a retry would post it twice.
        link = None
        try:
            p = self.http.request("GET", f"{API}/{mid}?fields=permalink", self._auth())
            link = (p.json() or {}).get("permalink") if p.status == 200 else None
        except Exception:
            pass
        return Result(url=link or f"https://www.threads.com/@{who['username']}", id=str(mid),
                      detail="" if link else "permalink unavailable; url is the profile")

    def verify(self, url: str) -> bool:
        r = self.http.request("GET", url)
        return r.status == 200
