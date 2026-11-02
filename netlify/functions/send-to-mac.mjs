/**
 * "Send to my Mac": a visitor on Windows, Linux, a phone or a tablet asks for the download link of a Mac app, and gets
 * one email with the product page link and the trial terms, to open on their Mac. Design: docs/designs/send-to-mac.md.
 * The block on the page is stamped by scripts/apply_send_to_mac.py; site/send-to-mac.js shows it and posts here.
 *
 * POST /.netlify/functions/send-to-mac
 *   body (JSON, at most 2 KB): { email, product, news?, website?, ft?, fc?, rdt? }
 *     news        asks for product news only when it is exactly true: the email then carries a signed confirm
 *                 link (double opt-in, netlify/lib/confirm-token.mjs kind "news-confirm"); nothing is stored here
 *     website     honeypot: filled means a bot; answered as if it worked, nothing sent, no counter used
 *     ft fc rdt   how the visitor first arrived (channel label, link tag, Reddit ad click id). Checked against
 *                 allow-lists; an invalid value is dropped, never an error. They only go into the query string of
 *                 the link in the email, so a purchase on the Mac is credited to the same channel and ad.
 *   200 { ok: true }      sent, or honeypot, or this address already had its two sends today (silent, so the
 *                         answer never tells anyone whether an address was used)
 *   400 { error: "invalid_json" | "invalid_email" | "invalid_product" }
 *   403 { error: "forbidden_origin" }   no Origin header, or one that is not this site
 *   413 { error: "too_large" }
 *   429 { error: "rate_limited" }       this IP, or all sends today
 *   502 { error: "send_failed" }        Resend refused; nothing stored
 *   503 { error: "unavailable" }        the rate-limit store could not be read: refuse rather than send unthrottled
 * GET  /.netlify/functions/send-to-mac?u=<hmac>&e=<email>   a page with one button that confirms the unsubscribe (a GET
 *                                                         never deletes, so mail scanners cannot unsubscribe anyone)
 * POST /.netlify/functions/send-to-mac?u=<hmac>&e=<email>   deletes the product-news record (RFC 8058 one-click too)
 * The confirm link goes to confirm-signup.mjs, which calls completeNewsSignup below when its button is pressed.
 *
 * Order: origin, size, JSON, honeypot, validation, counters (IP, then address, then all; each is counted as it
 * passes; a read-then-write in Blobs, so the limits are approximate under bursts), send. A failed send keeps its
 * counts, so retries cannot hammer Resend.
 *
 * It is not a relay: the template is fixed per product and the visitor supplies only the address. Links always point
 * at https://purplelink.llc, also from a deploy preview. Nothing is stored per request except the per-day counters in
 * "rate-limits" (hashed keys). An address is kept only after its owner confirms product news: "product-news" (key:
 * lowercase email; value { email, products, source, confirmedAt }). The unsubscribe token is an HMAC of the address,
 * so no token is stored. The address is never logged. Env: RESEND_API_KEY, SUBSCRIBE_SECRET (news links only).
 */

import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { getStore } from "@netlify/blobs";
import { SITE_ORIGIN, POSTAL_ADDRESS } from "../lib/trial-reminder.mjs";
import { signConfirmToken } from "../lib/confirm-token.mjs";

const ALLOWED_ORIGINS = new Set([SITE_ORIGIN, "https://www.purplelink.llc"]);
const RESEND_API_URL = "https://api.resend.com/emails";
const FROM_ADDRESS = "Benjamin Ampel <orders@purplelink.llc>";
const REPLY_TO = "ben@purplelink.llc";
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;
const CONTROL = /[\u0000-\u001f\u007f]/;
const HMAC_PATTERN = /^[a-f0-9]{64}$/;
// The channel label is whatever analytics.js channel() returned: paid:<src>, tool:<slug>, a campaign source or a
// referring host. Wide enough for those, narrow enough for a URL parameter (URLSearchParams encodes it anyway).
const CHANNEL_RE = /^[\w.\-:+/ ]{1,40}$/;
const TAG_RE = /^[\w.\-]{1,60}$/;
const RDT_RE = /^[\w.\-:=]{1,128}$/;
export const MAX_BODY_BYTES = 2048;
export const PER_IP_DAILY = 5;
export const PER_EMAIL_DAILY = 2;
export const ALL_DAILY = 150;
export const NEWS_STORE = "product-news";
export const NEWS_CONFIRM_KIND = "news-confirm";

