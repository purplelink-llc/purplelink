// Referrals for every product (netlify/lib/referrals.mjs): the friend's 20% at checkout, the webhook telling Modal
// about each paid order, and the buyer's own link on the success page and in the purchase email. Stripe, Modal,
// Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/referrals.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {
  STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", RESEND_API_KEY: "re_dummy",
  STRIPE_SECRET_KEY: "sk_test_dummy",
};
globalThis.Netlify = { env: { get: (k) => (k.startsWith("STRIPE_PRICE_") ? "price_dummy" : env[k]) } };

const lib = await import("../lib/referrals.mjs");
const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook } = await import("../functions/stripe-webhook.mjs");
const { default: offers } = await import("../functions/buyer-offers.mjs");

const REF = "0123456789";
const LINK = `https://purplelink.llc/?ref=${REF}`;
const mem = () => blobsModule.getStore("buyer-codes");

let calls, stripeReply, modalReply;
beforeEach(() => {
  store.clear();
  calls = [];
  stripeReply = () => new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
  modalReply = (url) => {
    if (url.includes("/referral/check")) return new Response(JSON.stringify({ valid: false }), { status: 200 });
    if (url.includes("/referral/register")) return new Response(JSON.stringify({ code: "abcdef0123", link: "https://purplelink.llc/?ref=abcdef0123", referral: "no_referral" }), { status: 200 });
    return new Response("{}", { status: 200 });
  };
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    if (u.startsWith("https://api.stripe.com/")) return stripeReply(u, opts);
    if (/modal\.run/.test(u)) return modalReply(u, opts);
    return new Response("{}", { status: 200 });
  };
});

// ---- the library ----

test("the friend discount skips bundles, seats, subscriptions and the small tools", () => {
  assert.equal(lib.friendEligible("moderntex", { amount: 1999 }), true);
  assert.equal(lib.friendEligible("paper-review-standard", { envKey: "X" }), true);
  assert.equal(lib.friendEligible("legroom", { envKey: "X" }), true);
  assert.equal(lib.friendEligible("cover-letter", { envKey: "X" }), false);
  assert.equal(lib.friendEligible("response-review", { envKey: "X" }), false);
  assert.equal(lib.friendEligible("lenses", { amount: 499 }), false);
  assert.equal(lib.friendEligible("bundle-2", { amount: 3499, bundle: true }), false);
  assert.equal(lib.friendEligible("moderntex-seats", { seats: true }), false);
  assert.equal(lib.friendEligible("paper-review-annual", { amount: 7900, mode: "subscription" }), false);
});

test("checkRef trusts the Blobs mirror, else asks Modal once and mirrors a yes", async () => {
  assert.equal(await lib.checkRef(mem(), "vitae", { secret: "s" }), false);
  assert.equal(calls.length, 0, "a malformed code never leaves the function");
  modalReply = () => new Response(JSON.stringify({ valid: true }), { status: 200 });
  assert.equal(await lib.checkRef(mem(), REF, { secret: "s" }), true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].opts.headers["x-webhook-secret"], "s");
  assert.ok(await mem().get(`ref/${REF}`));
  assert.equal(await lib.checkRef(mem(), REF, { secret: "s" }), true);
  assert.equal(calls.length, 1, "the second check is served from the mirror");
});

test("checkRef treats a Modal failure as no discount", async () => {
  modalReply = () => new Response("nope", { status: 500 });
  assert.equal(await lib.checkRef(mem(), REF, { secret: "s" }), false);
  globalThis.fetch = async () => { throw new Error("timeout"); };
  assert.equal(await lib.checkRef(mem(), REF, { secret: "s" }), false);
});

test("the email paragraph names the link and the terms", () => {
  const t = lib.referralText(LINK);
  assert.match(t.text, /Your referral link: https:\/\/purplelink\.llc\/\?ref=0123456789/);
  assert.match(t.text, /gets 20% off, and two weeks later you get a free Standard Paper Review/);
  assert.match(t.html, /<a href="https:\/\/purplelink\.llc\/\?ref=0123456789">/);
  assert.deepEqual(lib.referralText(""), { text: "", html: "" });
});

// ---- checkout ----

async function buy(product, extra, ip) {
  const res = await checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
    method: "POST",
    headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip },
    body: JSON.stringify({ product, ...extra }),
  }));
  const sent = calls.filter((c) => c.url.startsWith("https://api.stripe.com/v1/checkout/sessions"));
  return { res, forms: sent.map((c) => new URLSearchParams(c.opts.body)) };
}

test("checkout applies the friend coupon for a known code on an eligible product", async () => {
  await mem().set(`ref/${REF}`, "{}");
  const { res, forms } = await buy("moderntex", { ref: REF }, "203.0.113.80");
  assert.equal(res.status, 200);
  assert.equal(forms.length, 1);
  assert.equal(forms[0].get("discounts[0][coupon]"), "purplelink-friend-20");
  assert.equal(forms[0].get("metadata[friend_discount]"), "20");
  assert.equal(forms[0].get("metadata[referral_code]"), REF);
  assert.equal(forms[0].get("allow_promotion_codes"), null);
});

