#!/usr/bin/env python3
"""Event detection for the social pipeline. This script no longer posts anything.

PR 219 built a second posting path here. On 2026-10-18 it was consolidated: the ONE posting path is
backend/scripts/social.py (socialpost.engine and its adapters), fed by the daily ranked pipeline
(backend/socialpost/daily, docs/social-posting.md). What stays of PR 219 is its detection library:

  events.py   reads the live sitemap, product pages, changelog and YouTube; facts only from the live page
  core.py     HTTP, wording helpers, house-voice checks

  poster.py scan     print the new guides, releases and videos on the live site since the last scan (read only;
                     it writes nothing to any queue and never posts)

Every other former command (run, status, whoami, refresh) is retired and exits 2 with a pointer.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import events  # noqa: E402
from core import Http  # noqa: E402

RETIRED = ("run", "status", "whoami", "refresh")
POINTER = ("scripts/social/poster.py no longer posts. Use backend/scripts/social.py (daily run --dry-run, status, "
           "whoami, refresh). See docs/social-posting.md.")


def cmd_scan(http) -> int:
    """Read only, for debugging detection: count what the live site shows. Writes no state, queue or post."""
    state = {"seeded": False, "seen": {"guides": [], "releases": {}, "videos": []}}
    found, notes = events.scan(http, state, seed=True)
    for n in notes:
        print(f"note: {n}")
    print(f"{len(state['seen']['guides'])} guides, {len(state['seen']['releases'])} products, "
          f"{len(state['seen']['videos'])} videos live; nothing written, nothing posted")
    return 0


def main(argv=None, http=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("scan",) + RETIRED)
    ap.add_argument("rest", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd in RETIRED:
        print(POINTER)
        return 2
    return cmd_scan(http or Http())


if __name__ == "__main__":
    sys.exit(main())
