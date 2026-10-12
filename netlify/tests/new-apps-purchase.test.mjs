// Selling Panely and Summonly: the checkout catalog, the purchase email (link, key, first-run note), the Suite and
// custom-bundle emails, the recovery email, and the entitlement of each download. Stripe, Resend and Blobs are stubbed; signing
// keys are throwaway. The production keys are never read.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/new-apps-purchase.test.mjs

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
  PANELY_LICENSE_PRIVATE_KEY: Buffer.alloc(32, 7).toString("base64"),
  SUMMONLY_LICENSE_PRIVATE_KEY: Buffer.alloc(32, 8).toString("base64"),
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook, BLOB_DELIVERED_PRODUCTS } = await import("../functions/stripe-webhook.mjs");
const { recoveryEmail } = await import("../functions/purchases-recover.mjs");
const { default: panelyDl } = await import("../functions/panely-download.mjs");
const { default: summonlyDl } = await import("../functions/summonly-download.mjs");

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

test("checkout sells Panely and Summonly at $9.99 each, with their own success pages", async () => {
  for (const [slug, name] of [["panely", "Panely"], ["summonly", "Summonly"]]) {
    calls = [];
    const res = await post({ product: slug, amount: 1 });
    assert.equal(res.status, 200, slug);
    const p = stripeParams();
    assert.equal(p.get("line_items[0][price_data][unit_amount]"), "999", "the price comes from the catalog, not the request");
    assert.equal(p.get("line_items[0][price_data][product_data][name]"), `${name} for macOS`);
    assert.match(p.get("success_url"), new RegExp(`/${slug}/success/\\?session_id=`));
    assert.equal(p.get("metadata[product]"), slug);
  }
});

test("the Suite line names all seven apps and stays $59.99", async () => {
  await post({ product: "app-suite" });
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "5999");
  assert.match(p.get("line_items[0][price_data][product_data][name]"), /Tapefolio, Panely, Summonly and Vitae Plus for life/);
});

test("a custom bundle can hold the two new apps, priced by count", async () => {
  await post({ product: "bundle-2", apps: ["summonly", "panely"] });
  const p = stripeParams();
  assert.equal(p.get("metadata[apps]"), "panely,summonly");
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "3499");
});

// ---- delivery ----

test("both apps are blob-delivered products with their own success pages", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("panely").successPath, "/panely/success/");
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("summonly").successPath, "/summonly/success/");
});

test("a paid Panely order emails the page link, its key and the Accessibility note, and nothing about Summonly", async () => {
  const res = await webhook(signed(paid({ product: "panely" }, 999, "evt_pf", "cs_live_pf_abcdefghij")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = mailOf();
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/panely\/success\/\?session_id=cs_live_pf_abcdefghij/);
  assert.match(mail.text, /Your Panely license key[^\n]*\nPNL1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}\n/);
  assert.match(mail.text, /on up to two of your Macs/);
  assert.match(mail.text, /Accessibility permission/);
  assert.match(mail.text, /never what is inside a window/);
  assert.doesNotMatch(mail.text, /Summonly|SML1/);
  assert.doesNotMatch(mail.text + mail.html, /[—;]\s*$/m);
});

test("a paid Summonly order emails the page link, its key and the folder-permission note, and nothing about Panely", async () => {
  await webhook(signed(paid({ product: "summonly" }, 999, "evt_lf", "cs_live_lf_abcdefghij")));
  const mail = mailOf();
  assert.match(mail.text, /https:\/\/purplelink\.llc\/summonly\/success\/\?session_id=cs_live_lf_abcdefghij/);
  assert.match(mail.text, /Your Summonly license key[^\n]*\nSML1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}\n/);
  assert.match(mail.text, /Desktop, Documents and Downloads/);
  assert.match(mail.text, /clipboard history skips password managers/);
  assert.doesNotMatch(mail.text, /Panely|PNL1/);
});

test("the Suite email carries both new keys, and a bundle carries only the chosen ones", async () => {
  await webhook(signed(paid({ product: "app-suite" }, 5999, "evt_suite", "cs_live_suite_abcdefghij")));
  let mail = mailOf();
  assert.match(mail.text, /PNL1-/); assert.match(mail.text, /SML1-/);
  calls = [];
  await webhook(signed(paid({ product: "bundle-2", apps: "panely,keyfeel" }, 3499, "evt_b", "cs_live_bundle_abcdefg")));
  mail = mailOf();
  assert.match(mail.text, /PNL1-/); assert.doesNotMatch(mail.text, /SML1-/);
});

test("the keys are the same for one address wherever they are asked for: receipt email and recovery email", async () => {
  await webhook(signed(paid({ product: "panely" }, 999, "evt_same", "cs_live_same_abcdefghij")));
  const fromReceipt = mailOf().text.match(/PNL1-[0-9A-Z-]+/)[0];
  const rec = recoveryEmail([{ product: "panely", sessionId: "cs_live_same_abcdefghij" }], null, null, new Map(), null, fromReceipt, null);
  assert.ok(rec.text.includes(fromReceipt));
  assert.match(rec.text, /Panely license key \(in Panely, choose Enter License Key and paste it\)/);
});

// ---- entitlement ----

test("a Panely purchase unlocks the Panely download and not Summonly's, and the Suite unlocks both", async () => {
  const get = (h, name, sid) => h(new Request(`https://purplelink.llc/.netlify/functions/${name}?session_id=${sid}`));
  session = { id: "cs_live_pf_abcdefghij", status: "complete", payment_status: "paid", customer_details: { email: "buyer@example.com" }, metadata: { product: "panely" } };
  assert.notEqual((await get(panelyDl, "panely-download", session.id)).status, 403);
  assert.equal((await get(summonlyDl, "summonly-download", session.id)).status, 403);
  session = { ...session, id: "cs_live_suite_abcdefghij", metadata: { product: "app-suite" } };
  assert.notEqual((await get(panelyDl, "panely-download", session.id)).status, 403);
  assert.notEqual((await get(summonlyDl, "summonly-download", session.id)).status, 403);
  session = { ...session, id: "cs_live_bundle_abcdefg", metadata: { product: "bundle-2", apps: "summonly,keyfeel" } };
  assert.equal((await get(panelyDl, "panely-download", session.id)).status, 403, "a bundle without Panely does not unlock it");
  assert.notEqual((await get(summonlyDl, "summonly-download", session.id)).status, 403);
});
