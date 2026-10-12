/**
 * RubbleFront email list: GET or POST /.netlify/functions/rubblefront-unsubscribe?u=<token>
 * Deletes the record and its tokens, keeps only a hashed suppression marker, and:
 *   GET  -> 302 to rubblefront.com/unsubscribed/
 *   POST -> 200 (RFC 8058 one-click, body List-Unsubscribe=One-Click)
 * An unknown token gets the same answer, so nothing is revealed.
 */
import { getStore } from "@netlify/blobs";
import { LIST_SITE, STORE, TOKEN_STORE, SUPPRESS_STORE, TOKEN_PATTERN, hashEmail, parseRecord, removeRecord } from "../lib/rubblefront-list.mjs";

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "POST") return new Response("Method not allowed", { status: 405 });
  const token = new URL(request.url).searchParams.get("u") || "";
  if (TOKEN_PATTERN.test(token)) {
    try {
      const email = await getStore(TOKEN_STORE).get(`u:${token}`);
      if (email) {
        const record = parseRecord(await getStore(STORE).get(email)) || { email, unsubscribeToken: token };
        await getStore(SUPPRESS_STORE).set(hashEmail(email), new Date().toISOString());
        await removeRecord(record);
        await getStore(TOKEN_STORE).delete(`u:${token}`);
      }
    } catch (_) {
      console.error("rubblefront-unsubscribe: storage failed");
      return new Response("Try again later", { status: 500 });
    }
  }
  if (request.method === "POST") return new Response("ok", { status: 200, headers: { "Cache-Control": "no-store" } });
  return new Response(null, { status: 302, headers: { Location: `${LIST_SITE}/unsubscribed/`, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
}
