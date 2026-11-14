// Lab plans (Netlify side): the Stripe webhook branches, the plan page (/labs/plan/) and the group page
// (/labs/start/). Stripe, Modal, Resend and Blobs are all stubbed; nothing touches the network.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/lab-plans.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const store = new Map();
let listCalls = 0;
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
    list: async () => { listCalls += 1; return { blobs: [], cursor: undefined }; },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {
  STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", STRIPE_SECRET_KEY: "sk_test_dummy",
  RESEND_API_KEY: "re_dummy", ALERT_EMAIL_TO: "ops@example.com",
};
globalThis.Netlify = { env: { get: (k) => env[k] } };
Object.assign(process.env, {
  BACKEND_WEBHOOK_SECRET: "backend", STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_PORTAL_CONFIG_SUBSCRIPTIONS: "bpc_test",
});
const { default: webhook, LAB_PRODUCTS } = await import("../functions/stripe-webhook.mjs");
const { default: plan } = await import("../functions/lab-plan.mjs");
const { default: start } = await import("../functions/lab-start.mjs");
const { page } = await import("../lib/fn-page.mjs");

const MODAL_HOST = new URL("https://ben-ampel--purplelink-latextools-web.modal.run").hostname;
let calls;
let stripeData;   // "path?query" or "path" -> object served for GET api.stripe.com
let stripeStatus; // path -> HTTP status forced for GET api.stripe.com (a failed read)
let modalReply;   // path -> {status, body} or an Error to throw
let portalUrl;    // what a stripe billing portal session POST answers

beforeEach(() => {
  store.clear();
  listCalls = 0;
  calls = [];
  stripeData = {};
  stripeStatus = {};
  modalReply = {};
  portalUrl = "https://billing.stripe.com/p/session/test_1";
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    const parsed = new URL(u);
    if (parsed.hostname === "api.stripe.com") {
      if ((opts.method || "GET") === "POST") {
        if (portalUrl === null) return new Response("{}", { status: 400 });
        return new Response(JSON.stringify({ url: portalUrl }), { status: 200 });
      }
      const forced = stripeStatus[parsed.pathname];
      if (forced) return new Response("{}", { status: forced });
      const data = stripeData[parsed.pathname + parsed.search] ?? stripeData[parsed.pathname];
      return data ? new Response(JSON.stringify(data), { status: 200 }) : new Response("{}", { status: 404 });
    }
    if (parsed.hostname === MODAL_HOST) {
      const r = modalReply[parsed.pathname] || { status: 200, body: { ok: true } };
      if (r instanceof Error) throw r;
      return new Response(JSON.stringify(r.body), { status: r.status });
    }
    return new Response("{}", { status: 200 });
  };
});

const modalCalls = () => calls.filter((c) => new URL(c.url).hostname === MODAL_HOST)
  .map((c) => ({ path: new URL(c.url).pathname, body: JSON.parse(c.opts.body), headers: c.opts.headers }));
const alerts = () => calls.filter((c) => c.url === "https://api.resend.com/emails").map((c) => JSON.parse(c.opts.body));
const stripeReads = () => calls.filter((c) => new URL(c.url).hostname === "api.stripe.com");

function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", {
    method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body,
  });
}

const labSub = (extra = {}) => ({ id: "sub_lab", status: "active", metadata: { product: "lab-plus-monthly" }, ...extra });

// ------------------------------------------------------------------------------------- checkout.session.completed

const completed = (extra = {}, meta = {}) => ({
  id: "evt_c", type: "checkout.session.completed",
  data: { object: { id: "cs_live_lab1", status: "complete", payment_status: "paid", amount_total: 39900, amount_subtotal: 39900,
    customer: "cus_lab", subscription: "sub_lab", customer_details: { email: "lead@example.com" },
    metadata: { product: "lab-plus-monthly", referral_code: "ref1", ...meta }, ...extra } },
});

test("all four lab keys are lab products", () => {
  assert.deepEqual([...LAB_PRODUCTS].sort(), ["lab-annual", "lab-monthly", "lab-plus-annual", "lab-plus-monthly"]);
});

test("a paid lab checkout registers the plan with Modal and nothing else", async () => {
  const res = await webhook(signed(completed()));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "registered", session_id: "cs_live_lab1" });
  const mc = modalCalls();
  assert.equal(mc.length, 1, "no register-token, no referral, no buyer code");
  assert.equal(mc[0].path, "/lab/register");
  assert.equal(mc[0].headers["x-webhook-secret"], "backend");
  assert.deepEqual(mc[0].body, {
    session_id: "cs_live_lab1", subscription_id: "sub_lab", product: "lab-plus-monthly", email: "lead@example.com",
    amount_paid: 39900, amount_subtotal: 39900, customer: "cus_lab",
  });
  assert.equal(stripeReads().length, 0);
});

test("a lab checkout paid with a promotion code (amount_subtotal kept) still registers", async () => {
  const res = await webhook(signed(completed({ amount_total: 0, amount_subtotal: 19900, payment_status: "no_payment_required", subscription: { id: "sub_x" } }, { product: "lab-monthly" })));
  assert.equal(res.status, 200);
  const [reg] = modalCalls();
  assert.equal(reg.body.subscription_id, "sub_x");
  assert.equal(reg.body.amount_paid, 0);
  assert.equal(reg.body.amount_subtotal, 19900);
});

test("an unpaid lab checkout is not registered", async () => {
  const res = await webhook(signed(completed({ payment_status: "unpaid" })));
  assert.equal((await res.json()).status, "not_paid");
  assert.equal(modalCalls().length, 0);
});

test("a lab register that Modal rejects alerts the operator and is retried", async () => {
  modalReply["/lab/register"] = { status: 409, body: { error: "unpaid" } };
  const res = await webhook(signed(completed()));
  assert.equal(res.status, 502);
  assert.equal(alerts().length, 1);
  assert.match(alerts()[0].subject, /lab register failed/i);
  assert.match(alerts()[0].text, /cs_live_lab1/);
});

test("a lab register that cannot reach Modal alerts the operator and is retried", async () => {
  modalReply["/lab/register"] = new Error("connect refused");
  const res = await webhook(signed(completed()));
  assert.equal(res.status, 502);
  assert.equal(alerts().length, 1);
});

