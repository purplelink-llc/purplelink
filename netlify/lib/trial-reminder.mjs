/**
 * Shared engine for the optional Mac-app trial emails (Legroom, Keyfeel). Outbound Veil has its own copy of the same
 * logic in netlify/functions/outbound-veil-reminder.mjs and is deliberately left alone.
 *
 * One setup email when someone asks for it, and one reminder REMIND_AFTER_DAYS later. Nothing else, and never a
 * list: each record is deleted when its reminder is sent (or after KEEP_AT_MOST_DAYS, or on unsubscribe).
 *
 * createTrialReminder(config) returns { handler, sendDueReminders, setupEmail, reminderEmail }. The two function
 * files (<app>-reminder.mjs, <app>-reminder-send.mjs) are thin: they hold only the config and the email wording.
 *
 * Endpoint shape (same for every app; FN is config.fnName):
 *   POST /.netlify/functions/FN            body: { email, website?: "<honeypot>" }
 *     200 { ok: true }                 stored, setup email sent
 *     200 { ok: true, already: true }  same address within a day: nothing sent
 *     400 { error: "invalid_json" | "invalid_email" }
 *     403 { error: "forbidden_origin" }
 *     429 { error: "rate_limited" }    per IP or per address, per UTC day
 *     502 { error: "send_failed" }     Resend refused; nothing is kept
 *   GET or POST /.netlify/functions/FN?u=<token>
 *     One-click unsubscribe (the POST form is RFC 8058, for the List-Unsubscribe header). Deletes the record.
 *
 * Blobs, per app:
 *   config.store       key: lowercase email, value: { email, createdAt, remindAt, unsubscribeToken }
 *   config.tokenStore  key: unsubscribe token, value: email (a random token, so the link carries no address)
 *   "rate-limits"      the shared per-day counters (hashed keys).
 *
 * The address is never logged; errors log a code only. Env: RESEND_API_KEY, STRIPE_SECRET_KEY (to skip buyers).
 */

import { createHash, randomBytes } from "node:crypto";
import { getStore } from "@netlify/blobs";

export const SITE_ORIGIN = "https://purplelink.llc";
export const POSTAL_ADDRESS = "Purplelink LLC, 8735 Dunwoody Place #12398, Atlanta, GA 30350";
export const REMIND_AFTER_DAYS = 5;

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
const KEEP_AT_MOST_DAYS = 14;

/** A purplelink.llc URL for an email, with the campaign tags every email link carries. `path` may hold a #fragment. */
export function utmUrl(path, campaign) {
  const [beforeHash, hash] = path.split("#");
  const sep = beforeHash.includes("?") ? "&" : "?";
  const tags = `utm_source=email&utm_medium=trial-reminder&utm_campaign=${encodeURIComponent(campaign)}`;
  return `${SITE_ORIGIN}${beforeHash}${sep}${tags}${hash ? `#${hash}` : ""}`;
}

/**
 * config: {
 *   app: "Legroom", slug: "legroom" (also the utm_campaign), fnName: "legroom-reminder",
 *   store, tokenStore, products: ["legroom", "app-suite"]  (Stripe metadata.product values that count as a purchase),
 *   setup(link), reminder(link): () => { subject, text, html } where link(path) returns a tagged URL.
 * }
 */
