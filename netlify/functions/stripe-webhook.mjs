/**
 * Netlify Function — Paper Review Stripe webhook receiver.
 *
 * POST /.netlify/functions/stripe-webhook
 *
 * Stripe POSTs `checkout.session.completed` here when a Paper Review payment
 * succeeds. We verify the Stripe signature, extract session_id + customer
 * email + amount, then forward to the Modal backend's
 * /paper-review/register-token endpoint (authenticated by a shared secret
 * header) so the backend can mint a redemption token for that session.
 *
 * Required env vars:
 *   STRIPE_WEBHOOK_SECRET    — whsec_… signing secret from the Stripe webhook config
 *   BACKEND_WEBHOOK_SECRET   — same value as the Modal secret `paper-review-shared`
 *
 * Webhook endpoint to register in the Stripe dashboard:
 *   https://purplelink.llc/.netlify/functions/stripe-webhook
 *   subscribed to event: checkout.session.completed
 */

import { createHmac, timingSafeEqual } from "node:crypto";

const MODAL_REGISTER_URL =
  "https://ben-ampel--purplelink-latextools-web.modal.run/paper-review/register-token";

const MAX_SIG_AGE_SECONDS = 5 * 60;   // reject replays older than 5 min

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Verify a Stripe signature header against the raw body.
 * Stripe signs `${timestamp}.${rawBody}` with HMAC-SHA256 using the
 * webhook signing secret. The `Stripe-Signature` header looks like:
 *   t=1657123456,v1=abcdef…,v1=…   (multiple v1 entries allowed during rotation)
 */
function verifyStripeSignature(rawBody, header, secret) {
  if (!header || !secret) return false;
  const parts = header.split(",").map((p) => p.trim());
  let timestamp = null;
  const candidates = [];
  for (const part of parts) {
    const [k, v] = part.split("=");
    if (k === "t") timestamp = v;
    if (k === "v1") candidates.push(v);
  }
  if (!timestamp || candidates.length === 0) return false;

  const ts = parseInt(timestamp, 10);
  if (!Number.isFinite(ts)) return false;
  const ageSeconds = Math.floor(Date.now() / 1000) - ts;
  if (Math.abs(ageSeconds) > MAX_SIG_AGE_SECONDS) return false;

  const signedPayload = `${timestamp}.${rawBody}`;
  const expected = createHmac("sha256", secret).update(signedPayload).digest("hex");
  const expectedBuf = Buffer.from(expected, "utf8");

  for (const sig of candidates) {
    const sigBuf = Buffer.from(sig, "utf8");
    if (sigBuf.length === expectedBuf.length && timingSafeEqual(sigBuf, expectedBuf)) {
      return true;
    }
  }
  return false;
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return jsonResponse(405, { error: "method_not_allowed" });
  }

  const stripeSecret = Netlify.env.get("STRIPE_WEBHOOK_SECRET");
  const backendSecret = Netlify.env.get("BACKEND_WEBHOOK_SECRET");
  if (!stripeSecret || !backendSecret) {
    return jsonResponse(500, {
      error: "misconfigured",
      detail: "STRIPE_WEBHOOK_SECRET or BACKEND_WEBHOOK_SECRET not set.",
    });
  }

  // Stripe signature verification requires the raw request body.
  const rawBody = await request.text();
  const signature = request.headers.get("stripe-signature");
  if (!verifyStripeSignature(rawBody, signature, stripeSecret)) {
    return jsonResponse(400, { error: "invalid_signature" });
  }

  let event;
  try {
    event = JSON.parse(rawBody);
  } catch (_) {
    return jsonResponse(400, { error: "invalid_json" });
  }

  // We only care about a completed Checkout session for v1.
  if (event.type !== "checkout.session.completed") {
    // 200-OK every other event type so Stripe doesn't retry indefinitely.
    return jsonResponse(200, { status: "ignored", type: event.type });
  }

  const session = event.data && event.data.object;
  if (!session || !session.id) {
    return jsonResponse(400, { error: "missing_session" });
  }
  if (session.payment_status !== "paid") {
    return jsonResponse(200, { status: "not_paid", payment_status: session.payment_status });
  }

  const sessionId = session.id;
  const email =
    (session.customer_details && session.customer_details.email) ||
    session.customer_email ||
    "";
  const amountPaid = session.amount_total || 0;   // in cents
  // The checkout function stamps the product key into metadata so we can
  // dispatch on it here without needing a separate price_id → product map.
  const product =
    (session.metadata && session.metadata.product) ||
    "paper-review-standard";

  // Forward to the Modal backend so a redemption token is minted.
  let registerResp;
  try {
    registerResp = await fetch(MODAL_REGISTER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-webhook-secret": backendSecret,
      },
      body: JSON.stringify({
        session_id: sessionId,
        email,
        amount_paid: amountPaid,
        product,
      }),
    });
  } catch (err) {
    return jsonResponse(502, { error: "modal_unreachable", detail: String(err) });
  }

  if (!registerResp.ok) {
    const detail = await registerResp.text().catch(() => "");
    return jsonResponse(502, {
      error: "modal_register_failed",
      modal_status: registerResp.status,
      detail: detail.slice(0, 300),
    });
  }

  return jsonResponse(200, { status: "registered", session_id: sessionId });
}
