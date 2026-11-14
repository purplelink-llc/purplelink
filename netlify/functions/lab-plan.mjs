/**
 * The lab plan page (Lab and Lab Plus): see the plan and its monthly batches, cancel or restore renewal, replace the
 * group link, open the billing portal, or ask for a new plan link.
 *
 *   GET  ?t=<token>      Shows the plan. Changes nothing, so a mail scanner opening the link cannot cancel.
 *   GET  (no token)      The email box.
 *   POST action=cancel|undo, t=<token>   Cancels or restores renewal. Modal checks the link, asks Stripe,
 *                        sends a confirmation email and returns a new link (the old one stops working).
 *   POST action=rotate, t=<token>        Lab Plus: replaces the group link. The old group link stops working.
 *   POST action=portal, t=<token>        303 to the Stripe billing portal (card, invoices). The Stripe customer id
 *                        comes back from Modal for this one call and is never put on a page.
 *   POST action=link, email=<address>    Emails a fresh plan link to the address on a plan. The answer is the
 *                        same whether or not the address has a plan. 10 per IP and 3 per address a day.
 *
 * The plan link is a signed token for the plan (`lab_...`), not a Stripe id, and carries no personal data. Modal
 * (backend lab routes) owns the plan; this function only renders and relays. Everything Modal sends is escaped.
 * Served at /labs/plan/ (netlify.toml rewrite).
 *
 * Required env vars: BACKEND_WEBHOOK_SECRET. The billing portal also needs a Stripe key (STRIPE_SECRET_KEY, and
 * STRIPE_SECRET_KEY_NEW once the new account is set; each is tried in turn, netlify/lib/portal-link.mjs).
 */
import { clientIp, overDailyLimit } from "../lib/ratelimit.mjs"
import { escapeHtml, page } from "../lib/fn-page.mjs"
import { createPortalSession } from "../lib/portal-link.mjs"