test("a lab checkout with no subscription is retried and alerted", async () => {
  const res = await webhook(signed(completed({ subscription: null })));
  assert.equal(res.status, 502);
  assert.equal(modalCalls().length, 0);
  assert.equal(alerts().length, 1);
});

// ------------------------------------------------------------------------------------- subscription events

const subEvent = (type, sub) => ({ id: "evt_s", type, data: { object: sub } });

test("a lab subscription update asks Modal to sync, and never touches the digest store", async () => {
  const res = await webhook(signed(subEvent("customer.subscription.updated", labSub({ cancel_at_period_end: true }))));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/lab/sync", { subscription_id: "sub_lab" }]]);
  assert.equal(listCalls, 0);
});

test("a deleted lab subscription asks Modal to sync, and skips the digest lookup", async () => {
  const res = await webhook(signed(subEvent("customer.subscription.deleted", labSub({ status: "canceled" }))));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => c.path), ["/lab/sync"]);
  assert.equal(listCalls, 0);
});

test("a lab sync that Modal fails is retried and alerted", async () => {
  modalReply["/lab/sync"] = { status: 502, body: { error: "stripe_unreadable" } };
  const res = await webhook(signed(subEvent("customer.subscription.updated", labSub())));
  assert.equal(res.status, 502);
  assert.equal(alerts().length, 1);
});

// ------------------------------------------------------------------------------------- invoice.paid

const invoice = (reason, extra = {}) => ({
  id: "evt_i", type: "invoice.paid",
  data: { object: { id: "in_1", billing_reason: reason, subscription: "sub_lab", customer: "cus_lab", customer_email: "inv@example.com", ...extra } },
});

test("a lab renewal invoice syncs; the product comes from the invoice snapshot with no Stripe read", async () => {
  const snap = { parent: { subscription_details: { subscription: "sub_lab", metadata: { product: "lab-annual" } } } };
  const res = await webhook(signed(invoice("subscription_cycle", { subscription: undefined, ...snap })));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/lab/sync", { subscription_id: "sub_lab" }]]);
  assert.equal(stripeReads().length, 0);
});

test("the older snapshot shape (subscription_details) is read too", async () => {
  const res = await webhook(signed(invoice("subscription_update", { subscription_details: { metadata: { product: "lab-monthly" } } })));
  assert.equal(res.status, 200);
  assert.equal(modalCalls()[0].path, "/lab/sync");
});

test("without a snapshot the subscription is read, and a lab cycle syncs", async () => {
  stripeData["/v1/subscriptions/sub_lab"] = labSub();
  const res = await webhook(signed(invoice("subscription_cycle")));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => c.path), ["/lab/sync"]);
});

test("a lab invoice sync that Modal fails is retried", async () => {
  stripeData["/v1/subscriptions/sub_lab"] = labSub();
  modalReply["/lab/sync"] = { status: 500, body: {} };
  const res = await webhook(signed(invoice("subscription_cycle")));
  assert.equal(res.status, 502);
  assert.equal(alerts().length, 1);
});

test("a lab first invoice with a Checkout session waits for the completed-session event", async () => {
  stripeData["/v1/subscriptions/sub_lab"] = labSub();
  stripeData["/v1/checkout/sessions?subscription=sub_lab&limit=1"] = { data: [{ id: "cs_1" }] };
  const res = await webhook(signed(invoice("subscription_create")));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "ignored_checkout_plan");
  assert.equal(modalCalls().length, 0);
});

test("a lab first invoice with no Checkout session (a Dashboard invoice plan) registers the plan", async () => {
  stripeData["/v1/subscriptions/sub_lab"] = labSub();
  stripeData["/v1/checkout/sessions?subscription=sub_lab&limit=1"] = { data: [] };
  const res = await webhook(signed(invoice("subscription_create")));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [
    ["/lab/register", { subscription_id: "sub_lab", product: "lab-plus-monthly", email: "inv@example.com", customer: "cus_lab" }],
  ]);
});

test("an invoice plan whose register fails is alerted and retried", async () => {
  stripeData["/v1/subscriptions/sub_lab"] = labSub();
  stripeData["/v1/checkout/sessions?subscription=sub_lab&limit=1"] = { data: [] };
  modalReply["/lab/register"] = { status: 502, body: { error: "stripe_unreadable" } };
  const res = await webhook(signed(invoice("subscription_create")));
  assert.equal(res.status, 502);
  assert.equal(alerts().length, 1);
});

test("a lab first invoice whose session lookup fails is retried, not registered", async () => {
  stripeData["/v1/subscriptions/sub_lab"] = labSub();
  const res = await webhook(signed(invoice("subscription_create")));
  assert.equal(res.status, 502);
  assert.equal(modalCalls().length, 0);
});

