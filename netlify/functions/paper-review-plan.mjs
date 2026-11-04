/**
 * The Paper Review annual plan page: see the plan, cancel it, undo a cancel, or ask for a new link.
 *
 *   GET  ?t=<token>      Shows the plan. Changes nothing, so a mail scanner opening the link cannot cancel.
 *   GET  (no token)      The email box.
 *   POST action=cancel|undo, t=<token>   Cancels or restores renewal. Modal checks the link, asks Stripe,
 *                        sends a confirmation email and returns a new link (the old one stops working).
 *   POST action=link, email=<address>    Emails a fresh link to the address on a plan. The answer is the
 *                        same whether or not the address has a plan. 10 per IP and 3 per address a day.
 *
 * The plan link is a signed token for the plan, not a Stripe id, and carries no personal data. Modal
 * (backend/latextools/annual.py) owns the plan; this function only renders and relays.
 * Served at /tools/paper-review/plan/ (netlify.toml rewrite).
 *
 * Required env vars: BACKEND_WEBHOOK_SECRET
 */
import { clientIp, overDailyLimit } from "../lib/ratelimit.mjs"
import { escapeHtml, page } from "../lib/fn-page.mjs"

const MODAL_BASE = "https://ben-ampel--purplelink-latextools-web.modal.run"
const PLAN_URL = "/tools/paper-review/plan/"
const EMAIL_PATTERN = /^[^\s@<>"`\\]{1,64}@[^\s@<>"`\\]{1,190}\.[^\s@<>"`\\]{2,}$/
export const PER_IP_DAILY = 10
export const PER_EMAIL_DAILY = 3
const TITLE = "Your Paper Review plan"
const HELP = "If something looks wrong, reply to any plan email or write to ben@purplelink.llc."

