// The Mac Suite purchase email: one link to the suite page, the ModernTex key in the body,
// and no second email when Stripe delivers the same event twice. Stripe, Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/suite-webhook.test.mjs

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
const { default: handler, BLOB_DELIVERED_PRODUCTS } = await import("../functions/stripe-webhook.mjs");

let calls;
beforeEach(() => {
  store.clear();
  calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    return new Response("{}", { status: 200 });
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
const completed = (product, id = "evt_1") => ({
  id, type: "checkout.session.completed",
  data: { object: { id: "cs_live_suite_abcdefghij", status: "complete", payment_status: "paid", amount_total: 3900,
    customer_details: { email: "buyer@example.com" }, metadata: { product } } },
});

test("the Suite is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("app-suite").successPath, "/suite/success/");
});

test("a paid Suite order is acknowledged and emails the suite page link once", async () => {
  const res = await handler(signed(completed("app-suite")));
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, "delivered_by_blobs");
  assert.equal(body.product, "app-suite");
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.subject, /Purplelink Mac Suite/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/suite\/success\/\?session_id=cs_live_suite_abcdefghij/);
  assert.match(mail.text, /ModernTex download, the Outbound Veil download, and your Vitae Plus key/);
  assert.match(mail.html, /\/suite\/success\//);
});

test("Stripe delivering the same event twice sends one email", async () => {
  await handler(signed(completed("app-suite", "evt_dup")));
  const again = await handler(signed(completed("app-suite", "evt_dup")));
  assert.equal((await again.json()).status, "duplicate_event_ignored");
  assert.equal(calls.filter((c) => c.url.startsWith("https://api.resend.com/")).length, 1);
});
