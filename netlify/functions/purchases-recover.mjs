/**
 * Find my purchases. POST { "email": "<address used at checkout>" } from /recover/.
 *
 * ModernTex keys and kit links are emailed once at purchase and never stored,
 * so a lost email used to mean a lost key. This looks up the paid Checkout
 * Sessions for the address in Stripe and emails that same address:
 *   - for ModernTex, a newly signed license key (any validly signed key
 *     unlocks the app) and the download page of the latest purchase;
 *   - for kits, the download page of each purchase.
 * The answer is the same whether or not anything matched, and it goes out
 * before the lookup, so the endpoint says nothing about an address. Requests
 * are capped per address and per IP per UTC day.
 *
 * Env: STRIPE_SECRET_KEY, RESEND_API_KEY, MODERNTEX_LICENSE_PRIVATE_KEY
 * (the last through issueModernTexLicense in stripe-webhook.mjs).
 */

import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";
import { issueModernTexLicense, BLOB_DELIVERED_PRODUCTS } from "./stripe-webhook.mjs";

const SITE_ORIGIN = "https://purplelink.llc";
const RESEND_API_URL = "https://api.resend.com/emails";
const ORDER_FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>";
const ORDER_REPLY_TO = "ben@purplelink.llc";
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;
const PER_EMAIL_DAILY = 3;
const PER_IP_DAILY = 20;
const MAX_PAGES = 5;

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function clientIpOf(request) {
  return request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";
}

async function overLimit(kind, value, limit) {
  const day = new Date().toISOString().slice(0, 10);
  const digest = createHash("sha256").update(value).digest("hex").slice(0, 16);
  const key = `rl:purchases-${kind}:${day}:${digest}`;
  const store = getStore("rate-limits");
  const current = parseInt((await store.get(key)) || "0", 10) || 0;
  if (current >= limit) return true;
  await store.set(key, String(current + 1));
  return false;
}

async function stripeGet(path, secretKey) {
  try {
    const resp = await fetch(`https://api.stripe.com/v1${path}`, {
      headers: { Authorization: `Bearer ${secretKey}` },
    });
    if (!resp.ok) return { error: `stripe_${resp.status}` };
    return { data: await resp.json() };
  } catch (_) {
    return { error: "stripe_unreachable" };
  }
}

/** Paid ModernTex and kit purchases made with this address, newest first. */
export async function purchasesForEmail(email, secretKey) {
  const found = new Map();
  // Stripe matches the email as stored; try it as typed and in lower case.
  for (const address of new Set([email, email.toLowerCase()])) {
    let after = "";
    for (let page = 0; page < MAX_PAGES; page++) {
      const query =
        `/checkout/sessions?customer_details%5Bemail%5D=${encodeURIComponent(address)}&limit=100` +
        (after ? `&starting_after=${encodeURIComponent(after)}` : "");
      const res = await stripeGet(query, secretKey);
      if (res.error) return { error: res.error };
      const rows = res.data?.data ?? [];
      for (const s of rows) {
        const product = s?.metadata?.product || "";
        if (typeof s?.id !== "string" || s.payment_status !== "paid") continue;
        if (!BLOB_DELIVERED_PRODUCTS.has(product)) continue;
        found.set(s.id, { sessionId: s.id, product, created: s.created || 0 });
      }
      if (!res.data?.has_more || rows.length === 0) break;
      after = rows[rows.length - 1].id;
    }
  }
  return { purchases: [...found.values()].sort((a, b) => b.created - a.created) };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/** The email body for a set of purchases; exported for tests. */
export function recoveryEmail(purchases, license) {
  const lines = [];
  const html = [];
  const mtx = purchases.filter((p) => p.product === "moderntex");
  if (mtx.length) {
    const link = `${SITE_ORIGIN}${BLOB_DELIVERED_PRODUCTS.get("moderntex").successPath}?session_id=${encodeURIComponent(mtx[0].sessionId)}`;
    lines.push("ModernTex", `Download page: ${link}`);
    html.push(`<h3>ModernTex</h3><p><a href="${escapeHtml(link)}">Open your download page</a></p>`);
    if (license) {
      lines.push(`License key (paste into ModernTex's "Have a license key?"): ${license}`,
        "This is a new key; any key you had before keeps working too.");
      html.push(`<p>License key (paste into ModernTex's "Have a license key?"):</p>` +
        `<p style="font-family: ui-monospace, monospace; font-size: 14px; letter-spacing: 0.5px;">${escapeHtml(license)}</p>` +
        `<p>This is a new key; any key you had before keeps working too.</p>`);
    } else {
      lines.push("Reply to this email for your license key.");
      html.push("<p>Reply to this email for your license key.</p>");
    }
    lines.push("");
  }
  for (const p of purchases.filter((q) => q.product !== "moderntex")) {
    const entry = BLOB_DELIVERED_PRODUCTS.get(p.product);
    const link = `${SITE_ORIGIN}${entry.successPath}?session_id=${encodeURIComponent(p.sessionId)}`;
    lines.push(entry.name.charAt(0).toUpperCase() + entry.name.slice(1), `Download page: ${link}`, "");
    html.push(`<h3>${escapeHtml(entry.name.charAt(0).toUpperCase() + entry.name.slice(1))}</h3><p><a href="${escapeHtml(link)}">Open your download page</a></p>`);
  }
  const intro = "Here are the purchases made with this address, as requested.";
  const outro = "If you did not ask for this, you can ignore it; nothing has changed.";
  return {
    subject: "Your Purplelink purchases",
    text: `${intro}\n\n${lines.join("\n")}\n${outro}\n\nPurplelink LLC, Atlanta, Georgia`,
    html: `<p>${intro}</p>${html.join("")}<p>${outro}</p><p>Purplelink LLC, Atlanta, Georgia</p>`,
  };
}

async function sendRecovery(to, purchases) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  if (!apiKey) return false;
  const license = purchases.some((p) => p.product === "moderntex") ? issueModernTexLicense() : null;
  const mail = recoveryEmail(purchases, license);
  try {
    const resp = await fetch(RESEND_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ from: ORDER_FROM_ADDRESS, reply_to: ORDER_REPLY_TO, to: [to], ...mail }),
    });
    return resp.ok;
  } catch (_) {
    return false;
  }
}

async function recover(email, secretKey) {
  const found = await purchasesForEmail(email, secretKey);
  if (found.error) {
    console.error("purchases-recover: lookup failed", found.error);
    return;
  }
  if (found.purchases.length && !(await sendRecovery(email, found.purchases))) {
    console.error("purchases-recover: email failed");
  }
}

export default async function handler(request, context) {
  if (request.method !== "POST") return json(405, { error: "method_not_allowed" });
  const body = await request.json().catch(() => null);
  const email = typeof body?.email === "string" ? body.email.trim() : "";
  if (!EMAIL_PATTERN.test(email)) {
    return json(400, { error: "bad_email", detail: "Enter the email address you used at checkout." });
  }
  if ((await overLimit("ip", clientIpOf(request), PER_IP_DAILY)) ||
      (await overLimit("email", email.toLowerCase(), PER_EMAIL_DAILY))) {
    return json(429, { error: "rate_limited", detail: "Too many requests today. Please try again tomorrow." });
  }
  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!secretKey) return json(500, { error: "misconfigured", detail: "Purchase lookup is not set up." });
  // Answer first, the same way for every address; look up and email afterwards.
  const work = recover(email, secretKey);
  if (context && typeof context.waitUntil === "function") context.waitUntil(work);
  else await work;
  return json(200, { status: "sent_if_found" });
}
