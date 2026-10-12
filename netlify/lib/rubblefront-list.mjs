/**
 * Shared pieces of the RubbleFront double opt-in email list. Used by rubblefront-subscribe, -confirm,
 * -unsubscribe and -broadcast. Never logs an address.
 *
 * Blobs (all new; the academic digest's "subscribers" store is not touched):
 *   "rf-list"             key: lowercase email
 *                         value: { email, status: "pending"|"confirmed", source, createdAt, confirmedAt?,
 *                                  confirmToken, unsubscribeToken }
 *   "rf-list-tokens"      key: "c:<token>" or "u:<token>", value: email (random tokens, so links carry no address)
 *   "rf-list-suppressed"  key: sha256(email), value: ISO time. Written on unsubscribe, cleared when the same
 *                         person confirms a new signup. A broadcast never reaches a suppressed address.
 *   "rate-limits"         the shared per-day counters (hashed keys).
 */
import { createHash, randomBytes } from "node:crypto";
import { getStore } from "@netlify/blobs";

export const SITE_ORIGIN = "https://purplelink.llc";
export const LIST_SITE = "https://rubblefront.com";
export const ALLOWED_ORIGINS = new Set([LIST_SITE, "https://www.rubblefront.com", SITE_ORIGIN, "https://www.purplelink.llc"]);
export const RESEND_API_URL = "https://api.resend.com/emails";
export const FROM_ADDRESS = "RubbleFront <news@purplelink.llc>";
export const REPLY_TO = "ben@purplelink.llc";
// The one place the postal line lives. CAN-SPAM postal address (Purplelink's registered office, chosen by Ben).
export const POSTAL_ADDRESS = "Purplelink LLC, 8735 Dunwoody Place STE N, Atlanta, GA 30350, USA";
export const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;
export const TOKEN_PATTERN = /^[a-f0-9]{48}$/;
export const DAY_MS = 24 * 60 * 60 * 1000;
export const PENDING_EXPIRY_DAYS = 7;
export const STORE = "rf-list";
export const TOKEN_STORE = "rf-list-tokens";
export const SUPPRESS_STORE = "rf-list-suppressed";

export const newToken = () => randomBytes(24).toString("hex");
export const hashEmail = (email) => createHash("sha256").update(email).digest("hex");
export const confirmUrlFor = (t) => `${SITE_ORIGIN}/.netlify/functions/rubblefront-confirm?t=${t}`;
// The link a person clicks: a page on rubblefront.com with a button. The List-Unsubscribe header keeps the
// function URL, because mail clients POST to it (RFC 8058) and a plain GET there changes nothing.
export const unsubscribePageFor = (t) => `${LIST_SITE}/unsubscribe/?u=${t}`;
export const unsubscribeUrlFor = (t) => `${SITE_ORIGIN}/.netlify/functions/rubblefront-unsubscribe?u=${t}`;

export function parseRecord(raw) {
  try { return raw ? JSON.parse(raw) : null; } catch (_) { return null; }
}

export function isExpiredPending(record, now = Date.now()) {
  return record?.status === "pending" && now - Date.parse(record.createdAt) > PENDING_EXPIRY_DAYS * DAY_MS;
}

/** Remove a record and every token that points at it. */
export async function removeRecord(record) {
  if (!record) return;
  const store = getStore(STORE);
  const tokens = getStore(TOKEN_STORE);
  await store.delete(record.email);
  if (record.confirmToken) await tokens.delete(`c:${record.confirmToken}`);
  if (record.unsubscribeToken) await tokens.delete(`u:${record.unsubscribeToken}`);
}

export async function sendMail(mail) {
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

export const unsubscribeHeaders = (url) => ({
  "List-Unsubscribe": `<${url}>, <mailto:${REPLY_TO}?subject=unsubscribe>`,
  "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
});

export function confirmationEmail(to, record) {
  const link = confirmUrlFor(record.confirmToken);
  const unsub = unsubscribeUrlFor(record.unsubscribeToken);
  const page = unsubscribePageFor(record.unsubscribeToken);
  return {
    from: FROM_ADDRESS,
    reply_to: REPLY_TO,
    to: [to],
    subject: "Confirm your email for RubbleFront news",
    text: `Someone, probably you, asked for RubbleFront news at this address. To get it, confirm with this link:\n\n${link}\n\nYou will get news about the demo and the launch, and nothing else. If you did not ask, ignore this email and nothing happens.\n\nUnsubscribe: ${page}\n\n${POSTAL_ADDRESS}`,
    html: `<p>Someone, probably you, asked for RubbleFront news at this address. To get it, confirm with this link:</p><p><a href="${link}">Confirm my email</a></p><p>You will get news about the demo and the launch, and nothing else. If you did not ask, ignore this email and nothing happens.</p><p><a href="${page}">Unsubscribe</a></p><p>${POSTAL_ADDRESS}</p>`,
    headers: unsubscribeHeaders(unsub),
  };
}

export async function isSuppressed(email) {
  return (await getStore(SUPPRESS_STORE).get(hashEmail(email))) !== null;
}

/** Every confirmed, not-suppressed record, sorted by address. Pages through the store. */
export async function confirmedRecords() {
  const store = getStore(STORE);
  const out = [];
  let cursor;
  do {
    const page = await store.list({ cursor });
    for (const { key } of page.blobs ?? []) {
      const rec = parseRecord(await store.get(key));
      if (rec && rec.status === "confirmed" && rec.email && rec.unsubscribeToken && !(await isSuppressed(rec.email))) out.push(rec);
    }
    cursor = page.cursor;
  } while (cursor);
  out.sort((a, b) => (a.email < b.email ? -1 : 1));
  return out;
}
