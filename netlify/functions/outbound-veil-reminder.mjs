/**
 * Optional Outbound Veil trial emails: one setup email when someone asks for it, and one reminder about
 * five days later. Nothing else, and never a list: each record is deleted when its reminder is sent.
 *
 * POST /.netlify/functions/outbound-veil-reminder
 *   body: { email, website?: "<honeypot>" }
 *   200 { ok: true }                 stored, setup email sent
 *   200 { ok: true, already: true }  same address within a day: nothing sent
 *   400 { error: "invalid_json" | "invalid_email" }
 *   403 { error: "forbidden_origin" }
 *   429 { error: "rate_limited" }    per IP or per address, per UTC day
 *   502 { error: "send_failed" }     Resend refused; nothing is kept
 *
 * GET or POST /.netlify/functions/outbound-veil-reminder?u=<token>
 *   One-click unsubscribe (the POST form is RFC 8058, for the List-Unsubscribe header). Deletes the record.
 *
 * The reminder itself is sent by outbound-veil-reminder-send.mjs, a daily scheduled function that calls
 * sendDueReminders() below.
 *
 * Blobs:
 *   "ov-trial-reminders"        key: lowercase email
 *                               value: { email, createdAt, remindAt, unsubscribeToken }
 *   "ov-trial-reminder-tokens"  key: unsubscribe token, value: email (a random token, so the link carries no address)
 *   "rate-limits"               the shared per-day counters (hashed keys).
 *
 * The address is never logged; errors log a code only. Env: RESEND_API_KEY, STRIPE_SECRET_KEY (to skip buyers).
 */

import { createHash, randomBytes } from "node:crypto";
import { getStore } from "@netlify/blobs";

const SITE_ORIGIN = "https://purplelink.llc";
const ALLOWED_ORIGINS = new Set([SITE_ORIGIN, "https://www.purplelink.llc"]);
const RESEND_API_URL = "https://api.resend.com/emails";
const STRIPE_API = "https://api.stripe.com/v1";
const FROM_ADDRESS = "Benjamin Ampel <orders@purplelink.llc>";
const REPLY_TO = "ben@purplelink.llc";
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;
const TOKEN_PATTERN = /^[a-f0-9]{48}$/;
const PER_EMAIL_DAILY = 3;
const PER_IP_DAILY = 20;
const DAY_MS = 24 * 60 * 60 * 1000;
export const REMIND_AFTER_DAYS = 5;
const KEEP_AT_MOST_DAYS = 14;
const STORE = "ov-trial-reminders";
const TOKEN_STORE = "ov-trial-reminder-tokens";
const START_URL = `${SITE_ORIGIN}/outbound-veil/start/`;
const BUY_URL = `${SITE_ORIGIN}/outbound-veil/#buy`;
const RECOVER_URL = `${SITE_ORIGIN}/recover/`;

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
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": origin, "Vary": "Origin", "Cache-Control": "no-store" },
  });
}

function clientIpOf(request) {
  return request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";
}

async function overLimit(kind, value, limit) {
  const day = new Date().toISOString().slice(0, 10);
  const digest = createHash("sha256").update(value).digest("hex").slice(0, 16);
  const key = `rl:ov-reminder-${kind}:${day}:${digest}`;
  const store = getStore("rate-limits");
  const current = parseInt((await store.get(key)) || "0", 10) || 0;
  if (current >= limit) return true;
  await store.set(key, String(current + 1));
  return false;
}

const unsubscribeUrlFor = (token) => `${SITE_ORIGIN}/.netlify/functions/outbound-veil-reminder?u=${token}`;

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

