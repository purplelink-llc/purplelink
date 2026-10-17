/**
 * Billing portal for paying Daily Digest subscribers, opened only from an emailed, short-lived link.
 *
 *   GET  ?t=<token>         A link emailed to the subscriber (valid 30 minutes). 303 to a Stripe billing
 *                           portal limited to invoices, the card and cancelling at period end. A bad or
 *                           expired token shows the request form instead.
 *   GET  (anything else)    The request form. Old digest footer links (?email=...&token=...) land here:
 *                           that permanent token no longer opens anything, because a forwarded digest
 *                           would have handed billing access to whoever received it.
 *   POST email=<address>    Asks for a link. The answer is the same whether or not the address has a paid
 *                           subscription; the link goes only to that address, and only when it does.
 *
 * Token and portal configuration: netlify/lib/portal-link.mjs (kind "digest-portal", subject = email).
 * Limits: 10 requests per IP and 3 per address per day.
 *
 * Required env vars: SUBSCRIBE_SECRET, STRIPE_SECRET_KEY, RESEND_API_KEY
 */
import { getStore } from "@netlify/blobs"
import { clientIp, overDailyLimit } from "../lib/ratelimit.mjs"
import { escapeHtml, page } from "../lib/fn-page.mjs"
import {
  SITE_ORIGIN, createPortalSession, sendPortalEmail, signPortalToken, verifyPortalToken,
} from "../lib/portal-link.mjs"

const KIND = "digest-portal"
const FUNCTION_URL = `${SITE_ORIGIN}/.netlify/functions/subscription-portal`
const EMAIL_PATTERN = /^[^\s@<>"`\\]{1,64}@[^\s@<>"`\\]{1,190}\.[^\s@<>"`\\]{2,}$/
export const PER_IP_DAILY = 10
export const PER_EMAIL_DAILY = 3

function requestForm(note = "") {
  return page(
    "Manage your subscription",
    "Manage your subscription",
    `${note}<p class="post-lede">Enter the email address your Daily Digest subscription uses. If it has a paid subscription, we will email a link to that address. The link opens the billing page and works for 30 minutes.</p>
      <form class="waitlist-form" method="post" action="/.netlify/functions/subscription-portal">
        <input type="email" name="email" required autocomplete="email" aria-label="Email address" placeholder="you@example.com" maxlength="254">
        <button type="submit" class="btn btn-primary">Email me the link</button>
      </form>
      <p><a href="/blog/">Back to the blog</a></p>`,
  )
}

async function mailLinkIfPaid(email, secret) {
  try {
    const raw = await getStore("subscribers").get(email)
    const record = raw ? JSON.parse(raw) : null
    if (!record || record.tier !== "paid" || !record.stripe_customer_id) return
    const link = `${FUNCTION_URL}?t=${encodeURIComponent(signPortalToken(KIND, email, secret))}`
    if (!(await sendPortalEmail(email, link, "your Purplelink Daily Digest subscription"))) {
      console.error("subscription-portal: email failed")
    }
  } catch (err) {
    console.error("subscription-portal: lookup failed", err?.message)
  }
}

export default async function handler(request, context) {
  const secret = process.env.SUBSCRIBE_SECRET
  const stripeKey = process.env.STRIPE_SECRET_KEY
  if (!secret || !stripeKey) return new Response("Server misconfigured", { status: 500 })

  if (request.method === "POST") {
    const body = Object.fromEntries(new URLSearchParams(await request.text().catch(() => "")))
    const email = String(body.email ?? "").toLowerCase().trim()
    if (email.length > 254 || !EMAIL_PATTERN.test(email)) {
      return requestForm("<p>That does not look like an email address. Check it and try again.</p>")
    }
    if ((await overDailyLimit("portal-ip", clientIp(request), PER_IP_DAILY)) || (await overDailyLimit("portal-email", email, PER_EMAIL_DAILY))) {
      return page("Try again tomorrow", "Try again tomorrow", "<p>That is more requests than we can take today. If you are locked out, email ben@purplelink.llc and we will help.</p>", 429)
    }
    // Same page and same timing whether or not the address subscribes.
    const work = mailLinkIfPaid(email, secret)
    if (context?.waitUntil) context.waitUntil(work)
    else await work
    return page(
      "Check your email", "Check your email",
      `<p class="post-lede">If ${escapeHtml(email)} has a paid Daily Digest subscription, we have emailed a link to it. The link works for 30 minutes.</p><p>Nothing arrived? Check spam, or email ben@purplelink.llc.</p><p><a href="/blog/">Back to the blog</a></p>`,
    )
  }

  if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed", { status: 405 })

  const url = new URL(request.url)
  const token = url.searchParams.get("t")
  if (token) {
    const email = verifyPortalToken(KIND, token, secret)
    if (!email) return requestForm("<p>That link has expired or is not valid. Request a new one below.</p>")
    let customer = ""
    try {
      const raw = await getStore("subscribers").get(email)
      const record = raw ? JSON.parse(raw) : null
      if (record?.tier === "paid" && typeof record.stripe_customer_id === "string") customer = record.stripe_customer_id
    } catch (err) {
      console.error("subscription-portal: lookup failed", err?.message)
    }
    if (!customer) return requestForm("<p>No paid subscription is on file for that address. If you think that is wrong, email ben@purplelink.llc.</p>")
    const portal = await createPortalSession(customer, `${SITE_ORIGIN}/blog/`, stripeKey)
    if (!portal) {
      return page("Billing page unavailable", "Billing page unavailable", "<p>We could not open the billing page. Try again in a minute, or email ben@purplelink.llc and we will cancel or update it for you.</p>", 502)
    }
    return new Response(null, { status: 303, headers: { Location: portal, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } })
  }
  return requestForm()
}
