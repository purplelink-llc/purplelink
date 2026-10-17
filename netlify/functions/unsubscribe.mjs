/**
 * /.netlify/functions/unsubscribe?email=...&token=...
 *
 * Token is HMAC-SHA256(SUBSCRIBE_SECRET, email), minted by the digest mailer (backend/digest/mailer.py)
 * and stored on each subscriber record.
 *
 *   GET   Shows a confirm page with one button. It changes nothing, so a mail scanner or link prefetch
 *         that follows the link cannot unsubscribe anyone or cancel a paid subscription. Every link
 *         already sent keeps working: it lands on this page.
 *   POST  Unsubscribes. Used by the confirm page's button (form post) and by RFC 8058 one-click
 *         (List-Unsubscribe-Post: List-Unsubscribe=One-Click, posted by the mail client to the same URL
 *         with the email and token in the query string; no page is needed). Removes the subscriber from
 *         the Netlify Blobs store and shows a confirmation page.
 *
 * This is the ONLY unsubscribe link every digest email carries, regardless
 * of tier: free, legacy, and paid subscribers all get the same link. A
 * paid subscriber (tier: "paid", stripe_subscription_id set by
 * stripe-webhook.mjs on checkout.session.completed) has a real, billing
 * Stripe subscription behind their record. If we just deleted the record,
 * they'd stop receiving email but Stripe would keep charging them with no
 * remaining link between the orphaned subscription and a person, so a POST
 * cancels the Stripe subscription first for paid-tier subscribers.
 * Billing details are handled separately by subscription-portal.mjs.
 *
 * Required env vars: SUBSCRIBE_SECRET, STRIPE_SECRET_KEY
 */
import { getStore } from "@netlify/blobs"
import { createHmac, timingSafeEqual } from "node:crypto"
import { escapeHtml, page } from "../lib/fn-page.mjs"

const STRIPE_API = "https://api.stripe.com/v1"

// Best-effort: cancel the Stripe subscription behind a paid-tier record.
// Failure here (network blip, already-cancelled subscription, bad key)
// must NOT block the unsubscribe — leaving the person still subscribed
// to email AND still being billed is strictly worse than degrading to
// "no longer emailed, but the still-active charge is now their or
// support's problem to notice." Log and move on either way.
async function cancelStripeSubscription(subscriptionId) {
  const secretKey = process.env.STRIPE_SECRET_KEY
  if (!secretKey) {
    console.error(`unsubscribe: STRIPE_SECRET_KEY not set, cannot cancel subscription ${subscriptionId}`)
    return
  }
  try {
    const resp = await fetch(`${STRIPE_API}/subscriptions/${subscriptionId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${secretKey}` },
    })
    if (!resp.ok) {
      const detail = await resp.text().catch(() => "")
      console.error(`unsubscribe: Stripe cancellation failed for ${subscriptionId}: ${resp.status} ${detail}`)
    }
  } catch (err) {
    console.error(`unsubscribe: Stripe cancellation errored for ${subscriptionId}:`, err)
  }
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD" && request.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD, POST" } })
  }
  const url = new URL(request.url)
  let email = (url.searchParams.get("email") ?? "").toLowerCase().trim()
  let token = url.searchParams.get("token") ?? ""

  // The confirm page's form posts the same two fields in the body; one-click posts carry them in the URL.
  if (request.method === "POST") {
    const body = Object.fromEntries(new URLSearchParams(await request.text().catch(() => "")))
    if (typeof body.email === "string" && body.email) email = body.email.toLowerCase().trim()
    if (typeof body.token === "string" && body.token) token = body.token
  }

  const secret = process.env.SUBSCRIBE_SECRET
  if (!secret || !email || !token) {
    return page(
      "Invalid link", "Invalid link",
      "<p>This unsubscribe link is missing required parameters.</p><p><a href='/blog/'>Back to the blog</a></p>",
      400,
    )
  }

  const expected = createHmac("sha256", secret).update(email).digest("hex")

  let valid = false
  try {
    if (token.length === expected.length) {
      valid = timingSafeEqual(Buffer.from(expected), Buffer.from(token))
    }
  } catch {
    valid = false
  }

  if (!valid) {
    return page(
      "Invalid link", "Invalid link",
      "<p>This unsubscribe link is not valid. It may have been altered.</p><p><a href='/blog/'>Back to the blog</a></p>",
      400,
    )
  }

  if (request.method !== "POST") {
    return page(
      "Unsubscribe", "Unsubscribe from the Daily Digest",
      `<p class="post-lede">Stop Daily Digest emails to ${escapeHtml(email)}? If you have a paid subscription, this also cancels it and stops billing.</p>
      <form method="post" action="/.netlify/functions/unsubscribe">
        <input type="hidden" name="email" value="${escapeHtml(email)}">
        <input type="hidden" name="token" value="${escapeHtml(token)}">
        <button type="submit" class="btn btn-primary">Unsubscribe</button>
      </form>
      <p><a href="/blog/">Keep my subscription</a></p>`,
    )
  }

  const store = getStore("subscribers")

  let record = null
  try {
    const raw = await store.get(email)
    record = raw ? JSON.parse(raw) : null
  } catch (err) {
    console.error(`unsubscribe: failed to read/parse record for ${email}:`, err)
  }

  if (record && record.tier === "paid" && record.stripe_subscription_id) {
    await cancelStripeSubscription(record.stripe_subscription_id)
  }

  await store.delete(email)

  return page(
    "Unsubscribed", "Unsubscribed",
    `<p class="post-lede">You've been removed from the Daily Digest. No more emails will be sent to ${escapeHtml(email)}.</p><p><a href="/blog/">Back to the blog</a></p>`,
  )
}