function withFooter(to, token, subject, textBody, htmlBody) {
  const unsub = unsubscribeUrlFor(token);
  return {
    from: FROM_ADDRESS,
    reply_to: REPLY_TO,
    to: [to],
    subject,
    text: `${textBody}\n\nUnsubscribe with one click:\n${unsub}\n\nPurplelink LLC, Atlanta, Georgia`,
    html: `${htmlBody}<p><a href="${unsub}">Unsubscribe with one click</a></p><p>Purplelink LLC, Atlanta, Georgia</p>`,
    headers: { "List-Unsubscribe": `<${unsub}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" },
  };
}

export function setupEmail(to, token) {
  return withFooter(
    to, token, "Outbound Veil: your setup guide",
    `Thanks for trying Outbound Veil. The part that trips people up is the macOS Accessibility permission, so here is the setup guide, about ten minutes from the disk image to your first redaction:\n${START_URL}\n\n` +
      `The trial is the complete app for seven days from the first time you open it, with no account. After that the app asks for a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.\n\n` +
      `Questions: reply to this email and I will answer.\n\nBenjamin Ampel`,
    `<p>Thanks for trying Outbound Veil. The part that trips people up is the macOS Accessibility permission, so here is <a href="${START_URL}">the setup guide</a>, about ten minutes from the disk image to your first redaction.</p>` +
      `<p>The trial is the complete app for seven days from the first time you open it, with no account. After that the app asks for a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.</p>` +
      `<p>Questions: reply to this email and I will answer.</p><p>Benjamin Ampel</p>`,
  );
}

export function reminderEmail(to, token) {
  return withFooter(
    to, token, "Your Outbound Veil trial",
    `The Outbound Veil trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends it stops checking and shows one notice; nothing is charged.\n\n` +
      `If it has been useful, keeping it is $29.99 once, with updates included, and there is a 14-day refund:\n${BUY_URL}\n\n` +
      `Your license key arrives in the receipt email and is shown on the success page. Choose Enter license key\u2026 from the Outbound Veil menu-bar menu and paste it into the copy you already have. If you lose the key, the Find a purchase page sends it again:\n${RECOVER_URL}\n\n` +
      `If it has not, I would like to know why. Reply to this email with one line.\n\nBenjamin Ampel`,
    `<p>The Outbound Veil trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends it stops checking and shows one notice; nothing is charged.</p>` +
      `<p>If it has been useful, <a href="${BUY_URL}">keeping it is $29.99 once</a>, with updates included, and there is a 14-day refund.</p>` +
      `<p>Your license key arrives in the receipt email and is shown on the success page. Choose Enter license key\u2026 from the Outbound Veil menu-bar menu and paste it into the copy you already have. If you lose the key, <a href="${RECOVER_URL}">the Find a purchase page</a> sends it again.</p>` +
      `<p>If it has not, I would like to know why. Reply to this email with one line.</p><p>Benjamin Ampel</p>`,
  );
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
    <script src="/site.js" defer></script>
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <main id="main-content" class="static-page">
      <h1>${title}</h1>
      ${bodyHtml}
    </main>
  </body>
</html>`, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

async function unsubscribe(request, token) {
  const oneClick = request.method === "POST";
  if (!TOKEN_PATTERN.test(token)) {
    if (oneClick) return json(400, { error: "invalid_token" });
    return page("Invalid link", '<p>This unsubscribe link is not complete. Write to <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a> and the address will be removed by hand.</p>', 400);
  }
  try {
    const tokens = getStore(TOKEN_STORE);
    const email = await tokens.get(token);
    if (email) {
      const store = getStore(STORE);
      const raw = await store.get(email);
      let record = null;
      try { record = raw ? JSON.parse(raw) : null; } catch (_) { record = null; }
      if (!record || record.unsubscribeToken === token) await store.delete(email);
      await tokens.delete(token);
    }
  } catch (_) {
    console.error("outbound-veil-reminder: unsubscribe failed");
    if (oneClick) return json(500, { error: "server_error" });
    return page("Something went wrong", '<p>The address could not be removed just now. Try the link again in a minute, or write to <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>.</p>', 500);
  }
  if (oneClick) return json(200, { ok: true });
  // The same answer whether or not the token matched a record.
  return page("Unsubscribed", "<p>That address will get no more Outbound Veil trial email, and its record is deleted.</p><p><a href=\"/outbound-veil/\">Back to Outbound Veil</a></p>");
}

/** True when this address already bought Outbound Veil or the Mac Suite, so a buyer is never nudged to buy. */
async function hasBought(email) {
  const key = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!key) return null; // unknown: the caller skips this run rather than risk emailing a buyer
  for (const address of [...new Set([email, email.toLowerCase()])]) {
    const resp = await fetch(`${STRIPE_API}/checkout/sessions?customer_details%5Bemail%5D=${encodeURIComponent(address)}&limit=100`, {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (!resp.ok) return null;
    const data = await resp.json().catch(() => null);
    for (const s of data?.data ?? []) {
      const p = s?.metadata?.product;
      if ((p === "outbound-veil" || p === "app-suite") && s.payment_status === "paid") return true;
    }
  }
  return false;
}

/**
 * Send every reminder that is due and delete its record; drop records past their keep time. Returns counts only.
 * A record whose buyer check could not be made is left for tomorrow.
 */
export async function sendDueReminders(now = Date.now()) {
  const store = getStore(STORE);
  const tokens = getStore(TOKEN_STORE);
  const result = { sent: 0, skippedBuyers: 0, expired: 0, deferred: 0, failed: 0 };
  const listing = await store.list();
  for (const { key } of listing.blobs ?? []) {
    const raw = await store.get(key);
    let record = null;
    try { record = raw ? JSON.parse(raw) : null; } catch (_) { record = null; }
    if (!record || !record.email) { await store.delete(key); continue; }
    const drop = async () => { await store.delete(key); if (record.unsubscribeToken) await tokens.delete(record.unsubscribeToken); };
    if (now - Date.parse(record.createdAt) > KEEP_AT_MOST_DAYS * DAY_MS) { await drop(); result.expired++; continue; }
    if (now < Date.parse(record.remindAt)) continue;
    let bought;
    try { bought = await hasBought(record.email); } catch (_) { bought = null; }
    if (bought === null) { result.deferred++; continue; }
    if (bought) { await drop(); result.skippedBuyers++; continue; }
    const failure = await sendMail(reminderEmail(record.email, record.unsubscribeToken));
    if (failure) { console.error("outbound-veil-reminder: reminder failed", failure); result.failed++; continue; }
    await drop();
    result.sent++;
  }
  return result;
}

export default async function handler(request) {
  const url = new URL(request.url);
  const token = url.searchParams.get("u");
  if (token !== null && (request.method === "GET" || request.method === "POST")) return unsubscribe(request, token);

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

  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object") return json(400, { error: "invalid_json" }, origin);
  // Honeypot: a filled "website" field is a bot. Answer as if it worked.
  if (typeof body.website === "string" && body.website.trim()) return json(200, { ok: true }, origin);

  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (email.length > 254 || !EMAIL_PATTERN.test(email)) return json(400, { error: "invalid_email" }, origin);

  try {
    if ((await overLimit("ip", clientIpOf(request), PER_IP_DAILY)) || (await overLimit("email", email, PER_EMAIL_DAILY))) {
      return json(429, { error: "rate_limited" }, origin);
    }
    const store = getStore(STORE);
    const tokens = getStore(TOKEN_STORE);
    const raw = await store.get(email);
    let existing = null;
    try { existing = raw ? JSON.parse(raw) : null; } catch (_) { existing = null; }
    const now = Date.now();
    if (existing && now - Date.parse(existing.createdAt) < DAY_MS) return json(200, { ok: true, already: true }, origin);

    const record = {
      email,
      createdAt: new Date(now).toISOString(),
      remindAt: new Date(now + REMIND_AFTER_DAYS * DAY_MS).toISOString(),
      unsubscribeToken: randomBytes(24).toString("hex"),
    };
    // Written before the send, so a second submission that arrives meanwhile sees it and does not send again.
    await store.set(email, JSON.stringify(record));
    await tokens.set(record.unsubscribeToken, email);
    if (existing?.unsubscribeToken) await tokens.delete(existing.unsubscribeToken);

    const failure = await sendMail(setupEmail(email, record.unsubscribeToken));
    if (failure) {
      console.error("outbound-veil-reminder: email failed", failure);
      // Nobody is kept who got no email (and no unsubscribe link).
      await store.delete(email);
      await tokens.delete(record.unsubscribeToken);
      return json(502, { error: "send_failed" }, origin);
    }
    return json(200, { ok: true }, origin);
  } catch (_) {
    console.error("outbound-veil-reminder: storage failed");
    return json(500, { error: "server_error" }, origin);
  }
}
