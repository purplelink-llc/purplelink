#!/usr/bin/env python3
"""Stamp a content hash onto every local CSS/JS and Purplelink logo reference in site/*.html.

Root CSS and JS are served from stable paths, so a browser holding an old copy
kept it until the cache expired: a fix could sit live and unseen for a day. Each
reference now carries ?v=<hash of the file's bytes>, which makes every changed
asset a new URL and lets the assets themselves be cached hard and forever. The
HTML is revalidated on each load (max-age=0, must-revalidate), so a deploy
reaches people as soon as they load a page.

The committed tree is bare: since 2026-11-02 (docs/designs/generated-files-at-build.md, phase 2) the pages in git
carry no ?v= stamps, so two branches that touch styles.css no longer conflict on the stamp line of 400 pages. The
stamps are added only in throwaway build checkouts: the Netlify build (NETLIFY=true), GitHub Actions (CI=true) and
scripts/deploy.sh (--force-in-place, which restores site/ afterwards). Stamping anywhere else exits 2.

Idempotent: unchanged assets produce identical output. Run from anywhere; paths resolve against the repo root.

  python3 scripts/fingerprint_assets.py                  # stamp in place (build checkouts only)
  python3 scripts/fingerprint_assets.py --force-in-place # stamp in place anyway (deploy.sh)
  python3 scripts/fingerprint_assets.py --check          # exit 1 if any stamp is missing or stale (a built tree)
  python3 scripts/fingerprint_assets.py --strip          # remove every stamp (the committed form)
  python3 scripts/fingerprint_assets.py --check-bare [FILE ...]  # exit 1 if a file carries a stamp (CI, pre-commit)
"""
from __future__ import annotations

import hashlib
import os
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

# href/src pointing at a .css or .js, or at the Purplelink mark, logo or lockup, with an optional existing query string.
# The mark and logo sit under /assets/*, which netlify.toml caches for 30 days; without a stamp the new mark
# (2026-10-29) stayed hidden behind every returning visitor's cached copy.
REF = re.compile(r'((?:href|src)=")([^"?\s]+\.(?:css|js)|[^"?\s]*purplelink-(?:mark|logo|lockup)[^"?\s/]*\.(?:svg|png))(\?[^"]*)?(")')
EXTERNAL = ("http://", "https://", "//", "data:", "blob:")

# url() references to the logo files inside root stylesheets. The header wordmark is a CSS mask
# (styles.css .brand > span); stamping the stylesheet alone does not refresh a file it links to by a fixed path.
# The CSS pass runs before the HTML pass, so each stylesheet's own hash covers the stamps written into it.
CSS_REF = re.compile(r'(url\(")(/assets/purplelink-(?:mark|logo|lockup|wordmark)[^"?\s/]*\.(?:svg|png))(\?[^"]*)?("\))')

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


def process_css(css_file: Path, write: bool) -> int:
    original = css_file.read_text()

    def sub(m: re.Match) -> str:
        open_, url, _old_query, close = m.groups()
        target = SITE / url.lstrip("/")
        if not target.is_file():
            print(f"  warn: {css_file.relative_to(ROOT)} -> {url} (no such file, left alone)", file=sys.stderr)
            return m.group(0)
        return f"{open_}{url}?v={asset_hash(target)}{close}"

    updated = CSS_REF.sub(sub, original)
    if updated == original:
        return 0
    if write:
        css_file.write_text(updated)
    return 1


BARE_HELP = """The committed tree carries no ?v= stamps; the Netlify build adds them (docs/designs/generated-files-at-build.md).
To fix: python3 scripts/fingerprint_assets.py --strip, then commit. When merging origin/main into an old branch,
take main's side for stamp-only lines and run --strip."""

STAMP_Q = re.compile(r"\?v=[0-9a-f]+$")


def strip_text(text: str, css: bool) -> str:
    """The text with ?v=<hash> removed from every reference the stamper writes (local ones only)."""
    def sub(m: re.Match) -> str:
        head, url, query, close = m.groups()
        if url.startswith(EXTERNAL) or not query or not STAMP_Q.fullmatch(query):
            return m.group(0)
        return f"{head}{url}{close}"
    return (CSS_REF if css else REF).sub(sub, text)


def targets(args: list[str]) -> tuple[list[Path], list[Path]]:
    """(html, css) files to look at: the named files under site/, or the whole tree."""
    if args:
        paths = [(ROOT / a).resolve() for a in args]
        paths = [p for p in paths if p.is_file() and SITE.resolve() in p.parents]
        html = [p for p in paths if p.suffix == ".html"]
        css = [p for p in paths if p.suffix == ".css" and p.parent == SITE.resolve()]
    else:
        html = sorted(SITE.rglob("*.html"))
        css = sorted(SITE.glob("*.css"))
    return [f for f in html if not any(d.resolve() in f.parents for d in SKIP_DIRS)], css


def strip_or_check_bare(write: bool, args: list[str]) -> int:
    html, css = targets(args)
    stamped = []
    for f in css + html:
        text = f.read_text()
        bare = strip_text(text, css=f.suffix == ".css")
        if bare != text:
            stamped.append(f)
            if write:
                f.write_text(bare)
    if write:
        print(f"fingerprint: stripped stamps from {len(stamped)} of {len(html) + len(css)} files")
        return 0
    if stamped:
        for f in stamped[:20]:
            print(f"  stamped: {f.relative_to(ROOT)}", file=sys.stderr)
        if len(stamped) > 20:
            print(f"  ... and {len(stamped) - 20} more", file=sys.stderr)
        print(BARE_HELP, file=sys.stderr)
        return 1
    print(f"fingerprint: {len(html) + len(css)} files bare")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--strip" in args or "--check-bare" in args:
        return strip_or_check_bare(write="--strip" in args, args=[a for a in args if not a.startswith("--")])
    check = "--check" in args
    in_build = os.environ.get("NETLIFY") == "true" or os.environ.get("CI") == "true" or "--force-in-place" in args
    if not check and not in_build:
        print("fingerprint: not stamping a working tree. " + BARE_HELP.split("\n", 1)[0] + "\n"
              "Stamping happens in the Netlify build and CI; scripts/deploy.sh passes --force-in-place.", file=sys.stderr)
        return 2
    # One-time escape hatch for the backfill that first stamped the pages the
    # cron had already written. backend/digest/publisher.py stamps everything it
    # writes from now on, so routine deploys should never need this.
    if "--include-digest" in args:
        SKIP_DIRS.clear()
    files = [f for f in sorted(SITE.rglob("*.html"))
             if not any(d in f.parents for d in SKIP_DIRS)]
    css_changed = sum(process_css(f, write=not check) for f in sorted(SITE.glob("*.css")))
    _hashes.clear()  # stylesheets may have just changed; hash them afresh for the HTML pass
    changed = css_changed + sum(process(f, write=not check) for f in files)
    verb = "stale" if check else "updated"
    print(f"fingerprint: {changed} of {len(files)} files {verb}; "
          f"{len(_hashes)} distinct assets hashed")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