test("other billing reasons on a lab invoice are ignored", async () => {
  const res = await webhook(signed(invoice("manual")));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

// ------------------------------------------------------------------------------------- refunds and disputes

const refunded = (charge = {}) => ({ id: "evt_r", type: "charge.refunded", data: { object: {
  id: "ch_1", invoice: "in_1", payment_intent: "pi_1", amount: 39900, amount_refunded: 39900, refunded: true, ...charge } } });
const dispute = (type, extra = {}) => ({ id: "evt_d", type, data: { object: { id: "dp_1", charge: "ch_1", payment_intent: "pi_1", ...extra } } });

function labCharge() {
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", invoice: "in_1", payment_intent: "pi_1" };
  stripeData["/v1/invoices/in_1"] = { id: "in_1", subscription: "sub_lab" };
  stripeData["/v1/subscriptions/sub_lab"] = labSub();
  stripeData["/v1/checkout/sessions?payment_intent=pi_1&limit=1"] = { data: [] };
}
function orderCharge(product = "paper-review-deep") {
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", payment_intent: "pi_1" };
  stripeData["/v1/invoice_payments"] = { data: [] };
  stripeData["/v1/checkout/sessions?payment_intent=pi_1&limit=1"] = { data: [{ id: "cs_order1", metadata: { product } }] };
}

test("a full refund of a lab invoice revokes the plan", async () => {
  labCharge();
  const res = await webhook(signed(refunded()));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "refund_recorded");
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/lab/revoke", { subscription_id: "sub_lab", reason: "refund" }]]);
});

test("a lab revoke that Modal fails is retried and alerted", async () => {
  labCharge();
  modalReply["/lab/revoke"] = { status: 500, body: {} };
  const res = await webhook(signed(refunded()));
  assert.equal(res.status, 502);
  assert.equal(alerts().length, 1);
});

test("a dispute on a lab invoice revokes the plan with the dispute id", async () => {
  labCharge();
  const res = await webhook(signed(dispute("charge.dispute.created")));
  assert.equal(res.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/lab/revoke", { subscription_id: "sub_lab", reason: "dispute", dispute_id: "dp_1" }]]);
});

test("a won dispute on a lab invoice restores the plan; a lost one does not", async () => {
  labCharge();
  const won = await webhook(signed(dispute("charge.dispute.closed", { status: "won" })));
  assert.equal(won.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/lab/restore", { subscription_id: "sub_lab", dispute_id: "dp_1" }]]);
  calls.length = 0;
  const lost = await webhook(signed(dispute("charge.dispute.closed", { status: "lost" })));
  assert.equal(lost.status, 200);
  assert.equal(modalCalls().length, 0);
});

test("a lab restore that Modal fails is retried", async () => {
  labCharge();
  modalReply["/lab/restore"] = { status: 500, body: {} };
  const res = await webhook(signed(dispute("charge.dispute.closed", { status: "won" })));
  assert.equal(res.status, 502);
});

test("a partial refund of a lab invoice leaves the plan alone", async () => {
  labCharge();
  await webhook(signed(refunded({ amount_refunded: 1000, refunded: false })));
  assert.equal(modalCalls().length, 0);
});

test("a full refund of a one-time review order revokes that order", async () => {
  orderCharge();
  const res = await webhook(signed(refunded({ invoice: null })));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "refund_recorded");
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/paper-review/revoke-order", { session_id: "cs_order1", reason: "refund" }]]);
});

test("a dispute on a one-time order revokes it with the dispute id, and a won one restores it", async () => {
  orderCharge("publication-pack");
  const created = await webhook(signed(dispute("charge.dispute.created")));
  assert.equal(created.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/paper-review/revoke-order", { session_id: "cs_order1", reason: "dispute", dispute_id: "dp_1" }]]);
  calls.length = 0;
  const won = await webhook(signed(dispute("charge.dispute.closed", { status: "won" })));
  assert.equal(won.status, 200);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/paper-review/restore-order", { session_id: "cs_order1", dispute_id: "dp_1" }]]);
});

test("a partial refund of a one-time order, and a lost dispute on one, call no order route", async () => {
  orderCharge();
  await webhook(signed(refunded({ invoice: null, amount_refunded: 100, refunded: false })));
  await webhook(signed(dispute("charge.dispute.closed", { status: "lost" })));
  assert.equal(modalCalls().length, 0);
});

test("a failed lab revoke on a dispute is retried; an unreadable lab subscription on a renewal is alerted", async () => {
  labCharge();
  modalReply["/lab/revoke"] = { status: 500, body: {} };
  assert.equal((await webhook(signed(dispute("charge.dispute.created")))).status, 502);
  calls.length = 0;
  stripeData = {};
  const res = await webhook(signed(invoice("subscription_cycle")));
  assert.equal(res.status, 502);
  assert.equal(alerts().length, 1);
  assert.equal(modalCalls().length, 0);
});

test("a failed order call never blocks the refund bookkeeping or changes the answer, and alerts the operator", async () => {
  orderCharge();
  modalReply["/paper-review/revoke-order"] = { status: 500, body: {} };
  const res = await webhook(signed(refunded({ invoice: null })));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "refund_recorded", payment_intent: "pi_1" });
  assert.equal(alerts().length, 1);
  assert.ok([...store.keys()].some((k) => k.includes("pi_1")), "the revocation record was still written");
});

test("an order call that cannot reach Modal does not change a dispute answer", async () => {
  orderCharge();
  modalReply["/paper-review/revoke-order"] = new Error("down");
  const res = await webhook(signed(dispute("charge.dispute.created")));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "dispute_recorded");
});

test("a refund of an order Modal does not know (unknown_order) alerts, and the order is never registered later", async () => {
  orderCharge();
  modalReply["/paper-review/revoke-order"] = { status: 200, body: { ok: false, reason: "unknown_order" } };
  const res = await webhook(signed(refunded({ invoice: null })));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "refund_recorded");
  assert.equal(alerts().length, 1);
  assert.match(alerts()[0].subject, /unknown/i);
  calls.length = 0;
  const late = await webhook(signed(completed({ id: "cs_order1", subscription: null, payment_intent: "pi_1", amount_total: 3900, amount_subtotal: 3900 },
    { product: "paper-review-deep" })));
  assert.equal(late.status, 200);
  assert.equal((await late.json()).status, "refunded_before_register");
  assert.equal(modalCalls().length, 0, "no register-token, no referral");
  assert.equal(alerts().length, 1);
});

test("a dispute record does not stop an order from registering; a won-dispute restore of an unknown order does not alert", async () => {
  orderCharge();
  modalReply["/paper-review/revoke-order"] = { status: 200, body: { ok: false, reason: "unknown_order" } };
  modalReply["/paper-review/restore-order"] = { status: 200, body: { ok: false, reason: "unknown_order" } };
  await webhook(signed(dispute("charge.dispute.created")));
  calls.length = 0;
  await webhook(signed(dispute("charge.dispute.closed", { status: "won" })));
  assert.equal(alerts().length, 0);
  calls.length = 0;
  await webhook(signed(dispute("charge.dispute.created")));
  calls.length = 0;
  const res = await webhook(signed(completed({ id: "cs_order1", subscription: null, payment_intent: "pi_1", amount_total: 3900, amount_subtotal: 3900 },
    { product: "paper-review-deep" })));
  assert.equal(res.status, 200);
  assert.ok(modalCalls().some((c) => c.path === "/paper-review/register-token"));
});

test("a lab revoke Modal answers unknown_plan (refund before register) is alerted and retried", async () => {
  labCharge();
  modalReply["/lab/revoke"] = { status: 200, body: { ok: false, reason: "unknown_plan" } };
  const res = await webhook(signed(refunded()));
  assert.equal(res.status, 502);
  assert.equal(alerts().length, 1);
  assert.ok([...store.keys()].includes("refunds/pi:pi_1"), "the refund record is written before the retry");
});

