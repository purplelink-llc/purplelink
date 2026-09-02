"""Create the Stripe Product + one-time $1 Price for a monthly guide.

Uses the Stripe REST API directly (form-encoded, HTTP Basic auth with the
secret key as the username) so no ``stripe`` SDK dependency is added to the
Modal image. Mirrors backend/setup_resume_review_price.py.

IDEMPOTENT: every product is stamped with ``metadata[monthly_guide_slug]``.
Before creating anything, we search existing products for that slug; if one is
found we reuse it and return its existing active Price id, so re-running the
cron for the same month never creates a duplicate product or price.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

STRIPE_API = "https://api.stripe.com/v1"
UNIT_AMOUNT_CENTS = "100"  # $1.00
CURRENCY = "usd"
SLUG_METADATA_KEY = "monthly_guide_slug"


def _raise_for_status(resp: httpx.Response, what: str) -> dict:
    if not resp.is_success:
        raise RuntimeError(f"Stripe {what} failed: HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _find_existing_price(client: httpx.Client, secret_key: str, slug: str) -> str | None:
    """Return the active Price id for the product tagged with *slug*, or None.

    Uses Stripe's search API on product metadata. If the product exists but has
    no active price (an interrupted earlier run), returns None so the caller
    creates the missing price against the existing product.
    """
    search = client.get(
        f"{STRIPE_API}/products/search",
        auth=(secret_key, ""),
        params={"query": f"metadata['{SLUG_METADATA_KEY}']:'{slug}'"},
    )
    data = _raise_for_status(search, "product search")
    products = data.get("data", [])
    if not products:
        return None
    product_id = products[0]["id"]

    prices = client.get(
        f"{STRIPE_API}/prices",
        auth=(secret_key, ""),
        params={"product": product_id, "active": "true", "limit": "1"},
    )
    price_data = _raise_for_status(prices, "price list")
    existing = price_data.get("data", [])
    if existing:
        logger.info("stripe: reusing existing price %s for slug %s", existing[0]["id"], slug)
        return existing[0]["id"]
    # Product exists but has no active price: create one against it below.
    logger.info("stripe: product %s exists for slug %s but has no active price", product_id, slug)
    return _create_price(client, secret_key, product_id, slug)


def _create_price(client: httpx.Client, secret_key: str, product_id: str, slug: str) -> str:
    price_resp = client.post(
        f"{STRIPE_API}/prices",
        auth=(secret_key, ""),
        data={
            "product": product_id,
            "unit_amount": UNIT_AMOUNT_CENTS,
            "currency": CURRENCY,
            f"metadata[{SLUG_METADATA_KEY}]": slug,
        },
    )
    price = _raise_for_status(price_resp, "price create")
    logger.info("stripe: created price %s for slug %s", price["id"], slug)
    return price["id"]


def create_monthly_product(secret_key: str, title: str, slug: str) -> str:
    """Create (or reuse) a Product + one-time $1 Price for the monthly guide.

    *slug* is the stable product key (e.g. "research-review-2026-07"); it is
    stored in ``metadata[monthly_guide_slug]`` on the Product so the operation
    is idempotent. Returns the Stripe Price id to store in the site's
    ``STRIPE_PRICE_*`` env var.
    """
    if not secret_key:
        raise RuntimeError("create_monthly_product: empty Stripe secret key")
    with httpx.Client(timeout=30.0) as client:
        existing = _find_existing_price(client, secret_key, slug)
        if existing:
            return existing

        product_resp = client.post(
            f"{STRIPE_API}/products",
            auth=(secret_key, ""),
            data={
                "name": title,
                "description": (
                    "Monthly research review mini-guide synthesizing that month's "
                    "GLP-1 and muscle research roundups. One-time $1 PDF."
                ),
                f"metadata[{SLUG_METADATA_KEY}]": slug,
            },
        )
        product = _raise_for_status(product_resp, "product create")
        product_id = product["id"]
        logger.info("stripe: created product %s for slug %s", product_id, slug)
        return _create_price(client, secret_key, product_id, slug)
