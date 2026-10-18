"""Bluesky through a saved browser session (Playwright, headless), the same pattern as backend/scripts/linkedin_post.py.

No API credential of any kind is used. Ben logs in once in a visible window (backend/scripts/bluesky_login.py);
the profile is kept in ~/.purplelink/bluesky-profile. The signed-in account is read from the web app's own session
store (localStorage BSKY_STORAGE) and compared with the expected handle before and again right before publishing.
Posts are verified, and de-duplicated, through the public AppView (public.api.bsky.app), which needs no login.

Images: the composer has no standing <input type=file>. The photo button creates one on click, so the poster uses
Playwright's file chooser. After attaching, the number of thumbnails is checked against the number of images: the paste
workaround used by hand once added images twice, so extras are removed and a shortfall aborts the post.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import re
import time

from .. import paths
from ..errors import Ambiguous, Refused, SessionExpired, SocialError
from ..items import Item, image_path
from .base import Adapter, Result

APPVIEW = "https://public.api.bsky.app/xrpc"
HOME = "https://bsky.app/"
# The web app persists its session in localStorage (historically one BSKY_STORAGE key; newer builds split it across
# keys). Look for a stored object that has session.currentAccount with both a handle and a DID; the left-nav Profile
# link is the fallback (see _signed_in).
STORAGE_JS = """() => {
  for (const k of Object.keys(window.localStorage)) {
    try {
      const v = JSON.parse(window.localStorage.getItem(k));
      const c = v && ((v.session && v.session.currentAccount) || v.currentAccount);
      if (c && c.handle && c.did) return JSON.stringify({session: {currentAccount: c}});
    } catch (e) {}
  }
  return window.localStorage.getItem('BSKY_STORAGE');
}"""
NAV_JS = ("() => { const a = document.querySelector('a[aria-label=\"Profile\"], a[href^=\"/profile/\"][data-testid=\"leftNavButton\"]');"
          " return a ? a.getAttribute('href') : null; }")


def parse_storage(raw: str | None) -> dict | None:
    """Return {'handle','did'} of the signed-in account from BSKY_STORAGE, or None."""
    if not raw:
        return None
    try:
        s = json.loads(raw).get("session") or {}
    except ValueError:
        return None
    cur = s.get("currentAccount") or {}
    if cur.get("handle") and cur.get("did"):
        return {"handle": cur["handle"], "did": cur["did"]}
    return None


class Bluesky(Adapter):
    name = "bluesky"
    identity_keys = {"handle": "handle"}

    def __init__(self, *a, session_factory=None, **kw):
        super().__init__(*a, **kw)
        self._session_factory = session_factory

    # -- browser
    @contextlib.contextmanager
    def session(self):
        if self._session_factory:
            with self._session_factory() as page:
                yield page
            return
        prof = paths.bluesky_profile()
        if not prof.exists():
            raise SessionExpired("bluesky: no saved session; run: python3 backend/scripts/social.py setup bluesky")
        from playwright.sync_api import sync_playwright, Error as PWError  # lazy: not needed for tests or other platforms
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(prof), headless=True, viewport={"width": 1280, "height": 1500},
                args=["--disable-blink-features=AutomationControlled"])
            try:
                yield ctx.pages[0] if ctx.pages else ctx.new_page()
            except PWError as e:
                raise SocialError(f"bluesky: browser error: {str(e).splitlines()[0][:200]}")
            finally:
                ctx.close()

    def _signed_in(self, page) -> dict:
        acct = parse_storage(page.evaluate(STORAGE_JS))
        if not acct:
            href = page.evaluate(NAV_JS)
            m = re.match(r"^/profile/([^/?#]+)", href or "")
            if m:
                acct = {"handle": m.group(1), "did": ""}
        if not acct:
            raise SessionExpired("bluesky: not signed in; run: python3 backend/scripts/social.py setup bluesky")
        return acct

    def _open_home(self, page) -> dict:
        page.goto(HOME, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(3_000)
        return self._signed_in(page)

    def whoami(self) -> dict:
        with self.session() as page:
            acct = self._open_home(page)
        return self._cross_check(acct)

    def _cross_check(self, acct: dict) -> dict:
        """The handle shown by the app must resolve, on the public AppView, to the same DID."""
        r = self.http.request("GET", f"{APPVIEW}/app.bsky.actor.getProfile?actor={acct['handle']}")
        prof = r.json() or {}
        if r.status != 200 or not prof.get("did"):
            raise SocialError(f"bluesky: could not resolve {acct['handle']} on the public AppView ({r.status})")
        if acct.get("did") and prof["did"] != acct["did"]:
            raise Refused(f"bluesky: handle {acct['handle']!r} resolves to {prof['did']}, but the session is {acct['did']}")
        return {"handle": prof.get("handle", acct["handle"]), "did": prof["did"]}

    def check_identity(self) -> dict:
        got = super().check_identity()
        want_did = str(self.expected().get("did", "")).strip()
        if want_did and got.get("did") != want_did:
            raise Refused(f"bluesky: DID {got.get('did')!r}, expected {want_did!r}")
        return got

    # -- feed (verification and de-duplication)
    @staticmethod
    def _needle(text: str) -> str:
        return " ".join(text.split())[:50]

    def find_post(self, handle: str, text: str, since: dt.datetime) -> dict | None:
        r = self.http.request("GET", f"{APPVIEW}/app.bsky.feed.getAuthorFeed?actor={handle}&limit=15&filter=posts_no_replies")
        if r.status != 200:
            return None
        needle = self._needle(text)
        for entry in (r.json() or {}).get("feed", []):
            post = entry.get("post") or {}
            rec = post.get("record") or {}
            if (post.get("author") or {}).get("handle", "").lower() != handle.lower() or entry.get("reason"):
                continue
            try:
                created = dt.datetime.fromisoformat(str(rec.get("createdAt", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if created >= since and " ".join(str(rec.get("text", "")).split()).startswith(needle):
                return post
        return None

    @staticmethod
    def post_url(post: dict) -> str:
        rkey = post["uri"].rsplit("/", 1)[-1]
        return f"https://bsky.app/profile/{post['author']['handle']}/post/{rkey}"

    # -- posting
    def post(self, item: Item, dry_run: bool = False) -> Result:
        text = item.render("bluesky")
        images = item.images_for("bluesky")
        handle = self.expected().get("handle", "")
        with self.session() as page:
            acct = self._open_home(page)
            self._guard_identity(page, acct)
            if not dry_run:
                dup = self.find_post(handle, text, dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2))
                if dup:  # an earlier attempt already went out: report it, never post twice
                    return Result(url=self.post_url(dup), id=dup["uri"], detail="already live; not reposted")
            started = dt.datetime.now(dt.timezone.utc)
            self._compose(page, text, item, images)
            self._guard_identity(page, self._signed_in(page))
            if dry_run:
                return Result(dry_run=True, detail=f"composer filled: {len(text)} chars, {len(images)} images; not published")
            page.get_by_test_id("composerPublishBtn").click(timeout=15_000)
            page.wait_for_timeout(4_000)
        for _ in range(12):
            found = self.find_post(handle, text, started - dt.timedelta(minutes=1))
            if found:
                return Result(url=self.post_url(found), id=found["uri"])
            self.sleep(5)
        raise Ambiguous("bluesky: Post was clicked but the post is not on the public feed after 60 s; check the account")

    def _guard_identity(self, page, acct: dict) -> None:
        resolved = self._cross_check(acct)
        exp = str(self.expected().get("handle", "")).strip().lower()
        if not exp:
            raise Refused("bluesky: config has no expected handle")
        if resolved["handle"].lower() != exp:
            raise Refused(f"bluesky: signed in as {resolved['handle']!r}, expected {exp!r}")
        want_did = str(self.expected().get("did", "")).strip()
        if want_did and resolved["did"] != want_did:
            raise Refused(f"bluesky: DID {resolved['did']!r}, expected {want_did!r}")

    def _compose(self, page, text: str, item: Item, images: list[dict]) -> None:
        # Selectors checked against the live web app on 2026-10-18: the nav button is "Compose new post", the
        # editor is a TipTap contenteditable inside composePostView (there is no composerTextInput test id), and
        # the page can hold more than one [role=dialog], so everything is scoped to composePostView.
        try:
            page.get_by_role("button", name=re.compile(r"new post", re.I)).first.click(timeout=15_000)
        except Exception:
            page.get_by_test_id("composeFAB").click(timeout=15_000)
        view = page.get_by_test_id("composePostView")
        editor = view.locator("[contenteditable=true]").first
        editor.wait_for(state="visible", timeout=20_000)
        editor.click()
        page.keyboard.insert_text(text)
        page.wait_for_timeout(800)
        if not images:
            return
        files = [str(image_path(item, im)) for im in images]
        with page.expect_file_chooser(timeout=15_000) as fc:
            view.get_by_test_id("openMediaBtn").click()
        fc.value.set_files(files)
        page.wait_for_timeout(2_500)
        self._dedupe_thumbnails(view, page, len(images))
        for i, im in enumerate(images):
            view.get_by_test_id("altTextButton").nth(i).click(timeout=10_000)
            box = page.locator('textarea[aria-label="Alt text"]').last  # a label match also hits the "Add alt text" button
            box.wait_for(state="visible", timeout=10_000)
            box.fill(str(im["alt"]))
            page.get_by_role("button", name=re.compile(r"^save$", re.I)).last.click(timeout=10_000)
            page.wait_for_timeout(400)

    def _dedupe_thumbnails(self, view, page, want: int) -> None:
        # One "Remove image" button per attached image (the old selectedPhotoImage test id is gone).
        removes = view.get_by_test_id("removePhotoButton")
        for _ in range(want + 4):
            if removes.count() <= want:
                break
            removes.last.click(timeout=10_000)  # an image was added twice
            page.wait_for_timeout(400)
        if removes.count() != want:
            raise SocialError(f"bluesky: {removes.count()} images attached, expected {want}; nothing was posted")

    def verify(self, url: str) -> bool:
        m = re.match(r"^https://bsky\.app/profile/([^/]+)/post/([A-Za-z0-9]+)$", url)
        if not m:
            return False
        r = self.http.request("GET", f"{APPVIEW}/app.bsky.actor.getProfile?actor={m.group(1)}")
        did = (r.json() or {}).get("did")
        if not did:
            return False
        t = self.http.request("GET", f"{APPVIEW}/app.bsky.feed.getPosts?uris=at://{did}/app.bsky.feed.post/{m.group(2)}")
        return t.status == 200 and bool((t.json() or {}).get("posts"))
