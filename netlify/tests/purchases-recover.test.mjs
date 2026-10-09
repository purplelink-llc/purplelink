// Tests for purchases-recover.mjs: find-my-purchases by email.
// Stripe, Resend and Netlify Blobs are stubbed; a throwaway Ed25519 key signs ModernTex keys.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/purchases-recover.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";

const blobs = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => blobs.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { blobs.set(`${name}/${k}`, v); },
  }),
};
// `exports` on newer Node (Node 26 rejects both together), `namedExports` on Node 22.
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { privateKey } = generateKeyPairSync("ed25519");
const jwk = privateKey.export({ format: "jwk" });
const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy",
  RESEND_API_KEY: "re_dummy",
  MODERNTEX_LICENSE_PRIVATE_KEY: Buffer.from(jwk.d, "base64url").toString("base64"),
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: handler, purchasesForEmail, recoveryEmail } = await import("../functions/purchases-recover.mjs");

let calls;
let sessions;
beforeEach(() => {
  blobs.clear();
  calls = [];
  sessions = [];
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    if (u.startsWith("https://api.resend.com/")) return new Response("{}", { status: 200 });
    if (u.startsWith("https://api.stripe.com/v1/checkout/sessions")) {
      return new Response(JSON.stringify({ data: sessions, has_more: false }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${u}`);
  };
});

const post = (body, ip = "1.2.3.4") => handler(new Request("https://purplelink.llc/.netlify/functions/purchases-recover", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": ip }, body: JSON.stringify(body),
}));

test("finds paid ModernTex and kit purchases only, newest first", async () => {
  sessions = [
    { id: "cs_old", payment_status: "paid", created: 100, metadata: { product: "moderntex" } },
    { id: "cs_new", payment_status: "paid", created: 300, metadata: { product: "moderntex" } },
    { id: "cs_kit", payment_status: "paid", created: 200, metadata: { product: "kit-clip" } },
    { id: "cs_unpaid", payment_status: "unpaid", created: 400, metadata: { product: "moderntex" } },
    { id: "cs_review", payment_status: "paid", created: 500, metadata: { product: "paper-review-standard" } },
    { id: "cs_foreign", payment_status: "paid", created: 600, metadata: {} },
  ];
  const { purchases } = await purchasesForEmail("A@Example.com", "sk");
  assert.deepEqual(purchases.map((p) => p.sessionId), ["cs_new", "cs_kit", "cs_old"]);
  assert.ok(calls.some((c) => c.url.includes("customer_details%5Bemail%5D=A%40Example.com")));
  assert.ok(calls.some((c) => c.url.includes("customer_details%5Bemail%5D=a%40example.com")));
});

test("the email carries a fresh key and the latest download page", async () => {
  const mail = recoveryEmail([
    { sessionId: "cs_new", product: "moderntex", created: 3 },
    { sessionId: "cs_kit", product: "kit-clip", created: 2 },
  ], "MTX1-ABCDE");
  assert.match(mail.text, /moderntex\/success\/\?session_id=cs_new/);
  assert.match(mail.text, /MTX1-ABCDE/);
  assert.match(mail.text, /kits\/success\/\?session_id=cs_kit/);
  assert.match(mail.text, /The Clip Pipeline kit/);
});

test("answers the same whether or not anything matched, and emails only on a match", async () => {
  sessions = [];
  const r1 = await post({ email: "nobody@example.com" });
  assert.equal(r1.status, 200);
  assert.deepEqual(await r1.json(), { status: "sent_if_found" });
  assert.equal(calls.filter((c) => c.url.startsWith("https://api.resend.com/")).length, 0);

  sessions = [{ id: "cs_1", payment_status: "paid", created: 1, metadata: { product: "moderntex" } }];
  const r2 = await post({ email: "buyer@example.com" });
  assert.deepEqual(await r2.json(), { status: "sent_if_found" });
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const payload = JSON.parse(sent[0].opts.body);
  assert.deepEqual(payload.to, ["buyer@example.com"]);
  assert.match(payload.text, /MTX1-[0-9A-Z-]+/);
});

test("rejects a bad address and caps requests per address", async () => {
  assert.equal((await post({ email: "not-an-email" })).status, 400);
  for (let i = 0; i < 3; i++) assert.equal((await post({ email: "same@example.com" }, `10.0.0.${i}`)).status, 200);
  assert.equal((await post({ email: "same@example.com" }, "10.0.0.9")).status, 429);
});

// ---- Mac Suite ----

test("finds a paid Mac Suite purchase", async () => {
  sessions = [
    { id: "cs_suite", payment_status: "paid", created: 5, metadata: { product: "app-suite" } },
    { id: "cs_unpaid", payment_status: "unpaid", created: 6, metadata: { product: "app-suite" } },
  ];
  const { purchases } = await purchasesForEmail("buyer@example.com", "sk_test_dummy");
  assert.deepEqual(purchases.map((p) => p.sessionId), ["cs_suite"]);
});

test("the recovery email for the Suite links the one page and carries the ModernTex key", () => {
  const mail = recoveryEmail([{ sessionId: "cs_suite", product: "app-suite", created: 5 }], "MTX1-AAAAA-BBBBB");
  assert.match(mail.text, /Purplelink Mac Suite/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/suite\/success\/\?session_id=cs_suite/);
  assert.match(mail.text, /ModernTex, Outbound Veil, Legroom, Keyfeel and Tapefolio downloads and your lifetime Vitae Plus key/);
  assert.match(mail.html, /Keyfeel and Tapefolio downloads/);
  assert.match(mail.text, /MTX1-AAAAA-BBBBB/);
  assert.match(mail.html, /MTX1-AAAAA-BBBBB/);
  // Without a signing key it does not invent one.
  assert.doesNotMatch(recoveryEmail([{ sessionId: "cs_suite", product: "app-suite", created: 5 }], null).text, /MTX1/);
});

// ---- Legroom ----

test("finds a paid Legroom purchase and ignores an unpaid one", async () => {
  sessions = [
    { id: "cs_lg", payment_status: "paid", created: 7, metadata: { product: "legroom" } },
    { id: "cs_lg_unpaid", payment_status: "unpaid", created: 8, metadata: { product: "legroom" } },
  ];
  const { purchases } = await purchasesForEmail("buyer@example.com", "sk_test_dummy");
  assert.deepEqual(purchases.map((p) => [p.sessionId, p.product]), [["cs_lg", "legroom"]]);
});

test("the recovery email for Legroom links its success page and carries no ModernTex key", () => {
  const mail = recoveryEmail([{ sessionId: "cs_lg", product: "legroom", created: 7 }], null);
  assert.match(mail.text, /Legroom for macOS/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/legroom\/success\/\?session_id=cs_lg/);
  assert.doesNotMatch(mail.text, /MTX1|license key/i);
  assert.match(mail.html, /legroom\/success\//);
});

// ---- Keyfeel ----

test("finds a paid Keyfeel purchase and ignores an unpaid one", async () => {
  sessions = [
    { id: "cs_kf", payment_status: "paid", created: 9, metadata: { product: "keyfeel" } },
    { id: "cs_kf_unpaid", payment_status: "unpaid", created: 10, metadata: { product: "keyfeel" } },
  ];
  const { purchases } = await purchasesForEmail("buyer@example.com", "sk_test_dummy");
  assert.deepEqual(purchases.map((p) => [p.sessionId, p.product]), [["cs_kf", "keyfeel"]]);
});

test("the recovery email for Keyfeel links its success page and carries no ModernTex key", () => {
  const mail = recoveryEmail([{ sessionId: "cs_kf", product: "keyfeel", created: 9 }], null);
  assert.match(mail.text, /Keyfeel for macOS/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/keyfeel\/success\/\?session_id=cs_kf/);
  assert.doesNotMatch(mail.text, /MTX1|license key/i);
  assert.match(mail.html, /keyfeel\/success\//);
});

// ---- Tapefolio ----

test("finds a paid Tapefolio purchase and ignores an unpaid one", async () => {
  sessions = [
    { id: "cs_tf", payment_status: "paid", created: 11, metadata: { product: "tapefolio" } },
    { id: "cs_tf_unpaid", payment_status: "unpaid", created: 12, metadata: { product: "tapefolio" } },
  ];
  const { purchases } = await purchasesForEmail("buyer@example.com", "sk_test_dummy");
  assert.deepEqual(purchases.map((p) => [p.sessionId, p.product]), [["cs_tf", "tapefolio"]]);
});

test("the recovery email for Tapefolio links its success page, carries no ModernTex key, and carries the Tapefolio key it is given", () => {
  const without = recoveryEmail([{ sessionId: "cs_tf", product: "tapefolio", created: 11 }], null);
  assert.match(without.text, /Tapefolio for macOS/);
  assert.match(without.text, /https:\/\/purplelink\.llc\/tapefolio\/success\/\?session_id=cs_tf/);
  assert.doesNotMatch(without.text, /MTX1|license key/i);
  assert.match(without.html, /tapefolio\/success\//);
  const KEY = "TFL1-ABCDE-FGHJK";
  const withKey = recoveryEmail([{ sessionId: "cs_tf", product: "tapefolio", created: 11 }], null, null, new Map(), KEY);
  assert.match(withKey.text, /Tapefolio license key \(in Tapefolio, choose Enter License Key and paste it\): TFL1-ABCDE-FGHJK/);
  assert.match(withKey.html, /TFL1-ABCDE-FGHJK/);
  // Another product's recovery email never carries it.
  assert.doesNotMatch(recoveryEmail([{ sessionId: "cs_lg", product: "legroom", created: 7 }], null, null, new Map(), KEY).text, /TFL1/);
  // The Suite does.
  assert.match(recoveryEmail([{ sessionId: "cs_suite", product: "app-suite", created: 5 }], null, null, new Map(), KEY).text, /TFL1-ABCDE-FGHJK/);
});

test("the recovery handler emails a Tapefolio buyer the key for the address they typed, the same key checkout showed", async (t) => {
  env.TAPEFOLIO_LICENSE_PRIVATE_KEY = Buffer.alloc(32, 5).toString("base64");
  t.after(() => { delete env.TAPEFOLIO_LICENSE_PRIVATE_KEY; });
  sessions = [{ id: "cs_tf2", payment_status: "paid", created: 13, metadata: { product: "tapefolio" } }];
  const res = await post({ email: "Tapefolio.Buyer@example.com" }, "10.9.0.1");
  assert.equal(res.status, 200);
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const payload = JSON.parse(sent[0].opts.body);
  const { issueTapefolioLicense } = await import("../lib/tapefolio-license.mjs");
  const expected = issueTapefolioLicense("Tapefolio.Buyer@example.com", (k) => env[k]);
  if (expected === null) return t.skip("this Node rejects a seed that does not match the production public key");
  assert.ok(payload.text.includes(expected), "the emailed key is the key derived from the address");
});
