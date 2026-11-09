// Paper Review annual plan (Part D): the Stripe webhook's forwarding to Modal, the plan page function, and
// the checkout session. Stripe, Modal, Resend and Blobs are all stubbed; nothing touches the network.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/paper-review-annual.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    list: async () => { throw new Error("digest subscriber list must not be read for an annual plan"); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {
  STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", STRIPE_SECRET_KEY: "sk_test_dummy",
  RESEND_API_KEY: "re_dummy", ALERT_EMAIL_TO: "ops@example.com",
};
globalThis.Netlify = { env: { get: (k) => env[k] } };
Object.assign(process.env, { BACKEND_WEBHOOK_SECRET: "backend" });
const { default: webhook } = await import("../functions/stripe-webhook.mjs");
const { default: plan } = await import("../functions/paper-review-plan.mjs");
const { default: checkout } = await import("../functions/checkout.mjs");

const MODAL = "https://ben-ampel--purplelink-latextools-web.modal.run";
const MODAL_HOST = new URL(MODAL).hostname;
let calls;       // every fetch
let stripeData;  // path -> object served for GET api.stripe.com
let modalReply;  // path -> {status, body}

beforeEach(() => {
  store.clear();
  calls = [];
  stripeData = {};
  modalReply = {};
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    const host = new URL(u).hostname;
    if (host === "api.stripe.com") {
      const path = new URL(u).pathname;
      if (stripeData[path]) return new Response(JSON.stringify(stripeData[path]), { status: 200 });
      return new Response("{}", { status: 404 });
    }
    if (host === MODAL_HOST) {
      const path = new URL(u).pathname;
      const r = modalReply[path] || { status: 200, body: { ok: true } };
      return new Response(JSON.stringify(r.body), { status: r.status });
    }
    return new Response("{}", { status: 200 });
  };
});

const modalCalls = () => calls.filter((c) => new URL(c.url).hostname === MODAL_HOST).map((c) => ({ path: new URL(c.url).pathname, body: JSON.parse(c.opts.body), headers: c.opts.headers }));

function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", {
    method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body,
  });
}

const PERIOD_END = 1830000000;
const annualSub = (extra = {}) => ({
  id: "sub_1", status: "active", cancel_at_period_end: false, metadata: { product: "paper-review-annual" },
  items: { data: [{ current_period_end: PERIOD_END }] }, ...extra,
});

// ---------------------------------------------------------------------------------------------- checkout.session

const completed = (extra = {}) => ({
  id: "evt_c", type: "checkout.session.completed",
  data: { object: { id: "cs_live_annual1", status: "complete", payment_status: "paid", amount_total: 7900, amount_subtotal: 7900,
    customer: "cus_1", subscription: "sub_1", customer_details: { email: "buyer@example.com" },
    metadata: { product: "paper-review-annual", referral_code: "ref1" }, ...extra } },
});

test("an annual checkout forwards the subscription, the paid-through date and the card fingerprint", async () => {
  stripeData["/v1/subscriptions/sub_1"] = annualSub({ latest_invoice: { id: "in_1", charge: "ch_1" } });
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", payment_method_details: { card: { fingerprint: "fp_abc" } } };
  const res = await webhook(signed(completed()));
  assert.equal(res.status, 200);
  const [reg] = modalCalls();
  assert.equal(reg.path, "/paper-review/register-token");
  assert.equal(reg.headers["x-webhook-secret"], "backend");
  assert.equal(reg.body.product, "paper-review-annual");
  assert.equal(reg.body.subscription_id, "sub_1");
  assert.equal(reg.body.term_ends_at, PERIOD_END);
  assert.equal(reg.body.customer, "cus_1");
  assert.equal(reg.body.card_fingerprint, "fp_abc");
  assert.equal(reg.body.invoice_id, "in_1");
  assert.equal(reg.body.referral_code, "ref1");
});

test("an annual checkout whose subscription cannot be read is retried, not registered", async () => {
  const res = await webhook(signed(completed()));
  assert.equal(res.status, 502);
  assert.equal(modalCalls().length, 0);
});

test("a one-off Paper Review order carries no subscription fields", async () => {
  const ev = completed({ subscription: null, metadata: { product: "paper-review-standard" }, amount_total: 900, amount_subtotal: 900 });
  await webhook(signed(ev));
  const [reg] = modalCalls();
  assert.equal(reg.body.subscription_id, undefined);
});

// ---------------------------------------------------------------------------------------------- invoice.paid

const invoicePaid = (reason, sub = "sub_1") => ({
  id: "evt_i", type: "invoice.paid", data: { object: { id: "in_2", billing_reason: reason, subscription: sub } },
});

