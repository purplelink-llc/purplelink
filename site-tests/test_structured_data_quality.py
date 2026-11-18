"""Structured data that search engines and AI answer engines read must match what a visitor can see.

Three checks over every indexable page (site-quality pass 1, 2026-11-18):

1. Every JSON-LD block parses and holds no HTML entities. A script element is not entity-decoded, so "R&amp;R" in
   JSON-LD is read as the literal text "R&amp;R".
2. Every indexable page except the home page carries a BreadcrumbList.
3. Every FAQPage question is visible on the page word for word (Google's FAQ rule: the marked-up question and answer
   must be visible to the user). Pages where the visible wording had already drifted from the schema are listed in
   fixtures/faq_wording_drift.json. That list may only shrink: fix the page, then delete its entry.
"""
import html
import json
import re
import unittest
from common import ROOT, SITE

LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ENTITY = re.compile(r"&(?:[a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);")
NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex')
TAG = re.compile(r"<[^>]+>")
DRIFT = ROOT / "site-tests" / "fixtures" / "faq_wording_drift.json"


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(TAG.sub("", s)).lower()).strip()


def pages():
    for f in sorted(SITE.rglob("index.html")):
        h = f.read_text(encoding="utf-8")
        if NOINDEX.search(h) or 'http-equiv="refresh"' in h:
            continue
        yield f.relative_to(SITE).as_posix(), h


def nodes(block):
    d = json.loads(block)
    for n in d if isinstance(d, list) else d.get("@graph", [d]):
        if isinstance(n, dict):
            yield n


def hidden_questions():
    out = {}
    for rel, h in pages():
        body = norm(LD.sub("", h))
        for block in LD.findall(h):
            for n in nodes(block):
                if n.get("@type") != "FAQPage":
                    continue
                miss = [q["name"] for q in n.get("mainEntity", []) if norm(q["name"]) not in body]
                if miss:
                    out.setdefault(rel, []).extend(miss)
    return out


class StructuredDataQuality(unittest.TestCase):
    def test_json_ld_parses_and_has_no_html_entities(self):
        bad = []
        for rel, h in pages():
            for block in LD.findall(h):
                try:
                    json.loads(block)
                except ValueError as e:
                    bad.append(f"{rel}: does not parse ({e})")
                m = ENTITY.search(block)
                if m:
                    bad.append(f"{rel}: HTML entity {m.group(0)} inside JSON-LD (write the character itself)")
        self.assertEqual(bad, [])

    def test_every_indexable_page_has_a_breadcrumb_list(self):
        missing = [rel for rel, h in pages() if rel != "index.html" and "BreadcrumbList" not in h]
        self.assertEqual(missing, [], "Add a BreadcrumbList JSON-LD block (Home > section > page).")

    def test_faq_schema_questions_are_visible_on_the_page(self):
        allowed = json.loads(DRIFT.read_text(encoding="utf-8"))
        found = hidden_questions()
        new = {p: [q for q in qs if q not in allowed.get(p, [])] for p, qs in found.items()}
        new = {p: qs for p, qs in new.items() if qs}
        self.assertEqual(
            new, {},
            "These FAQPage questions are in the schema but not visible on the page. Show the question and answer in "
            "the page (a details/summary block), with the same wording as the schema.",
        )

    def test_faq_drift_list_only_shrinks(self):
        allowed = json.loads(DRIFT.read_text(encoding="utf-8"))
        found = hidden_questions()
        stale = {p: [q for q in qs if q not in found.get(p, [])] for p, qs in allowed.items()}
        stale = {p: qs for p, qs in stale.items() if qs}
        self.assertEqual(stale, {}, "Fixed. Now delete these entries from site-tests/fixtures/faq_wording_drift.json.")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--write-drift-list"]:
        DRIFT.write_text(json.dumps(hidden_questions(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", DRIFT)
