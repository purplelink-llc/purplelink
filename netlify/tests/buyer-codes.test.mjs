// Cross-sell code (netlify/lib/buyer-codes.mjs): issued once per paid order, applied once at checkout, shown on the
// success page and in the purchase email. Stripe, Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/buyer-codes.test.mjs

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

const lib = await import("../lib/buyer-codes.mjs");
const { makeCode, earnsCode, checkCode, issueCode, markUsed, crossSellOffer, familyOf, normalizeCode } = lib;
const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook } = await import("../functions/stripe-webhook.mjs");
const { default: offers } = await import("../functions/buyer-offers.mjs");

const NOW = Date.UTC(2026, 10, 5, 15, 0, 0);
const memStore = () => blobsModule.getStore("buyer-codes");
const paid = (over = {}) => ({
  id: "cs_live_abcdefghij1234", mode: "payment", payment_status: "paid", amount_total: 999,
  total_details: { amount_discount: 0 }, metadata: { product: "legroom" }, ...over,
});

let calls;
let stripeReply;
beforeEach(() => {
  store.clear();
  calls = [];
  stripeReply = () => new Response(JSON.stringify({ id: "x" }), { status: 200 });
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (String(url).startsWith("https://api.stripe.com/")) return stripeReply(String(url), opts);
    return new Response("{}", { status: 200 });
  };
});

async function seed(code, rec) {
  await memStore().set(`code/${code}`, JSON.stringify({
    coupon: `xs-${code.toLowerCase()}`, source_product: "legroom", family: "legroom", owned_parts: [],
    email_hash: "h", created: Math.floor(NOW / 1000), expires: Math.floor(Date.now() / 1000) + 86400, ...rec,
  }));
}

// ---- the library ----

test("a code is the same for the same order and has the PL- format", () => {
  const a = makeCode("cs_live_1", "s");
  assert.equal(a, makeCode("cs_live_1", "s"));
  assert.notEqual(a, makeCode("cs_live_2", "s"));
  assert.match(a, lib.CODE_RE);
  assert.equal(normalizeCode(` ${a.toLowerCase()} `), a);
  assert.equal(normalizeCode("PL-0OIL1111"), "");
});

test("only a paid, undiscounted one-time order earns a code", () => {
  assert.equal(earnsCode(paid()), true);
  assert.equal(earnsCode(paid({ mode: "subscription" })), false);
  assert.equal(earnsCode(paid({ payment_status: "unpaid" })), false);
  assert.equal(earnsCode(paid({ amount_total: 0 })), false);
  assert.equal(earnsCode(paid({ total_details: { amount_discount: 300 } })), false);
  assert.equal(earnsCode(paid({ metadata: { product: "keyfeel", buyer_code: "PL-23456789" } })), false, "no chaining");
});

test("Paper Review tiers and packs are one family", () => {
  assert.equal(familyOf("paper-review-standard"), familyOf("paper-review-pack-5"));
  assert.notEqual(familyOf("legroom"), familyOf("keyfeel"));
});

test("checkCode gives a plain reason for every refusal", async () => {
  const s = memStore();
  await seed("PL-23456789", {});
  await seed("PL-USED2345", { used: "cs_live_other" });
  await seed("PL-EXP23456", { expires: Math.floor(Date.now() / 1000) - 10 });
  await seed("PL-PRS23456", { source_product: "paper-review-standard", family: "paper-review" });
  await seed("PL-SUT23456", { source_product: "bundle-2", family: "bundle-2", owned_parts: ["keyfeel", "legroom"] });

  assert.equal((await checkCode(s, "PL-23456789", "keyfeel", {})).ok, true);
  assert.equal((await checkCode(s, "pl-23456789", "keyfeel", {})).coupon, "xs-pl-23456789");
  assert.match((await checkCode(s, "PL-99999999", "keyfeel", {})).detail, /not one of ours/);
  assert.match((await checkCode(s, "nonsense", "keyfeel", {})).detail, /not one of ours/);
  assert.match((await checkCode(s, "PL-23456789", "bundle-3", {})).detail, /not bundles/);
  assert.match((await checkCode(s, "PL-23456789", "paper-review-annual", { mode: "subscription" })).detail, /subscriptions/);
  assert.match((await checkCode(s, "PL-USED2345", "keyfeel", {})).detail, /already been used/);
  assert.match((await checkCode(s, "PL-EXP23456", "keyfeel", {})).detail, /expired/);
  assert.match((await checkCode(s, "PL-23456789", "legroom", {})).detail, /different product/);
  assert.match((await checkCode(s, "PL-PRS23456", "paper-review-pack-5", {})).detail, /different product/);
  assert.equal((await checkCode(s, "PL-PRS23456", "legroom", {})).ok, true);
  assert.match((await checkCode(s, "PL-SUT23456", "keyfeel", {})).detail, /already own/);
});