// One fixed email per product, stating only terms the product page itself states. Adding an app: one entry here and
// one in PAGES in scripts/apply_send_to_mac.py (site-tests check that the two lists match).
export const PRODUCTS = {
  moderntex: {
    name: "ModernTex",
    email: (link) => ({
      subject: "ModernTex: the download link for your Mac",
      text:
        `You asked for this on the ModernTex page. Open this email on your Mac and use the link below to download the free trial:\n${link("/moderntex/", "buy")}\n\n` +
        `The trial is the complete app for seven days from the first time you open it, with no account and nothing to enter. After that, keeping it is $19.99 once, with all updates included, and it is refunded if you email within 14 days of purchase.\n\n` +
        `ModernTex needs macOS 14 or later, on Apple silicon or Intel.\n\n` +
        `The first ten minutes, from install to the first PDF:\n${link("/moderntex/start/")}\n\n` +
        `Questions: reply to this email and I will answer.\n\nBenjamin Ampel`,
      html:
        `<p>You asked for this on the ModernTex page. Open this email on your Mac and use the link below to download the free trial.</p>` +
        `<p><a href="${link("/moderntex/", "buy")}">Download the ModernTex trial</a></p>` +
        `<p>The trial is the complete app for seven days from the first time you open it, with no account and nothing to enter. After that, keeping it is $19.99 once, with all updates included, and it is refunded if you email within 14 days of purchase.</p>` +
        `<p>ModernTex needs macOS 14 or later, on Apple silicon or Intel.</p>` +
        `<p><a href="${link("/moderntex/start/")}">The first ten minutes</a>, from install to the first PDF.</p>` +
        `<p>Questions: reply to this email and I will answer.</p><p>Benjamin Ampel</p>`,
    }),
  },
};

/** Keep only the attribution values that pass their allow-list; anything else becomes "". */
export function cleanAttribution(body) {
  const pick = (v, re) => (typeof v === "string" && re.test(v) ? v : "");
  return { ft: pick(body.ft, CHANNEL_RE), fc: pick(body.fc, TAG_RE), rdt: pick(body.rdt, RDT_RE) };
}

/**
 * The query string for the links in the email, so the visit on the Mac starts with the same first-touch channel in
 * analytics.js: paid:<src> -> utm_source=<src>&utm_medium=paid (read back as "paid:<src>"); another label ->
 * utm_source=<label>&utm_medium=send-to-mac (read back as "<label>"); none or "direct" ->
 * utm_source=send-to-mac&utm_medium=email. Always utm_campaign=send-to-mac. A Reddit click id rides as rdt_cid, which
 * is what loads the Reddit pixel on the Mac and lets a purchase there reach the Conversions API.
 */
export function attributionQuery({ ft, fc, rdt }) {
  const q = new URLSearchParams();
  if (ft.startsWith("paid:") && ft.length > 5) {
    q.set("utm_source", ft.slice(5));
    q.set("utm_medium", "paid");
  } else if (ft.startsWith("tool:")) {
    // analytics.js reads utm_source=tool-<slug> back as "tool:<slug>".
    q.set("utm_source", `tool-${ft.slice(5)}`);
    q.set("utm_medium", "send-to-mac");
  } else if (ft && ft !== "direct") {
    q.set("utm_source", ft);
    q.set("utm_medium", "send-to-mac");
  } else {
    q.set("utm_source", "send-to-mac");
    q.set("utm_medium", "email");
  }
  q.set("utm_campaign", "send-to-mac");
  if (fc) q.set("utm_content", fc);
  if (rdt) q.set("rdt_cid", rdt);
  return q.toString();
}

function allowedOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return null; // browsers send Origin on every POST; only scripts leave it out
  if (ALLOWED_ORIGINS.has(origin)) return origin;
  const preview = [Netlify.env.get("DEPLOY_PRIME_URL"), Netlify.env.get("DEPLOY_URL")];
  return preview.includes(origin) ? origin : null;
}

function json(status, body, origin = SITE_ORIGIN) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": origin, "Vary": "Origin", "Cache-Control": "no-store" },
  });
}

const clientIpOf = (request) =>
  request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";

