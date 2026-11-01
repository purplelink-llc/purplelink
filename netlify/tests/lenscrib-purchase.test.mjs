// Selling Lenscrib: the checkout catalog, the purchase email (link, key, model-download note), the Suite and
// bundle emails (which must not carry it), and the recovery email. Stripe, Resend and Blobs are stubbed; signing
// keys are throwaway. The production keys are never read.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/lenscrib-purchase.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
    list: async () => ({ blobs: [] }),   // nothing is published yet: an entitled buyer gets 'no release is staged', not 403
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", RESEND_API_KEY: "re_dummy",
  LENSCRIB_LICENSE_PRIVATE_KEY: Buffer.alloc(32, 9).toString("base64"),
  TAPEFOLIO_LICENSE_PRIVATE_KEY: Buffer.alloc(32, 6).toString("base64"),
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook, BLOB_DELIVERED_PRODUCTS } = await import("../functions/stripe-webhook.mjs");
const { recoveryEmail } = await import("../functions/purchases-recover.mjs");

let calls, session;
beforeEach(() => {
  store.clear(); calls = []; session = null;
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    const u = String(url);
    if (u.includes("api.stripe.com/v1/checkout/sessions") && opts.method === "POST") return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
    if (session && u.startsWith("https://api.stripe.com/v1/checkout/sessions/")) return new Response(JSON.stringify(session), { status: 200 });
    return new Response("{}", { status: 200 });
  };
});

const post = (body, ip = "203.0.113.9") => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": ip }, body: JSON.stringify(body) }));
const stripeParams = () => new URLSearchParams(calls.find((c) => c.url.includes("/checkout/sessions")).opts.body);

function signed(event) {
  const body = JSON.stringify(event); const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", { method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body });
}
const paid = (metadata, amount, id, sid) => ({ id, type: "checkout.session.completed", data: { object: { id: sid, status: "complete", payment_status: "paid", amount_total: amount,
  customer_details: { email: "buyer@example.com" }, metadata } } });
const mailOf = () => JSON.parse(calls.filter((c) => c.url.startsWith("https://api.resend.com/"))[0].opts.body);

// ---- checkout ----

test("checkout sells Lenscrib at $19.99 from the catalog, with its own success page and refund line", async () => {
  const res = await post({ product: "lenscrib", amount: 1 });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "1999", "the price comes from the catalog, not the request");
  assert.equal(p.get("line_items[0][price_data][product_data][name]"), "Lenscrib for macOS");
  assert.match(p.get("success_url"), /\/lenscrib\/success\/\?session_id=/);
  assert.equal(p.get("metadata[product]"), "lenscrib");
  assert.match(p.get("custom_text[submit][message]") || "", /full \$19\.99/);
});

test("Lenscrib is not a custom bundle part, and the Suite line does not name it", async () => {
  const bad = await post({ product: "bundle-2", apps: ["lenscrib", "panely"] });
  assert.equal(bad.status, 400);
  await post({ product: "app-suite" });
  assert.doesNotMatch(stripeParams().get("line_items[0][price_data][product_data][name]"), /Lenscrib/);
});

// ---- delivery ----

test("Lenscrib is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("lenscrib").successPath, "/lenscrib/success/");
});

test("a paid Lenscrib order emails the page link, its key and the model-download note", async () => {
  const res = await webhook(signed(paid({ product: "lenscrib" }, 1999, "evt_lc", "cs_live_lc_abcdefghij")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = mailOf();
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/lenscrib\/success\/\?session_id=cs_live_lc_abcdefghij/);
  assert.match(mail.text, /Your Lenscrib license key[^\n]*\nLCB1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}\n/);
  assert.match(mail.text, /on up to two of your Macs/);
  assert.match(mail.text, /macOS 14 or later/);
  assert.match(mail.text, /about 3 GB/);
  assert.match(mail.text, /The model can be wrong/);
  assert.doesNotMatch(mail.text, /Tapefolio|TFL1/);
  assert.doesNotMatch(mail.text + mail.html, /[—;]\s*$/m);
});

test("a paid Suite order carries no Lenscrib key or text", async () => {
  await webhook(signed(paid({ product: "app-suite" }, 5999, "evt_su", "cs_live_su_abcdefghij")));
  const mail = mailOf();
  assert.doesNotMatch(mail.text + mail.html, /Lenscrib|LCB1/);
});

// ---- recovery ----

test("the recovery email lists a Lenscrib purchase with its page and key, and a Suite purchase without one", () => {
  const key = "LCB1-AAAAA-BBBBB";
  const only = recoveryEmail([{ sessionId: "cs_lc", product: "lenscrib", created: 5 }], null, null, new Map(), null, null, null, key);
  assert.match(only.text, /Lenscrib for macOS/);
  assert.match(only.text, /\/lenscrib\/success\/\?session_id=cs_lc/);
  assert.ok(only.text.includes(`Lenscrib license key (in Lenscrib, choose Enter License Key and paste it): ${key}`));
  const suite = recoveryEmail([{ sessionId: "cs_su", product: "app-suite", created: 5 }], null, null, new Map(), null, null, null, key);
  assert.doesNotMatch(suite.text, /Lenscrib/);
});