test("an unknown code, an ineligible product or a buyer code means no friend discount", async () => {
  let r = await buy("moderntex", { ref: REF }, "203.0.113.81");             // Modal says no
  assert.equal(r.forms[0].get("discounts[0][coupon]"), null);
  assert.equal(r.forms[0].get("allow_promotion_codes"), "true");
  assert.equal(r.forms[0].get("metadata[referral_code]"), REF, "the code still rides along for the record");
  await mem().set(`ref/${REF}`, "{}");
  calls = [];
  r = await buy("cover-letter", { ref: REF }, "203.0.113.82");
  assert.equal(r.forms[0].get("discounts[0][coupon]"), null);
  calls = [];
  r = await buy("bundle-2", { ref: REF, apps: "keyfeel,panely" }, "203.0.113.83");
  if (r.forms[0]) assert.equal(r.forms[0].get("discounts[0][coupon]"), null);
});

test("a missing coupon is created once and the session made again", async () => {
  await mem().set(`ref/${REF}`, "{}");
  let n = 0;
  stripeReply = (url) => {
    if (url.endsWith("/v1/coupons")) return new Response(JSON.stringify({ id: "purplelink-friend-20" }), { status: 200 });
    n += 1;
    if (n === 1) return new Response(JSON.stringify({ error: { code: "resource_missing", param: "discounts[0][coupon]", message: "No such coupon: 'purplelink-friend-20'" } }), { status: 400 });
    return new Response(JSON.stringify({ id: "cs_test_2", url: "https://checkout.stripe.com/pay/cs_test_2" }), { status: 200 });
  };
  const { res, forms } = await buy("keyfeel", { ref: REF }, "203.0.113.84");
  assert.equal(res.status, 200);
  const coupon = calls.filter((c) => c.url.endsWith("/v1/coupons"));
  assert.equal(coupon.length, 1);
  const cf = new URLSearchParams(coupon[0].opts.body);
  assert.equal(cf.get("id"), "purplelink-friend-20");
  assert.equal(cf.get("percent_off"), "20");
  assert.equal(cf.get("duration"), "once");
  assert.equal(forms.length, 2);
  assert.equal(forms[1].get("discounts[0][coupon]"), "purplelink-friend-20");
});

test("a coupon Stripe keeps refusing never blocks the sale", async () => {
  await mem().set(`ref/${REF}`, "{}");
  stripeReply = (url, opts) => {
    if (url.endsWith("/v1/coupons")) return new Response(JSON.stringify({ error: { code: "api_error" } }), { status: 500 });
    if (new URLSearchParams(opts.body).get("discounts[0][coupon]")) {
      return new Response(JSON.stringify({ error: { code: "coupon_expired", param: "discounts[0][coupon]", message: "This coupon is expired" } }), { status: 400 });
    }
    return new Response(JSON.stringify({ id: "cs_test_3", url: "https://checkout.stripe.com/pay/cs_test_3" }), { status: 200 });
  };
  const { res, forms } = await buy("keyfeel", { ref: REF }, "203.0.113.85");
  assert.equal(res.status, 200);
  const last = forms[forms.length - 1];
  assert.equal(last.get("discounts[0][coupon]"), null);
  assert.equal(last.get("allow_promotion_codes"), "true");
});

// ---- the webhook and the success page ----

function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", {
    method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body,
  });
}
const completed = (product, id, obj = {}) => ({
  id, type: "checkout.session.completed",
  data: { object: { id: `cs_live_${product.replace(/-/g, "")}abcdefg1`, status: "complete", payment_status: "paid", mode: "payment",
    amount_total: 1599, total_details: { amount_discount: 400 }, customer_details: { email: "friend@example.com" },
    metadata: { product, referral_code: REF, friend_discount: "20" }, ...obj } },
});
const registerCall = () => calls.find((c) => c.url.endsWith("/referral/register"));

test("a referred app order is registered with Modal and the buyer's own link goes in the email and on the page", async () => {
  const res = await webhook(signed(completed("moderntex", "evt_rf1")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const reg = registerCall();
  assert.ok(reg, "Modal hears about the order");
  assert.equal(reg.opts.headers["x-webhook-secret"], "backend");
  assert.deepEqual(JSON.parse(reg.opts.body), {
    session_id: "cs_live_moderntexabcdefg1", email: "friend@example.com", product: "moderntex",
    amount_paid: 1599, referral_code: REF,
  });
  const mail = JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);
  assert.match(mail.text, /Your referral link: https:\/\/purplelink\.llc\/\?ref=abcdef0123/);
  assert.match(mail.html, /\?ref=abcdef0123/);
  const page = await offers(new Request("https://purplelink.llc/.netlify/functions/buyer-offers?session_id=cs_live_moderntexabcdefg1"));
  assert.equal((await page.json()).referral_link, "https://purplelink.llc/?ref=abcdef0123");
  assert.ok(await mem().get("ref/abcdef0123"), "the buyer's own code is mirrored for checkout");
});

test("Modal being down never blocks delivery; the email just has no link", async () => {
  modalReply = () => new Response("down", { status: 503 });
  const res = await webhook(signed(completed("legroom", "evt_rf2")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);
  assert.doesNotMatch(mail.text, /Your referral link/);
});

test("a Paper Review order is registered after its token", async () => {
  const res = await webhook(signed(completed("paper-review-deep", "evt_rf3", { amount_total: 1200 })));
  assert.ok(res.status < 300);
  const urls = calls.filter((c) => /modal\.run/.test(c.url)).map((c) => c.url);
  const tokenAt = urls.findIndex((u) => u.endsWith("/paper-review/register-token"));
  const refAt = urls.findIndex((u) => u.endsWith("/referral/register"));
  assert.ok(tokenAt >= 0 && refAt > tokenAt);
  assert.equal(JSON.parse(registerCall().opts.body).referral_code, REF);
});
