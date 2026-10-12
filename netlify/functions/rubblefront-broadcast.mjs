/**
 * RubbleFront email list: the broadcast endpoint. Never scheduled, never automatic; only
 * scripts/rubblefront-broadcast.py calls it, and only when a person runs it with --send.
 *
 * POST /.netlify/functions/rubblefront-broadcast        Authorization: Bearer <RUBBLEFRONT_BROADCAST_SECRET>
 *   { action: "count" }
 *       -> { count }                          confirmed, not-suppressed recipients (a number, never addresses)
 *   { action: "test", to, subject, text, html }
 *       -> { ok: true }                       one copy to one address; its unsubscribe link is inert
 *   { action: "send", broadcastId, subject, text, html, expect? }
 *       -> { sent, remaining, total }         sends to up to BATCH_SIZE recipients not yet sent for this
 *                                             broadcastId, and records them, so a retry or resume never
 *                                             double-sends. `expect` (first call) must equal the current
 *                                             count or nothing is sent (409).
 *
 * Every message gets its own unsubscribe link, List-Unsubscribe and List-Unsubscribe-Post headers, and the
 * postal line. Blobs: "rf-broadcast-sent" key "<broadcastId>:<sha256(email)>". Env: RESEND_API_KEY,
 * RUBBLEFRONT_BROADCAST_SECRET. Addresses are never logged or returned.
 */
import { getStore } from "@netlify/blobs";
import { timingSafeEqual } from "node:crypto";
import {
  FROM_ADDRESS, REPLY_TO, POSTAL_ADDRESS, TOKEN_PATTERN, hashEmail, unsubscribeUrlFor, unsubscribePageFor, unsubscribeHeaders,
  confirmedRecords, sendMail, EMAIL_PATTERN,
} from "../lib/rubblefront-list.mjs";

export const BATCH_SIZE = 50;
const SENT_STORE = "rf-broadcast-sent";
const BATCH_URL = "https://api.resend.com/emails/batch";
const ID_PATTERN = /^[a-z0-9-]{8,64}$/;

const reply = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });

function authorized(request) {
  const secret = Netlify.env.get("RUBBLEFRONT_BROADCAST_SECRET");
  const got = request.headers.get("authorization") ?? "";
  if (!secret) return false;
  const a = Buffer.from(got);
  const b = Buffer.from(`Bearer ${secret}`);
  return a.length === b.length && timingSafeEqual(a, b);
}

const escapeHtml = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function broadcastMail(to, token, subject, text, html) {
  const unsub = unsubscribeUrlFor(token);
  const page = unsubscribePageFor(token);
  return {
    from: FROM_ADDRESS,
    reply_to: REPLY_TO,
    to: [to],
    subject,
    text: `${text}\n\n--\nUnsubscribe: ${page}\n${POSTAL_ADDRESS}`,
    html: `${html}<hr><p><a href="${page}">Unsubscribe</a></p><p>${escapeHtml(POSTAL_ADDRESS)}</p>`,
    headers: unsubscribeHeaders(unsub),
  };
}

async function sendBatch(mails) {
  try {
    const resp = await fetch(BATCH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${Netlify.env.get("RESEND_API_KEY")}` },
      body: JSON.stringify(mails),
    });
    return resp.ok ? null : `resend_${resp.status}`;
  } catch (_) {
    return "resend_unreachable";
  }
}

export default async function handler(request) {
  if (request.method !== "POST") return reply(405, { error: "method_not_allowed" });
  if (!authorized(request)) return reply(401, { error: "unauthorized" });
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object") return reply(400, { error: "invalid_json" });

  try {
    if (body.action === "count") {
      return reply(200, { count: (await confirmedRecords()).length });
    }

    const subject = typeof body.subject === "string" ? body.subject.trim() : "";
    const text = typeof body.text === "string" ? body.text : "";
    const html = typeof body.html === "string" ? body.html : "";
    if (body.action === "test" || body.action === "send") {
      if (!subject || subject.length > 200 || !text || !html) return reply(400, { error: "invalid_message" });
    }

    if (body.action === "test") {
      const to = typeof body.to === "string" ? body.to.trim().toLowerCase() : "";
      if (!EMAIL_PATTERN.test(to)) return reply(400, { error: "invalid_email" });
      const failure = await sendMail(broadcastMail(to, "0".repeat(48), `[TEST] ${subject}`, text, html));
      if (failure) { console.error("rubblefront-broadcast: test failed", failure); return reply(502, { error: "send_failed" }); }
      return reply(200, { ok: true });
    }

    if (body.action === "send") {
      const id = typeof body.broadcastId === "string" ? body.broadcastId : "";
      if (!ID_PATTERN.test(id)) return reply(400, { error: "invalid_broadcast_id" });
      const records = await confirmedRecords();
      if (Number.isInteger(body.expect) && body.expect !== records.length) {
        return reply(409, { error: "count_changed", count: records.length });
      }
      const sentStore = getStore(SENT_STORE);
      const todo = [];
      for (const rec of records) {
        if (todo.length >= BATCH_SIZE) break;
        if ((await sentStore.get(`${id}:${hashEmail(rec.email)}`)) === null) todo.push(rec);
      }
      if (todo.length === 0) return reply(200, { sent: 0, remaining: 0, total: records.length });
      const failure = await sendBatch(todo.map((r) => broadcastMail(r.email, r.unsubscribeToken, subject, text, html)));
      if (failure) { console.error("rubblefront-broadcast: batch failed", failure); return reply(502, { error: "send_failed" }); }
      for (const rec of todo) await sentStore.set(`${id}:${hashEmail(rec.email)}`, new Date().toISOString());
      // Remaining = recipients not yet marked (cheap recount: total minus those marked in this and earlier calls).
      let remaining = 0;
      for (const rec of records) if ((await sentStore.get(`${id}:${hashEmail(rec.email)}`)) === null) remaining++;
      return reply(200, { sent: todo.length, remaining, total: records.length });
    }
    return reply(400, { error: "unknown_action" });
  } catch (_) {
    console.error("rubblefront-broadcast: failed");
    return reply(500, { error: "server_error" });
  }
}
