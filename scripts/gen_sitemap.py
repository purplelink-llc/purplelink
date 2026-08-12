#!/usr/bin/env python3
"""
Regenerate site/sitemap.xml from what is actually on disk.

Why this exists: the sitemap was maintained by hand, so it drifted. On
2026-08-12 it listed 84 URLs against 116 live pages. Thirty-two pages were
missing, most of them guides, and Search Console reported the worst case
plainly for /guides/word-to-latex/: "No referring sitemaps detected",
"Referring page: None detected", last crawl N/A. A page Google has never
discovered cannot rank at any position, and the git history shows this being
patched by hand more than once ("add the 3 /kits/ pages, missing since
launch"). Generating it removes the class of bug rather than the instance.

What it preserves, because these were tuned deliberately and are not
inferable from the filesystem:

  * <priority> and <changefreq> for any URL already in the sitemap, verbatim.
    Tool and kit pages intentionally carry no <changefreq> (see the commit
    "drop changefreq monthly on tool-page sitemap entries"), and priorities
    vary from 0.5 to 1.0 by intent.

What it excludes:

  * Pages carrying <meta name="robots" ... noindex>: upload, compose, status
    and success pages behind a purchase, plus /stats/. Listing a noindex page
    in a sitemap asks Google to crawl something it is then told to drop.
  * blog/digest/**, which the Modal cron publishes on its own cadence and
    which has never been in this sitemap; it ships an RSS feed instead.
    Including it here would also mean this file needed regenerating every
    time the cron ran.

lastmod comes from the file's last commit date, not today's date. deploy.sh
pings IndexNow for URLs whose lastmod is today, so stamping every page with
the current date would announce the whole site as changed on every deploy.

Usage:
    python3 scripts/gen_sitemap.py            # rewrite site/sitemap.xml
    python3 scripts/gen_sitemap.py --check    # report drift, write nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITEMAP = SITE / "sitemap.xml"
BASE = "https://purplelink.llc/"

EXCLUDE_PREFIXES = ("blog/digest",)
NOINDEX_RE = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*noindex', re.I)

# Defaults for a URL that is not already in the sitemap, by first path segment.
# Chosen to match what that section already uses; None means omit the element.
DEFAULTS: dict[str, tuple[str | None, str]] = {
    "guides":  ("monthly", "0.6"),
    "tools":   (None,      "0.7"),
    "kits":    (None,      "0.8"),
    "blog":    ("never",   "0.7"),
    "format":  ("monthly", "0.5"),
    "":        ("monthly", "0.8"),
}


def git_lastmod(path: Path) -> str:
    """Last commit date for a file, falling back to mtime for uncommitted ones."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        if out:
            return out
    except Exception:                                    # noqa: BLE001
        pass
    return dt.date.fromtimestamp(path.stat().st_mtime).isoformat()


def discover() -> list[str]:
    """Every indexable page URL on disk."""
    urls = []
    for f in sorted(SITE.rglob("index.html")):
        rel = f.relative_to(SITE).parent.as_posix()
        rel = "" if rel == "." else rel
        if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
            continue
        head = f.read_text(encoding="utf-8", errors="ignore")[:4000]
        if NOINDEX_RE.search(head):
            continue
        urls.append(BASE + (rel + "/" if rel else ""))
    return urls


def parse_existing() -> dict[str, dict[str, str]]:
    if not SITEMAP.exists():
        return {}
    xml = SITEMAP.read_text()
    out = {}
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>\s*([^<]+?)\s*</loc>", block)
        if not loc:
            continue
        entry = {}
        for tag in ("lastmod", "changefreq", "priority"):
            m = re.search(rf"<{tag}>\s*([^<]+?)\s*</{tag}>", block)
            if m:
                entry[tag] = m.group(1)
        out[loc.group(1)] = entry
    return out


def build() -> tuple[str, dict[str, list[str]]]:
    existing = parse_existing()
    urls = discover()
    added = [u for u in urls if u not in existing]
    dropped = [u for u in existing if u not in urls]

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        rel = url[len(BASE):].rstrip("/")
        section = rel.split("/")[0] if rel else ""
        prev = existing.get(url, {})
        cf_default, pr_default = DEFAULTS.get(section, ("monthly", "0.6"))
        # Preserve deliberate tuning; only fall back for genuinely new URLs.
        changefreq = prev.get("changefreq", cf_default if url not in existing else None)
        priority = prev.get("priority", pr_default)
        page = SITE / (rel + "/index.html" if rel else "index.html")
        lastmod = git_lastmod(page)

        lines.append("  <url>")
        lines.append(f"    <loc>{url}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        if changefreq:
            lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n", {"added": added, "dropped": dropped, "total": urls}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = ap.parse_args()

    xml, diff = build()
    print(f"  pages on disk (indexable): {len(diff['total'])}")
    print(f"  added:   {len(diff['added'])}")
    for u in diff["added"][:40]:
        print(f"    + {u.replace(BASE, '/')}")
    if len(diff["added"]) > 40:
        print(f"    ... and {len(diff['added']) - 40} more")
    print(f"  dropped: {len(diff['dropped'])}")
    for u in diff["dropped"]:
        print(f"    - {u.replace(BASE, '/')}")

    if args.check:
        drift = len(diff["added"]) + len(diff["dropped"])
        print(f"\n  {'DRIFT' if drift else 'in sync'}: {drift} URL(s) differ")
        return 1 if drift else 0

    SITEMAP.write_text(xml)
    print(f"\n  wrote {SITEMAP.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
