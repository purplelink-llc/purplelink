// Selling AKA: the checkout catalog, the purchase email (link, AKA1 key, practical note), the key a session is
// entitled to (including the Suite launch gate), the Suite and bundle emails (which must not carry it yet), and the
// recovery email. Stripe, Resend and Blobs are stubbed; signing keys are throwaway. The production keys are never read.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/aka-purchase.test.mjs

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

test("checkout sells AKA at $14.99 from the catalog, with its own success page and refund line", async () => {
  const res = await post({ product: "aka", amount: 1 });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "1499", "the price comes from the catalog, not the request");
  assert.equal(p.get("line_items[0][price_data][product_data][name]"), "AKA for macOS");
  assert.match(p.get("success_url"), /\/aka\/success\/\?session_id=/);
  assert.equal(p.get("metadata[product]"), "aka");
  assert.match(p.get("custom_text[submit][message]") || "", /full \$14\.99/);
});

test("AKA is not a custom bundle part, and the Suite line does not name it", async () => {
  const bad = await post({ product: "bundle-2", apps: ["aka", "panely"] });
  assert.equal(bad.status, 400);
  await post({ product: "app-suite" });
  assert.doesNotMatch(stripeParams().get("line_items[0][price_data][product_data][name]"), /AKA/);
});

test("AKA has a tax code and a follow-up name like the other apps", () => {
  assert.equal(MP_TAX_CODES.aka, "txcd_10202000");
  assert.equal(FOLLOWUP_PRODUCTS.aka, "AKA");
});

// ---- keys ----

test("a AKA session is entitled to one AKA1 key that verifies for AKA", () => {
  const keys = licenseKeysForSession("aka", "cs_live_aka_abcdefghij");
  assert.deepEqual(keys.map((k) => k.slug), ["aka"]);
  assert.equal(keys[0].label, "AKA");
  assert.match(keys[0].key, /^AKA1-/);
  assert.equal(verifyLicense("aka", keys[0].key, { publicB64: PUBLIC }), true);
  assert.equal(keys[0].key, licenseKeysForSession("aka", "cs_live_aka_abcdefghij")[0].key, "derived from the session, so every caller gets the same key");
});

test("LAUNCH GATE: a Mac Suite session gets keys for Outbound Veil and Legroom but no AKA key", () => {
  const slugs = licenseKeysForSession("app-suite", "cs_live_su_abcdefghij").map((k) => k.slug);
  assert.ok(slugs.includes("outbound-veil") && slugs.includes("legroom"));
  assert.ok(!slugs.includes("aka"));
});

test("once the Suite gate is flipped, a Suite session gets a AKA key too; a custom bundle still never does", () => {
  LICENSED_PRODUCTS.aka.inSuite = true;
  try {
    assert.ok(licenseKeysForSession("app-suite", "cs_live_su_abcdefghij").some((k) => k.slug === "aka"));
    assert.ok(!licenseKeysForSession("bundle-2", "cs_live_b2_abcdefghij", { apps: "legroom,panely" }).some((k) => k.slug === "aka"));
  } finally {
    LICENSED_PRODUCTS.aka.inSuite = false;
  }
});

// ---- delivery ----

test("AKA is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("aka").successPath, "/aka/success/");
});

test("a paid AKA order emails the page link, its AKA1 key and one practical note", async () => {
  const res = await webhook(signed(paid({ product: "aka" }, 1499, "evt_aka", "cs_live_aka_abcdefghij")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = mailOf();
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/aka\/success\/\?session_id=cs_live_aka_abcdefghij/);
  assert.match(mail.text, /AKA: AKA1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}/);
  assert.match(mail.text, /Paste a key into the matching app \(AKA: "Enter license key"\)/);
  assert.match(mail.text, /macOS 14 or later/);
  assert.match(mail.text, /hold Option/);
  assert.match(mail.text, /next to the original/);
  assert.match(mail.text, /Your files are not uploaded/);
  assert.doesNotMatch(mail.text + mail.html, /LG1|OV1|LCB1/);
  assert.doesNotMatch(mail.text + mail.html, /[—;]\s*$/m);
});

test("a paid Suite order carries no AKA key or text while the gate is closed", async () => {
  await webhook(signed(paid({ product: "app-suite" }, 5999, "evt_su", "cs_live_su_abcdefghij")));
  const mail = mailOf();
  assert.doesNotMatch(mail.text + mail.html, /AKA|AKA1-/);
});

// ---- recovery ----

test("the recovery email lists a AKA purchase with its page and key, and a Suite purchase without one", () => {
  const key = "AKA1-AAAAA-BBBBB";
  const only = recoveryEmail([{ sessionId: "cs_fr", product: "aka", created: 5 }], null, null, new Map([["cs_fr", [{ slug: "aka", label: "AKA", key }]]]));
  assert.match(only.text, /AKA for macOS/);
  assert.match(only.text, /\/aka\/success\/\?session_id=cs_fr/);
  assert.ok(only.text.includes(`AKA: ${key}`));
  const suite = recoveryEmail([{ sessionId: "cs_su", product: "app-suite", created: 5 }], null, null,
    new Map([["cs_su", licenseKeysForSession("app-suite", "cs_su")]]));
  assert.doesNotMatch(suite.text, /AKA|AKA1-/);
});
