/**
 * RubbleFront email list, step 1: someone asks for news. Nothing is on the list until they click the link
 * in the confirmation email (see rubblefront-confirm.mjs). Shared helpers: netlify/lib/rubblefront-list.mjs.
 *
 * POST /.netlify/functions/rubblefront-subscribe   from rubblefront.com (or purplelink.llc, for testing)
 *   body: { email, source: "hero"|"footer", website?: "<honeypot>" }
 *   200 { ok: true }   the same answer whether the address is new, pending, already confirmed or a bot
 *   400 invalid_json | invalid_email   403 forbidden_origin   429 rate_limited
 *   502 send_failed    Resend refused; nothing is kept
 *
 * The address is never logged; errors log a code only. Env: RESEND_API_KEY.
 */
import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";
import {
  SITE_ORIGIN, ALLOWED_ORIGINS, EMAIL_PATTERN, DAY_MS, STORE, TOKEN_STORE,
  newToken, parseRecord, isExpiredPending, removeRecord, sendMail, confirmationEmail,
} from "../lib/rubblefront-list.mjs";

const PER_EMAIL_DAILY = 3;
const PER_IP_DAILY = 20;
const SOURCES = new Set(["hero", "footer"]);

function allowedOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return SITE_ORIGIN; // curl and same-origin posts send none
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

const clientIpOf = (request) => request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";

async function overLimit(kind, value, limit) {
  const day = new Date().toISOString().slice(0, 10);
  const digest = createHash("sha256").update(value).digest("hex").slice(0, 16);
  const key = `rl:rf-subscribe-${kind}:${day}:${digest}`;
  const store = getStore("rate-limits");
  const current = parseInt((await store.get(key)) || "0", 10) || 0;
  if (current >= limit) return true;
  await store.set(key, String(current + 1));
  return false;
}

export default async function handler(request) {
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
  const source = SOURCES.has(body.source) ? body.source : "other";

  try {
    if ((await overLimit("ip", clientIpOf(request), PER_IP_DAILY)) || (await overLimit("email", email, PER_EMAIL_DAILY))) {
      return json(429, { error: "rate_limited" }, origin);
    }
    const store = getStore(STORE);
    const tokens = getStore(TOKEN_STORE);
    const existing = parseRecord(await store.get(email));
    const now = Date.now();
    // Already on the list: same answer, no email, nothing revealed.
    if (existing?.status === "confirmed") return json(200, { ok: true }, origin);
    // Pending and asked less than a day ago: nothing new.
    if (existing?.status === "pending" && !isExpiredPending(existing, now) && now - Date.parse(existing.createdAt) < DAY_MS) {
      return json(200, { ok: true }, origin);
    }

    const record = {
      email, status: "pending", source, createdAt: new Date(now).toISOString(),
      confirmToken: newToken(), unsubscribeToken: newToken(),
    };
    // Written before the send, so a second submission arriving meanwhile sees it and does not send again.
    await store.set(email, JSON.stringify(record));
    await tokens.set(`c:${record.confirmToken}`, email);
    await tokens.set(`u:${record.unsubscribeToken}`, email);
    if (existing) {
      if (existing.confirmToken) await tokens.delete(`c:${existing.confirmToken}`);
      if (existing.unsubscribeToken) await tokens.delete(`u:${existing.unsubscribeToken}`);
    }

    const failure = await sendMail(confirmationEmail(email, record));
    if (failure) {
      console.error("rubblefront-subscribe: email failed", failure);
      await removeRecord(record); // nobody is kept who got no email
      return json(502, { error: "send_failed" }, origin);
    }
    return json(200, { ok: true }, origin);
  } catch (_) {
    console.error("rubblefront-subscribe: storage failed");
    return json(500, { error: "server_error" }, origin);
  }
}
