"""Versions answer engines read (llms.txt, JSON-LD, launch.js) must agree with each other.

Each release changes a product page; this keeps llms.txt and pricing.md from keeping the old number.
"""
import re
import unittest

from common import SITE, jsonld_blocks, read_site, walk

# product page slug -> name of its "### <name> (...)" section in llms.txt
PRODUCTS = {
    "moderntex": "ModernTex",
    "outbound-veil": "Outbound Veil",
    "legroom": "Legroom",
    "keyfeel": "Keyfeel",
    "tapefolio": "Tapefolio",
    "panely": "Panely",
    "summonly": "Summonly",
    "batterymeter": "BatteryMeter",
    "vitae": "Vitae",
    "globepin": "GlobePin",
}

# Mac apps sold or given away from purplelink.llc that need a row in pricing.md
PRICING_ROWS = ["ModernTex", "Outbound Veil", "Legroom", "Keyfeel", "Tapefolio", "Panely", "Summonly", "BatteryMeter", "Mac Suite", "Vitae"]


def page_version(slug):
    text = read_site(f"{slug}/index.html")
    for block in jsonld_blocks(text):
        for d in walk(block):
            if d.get("@type") == "SoftwareApplication" and d.get("softwareVersion"):
                return str(d["softwareVersion"])
    return None


def llms_section(name):
    text = read_site("llms.txt")
    m = re.search(r"^### %s \([^)]*\)\n(.*?)(?=^### |^## )" % re.escape(name), text, re.S | re.M)
    return m.group(1) if m else None


class VersionConsistency(unittest.TestCase):
    def test_every_product_page_states_a_version(self):
        missing = [slug for slug in PRODUCTS if page_version(slug) is None]
        self.assertEqual(missing, [], "SoftwareApplication JSON-LD without softwareVersion")

    def test_llms_txt_names_the_page_version(self):
        bad = []
        for slug, name in PRODUCTS.items():
            ver = page_version(slug)
            section = llms_section(name)
            self.assertIsNotNone(section, f"no llms.txt section for {name}")
            status = "\n".join(l for l in section.splitlines() if l.startswith("- **Status:**"))
            if not re.search(r"(?<![\d.])%s(?![\d])" % re.escape(ver), status):
                bad.append(f"{name}: page {ver}, llms.txt status {status.strip() or '(none)'}")
        self.assertEqual(bad, [])

    def test_launch_js_matches_json_ld(self):
        for slug in ("panely", "summonly"):
            js = (SITE / slug / "launch.js").read_text(encoding="utf-8")
            m = re.search(r'^\s*version: "([^"]*)"', js, re.M)
            self.assertIsNotNone(m)
            self.assertEqual(m.group(1), page_version(slug), f"{slug}: launch.js vs JSON-LD")

    def test_guides_state_the_current_version(self):
        # A guide sentence "<product> ... current version is X" must name the page version; the
        # transcription guide kept Tapefolio 1.0.1 for days after 1.1.0 shipped.
        names = {name: slug for slug, name in PRODUCTS.items()}
        bad = []
        for page in sorted((SITE / "guides").glob("*/index.html")):
            text = re.sub(r"<[^>]+>", " ", page.read_text(encoding="utf-8"))
            for m in re.finditer(r"current version is (\d+(?:\.\d+)+)", text):
                before = text[max(0, m.start() - 600):m.start()]
                hits = [(before.rfind(n), n) for n in names if before.rfind(n) >= 0]
                if not hits:
                    continue
                name = max(hits)[1]
                if m.group(1) != page_version(names[name]):
                    bad.append(f"{page.parent.name}: {name} {m.group(1)}, page {page_version(names[name])}")
        self.assertEqual(bad, [])

    def test_pricing_md_has_a_row_for_each_mac_app(self):
        rows = {l.split("|")[1].strip() for l in read_site("pricing.md").splitlines() if l.startswith("| ")}
        self.assertEqual([n for n in PRICING_ROWS if n not in rows], [])


if __name__ == "__main__":
    unittest.main()