export function createTrialReminder(config) {
  const { app, slug, fnName, store: STORE, tokenStore: TOKEN_STORE, products } = config;
  const link = (path) => utmUrl(path, slug);
  const unsubscribeUrlFor = (token) => link(`/.netlify/functions/${fnName}?u=${token}`);

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

  const clientIpOf = (request) =>
    request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";

  async function overLimit(kind, value, limit) {
    const day = new Date().toISOString().slice(0, 10);
    const digest = createHash("sha256").update(value).digest("hex").slice(0, 16);
    const key = `rl:${slug}-reminder-${kind}:${day}:${digest}`;
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

  function withFooter(to, token, { subject, text, html }) {
    const unsub = unsubscribeUrlFor(token);
    return {
      from: FROM_ADDRESS,
      reply_to: REPLY_TO,
      to: [to],
      subject,
      text: `${text}\n\nUnsubscribe with one click:\n${unsub}\n\nYou asked for this on the ${app} page. After the reminder your address is deleted.\n${POSTAL_ADDRESS}`,
      html: `${html}<p><a href="${unsub}">Unsubscribe with one click</a></p><p>You asked for this on the ${app} page. After the reminder your address is deleted.<br>${POSTAL_ADDRESS}</p>`,
      headers: { "List-Unsubscribe": `<${unsub}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" },
    };
  }

  const setupEmail = (to, token) => withFooter(to, token, config.setup(link));
  const reminderEmail = (to, token) => withFooter(to, token, config.reminder(link));

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
        const records = getStore(STORE);
        const raw = await records.get(email);
        let record = null;
        try { record = raw ? JSON.parse(raw) : null; } catch (_) { record = null; }
        if (!record || record.unsubscribeToken === token) await records.delete(email);
        await tokens.delete(token);
      }
    } catch (_) {
      console.error(`${fnName}: unsubscribe failed`);
      if (oneClick) return json(500, { error: "server_error" });
      return page("Something went wrong", '<p>The address could not be removed just now. Try the link again in a minute, or write to <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>.</p>', 500);
    }
    if (oneClick) return json(200, { ok: true });
    // The same answer whether or not the token matched a record.
    return page("Unsubscribed", `<p>That address will get no more ${app} trial email, and its record is deleted.</p><p><a href="/${slug}/">Back to ${app}</a></p>`);
  }

  /** True when this address already bought the app or the Mac Suite, so a buyer is never nudged to buy. */
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
        if (products.includes(s?.metadata?.product) && s.payment_status === "paid") return true;
      }
    }
    return false;
  }

  /**
   * Send every reminder that is due and delete its record; drop records past their keep time. Returns counts only.
   * A record whose buyer check could not be made is left for tomorrow.
   */
  async function sendDueReminders(now = Date.now()) {
    const records = getStore(STORE);
    const tokens = getStore(TOKEN_STORE);
    const result = { sent: 0, skippedBuyers: 0, expired: 0, deferred: 0, failed: 0 };
    const listing = await records.list();
    for (const { key } of listing.blobs ?? []) {
      const raw = await records.get(key);
      let record = null;
      try { record = raw ? JSON.parse(raw) : null; } catch (_) { record = null; }
      if (!record || !record.email) { await records.delete(key); continue; }
      const drop = async () => { await records.delete(key); if (record.unsubscribeToken) await tokens.delete(record.unsubscribeToken); };
      if (now - Date.parse(record.createdAt) > KEEP_AT_MOST_DAYS * DAY_MS) { await drop(); result.expired++; continue; }
      if (now < Date.parse(record.remindAt)) continue;
      let bought;
      try { bought = await hasBought(record.email); } catch (_) { bought = null; }
      if (bought === null) { result.deferred++; continue; }
      if (bought) { await drop(); result.skippedBuyers++; continue; }
      const failure = await sendMail(reminderEmail(record.email, record.unsubscribeToken));
      if (failure) { console.error(`${fnName}: reminder failed`, failure); result.failed++; continue; }
      await drop();
      result.sent++;
    }
    return result;
  }

  async function handler(request) {
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
      const records = getStore(STORE);
      const tokens = getStore(TOKEN_STORE);
      const raw = await records.get(email);
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
      await records.set(email, JSON.stringify(record));
      await tokens.set(record.unsubscribeToken, email);
      if (existing?.unsubscribeToken) await tokens.delete(existing.unsubscribeToken);

      const failure = await sendMail(setupEmail(email, record.unsubscribeToken));
      if (failure) {
        console.error(`${fnName}: email failed`, failure);
        // Nobody is kept who got no email (and no unsubscribe link).
        await records.delete(email);
        await tokens.delete(record.unsubscribeToken);
        return json(502, { error: "send_failed" }, origin);
      }
      return json(200, { ok: true }, origin);
    } catch (_) {
      console.error(`${fnName}: storage failed`);
      return json(500, { error: "server_error" }, origin);
    }
  }

  return { handler, sendDueReminders, setupEmail, reminderEmail };
}