test("issueCode makes one Stripe coupon per order and is safe to repeat", async () => {
  const s = memStore();
  const first = await issueCode({ store: s, stripeKey: "sk", secret: "sec", session: paid(), product: "legroom", email: "a@b.c", nowMs: NOW });
  assert.equal(first.code, makeCode(paid().id, "sec"));
  assert.equal(first.expires, Math.floor(NOW / 1000) + 30 * 86400);
  const posts = calls.filter((c) => c.url === "https://api.stripe.com/v1/coupons");
  assert.equal(posts.length, 1);
  const form = new URLSearchParams(posts[0].opts.body);
  assert.equal(form.get("id"), `xs-${first.code.toLowerCase()}`);
  assert.equal(form.get("percent_off"), "30");
  assert.equal(form.get("duration"), "once");
  assert.equal(form.get("max_redemptions"), "1");
  assert.equal(form.get("redeem_by"), String(first.expires));

  const again = await issueCode({ store: s, stripeKey: "sk", secret: "sec", session: paid(), product: "legroom", email: "a@b.c", nowMs: NOW });
  assert.deepEqual(again, first);
  assert.equal(calls.filter((c) => c.url === "https://api.stripe.com/v1/coupons").length, 1, "no second coupon");
});

test("issueCode treats an existing coupon (a retry after a crash) as made", async () => {
  stripeReply = () => new Response(JSON.stringify({ error: { code: "resource_already_exists" } }), { status: 400 });
  const out = await issueCode({ store: memStore(), stripeKey: "sk", secret: "sec", session: paid(), product: "legroom", email: "", nowMs: NOW });
  assert.ok(out?.code);
});

test("issueCode throws on any other Stripe error and skips orders that earn nothing", async () => {
  stripeReply = () => new Response(JSON.stringify({ error: { code: "api_key_expired" } }), { status: 401 });
  await assert.rejects(issueCode({ store: memStore(), stripeKey: "sk", secret: "s", session: paid(), product: "legroom", nowMs: NOW }));
  assert.equal(await issueCode({ store: memStore(), stripeKey: "sk", secret: "s", session: paid({ amount_total: 0 }), product: "legroom" }), null);
  assert.equal(await issueCode({ store: memStore(), stripeKey: "", secret: "s", session: paid(), product: "legroom" }), null);
});

test("markUsed records the order that used a code", async () => {
  await seed("PL-23456789", {});
  assert.equal(await markUsed(memStore(), { id: "cs_live_used", metadata: { buyer_code: "PL-23456789" } }), true);
  const rec = JSON.parse(await memStore().get("code/PL-23456789"));
  assert.equal(rec.used, "cs_live_used");
  assert.equal(await markUsed(memStore(), { id: "cs_live_used", metadata: {} }), false);
});

test("the email paragraph names the code, the date and the products link", () => {
  const expires = Math.floor(Date.UTC(2026, 11, 5, 15) / 1000);
  const { text, html } = crossSellOffer({ code: "PL-23456789", expires });
  assert.match(text, /PL-23456789 takes 30% off one other Purplelink product, once, until December 5, 2026/);
  assert.match(text, /https:\/\/purplelink\.llc\/products\/\?code=PL-23456789/);
  assert.match(html, /<strong>PL-23456789<\/strong>/);
  assert.doesNotMatch(text + html, /—|–/);
  assert.deepEqual(crossSellOffer(null), { text: "", html: "" });
});

// ---- the success page function ----

const offerReq = (id) => new Request(`https://purplelink.llc/.netlify/functions/buyer-offers?session_id=${id}`);

test("buyer-offers: bad id, pending, the code, then done once used", async () => {
  assert.equal((await offers(offerReq("nope"))).status, 400);
  const sid = "cs_live_abcdefghij1234";
  assert.deepEqual(await (await offers(offerReq(sid))).json(), { pending: true });
  await seed("PL-23456789", {});
  await memStore().set(`session/${sid}`, "PL-23456789");
  const res = await offers(offerReq(sid));
  assert.equal(res.headers.get("cache-control"), "no-store");
  const body = await res.json();
  assert.equal(body.code, "PL-23456789");
  assert.equal(body.percent, 30);
  assert.equal(body.source_product, "legroom");
  assert.match(body.expires_text, /^[A-Z][a-z]+ \d{1,2}, \d{4}$/);
  await seed("PL-23456789", { used: "cs_live_x" });
  assert.deepEqual(await (await offers(offerReq(sid))).json(), { done: true });
});

// ---- checkout ----