test("a lab refund whose invoice cannot be read is retried and alerted, with the refund recorded", async () => {
  labCharge();
  stripeStatus["/v1/invoices/in_1"] = 500;
  const res = await webhook(signed(refunded()));
  assert.equal(res.status, 502);
  assert.equal((await res.json()).error, "stripe_unreadable");
  assert.equal(alerts().length, 1);
  assert.equal(modalCalls().length, 0);
  assert.ok([...store.keys()].includes("refunds/pi:pi_1"));
});

test("a refund whose subscription or invoice-payment lookup cannot be read is retried", async () => {
  labCharge();
  stripeStatus["/v1/subscriptions/sub_lab"] = 429;
  assert.equal((await webhook(signed(refunded()))).status, 502);
  stripeStatus = { "/v1/invoice_payments": 503 };
  assert.equal((await webhook(signed(refunded({ invoice: null })))).status, 502);
  assert.equal(modalCalls().length, 0);
});

test("a dispute whose charge cannot be read is retried and recorded; a won one is retried", async () => {
  labCharge();
  stripeStatus["/v1/charges/ch_1"] = 500;
  const created = await webhook(signed(dispute("charge.dispute.created")));
  assert.equal(created.status, 502);
  assert.ok([...store.keys()].includes("refunds/pi:pi_1"));
  const won = await webhook(signed(dispute("charge.dispute.closed", { status: "won" })));
  assert.equal(won.status, 502);
  assert.equal(alerts().length, 2);
  assert.equal(modalCalls().length, 0);
});

test("an order refund or dispute still revokes the order when the plan lookup keeps failing", async () => {
  orderCharge();
  stripeStatus["/v1/invoice_payments"] = 403;
  const res = await webhook(signed(refunded({ invoice: null })));
  assert.equal(res.status, 502);
  assert.equal((await res.json()).error, "stripe_unreadable");
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]),
    [["/paper-review/revoke-order", { session_id: "cs_order1", reason: "refund" }]]);
  calls = [];
  const created = await webhook(signed(dispute("charge.dispute.created")));
  assert.equal(created.status, 502);
  assert.deepEqual(modalCalls().map((c) => c.path), ["/paper-review/revoke-order"]);
  assert.equal(modalCalls()[0].body.dispute_id, "dp_1");
});

test("a charge Stripe has never heard of (404) is not a plan, and the refund is recorded as before", async () => {
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", payment_intent: "pi_1" };
  stripeData["/v1/checkout/sessions?payment_intent=pi_1&limit=1"] = { data: [{ id: "cs_x", metadata: { product: "legroom" } }] };
  const res = await webhook(signed(refunded({ invoice: null })));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "refund_recorded");
  assert.equal(alerts().length, 0);
});

