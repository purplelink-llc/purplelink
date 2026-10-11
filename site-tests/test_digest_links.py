import unittest
from common import read_site


class DigestLinks(unittest.TestCase):
    def test_blog_index_links_digest(self):
        self.assertIn('href="/blog/digest/"', read_site("blog/index.html"))

    def test_privacy_has_followup_paragraph(self):
        self.assertIn("One follow-up email after a Mac app purchase", read_site("privacy/index.html"))