test("a renewal invoice asks Modal to renew the plan", async () => {
  stripeData["/v1/subscriptions/sub_1"] = annualSub();
  const res = await webhook(signed(invoicePaid("subscription_cycle")));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/paper-review/annual-renew", { subscription_id: "sub_1" }]]);
});

test("the first invoice is not a renewal", async () => {
  const res = await webhook(signed(invoicePaid("subscription_create")));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

test("a renewal invoice for another product is ignored", async () => {
  stripeData["/v1/subscriptions/sub_1"] = annualSub({ metadata: { product: "digest-monthly" } });
  const res = await webhook(signed(invoicePaid("subscription_cycle")));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

test("the newer invoice shape (parent.subscription_details) is read too", async () => {
  stripeData["/v1/subscriptions/sub_9"] = annualSub({ id: "sub_9" });
  const ev = { id: "evt_i2", type: "invoice.paid", data: { object: { id: "in_3", billing_reason: "subscription_cycle", parent: { subscription_details: { subscription: "sub_9" } } } } };
  await webhook(signed(ev));
  assert.equal(modalCalls()[0].body.subscription_id, "sub_9");
});

test("a renewal that Modal fails is retried", async () => {
  stripeData["/v1/subscriptions/sub_1"] = annualSub();
  modalReply["/paper-review/annual-renew"] = { status: 502, body: { error: "stripe" } };
  const res = await webhook(signed(invoicePaid("subscription_cycle")));
  assert.equal(res.status, 502);
});

// ---------------------------------------------------------------------------------------------- subscription.updated

const updated = (sub) => ({ id: "evt_u", type: "customer.subscription.updated", data: { object: sub } });

test("a cancel in the Stripe portal is forwarded as cancel_at_period_end", async () => {
  const res = await webhook(signed(updated(annualSub({ cancel_at_period_end: true }))));
  assert.equal(res.status, 200);
  const [c] = modalCalls();
  assert.equal(c.path, "/paper-review/annual-status");
  assert.equal(c.body.subscription_id, "sub_1");
  assert.equal(c.body.cancel_at_period_end, true);
  assert.equal(c.body.status, "active");
  assert.equal(c.body.current_period_end, PERIOD_END);
});

test("an undo in the portal clears the mark", async () => {
  await webhook(signed(updated(annualSub({ cancel_at_period_end: false }))));
  assert.equal(modalCalls()[0].body.cancel_at_period_end, false);
});

test("a subscription for another product is ignored", async () => {
  const res = await webhook(signed(updated(annualSub({ metadata: { product: "digest-monthly" }, cancel_at_period_end: true }))));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

test("a past_due status is forwarded as a status only, never as a renewal", async () => {
  await webhook(signed(updated(annualSub({ status: "past_due" }))));
  const calls_ = modalCalls();
  assert.equal(calls_.length, 1);
  assert.equal(calls_[0].path, "/paper-review/annual-status");
  assert.equal(calls_[0].body.status, "past_due");
});

test("a Modal failure on a status change is retried", async () => {
  modalReply["/paper-review/annual-status"] = { status: 500, body: {} };
  const res = await webhook(signed(updated(annualSub({ cancel_at_period_end: true }))));
  assert.equal(res.status, 502);
});

test("a deleted annual subscription is recorded as canceled and skips the digest lookup", async () => {
  const ev = { id: "evt_d", type: "customer.subscription.deleted", data: { object: annualSub({ status: "canceled" }) } };
  const res = await webhook(signed(ev));
  assert.equal(res.status, 200);
  const [c] = modalCalls();
  assert.equal(c.path, "/paper-review/annual-status");
  assert.equal(c.body.status, "canceled");
});

// ---------------------------------------------------------------------------------------------- refunds, disputes

test("a full refund of an annual invoice revokes the plan", async () => {
  stripeData["/v1/invoices/in_1"] = { id: "in_1", subscription: "sub_1" };
  stripeData["/v1/subscriptions/sub_1"] = annualSub();
  const ev = { id: "evt_r", type: "charge.refunded", data: { object: { id: "ch_1", invoice: "in_1", payment_intent: "pi_1", amount: 7900, amount_refunded: 7900, refunded: true } } };
  const res = await webhook(signed(ev));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/paper-review/annual-revoke", { subscription_id: "sub_1", reason: "refund" }]]);
});

test("a partial refund leaves the plan alone", async () => {
  const ev = { id: "evt_r2", type: "charge.refunded", data: { object: { id: "ch_1", invoice: "in_1", payment_intent: "pi_1", amount: 7900, amount_refunded: 1000, refunded: false } } };
  await webhook(signed(ev));
  assert.equal(modalCalls().length, 0);
});

test("a refund of an ordinary charge does not call Modal", async () => {
  const ev = { id: "evt_r3", type: "charge.refunded", data: { object: { id: "ch_9", payment_intent: "pi_9", amount: 900, amount_refunded: 900, refunded: true } } };
  stripeData["/v1/invoice_payments"] = { data: [] };
  const res = await webhook(signed(ev));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

test("a refund of another product's subscription invoice does not call Modal", async () => {
  stripeData["/v1/invoices/in_5"] = { id: "in_5", subscription: "sub_5" };
  stripeData["/v1/subscriptions/sub_5"] = annualSub({ id: "sub_5", metadata: { product: "digest-monthly" } });
  const ev = { id: "evt_r4", type: "charge.refunded", data: { object: { id: "ch_5", invoice: "in_5", payment_intent: "pi_5", amount: 500, amount_refunded: 500, refunded: true } } };
  await webhook(signed(ev));
  assert.equal(modalCalls().length, 0);
});

test("a dispute on an annual invoice revokes the plan", async () => {
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", invoice: "in_1", payment_intent: "pi_1" };
  stripeData["/v1/invoices/in_1"] = { id: "in_1", subscription: "sub_1" };
  stripeData["/v1/subscriptions/sub_1"] = annualSub();
  const ev = { id: "evt_dp", type: "charge.dispute.created", data: { object: { id: "dp_1", charge: "ch_1", payment_intent: "pi_1" } } };
  const res = await webhook(signed(ev));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body.reason]), [["/paper-review/annual-revoke", "dispute"]]);
});

test("a dispute revoke carries the dispute id", async () => {
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", invoice: "in_1", payment_intent: "pi_1" };
  stripeData["/v1/invoices/in_1"] = { id: "in_1", subscription: "sub_1" };
  stripeData["/v1/subscriptions/sub_1"] = annualSub();
  const ev = { id: "evt_dp2", type: "charge.dispute.created", data: { object: { id: "dp_7", charge: "ch_1", payment_intent: "pi_1" } } };
  await webhook(signed(ev));
  assert.equal(modalCalls()[0].body.dispute_id, "dp_7");
});

test("a won dispute on an annual invoice restores the plan", async () => {
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", invoice: "in_1", payment_intent: "pi_1" };
  stripeData["/v1/invoices/in_1"] = { id: "in_1", subscription: "sub_1" };
  stripeData["/v1/subscriptions/sub_1"] = annualSub();
  const ev = { id: "evt_dw", type: "charge.dispute.closed", data: { object: { id: "dp_1", charge: "ch_1", payment_intent: "pi_1", status: "won" } } };
  const res = await webhook(signed(ev));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/paper-review/annual-restore", { subscription_id: "sub_1", dispute_id: "dp_1" }]]);
});

test("a lost dispute on an annual invoice leaves the plan revoked", async () => {
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", invoice: "in_1", payment_intent: "pi_1" };
  const ev = { id: "evt_dl", type: "charge.dispute.closed", data: { object: { id: "dp_1", charge: "ch_1", payment_intent: "pi_1", status: "lost" } } };
  const res = await webhook(signed(ev));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

test("a won dispute on an ordinary charge does not call Modal", async () => {
  stripeData["/v1/charges/ch_9"] = { id: "ch_9", payment_intent: "pi_9" };
  stripeData["/v1/invoice_payments"] = { data: [] };
  const ev = { id: "evt_dw9", type: "charge.dispute.closed", data: { object: { id: "dp_9", charge: "ch_9", payment_intent: "pi_9", status: "won" } } };
  const res = await webhook(signed(ev));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

// ---------------------------------------------------------------------------------------------- plan page

const planReq = (method, { query = "", form } = {}) => new Request(`https://purplelink.llc/tools/paper-review/plan/${query}`, {
  method,
  headers: { "x-nf-client-connection-ip": `198.51.100.${Math.floor(Math.random() * 200)}`, "content-type": "application/x-www-form-urlencoded" },
  body: form ? new URLSearchParams(form).toString() : undefined,
});
const view = (state, extra = {}) => ({ state, date: "June 1, 2027", amount: "$79", unused: 9, total: 12, ...extra });

test("opening the plan link shows the plan and changes nothing", async () => {
  modalReply["/paper-review/annual-plan"] = { status: 200, body: view("active") };
  const res = await plan(planReq("GET", { query: "?t=tok1" }));
  assert.equal(res.status, 200);
  const html = await res.text();
  assert.match(html, /renews on June 1, 2027 for \$79/);
  assert.match(html, /9 of 12 reviews unused/);
  assert.match(html, /name="action" value="cancel"/);
  assert.deepEqual(modalCalls().map((c) => c.path), ["/paper-review/annual-plan"]);
  assert.equal(res.headers.get("x-robots-tag"), "noindex");
});

test("cancel is a POST and relays the link, then shows the new state with the replacement link", async () => {
  modalReply["/paper-review/annual-cancel"] = { status: 200, body: view("cancelling", { token: "tok2" }) };
  const res = await plan(planReq("POST", { form: { action: "cancel", t: "tok1" } }));
  assert.equal(res.status, 200);
  const html = await res.text();
  assert.match(html, /will not renew/);
  assert.match(html, /name="t" value="tok2"/);
  assert.match(html, /name="action" value="undo"/);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/paper-review/annual-cancel", { token: "tok1" }]]);
});

test("undo restores renewal", async () => {
  modalReply["/paper-review/annual-undo"] = { status: 200, body: view("active", { token: "tok3" }) };
  const res = await plan(planReq("POST", { form: { action: "undo", t: "tok2" } }));
  assert.match(await res.text(), /renew again/);
  assert.equal(modalCalls()[0].path, "/paper-review/annual-undo");
});

test("an invalid or replaced link shows the email box, not the plan", async () => {
  modalReply["/paper-review/annual-plan"] = { status: 410, body: { error: "replaced" } };
  const html = await (await plan(planReq("GET", { query: "?t=old" }))).text();
  assert.match(html, /replaced by a newer one/);
  assert.match(html, /name="email"/);
  modalReply["/paper-review/annual-plan"] = { status: 404, body: { error: "invalid" } };
  assert.match(await (await plan(planReq("GET", { query: "?t=bad" }))).text(), /expired or is not valid/);
});

test("a failed cancel says nothing was changed", async () => {
  modalReply["/paper-review/annual-cancel"] = { status: 502, body: { error: "stripe_failed" } };
  const res = await plan(planReq("POST", { form: { action: "cancel", t: "tok1" } }));
  assert.equal(res.status, 502);
  assert.match(await res.text(), /Nothing was changed/);
});

test("a PUT or DELETE is refused", async () => {
  assert.equal((await plan(planReq("DELETE"))).status, 405);
});

test("asking for a link gives the same answer whether or not a plan exists", async () => {
  const a = await plan(planReq("POST", { form: { action: "link", email: "has-plan@example.com" } }));
  const b = await plan(planReq("POST", { form: { action: "link", email: "no-plan@example.com" } }));
  assert.equal(a.status, 200);
  assert.equal(b.status, 200);
  const norm = async (r, e) => (await r.text()).replace(e, "EMAIL");
  assert.equal(await norm(a, "has-plan@example.com"), await norm(b, "no-plan@example.com"));
});

test("an address is limited to three link requests a day", async () => {
  const codes = [];
  for (let i = 0; i < 4; i++) {
    codes.push((await plan(planReq("POST", { form: { action: "link", email: "limit@example.com" } }))).status);
  }
  assert.deepEqual(codes, [200, 200, 200, 429]);
});

test("a malformed address is rejected before any lookup", async () => {
  const res = await plan(planReq("POST", { form: { action: "link", email: "not-an-email" } }));
  assert.match(await res.text(), /does not look like an email/);
  assert.equal(modalCalls().length, 0);
});

// ---------------------------------------------------------------------------------------------- checkout

async function annualCheckout(priceEnv) {
  const saved = { ...env };
  env.STRIPE_PRICE_PAPER_REVIEW_ANNUAL = priceEnv;
  let body = null;
  globalThis.fetch = async (url, opts) => {
    if (new URL(String(url)).hostname === "api.stripe.com") {
      body = new URLSearchParams(opts.body);
      return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/c/pay/cs_test_1" }), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  };
  const res = await checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
    method: "POST", headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.77", origin: "https://purplelink.llc" },
    body: JSON.stringify({ product: "paper-review-annual" }),
  }));
  for (const k of Object.keys(env)) delete env[k];
  Object.assign(env, saved);
  return { res, body };
}

test("annual checkout uses the configured Stripe Price and asks for terms consent", async () => {
  const { res, body } = await annualCheckout("price_1UYByUJkzNxf3fKqUtZInNif");
  assert.equal(res.status, 200);
  assert.equal(body.get("mode"), "subscription");
  assert.equal(body.get("line_items[0][price]"), "price_1UYByUJkzNxf3fKqUtZInNif");
  assert.equal(body.get("consent_collection[terms_of_service]"), "required");
  assert.match(body.get("custom_text[submit][message]") || "", /Renews at \$79 a year/);
  assert.equal(body.get("metadata[product]"), "paper-review-annual");
  assert.equal(body.get("subscription_data[metadata][product]"), "paper-review-annual");
});

test("annual checkout falls back to an inline $79 yearly price when no Price is set", async () => {
  const { res, body } = await annualCheckout(undefined);
  assert.equal(res.status, 200);
  assert.equal(body.get("line_items[0][price_data][unit_amount]"), "7900");
  assert.equal(body.get("line_items[0][price_data][recurring][interval]"), "year");
  assert.equal(body.get("line_items[0][price]"), null);
});
