#!/usr/bin/env python3
"""Switch a new Mac app's pages on, on release day.

    python3 scripts/go-live-app.py panely 1.0.0 4 2026-10-20

Run it AFTER the release is published to the app's Blobs store (scripts/publish-release.sh in the app repo) and the
update token and license key secrets are set on Netlify. It does the five things that make the page real:
  1. site/<slug>/launch.js: live true, with the version, the disk image size in whole MB and the release date;
  2. site/<slug>/index.html: robots "index, follow", and the offer availability InStock;
  3. site/sitemap.xml: lists /<slug>/ (success pages are never listed);
  4. restamps asset versions (scripts/fingerprint_assets.py);
  5. prints the checks to run next.
Idempotent. It does not touch checkout, the webhook or the Suite: those are in the launch-day commit it ships with.
"""
import re, subprocess, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLUGS = ("panely", "summonly")

def main(argv):
    if len(argv) != 5 or argv[1] not in SLUGS:
        sys.exit(__doc__)
    slug, version, size, released = argv[1:]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version): sys.exit("version must be x.y.z")
    if not re.fullmatch(r"\d{1,4}", size): sys.exit("size must be whole megabytes")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", released): sys.exit("released must be YYYY-MM-DD")
    site = ROOT / "site"

    lj = site / slug / "launch.js"; s = lj.read_text()
    s, n = re.subn(r"window\.[A-Z]+_LAUNCH = \{.*?\};", f'window.{slug.upper()}_LAUNCH = {{\n  live: true,\n  version: "{version}",\n  sizeMb: "{size}",\n  released: "{released}"\n}};', s, count=1, flags=re.S)
    if n != 1: sys.exit("could not find the launch switch in launch.js")
    lj.write_text(s)

    page = site / slug / "index.html"; h = page.read_text()
    h = h.replace('<meta name="robots" content="noindex, follow">', '<meta name="robots" content="index, follow">')
    h = h.replace('"availability": "https://schema.org/PreOrder"', '"availability": "https://schema.org/InStock"')
    h = re.sub(r"<!-- LAUNCH CHECKLIST.*?-->\n", "", h, count=1, flags=re.S)
    # The static HTML goes live too, so the page is right with scripts off. The tags below are the ones launch.js switches.
    pf = {"panely": "pf", "summonly": "lf"}[slug]
    def gated(m):
        tag = m.group(0)
        href = re.search(rf'data-{pf}-href="([^"]+)"', tag).group(1)
        text = re.search(rf'data-{pf}-live-text="([^"]+)"', tag).group(1)
        tag = tag.replace(' aria-disabled="true"', f' href="{href}"')
        return re.sub(r">[^<]*</a>$", f">{text}</a>", tag)
    h = re.sub(rf'<a\b[^>]*data-{pf}-gated[^>]*>[^<]*</a>', gated, h)
    h = re.sub(r'(<button\b[^>]*id="checkout-btn"[^>]*?) disabled', r"\1", h)
    h = re.sub(rf'\s*<span class="product-status product-status-soon" data-{pf}-pre-only>[^<]*</span>', "", h)
    h = re.sub(rf'(data-{pf}-live-only) hidden', r"\1", h)
    nice = date.fromisoformat(released).strftime("%B %-d, %Y")
    h = re.sub(rf'(data-{pf}-facts>)[^<]*(</p>)', lambda m: f'{m.group(1)}Version {version}, released {nice}. {size} MB disk image.{m.group(2)}', h)    # also replaces an older version's text
    page.write_text(h)

    sm = site / "sitemap.xml"; x = sm.read_text()
    if f"<loc>https://purplelink.llc/{slug}/</loc>" not in x:
        entry = f"  <url>\n    <loc>https://purplelink.llc/{slug}/</loc>\n    <lastmod>{released}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.9</priority>\n  </url>\n"
        x = x.replace("</urlset>", entry + "</urlset>", 1) if "</urlset>" in x else sys.exit("no </urlset> in sitemap.xml")
        sm.write_text(x)

    subprocess.run([sys.executable, str(ROOT / "scripts" / "fingerprint_assets.py")], check=True)
    print(f"{slug} {version} is switched on in the files. Next: node --experimental-test-module-mocks --test netlify/tests/*.test.mjs; "
          f"python3 -m unittest discover -s site-tests; then merge, and verify https://purplelink.llc/{slug}/ and a 100%-off test purchase.")

if __name__ == "__main__":
    main(sys.argv)
