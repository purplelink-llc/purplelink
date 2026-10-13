"""Regression tests for the SSRF guard on the DOI redirect lookup in
backend/latextools/papercheck.py.

_crossref_lookup() resolves `https://doi.org/{ref.doi}` to check a citation
is alive. `ref.doi` is extracted verbatim from the uploaded manuscript's
bibliography via a loose regex with no allowlist, and doi.org is a
legitimate third-party redirector whose destination the DOI *registrant*
controls. Blindly following redirects (httpx `follow_redirects=True`) would
let a manuscript force the backend to issue an outbound request to any
attacker-chosen destination, including cloud metadata endpoints
(169.254.169.254) or internal-only hosts.

The fix walks the redirect chain manually via _resolve_doi_redirects_safely()
and vets every hop with _is_ssrf_safe_url(), which resolves the hostname and
requires every resolved address to be a public, globally-routable IP.

Run via: pytest backend/tests/test_papercheck_ssrf_guard.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from latextools import papercheck  # noqa: E402


# ----------------------------------------------------------------------------
# _is_ssrf_safe_url — the hostname/IP allowlist check
# ----------------------------------------------------------------------------

def test_public_https_url_is_safe():
    assert papercheck._is_ssrf_safe_url("https://doi.org/10.1000/abc") is True


def test_cloud_metadata_ip_is_unsafe():
    assert papercheck._is_ssrf_safe_url(
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
    ) is False


def test_literal_loopback_is_unsafe():
    assert papercheck._is_ssrf_safe_url("http://127.0.0.1/") is False


def test_localhost_hostname_is_unsafe(monkeypatch):
    # localhost resolves to 127.0.0.1 via getaddrinfo — must be blocked too,
    # not just literal IPs.
    assert papercheck._is_ssrf_safe_url("http://localhost:8000/") is False


def test_private_range_ip_is_unsafe():
    assert papercheck._is_ssrf_safe_url("http://10.0.0.5/") is False
    assert papercheck._is_ssrf_safe_url("http://192.168.1.1/") is False


def test_non_http_scheme_is_unsafe():
    assert papercheck._is_ssrf_safe_url("file:///etc/passwd") is False
    assert papercheck._is_ssrf_safe_url("ftp://example.com/") is False


def test_unresolvable_host_is_unsafe():
    assert papercheck._is_ssrf_safe_url(
        "http://this-host-does-not-exist.invalid/"
    ) is False


# ----------------------------------------------------------------------------
# _resolve_doi_redirects_safely — never auto-follows redirects
# ----------------------------------------------------------------------------

def _resp(status_code, location=None):
    r = MagicMock()
    r.status_code = status_code
    r.headers = {"location": location} if location else {}
    return r


@pytest.mark.asyncio
async def test_never_calls_head_with_follow_redirects_true():
    """The HEAD call must always pass follow_redirects=False -- redirects
    are walked (and vetted) manually, never delegated to httpx."""
    client = MagicMock()
    client.head = AsyncMock(return_value=_resp(200))

    await papercheck._resolve_doi_redirects_safely(client, "10.1000/abc")

    client.head.assert_awaited_once()
    _, kwargs = client.head.call_args
    assert kwargs.get("follow_redirects") is False


@pytest.mark.asyncio
async def test_redirect_to_public_host_is_followed():
    client = MagicMock()
    client.head = AsyncMock(
        side_effect=[
            _resp(302, location="https://example.com/paper.pdf"),
            _resp(200),
        ]
    )

    resp = await papercheck._resolve_doi_redirects_safely(client, "10.1000/abc")

    assert resp.status_code == 200
    assert client.head.await_count == 2


@pytest.mark.asyncio
async def test_redirect_to_metadata_ip_is_blocked():
    """The core SSRF regression case: doi.org 302s to the cloud metadata
    endpoint. The manual resolver must refuse to issue the follow-up
    request instead of transparently fetching it."""
    client = MagicMock()
    client.head = AsyncMock(
        return_value=_resp(
            302,
            location="http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        )
    )

    with pytest.raises(ValueError, match="non-public"):
        await papercheck._resolve_doi_redirects_safely(client, "10.1000/evil")

    # Only the first (doi.org) hop should ever have been requested.
    assert client.head.await_count == 1


@pytest.mark.asyncio
async def test_redirect_to_internal_host_is_blocked():
    client = MagicMock()
    client.head = AsyncMock(
        return_value=_resp(302, location="http://10.0.0.50:8080/internal-admin")
    )

    with pytest.raises(ValueError, match="non-public"):
        await papercheck._resolve_doi_redirects_safely(client, "10.1000/evil")

    assert client.head.await_count == 1


@pytest.mark.asyncio
async def test_excessive_redirect_chain_is_bounded():
    client = MagicMock()
    client.head = AsyncMock(
        return_value=_resp(302, location="https://doi.org/loop")
    )

    with pytest.raises(ValueError, match="too many redirects"):
        await papercheck._resolve_doi_redirects_safely(client, "10.1000/loop")

    assert client.head.await_count == papercheck._MAX_DOI_REDIRECTS


# ----------------------------------------------------------------------------
# _crossref_lookup — end-to-end: malicious DOI never leaks a raw response
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crossref_lookup_reports_network_error_for_ssrf_attempt():
    """From the caller's perspective, a manuscript citing a DOI that
    redirects to a metadata/internal endpoint must degrade gracefully to a
    'network_error' status -- never raise out of the pipeline, and never
    result in the metadata response being requested."""
    ref = papercheck.PaperReference(raw="Evil et al. 2024", doi="10.1000/evil")
    client = MagicMock()
    client.head = AsyncMock(
        return_value=_resp(
            302, location="http://169.254.169.254/latest/meta-data/"
        )
    )

    result = await papercheck._crossref_lookup(client, ref)

    assert result["status"] == "network_error"
    assert client.head.await_count == 1


# ----------------------------------------------------------------------------
# DNS-rebinding window: the request connects to the address that was checked
# ----------------------------------------------------------------------------

def _fake_getaddrinfo(mapping):
    calls = []

    def fake(host, port, *args, **kwargs):
        calls.append(host)
        if host not in mapping:
            raise OSError("unresolvable")
        return [(2, 1, 6, "", (ip, port or 0)) for ip in mapping[host]]

    fake.calls = calls
    return fake


def test_pin_connects_to_resolved_ip_and_keeps_name_for_host_and_sni(monkeypatch):
    monkeypatch.setattr(papercheck.socket, "getaddrinfo", _fake_getaddrinfo({"doi.org": ["8.8.8.8"]}))
    pinned, headers, ext = papercheck._pin_public_address("https://doi.org/10.1000/abc?x=1")
    assert pinned == "https://8.8.8.8/10.1000/abc?x=1"
    assert headers == {"Host": "doi.org"}
    assert ext == {"sni_hostname": "doi.org"}


def test_pin_keeps_port_and_brackets_ipv6_and_skips_sni_for_http(monkeypatch):
    monkeypatch.setattr(
        papercheck.socket, "getaddrinfo",
        _fake_getaddrinfo({"a.example": ["2606:4700:4700::1111"], "b.example": ["1.1.1.1"]}),
    )
    pinned, headers, ext = papercheck._pin_public_address("http://a.example:8080/x")
    assert pinned == "http://[2606:4700:4700::1111]:8080/x"
    assert headers == {"Host": "a.example:8080"} and ext == {}


def test_pin_refuses_when_any_address_is_private(monkeypatch):
    monkeypatch.setattr(
        papercheck.socket, "getaddrinfo",
        _fake_getaddrinfo({"mixed.example": ["8.8.8.8", "10.0.0.5"], "meta.example": ["169.254.169.254"]}),
    )
    assert papercheck._pin_public_address("https://mixed.example/") is None
    assert papercheck._pin_public_address("https://meta.example/") is None
    assert papercheck._pin_public_address("file:///etc/passwd") is None
    assert papercheck._pin_public_address("https://unknown.example/") is None


@pytest.mark.asyncio
async def test_each_hop_resolves_once_and_requests_the_checked_address(monkeypatch):
    """A name that would resolve differently on a second lookup is only ever
    resolved once per hop, and the request goes to the first (checked) answer."""
    fake = _fake_getaddrinfo({"doi.org": ["8.8.8.8"], "pub.example": ["1.1.1.1"]})
    monkeypatch.setattr(papercheck.socket, "getaddrinfo", fake)
    client = MagicMock()
    client.head = AsyncMock(side_effect=[_resp(302, location="https://pub.example/p"), _resp(200)])

    await papercheck._resolve_doi_redirects_safely(client, "10.1000/abc")

    assert fake.calls == ["doi.org", "pub.example"]
    first, second = client.head.await_args_list
    assert first.args[0] == "https://8.8.8.8/10.1000/abc"
    assert first.kwargs["headers"] == {"Host": "doi.org"}
    assert first.kwargs["extensions"] == {"sni_hostname": "doi.org"}
    assert second.args[0] == "https://1.1.1.1/p"
    assert second.kwargs["headers"] == {"Host": "pub.example"}
