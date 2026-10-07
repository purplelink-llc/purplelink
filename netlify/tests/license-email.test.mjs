// Purchase emails carry the license keys: Outbound Veil, Legroom and Keyfeel get their own PurplelinkLicenseV1
// key, the Suite gets one per app, and the same purchase always yields the same key. Stripe, Resend and Blobs
// are stubbed; the signing keypair is a throwaway test pair (never the production key).
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/license-email.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac, generateKeyPairSync } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { privateKey } = generateKeyPairSync("ed25519");
const jwk = privateKey.export({ format: "jwk" });
const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");
const TEST_SEED = b64(jwk.d), TEST_PUBLIC = b64(jwk.x);

const env = { STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", RESEND_API_KEY: "re_dummy",
  PURPLELINK_LICENSE_PRIVATE_KEY: TEST_SEED, PURPLELINK_LICENSE_PUBLIC_KEY: TEST_PUBLIC };
globalThis.Netlify = { env: { get: (k) => env[k] } };
const { default: handler, licenseKeysForSession } = await import("../functions/stripe-webhook.mjs");
const { verifyLicense } = await import("../lib/license.mjs");

let calls;
beforeEach(() => {
  store.clear();
  calls = [];
  env.PURPLELINK_LICENSE_PRIVATE_KEY = TEST_SEED;
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
const completed = (product, sessionId, eventId) => ({
  id: eventId, type: "checkout.session.completed",
  data: { object: { id: sessionId, status: "complete", payment_status: "paid", amount_total: 900,
    customer_details: { email: "buyer@example.com" }, metadata: { product } } },
});
const sentMail = () => JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);
const keyIn = (text, prefix) => text.match(new RegExp(`${prefix}-(?:[0-9A-Z]{5}-){21}[0-9A-Z]{4}`))?.[0];

test("an Outbound Veil purchase emails an OV1 key that verifies for Outbound Veil only", async () => {
  await handler(signed(completed("outbound-veil", "cs_live_ov_0123456789", "evt_ov")));
  const mail = sentMail();
  const key = keyIn(mail.text, "OV1");
  assert.ok(key, "the email carries an OV1 key");
  assert.equal(verifyLicense("outbound-veil", key, { publicB64: TEST_PUBLIC }), true);
  assert.equal(verifyLicense("legroom", key, { publicB64: TEST_PUBLIC }), false);
  assert.match(mail.text, /free for 7 days, then asks for its key/);
  assert.match(mail.html, /OV1-/);
  assert.doesNotMatch(mail.text, /—|–/);
});

test("a Legroom purchase emails its own key", async () => {
  for (const [product, prefix, slug] of [["legroom", "LG1", "legroom"]]) {
    calls.length = 0;
    await handler(signed(completed(product, `cs_live_${product}_0123456789`, `evt_${product}`)));
    const key = keyIn(sentMail().text, prefix);
    assert.ok(key, `${product} email carries a ${prefix} key`);
    assert.equal(verifyLicense(slug, key, { publicB64: TEST_PUBLIC }), true);
  }
});

test("the same purchase always yields the same key, whichever event delivers it", async () => {
  await handler(signed(completed("legroom", "cs_live_same_0123456789", "evt_a")));
  const first = keyIn(sentMail().text, "LG1");
  calls.length = 0;
  await handler(signed(completed("legroom", "cs_live_same_0123456789", "evt_b")));
  assert.equal(keyIn(sentMail().text, "LG1"), first);
  assert.deepEqual(
    licenseKeysForSession("legroom", "cs_live_same_0123456789").map((k) => k.key),
    [first],
  );
});

test("the Suite email lists a key for each app on the shared scheme", async () => {
  await handler(signed(completed("app-suite", "cs_live_suite_0123456789", "evt_suite")));
  const text = sentMail().text;
  for (const [prefix, slug] of [["OV1", "outbound-veil"], ["LG1", "legroom"]]) {
    const key = keyIn(text, prefix);
    assert.ok(key, `${prefix} present`);
    assert.equal(verifyLicense(slug, key, { publicB64: TEST_PUBLIC }), true);
  }
  assert.match(text, /Outbound Veil: OV1-/);
  assert.match(text, /Your license keys/);
});

test("without the signing secret the email still goes out, with no key", async () => {
  env.PURPLELINK_LICENSE_PRIVATE_KEY = "";
  const res = await handler(signed(completed("legroom", "cs_live_nokey_0123456789", "evt_nokey")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = sentMail();
  assert.doesNotMatch(mail.text, /LG1-/);
  assert.match(mail.text, /success\/\?session_id=cs_live_nokey_0123456789/);
});

test("unrelated products carry no licensed-app keys", () => {
  assert.deepEqual(licenseKeysForSession("kit-bundle", "cs_x_0123456789").map((k) => k.slug), []);
});

// --- the success-page endpoint ----------------------------------------------------------

const { default: licenseHandler } = await import("../functions/purchase-license.mjs");
const { recoveryEmail } = await import("../functions/purchases-recover.mjs");
env.STRIPE_SECRET_KEY = "sk_test_dummy";

function stripeSession(session, status = 200) {
  globalThis.fetch = async (url) => {
    if (String(url).includes("/checkout/sessions/")) return new Response(JSON.stringify(session), { status });
    return new Response("{}", { status: 200 });
  };
}
const licenseCall = (sessionId, headers = {}) =>
  licenseHandler(new Request(`https://purplelink.llc/.netlify/functions/purchase-license?session_id=${sessionId}`, { headers }));

test("a paid Outbound Veil session returns its key, and it is the key the email carried", async () => {
  stripeSession({ id: "cs_live_ov_0123456789", payment_status: "paid", metadata: { product: "outbound-veil" } });
  const res = await licenseCall("cs_live_ov_0123456789");
  assert.equal(res.status, 200);
  const { keys } = await res.json();
  assert.equal(keys.length, 1);
  assert.equal(keys[0].product, "outbound-veil");
  assert.equal(verifyLicense("outbound-veil", keys[0].key, { publicB64: TEST_PUBLIC }), true);
  assert.deepEqual(keys.map((k) => k.key), licenseKeysForSession("outbound-veil", "cs_live_ov_0123456789").map((k) => k.key));
});

test("a paid Suite session returns a key for each app on the shared scheme", async () => {
  stripeSession({ id: "cs_live_suite_0123456789", payment_status: "paid", metadata: { product: "app-suite" } });
  const { keys } = await (await licenseCall("cs_live_suite_0123456789")).json();
  assert.deepEqual(keys.map((k) => k.product).sort(), ["legroom", "outbound-veil"]);
});

test("unpaid, unknown, wrongly-shaped and keyless sessions get no key", async () => {
  stripeSession({ id: "cs_live_u_0123456789", payment_status: "unpaid", metadata: { product: "legroom" } });
  assert.equal((await licenseCall("cs_live_u_0123456789")).status, 403);
  stripeSession({ id: "cs_live_k_0123456789", payment_status: "paid", metadata: { product: "kit-bundle" } });
  assert.equal((await licenseCall("cs_live_k_0123456789")).status, 403);
  stripeSession({}, 404);
  assert.equal((await licenseCall("cs_live_n_0123456789")).status, 403);
  assert.equal((await licenseCall("nope")).status, 400);
  assert.equal((await licenseHandler(new Request("https://purplelink.llc/x", { method: "POST" }))).status, 405);
});

test("a missing signing secret gives an empty list, not an error", async () => {
  env.PURPLELINK_LICENSE_PRIVATE_KEY = "";
  stripeSession({ id: "cs_live_m_0123456789", payment_status: "paid", metadata: { product: "legroom" } });
  const res = await licenseCall("cs_live_m_0123456789");
  assert.equal(res.status, 200);
  assert.deepEqual((await res.json()).keys, []);
});

test("the endpoint stops answering one address after its daily limit", async () => {
  stripeSession({ id: "cs_live_r_0123456789", payment_status: "paid", metadata: { product: "legroom" } });
  let last;
  for (let i = 0; i < 125; i++) last = await licenseCall("cs_live_r_0123456789", { "x-nf-client-connection-ip": "203.0.113.9" });
  assert.equal(last.status, 429);
  assert.equal((await licenseCall("cs_live_r_0123456789", { "x-nf-client-connection-ip": "203.0.113.10" })).status, 200);
});

// --- recovery email ---------------------------------------------------------------------

test("the recovery email lists the same keys the purchase email carried", () => {
  const purchases = [{ sessionId: "cs_live_lg_0123456789", product: "legroom", created: 1 }];
  const keysBySession = new Map([["cs_live_lg_0123456789", licenseKeysForSession("legroom", "cs_live_lg_0123456789")]]);
  const mail = recoveryEmail(purchases, null, null, keysBySession);
  const key = keysBySession.get("cs_live_lg_0123456789")[0].key;
  assert.ok(mail.text.includes(`Legroom: ${key}`));
  assert.ok(mail.html.includes(key));
  assert.match(mail.text, /free for 7 days, then asks for its key/);
});