test("a refund of a charge whose product is not a review order calls no order route", async () => {
  orderCharge("legroom");
  const res = await webhook(signed(refunded({ invoice: null })));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

test("an order lookup that fails alerts but still answers as before", async () => {
  stripeData["/v1/charges/ch_1"] = { id: "ch_1", payment_intent: "pi_1" };
  stripeData["/v1/invoice_payments"] = { data: [] };
  const res = await webhook(signed(refunded({ invoice: null })));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
  assert.equal(alerts().length, 1);
});

// ------------------------------------------------------------------------------------- unchanged behaviour

const annualSub = (extra = {}) => ({ id: "sub_a", status: "active", cancel_at_period_end: false, metadata: { product: "paper-review-annual" },
  items: { data: [{ current_period_end: 1830000000 }] }, ...extra });

test("annual: a renewal still renews, the first invoice and a plan update are still ignored", async () => {
  stripeData["/v1/subscriptions/sub_a"] = annualSub();
  const ev = (reason) => ({ id: "e", type: "invoice.paid", data: { object: { id: "in_a", billing_reason: reason, subscription: "sub_a" } } });
  assert.equal((await webhook(signed(ev("subscription_cycle")))).status, 200);
  assert.deepEqual(modalCalls().map((c) => c.path), ["/paper-review/annual-renew"]);
  calls.length = 0;
  assert.equal((await webhook(signed(ev("subscription_create")))).status, 200);
  assert.equal((await webhook(signed(ev("subscription_update")))).status, 200);
  assert.equal(modalCalls().length, 0);
});

test("annual: a status change and a refund still go to the annual routes", async () => {
  await webhook(signed(subEvent("customer.subscription.updated", annualSub({ cancel_at_period_end: true }))));
  assert.deepEqual(modalCalls().map((c) => c.path), ["/paper-review/annual-status"]);
  calls.length = 0;
  stripeData["/v1/invoices/in_a"] = { id: "in_a", subscription: "sub_a" };
  stripeData["/v1/subscriptions/sub_a"] = annualSub();
  await webhook(signed(refunded({ invoice: "in_a" })));
  assert.deepEqual(modalCalls().map((c) => c.path), ["/paper-review/annual-revoke"]);
});

test("a one-time Paper Review order still registers its token", async () => {
  const res = await webhook(signed(completed({ subscription: null, amount_total: 900, amount_subtotal: 900 }, { product: "paper-review-standard" })));
  assert.equal(res.status, 200);
  assert.ok(modalCalls().some((c) => c.path === "/paper-review/register-token"));
  assert.ok(!modalCalls().some((c) => c.path.startsWith("/lab/")));
});

test("a delayed payment that succeeds later registers the order; the earlier unpaid completion did not", async () => {
  const sess = { subscription: null, amount_total: 1400, amount_subtotal: 1400 };
  const first = await webhook(signed(completed({ ...sess, payment_status: "unpaid" }, { product: "paper-review-standard" })));
  assert.equal((await first.json()).status, "not_paid");
  assert.equal(modalCalls().length, 0);
  const later = { ...completed({ ...sess }, { product: "paper-review-standard" }), id: "evt_async", type: "checkout.session.async_payment_succeeded" };
  const res = await webhook(signed(later));
  assert.equal(res.status, 200);
  assert.ok(modalCalls().some((c) => c.path === "/paper-review/register-token"));
});

test("a delayed-payment success sends no second Vitae Plus or live-sheet email", async () => {
  const ev = (product) => ({ ...completed({ subscription: null }, { product }), id: `evt_${product}`, type: "checkout.session.async_payment_succeeded" });
  const v = await webhook(signed(ev("vitae-plus-monthly")));
  assert.equal(v.status, 200);
  assert.equal(alerts().length, 0, "no email to Resend");
  const l = await webhook(signed(ev("live-scholar")));
  assert.equal(l.status, 200);
  assert.equal((await l.json()).status, "async_payment_acknowledged");
  assert.equal(alerts().length, 0, "no live-sheet email to Resend");
  assert.equal(modalCalls().length, 0);
});

test("Vitae Plus and digest subscription events behave as before", async () => {
  const v = await webhook(signed(subEvent("customer.subscription.deleted", { id: "sub_v", metadata: { product: "vitae-plus-monthly" } })));
  assert.equal((await v.json()).status, "vitae_plus_acknowledged");
  assert.equal(listCalls, 0);
  const d = await webhook(signed(subEvent("customer.subscription.deleted", { id: "sub_d", metadata: { product: "digest-monthly" } })));
  assert.equal((await d.json()).status, "subscriber_not_found");
  assert.equal(listCalls, 1);
  const u = await webhook(signed(subEvent("customer.subscription.updated", { id: "sub_d", metadata: { product: "digest-monthly" } })));
  assert.equal((await u.json()).status, "ignored_foreign_product");
  assert.equal(modalCalls().length, 0);
});

test("a renewal invoice for another product is still ignored", async () => {
  stripeData["/v1/subscriptions/sub_d"] = { id: "sub_d", metadata: { product: "digest-monthly" } };
  const res = await webhook(signed({ id: "e", type: "invoice.paid", data: { object: { id: "in_d", billing_reason: "subscription_cycle", subscription: "sub_d" } } }));
  assert.equal(res.status, 200);
  assert.equal(modalCalls().length, 0);
});

// ------------------------------------------------------------------------------------- fn-page

test("page() adds only same-origin stylesheet paths", async () => {
  const html = await page("T", "H", "<p>x</p>", 200, { styles: ["/labs/plan.css", "https://evil.example/x.css", "//evil.example/x.css", '/a.css" onload="x'] }).text();
  assert.match(html, /href="\/labs\/plan\.css"/);
  assert.doesNotMatch(html, /evil\.example|onload/);
  const plain = await page("T", "H", "<p>x</p>").text();
  assert.equal((plain.match(/rel="stylesheet"/g) || []).length, 1);
});

// ------------------------------------------------------------------------------------- plan page

let ipCounter = 0;
const planReq = (method, { query = "", form } = {}) => new Request(`https://purplelink.llc/labs/plan/${query}`, {
  method,
  headers: { "x-nf-client-connection-ip": `198.51.100.${(ipCounter++ % 250) + 1}`, "content-type": "application/x-www-form-urlencoded" },
  body: form ? new URLSearchParams(form).toString() : undefined,
});

const tokenRows = [
  { short: "aB3dE9xQ", used: false, start_url: "https://purplelink.llc/tools/paper-review/upload/?direct_token=tokA" },
  { short: "Zk81mN0p", used: true, start_url: "", followups: [
    { kind: "revision", name: "Revision Review", url: "https://purplelink.llc/tools/paper-review/revision/upload/?session_id=cs_r", used: false },
    { kind: "response", name: "Response Review", url: "https://purplelink.llc/tools/response-review/upload/?session_id=cs_s", used: true },
  ] },
];
const view = (extra = {}) => ({
  state: "active", plan_name: "Lab Plus", tier: "lab-plus", reviews_per_month: 40, billing: "monthly",
  date: "13 December 2026", next_grant: "13 December 2026", unused: 17,
  grants: [
    { label: "13 October 2026", valid_until: "13 December 2026", expired: true, count: 40, unused: 3, tokens: [{ short: "OldOne11", used: false, start_url: "https://purplelink.llc/tools/paper-review/upload/?direct_token=old" }] },
    { label: "13 November 2026", valid_until: "13 January 2027", expired: false, count: 40, unused: 17, tokens: tokenRows },
  ],
  group_url: "https://purplelink.llc/labs/start/?k=lg_abcdefghijklmnop1234", customer: "cus_SECRET123", ...extra,
});

test("opening the plan link shows the plan and changes nothing", async () => {
  modalReply["/lab/plan"] = { status: 200, body: view() };
  const res = await plan(planReq("GET", { query: "?t=lab_tok1" }));
  assert.equal(res.status, 200);
  const html = await res.text();
  assert.match(html, /Your plan renews on 13 December 2026/);
  assert.match(html, /<dt>Reviews left<\/dt><dd>17<\/dd>/);
  assert.match(html, /<dt>Next batch<\/dt><dd>13 December 2026<\/dd>/);
  assert.match(html, /Lab Plus/);
  assert.match(html, /readonly value="https:\/\/purplelink\.llc\/labs\/start\/\?k=lg_abcdefghijklmnop1234"/);
  assert.match(html, /Replace this link/);
  assert.match(html, /old link stops working/);
  assert.match(html, /name="action" value="cancel"/);
  assert.match(html, /Billing, card and invoices/);
  assert.match(html, /every reviewed paper also gets one Revision Review and one Response Review/i);
  assert.match(html, /href="\/labs\/plan\.css"/);
  assert.doesNotMatch(html, /cus_SECRET123/, "the customer id is never rendered");
  assert.doesNotMatch(html, /\sstyle=/i);
  assert.deepEqual(modalCalls().map((c) => c.path), ["/lab/plan"]);
  assert.equal(res.headers.get("x-robots-tag"), "noindex");
  assert.equal(res.headers.get("cache-control"), "no-store");
});

test("batches are listed newest first with their reviews, start links, copyable URLs and follow-ups", async () => {
  modalReply["/lab/plan"] = { status: 200, body: view() };
  const html = await (await plan(planReq("GET", { query: "?t=lab_tok1" }))).text();
  assert.ok(html.indexOf("Batch of 13 November 2026") < html.indexOf("Batch of 13 October 2026"));
  assert.match(html, /Use them by 13 January 2027/);
  assert.match(html, /<code>aB3dE9xQ<\/code>/);
  assert.match(html, />Unused<\/span>/);
  assert.match(html, /<a class="btn btn-primary" href="https:\/\/purplelink\.llc\/tools\/paper-review\/upload\/\?direct_token=tokA">Start<\/a>/);
  assert.match(html, /readonly value="https:\/\/purplelink\.llc\/tools\/paper-review\/upload\/\?direct_token=tokA"/);
  assert.match(html, />Used<\/span>/);
  assert.match(html, /<a href="https:\/\/purplelink\.llc\/tools\/paper-review\/revision\/upload\/\?session_id=cs_r">Revision Review<\/a>/);
  assert.match(html, /<li>Response Review, used<\/li>/);
  assert.match(html, /They expired on 13 December 2026/);
  assert.doesNotMatch(html, /direct_token=old/, "an expired batch offers no start link");
});

test("a plain Lab plan has no group box", async () => {
  modalReply["/lab/plan"] = { status: 200, body: view({ group_url: "", plan_name: "Lab", tier: "lab", reviews_per_month: 20 }) };
  const html = await (await plan(planReq("GET", { query: "?t=lab_tok1" }))).text();
  assert.doesNotMatch(html, /Group link|Replace this link/);
});

test("everything from Modal is escaped, and unsafe links are dropped", async () => {
  const evil = `<img src=x onerror=alert(1)>"'`;
  modalReply["/lab/plan"] = { status: 200, body: view({
    plan_name: evil, date: evil, next_grant: evil, unused: evil, group_url: "javascript:alert(1)",
    grants: [{ label: "1 January 2027", valid_until: evil, expired: false, count: evil, unused: evil, tokens: [
      { short: evil, used: false, start_url: "javascript:alert(1)" },
      { short: "ok", used: true, start_url: "", followups: [{ name: evil, url: "https://evil.example/x", used: false }] },
    ] }],
  }) };
  const html = await (await plan(planReq("GET", { query: "?t=lab_tok1" }))).text();
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /javascript:alert/);
  assert.doesNotMatch(html, /evil\.example/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
});

test("each state has its own sentence", async () => {
  const says = async (state, re, extra = {}) => {
    modalReply["/lab/plan"] = { status: 200, body: view({ state, ...extra }) };
    assert.match(await (await plan(planReq("GET", { query: "?t=lab_tok1" }))).text(), re, state);
  };
  await says("cancelling", /will not renew\. It ends on 13 December 2026/);
  await says("problem", /last payment failed\. Your plan is paid through 13 December 2026/);
  await says("revoked", /refunded or disputed/);
  await says("ended", /This plan ended on 13 December 2026/);
  modalReply["/lab/plan"] = { status: 200, body: view({ state: "cancelling" }) };
  const html = await (await plan(planReq("GET", { query: "?t=lab_tok1" }))).text();
  assert.match(html, /Keep my plan/);
  assert.doesNotMatch(html, /Cancel renewal/);
  modalReply["/lab/plan"] = { status: 200, body: view({ state: "revoked" }) };
  const rev = await (await plan(planReq("GET", { query: "?t=lab_tok1" }))).text();
  assert.doesNotMatch(rev, /Start<\/a>|Group link|Billing, card/);
});

test("no token shows the email box; a malformed or unknown token shows it with a note", async () => {
  assert.match(await (await plan(planReq("GET"))).text(), /name="email"/);
  assert.match(await (await plan(planReq("GET", { query: "?t=" + "x".repeat(401) }))).text(), /expired or is not valid/);
  assert.match(await (await plan(planReq("GET", { query: "?t=notalabtoken" }))).text(), /expired or is not valid/);
  assert.equal(modalCalls().length, 0);
  modalReply["/lab/plan"] = { status: 404, body: { error: "invalid" } };
  assert.match(await (await plan(planReq("GET", { query: "?t=lab_bad" }))).text(), /expired or is not valid/);
  modalReply["/lab/plan"] = { status: 410, body: { error: "replaced" } };
  assert.match(await (await plan(planReq("GET", { query: "?t=lab_old" }))).text(), /replaced by a newer one/);
});

test("a Modal failure on GET shows a problem page", async () => {
  modalReply["/lab/plan"] = { status: 502, body: {} };
  const res = await plan(planReq("GET", { query: "?t=lab_tok1" }));
  assert.equal(res.status, 502);
  assert.match(await res.text(), /Try again in a minute/);
});

test("cancel is a POST and relays the link, then shows the new state with the replacement link", async () => {
  modalReply["/lab/cancel"] = { status: 200, body: view({ state: "cancelling", token: "lab_tok2" }) };
  const res = await plan(planReq("POST", { form: { action: "cancel", t: "lab_tok1" } }));
  assert.equal(res.status, 200);
  const html = await res.text();
  assert.match(html, /Your plan will not renew\. A confirmation email is on its way/);
  assert.match(html, /name="t" value="lab_tok2"/);
  assert.match(html, /name="action" value="undo"/);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/lab/cancel", { token: "lab_tok1" }]]);
});

test("undo restores renewal", async () => {
  modalReply["/lab/undo"] = { status: 200, body: view({ token: "lab_tok3" }) };
  const html = await (await plan(planReq("POST", { form: { action: "undo", t: "lab_tok2" } }))).text();
  assert.match(html, /renew again/);
  assert.match(html, /name="t" value="lab_tok3"/);
});

test("cancel error mapping: 404, 410, 409 plan_over, 502", async () => {
  const post = () => plan(planReq("POST", { form: { action: "cancel", t: "lab_tok1" } }));
  modalReply["/lab/cancel"] = { status: 404, body: {} };
  assert.match(await (await post()).text(), /expired or is not valid/);
  modalReply["/lab/cancel"] = { status: 410, body: {} };
  assert.match(await (await post()).text(), /replaced by a newer one/);
  modalReply["/lab/cancel"] = { status: 409, body: { error: "plan_over" } };
  const over = await post();
  assert.equal(over.status, 409);
  assert.match(await over.text(), /nothing is left to change/i);
  modalReply["/lab/cancel"] = { status: 502, body: { error: "stripe_failed" } };
  const bad = await post();
  assert.equal(bad.status, 502);
  assert.match(await bad.text(), /Nothing was changed/);
});

test("rotate replaces the group link and shows the new one under the new token", async () => {
  modalReply["/lab/rotate-group-link"] = { status: 200, body: view({ token: "lab_tok9", group_url: "https://purplelink.llc/labs/start/?k=lg_newnewnewnewnew1234" }) };
  const html = await (await plan(planReq("POST", { form: { action: "rotate", t: "lab_tok1" } }))).text();
  assert.match(html, /old group link no longer works/);
  assert.match(html, /lg_newnewnewnewnew1234/);
  assert.match(html, /name="t" value="lab_tok9"/);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/lab/rotate-group-link", { token: "lab_tok1" }]]);
  modalReply["/lab/rotate-group-link"] = { status: 409, body: { error: "not_plus" } };
  const np = await plan(planReq("POST", { form: { action: "rotate", t: "lab_tok1" } }));
  assert.equal(np.status, 409);
  assert.match(await np.text(), /Only Lab Plus/);
});

test("portal answers 303 to Stripe's billing page, returns to the plan page, and never shows the customer", async () => {
  modalReply["/lab/plan"] = { status: 200, body: view() };
  const res = await plan(planReq("POST", { form: { action: "portal", t: "lab_tok1" } }));
  assert.equal(res.status, 303);
  assert.equal(res.headers.get("location"), "https://billing.stripe.com/p/session/test_1");
  const post = calls.find((c) => c.url === "https://api.stripe.com/v1/billing_portal/sessions");
  const sent = new URLSearchParams(post.opts.body);
  assert.equal(sent.get("customer"), "cus_SECRET123");
  assert.equal(sent.get("return_url"), "https://purplelink.llc/labs/plan/?t=lab_tok1");
  assert.equal(await res.text(), "");
});

test("portal failures show a problem page with the mailto", async () => {
  modalReply["/lab/plan"] = { status: 200, body: view() };
  portalUrl = null;
  const res = await plan(planReq("POST", { form: { action: "portal", t: "lab_tok1" } }));
  assert.equal(res.status, 502);
  const html = await res.text();
  assert.match(html, /mailto:ben@purplelink\.llc/);
  assert.doesNotMatch(html, /cus_SECRET123/);
  modalReply["/lab/plan"] = { status: 200, body: view({ customer: "" }) };
  assert.equal((await plan(planReq("POST", { form: { action: "portal", t: "lab_tok1" } }))).status, 502);
  modalReply["/lab/plan"] = { status: 410, body: {} };
  assert.match(await (await plan(planReq("POST", { form: { action: "portal", t: "lab_old" } }))).text(), /replaced by a newer one/);
});

test("asking for a link gives the same answer whether or not a plan exists", async () => {
  const a = await plan(planReq("POST", { form: { action: "link", email: "has-plan@example.com" } }));
  const b = await plan(planReq("POST", { form: { action: "link", email: "no-plan@example.com" } }));
  assert.equal(a.status, 200);
  assert.equal(b.status, 200);
  const norm = async (r, e) => (await r.text()).replace(e, "EMAIL");
  assert.equal(await norm(a, "has-plan@example.com"), await norm(b, "no-plan@example.com"));
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body.email]), [["/lab/link", "has-plan@example.com"], ["/lab/link", "no-plan@example.com"]]);
});

