#!/usr/bin/env python3
"""Stamp a content hash onto every local CSS/JS reference in site/*.html.

Root CSS and JS are served from stable paths, so a browser holding an old copy
kept it until the cache expired: a fix could sit live and unseen for a day. Each
reference now carries ?v=<hash of the file's bytes>, which makes every changed
asset a new URL and lets the assets themselves be cached hard and forever. The
HTML is revalidated on each load (max-age=0, must-revalidate), so a deploy
reaches people as soon as they load a page.

Idempotent: unchanged assets produce identical output, so it is safe to run on
every deploy. Run from anywhere; paths resolve against the repo root.

  python3 scripts/fingerprint_assets.py           # rewrite in place
  python3 scripts/fingerprint_assets.py --check   # exit 1 if anything is stale
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
HASH_LEN = 10

# site/blog/digest/ is written and committed by the Modal cron, not from here;
# a pre-commit hook refuses those paths, and the next cron run would overwrite
# any stamp we added. Those pages keep bare /styles.css, /site.js,
# /analytics.js and /ethicalads.js, which is why netlify.toml leaves exactly
# those four paths on a refreshable cache instead of making them immutable.
SKIP_DIRS = {SITE / "blog" / "digest"}

# href/src pointing at a .css or .js, with an optional existing query string.
REF = re.compile(r'((?:href|src)=")([^"?\s]+\.(?:css|js))(\?[^"]*)?(")')
EXTERNAL = ("http://", "https://", "//", "data:", "blob:")

_hashes: dict[Path, str] = {}


def asset_hash(path: Path) -> str:
    if path not in _hashes:
        _hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()[:HASH_LEN]
    return _hashes[path]


def resolve(url: str, html_file: Path) -> Path | None:
    """The file on disk a reference points at, or None if it isn't ours."""
    if url.startswith(EXTERNAL):
        return None
    target = SITE / url.lstrip("/") if url.startswith("/") else html_file.parent / url
    try:
        target = target.resolve()
        target.relative_to(SITE.resolve())
    except (ValueError, OSError):
        return None  # escapes site/, don't touch it
    return target if target.is_file() else None


def process(html_file: Path, write: bool) -> int:
    original = html_file.read_text()
    misses: list[str] = []

    def sub(m: re.Match) -> str:
        attr, url, _old_query, close = m.groups()
        target = resolve(url, html_file)
        if target is None:
            if not url.startswith(EXTERNAL):
                misses.append(url)
            return m.group(0)
        return f"{attr}{url}?v={asset_hash(target)}{close}"

    updated = REF.sub(sub, original)
    for miss in misses:
        print(f"  warn: {html_file.relative_to(ROOT)} -> {miss} (no such file, left alone)",
              file=sys.stderr)
    if updated == original:
        return 0
    if write:
        html_file.write_text(updated)
    return 1


def main() -> int:
    check = "--check" in sys.argv
    files = [f for f in sorted(SITE.rglob("*.html"))
             if not any(d in f.parents for d in SKIP_DIRS)]
    changed = sum(process(f, write=not check) for f in files)
    verb = "stale" if check else "updated"
    print(f"fingerprint: {changed} of {len(files)} html files {verb}; "
          f"{len(_hashes)} distinct assets hashed")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
