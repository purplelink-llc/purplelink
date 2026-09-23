/**
 * Netlify Function — Vitae Plus license keys.
 *
 * GET /.netlify/functions/vitae-license?session_id=cs_…
 *   -> 200 { key: "VP1-…", email: "<Stripe receipt address>" | null }
 *   -> 400 bad_session_id · 402 not_paid · 404 not_found · 429 rate_limited · 500/502
 *
 * Called by /vitae/plus/success/ after Stripe Checkout. Confirms the session is
 * paid and is for the "vitae-plus" product, then returns a license key that the
 * Vitae app verifies offline against the matching Ed25519 public key. The app
 * never contacts a server to check it.
 *
 * Key format (must match the app's verifier byte for byte):
 *   payload = UTF-8 JSON.stringify({ iat, id, p: "vitae-plus", v: 1 })   (key order: iat, id, p, v)
 *     iat = the Stripe session's `created` (unix seconds)
 *     id  = first 16 hex chars of sha256(session.id)
 *   sig     = Ed25519 signature over payload
 *   key     = "VP1-" + base64url(payload) + "." + base64url(sig)   (no padding)
 *
 * Both fields come from the session, so reloading the success page returns the
 * same key. No name or email goes into the key. The email in the response is
 * only shown on the page and is never logged.
 *
 * Env vars:
 *   STRIPE_SECRET_KEY          shared with checkout.mjs
 *   VITAE_LICENSE_PRIVATE_KEY  Ed25519 PKCS#8 PEM; literal "\n" sequences are accepted
 */
import { createHash, createPrivateKey, sign } from "node:crypto";
import { getStore } from "@netlify/blobs";

const STRIPE_API = "https://api.stripe.com/v1";
const PRODUCT_KEY = "vitae-plus";
const LICENSE_DAILY_LIMIT = 60;
const SESSION_ID = /^cs_[A-Za-z0-9_]{10,200}$/;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

/** Per-IP, per-UTC-day counter in the shared rate-limits store (same pattern as checkout.mjs). */
async function rateLimited(clientIp) {
  const day = new Date().toISOString().slice(0, 10);
  const digest = createHash("sha256").update(clientIp).digest("hex").slice(0, 16);
  const key = `rl:vitae-license:${day}:${digest}`;
  const store = getStore("rate-limits");
  const current = parseInt((await store.get(key)) || "0", 10) || 0;
  if (current >= LICENSE_DAILY_LIMIT) return true;
  await store.set(key, String(current + 1));
  return false;
}

/** Accepts a PEM whose newlines arrived escaped as the two characters "\n". */
export function loadPrivateKey(pem) {
  return createPrivateKey(String(pem).replace(/\\n/g, "\n"));
}

/**
 * Pure key builder: the same (sessionId, created) always yields the same payload,
 * and Ed25519 signatures are deterministic, so the whole key is stable too.
 */
export function buildLicenseKey({ sessionId, created, privateKey }) {
  const id = createHash("sha256").update(sessionId, "utf8").digest("hex").slice(0, 16);
  const payload = Buffer.from(JSON.stringify({ iat: created, id, p: PRODUCT_KEY, v: 1 }), "utf8");
  const sig = sign(null, payload, privateKey);
  return "VP1-" + payload.toString("base64url") + "." + sig.toString("base64url");
}

export default async function handler(request) {
  if (request.method !== "GET") return json(405, { error: "method_not_allowed" });

  const sessionId = new URL(request.url).searchParams.get("session_id") || "";
  if (!SESSION_ID.test(sessionId)) {
    return json(400, { error: "bad_session_id", detail: "That link is missing its order reference." });
  }

  const clientIp =
    request.headers.get("x-nf-client-connection-ip") ||
    request.headers.get("x-forwarded-for") ||
    "unknown";
  if (await rateLimited(clientIp)) {
    return json(429, { error: "rate_limited", detail: "Too many requests from this address today." });
  }

  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  const pem = Netlify.env.get("VITAE_LICENSE_PRIVATE_KEY");
  if (!secretKey || !pem) {
    return json(500, { error: "misconfigured", detail: "The license service is not set up yet." });
  }

  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/checkout/sessions/${encodeURIComponent(sessionId)}`, {
      headers: { Authorization: `Bearer ${secretKey}` },
    });
  } catch (_) {
    return json(502, { error: "stripe_unreachable", detail: "Could not reach the payment processor." });
  }
  if (resp.status === 404) {
    return json(404, { error: "not_found", detail: "No order matches this link." });
  }
  if (!resp.ok) {
    return json(502, { error: "stripe_error", detail: "The payment processor did not answer as expected." });
  }

  let session;
  try {
    session = await resp.json();
  } catch (_) {
    return json(502, { error: "stripe_bad_response" });
  }

  if ((session.metadata?.product || "") !== PRODUCT_KEY) {
    return json(404, { error: "not_found", detail: "No Vitae Plus order matches this link." });
  }
  if (session.payment_status !== "paid") {
    return json(402, { error: "not_paid", detail: "The payment has not cleared yet." });
  }
  if (!Number.isInteger(session.created) || typeof session.id !== "string") {
    return json(502, { error: "stripe_bad_response" });
  }

  let key;
  try {
    key = buildLicenseKey({ sessionId: session.id, created: session.created, privateKey: loadPrivateKey(pem) });
  } catch (_) {
    return json(500, { error: "signing_failed", detail: "The key could not be issued." });
  }

  return json(200, { key, email: session.customer_details?.email || null });
}
