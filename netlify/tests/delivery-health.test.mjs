// Delivery health: the decision logic against Stripe-shaped fixtures, and the handler's auth and error paths.
// Stripe is stubbed.
//
// Run with: node --test netlify/tests/delivery-health.test.mjs

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

const env = { STATS_TOKEN: "stats-token-for-tests-0123456789", STRIPE_SECRET_KEY: "sk_test_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: handler, evaluate } = await import("../functions/delivery-health.mjs");

const NOW = 1_800_000_000;
const HOUR = 3600;
const endpoint = (over = {}) => ({ id: "we_1", url: "https://purplelink.llc/.netlify/functions/stripe-webhook", status: "enabled", enabled_events: ["checkout.session.completed"], ...over });
const session = (id, ageSecs, over = {}) => ({ id, created: NOW - ageSecs, payment_status: "paid", amount_total: 1999, currency: "usd", metadata: { product: "moderntex" }, ...over });
const event = (sessionId, ageSecs, pending = 0) => ({ id: `evt_${sessionId}`, created: NOW - ageSecs, pending_webhooks: pending, data: { object: { id: sessionId } } });
const run = (o) => evaluate({ sessions: [], events: [], endpoints: [endpoint()], now: NOW, days: 14, ...o });
const check = (r, name) => r.checks.find((c) => c.check === name);

test("a delivered order passes every check", () => {
  const r = run({ sessions: [session("cs_live_aaaaaa111111", 3 * HOUR)], events: [event("cs_live_aaaaaa111111", 3 * HOUR)] });
  assert.equal(r.status, "ok");
  assert.equal(r.paidOrders, 1);
  assert.deepEqual(r.checks.map((c) => c.status), ["ok", "ok", "ok"]);
});

test("a paid order with no event is bad", () => {
  const r = run({ sessions: [session("cs_live_bbbbbb222222", 2 * HOUR)], events: [] });
  assert.equal(r.status, "bad");
  assert.equal(check(r, "Paid orders with a webhook event").status, "bad");
  assert.equal(r.missingEvent[0].session, "…222222");
  assert.equal(r.missingEvent[0].product, "moderntex");
});

test("an old event still pending is bad, and says when Stripe has stopped retrying", () => {
  const retrying = run({ sessions: [session("cs_live_cccccc333333", 2 * HOUR)], events: [event("cs_live_cccccc333333", 2 * HOUR, 1)] });
  assert.equal(retrying.status, "bad");
  assert.match(check(retrying, "Webhook deliveries confirmed").detail, /still retrying/);
  const spent = run({ sessions: [session("cs_live_dddddd444444", 80 * HOUR)], events: [event("cs_live_dddddd444444", 80 * HOUR, 1)] });
  assert.match(check(spent, "Webhook deliveries confirmed").detail, /retries used up/);
  assert.equal(spent.notAcknowledged[0].retriesUsed, true);
});

test("an order inside the grace period is not judged yet", () => {
  const r = run({ sessions: [session("cs_live_eeeeee555555", 120)], events: [] });
  assert.equal(r.status, "ok");
  assert.equal(r.notYetCounted, 1);
});

test("unpaid and abandoned sessions are ignored", () => {
  const r = run({ sessions: [session("cs_live_ffffff666666", 5 * HOUR, { payment_status: "unpaid" })], events: [] });
  assert.equal(r.paidOrders, 0);
  assert.equal(r.status, "ok");
});

test("a free (100% off) order still has to be delivered", () => {
  const r = run({ sessions: [session("cs_live_gggggg777777", 5 * HOUR, { payment_status: "no_payment_required", amount_total: 0 })], events: [] });
  assert.equal(r.status, "bad");
});

test("the worst of several events for one session counts", () => {
  const r = run({ sessions: [session("cs_live_hhhhhh888888", 2 * HOUR)], events: [event("cs_live_hhhhhh888888", 2 * HOUR, 0), { ...event("cs_live_hhhhhh888888", 2 * HOUR, 2), id: "evt_second" }] });
  assert.equal(r.status, "bad");
});

test("endpoint problems: missing, disabled, wrong events, unreadable, other site off", () => {
  assert.equal(check(run({ endpoints: [] }), "Stripe webhook endpoint").status, "bad");
  assert.match(check(run({ endpoints: [endpoint({ status: "disabled" })] }), "Stripe webhook endpoint").detail, /disabled/);
  assert.match(check(run({ endpoints: [endpoint({ enabled_events: ["charge.refunded"] })] }), "Stripe webhook endpoint").detail, /does not listen/);
  assert.equal(check(run({ endpoints: null }), "Stripe webhook endpoint").status, "warn");
  assert.equal(check(run({ endpoints: [endpoint({ enabled_events: ["*"] })] }), "Stripe webhook endpoint").status, "ok");
  const other = endpoint({ id: "we_2", url: "https://getmuscleonglp.com/.netlify/functions/stripe-webhook", status: "disabled" });
  const r = run({ endpoints: [endpoint(), other] });
  assert.equal(check(r, "Stripe webhook endpoint").status, "warn");
  assert.match(check(r, "Stripe webhook endpoint").detail, /getmuscleonglp\.com/);
});

test("nothing identifying a buyer is returned", () => {
  const s = session("cs_live_iiiiii999999", 2 * HOUR, { customer_details: { email: "buyer@example.com", name: "A Buyer" }, customer_email: "buyer@example.com" });
  const out = JSON.stringify(run({ sessions: [s], events: [] }));
  assert.ok(!out.includes("buyer@example.com") && !out.includes("A Buyer"));
  assert.ok(!out.includes("cs_live_iiiiii999999"));
});

test("a truncated read is flagged rather than passed silently", () => {
  assert.equal(check(run({ truncated: true }), "Check coverage").status, "warn");
});

// ---- the handler ----
let calls;
let methods;
const stripeReply = ({ sessions = [], events = [], endpoints = [endpoint()], fail } = {}) => {
  globalThis.fetch = async (url, init) => {
    const u = String(url);
    calls.push(u);
    methods.push(init?.method || "GET");
    if (fail) return new Response("boom", { status: 500 });
    if (u.includes("/v1/checkout/sessions")) return new Response(JSON.stringify({ data: sessions, has_more: false }));
    if (u.includes("/v1/events")) return new Response(JSON.stringify({ data: events, has_more: false }));
    if (u.includes("/v1/webhook_endpoints")) return new Response(JSON.stringify({ data: endpoints, has_more: false }));
    throw new Error(`Unexpected fetch to ${u}`);
  };
};
const call = (init = {}, path = "") => handler(new Request(`https://purplelink.llc/.netlify/functions/delivery-health${path}`, init));

beforeEach(() => { calls = []; methods = []; stripeReply(); env.STATS_TOKEN = "stats-token-for-tests-0123456789"; env.STRIPE_SECRET_KEY = "sk_test_dummy"; });

test("handler: no token, wrong token and a wrong length token are all refused before Stripe is touched", async () => {
  assert.equal((await call()).status, 401);
  assert.equal((await call({ headers: { "x-stats-token": "nope" } })).status, 401);
  assert.equal((await call({}, "?token=short")).status, 401);
  assert.equal(calls.length, 0);
});

test("handler: header or query token works, only GET is allowed", async () => {
  assert.equal((await call({ headers: { "x-stats-token": env.STATS_TOKEN } })).status, 200);
  assert.equal((await call({}, `?token=${env.STATS_TOKEN}`)).status, 200);
  assert.equal((await call({ method: "POST", headers: { "x-stats-token": env.STATS_TOKEN } })).status, 405);
});

test("handler: misconfiguration is reported, not guessed around", async () => {
  delete env.STRIPE_SECRET_KEY;
  assert.equal((await call({ headers: { "x-stats-token": env.STATS_TOKEN } })).status, 500);
  env.STRIPE_SECRET_KEY = "sk_test_dummy";
  delete env.STATS_TOKEN;
  assert.equal((await call({ headers: { "x-stats-token": "anything" } })).status, 500);
});

test("handler: days is clamped to what the Events API keeps, and every Stripe call is a read", async () => {
  const res = await call({ headers: { "x-stats-token": env.STATS_TOKEN } }, "?days=400");
  assert.equal((await res.json()).windowDays, 30);
  assert.ok(calls.length >= 3);
  assert.ok(methods.every((m) => m === "GET"));
  assert.ok(calls.every((u) => u.startsWith("https://api.stripe.com/v1/")));
});

test("handler: a Stripe outage is a 502 with no secrets in it", async () => {
  stripeReply({ fail: true });
  const res = await call({ headers: { "x-stats-token": env.STATS_TOKEN } });
  assert.equal(res.status, 502);
  const body = await res.text();
  assert.ok(!body.includes("sk_test_dummy"));
});

test("handler: a stuck order comes back as bad with checks shaped for the dashboard", async () => {
  const now = Math.floor(Date.now() / 1000);
  stripeReply({ sessions: [session("cs_live_jjjjjj000000", 4 * HOUR, { created: now - 4 * HOUR })], events: [{ ...event("cs_live_jjjjjj000000", 4 * HOUR, 1), created: now - 4 * HOUR }] });
  const body = await (await call({ headers: { "x-stats-token": env.STATS_TOKEN } })).json();
  assert.equal(body.status, "bad");
  assert.deepEqual(Object.keys(body.checks[0]).sort(), ["check", "detail", "n", "status"]);
});
