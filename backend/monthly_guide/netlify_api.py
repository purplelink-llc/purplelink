"""Netlify helpers for listing a new monthly guide product.

Two side effects the deploy needs beyond the file edits:

1. ``set_env_var`` creates/updates the site env var that checkout.mjs resolves
   for the new product's ``envKey`` (e.g. ``STRIPE_PRICE_RESEARCH_REVIEW_2026_07``).
   It uses the Netlify account-env REST API. Because env vars only take effect
   on the *next* deploy, the caller must set the var BEFORE running
   ``netlify deploy`` (see app.py ordering).

2. ``blobs_set`` uploads the generated PDF into the ``guide-files`` Netlify
   Blobs store (the same store checkout's download.mjs streams from) using the
   Blobs signed-URL handshake directly, then downloads it back and refuses to
   return until the bytes match.

   It used to shell out to ``netlify blobs:set --input``. The image pins
   netlify-cli@17, and that version reads ``--input`` as TEXT: every byte above
   0x7F in the PDF's deflate streams was re-encoded, the file grew ~1.75x, the
   xref offsets no longer pointed anywhere, and Preview/Safari/iOS refused to
   open it. The 2026-08 review shipped that way and was on sale — and being
   given away as a bonus — as a file nobody could read. Nothing in the pipeline
   noticed, because the CLI exited 0. Hence the round-trip check.

Both operations are idempotent: setting an env var that already exists updates
it in place, and re-uploading a blob overwrites it.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)
# httpx logs every request URL at INFO, and the Blobs handshake hands back
# presigned S3 URLs carrying short-lived credentials. Keep those out of the run log.
logging.getLogger("httpx").setLevel(logging.WARNING)

NETLIFY_API = "https://api.netlify.com/api/v1"

# No "scopes" field is sent. Netlify rejects an explicit scopes list on the
# free tier with 403 "Upgrade your Netlify account to set specific scopes",
# which is what failed the 2026-09-01 run at the last step, after the Stripe
# product and price had already been created. Omitting it makes Netlify apply
# its defaults -- builds, functions, post_processing, runtime -- which is a
# superset of the three that were being requested, so nothing is lost.
# Verified against the live API on 2026-09-02: with scopes 403, without 201.


def _account_slug(client: httpx.Client, token: str, site_id: str) -> str:
    """Resolve the account slug that owns *site_id* (needed for the env API)."""
    resp = client.get(
        f"{NETLIFY_API}/sites/{site_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not resp.is_success:
        raise RuntimeError(f"Netlify site lookup failed: HTTP {resp.status_code}: {resp.text[:200]}")
    site = resp.json()
    slug = site.get("account_slug")
    if not slug:
        raise RuntimeError("Netlify site lookup returned no account_slug")
    return slug


def set_env_var(token: str, site_id: str, key: str, value: str) -> None:
    """Create or update the site-scoped Netlify env var *key*=*value*.

    Idempotent: attempts to create the variable; if it already exists, updates
    its value in place. The var is scoped to the single site so it does not
    leak into other sites on the same Netlify account.
    """
    if not token:
        raise RuntimeError("set_env_var: empty Netlify token")
    with httpx.Client(timeout=30.0) as client:
        account = _account_slug(client, token, site_id)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        base = f"{NETLIFY_API}/accounts/{account}/env"

        create = client.post(
            base,
            params={"site_id": site_id},
            headers=headers,
            json=[{
                "key": key,
                "values": [{"context": "all", "value": value}],
            }],
        )
        if create.is_success:
            logger.info("netlify: created env var %s", key)
            return

        # Already exists (or otherwise not created): update the value in place.
        update = client.put(
            f"{base}/{key}",
            params={"site_id": site_id},
            headers=headers,
            json={
                "key": key,
                "values": [{"context": "all", "value": value}],
            },
        )
        if not update.is_success:
            raise RuntimeError(
                "Netlify env set failed: "
                f"create HTTP {create.status_code} ({create.text[:150]}); "
                f"update HTTP {update.status_code} ({update.text[:150]})"
            )
        logger.info("netlify: updated existing env var %s", key)


_SIGNED_URL_ACCEPT = "application/json;type=signed-url"


def _blob_signed_url(client: httpx.Client, token: str, site_id: str,
                     store: str, key: str, method: str) -> str:
    """One leg of the Blobs handshake: ask the Netlify API for a short-lived
    signed URL for *method* on this blob. Mirrors @netlify/blobs' getFinalRequest
    (the request method to the API is the method you intend to use on the URL)."""
    res = client.request(
        method,
        f"{NETLIFY_API}/blobs/{site_id}/{store}/{key}",
        headers={"Authorization": f"Bearer {token}", "Accept": _SIGNED_URL_ACCEPT},
    )
    if res.status_code != 200:
        raise RuntimeError(
            f"blobs: signed-url request ({method}) for {store}/{key} failed: "
            f"HTTP {res.status_code} {res.text[:300]}"
        )
    return res.json()["url"]


def blobs_get(token: str, site_id: str, store: str, key: str) -> bytes:
    """Download a blob's raw bytes (used to verify an upload)."""
    with httpx.Client(timeout=60) as client:
        url = _blob_signed_url(client, token, site_id, store, key, "GET")
        res = client.get(url)
        if res.status_code != 200:
            raise RuntimeError(f"blobs: download of {store}/{key} failed: HTTP {res.status_code}")
        return res.content


def blobs_set(token: str, site_id: str, store: str, key: str, file_path: str) -> None:
    """Upload *file_path* into the Netlify Blobs *store* under *key*, as bytes,
    then read it back and require a byte-identical round trip.

    Overwrites any existing blob at *key*, so re-runs are idempotent. Raises
    rather than returning if the stored bytes differ from the file: a PDF that
    is "uploaded" but unreadable is worse than a run that fails loudly.
    """
    if not token:
        raise RuntimeError("blobs_set: empty Netlify token")
    data = open(file_path, "rb").read()
    if not data.startswith(b"%PDF-"):
        raise RuntimeError(f"blobs_set: {file_path} is not a PDF (no %PDF- header)")

    with httpx.Client(timeout=120) as client:
        url = _blob_signed_url(client, token, site_id, store, key, "PUT")
        res = client.put(
            url,
            content=data,  # bytes, never str: the whole point
            headers={"cache-control": "max-age=0, stale-while-revalidate=60"},
        )
        if res.status_code not in (200, 201, 204):
            raise RuntimeError(f"blobs: upload of {store}/{key} failed: HTTP {res.status_code} {res.text[:300]}")

    stored = blobs_get(token, site_id, store, key)
    if stored != data:
        raise RuntimeError(
            f"blobs: round-trip mismatch for {store}/{key}: sent {len(data)} bytes, "
            f"store holds {len(stored)}. Refusing to continue — the file for sale would be corrupt."
        )
    logger.info("netlify: uploaded + verified blob %s/%s (%d bytes)", store, key, len(data))
