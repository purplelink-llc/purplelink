// Reddit Conversions API: a server-side Purchase event for a ModernTex sale that came from a Reddit ad.
// Sent from stripe-webhook.mjs AFTER delivery has finished, never awaited by the webhook's response, and it never
// throws, so it cannot break or delay a license, a download or the 2xx to Stripe.
//
// Reddit Ads Conversions API v2.0 (reference: https://ads-api.reddit.com/docs/v2/ , Conversions section;
// help article: https://business.reddithelp.com/s/article/Conversions-API):
//   POST https://ads-api.reddit.com/api/v2.0/conversions/events/{account or pixel id}
//   Authorization: Bearer <conversion access token>, Content-Type: application/json
//   { test_mode, events: [{ event_at (ISO 8601), event_type: { tracking_type: "Purchase" }, click_id,
//       event_metadata: { conversion_id, currency, item_count, value_decimal },
//       user: { email: <SHA-256 hex of the trimmed, lowercased email> } }] }
// The conversion_id is the Stripe Checkout Session id, the same value site/reddit-pixel.js sends from the browser,
// so Reddit de-duplicates the pixel and server events (same conversion id and event name).
// Keep this file in step with Reddit's docs if they change; nothing here is secret (the token is an env var).
import { createHash } from "node:crypto";

export const REDDIT_PIXEL_ID = "a2_jx9tsee4sm5h"; // same id as site/reddit-pixel.js
export const CAPI_ORIGIN = "https://ads-api.reddit.com";
export const CAPI_PRODUCTS = new Set(["moderntex", "moderntex-seats"]); // ModernTex only
const TIMEOUT_MS = 3000;
const CLICK_ID_RE = /^[\w.\-:=]{1,128}$/;
const ID_RE = /^[A-Za-z0-9_\-]{1,64}$/;

let warnedNoToken = false;

export function isRedditSale(session) {
  const m = (session && session.metadata) || {};
  return m.reddit_ad === "1" && CAPI_PRODUCTS.has(m.product);
}

export function buildEvent(session, nowMs = Date.now()) {
  const cents = session.amount_total;
  const m = session.metadata || {};
  const event = {
    event_at: new Date(nowMs).toISOString(),
    event_type: { tracking_type: "Purchase" },
    event_metadata: {
      conversion_id: String(session.id),
      currency: String(session.currency || "usd").toUpperCase(),
      item_count: 1,
      value_decimal: Math.round(cents) / 100,
    },
  };
  if (m.reddit_click_id && CLICK_ID_RE.test(m.reddit_click_id)) event.click_id = m.reddit_click_id;
  const email = ((session.customer_details && session.customer_details.email) || session.customer_email || "").trim().toLowerCase();
  if (email) event.user = { email: createHash("sha256").update(email).digest("hex") };
  return event;
}

// Resolves to a short status string; never rejects. Logs the status only (no token, no email).
export async function sendRedditPurchase(session, { env = (k) => process.env[k], fetchImpl = globalThis.fetch, nowMs } = {}) {
  try {
    if (!isRedditSale(session)) return "skipped_not_reddit";
    if (session.payment_status !== "paid" || !Number.isFinite(session.amount_total) || session.amount_total <= 0) return "skipped_no_revenue";
    const token = env("REDDIT_CAPI_TOKEN");
    if (!token) {
      if (!warnedNoToken) { warnedNoToken = true; console.debug("reddit-capi: REDDIT_CAPI_TOKEN is not set, server-side Purchase events are off"); }
      return "skipped_no_token";
    }
    const acct = env("REDDIT_AD_ACCOUNT_ID");
    const id = acct && ID_RE.test(acct) ? acct : REDDIT_PIXEL_ID;
    const url = `${CAPI_ORIGIN}/api/v2.0/conversions/events/${id}`;
    const body = JSON.stringify({ test_mode: env("REDDIT_CAPI_TEST_MODE") === "1", events: [buildEvent(session, nowMs)] });
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const r = await fetchImpl(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body,
          signal: AbortSignal.timeout(TIMEOUT_MS),
        });
        if (r.ok) return "sent";
        console.warn("reddit-capi: rejected with status", r.status);
        if (r.status < 500 && r.status !== 429) return "rejected";
      } catch (err) {
        console.warn("reddit-capi: request failed", (err && err.name) || "error");
      }
    }
    return "failed";
  } catch (err) {
    console.warn("reddit-capi: unexpected error", (err && err.name) || "error");
    return "failed";
  }
}
