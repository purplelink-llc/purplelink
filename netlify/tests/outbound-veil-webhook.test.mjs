// The Outbound Veil purchase email carries the download page link and the setup guide link,
// and nobody else's email does. Stripe, Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/outbound-veil-webhook.test.mjs

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
const completed = (product, id) => ({
  id, type: "checkout.session.completed",
  data: { object: { id: "cs_live_ov_abcdefghij12", status: "complete", payment_status: "paid", amount_total: 2999,
    customer_details: { email: "buyer@example.com" }, metadata: { product } } },
});
const sentMail = () => JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);

test("an Outbound Veil order emails the download page and the setup guide", async () => {
  await handler(signed(completed("outbound-veil", "evt_ov")));
  const mail = sentMail();
  assert.match(mail.text, /outbound-veil\/success\/\?session_id=cs_live_ov_abcdefghij12/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/outbound-veil\/start\//);
  assert.match(mail.text, /Accessibility/);
  assert.match(mail.html, /outbound-veil\/start\//);
});

test("other products' emails do not mention the Outbound Veil setup guide", async () => {
  await handler(signed(completed("moderntex", "evt_mtx")));
  assert.doesNotMatch(sentMail().text, /outbound-veil\/start/);
});
