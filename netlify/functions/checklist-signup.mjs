/**
 * The researcher list: one email with the submission checklist PDF, then an
 * occasional note when a tool changes.
 *
 * POST /.netlify/functions/checklist-signup
 *   body: { email, page?: "<path the form was on>", website?: "<honeypot>" }
 *   200 { ok: true }                     stored and emailed
 *   200 { ok: true, already: true }      same address within a day: nothing sent
 *   400 { error: "invalid_json" | "invalid_email" }
 *   403 { error: "forbidden_origin" }    Origin header present and not this site
 *   429 { error: "rate_limited" }        per IP or per address, per UTC day
 *   502 { error: "send_failed" }         Resend refused; nothing is kept
 *
 * GET or POST /.netlify/functions/checklist-signup?u=<token>
 *   One-click unsubscribe (the POST form is RFC 8058, for the
 *   List-Unsubscribe header). Deletes the record. The existing unsubscribe.mjs
 *   only knows the digest's "subscribers" store, so this list handles its own.
 *
 * Blobs:
 *   "researcher-list"         key: lowercase email
 *                             value: { email, source, createdAt,
 *                                      unsubscribeToken, lastSentAt }
 *   "researcher-list-tokens"  key: unsubscribe token, value: email. A random
 *                             token, so the link carries no address.
 *   "rate-limits"             the shared per-day counters (hashed keys).
 *
 * The address is never logged; errors log a code only.
 *
 * Env: RESEND_API_KEY (the key the order and recovery emails already use).
 */

import { createHash, randomBytes } from "node:crypto";
import { getStore } from "@netlify/blobs";

const SITE_ORIGIN = "https://purplelink.llc";
const ALLOWED_ORIGINS = new Set([SITE_ORIGIN, "https://www.purplelink.llc"]);
const RESEND_API_URL = "https://api.resend.com/emails";
const FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>";
const REPLY_TO = "ben@purplelink.llc";
const PDF_PATH = "/assets/downloads/submission-checklist.pdf";
const PDF_FILENAME = "submission-checklist.pdf";
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;
const TOKEN_PATTERN = /^[a-f0-9]{48}$/;
const PER_EMAIL_DAILY = 3;
const PER_IP_DAILY = 20;
const RESEND_WINDOW_MS = 24 * 60 * 60 * 1000;

function allowedOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return SITE_ORIGIN; // same-origin form posts and curl send none
  if (ALLOWED_ORIGINS.has(origin)) return origin;
  // A deploy preview posts from its own address.
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

function clientIpOf(request) {
  return request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";
}

/** Per-UTC-day counter in the shared rate-limits store (same pattern as purchases-recover.mjs). */
async function overLimit(kind, value, limit) {
  const day = new Date().toISOString().slice(0, 10);
  const digest = createHash("sha256").update(value).digest("hex").slice(0, 16);
  const key = `rl:checklist-${kind}:${day}:${digest}`;
  const store = getStore("rate-limits");
  const current = parseInt((await store.get(key)) || "0", 10) || 0;
  if (current >= limit) return true;
  await store.set(key, String(current + 1));
  return false;
}

