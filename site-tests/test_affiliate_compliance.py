"""Site-wide affiliate compliance (added 2026-10-28).

For every paid link on the site (rel="sponsored", or a link the registry in backend/digest/affiliates.py recognises
as tracked):

1. rel carries both "sponsored" and "nofollow".
2. The page discloses it: the standard aff-disclosure paragraph, the Amazon Associates sentence for Amazon links,
   or a page's own "Disclosure:" paragraph that says referral or affiliate (the photography page).
3. Clicks are countable: data-aff or data-track on the link (see site/analytics.js).
4. No tracked link belongs to a program the registry marks rejected (1Password, Proton were declined on CJ).
5. Amazon links do not sit next to a hard-coded price (Associates Operating Agreement: prices change, so a stated
   price goes stale; show it only through Amazon's own tools).

Fix most failures with: python3 scripts/affiliates.py apply --write
"""
import html
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "backend"))
from digest import affiliates as aff  # noqa: E402

A_TAG = re.compile(r"<a\b[^>]*>", re.I)
PRICE = re.compile(r"(?:US)?\$\s?\d[\d,]*(?:\.\d\d)?|\b\d+(?:\.\d\d)?\s?(?:USD|dollars)\b")
OWN_DISCLOSURE = re.compile(r"Disclosure:[^<]{0,300}\b(?:referral|affiliate)", re.I)


def _href(tag):
    m = re.search(r'\bhref="([^"]+)"', tag)
    return html.unescape(m.group(1)) if m else ""


def _rel(tag):
    m = re.search(r'\brel="([^"]*)"', tag)
    return m.group(1).split() if m else []


def _pages():
    for page in sorted(SITE.rglob("*.html")):
        rel = page.relative_to(SITE).as_posix()
        if rel.startswith("blog/digest/"):  # retired digest; publisher.py applied the same rules when it rendered
            continue
        yield rel, page.read_text(encoding="utf-8", errors="ignore")


def _paid_links(text):
    for m in A_TAG.finditer(text):
        tag, href = m.group(0), _href(m.group(0))
        owner = aff.tracked_owner(href)
        if "sponsored" in _rel(tag) or owner is not None:
            yield m, tag, href, owner


def _block(text, start, end):
    """The paragraph, list item, table row or card around a link, as plain text."""
    opens = [text.rfind(o, 0, start) for o in ("<p", "<li", "<tr", "<figure", '<a class="catalog-card')]
    s = max(opens)
    closes = [i for i in (text.find(c, end) for c in ("</p>", "</li>", "</tr>", "</figure>")) if i > 0]
    e = min(closes) if closes else end + 400
    return html.unescape(re.sub(r"<[^>]+>", " ", text[max(s, 0):e]))


class AffiliateCompliance(unittest.TestCase):
    def test_paid_links_are_sponsored_nofollow_disclosed_and_countable(self):
        problems = []
        for rel, text in _pages():
            links = list(_paid_links(text))
            if not links:
                continue
            generic = aff.DISCLOSURE_MARK in text or bool(OWN_DISCLOSURE.search(text))
            for m, tag, href, owner in links:
                r = _rel(tag)
                if "sponsored" not in r or "nofollow" not in r:
                    problems.append(f"{rel}: rel={' '.join(r)!r} needs sponsored and nofollow: {href[:70]}")
                if "data-aff=" not in tag and "data-track=" not in tag:
                    problems.append(f"{rel}: not countable (no data-aff/data-track): {href[:70]}")
                if owner is not None and owner.id == "amazon":
                    if aff.AMAZON_DISCLOSURE not in text:
                        problems.append(f"{rel}: Amazon link without the Associates sentence")
                elif not generic:
                    problems.append(f"{rel}: paid link without a disclosure paragraph: {href[:70]}")
        self.assertEqual(problems, [])

    def test_no_tracked_links_for_rejected_programs(self):
        rejected = [p for p in aff.REGISTRY if p.status == "rejected"]
        self.assertTrue(rejected, "registry has no rejected programs; update this test if that changed")
        problems = []
        for p in rejected:
            self.assertFalse(p.live, p.id)
            self.assertEqual((p.link, p.deep_link, p.tag), ("", "", ""), p.id)
        for rel, text in _pages():
            for m in A_TAG.finditer(text):
                tag, href = m.group(0), _href(m.group(0))
                host = re.sub(r"^www\.", "", (re.match(r"https?://([^/]+)", href) or [None, ""])[1].lower())
                for p in rejected:
                    if any(host == d or host.endswith("." + d) for d in p.domains) and "sponsored" in _rel(tag):
                        problems.append(f"{rel}: paid link to declined program {p.id}: {href[:70]}")
        self.assertEqual(problems, [])

    def test_amazon_links_have_no_hard_coded_price_nearby(self):
        problems = []
        for rel, text in _pages():
            for m, tag, href, owner in _paid_links(text):
                if owner is None or owner.id != "amazon":
                    continue
                hits = PRICE.findall(_block(text, m.start(), m.end()))
                if hits:
                    problems.append(f"{rel}: price {hits} next to Amazon link {href[:60]}")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
