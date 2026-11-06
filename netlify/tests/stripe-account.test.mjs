// Two Stripe accounts (netlify/lib/stripe-account.mjs): with the new env vars unset nothing changes; with them set,
// new Checkout Sessions use the new key and `_NEW` Price ids, lookups fall through to the old account, and the
// webhook accepts either account's signing secret.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/stripe-account.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {} }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {};
const setEnv = (over) => { for (const k of Object.keys(env)) delete env[k]; Object.assign(env, over); };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const acct = await import("../lib/stripe-account.mjs");
const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook } = await import("../functions/stripe-webhook.mjs");

const OLD = { STRIPE_SECRET_KEY: "sk_test_old", STRIPE_WEBHOOK_SECRET: "whsec_old", BACKEND_WEBHOOK_SECRET: "backend", STRIPE_PRICE_LEGROOM: "price_old_legroom" };
const NEW = { STRIPE_SECRET_KEY_NEW: "sk_test_new", STRIPE_WEBHOOK_SECRET_NEW: "whsec_new", STRIPE_PRICE_LEGROOM_NEW: "price_new_legroom" };

test("new env vars unset: the old key, the old Price env names and one lookup key", () => {
  setEnv({ ...OLD, STRIPE_NEW_ACCOUNT: "on" }); // flag alone, with no new key, changes nothing
  assert.equal(acct.newAccountActive(), false);
  assert.equal(acct.checkoutSecretKey(), "sk_test_old");
  assert.equal(acct.priceEnvName("STRIPE_PRICE_LEGROOM"), "STRIPE_PRICE_LEGROOM");
  assert.deepEqual(acct.lookupKeys(), ["sk_test_old"]);
  assert.deepEqual(acct.webhookSecrets().map((s) => s.account), ["legacy"]);
});

test("new key set but flag off: sessions stay on the old account, lookups cover both", () => {
  setEnv({ ...OLD, ...NEW });
  assert.equal(acct.newAccountActive(), false);
  assert.equal(acct.checkoutSecretKey(), "sk_test_old");
  assert.deepEqual(acct.lookupKeys(), ["sk_test_new", "sk_test_old"]);
});

test("flag on with the new key: new key and _NEW Price names", () => {
  setEnv({ ...OLD, ...NEW, STRIPE_NEW_ACCOUNT: "on" });
  assert.equal(acct.newAccountActive(), true);
  assert.equal(acct.checkoutSecretKey(), "sk_test_new");
  assert.equal(acct.priceEnvName("STRIPE_PRICE_LEGROOM"), "STRIPE_PRICE_LEGROOM_NEW");
});

test("stripeFetchAny falls through a 404 to the old account and returns the first ok answer", async () => {
  setEnv({ ...OLD, ...NEW });
  const seen = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    seen.push(init.headers.Authorization);
    return init.headers.Authorization === "Bearer sk_test_old"
      ? new Response(JSON.stringify({ id: "cs_old" }), { status: 200 })
      : new Response(JSON.stringify({ error: { code: "resource_missing" } }), { status: 404 });
  };
  try {
    const resp = await acct.stripeFetchAny("https://api.stripe.com/v1/checkout/sessions/cs_old", { headers: { Authorization: "Bearer ignored" } });
    assert.equal(resp.status, 200);
    assert.deepEqual(seen, ["Bearer sk_test_new", "Bearer sk_test_old"]);
  } finally { globalThis.fetch = original; }
});

test("stripeFetchAny with only the old key makes one call with it", async () => {
  setEnv({ ...OLD });
  const seen = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => { seen.push(init.headers.Authorization); return new Response("{}", { status: 404 }); };
  try {
    const resp = await acct.stripeFetchAny("https://api.stripe.com/v1/checkout/sessions/cs_x", {});
    assert.equal(resp.status, 404);
    assert.deepEqual(seen, ["Bearer sk_test_old"]);
  } finally { globalThis.fetch = original; }
});

async function startCheckout() {
  let used = null;
  let priceId = null;
  const original = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (new URL(String(url)).hostname === "api.stripe.com") {
      used = opts.headers.Authorization;
      priceId = new URLSearchParams(opts.body).get("line_items[0][price]");
      return new Response(JSON.stringify({ id: "cs_test_x", url: "https://checkout.stripe.com/pay/cs_test_x" }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const resp = await checkout(new Request("https://purplelink.llc/api/checkout", {
      method: "POST", headers: { "content-type": "application/json", "x-nf-client-connection-ip": `10.9.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}` },
      body: JSON.stringify({ product: "legroom" }),
    }), {});
    return { status: resp.status, used, priceId };
  } finally { globalThis.fetch = original; }
}

test("checkout today: old key and old Price id", async () => {
  setEnv({ ...OLD });
  const r = await startCheckout();
  assert.equal(r.status, 200);
  assert.equal(r.used, "Bearer sk_test_old");
  assert.equal(r.priceId, "price_old_legroom");
});

test("checkout with the new account on: new key and the _NEW Price id", async () => {
  setEnv({ ...OLD, ...NEW, STRIPE_NEW_ACCOUNT: "on" });
  const r = await startCheckout();
  assert.equal(r.status, 200);
  assert.equal(r.used, "Bearer sk_test_new");
  assert.equal(r.priceId, "price_new_legroom");
});

test("checkout with the new account on but no _NEW Price id is misconfigured, never the old Price", async () => {
  setEnv({ ...OLD, STRIPE_SECRET_KEY_NEW: "sk_test_new", STRIPE_NEW_ACCOUNT: "on" });
  const r = await startCheckout();
  assert.equal(r.status, 500);
  assert.equal(r.used, null);
});

function signedBy(secret, body = JSON.stringify({ id: "evt_ping", type: "ping", data: { object: {} } })) {
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", secret).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", { method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body });
}

test("webhook: the old secret is accepted, the new one is rejected until it is set", async () => {
  setEnv({ ...OLD });
  assert.equal((await webhook(signedBy("whsec_old"), {})).status, 200);
  assert.equal((await webhook(signedBy("whsec_new"), {})).status, 400);
});

test("webhook: with the new secret set, either account's signature passes and others fail", async () => {
  setEnv({ ...OLD, ...NEW });
  assert.equal((await webhook(signedBy("whsec_old"), {})).status, 200);
  assert.equal((await webhook(signedBy("whsec_new"), {})).status, 200);
  assert.equal((await webhook(signedBy("whsec_other"), {})).status, 400);
});

test("currentSecretKey follows the account that signed the event, per request", async () => {
  setEnv({ ...OLD, ...NEW });
  assert.equal(acct.currentSecretKey(), "sk_test_old");
  await acct.runWithAccount(async () => {
    acct.setRequestAccount("new");
    assert.equal(acct.currentSecretKey(), "sk_test_new");
  });
  await acct.runWithAccount(async () => assert.equal(acct.currentSecretKey(), "sk_test_old"));
});
