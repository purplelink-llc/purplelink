// Selling Née: the checkout catalog, the purchase email (link, NEE1 key, practical note), the key a session is
// entitled to (the Suite and bundles that name it), the Suite and bundle emails, and the
// recovery email. Stripe, Resend and Blobs are stubbed; signing keys are throwaway. The production keys are never read.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/nee-purchase.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac, generateKeyPairSync } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
    list: async () => ({ blobs: [] }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

// A throwaway Ed25519 pair stands in for the production PurplelinkLicenseV1 key.
const { privateKey } = generateKeyPairSync("ed25519");
const jwk = privateKey.export({ format: "jwk" });
const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");
const SEED = b64(jwk.d), PUBLIC = b64(jwk.x);

const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", RESEND_API_KEY: "re_dummy",
  PURPLELINK_LICENSE_PRIVATE_KEY: SEED, PURPLELINK_LICENSE_PUBLIC_KEY: PUBLIC,
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook, BLOB_DELIVERED_PRODUCTS, licenseKeysForSession } = await import("../functions/stripe-webhook.mjs");
const { recoveryEmail } = await import("../functions/purchases-recover.mjs");
const { verifyLicense, LICENSED_PRODUCTS } = await import("../lib/license.mjs");
const { FOLLOWUP_PRODUCTS } = await import("../lib/followup.mjs");
const { MP_TAX_CODES } = await import("../lib/managed-payments.mjs");

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

test("checkout sells Née at $14.99 from the catalog, with its own success page and refund line", async () => {
  const res = await post({ product: "nee", amount: 1 });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "1499", "the price comes from the catalog, not the request");
  assert.equal(p.get("line_items[0][price_data][product_data][name]"), "Née for macOS");
  assert.match(p.get("success_url"), /\/nee\/success\/\?session_id=/);
  assert.equal(p.get("metadata[product]"), "nee");
  assert.match(p.get("custom_text[submit][message]") || "", /full \$14\.99/);
});

test("Née is a custom bundle part, and the Suite line names it", async () => {
  const ok = await post({ product: "bundle-2", apps: ["nee", "panely"] });
  assert.equal(ok.status, 200);
  assert.equal(stripeParams().get("metadata[apps]"), "panely,nee");
  calls.length = 0;
  await post({ product: "app-suite" });
  assert.match(stripeParams().get("line_items[0][price_data][product_data][name]"), /Summonly, Née and Vitae Plus for life/);
});

test("Née has a tax code and a follow-up name like the other apps", () => {
  assert.equal(MP_TAX_CODES.nee, "txcd_10202000");
  assert.equal(FOLLOWUP_PRODUCTS.nee, "Née");
});

// ---- keys ----

test("a Née session is entitled to one NEE1 key that verifies for Née", () => {
  const keys = licenseKeysForSession("nee", "cs_live_nee_abcdefghij");
  assert.deepEqual(keys.map((k) => k.slug), ["nee"]);
  assert.equal(keys[0].label, "Née");
  assert.match(keys[0].key, /^NEE1-/);
  assert.equal(verifyLicense("nee", keys[0].key, { publicB64: PUBLIC }), true);
  assert.equal(keys[0].key, licenseKeysForSession("nee", "cs_live_nee_abcdefghij")[0].key, "derived from the session, so every caller gets the same key");
});

test("a Mac Suite session gets an Née key with the other keyed apps; a custom bundle gets one only if it names Née", () => {
  const slugs = licenseKeysForSession("app-suite", "cs_live_su_abcdefghij").map((k) => k.slug);
  assert.ok(slugs.includes("outbound-veil") && slugs.includes("legroom") && slugs.includes("nee"));
  assert.ok(!licenseKeysForSession("bundle-2", "cs_live_b2_abcdefghij", { apps: "legroom,panely" }).some((k) => k.slug === "nee"));
  const withAka = licenseKeysForSession("bundle-2", "cs_live_b2_abcdefghij", { apps: "legroom,nee" });
  assert.deepEqual(withAka.map((k) => k.slug).sort(), ["legroom", "nee"]);
  const key = withAka.find((k) => k.slug === "nee").key;
  assert.equal(verifyLicense("nee", key, { publicB64: PUBLIC }), true);
});

// ---- delivery ----

test("Née is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("nee").successPath, "/nee/success/");
});

test("a paid Née order emails the page link, its NEE1 key and one practical note", async () => {
  const res = await webhook(signed(paid({ product: "nee" }, 1499, "evt_nee", "cs_live_nee_abcdefghij")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = mailOf();
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/nee\/success\/\?session_id=cs_live_nee_abcdefghij/);
  assert.match(mail.text, /Née: NEE1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}/);
  assert.match(mail.text, /Paste a key into the matching app \(Née: "Enter license key"\)/);
  assert.match(mail.text, /macOS 14 or later/);
  assert.match(mail.text, /hold Option/);
  assert.match(mail.text, /next to the original/);
  assert.match(mail.text, /Your files are not uploaded/);
  assert.doesNotMatch(mail.text + mail.html, /LG1|OV1|LCB1/);
  assert.doesNotMatch(mail.text + mail.html, /[—;]\s*$/m);
});

test("a paid Suite order carries the Née key and the practical note, and a bundle without Née carries neither", async () => {
  await webhook(signed(paid({ product: "app-suite" }, 5999, "evt_su", "cs_live_su_abcdefghij")));
  const mail = mailOf();
  assert.match(mail.text, /Née: NEE1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}/);
  assert.match(mail.text, /Née downloads/);
  assert.match(mail.text, /hold Option/);
  calls.length = 0;
  await webhook(signed(paid({ product: "bundle-2", apps: "legroom,panely" }, 3499, "evt_b2", "cs_live_b2_abcdefghij")));
  const other = mailOf();
  assert.doesNotMatch(other.text + other.html, /Née|NEE1-/);
});

// ---- recovery ----

test("the recovery email lists a Née purchase with its page and key, and a Suite purchase with the key and the Née download", () => {
  const key = "NEE1-AAAAA-BBBBB";
  const only = recoveryEmail([{ sessionId: "cs_fr", product: "nee", created: 5 }], null, null, new Map([["cs_fr", [{ slug: "nee", label: "Née", key }]]]));
  assert.match(only.text, /Née for macOS/);
  assert.match(only.text, /\/nee\/success\/\?session_id=cs_fr/);
  assert.ok(only.text.includes(`Née: ${key}`));
  const suite = recoveryEmail([{ sessionId: "cs_su", product: "app-suite", created: 5 }], null, null,
    new Map([["cs_su", licenseKeysForSession("app-suite", "cs_su")]]));
  assert.match(suite.text, /Née: NEE1-/);
  assert.match(suite.text, /Summonly and Née downloads/);
});
