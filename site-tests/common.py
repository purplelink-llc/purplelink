"""Shared helpers for the site tests. Stdlib only; everything reads checked-in files, no network."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = "https://purplelink.llc"

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF\U00002B50\U00002B55\U0000FE0F\U0000200D]"
)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def read_site(rel):
    return (SITE / rel).read_text(encoding="utf-8")


def page_of(url_path):
    """/guides/x/ -> site/guides/x/index.html"""
    return SITE / url_path.strip("/") / "index.html"


def meta(text, key):
    """Content of <meta property|name=key content=...>, unescaped, or None."""
    for m in re.finditer(r"<meta\b[^>]*>", text):
        tag = m.group(0)
        k = re.search(r'\b(?:property|name)="([^"]*)"', tag)
        c = re.search(r'\bcontent="([^"]*)"', tag)
        if k and c and k.group(1) == key:
            return html.unescape(c.group(1))
    return None


def canonical(text):
    for m in re.finditer(r"<link\b[^>]*>", text):
        tag = m.group(0)
        if re.search(r'\brel="canonical"', tag):
            h = re.search(r'\bhref="([^"]*)"', tag)
            return h.group(1) if h else None
    return None


def jsonld_blocks(text):
    """Parsed JSON-LD blocks; raises ValueError naming the block if one does not parse."""
    out = []
    for i, m in enumerate(re.finditer(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)):
        try:
            out.append(json.loads(m.group(1)))
        except ValueError as e:
            raise ValueError(f"JSON-LD block {i} does not parse: {e}")
    return out


def walk(obj):
    """Every dict nested in a JSON value."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def has_noindex(text):
    r = meta(text, "robots")
    return bool(r and "noindex" in r.lower())


def main_text(text):
    """Visible text of <main> (or the body): scripts, styles and tags removed, entities unescaped."""
    m = re.search(r"<main\b.*?</main>", text, re.S)
    body = m.group(0) if m else text
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return html.unescape(body)


def sitemap_locs():
    return re.findall(r"<loc>\s*([^<]+?)\s*</loc>", read_site("sitemap.xml"))


def sitemap_paths():
    return {u[len(ORIGIN):] for u in sitemap_locs() if u.startswith(ORIGIN)}
