/**
 * Netlify Function — Stripe Checkout session creator (all paid products).
 *
 * POST /.netlify/functions/checkout
 *   body: { product: "paper-review-standard" | "paper-review-deep" | ... }
 *
 * Maps the product key to a Stripe price_id via per-product env vars, then
 * creates a one-time-payment Checkout Session. Returns the hosted URL.
 *
 * The Stripe success URL routes the user to the right post-payment page
 * based on the product category (paper-review goes to /upload/, cover-letter
 * to /tools/cover-letter/compose/, etc.).
 *
 * Required env vars per product key — each is the corresponding price_id.
 * These dollar amounts are the source of truth; the Stripe Price objects
 * created at launch must match them exactly, and so must the visible copy
 * on each tool's landing page. Repriced 2026-07-03 for the Fable 5 model
 * upgrade (see backend/app.py PAID_PRODUCTS for the margin rationale):
 *   STRIPE_PRICE_PAPER_REVIEW_STANDARD     (paper-review-standard, $9)
 *   STRIPE_PRICE_PAPER_REVIEW_JOURNAL      (paper-review-journal, $11)
 *   STRIPE_PRICE_PAPER_REVIEW_DEEP         (paper-review-deep, $15)
 *   STRIPE_PRICE_PAPER_REVIEW_PACK_5       (paper-review-pack-5, $38)
 *   STRIPE_PRICE_PAPER_REVIEW_PACK_20      (paper-review-pack-20, $150)
 *   STRIPE_PRICE_COVER_LETTER              (cover-letter, $2)
 *   STRIPE_PRICE_ANONYMITY_CHECK           (anonymity-check, $2)
 *   STRIPE_PRICE_CITATION_GAP              (citation-gap, $3)
 *   STRIPE_PRICE_REVISION_REVIEW           (revision-review, $2)
 *   STRIPE_PRICE_RESPONSE_REVIEW           (response-review, $6)
 *   STRIPE_SECRET_KEY (shared, sk_test_… or sk_live_…)
 */

import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";

const STRIPE_API = "https://api.stripe.com/v1";

// success_url/cancel_url are handed back to the browser as part of a real
// Stripe Checkout URL, so the Origin header must be checked against a fixed
// allowlist rather than trusted verbatim — otherwise an attacker can point a
// victim's post-payment redirect (with the live session_id) at a domain they
// control. Mirrors backend/app.py's ALLOWED_ORIGINS.
const ALLOWED_ORIGINS = new Set([
  "https://purplelink.llc",
  "https://www.purplelink.llc",
]);
const DEFAULT_ORIGIN = "https://purplelink.llc";

// Idempotency window: retries of the *same* checkout click (e.g. after a
// timed-out/lost response) within this many milliseconds collapse into the
// same Stripe Checkout Session instead of creating a duplicate one.
const IDEMPOTENCY_WINDOW_MS = 5 * 60 * 1000;

// Defense-in-depth: cap how many Checkout Sessions one IP can spin up per
// day. This costs the attacker nothing directly, but unbounded creation
// pollutes the Stripe dashboard and can trip Stripe's own abuse detection
// on the account, so it's worth throttling even though it's not a direct
// financial exposure. Mirrors backend/latextools/core.py's DAILY_LIMIT
// pattern (per-IP, per-bucket, per-UTC-day counter).
const CHECKOUT_DAILY_LIMIT = 25;

async function checkoutRateLimited(clientIp) {
  const day = new Date().toISOString().slice(0, 10); // YYYY-MM-DD (UTC)
  const digest = createHash("sha256").update(clientIp).digest("hex").slice(0, 16);
  const key = `rl:checkout:${day}:${digest}`;
  const store = getStore("rate-limits");
  const raw = await store.get(key);
  const current = raw ? parseInt(raw, 10) || 0 : 0;
  if (current >= CHECKOUT_DAILY_LIMIT) {
    return true;
  }
  await store.set(key, String(current + 1));
  return false;
}