async function modal(path, body, secret) {
  try {
    const r = await fetch(`${MODAL_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-webhook-secret": secret },
      body: JSON.stringify(body),
    })
    let data = {}
    try { data = await r.json() } catch { /* keep {} */ }
    return { status: r.status, data }
  } catch (_) {
    return { status: 0, data: {} }
  }
}

function emailBox(note = "") {
  return page(
    TITLE, TITLE,
    `${note}<p class="post-lede">Enter the email address you used to buy the plan. If it has a plan, we will email a link to that address. The link lasts 60 days.</p>
      <form class="waitlist-form" method="post" action="${PLAN_URL}">
        <input type="hidden" name="action" value="link">
        <input type="email" name="email" required autocomplete="email" aria-label="Email address" placeholder="you@example.com" maxlength="254">
        <button type="submit" class="btn btn-primary">Email me the link</button>
      </form>
      <p>${HELP}</p>`,
  )
}

function expiredLink(reason) {
  const note = reason === "replaced"
    ? "<p>That link has been replaced by a newer one. Use the link in your latest plan email, or ask for a new one below.</p>"
    : "<p>That link has expired or is not valid. Ask for a new one below.</p>"
  return emailBox(note)
}

function reviewsLine(v) {
  return `${v.unused} of ${v.total} reviews unused this year`
}

/** The plan as the page shows it. `v` is the view from Modal; `token` is the link to put in the buttons. */
function planPage(v, token, note = "") {
  const t = escapeHtml(token)
  const form = (action, label, kind) => `<form method="post" action="${PLAN_URL}">
        <input type="hidden" name="action" value="${action}">
        <input type="hidden" name="t" value="${t}">
        <button type="submit" class="btn ${kind}">${label}</button>
      </form>`
  let body
  switch (v.state) {
    case "active":
      body = `<p class="post-lede">Your plan renews on ${escapeHtml(v.date)} for ${escapeHtml(v.amount)}. ${reviewsLine(v)}.</p>
      <p>Cancel any time before then. You keep every review until ${escapeHtml(v.date)}, and nothing more is charged.</p>
      ${form("cancel", "Cancel renewal", "btn-secondary")}`
      break
    case "cancelling":
      body = `<p class="post-lede">Your plan will not renew. It ends on ${escapeHtml(v.date)}, and you keep your reviews until then. ${reviewsLine(v)}.</p>
      <p>Changed your mind? You can turn renewal back on until that date.</p>
      ${form("undo", "Keep my plan", "btn-primary")}`
      break
    case "problem":
      body = `<p class="post-lede">The last renewal payment did not go through. Your reviews stay available until ${escapeHtml(v.date)}. ${reviewsLine(v)}.</p><p>${HELP}</p>`
      break
    case "revoked":
      body = `<p class="post-lede">This plan was refunded or disputed, so its reviews are no longer available.</p><p>${HELP}</p>`
      break
    default:
      body = `<p class="post-lede">This plan ended on ${escapeHtml(v.date)}.</p><p><a href="/tools/paper-review/">See Paper Review options</a></p>`
  }
  return page(TITLE, TITLE, `${note}${body}<p><a href="/tools/paper-review/">Back to Paper Review</a></p>`)
}

function problemPage(heading, text, status = 502) {
  return page(heading, heading, `<p>${text}</p><p>${HELP}</p>`, status)
}

export default async function handler(request, context) {
  const secret = process.env.BACKEND_WEBHOOK_SECRET
  if (!secret) return new Response("Server misconfigured", { status: 500 })

  if (request.method === "POST") {
    const body = Object.fromEntries(new URLSearchParams(await request.text().catch(() => "")))
    const action = String(body.action ?? "")

    if (action === "link") {
      const email = String(body.email ?? "").toLowerCase().trim()
      if (email.length > 254 || !EMAIL_PATTERN.test(email)) {
        return emailBox("<p>That does not look like an email address. Check it and try again.</p>")
      }
      if ((await overDailyLimit("plan-ip", clientIp(request), PER_IP_DAILY)) || (await overDailyLimit("plan-email", email, PER_EMAIL_DAILY))) {
        return page("Try again tomorrow", "Try again tomorrow", `<p>That is more requests than we can take today. ${HELP}</p>`, 429)
      }
      // Same page whether or not the address has a plan.
      const work = modal("/paper-review/annual-link", { email }, secret)
      if (context?.waitUntil) context.waitUntil(work)
      else await work
      return page(
        "Check your email", "Check your email",
        `<p class="post-lede">If ${escapeHtml(email)} has a Paper Review plan, we have emailed a link to it. The link lasts 60 days.</p><p>Nothing arrived? Check spam, or write to ben@purplelink.llc.</p>`,
      )
    }

    if (action === "cancel" || action === "undo") {
      const token = String(body.t ?? "")
      if (!token || token.length > 400) return expiredLink("invalid")
      if (await overDailyLimit("plan-ip", clientIp(request), PER_IP_DAILY * 5)) {
        return page("Try again tomorrow", "Try again tomorrow", `<p>That is more requests than we can take today. ${HELP}</p>`, 429)
      }
      const res = await modal(`/paper-review/annual-${action}`, { token }, secret)
      if (res.status === 404) return expiredLink("invalid")
      if (res.status === 410) return expiredLink("replaced")
      if (res.status === 409) return problemPage("This plan has ended", "There is nothing left to change on this plan.", 409)
      if (res.status !== 200) {
        return problemPage("That did not go through", "We could not reach the billing system. Nothing was changed. Try again in a minute.")
      }
      const note = action === "cancel"
        ? "<p>Done. Your plan will not renew. We emailed a confirmation.</p>"
        : "<p>Done. Your plan will renew again. We emailed a confirmation.</p>"
      return planPage(res.data, res.data.token || token, note)
    }
    return new Response("Bad request", { status: 400 })
  }

  if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed", { status: 405 })

  const token = new URL(request.url).searchParams.get("t")
  if (!token) return emailBox()
  if (token.length > 400) return expiredLink("invalid")
  const res = await modal("/paper-review/annual-plan", { token }, secret)
  if (res.status === 404) return expiredLink("invalid")
  if (res.status === 410) return expiredLink("replaced")
  if (res.status !== 200) return problemPage("Plan unavailable", "We could not load your plan just now. Try again in a minute.")
  return planPage(res.data, token)
}
