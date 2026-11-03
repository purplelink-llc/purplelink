"""LinkedIn company page 120183926 only, through backend/scripts/linkedin_post.py (unchanged).

That script already refuses (exit 4) unless the page is /company/120183926/admin and the composer reads
"Purplelink LLC", before typing and again before Post. This adapter adds a read-only identity check of its own and a
published-page check, so a retry never posts the same text twice. Text and PDF documents only (no images).
"""
from __future__ import annotations

import contextlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import paths
from ..errors import Ambiguous, Refused, SessionExpired, SocialError
from ..items import Item, _resolve
from .base import Adapter, Result

COMPANY_URL = "https://www.linkedin.com/company/120183926/admin/page-posts/published/"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "linkedin_post.py"


def _norm(s: str) -> str:
    return " ".join(s.split())


FEED_URL = "https://www.linkedin.com/feed/update/{urn}/"
URLISH = re.compile(r"https?://\S+")


def permalink_for(rows: list, text: str) -> str | None:
    """The public URL of the post whose text starts like `text`, from the published page's [urn, visible text] rows
    (each post element carries data-urn="urn:li:activity:<id>"). Links are left out of the match: LinkedIn shortens
    them in the visible text."""
    want = _norm(URLISH.sub(" ", text))[:50]
    for urn, body in rows:
        if want and want in _norm(body) and re.fullmatch(r"urn:li:activity:\d{15,22}", str(urn)):
            return FEED_URL.format(urn=urn)
    return None


class LinkedIn(Adapter):
    name = "linkedin"
    identity_keys = {"company_id": "company_id", "name": "name"}

    def __init__(self, *a, session_factory=None, runner=subprocess.run, **kw):
        super().__init__(*a, **kw)
        self._session_factory = session_factory
        self._run = runner

    @contextlib.contextmanager
    def session(self):
        if self._session_factory:
            with self._session_factory() as page:
                yield page
            return
        prof = paths.linkedin_profile()
        if not prof.exists():
            raise SessionExpired("linkedin: no saved session; run: python3 backend/scripts/linkedin_login.py")
        from playwright.sync_api import sync_playwright, Error as PWError
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(prof), headless=True, viewport={"width": 1280, "height": 1800},
                args=["--disable-blink-features=AutomationControlled"])
            try:
                yield ctx.pages[0] if ctx.pages else ctx.new_page()
            except PWError as e:
                raise SocialError(f"linkedin: browser error: {str(e).splitlines()[0][:200]}")
            finally:
                ctx.close()

    def _published_page(self) -> tuple[str, str]:
        """(final URL, visible text) of the company's published-posts admin page. Read only."""
        with self.session() as page:
            page.goto(COMPANY_URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(4_000)
            url = page.url
            if "login" in url or "signup" in url or "checkpoint" in url:
                raise SessionExpired("linkedin: session expired; run: python3 backend/scripts/linkedin_login.py")
            return url, page.inner_text("body", timeout=15_000)

    def _published_rows(self) -> list:
        """[[urn, visible text]] for each post on the published page. Read only."""
        with self.session() as page:
            page.goto(COMPANY_URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(6_000)
            return page.evaluate("""() => [...document.querySelectorAll('[data-urn^="urn:li:activity:"]')]
                .map(e => [e.getAttribute('data-urn'), e.innerText])""")

    def permalink(self, text: str) -> str | None:
        try:
            return permalink_for(self._published_rows(), text)
        except Exception:
            return None

    def whoami(self) -> dict:
        url, body = self._published_page()
        m = re.search(r"/company/(\d+)/admin", url)
        return {"company_id": m.group(1) if m else "", "name": "Purplelink LLC" if "Purplelink LLC" in body else ""}

    def validate(self, item: Item) -> list[str]:
        return []

    def _already_live(self, text: str) -> bool:
        return _norm(text)[:50] in _norm(self._published_page()[1])

    def post(self, item: Item, dry_run: bool = False) -> Result:
        text = item.render("linkedin")
        doc = item.document()
        if not dry_run:
            self.check_identity()
            if self._already_live(text):
                return Result(url=self.permalink(text) or COMPANY_URL, id="already-live",
                              detail="the same text is already on the page; not reposted")
        with tempfile.TemporaryDirectory() as td:
            tf = Path(td) / "post.txt"
            tf.write_text(text, encoding="utf-8")
            cmd = [sys.executable, str(SCRIPT), "--text-file", str(tf), "--headless"]
            if doc:
                cmd += ["--document", str(_resolve(doc["path"], item.path.parent)), "--document-title", str(doc["title"])]
            if dry_run:
                cmd.append("--dry-run")
            p = self._run(cmd, capture_output=True, text=True, timeout=600)
        code = p.returncode
        if code == 4:
            raise Refused("linkedin: linkedin_post.py refused (not the company page / not posting as Purplelink LLC)")
        if code == 2:
            raise SessionExpired("linkedin: session expired; run: python3 backend/scripts/linkedin_login.py")
        if code != 0:
            raise SocialError(f"linkedin: linkedin_post.py exited {code}")
        if dry_run:
            return Result(dry_run=True, detail="composer filled as the company; not posted")
        if not self._already_live(text):
            self.sleep(20)
            if not self._already_live(text):
                raise Ambiguous("linkedin: the poster reported success but the post is not on the page yet; check the page")
        # The published page lists each post with data-urn="urn:li:activity:<id>"; its public URL is the feed update
        # URL. Nothing below may raise: the post is live.
        link = self.permalink(text)
        return Result(url=link or COMPANY_URL, id=link.rsplit(":", 1)[-1].strip("/") if link else
                      f"company-page-{_norm(text)[:24]}",
                      detail="" if link else "post found on the page, but its public link could not be read")

    def verify(self, url: str) -> bool:
        return url.startswith(("https://www.linkedin.com/company/120183926/", "https://www.linkedin.com/feed/update/"))
