#!/usr/bin/env python3
"""Per-page social cards (1200x630 JPEG) for the pages that share a generic card.

Pages covered: /format/references-for-*/, the guides and the blog posts whose og:image is still
assets/og/purplelink-card.png or assets/og/brand.png. Each gets site/assets/og/cards/<section>-<slug>.jpg: a
background from site/assets/og/bg/ (made with ChatGPT, no text in the image), the page title in Fraunces, and the
brand mark. The page's og:image and twitter:image tags are rewritten to point at it.

Rendering: scripts/og-card.html in headless Chrome over a local server rooted at the repo.

  python3 scripts/gen_og_cards.py            # render and rewrite
  python3 scripts/gen_og_cards.py --dry-run  # list what would change
  python3 scripts/gen_og_cards.py --only blog/starting-purplelink
  python3 scripts/gen_og_cards.py --refresh  # re-render every existing card too
  python3 scripts/gen_og_cards.py --brand    # re-render the two generic brand cards (scripts/og-brand-card.html)
"""
import argparse, html, http.server, re, socketserver, subprocess, sys, threading, urllib.parse
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = SITE / "assets" / "og" / "cards"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = "https://purplelink.llc"
GENERIC = ("purplelink-card.png", "brand.png")

LATEX_WORDS = ("latex", "bibtex", "convert-references", "format-citation", "pdf-to-markdown", "build-bibtex", "csv-to")
BLOG_BG = {
    "travel-photographs-as-prints": "photography",
    "what-globepin-does-differently": "apps", "why-haea-is-on-device": "apps", "tikz-and-tables-without-the-syntax": "apps",
    "the-latex-editor-academics-want": "apps", "the-co-author-who-writes-in-word": "apps",
    "both-bugs-had-the-same-symptom-zero": "latex", "the-comment-said-this-would-break": "latex",
    "forward-and-inverse-search-arent-mirror-images": "latex", "pdf-to-llm-without-losing-the-math": "latex",
    "what-openalex-returns-when-you-ask-for-an-abstract": "latex", "where-bibtex-errors-actually-come-from": "latex",
    "one-curation-call-per-day": "latex", "detecting-checkout-without-a-click-handler": "latex",
    "what-counts-as-a-run": "latex", "producing-a-diff-pdf-for-journal-resubmission": "latex",
    "starting-purplelink": "general", "keeping-up-when-your-research-crosses-fields": "general",
}
FOOT = {"format": "Reference formats for journals and conferences", "guides": "Free guides for academic authors",
        "blog": "Notes from a one-person software studio",
        "de/guides": "Kostenlose Anleitungen für Forschende",
        "fr/guides": "Guides gratuits pour les chercheurs", "ja/guides": "研究者のための無料ガイド",
        "zh-cn/guides": "为研究者准备的免费指南"}
KICKER = {"format": "Reference format", "guides": "Guide", "blog": "Blog",
          "de/guides": "Anleitung", "fr/guides": "Guide", "ja/guides": "ガイド", "zh-cn/guides": "指南"}
# Localized guides (2026-10-29). Their cards are named de-guides-<slug>.jpg, and the template draws CJK text with
# the system fonts, since Fraunces and Plus Jakarta Sans are Latin subsets.
SECTIONS = ("format", "guides", "blog", "de/guides", "fr/guides", "ja/guides", "zh-cn/guides")


def meta(t, prop):
    m = re.search(r'<meta (?:property|name)="%s" content="([^"]*)"' % re.escape(prop), t)
    return html.unescape(m.group(1)) if m else None


def title_of(t, section):
    ti = meta(t, "og:title") or ""
    if not ti:
        m = re.search(r"<title>(.*?)</title>", t, re.S)
        ti = html.unescape(m.group(1)).strip() if m else ""
    ti = re.sub(r"\s*[|—-]\s*Purplelink.*$", "", ti).strip()
    return ti


