/**
 * The group page for a Lab Plus plan: a member opens the group link, sees how many reviews are left, and starts one.
 *
 *   GET  ?k=<group key>   Shows how many reviews are available and a button. Changes nothing: link previews and mail
 *                         scanners open GETs, and none of them may use up a review.
 *   POST k=<group key>    Claims one review from the plan (Modal /lab/member-claim) and answers 303 to the paper
 *                         review upload page that review opens. 30 per IP a day.
 *
 * The group key (`lg_...`) names the plan's group link only. This page never shows the plan owner's email or any plan
 * detail beyond its name and how many reviews are left. Modal owns the plan; this function only renders and relays.
 * Served at /labs/start/ (netlify.toml rewrite).
 *
 * Required env vars: BACKEND_WEBHOOK_SECRET
 */
import { clientIp, overDailyLimit } from "../lib/ratelimit.mjs"
import { escapeHtml, page } from "../lib/fn-page.mjs"

const MODAL_BASE = "https://ben-ampel--purplelink-latextools-web.modal.run"
const START_URL = "/labs/start/"
const UPLOAD_PREFIX = "https://purplelink.llc/tools/paper-review/upload/?direct_token="
const KEY_PATTERN = /^lg_[A-Za-z0-9_-]{16,64}$/
export const PER_IP_DAILY = 30
const STYLES = { styles: ["/labs/plan.css"] }
const TITLE = "Start a review"
const NEXT_STEPS = `<p class="lab-note">The button uses one review from your group's plan and opens the upload page. Have the manuscript ready first. On the next page, upload it (PDF or Word .docx) and pick the domain profile that best matches it. The review starts on Submit and typically takes 4 to 8 minutes. The report is emailed as a PDF.</p>`

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

const shell = (title, heading, body, status = 200) =>
  page(title, heading, `<div class="lab-start">${body}</div>`, status, STYLES)

const invalidKey = () =>
  shell("Link not valid", "This link is not valid", "<p>Ask your group lead for the current link.</p>", 404)

const planEnded = () =>
  shell("Plan not active", "This plan is not active", "<p>Ask your group lead about the plan.</p>", 410)

const problem = () =>
  shell("Try again", "That did not go through", "<p>The review system did not answer. No review was used. Try again in a minute. If it keeps failing, ask your group lead to write to ben@purplelink.llc.</p>", 502)

function noneLeft(nextGrant) {
  const when = typeof nextGrant === "string" && nextGrant ? ` The next batch arrives on ${escapeHtml(nextGrant)}.` : ""
  return shell("None available", "No reviews available right now", `<p class="post-lede">This month's reviews for your group are all used.${when}</p><p>Ask your group lead if you need one sooner.</p>`, 409)
}

function startPage(v, key) {
  const n = Number.isInteger(v.available) ? v.available : 0
  if (n < 1) return noneLeft(v.next_grant)
  const plan = typeof v.plan_name === "string" && v.plan_name ? `<p class="lab-note">Plan: ${escapeHtml(v.plan_name)}</p>` : ""
  return shell(TITLE, TITLE, `${plan}<p class="post-lede lab-count">${n} ${n === 1 ? "review" : "reviews"} available</p>
      ${NEXT_STEPS}
      <form method="post" action="${START_URL}">
        <input type="hidden" name="k" value="${escapeHtml(key)}">
        <button type="submit" class="btn btn-primary">Start a review</button>
      </form>`)
}

const live = (state) => state === "active" || state === "cancelling"

export default async function handler(request, context) {
  const secret = process.env.BACKEND_WEBHOOK_SECRET
  if (!secret) return new Response("Server misconfigured", { status: 500 })

  if (request.method === "POST") {
    const body = Object.fromEntries(new URLSearchParams(await request.text().catch(() => "")))
    const key = String(body.k ?? "")
    if (!KEY_PATTERN.test(key)) return invalidKey()
    if (await overDailyLimit("lab-start-ip", clientIp(request), PER_IP_DAILY)) {
      return shell("Try again tomorrow", "Try again tomorrow", "<p>The daily limit for this page is reached. Ask your group lead for help.</p>", 429)
    }
    const res = await modal("/lab/member-claim", { k: key }, secret)
    if (res.status === 200) {
      const url = res.data?.start_url
      if (typeof url !== "string" || !url.startsWith(UPLOAD_PREFIX)) return problem()
      return new Response(null, { status: 303, headers: { Location: url, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } })
    }
    if (res.status === 409) return noneLeft(res.data?.next_grant)
    if (res.status === 404) return invalidKey()
    if (res.status === 410) return planEnded()
    return problem()
  }

  if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed", { status: 405 })

  const key = new URL(request.url).searchParams.get("k") || ""
  if (!KEY_PATTERN.test(key)) return invalidKey()
  const res = await modal("/lab/group-view", { k: key }, secret)
  if (res.status === 404) return invalidKey()
  if (res.status !== 200) return problem()
  if (!live(res.data?.state)) return planEnded()
  return startPage(res.data, key)
}
