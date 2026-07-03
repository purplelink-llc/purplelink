"""Regression test for the sitewide Content-Security-Policy in netlify.toml.

CLAUDE.md hard constraint: "Strict CSP: style-src 'self' — no inline styles,
ever." This guards against that policy being weakened (e.g. by a stray
'unsafe-inline' added for third-party ad/script integrations) since the
header in netlify.toml applies to every route, including the paid-tool
upload/status/checkout flow.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NETLIFY_TOML = REPO_ROOT / "netlify.toml"


def _sitewide_csp() -> str:
    text = NETLIFY_TOML.read_text()
    match = re.search(r'Content-Security-Policy = "([^"]*)"', text)
    assert match, "Content-Security-Policy header not found in netlify.toml"
    return match.group(1)


def test_netlify_toml_exists():
    assert NETLIFY_TOML.is_file()


def test_style_src_has_no_unsafe_inline():
    csp = _sitewide_csp()
    directives = {
        d.strip().split()[0]: d.strip()
        for d in csp.split(";")
        if d.strip()
    }
    assert "style-src" in directives, "style-src directive missing from CSP"
    assert directives["style-src"] == "style-src 'self'", (
        "style-src must remain 'self' only (no 'unsafe-inline') per "
        f"CLAUDE.md's hard constraint; got: {directives['style-src']!r}"
    )
