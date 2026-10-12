/**
 * RubbleFront email list unsubscribe: /.netlify/functions/rubblefront-unsubscribe?u=<token>
 *   GET  -> changes nothing. 302 to https://rubblefront.com/unsubscribe/?u=<token>, a page with one button.
 *           (A mail scanner that follows the link must not unsubscribe anyone.)
 *   POST -> unsubscribes: deletes the record and its tokens, keeps only a hashed suppression marker, answers 200.
 *           Used by RFC 8058 one-click (List-Unsubscribe=One-Click, from the mail client) and by that page's
 *           button (fetch from rubblefront.com, so CORS is allowed for it and answers 200 {ok:true}).
 * An unknown or used token gets the same answers, so nothing is revealed.
 */
import { getStore } from "@netlify/blobs";
import { LIST_SITE, STORE, TOKEN_STORE, SUPPRESS_STORE, TOKEN_PATTERN, ALLOWED_ORIGINS, hashEmail, parseRecord, removeRecord } from "../lib/rubblefront-list.mjs";

const corsFor = (request) => {
  const origin = request.headers.get("origin");
  return origin && ALLOWED_ORIGINS.has(origin)
    ? { "Access-Control-Allow-Origin": origin, "Vary": "Origin" }
    : {};
};

export default async function handler(request) {
  const cors = corsFor(request);
  if (request.method === "OPTIONS") {
    if (!cors["Access-Control-Allow-Origin"]) return new Response(null, { status: 403 });
    return new Response(null, {
      status: 204,
      headers: { ...cors, "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400" },
    });
  }
  if (request.method !== "GET" && request.method !== "POST") return new Response("Method not allowed", { status: 405 });
  const token = new URL(request.url).searchParams.get("u") || "";

  if (request.method === "GET") {
    const dest = TOKEN_PATTERN.test(token) ? `${LIST_SITE}/unsubscribe/?u=${token}` : `${LIST_SITE}/unsubscribe/`;
    return new Response(null, { status: 302, headers: { Location: dest, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
  }

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
      return new Response("Try again later", { status: 500, headers: cors });
    }
  }
  return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...cors } });
}
