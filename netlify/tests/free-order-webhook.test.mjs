// A 100%-off promotion code completes a Paper Review checkout with payment_status "no_payment_required"
// and a $0 total. The webhook must still ask Modal for the upload token, and send the pre-discount
// subtotal so the backend's price check passes. Stripe, Modal and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/free-order-webhook.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", RESEND_API_KEY: "re_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };
const { default: handler } = await import("../functions/stripe-webhook.mjs");

let calls;
beforeEach(() => {
  store.clear();
  calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    return new Response(JSON.stringify({ tokens: ["tok"] }), { status: 200 });
  };
});

function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", {
    method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body,
  });
}
const completed = (over) => ({
  id: "evt_free", type: "checkout.session.completed",
  data: { object: { id: "cs_live_free_abcdefghij", status: "complete", payment_status: "paid", amount_total: 900,
    amount_subtotal: 900, customer_details: { email: "buyer@example.com" },
    metadata: { product: "paper-review-standard" }, ...over } },
});
const registerCalls = () => calls.filter((c) => c.url.includes("/paper-review/register-token"));

test("a $0 order from a 100%-off code is forwarded with its list price", async () => {
  const res = await handler(signed(completed({ payment_status: "no_payment_required", amount_total: 0 })));
  assert.equal(res.status, 200);
  const reg = registerCalls();
  assert.equal(reg.length, 1);
  const body = JSON.parse(reg[0].opts.body);
  assert.equal(body.amount_paid, 0);
  assert.equal(body.amount_subtotal, 900);
  assert.equal(body.product, "paper-review-standard");
});

test("an unpaid order with money still due is not forwarded", async () => {
  const res = await handler(signed(completed({ payment_status: "unpaid", amount_total: 900 })));
  assert.equal((await res.json()).status, "not_paid");
  assert.equal(registerCalls().length, 0);
});

test("no_payment_required with a non-zero total is not treated as free", async () => {
  const res = await handler(signed(completed({ payment_status: "no_payment_required", amount_total: 900 })));
  assert.equal((await res.json()).status, "not_paid");
  assert.equal(registerCalls().length, 0);
});

test("a paid order sends its subtotal too", async () => {
  await handler(signed(completed({})));
  const body = JSON.parse(registerCalls()[0].opts.body);
  assert.equal(body.amount_paid, 900);
  assert.equal(body.amount_subtotal, 900);
});
