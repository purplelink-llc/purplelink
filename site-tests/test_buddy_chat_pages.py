"""Where Buddy, the site chat, appears (docs/designs/buddy-chat.md, Boundaries; Ben, 2026-11-03: "Everywhere except
checkout"): on every public page, never on an account or payment flow page, and never as a render-blocking stylesheet."""
import re
import unittest

from common import SITE

LOADER = re.compile(r'<script src="/buddy-chat/loader\.js[^"]*" defer></script>')
FLOW_DIRS = {"checkout", "success", "upload", "manage", "recover", "account", "stats", "digest"}


def pages():
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        if rel.startswith("assets/") or rel.startswith("google"):
            continue
        yield rel, f.read_text(encoding="utf-8")


class BuddyChatPages(unittest.TestCase):
    def test_never_on_flow_pages(self):
        on_flow = [rel for rel, text in pages() if set(rel.split("/")[:-1]) & FLOW_DIRS and LOADER.search(text)]
        self.assertEqual(on_flow, [])

    def test_on_the_public_pages(self):
        for rel in ("index.html", "nee/index.html", "globepin/index.html", "guides/index.html", "blog/index.html",
                    "tools/png-to-jpg/index.html", "tools/heic-to-jpg/index.html", "tools/citation-gap/index.html",
                    "moderntex/index.html", "games/index.html"):
            with self.subTest(rel=rel):
                self.assertRegex((SITE / rel).read_text(encoding="utf-8"), LOADER)

    def test_stylesheet_is_added_by_the_loader_not_the_page(self):
        # A <link> to chat.css in <head> would hold up rendering on every page; loader.js adds it itself.
        with_css = [rel for rel, text in pages() if "/buddy-chat/chat.css" in text]
        self.assertEqual(with_css, [])
        loader = (SITE / "buddy-chat" / "loader.js").read_text(encoding="utf-8")
        self.assertIn('BASE + "chat.css"', loader)
        self.assertIn("css.onload = draw", loader)


if __name__ == "__main__":
    unittest.main()
