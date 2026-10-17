import re
import unittest
from datetime import datetime, timezone
from common import SITE, ORIGIN, EMOJI, read_site


class SecurityTxt(unittest.TestCase):
    def setUp(self):
        self.text = read_site(".well-known/security.txt")
        self.fields = dict(
            line.split(": ", 1) for line in self.text.splitlines() if line and not line.startswith("#")
        )

    def test_required_fields(self):
        self.assertEqual(self.fields["Contact"], "mailto:ben@purplelink.llc")
        self.assertEqual(self.fields["Canonical"], ORIGIN + "/.well-known/security.txt")
        self.assertEqual(self.fields["Preferred-Languages"], "en")

    def test_expires_is_future_and_within_a_year(self):
        exp = datetime.strptime(self.fields["Expires"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        days = (exp - datetime.now(timezone.utc)).days
        self.assertGreater(days, 14, "security.txt expires soon: renew it (RFC 9116)")
        self.assertLess(days, 366)

    def test_policy_points_at_a_real_section(self):
        url, _, frag = self.fields["Policy"].partition("#")
        self.assertEqual(url, ORIGIN + "/security/")
        page = read_site("security/index.html")
        self.assertIn('id="%s"' % frag, page)
        self.assertIn("Reporting a security problem", page)
        self.assertIn("/.well-known/security.txt", page)
        self.assertIsNone(EMOJI.search(page))
        self.assertIsNone(re.search(r'<[^>]+\sstyle="', page))


if __name__ == "__main__":
    unittest.main()