// product key -> {env var name for price_id, success path}
const PRODUCT_CATALOG = {
  "paper-review-standard":   { envKey: "STRIPE_PRICE_PAPER_REVIEW_STANDARD",   successPath: "/tools/paper-review/upload/" },
  "paper-review-journal":    { envKey: "STRIPE_PRICE_PAPER_REVIEW_JOURNAL",    successPath: "/tools/paper-review/upload/" },
  "paper-review-deep":       { envKey: "STRIPE_PRICE_PAPER_REVIEW_DEEP",       successPath: "/tools/paper-review/upload/" },
  "paper-review-pack-5":     { envKey: "STRIPE_PRICE_PAPER_REVIEW_PACK_5",     successPath: "/tools/paper-review/packs/success/" },
  "paper-review-pack-20":    { envKey: "STRIPE_PRICE_PAPER_REVIEW_PACK_20",    successPath: "/tools/paper-review/packs/success/" },
  "cover-letter":            { envKey: "STRIPE_PRICE_COVER_LETTER",            successPath: "/tools/cover-letter/compose/" },
  "anonymity-check":         { envKey: "STRIPE_PRICE_ANONYMITY_CHECK",         successPath: "/tools/anonymity-check/upload/" },
  "citation-gap":            { envKey: "STRIPE_PRICE_CITATION_GAP",            successPath: "/tools/citation-gap/upload/" },
  "revision-review":         { envKey: "STRIPE_PRICE_REVISION_REVIEW",         successPath: "/tools/paper-review/revision/upload/" },
  "response-review":         { envKey: "STRIPE_PRICE_RESPONSE_REVIEW",         successPath: "/tools/response-review/upload/" },
};

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function formEncode(params) {
  const parts = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(String(v)));
  }
  return parts.join("&");
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return jsonResponse(405, { error: "method_not_allowed" });
  }

  const clientIp =
    request.headers.get("x-nf-client-connection-ip") ||
    request.headers.get("x-forwarded-for") ||
    "unknown";

  if (await checkoutRateLimited(clientIp)) {
    return jsonResponse(429, { error: "rate_limited" });
  }

  let body;
  try {
    body = await request.json();
  } catch (_) {
    body = {};
  }
  const product = (body && body.product) || "paper-review-standard";
  const entry = PRODUCT_CATALOG[product];
  if (!entry) {
    return jsonResponse(400, { error: "unknown_product", detail: product });
  }
  // Referral code from a shared report's footer link (?ref=...), passed
  // through as Stripe metadata so stripe-webhook.mjs can forward it to
  // the backend's register-token endpoint. Untrusted input — just a short
  // opaque string, validated server-side against referral_dict, not used
  // for anything here.
  const referralCode = typeof body?.ref === "string" ? body.ref.trim().slice(0, 32) : "";

  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  const priceId = Netlify.env.get(entry.envKey);
  if (!secretKey || !priceId) {
    return jsonResponse(500, {
      error: "misconfigured",
      detail: `Set STRIPE_SECRET_KEY and ${entry.envKey} on this site.`,
    });
  }

  const requestOrigin = request.headers.get("origin");
  const origin = ALLOWED_ORIGINS.has(requestOrigin) ? requestOrigin : DEFAULT_ORIGIN;

  // Derive a stable Idempotency-Key from the buyer's client + the product
  // they're buying, bucketed into a short time window. A client retry (lost
  // response, timeout, double-click) for the same buyer+product within the
  // window reuses the same key, so Stripe returns the original Checkout
  // Session instead of creating a second, independently payable one. A
  // genuinely new purchase attempt after the window (or by a different
  // client) still gets a fresh session.
  const timeBucket = Math.floor(Date.now() / IDEMPOTENCY_WINDOW_MS);
  const idempotencyKey = createHash("sha256")
    .update(`${clientIp}:${product}:${timeBucket}`)
    .digest("hex");

  // Attach the product key as Stripe metadata so the webhook can route
  // correctly without re-deriving from price_id.
  const params = {
    mode: "payment",
    "payment_method_types[0]": "card",
    "line_items[0][price]": priceId,
    "line_items[0][quantity]": "1",
    success_url: `${origin}${entry.successPath}?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}${entry.successPath.replace(/\/(upload|compose|packs\/success)\/$/, "/")}`,
    customer_creation: "if_required",
    "metadata[product]": product,
    "metadata[product_category]": product.startsWith("paper-review") ? "paper-review" : product,
  };
  if (referralCode) {
    params["metadata[referral_code]"] = referralCode;
  }

  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/checkout/sessions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${secretKey}`,
        "Content-Type": "application/x-www-form-urlencoded",
        "Idempotency-Key": idempotencyKey,
      },
      body: formEncode(params),
    });
  } catch (err) {
    return jsonResponse(502, { error: "stripe_unreachable", detail: String(err) });
  }

  let data;
  try {
    data = await resp.json();
  } catch (_) {
    return jsonResponse(502, { error: "stripe_bad_response" });
  }

  if (!resp.ok) {
    const detail =
      (data && data.error && (data.error.message || data.error.code)) ||
      "Stripe rejected the request.";
    return jsonResponse(502, { error: "stripe_error", detail });
  }

  if (!data.url) {
    return jsonResponse(502, { error: "no_redirect_url" });
  }

  return jsonResponse(200, { url: data.url, id: data.id, product });
}