def plan(only=None, refresh=False):
    jobs = []
    for section in SECTIONS:
        for p in sorted((SITE / section).glob("*/index.html")):
            slug = p.parent.name
            if slug == "digest" or (only and f"{section}/{slug}" != only):
                continue
            t = p.read_text(encoding="utf-8", errors="ignore")
            cur = (meta(t, "og:image") or "").rsplit("/", 1)[-1]
            card = f"{section.replace('/', '-')}-{slug}.jpg"
            if cur not in GENERIC and not (refresh and cur == card):
                continue
            title = title_of(t, section)
            sub, bg = "", "research"
            if section == "format":
                venue = re.sub(r"\s+Reference Format.*$", "", title)
                title, sub, bg = f"{venue} references", "BibTeX style, examples and a checker.", "latex"
            elif section.endswith("guides"):
                bg = "latex" if any(w in slug for w in LATEX_WORDS) else "research"
            else:
                bg = BLOG_BG.get(slug, "research")
            jobs.append({"page": p, "section": section, "slug": slug, "title": title, "sub": sub, "bg": bg,
                         "out": OUT / card, "url": f"{BASE}/assets/og/cards/{card}"})
    return jobs


def rewrite(job):
    p = job["page"]
    t = p.read_text(encoding="utf-8")
    url = job["url"]
    t = re.sub(r'(<meta property="og:image" content=")[^"]*(")', r"\g<1>%s\g<2>" % url, t, count=1)
    t = re.sub(r'(<meta name="twitter:image" content=")[^"]*(")', r"\g<1>%s\g<2>" % url, t, count=1)
    if 'property="og:image:width"' not in t:
        t = re.sub(r'(<meta property="og:image" content="[^"]*">)',
                   r'\1\n    <meta property="og:image:width" content="1200">\n    <meta property="og:image:height" content="630">', t, count=1)
    if 'name="twitter:image:alt"' not in t:
        alt = html.escape(job["title"], quote=True)
        t = re.sub(r'(<meta name="twitter:image" content="[^"]*">)', r'\1\n    <meta name="twitter:image:alt" content="%s">' % alt, t, count=1)
    p.write_text(t, encoding="utf-8")


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)
        def log_message(self, *a): pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def render(srv, job):
    q = urllib.parse.urlencode({"t": job["title"], "k": KICKER[job["section"]], "s": job["sub"], "bg": job["bg"], "f": FOOT[job["section"]]})
    url = f"http://127.0.0.1:{srv.server_address[1]}/scripts/og-card.html?{q}"
    png = job["out"].with_suffix(".png")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1200,630",
                    "--force-device-scale-factor=1", "--virtual-time-budget=6000", f"--screenshot={png}", url],
                   check=True, capture_output=True, timeout=90)
    Image.open(png).convert("RGB").save(job["out"], quality=84, optimize=True, progressive=True)
    png.unlink()


# The two generic cards, built around the primary lockup (see docs/brand/logo-usage.md). Their text is fixed here.
BRAND_CARDS = {
    "brand.png": {"k": "Making software that lasts",
                  "s": "Atlanta studio. Native macOS and iOS apps, plus free academic tools.",
                  "f": "No sign-up \u00b7 Files deleted after use"},
    "purplelink-card.png": {"k": "Purplelink LLC",
                            "s": "macOS and iOS apps, applied AI, and free tools for academics.",
                            "f": "No sign-up \u00b7 Files never stored"},
}


def render_brand(srv):
    for name, q in BRAND_CARDS.items():
        url = f"http://127.0.0.1:{srv.server_address[1]}/scripts/og-brand-card.html?{urllib.parse.urlencode(q)}"
        out = SITE / "assets" / "og" / name
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1200,630",
                        "--force-device-scale-factor=1", "--virtual-time-budget=6000", f"--screenshot={out}", url],
                       check=True, capture_output=True, timeout=90)
        Image.open(out).convert("RGB").save(out, optimize=True)
        print(f"wrote {out.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--no-rewrite", action="store_true", help="render the images only")
    ap.add_argument("--refresh", action="store_true",
                    help="also re-render pages that already use their own card (after a brand or template change)")
    ap.add_argument("--brand", action="store_true", help="re-render only the two generic brand cards")
    a = ap.parse_args()
    if a.brand:
        srv = serve()
        render_brand(srv)
        srv.shutdown()
        return
    jobs = plan(a.only, a.refresh)
    print(f"{len(jobs)} pages")
    if a.dry_run:
        for j in jobs:
            print(f"  {j['section']}/{j['slug']}  [{j['bg']}]  {j['title']}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    srv = serve()
    for j in jobs:
        render(srv, j)
        if not a.no_rewrite:
            rewrite(j)
    srv.shutdown()
    print(f"wrote {len(jobs)} cards to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
