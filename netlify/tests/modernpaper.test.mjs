// ModernPaper: PurplelinkLicenseV1 key (prefix MP1, slug "modernpaper"), checkout at $49, and the
// Suite and bundle membership (public since 2026-11-27, $49).
// Run with: node --experimental-test-module-mocks --test netlify/tests/modernpaper.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {}, list: async () => ({ blobs: [] }) }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_SECRET_KEY: "sk_test_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { issueLicense, verifyLicense, licensedSlugsFor, suiteIncludes, LICENSED_PRODUCTS } = await import("../lib/license.mjs");
const { BUNDLE_SLUGS, entitledParts } = await import("../lib/bundles.mjs");
const { default: checkout } = await import("../functions/checkout.mjs");
const { BLOB_DELIVERED_PRODUCTS, licenseKeysForSession } = await import("../functions/stripe-webhook.mjs");

function testPair() {
  const { privateKey } = generateKeyPairSync("ed25519");
  const j = privateKey.export({ format: "jwk" });
  const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");
  return { seedB64: b64(j.d), publicB64: b64(j.x) };
}
const pair = testPair();

test("ModernPaper is on the shared scheme with prefix MP1 and its own page", () => {
  assert.equal(LICENSED_PRODUCTS.modernpaper.prefix, "MP1");
  assert.equal(LICENSED_PRODUCTS.modernpaper.label, "ModernPaper");
  assert.equal(LICENSED_PRODUCTS.modernpaper.appPath, "/modernpaper/");
});

test("a ModernPaper key has the MP1 shape, round-trips, and unlocks no other product", () => {
  const key = issueLicense("modernpaper", { sessionId: "cs_test_mp", ...pair });
  assert.match(key, /^MP1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/);
  assert.equal(verifyLicense("modernpaper", key, { publicB64: pair.publicB64 }), true);
  assert.equal(key, issueLicense("modernpaper", { sessionId: "cs_test_mp", ...pair }));
  for (const other of ["nee", "legroom", "outbound-veil", "lenses"]) {
    assert.equal(verifyLicense(other, key, { publicB64: pair.publicB64 }), false, `not ${other}`);
    assert.equal(verifyLicense("modernpaper", issueLicense(other, { sessionId: "cs_test_mp", ...pair }), { publicB64: pair.publicB64 }), false, other);
  }
});

test("Suite gate: ModernPaper is in the Suite and the bundles, with its own MP1 key", () => {
  assert.equal(suiteIncludes("modernpaper"), true);
  assert.deepEqual(licensedSlugsFor("modernpaper"), ["modernpaper"]);
  assert.ok(licensedSlugsFor("app-suite").includes("modernpaper"), "a Suite buyer gets an MP1 key");
  assert.ok(BUNDLE_SLUGS.includes("modernpaper"));
  assert.ok(entitledParts("app-suite").has("modernpaper"));
  assert.equal(LICENSED_PRODUCTS.modernpaper.inSuite, undefined);
});

test("a paid ModernPaper session is handed exactly one MP1 key; a Suite session is handed one too", () => {
  const prev = env.PURPLELINK_LICENSE_PRIVATE_KEY;
  env.PURPLELINK_LICENSE_PRIVATE_KEY = pair.seedB64;
  try {
    const keys = licenseKeysForSession("modernpaper", "cs_test_mp");
    assert.deepEqual(keys.map((k) => k.slug), ["modernpaper"]);
    assert.match(keys[0].key, /^MP1-/);
    const suiteKey = licenseKeysForSession("app-suite", "cs_test_mp").find((k) => k.slug === "modernpaper");
    assert.match(suiteKey.key, /^MP1-/);
    assert.equal(suiteKey.key, keys[0].key, "same key whether bought alone or in the Suite");
  } finally { env.PURPLELINK_LICENSE_PRIVATE_KEY = prev; }
});

test("the webhook knows ModernPaper and points its success page at /modernpaper/success/", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("modernpaper").successPath, "/modernpaper/success/");
});

let calls;
beforeEach(() => {
  calls = [];
  delete env.STRIPE_PRICE_MODERNPAPER;
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (String(url).includes("/checkout/sessions") && opts.method === "POST") {
      return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  };
});
let ipN = 0;
const post = (body) => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": `203.0.113.${10 + (ipN++ % 200)}` }, body: JSON.stringify(body),
}));

test("checkout with STRIPE_PRICE_MODERNPAPER unset charges the inline $49", async () => {
  const r = await post({ product: "modernpaper" });
  assert.equal(r.status, 200);
  const c = calls.find((x) => x.url.includes("/checkout/sessions") && x.opts.method === "POST");
  const p = new URLSearchParams(c.opts.body);
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "4900");
  assert.equal(p.get("metadata[product]"), "modernpaper");
  assert.match(p.get("success_url"), /\/modernpaper\/success\/\?session_id=/);
});

test("checkout with the env Price set uses that Price and the success page", async () => {
  env.STRIPE_PRICE_MODERNPAPER = "price_mp_test";
  const r = await post({ product: "modernpaper" });
  assert.equal(r.status, 200);
  const c = calls.find((x) => x.url.includes("/checkout/sessions") && x.opts.method === "POST");
  const p = new URLSearchParams(c.opts.body);
  assert.equal(p.get("line_items[0][price]"), "price_mp_test");
  assert.equal(p.get("metadata[product]"), "modernpaper");
  assert.match(p.get("success_url"), /\/modernpaper\/success\/\?session_id=/);
});

test("the unset case leaves other products alone", async () => {
  env.STRIPE_PRICE_OUTBOUND_VEIL = "price_ov";
  const r = await post({ product: "outbound-veil" });
  assert.equal(r.status, 200);
  delete env.STRIPE_PRICE_OUTBOUND_VEIL;
});
