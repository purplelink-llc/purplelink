/**
 * GET /.netlify/functions/health
 *
 * Liveness probe for the uptime workflow (.github/workflows/uptime.yml). It proves the functions
 * runtime is up and that Netlify Blobs answers a read. It has no side effects: one read of a key that
 * does not exist, no write, no Stripe or email call, and it returns no data from the store.
 *
 * 200 { ok: true }                 runtime and Blobs both answered
 * 503 { ok: false, blobs: false }  the Blobs read failed
 */
import { getStore } from "@netlify/blobs";

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  let blobs = true;
  try {
    await getStore("rate-limits").get("health-probe");
  } catch {
    blobs = false;
  }
  return new Response(JSON.stringify(blobs ? { ok: true } : { ok: false, blobs: false }), {
    status: blobs ? 200 : 503,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
