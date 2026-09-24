#!/usr/bin/env python3
"""Fail if any page's og:image or twitter:image points at a file not in site/.

Six paid tool pages once shipped pointing at share cards that were never
generated, so every link to them in Slack, email or social showed no image.
A missing card fell through to the 404 rule silently; this makes it loud.

Usage: python3 scripts/check_og_images.py
"""
import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent / "site"
PATTERN = re.compile(
    r'<meta\s+(?:property|name)="(?:og:image|twitter:image)"\s+content="https://purplelink\.llc/([^"]+)"'
)


def main() -> int:
    missing: dict[str, list[str]] = {}
    for page in sorted(SITE.rglob("*.html")):
        for rel in PATTERN.findall(page.read_text(encoding="utf-8", errors="replace")):
            if not (SITE / rel).is_file():
                missing.setdefault(rel, []).append(str(page.relative_to(SITE)))
    if not missing:
        print("share images: all present")
        return 0
    for rel, pages in missing.items():
        print(f"MISSING {rel}  (used by {len(pages)}: {', '.join(pages[:3])}{' ...' if len(pages) > 3 else ''})")
    print("Generate them with site/assets/og/_gen.html?t=<key> at 1200x630.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
