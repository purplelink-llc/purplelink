import re
import unittest
from common import read_site


class BuyProof(unittest.TestCase):
    def test_buy_proof_paragraph(self):
        text = read_site("outbound-veil/index.html")
        m = re.search(r'<p\b[^>]*class="[^"]*\bbuy-proof\b[^"]*"[^>]*>(.*?)</p>', text, re.S)
        self.assertIsNotNone(m, "no p.buy-proof")
        body = m.group(1)
        self.assertIn("ChatGPT", body)
        self.assertIn("claude.ai", body)
        self.assertIn('href="/outbound-veil/works-in/"', body)
        self.assertIn('href="/guides/before-you-paste-client-notes-into-chatgpt/"', body)
