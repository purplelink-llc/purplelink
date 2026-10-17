/**
 * POST /.netlify/functions/subscribe
 *
 * Retired 2026-10-17 with the Daily Digest. Every request, whatever the method or body, gets 410 Gone
 * and nothing is stored or sent, so a cached old page cannot add anyone to the list.
 *
 * Still working on purpose: confirm-signup.mjs (a confirmation link already in someone's inbox),
 * unsubscribe.mjs, subscription-portal.mjs and subscribers-list.mjs.
 */
export default async function handler() {
  return new Response(
    JSON.stringify({ error: "gone", message: "The Daily Digest is no longer published and signups are closed." }),
    { status: 410, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } },
  )
}
