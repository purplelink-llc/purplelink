// Gaps left by moderntex-seats.test.mjs and post-purchase-followup.test.mjs: the seats product is registered
// for delivery, find-my-purchases returns every seat key for a seat order, and the day-14 follow-up goes to seat
// buyers but never to single ModernTex copies. Stripe, Resend and Blobs are stubbed; the signing key is a throwaway.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/roadmap-extra.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { privateKey } = generateKeyPairSync("ed25519");
const jwk = privateKey.export({ format: "jwk" });
const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_unit", RESEND_API_KEY: "re_dummy",
  MODERNTEX_LICENSE_PRIVATE_KEY: Buffer.from(jwk.d, "base64url").toString("base64"),
  POST_PURCHASE_FOLLOWUP: "on",
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { BLOB_DELIVERED_PRODUCTS, licenseKeysForSession } = await import("../functions/stripe-webhook.mjs");
const { default: recoverHandler } = await import("../functions/purchases-recover.mjs");
const { runFollowups } = await import("../functions/post-purchase-followup.mjs");
const lib = await import("../lib/followup.mjs");

const NOW = 1_800_000_000;
let sessions, mails;
beforeEach(() => {
  store.clear();
  sessions = [];
  mails = [];
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    if (u.startsWith("https://api.resend.com/")) { mails.push(JSON.parse(opts.body)); return new Response("{}", { status: 200 }); }
    if (u.startsWith("https://api.stripe.com/v1/checkout/sessions")) return new Response(JSON.stringify({ data: sessions, has_more: false }), { status: 200 });
    return new Response("{}", { status: 404 });
  };
});

test("the seats product is delivered from the ModernTex success page", () => {
  const entry = BLOB_DELIVERED_PRODUCTS.get("moderntex-seats");
  assert.ok(entry, "moderntex-seats is listed in BLOB_DELIVERED_PRODUCTS");
  assert.equal(entry.successPath, "/moderntex/success/");
  assert.ok(BLOB_DELIVERED_PRODUCTS.get("moderntex"));
});

test("find-my-purchases emails every seat key for a seat order", async () => {
  sessions = [{ id: "cs_live_recover_seats_01", payment_status: "paid", created: 9, metadata: { product: "moderntex-seats", seats: "7" } }];
  const res = await recoverHandler(new Request("https://purplelink.llc/.netlify/functions/purchases-recover", {
    method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": "203.0.113.77" },
    body: JSON.stringify({ email: "lab@example.edu" }),
  }));
  assert.equal(res.status, 200);
  assert.equal(mails.length, 1);
  const keys = mails[0].text.match(/MTX1-(?:[0-9A-Z]{5}-){21}[0-9A-Z]{4}/g) ?? [];
  const expected = licenseKeysForSession("moderntex-seats", "cs_live_recover_seats_01", { seats: 7 }).map((k) => k.key);
  assert.equal(expected.length, 7);
  assert.deepEqual(keys, expected);
  assert.match(mails[0].text, /moderntex\/success\/\?session_id=cs_live_recover_seats_01/);
});

test("the day-14 follow-up goes to a seat buyer and never to a single ModernTex copy", async () => {
  const order = (id, product, email, seats) => ({
    id, payment_status: "paid", metadata: { product, ...(seats ? { seats: String(seats) } : {}) },
    customer_details: { email }, payment_intent: null,
  });
  sessions = [order("cs_single", "moderntex", "single@x.edu"), order("cs_seats", "moderntex-seats", "lab@x.edu", 12)];
  const r = await runFollowups({ nowS: NOW });
  assert.equal(r.sent, 1);
  assert.deepEqual(mails.map((m) => m.to[0]), ["lab@x.edu"]);
  assert.match(mails[0].text, /12 copies for your lab or department/);
  assert.equal(lib.followupEmail({ to: "single@x.edu", product: "moderntex", secret: "s" }), null);
  assert.ok(!Object.hasOwn(lib.FOLLOWUP_PRODUCTS, "moderntex"));
});
