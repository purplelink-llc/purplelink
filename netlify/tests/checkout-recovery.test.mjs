// ModernTex checkout recovery: checkout.mjs adds the consent and recovery parameters (and retries without them if
// Stripe rejects them), and stripe-webhook.mjs sends one recovery email per consenting address. Stripe, Resend and
// Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/checkout-recovery.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend",
  RESEND_API_KEY: "re_dummy", FOLLOWUP_UNSUBSCRIBE_SECRET: "unsub_secret",
};
globalThis.Netlify = { env: { get: (k) => (k.startsWith("STRIPE_PRICE_") ? "price_dummy" : env[k]) } };

const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook } = await import("../functions/stripe-webhook.mjs");
const { RECOVERY_PRODUCTS, recoveryParams, recoveryEmail, isRecoveryParamError } = await import("../lib/checkout-recovery.mjs");
const { emailHash } = await import("../lib/followup.mjs");

let calls;
let stripeReply;
beforeEach(() => {
  store.clear();
  calls = [];
  delete env.CHECKOUT_RECOVERY;
  stripeReply = () => new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/c/pay/cs_test_1" }), { status: 200 });
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (String(url).startsWith("https://api.stripe.com/")) return stripeReply(opts);
    return new Response("{}", { status: 200 });
  };
});

let ipN = 10;
const buy = (product) => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST",
  headers: { "content-type": "application/json", "x-nf-client-connection-ip": `203.0.113.${ipN++}` },
  body: JSON.stringify({ product }),
}));
const stripeBodies = () => calls.filter((c) => c.url.startsWith("https://api.stripe.com/")).map((c) => new URLSearchParams(c.opts.body));

test("a ModernTex checkout asks for consent and enables recovery without promotion codes", async () => {
  const res = await buy("moderntex");
  assert.equal(res.status, 200);
  const [p] = stripeBodies();
  assert.equal(p.get("consent_collection[promotions]"), "auto");
  assert.equal(p.get("after_expiration[recovery][enabled]"), "true");
  assert.equal(p.get("after_expiration[recovery][allow_promotion_codes]"), "false");
});

test("the price the recovery email states is the price checkout charges", async () => {
  await buy("moderntex");
  const [p] = stripeBodies();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), String(RECOVERY_PRODUCTS.moderntex.cents));
  assert.equal(RECOVERY_PRODUCTS.moderntex.price, `$${(RECOVERY_PRODUCTS.moderntex.cents / 100).toFixed(2)}`);
});

test("other products get no recovery parameters", async () => {
  await buy("keyfeel");
  const [p] = stripeBodies();
  assert.equal(p.get("consent_collection[promotions]"), null);
  assert.equal(p.get("after_expiration[recovery][enabled]"), null);
  assert.deepEqual(recoveryParams("keyfeel"), {});
});

test("if Stripe rejects the recovery parameters, checkout retries once without them and still returns a URL", async () => {
  let n = 0;
  stripeReply = () => (n++ === 0
    ? new Response(JSON.stringify({ error: { type: "invalid_request_error", param: "consent_collection[promotions]", message: "Not available" } }), { status: 400 })
    : new Response(JSON.stringify({ id: "cs_test_2", url: "https://checkout.stripe.com/c/pay/cs_test_2" }), { status: 200 }));
  const res = await buy("moderntex");
  assert.equal(res.status, 200);
  assert.equal((await res.json()).id, "cs_test_2");
  const bodies = stripeBodies();
  assert.equal(bodies.length, 2);
  assert.equal(bodies[1].get("consent_collection[promotions]"), null);
  const keys = calls.filter((c) => c.url.startsWith("https://api.stripe.com/")).map((c) => c.opts.headers["Idempotency-Key"]);
  assert.notEqual(keys[0], keys[1], "the retry needs its own idempotency key");
});

test("an unrelated Stripe error is not retried", async () => {
  stripeReply = () => new Response(JSON.stringify({ error: { type: "card_error", message: "Your account cannot currently make live charges." } }), { status: 400 });
  const res = await buy("moderntex");
  assert.equal(res.status, 502);
  assert.equal(stripeBodies().length, 1);
  assert.equal(isRecoveryParamError({ error: { param: "line_items[0][price]" } }), false);
});

