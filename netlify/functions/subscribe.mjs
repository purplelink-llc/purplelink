/**
 * POST /.netlify/functions/subscribe
 * body: { email: "...", ref?: "<referral code>" }
 *
 * Double opt-in. A new address is NOT added: it gets a confirmation email with a signed link that
 * lasts 3 days (netlify/lib/confirm-token.mjs), and joins the "subscribers" Blobs store only when it
 * confirms (confirm-signup.mjs, which calls netlify/lib/digest-signup.mjs). Nothing is stored before then,
 * so a stranger cannot enrol or mail-bomb an address beyond one confirmation email, and the digest cron
 * (which reads "subscribers") only ever mails confirmed addresses.
 *
 * The answer is the same ({ ok: true, confirm: true }) whether the address is new or already subscribed,
 * so the form does not reveal who subscribes; an address already on the list gets no email. Its
 * missing referral code or tier is still backfilled quietly (the old behaviour). The referral link is
 * shown on the page the confirmation link opens.
 *
 * Paid digest subscriptions created by Stripe checkout skip this: payment is consent, and
 * stripe-webhook.mjs writes those records directly.
 *
 * Abuse limits: Origin check, 30 requests per IP and 5 per address per day (netlify/lib/ratelimit.mjs).
 *
 * Required env vars: SUBSCRIBE_SECRET, RESEND_API_KEY
 */
import { getStore } from "@netlify/blobs"
import { signConfirmToken } from "../lib/confirm-token.mjs"
import { referralCode } from "../lib/digest-signup.mjs"
import { clientIp, overDailyLimit } from "../lib/ratelimit.mjs"

// Abuse limits (security baseline 2026-10-16). Generous for a real person on a shared
// network; they stop a script from filling the list or mailing one address repeatedly.
export const PER_IP_DAILY = 30
export const PER_EMAIL_DAILY = 5
const ALLOWED_ORIGINS = new Set(["https://purplelink.llc", "https://www.purplelink.llc"])

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

const SITE_ORIGIN = "https://purplelink.llc"
const FROM_EMAIL = "Purplelink Daily Digest <ben@purplelink.llc>"
const RESEND_API_URL = "https://api.resend.com/emails"

async function sendConfirmation(email, link) {
  const apiKey = process.env.RESEND_API_KEY
  if (!apiKey) return false
  const text = `Someone, probably you, asked for the Purplelink Daily Digest at this address. To get it, confirm with this link:\n\n${link}\n\nThe link works for 3 days. After you confirm you get one short email per day, and every email has an unsubscribe link. If you did not ask, ignore this email and nothing happens.\n\nPurplelink LLC, Atlanta, Georgia`
  const html = `<p>Someone, probably you, asked for the Purplelink Daily Digest at this address. To get it, confirm with this link:</p><p><a href="${link}">Confirm my email</a></p><p>The link works for 3 days. After you confirm you get one short email per day, and every email has an unsubscribe link. If you did not ask, ignore this email and nothing happens.</p><p>Purplelink LLC, Atlanta, Georgia</p>`
  try {
    const resp = await fetch(RESEND_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ from: FROM_EMAIL, to: [email], subject: "Confirm your Daily Digest signup", text, html }),
    })
    return resp.ok
  } catch {
    return false
  }
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return json(405, { error: "method_not_allowed" })
  }

  // A browser on another site sends its own Origin; curl and same-origin posts may send none.
  const origin = request.headers.get("origin")
  if (origin && !ALLOWED_ORIGINS.has(origin)) {
    const preview = [process.env.DEPLOY_PRIME_URL, process.env.DEPLOY_URL]
    if (!preview.includes(origin)) return json(403, { error: "forbidden_origin" })
  }
  if (await overDailyLimit("subscribe-ip", clientIp(request), PER_IP_DAILY)) {
    return json(429, { error: "rate_limited" })
  }

  let body
  try {
    body = await request.json()
  } catch {
    return json(400, { error: "invalid_json" })
  }

  const email = (body?.email ?? "").toLowerCase().trim()
  if (!email || email.length > 254 || !/^[^\s@<>"`\\]+@[^\s@<>"`\\]+\.[^\s@<>"`\\]+$/.test(email)) {
    return json(400, { error: "invalid_email" })
  }
  if (await overDailyLimit("subscribe-email", email, PER_EMAIL_DAILY)) {
    return json(429, { error: "rate_limited" })
  }
  const refCode = typeof body?.ref === "string" ? body.ref.trim().slice(0, 32) : ""

  const secret = process.env.SUBSCRIBE_SECRET
  if (!secret) {
    console.error("subscribe: SUBSCRIBE_SECRET not set")
    return json(500, { error: "server_error" })
  }

  const store = getStore("subscribers")
  const existing = await store.get(email)
  if (existing) {
    // Already subscribed: no email, same answer. Backfill what older records lack, as before.
    try {
      const record = JSON.parse(existing)
      let changed = false
      if (!record.referralCode) {
        record.referralCode = referralCode(email, secret)
        await getStore("referral-index").set(record.referralCode, email)
        changed = true
      }
      if (!record.tier) {
        record.tier = "legacy"
        changed = true
      }
      if (changed) await store.set(email, JSON.stringify(record))
    } catch (err) {
      console.error("subscribe: backfill failed", err)
    }
    return json(200, { ok: true, confirm: true })
  }

  const token = signConfirmToken("digest-confirm", { e: email, r: refCode }, secret)
  const link = `${SITE_ORIGIN}/.netlify/functions/confirm-signup?t=${encodeURIComponent(token)}`
  if (!(await sendConfirmation(email, link))) {
    console.error("subscribe: confirmation email failed")
    return json(502, { error: "send_failed" })
  }
  return json(200, { ok: true, confirm: true })
}