/** The page the form was on: a site path only, no query string, no fragment. */
function sourcePath(value) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) return "";
  return value.split(/[?#]/)[0].replace(/[^\w\-./]/g, "").slice(0, 200);
}

/** The PDF as base64, read from the deployed site; null if it cannot be fetched. */
async function checklistPdf() {
  try {
    const resp = await fetch(`${SITE_ORIGIN}${PDF_PATH}`);
    if (!resp.ok) return null;
    const bytes = Buffer.from(await resp.arrayBuffer());
    if (bytes.length < 1000 || bytes.subarray(0, 4).toString("latin1") !== "%PDF") return null;
    return bytes.toString("base64");
  } catch (_) {
    return null;
  }
}

async function sendChecklist(to, token) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  if (!apiKey) return "no_api_key";
  const unsubscribeUrl = `${SITE_ORIGIN}/.netlify/functions/checklist-signup?u=${token}`;
  const pdfUrl = `${SITE_ORIGIN}${PDF_PATH}`;
  const toolUrl = `${SITE_ORIGIN}/tools/submission-checklist/`;
  const pdf = await checklistPdf();
  const where = pdf ? "The submission checklist is attached as a one-page PDF." : "The submission checklist is a one-page PDF.";
  const mail = {
    from: FROM_ADDRESS,
    reply_to: REPLY_TO,
    to: [to],
    subject: "Your submission checklist",
    text:
      `${where} You can also download it here:\n${pdfUrl}\n\n` +
      `It lists twelve checks to run before you submit a paper, each with the tool that does it. ` +
      `There is an interactive version that keeps your ticks in the browser:\n${toolUrl}\n\n` +
      `You are on the Purplelink researcher list. It sends a short note when a tool changes, and nothing daily.\n\n` +
      `Unsubscribe with one click:\n${unsubscribeUrl}\n\n` +
      `Purplelink LLC, Atlanta, Georgia`,
    html:
      `<p>${where} You can also <a href="${pdfUrl}">download it here</a>.</p>` +
      `<p>It lists twelve checks to run before you submit a paper, each with the tool that does it. ` +
      `There is an <a href="${toolUrl}">interactive version</a> that keeps your ticks in the browser.</p>` +
      `<p>You are on the Purplelink researcher list. It sends a short note when a tool changes, and nothing daily.</p>` +
      `<p><a href="${unsubscribeUrl}">Unsubscribe with one click</a></p>` +
      `<p>Purplelink LLC, Atlanta, Georgia</p>`,
    headers: {
      "List-Unsubscribe": `<${unsubscribeUrl}>`,
      "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
  };
  if (pdf) mail.attachments = [{ filename: PDF_FILENAME, content: pdf }];
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

function page(title, bodyHtml, status = 200) {
  return new Response(`<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex">
    <title>${title} | Purplelink LLC</title>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <script src="/theme.js"></script>
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-mark.svg" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/products/">Products</a>
        <a href="/tools/">Tools</a>
        <a href="/guides/">Guides</a>
        <a href="/blog/">Blog</a>
        <a href="/about/">About</a>
      </nav>
    </header>
    <main id="main-content" class="static-page">
      <h1>${title}</h1>
      ${bodyHtml}
    </main>
  </body>
</html>`, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  });
}

async function unsubscribe(request, token) {
  const oneClick = request.method === "POST";
  if (!TOKEN_PATTERN.test(token)) {
    if (oneClick) return json(400, { error: "invalid_token" });
    return page("Invalid link", '<p>This unsubscribe link is not complete. Write to <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a> and the address will be removed by hand.</p>', 400);
  }
  try {
    const tokens = getStore("researcher-list-tokens");
    const email = await tokens.get(token);
    if (email) {
      const list = getStore("researcher-list");
      const raw = await list.get(email);
      let record = null;
      try { record = raw ? JSON.parse(raw) : null; } catch (_) { record = null; }
      if (!record || record.unsubscribeToken === token) await list.delete(email);
      await tokens.delete(token);
    }
  } catch (_) {
    console.error("checklist-signup: unsubscribe failed");
    if (oneClick) return json(500, { error: "server_error" });
    return page("Something went wrong", '<p>The address could not be removed just now. Try the link again in a minute, or write to <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>.</p>', 500);
  }
  if (oneClick) return json(200, { ok: true });
  // The same answer whether or not the token matched a record, so the link
  // says nothing about who is on the list.
  return page("Unsubscribed", '<p>That address is off the Purplelink researcher list and its record is deleted. No more email will be sent to it.</p><p><a href="/tools/">Back to the tools</a></p>');
}

export default async function handler(request) {
  const url = new URL(request.url);
  const token = url.searchParams.get("u");
  if (token !== null && (request.method === "GET" || request.method === "POST")) {
    return unsubscribe(request, token);
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

  // Honeypot: a filled "website" field is a bot. Answer as if it worked.
  if (typeof body.website === "string" && body.website.trim()) return json(200, { ok: true }, origin);

  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (email.length > 254 || !EMAIL_PATTERN.test(email)) return json(400, { error: "invalid_email" }, origin);

  try {
    if ((await overLimit("ip", clientIpOf(request), PER_IP_DAILY)) ||
        (await overLimit("email", email, PER_EMAIL_DAILY))) {
      return json(429, { error: "rate_limited" }, origin);
    }

    const list = getStore("researcher-list");
    const tokens = getStore("researcher-list-tokens");
    const raw = await list.get(email);
    let existing = null;
    try { existing = raw ? JSON.parse(raw) : null; } catch (_) { existing = null; }

    const now = Date.now();
    const lastSent = existing && existing.lastSentAt ? Date.parse(existing.lastSentAt) : 0;
    if (lastSent && now - lastSent < RESEND_WINDOW_MS) {
      return json(200, { ok: true, already: true }, origin);
    }

    const record = {
      email,
      source: (existing && existing.source) || sourcePath(body.page),
      createdAt: (existing && existing.createdAt) || new Date(now).toISOString(),
      unsubscribeToken: (existing && existing.unsubscribeToken) || randomBytes(24).toString("hex"),
      lastSentAt: new Date(now).toISOString(),
    };
    // Written before the send, so a second submission that arrives while the
    // first is still sending sees lastSentAt and does not send again.
    await list.set(email, JSON.stringify(record));
    await tokens.set(record.unsubscribeToken, email);

    const failure = await sendChecklist(email, record.unsubscribeToken);
    if (failure) {
      console.error("checklist-signup: email failed", failure);
      // Nobody is kept on a list they got no email (and no unsubscribe link) from.
      if (existing) {
        await list.set(email, JSON.stringify(existing));
      } else {
        await list.delete(email);
        await tokens.delete(record.unsubscribeToken);
      }
      return json(502, { error: "send_failed" }, origin);
    }
    return json(200, { ok: true }, origin);
  } catch (_) {
    console.error("checklist-signup: storage failed");
    return json(500, { error: "server_error" }, origin);
  }
}