test("an address is limited to three link requests a day, and the limit is per kind lab-plan-email", async () => {
  const codes = [];
  for (let i = 0; i < 4; i++) codes.push((await plan(planReq("POST", { form: { action: "link", email: "limit@example.com" } }))).status);
  assert.deepEqual(codes, [200, 200, 200, 429]);
  assert.ok([...store.keys()].some((k) => k.startsWith("rate-limits/rl:lab-plan-email:")));
});

test("an IP is limited to ten link requests a day", async () => {
  const codes = [];
  for (let i = 0; i < 11; i++) {
    const req = new Request("https://purplelink.llc/labs/plan/", { method: "POST",
      headers: { "x-nf-client-connection-ip": "203.0.113.9", "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ action: "link", email: `p${i}@example.com` }).toString() });
    codes.push((await plan(req)).status);
  }
  assert.equal(codes[9], 200);
  assert.equal(codes[10], 429);
  assert.ok([...store.keys()].some((k) => k.startsWith("rate-limits/rl:lab-plan-ip:")));
});

test("plan actions have their own daily limit (50), apart from link requests", async () => {
  modalReply["/lab/cancel"] = { status: 200, body: view({ state: "cancelling", token: "lab_tok2" }) };
  const codes = [];
  for (let i = 0; i < 51; i++) {
    const req = new Request("https://purplelink.llc/labs/plan/", { method: "POST",
      headers: { "x-nf-client-connection-ip": "203.0.113.77", "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ action: "cancel", t: "lab_tok1" }).toString() });
    codes.push((await plan(req)).status);
  }
  assert.equal(codes[49], 200);
  assert.equal(codes[50], 429);
  const link = new Request("https://purplelink.llc/labs/plan/", { method: "POST",
    headers: { "x-nf-client-connection-ip": "203.0.113.77", "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ action: "link", email: "fresh@example.com" }).toString() });
  assert.equal((await plan(link)).status, 200, "a lead who used many actions can still ask for a link");
});

test("a token with reserved characters round-trips through the portal return_url", async () => {
  const tok = "lab_a+b/c=d&e#f%g";
  modalReply["/lab/plan"] = { status: 200, body: view() };
  const res = await plan(planReq("POST", { form: { action: "portal", t: tok } }));
  assert.equal(res.status, 303);
  const post = calls.find((c) => c.url === "https://api.stripe.com/v1/billing_portal/sessions");
  const ret = new URLSearchParams(post.opts.body).get("return_url");
  assert.equal(new URL(ret).searchParams.get("t"), tok);
});

test("a malformed address is rejected before any lookup", async () => {
  const res = await plan(planReq("POST", { form: { action: "link", email: "not-an-email" } }));
  assert.match(await res.text(), /is not an email address/);
  assert.equal(modalCalls().length, 0);
});

test("unknown actions are 400, other methods 405, and a missing token on cancel shows the email box", async () => {
  assert.equal((await plan(planReq("POST", { form: { action: "delete-everything" } }))).status, 400);
  assert.equal((await plan(planReq("DELETE"))).status, 405);
  assert.match(await (await plan(planReq("POST", { form: { action: "cancel" } }))).text(), /name="email"/);
  assert.equal(modalCalls().length, 0);
});

// ------------------------------------------------------------------------------------- group page

const KEY = "lg_abcdefghijklmnop1234";
const startReq = (method, { query = "", form, ip } = {}) => new Request(`https://purplelink.llc/labs/start/${query}`, {
  method,
  headers: { "x-nf-client-connection-ip": ip || `192.0.2.${(ipCounter++ % 250) + 1}`, "content-type": "application/x-www-form-urlencoded" },
  body: form ? new URLSearchParams(form).toString() : undefined,
});
const group = (extra = {}) => ({ ok: true, plan_name: "Lab Plus", available: 3, state: "active", next_grant: "13 December 2026", ...extra });

test("opening a group link shows the count and a form, and claims nothing", async () => {
  modalReply["/lab/group-view"] = { status: 200, body: group() };
  const res = await start(startReq("GET", { query: `?k=${KEY}` }));
  assert.equal(res.status, 200);
  const html = await res.text();
  assert.match(html, /3 reviews available/);
  assert.match(html, /<form method="post" action="\/labs\/start\/">/);
  assert.match(html, new RegExp(`name="k" value="${KEY}"`));
  assert.match(html, /Start a review/);
  assert.match(html, /4 to 8 minutes/);
  assert.match(html, /PDF or Word \.docx/);
  assert.doesNotMatch(html, /\sstyle=/i);
  assert.deepEqual(modalCalls().map((c) => c.path), ["/lab/group-view"], "a GET never calls member-claim");
  assert.equal(res.headers.get("x-robots-tag"), "noindex");
});

test("a group link with one review left says so in the singular", async () => {
  modalReply["/lab/group-view"] = { status: 200, body: group({ available: 1 }) };
  assert.match(await (await start(startReq("GET", { query: `?k=${KEY}` }))).text(), /1 review available/);
});

test("a group link with none left offers no button and names the next batch", async () => {
  modalReply["/lab/group-view"] = { status: 200, body: group({ available: 0 }) };
  const res = await start(startReq("GET", { query: `?k=${KEY}` }));
  const html = await res.text();
  assert.match(html, /No reviews available right now/);
  assert.match(html, /next batch arrives on 13 December 2026/);
  assert.doesNotMatch(html, /<form/);
});

test("a malformed key is refused before Modal is asked", async () => {
  for (const q of ["", "?k=", "?k=lg_short", "?k=lab_abcdefghijklmnop1234", `?k=${KEY}%22%3E%3Cscript%3E`, `?k=lg_${"a".repeat(65)}`]) {
    const res = await start(startReq("GET", { query: q }));
    assert.equal(res.status, 404, q);
    assert.match(await res.text(), /This link is not valid[\s\S]*Ask your group lead for the current link\./);
  }
  assert.equal(modalCalls().length, 0);
});

test("group view: 404 is not valid, a finished plan has ended, a Modal failure is a problem page", async () => {
  modalReply["/lab/group-view"] = { status: 404, body: { error: "invalid" } };
  assert.match(await (await start(startReq("GET", { query: `?k=${KEY}` }))).text(), /not valid/);
  for (const state of ["problem", "revoked", "ended"]) {
    modalReply["/lab/group-view"] = { status: 200, body: group({ state }) };
    const res = await start(startReq("GET", { query: `?k=${KEY}` }));
    assert.equal(res.status, 410, state);
    assert.match(await res.text(), /This plan is not active/);
  }
  modalReply["/lab/group-view"] = { status: 200, body: group({ state: "cancelling" }) };
  assert.equal((await start(startReq("GET", { query: `?k=${KEY}` }))).status, 200);
  modalReply["/lab/group-view"] = { status: 502, body: {} };
  assert.equal((await start(startReq("GET", { query: `?k=${KEY}` }))).status, 502);
});

test("the group page never shows an email address", async () => {
  modalReply["/lab/group-view"] = { status: 200, body: group({ email: "lead@example.com", owner_email: "lead@example.com" }) };
  assert.doesNotMatch(await (await start(startReq("GET", { query: `?k=${KEY}` }))).text(), /lead@example\.com/);
});

test("the button claims one review and answers 303 to the upload page", async () => {
  const url = "https://purplelink.llc/tools/paper-review/upload/?direct_token=tokZ";
  modalReply["/lab/member-claim"] = { status: 200, body: { start_url: url } };
  const res = await start(startReq("POST", { form: { k: KEY } }));
  assert.equal(res.status, 303);
  assert.equal(res.headers.get("location"), url);
  assert.deepEqual(modalCalls().map((c) => [c.path, c.body]), [["/lab/member-claim", { k: KEY }]]);
});

test("a start_url that is not the upload page is never followed", async () => {
  for (const bad of ["https://evil.example/?direct_token=1", "https://purplelink.llc/tools/paper-review/upload/", "javascript:alert(1)", "", undefined]) {
    modalReply["/lab/member-claim"] = { status: 200, body: { start_url: bad } };
    const res = await start(startReq("POST", { form: { k: KEY } }));
    assert.equal(res.status, 502, String(bad));
    assert.equal(res.headers.get("location"), null);
  }
});

test("claim error mapping: none_left, invalid, ended, failure", async () => {
  const post = () => start(startReq("POST", { form: { k: KEY } }));
  modalReply["/lab/member-claim"] = { status: 409, body: { error: "none_left", next_grant: "13 December 2026" } };
  const none = await post();
  assert.equal(none.status, 409);
  assert.match(await none.text(), /next batch arrives on 13 December 2026/);
  modalReply["/lab/member-claim"] = { status: 409, body: { error: "none_left", next_grant: "" } };
  assert.doesNotMatch(await (await post()).text(), /next batch arrives/);
  modalReply["/lab/member-claim"] = { status: 404, body: { error: "invalid" } };
  assert.match(await (await post()).text(), /This link is not valid[\s\S]*Ask your group lead for the current link\./);
  modalReply["/lab/member-claim"] = { status: 410, body: { error: "plan_over" } };
  assert.match(await (await post()).text(), /This plan is not active/);
  modalReply["/lab/member-claim"] = { status: 500, body: {} };
  assert.equal((await post()).status, 502);
});

test("a POST with a malformed key never reaches Modal", async () => {
  const res = await start(startReq("POST", { form: { k: "lg_x" } }));
  assert.equal(res.status, 404);
  assert.equal(modalCalls().length, 0);
});

test("an IP can claim 30 times a day, then is stopped", async () => {
  modalReply["/lab/member-claim"] = { status: 200, body: { start_url: "https://purplelink.llc/tools/paper-review/upload/?direct_token=t" } };
  const codes = [];
  for (let i = 0; i < 31; i++) codes.push((await start(startReq("POST", { form: { k: KEY }, ip: "203.0.113.50" }))).status);
  assert.equal(codes.slice(0, 30).every((c) => c === 303), true);
  assert.equal(codes[30], 429);
  assert.ok([...store.keys()].some((k) => k.startsWith("rate-limits/rl:lab-start-ip:")));
  assert.equal(modalCalls().length, 30);
});

test("other methods are refused", async () => {
  assert.equal((await start(startReq("DELETE"))).status, 405);
});
