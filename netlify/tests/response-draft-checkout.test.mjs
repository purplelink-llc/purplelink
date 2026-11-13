// Selling the response letter draft ($24, response-draft): closed until RESPONSE_DRAFT_OPEN is 1, then sold at the
// catalog's $24 (or the env Price when one is set) with the drafting upload page as the success page. Stripe is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/response-draft-checkout.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {}, delete: async () => {}, list: async () => ({ blobs: [] }) }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_SECRET_KEY: "sk_test_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: checkout } = await import("../functions/checkout.mjs");

let calls;
let ipN = 10;
beforeEach(() => {
  calls = [];
  delete env.RESPONSE_DRAFT_OPEN; delete env.STRIPE_PRICE_RESPONSE_DRAFT;
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (String(url).includes("api.stripe.com/v1/checkout/sessions") && opts.method === "POST") {
      return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  };
});

const post = (body) => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": `198.51.100.${ipN++}` }, body: JSON.stringify(body) }));
const stripeParams = () => new URLSearchParams(calls.find((c) => c.url.includes("/checkout/sessions")).opts.body);
const stripeCalls = () => calls.filter((c) => c.url.startsWith("https://api.stripe.com/")).length;

test("response-draft is not for sale until RESPONSE_DRAFT_OPEN is 1, and never reaches Stripe", async () => {
  for (const v of [undefined, "", "0", "true"]) {
    if (v === undefined) delete env.RESPONSE_DRAFT_OPEN; else env.RESPONSE_DRAFT_OPEN = v;
    const res = await post({ product: "response-draft" });
    assert.equal(res.status, 400, `RESPONSE_DRAFT_OPEN=${v}`);
    assert.equal((await res.json()).error, "not_for_sale");
  }
  assert.equal(stripeCalls(), 0, "no Stripe session is created");
});

test("once open, response-draft sells at the catalog's $24 and lands on the drafting upload page", async () => {
  env.RESPONSE_DRAFT_OPEN = "1";
  const res = await post({ product: "response-draft", amount: 1 });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "2400", "the price comes from the catalog, not the request");
  assert.match(p.get("success_url"), /\/tools\/response-review\/draft\/upload\/\?session_id=/);
  assert.equal(p.get("metadata[product]"), "response-draft");
});

test("once open, an env Price for response-draft wins over the inline amount", async () => {
  env.RESPONSE_DRAFT_OPEN = "1";
  env.STRIPE_PRICE_RESPONSE_DRAFT = "price_test_draft";
  const res = await post({ product: "response-draft" });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price]"), "price_test_draft");
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), null);
});