// --- webhook ------------------------------------------------------------------------------------------------
function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", {
    method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body,
  });
}
const expired = ({ id = "cs_exp_1", product = "moderntex", consent = "opt_in", email = "lead@example.edu", url = "https://buy.stripe.com/r/live_abc" } = {}) => ({
  id: `evt_${id}`, type: "checkout.session.expired",
  data: { object: {
    id, status: "expired", payment_status: "unpaid", metadata: { product },
    consent: consent ? { promotions: consent } : null,
    customer_details: email ? { email } : null,
    after_expiration: url ? { recovery: { enabled: true, url, expires_at: 0 } } : null,
  } },
});
const resendCalls = () => calls.filter((c) => c.url.startsWith("https://api.resend.com/"));

test("a consenting ModernTex lead gets exactly one plain recovery email with the recovery link and an unsubscribe", async () => {
  const res = await webhook(signed(expired()));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "recovery_sent");
  const sent = resendCalls();
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["lead@example.edu"]);
  assert.match(mail.text, /https:\/\/buy\.stripe\.com\/r\/live_abc/);
  assert.match(mail.text, /\$19\.99/);
  assert.match(mail.text, /nothing was charged/);
  assert.match(mail.text, /followup-unsubscribe\?u=/);
  assert.ok(mail.headers["List-Unsubscribe"]);
  assert.doesNotMatch(mail.text, /—/, "no em dashes");

  // Stripe redelivers the same event: no second email.
  await webhook(signed(expired()));
  assert.equal(resendCalls().length, 1);
  // A second abandoned checkout from the same address inside 30 days: still no second email.
  const again = await webhook(signed(expired({ id: "cs_exp_2" })));
  assert.equal((await again.json()).status, "recovery_quiet");
  assert.equal(resendCalls().length, 1);
});

test("no email without consent, without an address, without a recovery URL, or for another product", async () => {
  for (const [opts, status] of [
    [{ consent: "none" }, "recovery_no_consent"],
    [{ consent: null }, "recovery_no_consent"],
    [{ email: "" }, "recovery_no_email"],
    [{ url: "" }, "recovery_no_recovery_url"],
    [{ product: "keyfeel" }, "recovery_not_recovery_product"],
  ]) {
    const res = await webhook(signed(expired(opts)));
    assert.equal((await res.json()).status, status);
  }
  assert.equal(resendCalls().length, 0);
});

test("no email to someone who already bought ModernTex or unsubscribed from follow-ups", async () => {
  const paid = {
    id: "evt_paid", type: "checkout.session.completed",
    data: { object: { id: "cs_live_mtx_abcdefghij", status: "complete", payment_status: "paid", amount_total: 1999,
      customer_details: { email: "Buyer@Example.edu" }, metadata: { product: "moderntex" } } },
  };
  await webhook(signed(paid));
  calls = [];
  const res = await webhook(signed(expired({ email: "buyer@example.edu" })));
  assert.equal((await res.json()).status, "recovery_already_bought");

  store.set(`followup-suppressed/${emailHash("gone@example.edu")}`, "2026-10-01T00:00:00Z");
  const res2 = await webhook(signed(expired({ id: "cs_exp_9", email: "gone@example.edu" })));
  assert.equal((await res2.json()).status, "recovery_suppressed");
  assert.equal(resendCalls().length, 0);
});

test("CHECKOUT_RECOVERY=off sends nothing", async () => {
  env.CHECKOUT_RECOVERY = "off";
  const res = await webhook(signed(expired()));
  assert.equal((await res.json()).status, "recovery_off");
  assert.equal(resendCalls().length, 0);
});

test("a failed send returns 502 so Stripe retries, and the retry sends", async () => {
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    return new Response("{}", { status: 500 });
  };
  const res = await webhook(signed(expired()));
  assert.equal(res.status, 502);
  globalThis.fetch = async (url, opts = {}) => { calls.push({ url: String(url), opts }); return new Response("{}", { status: 200 }); };
  const retry = await webhook(signed(expired()));
  assert.equal((await retry.json()).status, "recovery_sent");
});

test("the recovery URL is escaped in the HTML part", () => {
  const mail = recoveryEmail({ to: "a@b.co", product: "moderntex", url: "https://buy.stripe.com/r/x?a=1&b=<2>", secret: "s" });
  assert.match(mail.html, /a=1&amp;b=&lt;2&gt;/);
  assert.doesNotMatch(mail.html, /<2>/);
});
