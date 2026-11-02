/**
 * The Undershelf waitlist: a 14-day demand test for a printed Mac mini mount (docs/designs/undershelf-waitlist.md).
 *
 * POST /.netlify/functions/undershelf-waitlist
 *   body: { email, version?: "standard" | "carbon" | "unsure", page?, utm?, website?: "<honeypot>" }
 *   200 { ok: true }                     every accepted request, whether or not a confirmation was sent, so the
 *                                        response never says if an address is on the list
 *   400 { error: "invalid_json" | "invalid_email" }
 *   403 { error: "forbidden_origin" }    Origin header present and not this site
 *   429 { error: "rate_limited" }        per IP or per address, per UTC day
 *   502 { error: "send_failed" }         Resend refused
 *
 * Double opt-in: the request travels inside a signed "undershelf-confirm" link (netlify/lib/confirm-token.mjs);
 * confirm-signup.mjs calls completeUndershelfSignup below when the button on that page is pressed. Nothing is
 * stored before then, and the confirmation itself sends no email.
 *
 * GET ?u=<token>&e=<email>   A page with one button; changes nothing, so mail scanners cannot unsubscribe anyone.
 * POST ?u=<token>&e=<email>  The button, or RFC 8058 one-click: deletes the record and suppresses the address.
 *   The token is an HMAC of the address, so it works before any record exists (from the confirmation email).
 *
 * Blobs:
 *   "undershelf-waitlist"    key: lowercase email; value: { email, version, page, utm, confirmedAt }
 *   "undershelf-suppressed"  key: sha256 hex of the lowercase email; value: { at }. No address kept.
 *   "rate-limits"            shared counters (netlify/lib/ratelimit.mjs), kind prefix "undershelf-".
 *
 * Counts and the launch email are read from Blobs by scripts/undershelf_list.py on Ben's Mac; no endpoint here
 * returns addresses or counts.
 */
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { getStore } from "@netlify/blobs";
import { signConfirmToken } from "../lib/confirm-token.mjs";
import { escapeHtml, page } from "../lib/fn-page.mjs";
import { clientIp, overDailyLimit } from "../lib/ratelimit.mjs";

const SITE_ORIGIN = "https://purplelink.llc";
const ALLOWED_ORIGINS = new Set([SITE_ORIGIN, "https://www.purplelink.llc"]);
const RESEND_API_URL = "https://api.resend.com/emails";
const FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>";
const REPLY_TO = "ben@purplelink.llc";
const EMAIL_PATTERN = /^[^\s@<>"`\\]{1,64}@[^\s@<>"`\\]{1,190}\.[^\s@<>"`\\]{2,}$/;
const VERSIONS = new Set(["standard", "carbon", "unsure"]);
const UTM_PATTERN = /^[a-z0-9_-]{0,64}$/;
const PER_EMAIL_DAILY = 3;
const PER_IP_DAILY = 20;

const LIST = "undershelf-waitlist";
const SUPPRESSED = "undershelf-suppressed";

function allowedOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return SITE_ORIGIN; // same-origin form posts and curl send none
  if (ALLOWED_ORIGINS.has(origin)) return origin;
  const preview = [Netlify.env.get("DEPLOY_PRIME_URL"), Netlify.env.get("DEPLOY_URL")];
  return preview.includes(origin) ? origin : null;
}

function json(status, body, origin = SITE_ORIGIN) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": origin,
      "Vary": "Origin",
      "Cache-Control": "no-store",
    },
  });
}

