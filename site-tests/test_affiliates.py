"""Affiliate registry: rewriting, disclosure, and the real site. Stdlib only."""
import dataclasses
import subprocess
import sys
import unittest
from datetime import date

from common import ROOT, read_site

sys.path.insert(0, str(ROOT / "backend"))
from digest import affiliates as aff  # noqa: E402

PAGE = '<html><body><h1 class="post-title">T</h1><p><a class="x" href="https://setapp.com/apps" target="_blank">Setapp</a></p></body></html>'


def live_setapp(**kw):
    base = next(p for p in aff.REGISTRY if p.id == "setapp")
    return dataclasses.replace(base, status="approved", link="https://setapp.sjv.io/abc123", **kw)


class Rewrite(unittest.TestCase):
    def test_candidate_programs_change_nothing(self):
        self.assertEqual(aff.rewrite_html(PAGE), (PAGE, 0))
        self.assertEqual(aff.rewrite_url("https://setapp.com/apps"), ("https://setapp.com/apps", None))

    def test_approved_program_rewrites_link_and_keeps_other_attributes(self):
        reg = (live_setapp(),)
        new, n = aff.rewrite_html(PAGE, reg)
        self.assertGreaterEqual(n, 1)
        self.assertIn('href="https://setapp.sjv.io/abc123"', new)
        self.assertIn('class="x"', new)
        self.assertIn('target="_blank"', new)
        self.assertIn('rel="sponsored noopener"', new)

    def test_every_rewritten_link_gets_one_label_after_the_anchor(self):
        reg = (live_setapp(),)
        new, _ = aff.rewrite_html(PAGE, reg)
        self.assertIn("Setapp</a>" + aff.LABEL_HTML, new)
        self.assertEqual(new.count(aff.LABEL_HTML), 1)

    def test_lint_flags_missing_label(self):
        reg = (live_setapp(),)
        new, _ = aff.rewrite_html(PAGE, reg)
        unlabeled = new.replace(aff.LABEL_HTML, "")
        self.assertTrue(any("(paid link)" in p for p in aff.lint_html(unlabeled, reg)))

    def test_amazon_links_get_no_label(self):
        page = '<h1>T</h1><a href="https://www.amazon.com/dp/1">b</a>'
        new, _ = aff.rewrite_html(page)
        self.assertNotIn("aff-label", new)

    def test_requested_programs_are_candidates_without_links(self):
        ids = {"wordvice", "raycast", "paperpal", "scrivener", "ulysses", "proton", "pcloud", "readwise",
               "logitech", "setapp", "1password"}
        by_id = {p.id: p for p in aff.REGISTRY}
        self.assertTrue(ids <= set(by_id))
        for i in ids:
            p = by_id[i]
            self.assertEqual((p.status, p.link, p.deep_link, p.tag), ("candidate", "", "", ""), i)
            self.assertTrue(p.source_url.startswith("http"), i)

    def test_disclosure_added_once_after_h1_and_apply_is_idempotent(self):
        reg = (live_setapp(),)
        new, _ = aff.rewrite_html(PAGE, reg)
        self.assertEqual(new.count(aff.DISCLOSURE_MARK), 1)
        self.assertLess(new.index("</h1>"), new.index(aff.DISCLOSURE_MARK))
        again, n = aff.rewrite_html(new, reg)
        self.assertEqual((again, n), (new, 0))
        self.assertEqual(aff.lint_html(new, reg), [])

    def test_existing_rel_values_are_kept(self):
        reg = (live_setapp(),)
        page = PAGE.replace('target="_blank"', 'rel="nofollow" target="_blank"')
        new, _ = aff.rewrite_html(page, reg)
        self.assertIn('rel="nofollow sponsored noopener"', new)

    def test_deep_link_template_encodes_destination(self):
        reg = (live_setapp(deep_link="https://setapp.sjv.io/c/1/2/3?u={url}"),)
        url, p = aff.rewrite_url("https://setapp.com/apps?a=1&b=2", reg)
        self.assertEqual(p.id, "setapp")
        self.assertIn("u=https%3A%2F%2Fsetapp.com%2Fapps%3Fa%3D1%26b%3D2", url)

    def test_lint_flags_missing_disclosure_and_rel(self):
        reg = (live_setapp(),)
        bad = '<h1>T</h1><a href="https://setapp.sjv.io/abc123">x</a>'
        problems = aff.lint_html(bad, reg)
        self.assertTrue(any("rel=sponsored" in p for p in problems))
        self.assertTrue(any("no disclosure" in p for p in problems))

    def test_amazon_tag_is_added_only_on_product_paths(self):
        self.assertEqual(aff.rewrite_url("https://www.amazon.com/dp/0199760241")[0],
                         "https://www.amazon.com/dp/0199760241?tag=purplelinkpl-20")
        self.assertEqual(aff.rewrite_url("https://www.amazon.com/gp/help/customer/display.html")[1], None)
        self.assertEqual(aff.rewrite_url("https://www.amazon.com/dp/0199760241?tag=purplelinkpl-20")[1], None)

    def test_amazon_links_need_amazon_sentence_not_generic_disclosure(self):
        page = '<h1>T</h1><a href="https://www.amazon.com/dp/1?tag=purplelinkpl-20" rel="sponsored noopener">b</a>'
        self.assertEqual(aff.lint_html(page), ["Amazon links but no Amazon Associate statement"])
        self.assertEqual(aff.lint_html(page + aff.AMAZON_DISCLOSURE), [])


class Registry(unittest.TestCase):
    def test_registry_is_sound(self):
        self.assertEqual(aff.check_registry(), [])

    def test_unapproved_program_with_a_link_is_a_problem(self):
        bad = dataclasses.replace(next(p for p in aff.REGISTRY if p.id == "setapp"), link="https://x.example/a")
        self.assertTrue(any("not approved" in p for p in aff.check_registry((bad,))))

    def test_approved_terms_go_stale(self):
        old = live_setapp(terms_checked="2026-01-01")
        self.assertTrue(any("re-read" in p for p in aff.check_registry((old,), today=date(2026, 10, 12))))

    def test_http_tracked_link_is_rejected(self):
        bad = live_setapp(deep_link="http://x.example/?u={url}")
        self.assertTrue(any("https" in p for p in aff.check_registry((bad,))))


class RealSite(unittest.TestCase):
    def test_every_page_passes_the_affiliate_check(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "affiliates.py"), "check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_stylesheet_styles_the_disclosure(self):
        self.assertIn(".aff-disclosure", read_site("styles.css"))
        self.assertIn(".aff-label", read_site("styles.css"))

    def test_privacy_page_explains_affiliate_links(self):
        self.assertIn("(paid link)", read_site("privacy/index.html"))


if __name__ == "__main__":
    unittest.main()
