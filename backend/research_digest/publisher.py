"""Write the weekly roundup into a local checkout of the site repo.

Option-B publishing: the Modal job clones the getmuscleonglp.com repo, calls
write_into() to render the post + rebuild the hub + update the manifest and
sitemap on disk, then commits and deploys the whole directory via the Netlify
CLI (which bundles the functions). No Netlify git-connection / Pro plan needed,
and the repo stays private.
"""
from __future__ import annotations

import json
import os
import re

from .models import WeeklyDigest
from .renderer import render_post_html, render_hub_html, post_url

MANIFEST_REL = "research/index.json"
HUB_URL = "https://getmuscleonglp.com/research/"


def bump_lastmod(xml: str, loc: str, date: str) -> str:
    """Set the <lastmod> of the sitemap entry for *loc* to *date*, if it has one.

    Adding a URL once is not enough for a hub page: /research/ changes every
    week, but its lastmod sat at 2026-08-22 because nothing ever updated it.
    """
    pattern = re.compile(r"(<loc>" + re.escape(loc) + r"</loc>\s*<lastmod>)[^<]*(</lastmod>)")
    return pattern.sub(lambda m: m.group(1) + date + m.group(2), xml, count=1)


def _url_block(loc: str, date: str, freq: str, prio: str) -> str:
    return (f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{date}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>\n")


def _sitemap_add(xml: str, slug: str, date: str) -> str:
    additions = []
    if f"{HUB_URL}</loc>" not in xml:
        additions.append(_url_block(HUB_URL, date, "weekly", "0.9"))
    else:
        xml = bump_lastmod(xml, HUB_URL, date)
    post = post_url(slug)
    if post not in xml:
        additions.append(_url_block(post, date, "monthly", "0.7"))
    return xml.replace("</urlset>", "".join(additions) + "</urlset>") if additions else xml


def write_into(site_dir: str, digest: WeeklyDigest) -> list[dict]:
    """Render the digest into a checkout at site_dir. Returns the manifest."""
    mpath = os.path.join(site_dir, MANIFEST_REL)
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else []
    manifest = [m for m in manifest if m.get("slug") != digest.slug]
    blurb = (digest.items[0].summary if digest.items else digest.intro)[:180]
    manifest.insert(0, {"slug": digest.slug, "week_label": digest.week_label,
                        "date": digest.date, "count": digest.count, "blurb": blurb})
    manifest.sort(key=lambda m: m["date"], reverse=True)

    post_dir = os.path.join(site_dir, "research", digest.slug)
    os.makedirs(post_dir, exist_ok=True)
    with open(os.path.join(post_dir, "index.html"), "w") as f:
        f.write(render_post_html(digest))
    with open(os.path.join(site_dir, "research", "index.html"), "w") as f:
        f.write(render_hub_html(manifest))
    with open(mpath, "w") as f:
        f.write(json.dumps(manifest, indent=2))

    smp = os.path.join(site_dir, "sitemap.xml")
    if os.path.exists(smp):
        xml = open(smp).read()
        new = _sitemap_add(xml, digest.slug, digest.date)
        if new != xml:
            open(smp, "w").write(new)
    return manifest