/** Server-side cleaning of the optional fields (the page script is not trusted). */
export function cleanFields(body) {
  const version = VERSIONS.has(body.version) ? body.version : "unsure";
  const utm = typeof body.utm === "string" && UTM_PATTERN.test(body.utm) ? body.utm : "";
  let pagePath = "";
  if (typeof body.page === "string" && body.page.startsWith("/") && !body.page.startsWith("//")) {
    pagePath = body.page.split(/[?#]/)[0].replace(/[^\w\-./]/g, "").slice(0, 120);
  }
  return { version, utm, page: pagePath };
}

export function suppressionKey(email) {
  return createHash("sha256").update(email.toLowerCase()).digest("hex");
}

/** Stateless unsubscribe token: works from the confirmation email before any record exists. */
export function unsubscribeToken(email, secret) {
  return createHmac("sha256", secret).update(`undershelf-unsub:${email.toLowerCase()}`).digest("hex");
}

function tokenMatches(email, token, secret) {
  if (typeof token !== "string" || !/^[0-9a-f]{64}$/.test(token)) return false;
  return timingSafeEqual(Buffer.from(unsubscribeToken(email, secret)), Buffer.from(token));
}

export function unsubscribeUrl(email, secret) {
  return `${SITE_ORIGIN}/.netlify/functions/undershelf-waitlist?u=${unsubscribeToken(email, secret)}&e=${encodeURIComponent(email)}`;
}

async function isSuppressed(email) {
  return (await getStore(SUPPRESSED).get(suppressionKey(email))) !== null;
}

async function sendConfirmation(to, link, unsub) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  if (!apiKey) return "no_api_key";
  const mail = {
    from: FROM_ADDRESS,
    reply_to: REPLY_TO,
    to: [to],
    subject: "Confirm your place on the Undershelf waitlist",
    text:
      `Confirm your place on the Undershelf waitlist with this link (it works for 3 days):\n\n${link}\n\n` +
      `If you did not ask, ignore this email and nothing is kept. To never get email about Undershelf:\n${unsub}\n\n` +
      `Purplelink LLC, Atlanta, Georgia`,
    html:
      `<p>Confirm your place on the Undershelf waitlist: <a href="${link}">confirm my email</a>. The link works for 3 days.</p>` +
      `<p>If you did not ask, ignore this email and nothing is kept. <a href="${unsub}">Never email me about Undershelf</a>.</p>` +
      `<p>Purplelink LLC, Atlanta, Georgia</p>`,
    headers: {
      "List-Unsubscribe": `<${unsub}>`,
      "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
  };
  try {
    const resp = await fetch(RESEND_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify(mail),
    });
    return resp.ok ? null : `resend_${resp.status}`;
  } catch (_) {
    return "resend_unreachable";
  }
}

/**
 * Called by confirm-signup.mjs when the confirmation button is pressed. Stores the record unless the address is
 * suppressed. Sends nothing. Returns "stored", "repeat" (already on the list) or "suppressed".
 */
export async function completeUndershelfSignup(email, version, pagePath, utm) {
  const addr = email.toLowerCase();
  if (await isSuppressed(addr)) return "suppressed";
  const list = getStore(LIST);
  if ((await list.get(addr)) !== null) return "repeat";
  const fields = cleanFields({ version, page: pagePath, utm });
  await list.set(addr, JSON.stringify({ email: addr, ...fields, confirmedAt: new Date().toISOString() }));
  return "stored";
}

async function unsubscribe(request, token, email) {
  const secret = process.env.SUBSCRIBE_SECRET;
  const addr = (email || "").trim().toLowerCase();
  if (!secret || !EMAIL_PATTERN.test(addr) || !tokenMatches(addr, token, secret)) {
    return page("Unsubscribe", "This link is not valid",
      `<p class="post-lede">The unsubscribe link is incomplete. Reply to any Undershelf email and we will remove you by hand.</p>`, 400);
  }
  if (request.method === "GET") {
    const action = `/.netlify/functions/undershelf-waitlist?u=${escapeHtml(token)}&e=${encodeURIComponent(addr)}`;
    return page("Unsubscribe", "Stop Undershelf emails?",
      `<p class="post-lede">Remove ${escapeHtml(addr)} from the Undershelf waitlist and never email it about Undershelf again?</p>
      <form method="post" action="${action}"><button type="submit" class="btn btn-primary">Unsubscribe</button></form>`);
  }
  try {
    await getStore(LIST).delete(addr);
    await getStore(SUPPRESSED).set(suppressionKey(addr), JSON.stringify({ at: new Date().toISOString() }));
  } catch (err) {
    console.error("undershelf-waitlist: unsubscribe failed", err?.message);
    return page("Try again", "Something went wrong", `<p class="post-lede">Press the button again in a minute.</p>`, 500);
  }
  return page("Unsubscribed", "You are unsubscribed",
    `<p class="post-lede">${escapeHtml(addr)} is off the Undershelf waitlist and will not get email about it.</p>`);
}

export default async function handler(request) {
  const url = new URL(request.url);
  const token = url.searchParams.get("u");
  if (token !== null && (request.method === "GET" || request.method === "POST")) {
    return unsubscribe(request, token, url.searchParams.get("e"));
  }

  const origin = allowedOrigin(request);
  if (request.method === "OPTIONS") {
    if (!origin) return new Response(null, { status: 403 });
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
      },
    });
  }
  if (request.method !== "POST") return json(405, { error: "method_not_allowed" });
  if (!origin) return json(403, { error: "forbidden_origin" });

  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object") return json(400, { error: "invalid_json" }, origin);

  // Honeypot: a filled "website" field is a bot. Answer exactly as for a person.
  if (typeof body.website === "string" && body.website.trim()) return json(200, { ok: true }, origin);

  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (email.length > 254 || !EMAIL_PATTERN.test(email)) return json(400, { error: "invalid_email" }, origin);

  // Fails open when the store is down (netlify/lib/ratelimit.mjs): accepted for a waitlist.
  if ((await overDailyLimit("undershelf-ip", clientIp(request), PER_IP_DAILY)) ||
      (await overDailyLimit("undershelf-email", email, PER_EMAIL_DAILY))) {
    return json(429, { error: "rate_limited" }, origin);
  }

  const secret = process.env.SUBSCRIBE_SECRET;
  if (!secret) {
    console.error("undershelf-waitlist: SUBSCRIBE_SECRET not set");
    return json(500, { error: "server_error" }, origin);
  }

  try {
    // Already confirmed or suppressed: same answer, nothing sent.
    if ((await isSuppressed(email)) || (await getStore(LIST).get(email)) !== null) {
      return json(200, { ok: true }, origin);
    }
  } catch (err) {
    console.error("undershelf-waitlist: store read failed", err?.message);
    return json(500, { error: "server_error" }, origin);
  }

  const { version, utm, page: pagePath } = cleanFields(body);
  const confirmToken = signConfirmToken("undershelf-confirm", { e: email, v: version, p: pagePath, u: utm }, secret);
  const link = `${SITE_ORIGIN}/.netlify/functions/confirm-signup?t=${encodeURIComponent(confirmToken)}`;
  const failure = await sendConfirmation(email, link, unsubscribeUrl(email, secret));
  if (failure) {
    console.error("undershelf-waitlist: confirmation email failed", failure);
    return json(502, { error: "send_failed" }, origin);
  }
  return json(200, { ok: true }, origin);
}
