// One-click unsubscribe for the day-14 follow-up email. GET shows a short page; POST is RFC 8058 List-Unsubscribe-Post.
// The token is an HMAC of the address (netlify/lib/followup.mjs), so no record exists to look up. A valid token
// writes a suppression keyed by a hash of the address; the page says the same thing for any token.
import { getStore } from "@netlify/blobs";
import { emailHash, verifyUnsubscribeToken } from "../lib/followup.mjs";

function page(title, body, status = 200) {
  return new Response(`<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex">
    <title>${title} | Purplelink LLC</title>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <script src="/theme.js"></script>
    <link rel="stylesheet" href="/styles.css">
  </head>
  <body>
    <main id="main-content" class="static-page">
      <h1>${title}</h1>
      ${body}
    </main>
  </body>
</html>`, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

export default async function handler(request) {
  const url = new URL(request.url);
  const token = url.searchParams.get("u") || "";
  const secret = Netlify.env.get("FOLLOWUP_UNSUBSCRIBE_SECRET") || Netlify.env.get("STRIPE_WEBHOOK_SECRET");
  const oneClick = request.method === "POST";
  if (request.method !== "GET" && !oneClick) return new Response("method_not_allowed", { status: 405 });
  const email = secret ? verifyUnsubscribeToken(token, secret) : null;
  if (email) {
    try {
      await getStore("followup-suppressed").set(emailHash(email), new Date().toISOString());
    } catch (_) {
      console.error("followup-unsubscribe: write failed");
      if (oneClick) return new Response(JSON.stringify({ error: "server_error" }), { status: 500, headers: { "Content-Type": "application/json" } });
      return page("Something went wrong", '<p>That could not be saved just now. Reply to the email with the word stop, or write to <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>.</p>', 500);
    }
  }
  if (oneClick) return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
  return page("Unsubscribed", "<p>You will get no more follow-up email from Purplelink LLC about your purchase.</p><p><a href=\"/\">Back to the site</a></p>");
}
