#!/usr/bin/env python3
"""Window-only captures for the still-driven promos (Playwright, local files and the
locally served site only; every non-local request is blocked).

    python3 capture.py            # writes video/.cache/captures/*.png and geometry.json

- paper-review: full-page capture of /tools/paper-review/ at 1440 wide, 2x, compare table open.
- products: full-page capture of /products/ at 1440 wide, 2x.
- sub-N: the extension's store mockups with invented names, browser bar and callouts removed.
- sub-popup: the extension's own popup.html rendered at 3x.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / ".cache" / "captures"
OUT.mkdir(parents=True, exist_ok=True)
SITE = "http://127.0.0.1:8765"
EXT = Path("/Volumes/Extreme SSD/Chrome Scholar Extension")

# Invented people (the same fictional researcher set the Vitae screenshots use).
RENAMES = [
    ("Hsinchun Chen", "Maya Okafor"),
    ("Regents Professor, New York University", "Assistant Professor, Northfield University"),
    ("Benjamin M. Ampel", "Grace Liu"),
    ("Sagar Samtani", "Aiko Tanaka"),
    ("Ben Lazarine", "Daniel Reyes"),
    ("Herbert Simon", "Anna Lindqvist"),
    ("Harry Pople", "Rafael Castellanos"),
    ("Vasant Dhar", "Joseph Mbeki"),
    ("B Ampel, S Samtani, H Chen", "M Okafor, T Kowal, L Hoffmeister"),
    ("H Chen, S Samtani", "M Okafor, T Kowal"),
    ("H Chen, B Ampel", "M Okafor, L Hoffmeister"),
    ("S Samtani, H Chen", "T Kowal, M Okafor"),
    ("B Ampel, S Samtani", "L Hoffmeister, A Tanaka"),
    ("V Dhar", "R Okonkwo"),
    ("A Rai", "D Reyes"),
    ("X Author", "P Venkataraman"),
    ("A Survey of Large Language Models", "Large language models in information systems: a survey"),
    ("W Zhao, K Zhou…", "M Okafor, T Kowal"),
    ("LLaMA: Open and Efficient Foundation Language Models", "Open foundation models for tabular research data"),
    ("H Touvron…", "L Hoffmeister, G Liu"),
    ("GPT-4 Technical Report", "Retrieval-augmented screening for systematic reviews"),
    ("OpenAI - arXiv preprint, 2023", "D Reyes, A Tanaka - arXiv preprint, 2025"),
]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]\s?")


def block_external(page):
    def route(r):
        u = r.request.url
        if u.startswith(SITE) or u.startswith("file://") or u.startswith("data:"):
            r.continue_()
        else:
            r.abort()
    page.route("**/*", route)


def geometry(page, selectors):
    g = {}
    for name, sel in selectors.items():
        box = page.evaluate(
            """(sel) => { const el = document.querySelector(sel); if (!el) return null;
                 const r = el.getBoundingClientRect(); return { y: r.top + window.scrollY, h: r.height, x: r.left, w: r.width }; }""",
            sel,
        )
        g[name] = box
    g["pageHeight"] = page.evaluate("document.documentElement.scrollHeight")
    return g


def main():
    geo = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="light")
        page = ctx.new_page()
        block_external(page)
        page.add_style_tag  # noqa

        # ---- Paper Review -------------------------------------------------------------------
        page.goto(f"{SITE}/tools/paper-review/", wait_until="load")
        page.evaluate("document.querySelector('details.pr-compare') && (document.querySelector('details.pr-compare').open = true)")
        page.add_style_tag(content="*{animation:none!important;transition:none!important} .adsbygoogle,ins,.ad-slot{display:none!important} .skip-link{display:none!important}")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "paper-review.png"), full_page=True)
        geo["paper-review"] = geometry(page, {
            "h1": "h1", "tiers": ".pr-tiers, .tier-cards, .tiers", "compare": "details.pr-compare table",
            "sample": ".pr-sample, details[open] .sample-report", "sampleDetails": "main details[open]",
            "how": "#how, .pr-how, section.how", "handled": "#handling, .pr-handling",
        })
        print("paper-review", json.dumps(geo["paper-review"]))

        # ---- Products page --------------------------------------------------------------------
        page.goto(f"{SITE}/products/", wait_until="load")
        page.add_style_tag(content="*{animation:none!important;transition:none!important} .skip-link{display:none!important}")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "products.png"), full_page=True)
        geo["products"] = geometry(page, {
            "hero": ".catalog-hero", "chooser": ".catalog-chooser", "moderntex": ".catalog-feature", "mac": "section[aria-labelledby=cat-mac]",
            "review": "section[aria-labelledby=cat-review]", "free": "section[aria-labelledby=cat-free]", "ios": "section[aria-labelledby=cat-ios]",
        })
        print("products", json.dumps(geo["products"]))

        # ---- Extension mockups (sanitized copy) ------------------------------------------------
        src = (EXT / "store-assets" / "screenshots.html").read_text()
        for a, z in RENAMES:
            src = src.replace(a, z)
        src = EMOJI.sub("", src)
        for leak in ["Ampel", "Samtani", "Chen", "Lazarine", "Hinton", "Zhao", "Touvron", "OpenAI"]:
            assert leak not in src, f"unsanitized: {leak}"
        san = OUT / "sub-mockups.html"
        san.write_text(src)
        ctx2 = b.new_context(viewport={"width": 1400, "height": 900}, device_scale_factor=2, color_scheme="light")
        pg = ctx2.new_page()
        block_external(pg)
        pg.goto(san.as_uri())
        pg.add_style_tag(content=".browser-bar,.feature-strip,.callout{display:none!important} .scholar-body{height:100%!important} .lineage-panel{top:0!important;height:100%!important} .screenshot{height:756px!important}")
        pg.wait_for_timeout(300)
        for i in range(1, 6):
            pg.locator(f"#ss{i}").screenshot(path=str(OUT / f"sub-{i}.png"))
        print("sub mockups done")

        # ---- Extension popup ------------------------------------------------------------------
        ctx3 = b.new_context(viewport={"width": 320, "height": 420}, device_scale_factor=3, color_scheme="light")
        pp = ctx3.new_page()
        block_external(pp)
        pp.goto((EXT / "src" / "popup" / "popup.html").as_uri())
        pp.wait_for_timeout(300)
        pp.evaluate("""() => { document.getElementById('savedCount').textContent = '12';
            for (const id of ['showQualityBadges','showRetractionWatch','showHoverSummary']) document.getElementById(id).checked = true; }""")
        h = pp.evaluate("document.body.scrollHeight")
        pp.set_viewport_size({"width": 320, "height": h})
        pp.screenshot(path=str(OUT / "sub-popup.png"))
        print("popup", h)
        b.close()
    (OUT / "geometry.json").write_text(json.dumps(geo, indent=1))


if __name__ == "__main__":
    main()
