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
  data: { object: { id: "cs_live_suite_abcdefghij", status: "complete", payment_status: "paid", amount_total: 5400,
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
  assert.match(mail.text, /That page has five things: the ModernTex, Outbound Veil, Legroom and Keyfeel downloads, and your Vitae Plus key/);
  assert.match(mail.html, /ModernTex, Outbound Veil, Legroom and Keyfeel downloads/);
  assert.match(mail.html, /\/suite\/success\//);
});

test("Stripe delivering the same event twice sends one email", async () => {
  await handler(signed(completed("app-suite", "evt_dup")));
  const again = await handler(signed(completed("app-suite", "evt_dup")));
  assert.equal((await again.json()).status, "duplicate_event_ignored");
  assert.equal(calls.filter((c) => c.url.startsWith("https://api.resend.com/")).length, 1);
});

test("Legroom is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("legroom").successPath, "/legroom/success/");
});

test("a paid Legroom order emails the download page and the one-sentence review ask, with no signing secret configured it still delivers, without a key", async () => {
  const res = await handler(signed({ ...completed("legroom", "evt_lg"), data: { object: { ...completed("legroom").data.object, id: "cs_live_legroom_abcdefg1", amount_total: 900 } } }));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.subject, /Legroom for macOS download/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/legroom\/success\/\?session_id=cs_live_legroom_abcdefg1/);
  assert.match(mail.text, /If Legroom is useful, reply to this email with one sentence/);
  assert.doesNotMatch(mail.text, /license key|MTX1|Vitae/i);
  assert.doesNotMatch(mail.text, /—|–/);
  assert.match(mail.html, /legroom\/success\//);
});

test("the Suite email mentions Legroom but carries no Legroom review ask", async () => {
  await handler(signed(completed("app-suite", "evt_s2")));
  const suiteMail = JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);
  assert.doesNotMatch(suiteMail.text, /If Legroom is useful/);
  assert.match(suiteMail.text, /Legroom/);
});

test("Keyfeel is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("keyfeel").successPath, "/keyfeel/success/");
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("keyfeel").name, "Keyfeel for macOS");
});

test("a paid Keyfeel order emails the download page, the Input Monitoring note and the Keyfeel license key", async () => {
  env.KEYFEEL_LICENSE_PRIVATE_KEY = Buffer.alloc(32, 9).toString("base64");
  const res = await handler(signed({ ...completed("keyfeel", "evt_kf"), data: { object: { ...completed("keyfeel").data.object, id: "cs_live_keyfeel_abcdefg1", amount_total: 999 } } }));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.subject, /Keyfeel for macOS download/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/keyfeel\/success\/\?session_id=cs_live_keyfeel_abcdefg1/);
  assert.match(mail.text, /Input Monitoring/);
  assert.match(mail.text, /never the characters/);
  assert.match(mail.text, /Your Keyfeel license key[^\n]*\nKFL1-/);
  assert.doesNotMatch(mail.text, /MTX1|Vitae|Outbound Veil/i);
  assert.doesNotMatch(mail.text, /—|–/);
  assert.match(mail.html, /keyfeel\/success\//);
  assert.match(mail.html, /KFL1-/);
  delete env.KEYFEEL_LICENSE_PRIVATE_KEY;
});

test("other products' emails do not carry the Keyfeel permission note", async () => {
  await handler(signed(completed("legroom", "evt_lg2")));
  const mail = JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);
  assert.doesNotMatch(mail.text, /Input Monitoring/);
});
