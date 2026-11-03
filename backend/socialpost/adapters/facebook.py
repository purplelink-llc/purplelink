"""Facebook: the Purplelink LLC Page, through the Pages API (graph.facebook.com) with a Page access token.

The Page token comes from `social.py setup facebook` (a user token from the Graph API Explorer, made long-lived, then
the Page's own token from /me/accounts; a Page token derived that way does not expire). It is in the keychain as
`page_token` (service purplelink-social-facebook) and also serves Instagram in its "facebook" mode, because
@purplelink.llc is connected to this Page. A text post goes to /{page}/feed with its link (Facebook draws the
preview); a post with one image goes to /{page}/photos with the text as the caption. Credentials travel in the
Authorization header, never in a URL.

A Reel (an item with `video`) goes through the Pages Reels API: /{page}/video_reels upload_phase=start gives a video
id, rupload.facebook.com fetches the file from the public video bucket (media.host_video; the object is deleted after),
and upload_phase=finish with video_state=PUBLISHED and the description makes it public. Reels here are 3 to 90 s.
"""
from __future__ import annotations

from .. import media
from ..errors import Ambiguous, Refused, SocialError
from ..items import Item, _resolve, image_path
from ..text import utm_link
from .base import Adapter, Result

API = "https://graph.facebook.com/v23.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v23.0"
# Pages Ben also manages that must never receive Purplelink posts, checked before the pinned identity.
NEVER = ("rubblefront", "ball bouncer", "bald streamer")


class Facebook(Adapter):
    name = "facebook"
    identity_keys = {"page_id": "page_id", "name": "name"}

    def __init__(self, cfg: dict, http=None, secret=None, sleep=None, video_client=None):
        import time
        super().__init__(cfg, http, secret, sleep or time.sleep)
        self.video_client = video_client  # tests inject a fake S3 client factory

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.secret('page_token')}"}

    def page_id(self) -> str:
        return str(self.expected().get("page_id") or "")

    def whoami(self) -> dict:
        pid = self.page_id()
        if not pid:
            raise SocialError("facebook: no page_id pinned; run social.py setup facebook")
        r = self.ok(self.http.request("GET", f"{API}/{pid}?fields=id,name", self._auth()), "page")
        j = r.json() or {}
        return {"page_id": str(j.get("id") or ""), "name": j.get("name")}

    def check_identity(self) -> dict:
        got = self.whoami()
        if any(bad in str(got.get("name") or "").lower() for bad in NEVER):
            raise Refused(f"facebook: the token is for the Page {got.get('name')!r}; Purplelink never posts there")
        return super().check_identity()

    def refresh(self) -> None:
        """A Page token made from a long-lived user token does not expire; nothing to renew."""

    def post(self, item: Item, dry_run: bool = False) -> Result:
        text = item.render("facebook")
        images = item.images_for("facebook")
        if dry_run:
            return Result(dry_run=True, detail=f"{len(text)} chars, {len(images)} image")
        who = self.check_identity()
        pid = who["page_id"]
        if item.video():
            return self._reel(item, pid, text)
        if images:
            url = media.ensure_hosted(self.cfg["_root"], image_path(item, images[0]), self.http)
            r = self.http.request("POST", f"{API}/{pid}/photos", self._auth(), form={"url": url, "caption": text})
        else:
            form = {"message": text}
            if item.link:
                form["link"] = utm_link(item.link, "facebook", item.campaign, item.utm_content("facebook"))
            r = self.http.request("POST", f"{API}/{pid}/feed", self._auth(), form=form)
        if r.status == 0 or r.status >= 500:
            raise Ambiguous(f"facebook: publish answered {r.status}; the post may be live, check the Page")
        self.ok(r, "publish")
        j = r.json() or {}
        post_id = j.get("post_id") or j.get("id")
        if not post_id:
            raise Ambiguous("facebook: publish answered 2xx without an id; the post may be live, check the Page")
        # From here the post is public. Nothing below may raise: a retry would post it twice.
        link = None
        try:
            p = self.http.request("GET", f"{API}/{post_id}?fields=permalink_url", self._auth())
            link = (p.json() or {}).get("permalink_url") if p.status == 200 else None
        except Exception:
            pass
        return Result(url=link or f"https://www.facebook.com/{pid}", id=str(post_id),
                      detail="" if link else "permalink unavailable; url is the Page")

    def _reel(self, item: Item, pid: str, text: str) -> Result:
        cfg = self.cfg["_root"]
        v = item.video()
        r = self.ok(self.http.request("POST", f"{API}/{pid}/video_reels", self._auth(), form={"upload_phase": "start"}),
                    "reel start")
        vid = (r.json() or {}).get("video_id")
        if not vid:
            raise SocialError("facebook: reel start answered without a video_id")
        url, key = media.host_video(cfg, _resolve(v["path"], item.path.parent), self.http, self.video_client)
        try:
            tok = self.secret("page_token")
            up = self.http.request("POST", f"{RUPLOAD}/{vid}", {"Authorization": f"OAuth {tok}", "file_url": url})
            if up.status >= 400 or not (up.json() or {}).get("success"):
                raise SocialError(f"facebook: the reel upload answered {up.status}")
            fin = self.http.request("POST", f"{API}/{pid}/video_reels", self._auth(),
                                    form={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                          "description": text})
            if fin.status == 0 or fin.status >= 500:
                raise Ambiguous(f"facebook: reel finish answered {fin.status}; the reel may be live, check the Page")
            self.ok(fin, "reel finish")
            if not (fin.json() or {}).get("success"):
                raise Ambiguous("facebook: reel finish answered without success; check the Page")
            # Facebook processes the video after finish; wait (up to 5 minutes) so the bucket copy is not deleted
            # before it has been fetched. Nothing here may raise now: the reel is published.
            for _ in range(30):
                try:
                    st = self.http.request("GET", f"{API}/{vid}?fields=status", self._auth())
                    phase = (((st.json() or {}).get("status") or {}).get("video_status") or "")
                    if phase in ("ready", "published", "error"):
                        break
                except Exception:
                    break
                self.sleep(10)
        finally:
            media.delete_video(cfg, key, self.video_client)
        return Result(url=f"https://www.facebook.com/reel/{vid}", id=str(vid))

    def verify(self, url: str) -> bool:
        return bool(url)   # Facebook answers scripts with a login wall; the publish id is the proof
