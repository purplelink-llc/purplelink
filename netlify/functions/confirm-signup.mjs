/**
 * Step two of double opt-in for the Daily Digest and the researcher checklist.
 *
 *   GET  ?t=<token>   The link in the confirmation email. Shows a page with one button and changes nothing, so
 *                     a mail scanner that follows the link cannot confirm an address for its owner.
 *   POST t=<token>    The button. Digest: adds the subscriber (digest-signup.mjs) and shows their referral
 *                     link. Checklist: stores the record and emails the checklist PDF. Safe to press twice.
 *
 * Tokens are signed and expire after 3 days (netlify/lib/confirm-token.mjs, kinds "digest-confirm" and
 * "checklist-confirm"). A bad or expired token gets a page that points back to the signup form.
 *
 * Required env vars: SUBSCRIBE_SECRET, RESEND_API_KEY
 */
import { escapeHtml, page } from "../lib/fn-page.mjs"
import { verifyConfirmToken } from "../lib/confirm-token.mjs"
import { addDigestSubscriber } from "../lib/digest-signup.mjs"
import { completeChecklistSignup } from "./checklist-signup.mjs"

const SITE_ORIGIN = "https://purplelink.llc"
const EMAIL_PATTERN = /^[^\s@<>"`\\]{1,64}@[^\s@<>"`\\]{1,190}\.[^\s@<>"`\\]{2,}$/

function expired() {
  return page(
    "Link expired", "This link has expired",
    `<p class="post-lede">Confirmation links work for 3 days, and this one is past that or not valid. Sign up again and we will send a fresh one.</p><p><a href="/blog/">Daily Digest</a> &middot; <a href="/checklist/">Submission checklist</a></p>`,
    400,
  )
}

function identify(token, secret) {
  const digest = verifyConfirmToken("digest-confirm", token, secret)
  if (digest && typeof digest.e === "string" && EMAIL_PATTERN.test(digest.e)) {
    return { kind: "digest", email: digest.e, ref: typeof digest.r === "string" ? digest.r.slice(0, 32) : "" }
  }
  const list = verifyConfirmToken("checklist-confirm", token, secret)
  if (list && typeof list.e === "string" && EMAIL_PATTERN.test(list.e)) {
    return { kind: "checklist", email: list.e, source: typeof list.p === "string" ? list.p : "" }
  }
  return null
}

export default async function handler(request) {
  const secret = process.env.SUBSCRIBE_SECRET
  if (!secret) return new Response("Server misconfigured", { status: 500 })
  if (request.method !== "GET" && request.method !== "HEAD" && request.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD, POST" } })
  }

  let token = new URL(request.url).searchParams.get("t") ?? ""
  if (request.method === "POST") {
    const body = Object.fromEntries(new URLSearchParams(await request.text().catch(() => "")))
    if (typeof body.t === "string" && body.t) token = body.t
  }
  const who = identify(token, secret)
  if (!who) return expired()

  const what = who.kind === "digest" ? "the Purplelink Daily Digest" : "the Purplelink submission checklist"
  if (request.method !== "POST") {
    return page(
      "Confirm your email", "Confirm your email",
      `<p class="post-lede">Confirm ${escapeHtml(who.email)} for ${what}?${who.kind === "checklist" ? " The checklist is emailed right away." : ""}</p>
      <form method="post" action="/.netlify/functions/confirm-signup">
        <input type="hidden" name="t" value="${escapeHtml(token)}">
        <button type="submit" class="btn btn-primary">Confirm my email</button>
      </form>
      <p>Did not ask for this? Close the page and nothing happens.</p>`,
    )
  }

  try {
    if (who.kind === "digest") {
      const code = await addDigestSubscriber(who.email, who.ref, secret)
      const share = `${SITE_ORIGIN}/blog/?ref=${encodeURIComponent(code)}`
      return page(
        "Subscribed", "You are subscribed",
        `<p class="post-lede">${escapeHtml(who.email)} will get the next Daily Digest. Every email has an unsubscribe link.</p>
        <p>Know someone who would like it? Your referral link: <a href="${escapeHtml(share)}">${escapeHtml(share)}</a></p>
        <p><a href="/blog/">Back to the blog</a></p>`,
      )
    }
    const result = await completeChecklistSignup(who.email, who.source)
    if (result === "failed") {
      return page(
        "Could not send", "We could not send the checklist",
        `<p class="post-lede">The email did not go through. Press the button again in a minute, or <a href="/assets/downloads/submission-checklist.pdf" download>download the checklist now</a>.</p>`,
        502,
      )
    }
    return page(
      "Confirmed", "You are confirmed",
      `<p class="post-lede">${result === "sent" ? "The checklist is on its way to " : "The checklist was just sent to "}${escapeHtml(who.email)}. You can also <a href="/assets/downloads/submission-checklist.pdf" download>download it now</a>.</p>
      <p><a href="/tools/">Back to the tools</a></p>`,
    )
  } catch (err) {
    console.error("confirm-signup: storage failed", err?.message)
    return page("Try again", "Something went wrong", "<p class=\"post-lede\">We could not finish just now. Press the button again in a minute.</p>", 500)
  }
}