const MODAL_BASE = "https://ben-ampel--purplelink-latextools-web.modal.run"
const SITE = "https://purplelink.llc"
const PLAN_URL = "/labs/plan/"
const STYLES = { styles: ["/labs/plan.css"] }
const EMAIL_PATTERN = /^[^\s@<>"`\\]{1,64}@[^\s@<>"`\\]{1,190}\.[^\s@<>"`\\]{2,}$/
const TOKEN_PATTERN = /^lab_[^\s"'<>`\\]+$/
const CUSTOMER_PATTERN = /^cus_[A-Za-z0-9_]+$/
export const PER_IP_DAILY = 10
export const PER_EMAIL_DAILY = 3
const TITLE = "Your lab plan"
const MAILTO = `<a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>`
const HELP = `If something looks wrong, reply to any plan email or write to ${MAILTO}.`

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

const shell = (title, heading, body, status = 200) => page(title, heading, body, status, STYLES)

function emailBox(note = "") {
  return shell(
    TITLE, TITLE,
    `${note}<p class="post-lede">Enter the email address you used to buy the plan. If it has a plan, we will email a link to that address.</p>
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

function problemPage(heading, text, status = 502) {
  return shell(heading, heading, `<p>${text}</p><p>${HELP}</p>`, status)
}

function tooMany() {
  return shell("Try again tomorrow", "Try again tomorrow", `<p>That is more requests than we can take today. ${HELP}</p>`, 429)
}

const validToken = (t) => typeof t === "string" && t.length > 0 && t.length <= 400 && TOKEN_PATTERN.test(t)
const siteUrl = (u, prefix = `${SITE}/`) => (typeof u === "string" && u.startsWith(prefix) ? u : "")

const STATE_LABEL = { active: "Renews on", cancelling: "Ends on", problem: "Paid through", ended: "Ended on" }

function stateSentence(v) {
  const date = escapeHtml(v.date ?? "")
  switch (v.state) {
    case "active":
      return `Your plan renews on ${date}. Each month it adds a new batch of reviews.`
    case "cancelling":
      return `Your plan will not renew. It ends on ${date}. Reviews you already have can be used until the date shown on each batch.`
    case "problem":
      return `The last payment did not go through. Your plan is paid through ${date}. Update your card under billing to keep it.`
    case "revoked":
      return "This plan was refunded or disputed, so its reviews are no longer available."
    default:
      return `This plan ended on ${date}.`
  }
}

function reviewWord(n) {
  return Number(n) === 1 ? "1 review" : `${escapeHtml(n)} reviews`
}

function tokenRow(tok, expired) {
  const short = escapeHtml(tok.short ?? "")
  const used = tok.used === true
  const start = siteUrl(tok.start_url)
  let status
  let link
  if (used) {
    status = `<span class="lab-chip">Used</span>`
    const items = (Array.isArray(tok.followups) ? tok.followups : []).map((f) => {
      const name = escapeHtml(f?.name ?? "Follow-up")
      const url = siteUrl(f?.url)
      if (f?.used === true || !url) return `<li>${name}, used</li>`
      return `<li><a href="${escapeHtml(url)}">${name}</a></li>`
    })
    link = items.length ? `<ul>${items.join("")}</ul>` : "Used"
  } else if (expired || !start) {
    status = `<span class="lab-chip">${expired ? "Expired" : "Unavailable"}</span>`
    link = ""
  } else {
    status = `<span class="lab-chip is-unused">Unused</span>`
    link = `<a class="btn btn-primary" href="${escapeHtml(start)}">Start</a>
          <input class="lab-copy" type="text" readonly value="${escapeHtml(start)}" aria-label="Link for review ${short}">`
  }
  return `<tr>
        <td data-label="Review"><code>${short}</code></td>
        <td data-label="Status">${status}</td>
        <td data-label="Link or follow-ups">${link}</td>
      </tr>`
}

function batchesHtml(v) {
  const grants = Array.isArray(v.grants) ? [...v.grants] : []
  if (!grants.length) return `<p class="lab-note">No reviews have been issued yet.</p>`
  // Newest first, by the date label ("13 November 2026"); labels that do not parse keep Modal's order.
  const when = (g) => Date.parse(g?.label ?? "")
  if (grants.every((g) => Number.isFinite(when(g)))) grants.sort((a, b) => when(b) - when(a))
  return grants.map((g) => {
    const expired = g?.expired === true
    const tokens = Array.isArray(g?.tokens) ? g.tokens : []
    const label = escapeHtml(g?.label ?? "")
    const until = escapeHtml(g?.valid_until ?? "")
    const meta = expired
      ? `${reviewWord(g?.count)} issued. These expired on ${until}.`
      : `${reviewWord(g?.count)} issued, ${escapeHtml(g?.unused ?? 0)} unused. Use them by ${until}.`
    return `<section class="lab-batch${expired ? " is-expired" : ""}" aria-label="Batch of ${label}">
      <h2>Batch of ${label}</h2>
      <p class="lab-batch-meta">${meta}</p>
      <table class="lab-table">
        <caption>Reviews in the batch of ${label}</caption>
        <thead><tr><th scope="col" class="col-id">Review</th><th scope="col" class="col-status">Status</th><th scope="col">Link or follow-ups</th></tr></thead>
        <tbody>
      ${tokens.map((t) => tokenRow(t ?? {}, expired)).join("\n      ")}
        </tbody>
      </table>
    </section>`
  }).join("\n    ")
}

/** The plan as the page shows it. `v` is the view from Modal; `token` is the link to put in the buttons. */
function planPage(v, token, note = "") {
  const t = escapeHtml(token)
  const form = (action, label, kind) => `<form method="post" action="${PLAN_URL}">
        <input type="hidden" name="action" value="${action}">
        <input type="hidden" name="t" value="${t}">
        <button type="submit" class="btn ${kind}">${label}</button>
      </form>`
  const revoked = v.state === "revoked"
  const hasEnd = Boolean(STATE_LABEL[v.state])
  const next = v.next_grant ? escapeHtml(v.next_grant) : "None coming"
  const billing = v.billing === "yearly" ? "billed yearly" : "billed monthly"

  const summary = revoked ? "" : `<dl class="lab-summary">
      <div><dt>Plan</dt><dd>${escapeHtml(v.plan_name ?? "Lab")}</dd><dd class="lab-note">${escapeHtml(v.reviews_per_month ?? "")} reviews a month, ${billing}</dd></div>
      ${hasEnd ? `<div><dt>${STATE_LABEL[v.state]}</dt><dd>${escapeHtml(v.date ?? "")}</dd></div>` : ""}
      <div><dt>Next batch</dt><dd>${next}</dd></div>
      <div><dt>Reviews left</dt><dd>${escapeHtml(v.unused ?? 0)}</dd></div>
    </dl>`

  const groupUrl = siteUrl(v.group_url, `${SITE}/labs/start/?k=`)
  const group = !revoked && groupUrl ? `<section class="lab-group" aria-labelledby="lab-group-title">
      <h2 id="lab-group-title">Group link</h2>
      <p class="lab-note">Share this link with your group. Each time someone opens it and presses the button, one review from this plan is used.</p>
      <input class="lab-copy" type="text" readonly value="${escapeHtml(groupUrl)}" aria-label="Group link">
      ${form("rotate", "Replace this link", "btn-secondary")}
      <p class="lab-note">The old link stops working as soon as you replace it.</p>
    </section>` : ""

  const buttons = []
  if (v.state === "active") buttons.push(form("cancel", "Cancel renewal", "btn-secondary"))
  if (v.state === "cancelling") buttons.push(form("undo", "Keep my plan", "btn-primary"))
  if (!revoked && v.customer) buttons.push(form("portal", "Billing, card and invoices", "btn-secondary"))
  const actions = buttons.length ? `<div class="lab-actions">${buttons.join("")}</div>` : ""

  const explain = revoked ? `<p>${HELP}</p>` : `<p class="lab-note">Each month's reviews can be used until the date shown on their batch. Every reviewed paper includes one Revision Review and one Response Review.</p>`
  const batches = revoked ? "" : batchesHtml(v)
  const help = v.state === "problem" ? `<p>${HELP}</p>` : ""

  return shell(TITLE, TITLE, `${note}<p class="post-lede">${stateSentence(v)}</p>
    ${summary}
    ${group}
    ${actions}
    ${explain}
    ${help}
    ${batches}
    <p><a href="/tools/paper-review/">Back to Paper Review</a></p>`)
}

async function portalRedirect(token, secret) {
  const res = await modal("/lab/plan", { token }, secret)
  if (res.status === 404) return expiredLink("invalid")
  if (res.status === 410) return expiredLink("replaced")
  const customer = res.data?.customer
  if (res.status !== 200 || typeof customer !== "string" || !CUSTOMER_PATTERN.test(customer)) {
    return problemPage("Billing page unavailable", `We could not open the billing page. Try again in a minute, or write to ${MAILTO} and we will update your card or invoice for you.`)
  }
  const returnUrl = `${SITE}${PLAN_URL}?t=${encodeURIComponent(token)}`
  const url = await createPortalSession(customer, returnUrl, process.env.STRIPE_SECRET_KEY || "")
  if (!url) {
    return problemPage("Billing page unavailable", `We could not open the billing page. Try again in a minute, or write to ${MAILTO} and we will update your card or invoice for you.`)
  }
  return new Response(null, { status: 303, headers: { Location: url, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } })
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
      if ((await overDailyLimit("lab-plan-ip", clientIp(request), PER_IP_DAILY)) || (await overDailyLimit("lab-plan-email", email, PER_EMAIL_DAILY))) {
        return tooMany()
      }
      // Same page whether or not the address has a plan.
      const work = modal("/lab/link", { email }, secret)
      if (context?.waitUntil) context.waitUntil(work)
      else await work
      return shell(
        "Check your email", "Check your email",
        `<p class="post-lede">If ${escapeHtml(email)} has a lab plan, we have emailed a link to it.</p><p>Nothing arrived? Check spam, or write to ${MAILTO}.</p>`,
      )
    }

    if (action === "cancel" || action === "undo" || action === "rotate" || action === "portal") {
      const token = String(body.t ?? "")
      if (!validToken(token)) return expiredLink("invalid")
      if (await overDailyLimit("lab-plan-act-ip", clientIp(request), PER_IP_DAILY * 5)) return tooMany()

      if (action === "portal") return portalRedirect(token, secret)

      const route = action === "rotate" ? "/lab/rotate-group-link" : `/lab/${action}`
      const res = await modal(route, { token }, secret)
      if (res.status === 404) return expiredLink("invalid")
      if (res.status === 410) return expiredLink("replaced")
      if (res.status === 409) {
        if (res.data?.error === "not_plus") return problemPage("No group link on this plan", "Only Lab Plus plans have a group link.", 409)
        return problemPage("This plan has ended", "There is nothing left to change on this plan.", 409)
      }
      if (res.status !== 200) {
        return problemPage("That did not go through", "We could not reach the billing system. Nothing was changed. Try again in a minute.")
      }
      const note = {
        cancel: "<p>Done. Your plan will not renew. We emailed a confirmation.</p>",
        undo: "<p>Done. Your plan will renew again. We emailed a confirmation.</p>",
        rotate: "<p>Done. The old group link no longer works. The new one is below. Send it to your group.</p>",
      }[action]
      const next = typeof res.data.token === "string" && validToken(res.data.token) ? res.data.token : token
      return planPage(res.data, next, note)
    }
    return new Response("Bad request", { status: 400 })
  }

  if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed", { status: 405 })

  const token = new URL(request.url).searchParams.get("t")
  if (!token) return emailBox()
  if (!validToken(token)) return expiredLink("invalid")
  const res = await modal("/lab/plan", { token }, secret)
  if (res.status === 404) return expiredLink("invalid")
  if (res.status === 410) return expiredLink("replaced")
  if (res.status !== 200) return problemPage("Plan unavailable", "We could not load your plan just now. Try again in a minute.")
  return planPage(res.data, token)
}
