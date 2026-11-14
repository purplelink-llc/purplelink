"""Shared markup blocks (scripts/partials/*.html) stamped into pages by scripts/apply_layout.py.

test_layout_in_sync already fails when a page's copy drifts from the partial. These tests cover the rest: each
partial's stylesheet is linked wherever the partial appears, and the pages that should carry it still do."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
PARTIALS = ROOT / "scripts" / "partials"

# partial name -> stylesheet every page carrying it must link
STYLESHEETS = {"report-pipeline": "/tools/paper-review/pipeline-compare.css"}
EXPECTED = {
    "report-pipeline": {
        "tools/paper-review/index.html",
        "tools/paper-review/confidential-manuscript-review/index.html",
        "tools/paper-review/sample/index.html",
        "publication-suite/index.html",
    },
}
MARK = re.compile(r"<!-- partial:([a-z0-9-]+) -->")


def _carriers():
    found: dict[str, set[str]] = {}
    for f in SITE.rglob("*.html"):
        rel = f.relative_to(SITE).as_posix()
        for name in set(MARK.findall(f.read_text(encoding="utf-8"))):
            found.setdefault(name, set()).add(rel)
    return found


def test_every_partial_has_a_file_and_a_stylesheet():
    for name in _carriers():
        assert (PARTIALS / f"{name}.html").is_file(), f"no scripts/partials/{name}.html"
        assert name in STYLESHEETS, f"add the stylesheet for partial {name} to STYLESHEETS"


def test_carriers_link_the_stylesheet():
    for name, rels in _carriers().items():
        css = STYLESHEETS[name]
        for rel in rels:
            head = (SITE / rel).read_text(encoding="utf-8").split("</head>", 1)[0]
            assert f'href="{css}' in head, f"{rel} carries partial {name} but does not link {css}"


def test_expected_pages_carry_the_partial():
    found = _carriers()
    for name, rels in EXPECTED.items():
        assert rels <= found.get(name, set()), f"partial {name} missing from {sorted(rels - found.get(name, set()))}"
