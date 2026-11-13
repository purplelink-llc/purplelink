"""The $2 journal check (Paper Review upgrades, 2026-11-06): landing and upload pages, the journal select, the
product key wired to checkout, and the report-page offers in status.js. No deadlines or scarcity copy."""
import re
import sys
import unittest

from common import ROOT, SITE, EMOJI, read_site

sys.path.insert(0, str(ROOT / "backend"))
from latextools import journals  # noqa: E402

LANDING = "tools/paper-review/journal-check/index.html"
UPLOAD = "tools/paper-review/journal-check/upload/index.html"


class JournalCheckPages(unittest.TestCase):
    def test_landing_sells_the_journal_check_at_ten_dollars(self):
        page = read_site(LANDING)
        self.assertIn('data-product="journal-check"', page)
        self.assertIn("$10", page)
        self.assertIn("paid-tool-landing.js", page)
        self.assertIn('name="robots" content="noindex, follow"', page)
        self.assertNotIn("style=", page)
        self.assertFalse(EMOJI.search(page))
        for word in ("hurry", "only today", "limited time", "expires"):
            self.assertNotIn(word, page.lower())

    def test_landing_lists_every_journal_the_backend_knows(self):
        page = read_site(LANDING)
        for spec in journals.JOURNAL_SPECS.values():
            self.assertIn(spec["name"].replace("&", "&amp;"), page, spec["name"])

    def test_upload_page_has_the_journal_select_and_script(self):
        page = read_site(UPLOAD)
        self.assertIn('<select id="journal-input"', page)
        self.assertIn('name="robots" content="noindex, nofollow"', page)
        self.assertIn("/tools/paper-review/journal-check/upload.js", page)
        self.assertNotIn("style=", page)
        js = read_site("tools/paper-review/journal-check/upload.js")
        self.assertIn('productCategory: "journal-check"', js)
        self.assertIn('submitPath: "/journal-check/submit"', js)
        self.assertIn("/paper-review/journals?domain=general", js)

    def test_checkout_and_backend_agree_on_the_product(self):
        checkout = (ROOT / "netlify/functions/checkout.mjs").read_text()
        self.assertRegex(checkout, r'"journal-check":\s*\{\s*amount:\s*1000')
        app = (ROOT / "backend/app.py").read_text()
        self.assertRegex(app, r'"journal-check":\s*\{"category":\s*"journal-check",\s*"qty":\s*1,\s*"amount":\s*1000,\s*"legacy_amounts":\s*\[200\]\}')
        self.assertIn('@api.post("/journal-check/submit")', app)

    def test_status_page_renders_upgrade_offers(self):
        js = read_site("tools/paper-review/status.js")
        self.assertIn("renderUpgradeOffers(payload.upgrade_offers)", js)
        self.assertIn("/tools/paper-review/journal-check/?from=after-paper-review", js)
        self.assertIn("/tools/paper-review/packs/?from=after-paper-review", js)
        self.assertIn('"journal-check"', js)
        css = read_site("tools/paper-review/paper-review.css")
        self.assertIn(".pr-upgrade", css)


if __name__ == "__main__":
    unittest.main()
