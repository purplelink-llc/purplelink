// Two Stripe accounts, the remaining readers: Vitae Plus recovery, the billing portal, the follow-up job and
// unsubscribe all look in the new account first and then the old one, and behave as before with the new key unset.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/stripe-account-remaining.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {}, delete: async () => {} }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {};
const setEnv = (over) => {
  for (const k of Object.keys(env)) { delete env[k]; delete process.env[k]; }
  Object.assign(env, over);
  Object.assign(process.env, over); // portal-link.mjs reads process.env
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { keysForEmail } = await import("../functions/vitae-license.mjs");
const { createPortalSession } = await import("../lib/portal-link.mjs");
const { dueOrders } = await import("../functions/post-purchase-followup.mjs");

const OLD = { STRIPE_SECRET_KEY: "sk_test_old", STRIPE_PORTAL_CONFIG_SUBSCRIPTIONS: "bpc_old" };
const NEW = { STRIPE_SECRET_KEY_NEW: "sk_test_new", STRIPE_PORTAL_CONFIG_SUBSCRIPTIONS_NEW: "bpc_new" };
const pem = generateKeyPairSync("ed25519").privateKey.export({ type: "pkcs8", format: "pem" });

/** Run fn with fetch replaced by handler(url, bearerKey) -> body | { status, body }; returns the calls made. */
async function withFetch(handler, fn) {
  const calls = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init = {}) => {
    const key = String(init.headers?.Authorization || "").replace("Bearer ", "");
    calls.push({ url: String(url), key, method: init.method || "GET" });
    const out = handler(String(url), key);
    const { status = 200, body } = out && out.body !== undefined ? out : { body: out };
    return new Response(JSON.stringify(body), { status });
  };
  try { await fn(); } finally { globalThis.fetch = original; }
  return calls;
}

const sub = (id, product) => ({
  id, status: "active", metadata: { product: `vitae-plus-${product}` },
  items: { data: [{ current_period_end: Math.floor(Date.now() / 1000) + 86400 * 20, price: { recurring: { interval: product === "annual" ? "year" : "month" } } }] },
  current_period_end: Math.floor(Date.now() / 1000) + 86400 * 20,
});

test("recovery by email lists each account and merges the keys", async () => {
  setEnv({ ...OLD, ...NEW });
  let result;
  const calls = await withFetch((url, key) => {
    if (url.includes("/customers?")) return { data: [{ id: key === "sk_test_new" ? "cus_new" : "cus_old" }] };
    if (url.includes("/subscriptions?")) return { data: [sub(key === "sk_test_new" ? "sub_new" : "sub_old", "monthly")] };
    return { data: [] };
  }, async () => { result = await keysForEmail("a@example.com", "sk_test_old", pem); });
  assert.equal(result.error, undefined);
  assert.equal(result.keys.length, 2, "one Vitae Plus key from each account");
  assert.ok(calls.some((c) => c.key === "sk_test_new" && c.url.includes("/customers?")));
  assert.ok(calls.some((c) => c.key === "sk_test_old" && c.url.includes("/customers?")));
});

test("recovery with the new key unset reads the old account only", async () => {
  setEnv({ ...OLD });
  const calls = await withFetch(() => ({ data: [] }), async () => { await keysForEmail("a@example.com", "sk_test_old", pem); });
  assert.ok(calls.length > 0);
  assert.ok(calls.every((c) => c.key === "sk_test_old"));
});

test("billing portal: the new account is tried first with its own configuration, then the old", async () => {
  setEnv({ ...OLD, ...NEW });
  let url = null;
  const calls = await withFetch((u, key) => {
    if (!u.endsWith("/billing_portal/sessions")) return { status: 404, body: {} };
    return key === "sk_test_old" ? { url: "https://billing.stripe.com/p/session/abc" } : { status: 400, body: { error: { message: "No such customer" } } };
  }, async () => { url = await createPortalSession("cus_old", "https://purplelink.llc/", "sk_test_old"); });
  assert.equal(url, "https://billing.stripe.com/p/session/abc");
  assert.deepEqual(calls.map((c) => c.key), ["sk_test_new", "sk_test_old"]);
});

test("billing portal with the new key unset makes one call with the old key", async () => {
  setEnv({ ...OLD });
  let url = null;
  const calls = await withFetch(() => ({ url: "https://billing.stripe.com/p/session/xyz" }), async () => {
    url = await createPortalSession("cus_old", "https://purplelink.llc/", "sk_test_old");
  });
  assert.equal(url, "https://billing.stripe.com/p/session/xyz");
  assert.equal(calls.length, 1);
});

test("follow-up job reads orders from both accounts", async () => {
  setEnv({ ...OLD, ...NEW });
  const order = (id) => ({ id, payment_status: "paid", metadata: { product: "moderntex-seats" }, customer_details: { email: `${id}@example.com` } });
  let out;
  await withFetch((url, key) => ({ data: [order(key === "sk_test_new" ? "cs_new" : "cs_old")], has_more: false }), async () => {
    out = await dueOrders(Math.floor(Date.now() / 1000), "sk_test_old");
  });
  assert.deepEqual(out.orders.map((o) => o.id).sort(), ["cs_new", "cs_old"]);
});
