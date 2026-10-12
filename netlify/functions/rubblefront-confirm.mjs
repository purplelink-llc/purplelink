/**
 * RubbleFront email list, step 2: GET /.netlify/functions/rubblefront-confirm?t=<token>
 * Marks the pending record confirmed and sends the browser to rubblefront.com/confirmed/.
 * A bad, unknown or expired (7 days) token goes to /confirmed/?error=1. A second click on a used link
 * still lands on the success page. Clears any earlier unsubscribe marker: confirming is fresh consent.
 */
import { getStore } from "@netlify/blobs";
import {
  LIST_SITE, STORE, TOKEN_STORE, SUPPRESS_STORE, TOKEN_PATTERN,
  hashEmail, parseRecord, isExpiredPending, removeRecord,
} from "../lib/rubblefront-list.mjs";

const go = (path) => new Response(null, { status: 302, headers: { Location: `${LIST_SITE}${path}`, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });

export default async function handler(request) {
  if (request.method !== "GET") return new Response("Method not allowed", { status: 405 });
  const token = new URL(request.url).searchParams.get("t") || "";
  if (!TOKEN_PATTERN.test(token)) return go("/confirmed/?error=1");
  try {
    const email = await getStore(TOKEN_STORE).get(`c:${token}`);
    const record = email ? parseRecord(await getStore(STORE).get(email)) : null;
    if (!record || record.confirmToken !== token) return go("/confirmed/?error=1");
    if (record.status === "confirmed") return go("/confirmed/");
    if (isExpiredPending(record)) {
      await removeRecord(record);
      return go("/confirmed/?error=1");
    }
    record.status = "confirmed";
    record.confirmedAt = new Date().toISOString();
    await getStore(STORE).set(record.email, JSON.stringify(record));
    await getStore(SUPPRESS_STORE).delete(hashEmail(record.email));
    return go("/confirmed/");
  } catch (_) {
    console.error("rubblefront-confirm: storage failed");
    return go("/confirmed/?error=1");
  }
}
