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
 * Required env vars per product key — each is the corresponding price_id:
 *   STRIPE_PRICE_PAPER_REVIEW_STANDARD     (paper-review-standard, $5)
 *   STRIPE_PRICE_PAPER_REVIEW_ANONYMITY    (paper-review-anonymity, $7)
 *   STRIPE_PRICE_PAPER_REVIEW_JOURNAL      (paper-review-journal, $9)
 *   STRIPE_PRICE_PAPER_REVIEW_DEEP         (paper-review-deep, $19)
 *   STRIPE_PRICE_PAPER_REVIEW_PACK_5       (paper-review-pack-5, $20)
 *   STRIPE_PRICE_PAPER_REVIEW_PACK_20      (paper-review-pack-20, $60)
 *   STRIPE_PRICE_COVER_LETTER              (cover-letter, $3)
 *   STRIPE_PRICE_ANONYMITY_CHECK           (anonymity-check, $2)
 *   STRIPE_PRICE_CITATION_GAP              (citation-gap, $5)
 *   STRIPE_PRICE_REVISION_REVIEW           (revision-review, $2)
 *   STRIPE_PRICE_RESPONSE_REVIEW           (response-review, $9)
 *   STRIPE_SECRET_KEY (shared, sk_test_… or sk_live_…)
 */

const STRIPE_API = "https://api.stripe.com/v1";

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

  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  const priceId = Netlify.env.get(entry.envKey);
  if (!secretKey || !priceId) {
    return jsonResponse(500, {
      error: "misconfigured",
      detail: `Set STRIPE_SECRET_KEY and ${entry.envKey} on this site.`,
    });
  }

  const origin = request.headers.get("origin") || "https://purplelink.llc";

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

  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/checkout/sessions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${secretKey}`,
        "Content-Type": "application/x-www-form-urlencoded",
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
