"""scripts/affiliates.py health: which URL it may fetch for each paid link. No network here.

A request to a network tracking URL (CJ, Impact) is recorded as a click, so the health check fetches only the
destination: an Amazon product page without the tag, a CJ deep link's url= target, or a plain link with its
referral query stripped. Fixed tracking links with no visible destination are reported, never fetched.
"""
import importlib.util
import unittest

from common import ROOT

spec = importlib.util.spec_from_file_location("affiliates_cli", ROOT / "scripts" / "affiliates.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class HealthTarget(unittest.TestCase):
    def test_amazon_product_is_checked_without_the_tag(self):
        self.assertEqual(cli.health_target("https://www.amazon.com/dp/0226826678?tag=purplelinkpl-20"),
                         ("https://www.amazon.com/dp/0226826678", "amazon product"))

    def test_lookalike_host_is_not_treated_as_amazon(self):
        self.assertEqual(cli.health_target("https://evilamazon.com/dp/0226826678"),
                         ("https://evilamazon.com/dp/0226826678", "referral link, query dropped"))

    def test_amazon_search_is_not_fetched(self):
        url, why = cli.health_target("https://www.amazon.com/s?k=laptop+stand&tag=purplelinkpl-20")
        self.assertIsNone(url)
        self.assertIn("search", why)

    def test_cj_deep_link_checks_its_destination_only(self):
        self.assertEqual(
            cli.health_target("https://www.tkqlhce.com/click-101903253-15733336?url=https%3A%2F%2Fwww.parallels.com%2Fproducts%2Fdesktop%2F"),
            ("https://www.parallels.com/products/desktop/", "deep link destination"))

    def test_fixed_tracking_links_are_never_fetched(self):
        for href in ("https://www.kqzyfj.com/click-101903253-15545954", "https://setapp.sjv.io/c/7961034/344326/5114"):
            url, why = cli.health_target(href)
            self.assertIsNone(url, href)
            self.assertIn("counts as a click", why)

    def test_plain_referral_link_drops_its_query(self):
        self.assertEqual(cli.health_target("https://wordvice.com/?aff=benjamin"), ("https://wordvice.com/", "referral link, query dropped"))


if __name__ == "__main__":
    unittest.main()
