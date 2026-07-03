"""Regression test for the sitewide Content-Security-Policy in netlify.toml.

CLAUDE.md's hard constraint is "Strict CSP: style-src 'self' — no inline
styles, ever," with one explicit, owner-authorized exception documented in
CLAUDE.md under "AdSense exception": style-src 'unsafe-inline' plus a fixed
set of Google/AdSense origins, sitewide, so AdSense can render. This test
pins the CSP to exactly that authorized state — it fails if style-src gains
'unsafe-inline' from anywhere OTHER than this documented exception (i.e. the
AdSense origins are missing/changed), or if it silently loses the exception,
so any future drift (accidental or an automated sweep reverting it again)
surfaces as a visible, explainable test failure rather than either a silent
regression or a silent policy violation.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NETLIFY_TOML = REPO_ROOT / "netlify.toml"

# Must exactly match the AdSense exception documented in CLAUDE.md.
EXPECTED_STYLE_SRC = "style-src 'self' 'unsafe-inline'"
EXPECTED_ADSENSE_ORIGINS = {
    "https://pagead2.googlesyndication.com",
    "https://googleads.g.doubleclick.net",
    "https://www.google.com",
    "https://www.gstatic.com",
    "https://www.googletagservices.com",
    "https://tpc.googlesyndication.com",
}


def _sitewide_csp() -> str:
    text = NETLIFY_TOML.read_text()
    match = re.search(r'Content-Security-Policy = "([^"]*)"', text)
    assert match, "Content-Security-Policy header not found in netlify.toml"
    return match.group(1)


def _directives() -> dict:
    csp = _sitewide_csp()
    return {
        d.strip().split()[0]: d.strip()
        for d in csp.split(";")
        if d.strip()
    }


def test_netlify_toml_exists():
    assert NETLIFY_TOML.is_file()


def test_style_src_matches_the_authorized_adsense_exception():
    directives = _directives()
    assert "style-src" in directives, "style-src directive missing from CSP"
    assert directives["style-src"] == EXPECTED_STYLE_SRC, (
        "style-src must be exactly the CLAUDE.md-documented AdSense exception "
        f"({EXPECTED_STYLE_SRC!r}); got: {directives['style-src']!r}. If this "
        "is an intentional further change, update CLAUDE.md's AdSense "
        "exception note and this test together."
    )


def test_adsense_origins_present_in_relevant_directives():
    directives = _directives()
    for name in ("img-src", "script-src", "connect-src", "frame-src"):
        assert name in directives, f"{name} directive missing from CSP"
        present = {o for o in EXPECTED_ADSENSE_ORIGINS if o in directives[name]}
        assert present, (
            f"expected at least one AdSense origin in {name} per the "
            "CLAUDE.md-documented exception, found none"
        )
