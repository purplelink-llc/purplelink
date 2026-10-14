"""Tool-page offer cards: at most one per tool page, correctly tagged, only the four allowed apps, claims that the
product page still states, and none of the old generic ModernTex block. The mapping lives in scripts/tool_offers.py."""
import html
import re
import sys
import unittest
from urllib.parse import urlsplit, parse_qs

from common import ROOT, SITE, EMOJI, read_site

sys.path.insert(0, str(ROOT / "scripts"))
import tool_offers as T  # noqa: E402

TOOL_DIRS = sorted(p.parent.name for p in (SITE / "tools").glob("*/index.html"))
APPS = {"moderntex", "tapefolio", "outbound-veil", "vitae"}
FORBIDDEN = ("/keyfeel/", "/legroom/", "/panely/", "/summonly/", "/batterymeter/")
CARD = re.compile(r'<aside class="tool-offer"[^>]*>.*?</aside>', re.S)


def text_of(path):
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", read_site(path))
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)))


class ToolOffers(unittest.TestCase):
    def test_every_offer_slug_is_a_tool_page(self):
        self.assertFalse(set(T.OFFERS) - set(TOOL_DIRS))

    def test_each_page_has_at_most_one_card_and_only_where_mapped(self):
        for slug in TOOL_DIRS:
            page = read_site(f"tools/{slug}/index.html")
            n = len(CARD.findall(page))
            self.assertEqual(page.count('class="tool-offer"'), n, slug)
            self.assertEqual(n, 1 if slug in T.OFFERS else 0, slug)

    def test_offer_links_are_tagged_with_their_own_slug_and_one_of_four_apps(self):
        for slug in T.OFFERS:
            card = CARD.search(read_site(f"tools/{slug}/index.html")).group(0)
            hrefs = re.findall(r'href="([^"]+)"', card)
            self.assertEqual(len(hrefs), 1, slug)
            u = urlsplit(html.unescape(hrefs[0]))
            q = parse_qs(u.query)
            self.assertEqual(q["utm_source"], [f"tool-{slug}"], slug)
            self.assertEqual(q["utm_medium"], ["tool"], slug)
            self.assertIn(q["utm_campaign"][0], APPS, slug)
            self.assertEqual(u.path, T.APPS[q["utm_campaign"][0]]["href"], slug)
            self.assertIn(f'data-offer="{q["utm_campaign"][0]}"', card, slug)
            self.assertIn(f'data-track-meta="{q["utm_campaign"][0]}"', card, slug)
            self.assertTrue((SITE / u.path.strip("/") / "index.html").is_file(), slug)

    def test_card_never_links_to_the_other_apps(self):
        for slug in T.OFFERS:
            card = CARD.search(read_site(f"tools/{slug}/index.html")).group(0)
            for bad in FORBIDDEN:
                self.assertNotIn(bad, card, slug)
            for name in ("Keyfeel", "Legroom", "Panely", "Summonly", "BatteryMeter"):
                self.assertNotIn(name, card, slug)

    def test_no_page_still_has_the_old_generic_block(self):
        for slug in TOOL_DIRS:
            page = read_site(f"tools/{slug}/index.html")
            for gone in ("<!-- moderntex-cta -->", "Writing LaTeX on a Mac?", "waitlist-section mt-cta", "From the maker of these tools"):
                self.assertNotIn(gone, page, f"{slug}: {gone}")

    def test_pages_are_exactly_what_the_generator_writes(self):
        for slug in TOOL_DIRS:
            page = read_site(f"tools/{slug}/index.html")
            self.assertEqual(T.rewrite(slug, page), page, slug)

    def test_copy_is_plain(self):
        for slug in T.OFFERS:
            card = html.unescape(CARD.search(read_site(f"tools/{slug}/index.html")).group(0))
            self.assertNotRegex(card, EMOJI, slug)
            self.assertNotIn("—", card, slug)
            self.assertNotIn("&mdash;", card, slug)
            self.assertNotIn("!", re.sub(r"<[^>]+>", "", card), slug)
            self.assertNotRegex(card, r"(?i)\b(discount|% off|bundle|HIPAA|compliant with|guarantee|trusted by)\b", slug)

    def test_price_and_limit_lines_match_the_product_pages(self):
        must = {
            "moderntex": ["$19.99 once, after a free 7-day trial", "macOS 14"],
            "tapefolio": ["$29.99", "7 days", "macOS 26 or later on a Mac with Apple silicon", "It will mishear words"],
            "outbound-veil": ["$29.99", "7 days", "macOS 14 or later", "It will miss some things", "not a compliance product"],
            "vitae": ["The app is free, with no limits on your record", "macOS 15 Sequoia or later"],
        }
        for app, phrases in must.items():
            page = text_of(f"{app}/index.html")
            for p in phrases:
                self.assertIn(p, page, f"{app}: {p}")

    def test_every_claim_is_still_stated_on_the_product_page(self):
        evidence = {
            "latex-to-pdf": ("moderntex", ["so there is no server compile timeout", "Live mode keeps the PDF in sync as you type"]),
            "latex-diff": ("moderntex", ["Take a snapshot at any point", "Compare any two snapshots in a diff"]),
            "bib-validator": ("moderntex", ["Clearer bibliography build errors, pointing at the .bib line", "BibTeX autocomplete that searches your bibliography by author, title, or key"]),
            "bib-builder": ("moderntex", ["BibTeX autocomplete that searches your bibliography by author, title, or key"]),
            "citation-generator": ("moderntex", ["BibTeX autocomplete that searches your bibliography by author, title, or key"]),
            "reference-converter": ("moderntex", ["BibTeX autocomplete that searches your bibliography by author, title, or key"]),
            "word-to-latex": ("moderntex", ["shows a structured sidebar", "Synchronized PDF preview", "plain explanations"]),
            "latex-table-generator": ("moderntex", ["Table editor", "Paste a range from Excel or Google Sheets", "Resize columns by dragging", "booktabs-style LaTeX"]),
            "equation-renderer": ("moderntex", ["Live mode keeps the PDF in sync as you type", "plain explanations"]),
            "thesis-format-checker": ("moderntex", ["dissertation chapters", "Jump between chapters, sections, and bibliography files"]),
            "camera-ready-checker": ("moderntex", ["anonymization, page limits, required sections, and submission packaging"]),
            "submission-checklist": ("moderntex", ["anonymization, page limits, required sections, and submission packaging"]),
            "transcript-cleaner": ("tapefolio", ["transcribes interview and meeting recordings on your Mac", "labels the speakers", "replace names and other identifiers", "Your files are not uploaded", "It will mishear words"]),
            "metadata-cleaner": ("outbound-veil", ["checks what you type for personal information", "Names, street addresses, phone numbers", "Card numbers", "ChatGPT and claude.ai prompt boxes in Chrome", "the text never leaves it"]),
            "anonymity-check": ("outbound-veil", ["checks what you type for personal information", "Names, street addresses, phone numbers", "Government and tax"]),
            "resume-review": ("vitae", ["imports it from Word, PDF, RTF, ODT, or a web page", "your CV fills itself from your records", "Export to PDF, LaTeX or rich text"]),
        }
        self.assertEqual(set(evidence), set(T.OFFERS))
        for slug, (app, phrases) in evidence.items():
            page = text_of(f"{app}/index.html")
            for p in phrases:
                self.assertIn(p.lower(), page.lower(), f"{slug}: {p}")


if __name__ == "__main__":
    unittest.main()