async function buy(product, code, ip) {
  const res = await checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
    method: "POST",
    headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip },
    body: JSON.stringify({ product, ...(code ? { code } : {}) }),
  }));
  const sent = calls.find((c) => c.url.startsWith("https://api.stripe.com/v1/checkout/sessions"));
  return { res, form: sent ? new URLSearchParams(sent.opts.body) : null };
}

test("checkout applies a valid code as the only discount", async () => {
  stripeReply = () => new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
  await seed("PL-23456789", {});
  const { res, form } = await buy("keyfeel", "PL-23456789", "203.0.113.70");
  assert.equal(res.status, 200);
  assert.equal(form.get("discounts[0][coupon]"), "xs-pl-23456789");
  assert.equal(form.get("metadata[buyer_code]"), "PL-23456789");
  assert.equal(form.get("allow_promotion_codes"), null, "a coupon replaces the promotion-code box");
});

test("checkout without a code keeps the promotion-code box", async () => {
  stripeReply = () => new Response(JSON.stringify({ id: "cs_test_2", url: "https://checkout.stripe.com/pay/cs_test_2" }), { status: 200 });
  const { res, form } = await buy("keyfeel", "", "203.0.113.71");
  assert.equal(res.status, 200);
  assert.equal(form.get("discounts[0][coupon]"), null);
  assert.equal(form.get("metadata[buyer_code]"), null);
});

test("checkout refuses a code that does not apply, with the reason, and never calls Stripe", async () => {
  await seed("PL-23456789", {});
  const { res, form } = await buy("legroom", "PL-23456789", "203.0.113.72");
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.equal(body.error, "code_not_valid");
  assert.match(body.detail, /different product.*Press the button again to buy at the full price/);
  assert.equal(form, null);
});

test("checkout turns a Stripe coupon error into code_not_valid", async () => {
  stripeReply = () => new Response(JSON.stringify({ error: { code: "resource_missing", param: "discounts[0][coupon]", message: "No such coupon" } }), { status: 400 });
  await seed("PL-23456789", {});
  const { res } = await buy("keyfeel", "PL-23456789", "203.0.113.73");
  assert.equal(res.status, 400);
  assert.equal((await res.json()).error, "code_not_valid");
});

// ---- the webhook ----

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
  data: { object: { id: `cs_live_${product.replace(/-/g, "")}_abcdefg1`, status: "complete", payment_status: "paid", mode: "payment",
    amount_total: 999, total_details: { amount_discount: 0 }, customer_details: { email: "buyer@example.com" },
    metadata: { product }, ...obj } },
});
const mailOf = () => JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);

test("a paid app order makes a coupon and puts the code in the purchase email", async () => {
  const res = await webhook(signed(completed("legroom", "evt_xs1")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  assert.equal(calls.filter((c) => c.url === "https://api.stripe.com/v1/coupons").length, 1);
  const code = makeCode("cs_live_legroom_abcdefg1", env.STRIPE_WEBHOOK_SECRET);
  const mail = mailOf();
  assert.match(mail.text, new RegExp(`${code} takes 30% off one other Purplelink product`));
  assert.match(mail.html, new RegExp(`products/\\?code=${code}`));
  assert.equal(await memStore().get("session/cs_live_legroom_abcdefg1"), code);
});

test("a discounted order earns no code, and an order that used a code marks it used", async () => {
  await seed("PL-23456789", {});
  await webhook(signed(completed("keyfeel", "evt_xs2", { total_details: { amount_discount: 300 }, metadata: { product: "keyfeel", buyer_code: "PL-23456789" } })));
  assert.equal(calls.filter((c) => c.url === "https://api.stripe.com/v1/coupons").length, 0);
  assert.doesNotMatch(mailOf().text, /takes 30% off/);
  assert.equal(JSON.parse(await memStore().get("code/PL-23456789")).used, "cs_live_keyfeel_abcdefg1");
});

test("a failed coupon never blocks delivery", async () => {
  stripeReply = () => new Response(JSON.stringify({ error: { code: "api_error" } }), { status: 500 });
  const res = await webhook(signed(completed("legroom", "evt_xs3")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = mailOf();
  assert.match(mail.text, /legroom\/success\//);
  assert.doesNotMatch(mail.text, /takes 30% off/);
});

test("a Modal-delivered order passes the code and its date to the backend", async () => {
  const res = await webhook(signed(completed("paper-review-standard", "evt_xs4", { amount_total: 900 })));
  assert.ok(res.status < 500);
  const modal = calls.find((c) => /modal\.run/.test(c.url) && c.opts.body && String(c.opts.body).includes("buyer_code"));
  assert.ok(modal, "the backend payload carries buyer_code");
  const payload = JSON.parse(modal.opts.body);
  assert.match(payload.buyer_code, lib.CODE_RE);
  assert.match(payload.buyer_code_expires, /^[A-Z][a-z]+ \d{1,2}, \d{4}$/);
});
