/**
 * GET /.netlify/functions/buyer-offers?session_id=cs_...
 *
 * The success page asks for the buyer's cross-sell code (netlify/lib/buyer-codes.mjs). The Checkout Session id is
 * the proof of purchase, as on every other success page: it is long, random and only shown to the buyer.
 *
 *   200 { pending: true }  the webhook has not issued it yet (or this order earns none); the page asks again a few times
 *   200 { code, expires, expires_text, percent, source_product }
 *   400 { error: "invalid_request" }
 * Any 200 may also carry referral_link: the buyer's own referral link (netlify/lib/referrals.mjs), once the webhook
 * has registered the order.
 */
import { getStore } from "@netlify/blobs";
import { STORE, PERCENT_OFF, readRecord, expiryText } from "../lib/buyer-codes.mjs";
import { referralFor } from "../lib/referrals.mjs";

const SESSION_RE = /^cs_(live|test)_[A-Za-z0-9]{10,200}$/;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

export default async function handler(request, { nowMs = Date.now() } = {}) {
  if (request.method !== "GET") return json(405, { error: "method_not_allowed" });
  const sessionId = new URL(request.url).searchParams.get("session_id") || "";
  if (!SESSION_RE.test(sessionId)) return json(400, { error: "invalid_request" });
  let store;
  try { store = getStore(STORE); } catch (_) { return json(200, { pending: true }); }
  const ref = await referralFor(store, sessionId);
  const extra = ref ? { referral_link: ref.link } : {};
  const code = await store.get(`session/${sessionId}`).catch(() => null);
  if (!code) return json(200, { pending: true, ...extra });
  const rec = await readRecord(store, code);
  if (!rec) return json(200, { pending: true, ...extra });
  if (rec.used || Number(rec.expires) * 1000 <= nowMs) return json(200, { done: true, ...extra });
  return json(200, {
    ...extra,
    code,
    expires: new Date(Number(rec.expires) * 1000).toISOString(),
    expires_text: expiryText(rec.expires),
    percent: PERCENT_OFF,
    source_product: rec.source_product,
  });
}
