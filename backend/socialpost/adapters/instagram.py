"""Instagram: official API with Instagram Login (graph.instagram.com). Permissions instagram_business_basic +
instagram_business_content_publish. The account is the Purplelink business account @purplelink.llc; RubbleFront's
account (same Meta account) is refused by name before anything else, whatever the config says.

Flow: create a media container (an IMAGE from a public JPEG URL with alt_text, or a REELS container from a public MP4
URL), poll its status_code until FINISHED, publish with media_publish, then read the permalink. Images are served by
the social-media function (media.ensure_hosted); Reels go to the public video bucket for the few minutes Meta needs to
fetch them and are deleted after (media.host_video / delete_video). The long-lived token (60 days) is in the keychain
as `access_token`; run-due refreshes it at 30 days. Credentials travel in the Authorization header, never in a URL.
"""
from __future__ import annotations

import time

from .. import media, sysutil
from ..errors import Ambiguous, Refused, SocialError
from ..items import Item, _resolve, image_path
from .base import Adapter, Result

API = "https://graph.instagram.com"
# Accounts that must never receive Purplelink posts, checked before the pinned identity.
NEVER = ("rubblefront",)


class Instagram(Adapter):
    name = "instagram"
    identity_keys = {"user_id": "user_id", "username": "username"}

    def __init__(self, cfg: dict, http=None, secret=None, sleep=time.sleep, video_client=None):
        super().__init__(cfg, http, secret, sleep)
        self.video_client = video_client  # tests inject a fake S3 client factory

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.secret('access_token')}"}

    def whoami(self) -> dict:
        r = self.ok(self.http.request("GET", f"{API}/me?fields=user_id,username,account_type", self._auth()), "me")
        j = r.json() or {}
        return {"user_id": str(j.get("user_id") or ""), "username": j.get("username"),
                "account_type": j.get("account_type")}

    def check_identity(self) -> dict:
        got = self.whoami()
        name = str(got.get("username") or "").lower()
        if any(bad in name for bad in NEVER):
            raise Refused(f"instagram: signed in as {got.get('username')!r}; Purplelink never posts there")
        exp = self.expected()
        missing = [k for k in self.identity_keys if not str(exp.get(k, "")).strip()]
        if missing:
            raise Refused(f"instagram: config has no expected {', '.join(missing)}; refusing to post to an "
                          f"account nobody named")
        for key, got_key in self.identity_keys.items():
            if str(got.get(got_key, "")).strip().lower() != str(exp[key]).strip().lower():
                raise Refused(f"instagram: signed in as {got.get(got_key)!r}, expected {exp[key]!r} ({key})")
        return got

    def refresh(self) -> None:
        """Renew the long-lived token (allowed once it is 24 hours old and before it expires)."""
        r = self.ok(self.http.request("GET", f"{API}/refresh_access_token?grant_type=ig_refresh_token", self._auth()),
                    "token refresh")
        new = (r.json() or {}).get("access_token")
        if not new:
            raise SocialError("instagram: refresh answered without a token")
        sysutil.keychain_set("instagram", "access_token", new)

    def _create(self, uid: str, params: dict) -> str:
        r = self.ok(self.http.request("POST", f"{API}/{uid}/media", self._auth(), form=params), "create container")
        cid = (r.json() or {}).get("id")
        if not cid:
            raise SocialError("instagram: container answered without an id")
        return str(cid)

    def _wait(self, cid: str, tries: int, every: int) -> None:
        for _ in range(tries):
            r = self.ok(self.http.request("GET", f"{API}/{cid}?fields=status_code,status", self._auth()),
                        "container status")
            j = r.json() or {}
            st = j.get("status_code")
            if st in ("FINISHED", "PUBLISHED"):
                return
            if st in ("ERROR", "EXPIRED"):
                raise SocialError(f"instagram: container {st}: {str(j.get('status') or '')[:200]}")
            self.sleep(every)
        raise SocialError(f"instagram: container not ready after {tries * every // 60} minutes")

    def post(self, item: Item, dry_run: bool = False) -> Result:
        caption = item.render("instagram")
        images = item.images_for("instagram")
        video = item.video()
        if dry_run:
            what = f"Reel {video.get('duration')} s" if video else f"{len(images)} image"
            return Result(dry_run=True, detail=f"{len(caption)} chars, {what}")
        who = self.check_identity()
        uid = who["user_id"]
        cfg = self.cfg["_root"]
        key = None
        try:
            if video:
                url, key = media.host_video(cfg, _resolve(video["path"], item.path.parent), self.http,
                                            self.video_client)
                params = {"media_type": "REELS", "video_url": url, "caption": caption, "share_to_feed": "true"}
                if video.get("cover"):
                    params["cover_url"] = media.ensure_hosted(cfg, _resolve(video["cover"], item.path.parent), self.http)
                cid = self._create(uid, params)
                self._wait(cid, tries=40, every=15)      # a Reel takes a few minutes to process
            elif images:
                url = media.ensure_hosted(cfg, image_path(item, images[0]), self.http)
                cid = self._create(uid, {"image_url": url, "caption": caption, "alt_text": str(images[0]["alt"])})
                self._wait(cid, tries=12, every=5)
            else:
                raise SocialError("instagram: nothing to post (no image and no Reel)")
            self.check_identity()  # again, right before it becomes public
            r = self.http.request("POST", f"{API}/{uid}/media_publish", self._auth(), form={"creation_id": cid})
            if r.status == 0 or r.status >= 500:
                raise Ambiguous(f"instagram: publish answered {r.status}; the post may be live, check the account")
            self.ok(r, "publish")
            mid = (r.json() or {}).get("id")
            if not mid:
                raise Ambiguous("instagram: publish answered 2xx without an id; the post may be live, check the account")
        finally:
            if key:
                media.delete_video(cfg, key, self.video_client)
        # From here the post is public. Nothing below may raise: a retry would post it twice.
        link = None
        try:
            p = self.http.request("GET", f"{API}/{mid}?fields=permalink", self._auth())
            link = (p.json() or {}).get("permalink") if p.status == 200 else None
        except Exception:
            pass
        return Result(url=link or f"https://www.instagram.com/{who['username']}/", id=str(mid),
                      detail="" if link else "permalink unavailable; url is the profile")

    def verify(self, url: str) -> bool:
        r = self.http.request("GET", url)
        return r.status == 200
