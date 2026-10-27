"""The monthly guide must upload into the same Blobs namespace download.mjs reads."""
import httpx

from monthly_guide import netlify_api


def test_bare_store_name_gets_site_prefix():
    assert netlify_api._api_store("guide-files") == "site:guide-files"
    assert netlify_api._api_store("site:guide-files") == "site:guide-files"
    assert netlify_api._api_store("deploy:abc") == "deploy:abc"


def test_signed_url_request_uses_site_namespace():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"url": "https://signed.example/x"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        url = netlify_api._blob_signed_url(client, "tok", "SITE", "guide-files", "research-review-2026-11.pdf", "PUT")
    assert url == "https://signed.example/x"
    assert seen == ["/api/v1/blobs/SITE/site:guide-files/research-review-2026-11.pdf"]
