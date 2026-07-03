"""Regression test for the SSRF guard on /validate-bib's DOI check.

_doi_check() (backend/app.py) resolves `https://doi.org/{r.doi}` to verify a
bib entry's DOI is alive. `r.doi` comes straight from an uploaded .bib file
via latextools.bibcheck._clean_doi(), which does no format validation --
any string in a `doi = {...}` field reaches the URL unmodified. doi.org is a
legitimate redirector, but the redirect *target* is chosen by the DOI
registrant, so blindly following it (`follow_redirects=True`) lets a
crafted .bib entry make the backend issue a request to an attacker-chosen
destination (e.g. an internal host or a cloud metadata endpoint).

The fix routes _doi_check through latextools.papercheck's already-hardened
_resolve_doi_redirects_safely()/_is_ssrf_safe_url(), which walks redirects
manually and only follows a hop whose hostname resolves exclusively to
public, globally-routable IPs.

Run via: pytest backend/tests/test_validate_bib_ssrf_guard.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _resp(status_code, location=None):
    r = MagicMock()
    r.status_code = status_code
    r.headers = {"location": location} if location else {}
    return r


@pytest.mark.asyncio
async def test_doi_check_does_not_follow_redirect_to_private_ip(monkeypatch):
    """A malicious doi.org redirect to a private/internal address must be
    refused -- the follow-up request must never be issued."""
    from latextools import papercheck

    calls = []

    async def _fake_head(url, follow_redirects=False, timeout=None):
        calls.append(url)
        if url == "https://doi.org/10.1000/evil":
            return _resp(302, location="https://169.254.169.254/latest/meta-data/")
        raise AssertionError(f"unexpected follow-up request to {url!r}")

    client = MagicMock()
    client.head = AsyncMock(side_effect=_fake_head)

    with pytest.raises(ValueError, match="refusing to request non-public URL"):
        await papercheck._resolve_doi_redirects_safely(client, "10.1000/evil")

    # Only the initial doi.org request was made; the metadata-endpoint hop
    # was never requested.
    assert calls == ["https://doi.org/10.1000/evil"]


@pytest.mark.asyncio
async def test_doi_check_follows_redirect_to_public_host(monkeypatch):
    """A normal doi.org redirect to a public host (the common case) still
    works end to end."""
    from latextools import papercheck

    calls = []

    async def _fake_head(url, follow_redirects=False, timeout=None):
        calls.append(url)
        if url == "https://doi.org/10.1038/nature12373":
            return _resp(302, location="https://www.nature.com/articles/nature12373")
        if url == "https://www.nature.com/articles/nature12373":
            return _resp(200)
        raise AssertionError(f"unexpected request to {url!r}")

    client = MagicMock()
    client.head = AsyncMock(side_effect=_fake_head)

    resp = await papercheck._resolve_doi_redirects_safely(client, "10.1038/nature12373")

    assert calls == [
        "https://doi.org/10.1038/nature12373",
        "https://www.nature.com/articles/nature12373",
    ]
    assert resp.status_code == 200


def test_validate_bib_endpoint_wires_doi_check_through_safe_resolver():
    """/validate-bib's _doi_check must import and call
    papercheck._resolve_doi_redirects_safely rather than issuing its own
    follow_redirects=True request -- guards against the fix regressing back
    to the direct httpx call."""
    import inspect

    import app as backend_app

    src = inspect.getsource(backend_app.web.get_raw_f())
    doi_check_start = src.index("async def _doi_check")
    doi_check_end = src.index("async def _crossref_check", doi_check_start)
    doi_check_src = src[doi_check_start:doi_check_end]

    assert "_resolve_doi_redirects_safely" in doi_check_src
    assert "follow_redirects=True" not in doi_check_src


# ---------------------------------------------------------------------------
# End-to-end: POST a malicious .bib file to /validate-bib and prove the
# metadata-endpoint host is never actually contacted.
# ---------------------------------------------------------------------------

EVIL_BIB = """
@article{evil2024,
  author  = {Attacker, Eve},
  title   = {Malicious Redirect Target},
  journal = {Journal of Nothing},
  year    = {2024},
  doi     = {10.1000/evil},
}
"""


def test_validate_bib_endpoint_refuses_malicious_doi_redirect(monkeypatch):
    import io

    import httpx
    from fastapi.testclient import TestClient

    import app as backend_app

    class _FakeDict:
        def __init__(self):
            self._data = {}

        def get(self, key, default=None):
            return self._data.get(key, default)

        def __setitem__(self, key, value):
            self._data[key] = value

    monkeypatch.setattr(backend_app, "rate_dict", _FakeDict())

    contacted_hosts = []

    async def _fake_head(self, url, follow_redirects=False, **kwargs):
        host = httpx.URL(url).host
        contacted_hosts.append(host)
        if host == "doi.org":
            return httpx.Response(
                302,
                headers={"location": "https://169.254.169.254/latest/meta-data/"},
                request=httpx.Request("HEAD", url),
            )
        raise AssertionError(f"unexpected outbound request to host {host!r}")

    monkeypatch.setattr(httpx.AsyncClient, "head", _fake_head)

    fastapi_app = backend_app.web.local()
    client = TestClient(fastapi_app)

    resp = client.post(
        "/validate-bib",
        files={"file": ("refs.bib", io.BytesIO(EVIL_BIB.encode()), "text/plain")},
        data={"check_doi": "true"},
    )

    assert resp.status_code == 200
    body = resp.json()
    entry = body["entries"][0]
    # The metadata endpoint must never have been contacted.
    assert "169.254.169.254" not in contacted_hosts
    assert contacted_hosts == ["doi.org"]
    # And the check must not report the DOI as verified/alive.
    assert entry["doi_ok"] is not True
