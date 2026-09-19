/**
 * GET /.netlify/functions/unsubscribe?email=...&token=...
 *
 * One-click unsubscribe. Token is HMAC-SHA256(SUBSCRIBE_SECRET, email).
 * Removes the subscriber from the Netlify Blobs store and returns
 * a confirmation page using the site's existing CSS.
 *
 * This is the ONLY unsubscribe link every digest email carries, regardless
 * of tier — free, legacy, and paid subscribers all get the same link. A
 * paid subscriber (tier: "paid", stripe_subscription_id set by
 * stripe-webhook.mjs on checkout.session.completed) has a real, billing
 * Stripe subscription behind their record. If we just deleted the record,
 * they'd stop receiving email but Stripe would keep charging them with no
 * remaining link between the orphaned subscription and a person — so this
 * handler cancels the Stripe subscription first for paid-tier subscribers.
 * There is no Customer Portal yet, so this link is currently their only
 * self-serve cancellation path.
 *
 * Required env vars: SUBSCRIBE_SECRET, STRIPE_SECRET_KEY
 */
import { getStore } from "@netlify/blobs"
import { createHmac, timingSafeEqual } from "node:crypto"

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

function page(title, heading, bodyHtml, status = 200) {
  return new Response(`<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>${title} | Purplelink LLC</title>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="preload" href="/assets/fonts/fraunces-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/tools/">Tools</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>
    <div id="main-content" class="post-hero">
      <h1>${heading}</h1>
      ${bodyHtml}
    </div>
    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
        <a href="/blog/">Blog</a>
        <a href="/guides/">Guides</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>
  </body>
</html>`, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  })
}

export default async function handler(request) {
  const url = new URL(request.url)
  const email = (url.searchParams.get("email") ?? "").toLowerCase().trim()
  const token = url.searchParams.get("token") ?? ""

  const secret = process.env.SUBSCRIBE_SECRET
  if (!secret || !email || !token) {
    return page(
      "Invalid link", "Invalid link",
      "<p>This unsubscribe link is missing required parameters.</p><p><a href='/blog/digest/'>Back to Daily Digest</a></p>",
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
      "<p>This unsubscribe link is not valid. It may have been altered.</p><p><a href='/blog/digest/'>Back to Daily Digest</a></p>",
      400,
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
    `<p class="post-lede">You've been removed from the Daily Digest. No more emails will be sent to ${email}.</p><p><a href="/blog/digest/">Back to Daily Digest</a></p>`,
  )
}
