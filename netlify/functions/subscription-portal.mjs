/**
 * GET /.netlify/functions/subscription-portal?email=...&token=...
 *
 * Redirects a paying digest subscriber to Stripe's hosted Customer
 * Portal, where they can cancel or update their payment method
 * themselves -- no custom account UI needed. `token` is an HMAC of the
 * email, the same signing pattern unsubscribe.mjs already uses
 * (HMAC-SHA256 of the bare email string, hex-encoded), so this link
 * can be embedded directly in the paid-tier email footer without a
 * separate login step.
 *
 * Required env vars: SUBSCRIBE_SECRET, STRIPE_SECRET_KEY
 */
import { getStore } from "@netlify/blobs"
import { createHmac, timingSafeEqual } from "node:crypto"

const STRIPE_API = "https://api.stripe.com/v1"

function verifyToken(email, token, secret) {
  const expected = createHmac("sha256", secret).update(email).digest("hex")
  try {
    return token.length === expected.length &&
      timingSafeEqual(Buffer.from(expected), Buffer.from(token))
  } catch {
    return false
  }
}

export default async function handler(request) {
  const url = new URL(request.url)
  const email = (url.searchParams.get("email") || "").toLowerCase().trim()
  const token = url.searchParams.get("token") || ""

  const secret = process.env.SUBSCRIBE_SECRET
  const stripeKey = process.env.STRIPE_SECRET_KEY
  if (!secret || !stripeKey) {
    return new Response("Server misconfigured", { status: 500 })
  }
  if (!email || !token || !verifyToken(email, token, secret)) {
    return new Response("Invalid or expired link", { status: 403 })
  }

  const store = getStore("subscribers")
  const raw = await store.get(email)
  if (!raw) {
    return new Response("No subscription found", { status: 404 })
  }
  const record = JSON.parse(raw)
  if (!record.stripe_customer_id) {
    return new Response("No billing account on file", { status: 404 })
  }

  const resp = await fetch(`${STRIPE_API}/billing_portal/sessions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${stripeKey}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      customer: record.stripe_customer_id,
      return_url: "https://purplelink.llc/blog/digest/",
    }),
  })
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "")
    console.error("subscription-portal: stripe error", resp.status, detail)
    return new Response("Could not open billing portal", { status: 502 })
  }
  const session = await resp.json()
  return Response.redirect(session.url, 303)
}