// Throws when the store is unreachable; the handler turns that into 503 (fail closed, unlike lib/ratelimit.mjs,
// because an unthrottled email sender is worse than a missed offer).
async function overLimit(kind, value, limit) {
  const day = new Date().toISOString().slice(0, 10);
  const digest = createHash("sha256").update(String(value)).digest("hex").slice(0, 16);
  const key = `rl:send-to-mac-${kind}:${day}:${digest}`;
  const limits = getStore("rate-limits");
  const current = parseInt((await limits.get(key)) || "0", 10) || 0;
  if (current >= limit) return true;
  await limits.set(key, String(current + 1));
  return false;
}

async function sendMail(mail) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  if (!apiKey) return "no_api_key";
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

/** Stateless unsubscribe token for product news: an HMAC of the address, so nothing extra is stored. */
export function newsUnsubscribeToken(email, secret) {
  return createHmac("sha256", secret).update(`product-news-unsub:${email.toLowerCase()}`).digest("hex");
}

export function newsUnsubscribeUrl(email, secret) {
  return `${SITE_ORIGIN}/.netlify/functions/send-to-mac?u=${newsUnsubscribeToken(email, secret)}&e=${encodeURIComponent(email.toLowerCase())}`;
}

/**
 * The one email. `to` is the only value from the request; `query` holds checked attribution only. With a news
 * confirm link, the footer offers it (nothing is stored until it is pressed).
 */
export function buildEmail(product, to, query, newsConfirmLink = "") {
  const p = PRODUCTS[product];
  const link = (path, hash = "") => `${SITE_ORIGIN}${path}?${query}${hash ? `#${hash}` : ""}`;
  const { subject, text, html } = p.email(link);
  const why = `Someone entered this address on the ${p.name} page at purplelink.llc and asked for this link. If it was not you, ignore this email: the address was not kept.`;
  const mail = { from: FROM_ADDRESS, reply_to: REPLY_TO, to: [to], subject };
  if (newsConfirmLink) {
    const ask = "You also ticked the box for news about new Purplelink apps. Nothing is signed up until you confirm, and the link works for 3 days:";
    mail.text = `${text}\n\n${ask}\n${newsConfirmLink}\n\n${why}\n${POSTAL_ADDRESS}`;
    mail.html = `${html}<p>${ask.replace(/:$/, ".")} <a href="${newsConfirmLink}">Confirm product news</a>.</p><p>${why}<br>${POSTAL_ADDRESS}</p>`;
  } else {
    mail.text = `${text}\n\n${why}\n${POSTAL_ADDRESS}`;
    mail.html = `${html}<p>${why}<br>${POSTAL_ADDRESS}</p>`;
  }
  return mail;
}

/**
 * Called by confirm-signup.mjs when the confirm button is pressed: stores the product-news record (or adds the
 * product to an existing one). Sends nothing. Returns "stored" or "repeat".
 */
export async function completeNewsSignup(email, product) {
  const addr = email.toLowerCase();
  const slug = Object.hasOwn(PRODUCTS, product) ? product : "other";
  const records = getStore(NEWS_STORE);
  let existing = null;
  try { existing = JSON.parse((await records.get(addr)) || "null"); } catch (_) { existing = null; }
  if (existing && Array.isArray(existing.products)) {
    if (existing.products.includes(slug)) return "repeat";
    existing.products.push(slug);
    await records.set(addr, JSON.stringify(existing));
    return "stored";
  }
  await records.set(addr, JSON.stringify({ email: addr, products: [slug], source: "send-to-mac", confirmedAt: new Date().toISOString() }));
  return "stored";
}

