/**
 * Per-UTC-day counter in the shared "rate-limits" Blobs store, keyed by a hash
 * of the value (an IP address or an email), so no raw address is stored.
 *
 * Returns true when the caller is over the limit. It fails open: if the store
 * is unreachable the request goes ahead, because blocking a paying customer is
 * worse than missing one throttle. Same pattern as purchase-license.mjs and
 * checklist-signup.mjs.
 */
import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";

export function clientIp(request) {
  return request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";
}

export async function overDailyLimit(kind, value, limit) {
  try {
    const day = new Date().toISOString().slice(0, 10);
    const digest = createHash("sha256").update(String(value)).digest("hex").slice(0, 16);
    const key = `rl:${kind}:${day}:${digest}`;
    const store = getStore("rate-limits");
    const current = parseInt((await store.get(key)) || "0", 10) || 0;
    if (current >= limit) return true;
    await store.set(key, String(current + 1));
    return false;
  } catch (err) {
    console.error("ratelimit: store unavailable, allowing", kind, err?.message);
    return false;
  }
}
