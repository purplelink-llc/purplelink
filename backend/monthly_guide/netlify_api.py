"""Netlify helpers for listing a new monthly guide product.

Two side effects the deploy needs beyond the file edits:

1. ``set_env_var`` creates/updates the site env var that checkout.mjs resolves
   for the new product's ``envKey`` (e.g. ``STRIPE_PRICE_RESEARCH_REVIEW_2026_07``).
   It uses the Netlify account-env REST API. Because env vars only take effect
   on the *next* deploy, the caller must set the var BEFORE running
   ``netlify deploy`` (see app.py ordering).

2. ``blobs_set`` uploads the generated PDF into the ``guide-files`` Netlify
   Blobs store via the bundled ``netlify`` CLI (the same store checkout's
   download.mjs streams from). Shelling to the CLI avoids reimplementing the
   Blobs signed-upload handshake.

Both operations are idempotent: setting an env var that already exists updates
it in place, and re-uploading a blob overwrites it.
"""
from __future__ import annotations

import logging
import os
import subprocess

import httpx

logger = logging.getLogger(__name__)

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


def blobs_set(token: str, site_id: str, store: str, key: str, file_path: str) -> None:
    """Upload *file_path* into the Netlify Blobs *store* under *key* via the CLI.

    Runs ``netlify blobs:set <store> <key> --input <file>`` with the auth token
    and site id supplied through the environment (non-interactive). Overwrites
    any existing blob at *key*, so re-runs are idempotent.
    """
    if not token:
        raise RuntimeError("blobs_set: empty Netlify token")
    env = {
        **os.environ,
        "NETLIFY_AUTH_TOKEN": token,
        "NETLIFY_SITE_ID": site_id,
    }
    # No --site flag: blobs:set does not accept one ("Error: unknown option
    # '--site'"), which failed the 2026-08 run at the upload step. The site is
    # already supplied through NETLIFY_SITE_ID in env above, which is how the
    # command expects it. Output is captured so a future failure reports the
    # CLI's own message instead of a bare non-zero exit status.
    proc = subprocess.run(
        ["netlify", "blobs:set", store, key, "--input", file_path],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"netlify blobs:set failed (exit {proc.returncode}) for {store}/{key}: "
            f"{(proc.stderr or proc.stdout or '').strip()[:500]}"
        )
    logger.info("netlify: uploaded blob %s/%s from %s", store, key, file_path)