function page(title, bodyHtml, status = 200) {
  return new Response(`<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex">
    <title>${title} | Purplelink LLC</title>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#19141d">
    <script src="/theme.js"></script>
    <link rel="stylesheet" href="/styles.css">
  </head>
  <body>
    <main id="main-content" class="static-page">
      <h1>${title}</h1>
      ${bodyHtml}
    </main>
  </body>
</html>`, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

async function unsubscribe(request, token, rawEmail) {
  const wantsJson = !/text\/html/.test(request.headers.get("accept") || "");
  const secret = Netlify.env.get("SUBSCRIBE_SECRET");
  const addr = String(rawEmail || "").trim().toLowerCase();
  const valid = secret && EMAIL_PATTERN.test(addr) && HMAC_PATTERN.test(token)
    && timingSafeEqual(Buffer.from(newsUnsubscribeToken(addr, secret)), Buffer.from(token));
  if (!valid) {
    if (request.method === "POST" && wantsJson) return json(400, { error: "invalid_token" });
    return page("Invalid link", '<p>This link is not complete. Write to <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a> and the address will be removed by hand.</p>', 400);
  }
  if (request.method === "GET") {
    return page("Stop product news", `<p>Press the button to stop Purplelink product news to this address and delete its record.</p><form method="post" action="/.netlify/functions/send-to-mac?u=${token}&amp;e=${encodeURIComponent(addr)}"><button type="submit" class="btn btn-primary">Stop product news</button></form>`);
  }
  try {
    await getStore(NEWS_STORE).delete(addr);
  } catch (_) {
    console.error("send-to-mac: unsubscribe failed");
    if (wantsJson) return json(500, { error: "server_error" });
    return page("Something went wrong", '<p>The address could not be removed just now. Try again in a minute, or write to <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>.</p>', 500);
  }
  if (wantsJson) return json(200, { ok: true });
  // The same answer whether or not there was a record.
  return page("Unsubscribed", '<p>That address will get no Purplelink product news, and its record is deleted.</p><p><a href="/">Back to purplelink.llc</a></p>');
}

export default async function handler(request) {
  const url = new URL(request.url);
  const token = url.searchParams.get("u");
  if (token !== null && (request.method === "GET" || request.method === "POST")) return unsubscribe(request, token, url.searchParams.get("e"));

  const origin = allowedOrigin(request);
  if (request.method === "OPTIONS") {
    if (!origin) return new Response(null, { status: 403 });
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400", "Vary": "Origin",
      },
    });
  }
  if (request.method !== "POST") return json(405, { error: "method_not_allowed" });
  if (!origin) return json(403, { error: "forbidden_origin" });

  const raw = await request.text().catch(() => "");
  if (raw.length > MAX_BODY_BYTES) return json(413, { error: "too_large" }, origin);
  let body = null;
  try { body = JSON.parse(raw); } catch (_) { body = null; }
  if (!body || typeof body !== "object" || Array.isArray(body)) return json(400, { error: "invalid_json" }, origin);
  // Honeypot: a filled "website" field is a bot. Answer as if it worked.
  if (typeof body.website === "string" && body.website.trim()) return json(200, { ok: true }, origin);

  const email = typeof body.email === "string" ? body.email.trim() : "";
  if (email.length > 254 || CONTROL.test(email) || !EMAIL_PATTERN.test(email)) return json(400, { error: "invalid_email" }, origin);
  const product = typeof body.product === "string" ? body.product : "";
  if (!Object.hasOwn(PRODUCTS, product)) return json(400, { error: "invalid_product" }, origin);
  const wantsNews = body.news === true;
  const key = email.toLowerCase();

  try {
    if (await overLimit("ip", clientIpOf(request), PER_IP_DAILY)) return json(429, { error: "rate_limited" }, origin);
    // Silent: the same answer as a send, so nobody can learn whether an address was used today.
    if (await overLimit("email", key, PER_EMAIL_DAILY)) return json(200, { ok: true }, origin);
    if (await overLimit("all", "all", ALL_DAILY)) return json(429, { error: "rate_limited" }, origin);
  } catch (_) {
    console.error("send-to-mac: rate-limit store unavailable");
    return json(503, { error: "unavailable" }, origin);
  }

  let newsConfirmLink = "";
  if (wantsNews) {
    const secret = Netlify.env.get("SUBSCRIBE_SECRET");
    if (secret) {
      const t = signConfirmToken(NEWS_CONFIRM_KIND, { e: key, p: product }, secret);
      newsConfirmLink = `${SITE_ORIGIN}/.netlify/functions/confirm-signup?t=${encodeURIComponent(t)}`;
    } else {
      console.error("send-to-mac: SUBSCRIBE_SECRET not set, news link left out");
    }
  }
  const failure = await sendMail(buildEmail(product, email, attributionQuery(cleanAttribution(body)), newsConfirmLink));
  if (failure) {
    console.error("send-to-mac: email failed", failure);
    return json(502, { error: "send_failed" }, origin);
  }
  return json(200, { ok: true }, origin);
}
