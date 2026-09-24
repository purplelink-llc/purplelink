#!/usr/bin/env python3
"""
Write site/tools/abstract-checker/venues.json from the Journal Pack's rule
library (backend/latextools/journals.py), so the free Abstract Checker shows
the same limits the paid check applies and the two cannot drift apart.

Usage:
    python3 scripts/gen_venue_json.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from latextools.journals import JOURNAL_SPECS  # noqa: E402

FIELDS = ("name", "domain", "abstract_max_words", "manuscript_max_words", "manuscript_max_pages",
          "required_sections", "recommended_sections", "reference_style_hint",
          "anonymous_submission", "notes", "sources")


def main() -> int:
    venues = [dict({"key": key}, **{f: spec.get(f) for f in FIELDS}) for key, spec in JOURNAL_SPECS.items()]
    out = ROOT / "site" / "tools" / "abstract-checker" / "venues.json"
    out.write_text(json.dumps(venues, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"venues: {len(venues)} written to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
