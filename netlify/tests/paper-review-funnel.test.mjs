// Paper Review funnel instrumentation (docs/designs/paper-review-growth.md, Part A):
//  - checkout.mjs writes metadata[pr_preview] for Paper Review products when the page says the buyer ran the free
//    check in the last 30 days, and the flag is part of the idempotency key;
//  - sales.mjs gives each Paper Review order `purchase` (sha256 of the session id, first 16 hex) and `pr_preview`,
//    and lists Paper Review comps (100%-off orders) with the same fields.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/paper-review-funnel.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {} }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

globalThis.Netlify = {
  env: {
    get: (key) => {
      if (key === "STRIPE_SECRET_KEY") return "sk_test_dummy";
      if (key === "STATS_TOKEN") return "tok-123";
      if (key.startsWith("STRIPE_PRICE_")) return "price_dummy";
      return undefined;
    },
  },
};

const { default: checkout } = await import("../functions/checkout.mjs");
const sales = (await import("../functions/sales.mjs")).default;

async function post(body, ip) {
  const realFetch = globalThis.fetch;
  let captured = null;
  globalThis.fetch = async (url, opts) => {
    if (String(url).includes("api.stripe.com")) {
      captured = { body: new URLSearchParams(opts.body), key: opts.headers["Idempotency-Key"] };
      return Response.json({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const res = await checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip },
      body: JSON.stringify(body),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = realFetch;
  }
  return captured;
}

test("pr_preview becomes metadata on Paper Review products", async () => {
  for (const [i, product] of ["paper-review-standard", "paper-review-pack-5"].entries()) {
    const c = await post({ product, pr_preview: 1 }, `203.0.113.${10 + i}`);
    assert.equal(c.body.get("metadata[pr_preview]"), "1", product);
  }
});

test("no flag, no metadata; only the exact value 1 counts", async () => {
  const none = await post({ product: "paper-review-standard" }, "203.0.113.20");
  assert.equal(none.body.get("metadata[pr_preview]"), null);
  for (const [i, bad] of [true, "1", 2, null].entries()) {
    const c = await post({ product: "paper-review-standard", pr_preview: bad }, `203.0.113.${21 + i}`);
    assert.equal(c.body.get("metadata[pr_preview]"), null, JSON.stringify(bad));
  }
});

test("other products ignore pr_preview", async () => {
  const c = await post({ product: "moderntex", pr_preview: 1 }, "203.0.113.30");
  assert.equal(c.body.get("metadata[pr_preview]"), null);
});

test("the flag changes the idempotency key, and the key is stable without it", async () => {
  const ip = "203.0.113.40";
  const a = await post({ product: "paper-review-standard" }, ip);
  const a2 = await post({ product: "paper-review-standard" }, ip);
  const b = await post({ product: "paper-review-standard", pr_preview: 1 }, ip);
  assert.equal(a.key, a2.key);
  assert.notEqual(a.key, b.key);
});

// ---- sales.mjs -------------------------------------------------------------

const prSession = (id, product, amount, metadata = {}) => ({
  id, object: "checkout.session", payment_status: "paid", created: 1793000000, amount_total: amount, currency: "usd",
  customer_details: { email: `${id}@example.com` }, metadata: { product, ...metadata },
});
const SESSIONS = [
  prSession("cs_pr_flagged", "paper-review-standard", 900, { pr_preview: "1" }),
  prSession("cs_pr_plain", "paper-review-deep", 1500),
  prSession("cs_pr_comp", "paper-review-standard", 0, { pr_preview: "1" }),
  prSession("cs_other", "moderntex", 1999, { pr_preview: "1" }),
];
const hash = (id) => createHash("sha256").update(id).digest("hex").slice(0, 16);

test("Paper Review ledger orders carry purchase and pr_preview; other products do not", async () => {
  globalThis.fetch = async (url) => {
    const u = String(url);
    if (u.includes("/checkout/sessions")) return Response.json({ data: SESSIONS, has_more: false });
    if (u.includes("/balance") && !u.includes("balance_transactions")) return Response.json({ available: [], pending: [] });
    if (u.startsWith("https://api.stripe.com/")) return Response.json({ data: [], has_more: false });
    return new Response("offline", { status: 503 });
  };
  const r = await sales(new Request("https://purplelink.llc/.netlify/functions/sales?days=3650", { headers: { "x-stats-token": "tok-123" } }));
  assert.equal(r.status, 200);
  const body = await r.json();
  const byId = Object.fromEntries(body.ledger.map((x) => [x.id, x]));
  assert.equal(byId.cs_pr_flagged.purchase, hash("cs_pr_flagged"));
  assert.equal(byId.cs_pr_flagged.pr_preview, true);
  assert.equal(byId.cs_pr_plain.purchase, hash("cs_pr_plain"));
  assert.equal(byId.cs_pr_plain.pr_preview, false);
  assert.ok(!("purchase" in byId.cs_other) && !("pr_preview" in byId.cs_other));
  // The comp is not an order, but the funnel counts it as a signup.
  assert.ok(!byId.cs_pr_comp);
  assert.equal(body.comps.orders, 1);
  assert.equal(body.comps.paperReview.length, 1);
  const comp = body.comps.paperReview[0];
  assert.equal(comp.purchase, hash("cs_pr_comp"));
  assert.equal(comp.pr_preview, true);
  assert.ok(comp.cust && !JSON.stringify(body.comps).includes("@example.com"), "no email leaves sales.mjs");
});
