// The sales ledger tells the marketing hub which orders came from a Reddit ad (checkout.mjs metadata reddit_ad and
// reddit_click_id). The click id itself never leaves Stripe: the ledger says only whether one was present.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/sales-reddit.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

globalThis.Netlify = { env: { get: (k) => ({ STATS_TOKEN: "tok-123", STRIPE_SECRET_KEY: "sk_test_x" })[k] } };

const session = (id, metadata) => ({
  id, object: "checkout.session", payment_status: "paid", created: 1793000000, amount_total: 1999, currency: "usd",
  customer_details: { email: `${id}@example.com` }, metadata: { product: "moderntex", ...metadata },
});
const SESSIONS = [
  session("cs_ad_click", { reddit_ad: "1", reddit_click_id: "click-abc", attr_first: JSON.stringify({ s: "reddit", m: "cpc", t: "moderntex-reddit-261027-a" }) }),
  session("cs_ad_cookie", { reddit_ad: "1", attr_first: JSON.stringify({ s: "reddit", m: "cpc", c: "attr-cookie", d: "2026-10-28" }) }),
  session("cs_plain", { attr_first: JSON.stringify({ s: "google" }) }),
];

globalThis.fetch = async (url) => {
  const u = String(url);
  if (u.includes("/checkout/sessions")) return Response.json({ data: SESSIONS, has_more: false });
  if (u.includes("/balance") && !u.includes("balance_transactions")) return Response.json({ available: [], pending: [] });
  if (u.startsWith("https://api.stripe.com/")) return Response.json({ data: [], has_more: false });
  return new Response("offline", { status: 503 });
};

const sales = (await import("../functions/sales.mjs")).default;

test("ledger rows say which orders came from a Reddit ad, never the click id", async () => {
  const r = await sales(new Request("https://purplelink.llc/.netlify/functions/sales?days=3650", { headers: { "x-stats-token": "tok-123" } }));
  assert.equal(r.status, 200);
  const body = await r.json();
  const byId = Object.fromEntries(body.ledger.map((x) => [x.id, x]));
  assert.deepEqual(byId.cs_ad_click.reddit, { ad: true, click: true });
  assert.deepEqual(byId.cs_ad_cookie.reddit, { ad: true, click: false });
  assert.equal(byId.cs_plain.reddit, null);
  assert.ok(!JSON.stringify(body).includes("click-abc"), "the Reddit click id must not leave Stripe");
});
