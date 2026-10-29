// Reddit Conversions API (2026-10-29): a ModernTex sale from a Reddit ad is reported server-side with the Stripe
// session id as the conversion id. Covers the signal reaching the session metadata (never under Do Not Track),
// the event's shape, and that no failure can change the webhook's answer or the delivery.
// Stripe, Resend, Reddit and Blobs are stubbed; nothing real is called.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/reddit-capi.test.mjs

import { readFileSync } from "node:fs";
import vm from "node:vm";
import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac, createHash, generateKeyPairSync } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({ get: async (k) => store.get(`${name}/${k}`) ?? null, set: async (k, v) => { store.set(`${name}/${k}`, v); } }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { privateKey } = generateKeyPairSync("ed25519");
const jwk = privateKey.export({ format: "jwk" });
const TOKEN = "rdt-secret-token-123";
const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend",
  RESEND_API_KEY: "re_dummy", STRIPE_PRICE_KIT_CLIP: "price_dummy", MODERNTEX_LICENSE_PRIVATE_KEY: Buffer.from(jwk.d, "base64url").toString("base64"),
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook } = await import("../functions/stripe-webhook.mjs");
const { sendRedditPurchase, buildEvent } = await import("../lib/reddit-capi.mjs");

let calls, redditImpl, logs;
const realLog = { warn: console.warn, debug: console.debug, log: console.log };
beforeEach(() => {
  store.clear(); calls = []; logs = [];
  delete env.REDDIT_CAPI_TOKEN; delete env.REDDIT_AD_ACCOUNT_ID; delete env.REDDIT_CAPI_TEST_MODE;
  redditImpl = async () => new Response("{}", { status: 200 });
  for (const k of ["warn", "debug", "log"]) console[k] = (...a) => logs.push(a.map(String).join(" "));
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (String(url).includes("ads-api.reddit.com")) return redditImpl(url, opts);
    if (String(url).includes("api.stripe.com/v1/checkout/sessions")) return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/x" }), { status: 200 });
    return new Response("{}", { status: 200 });
  };
});
import { afterEach } from "node:test";
afterEach(() => { Object.assign(console, realLog); });

const post = (body, ip = "203.0.113.9") => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": ip }, body: JSON.stringify(body),
}));
const stripeParams = () => new URLSearchParams(calls.find((c) => c.url.includes("/checkout/sessions")).opts.body);
const reddit = () => calls.filter((c) => c.url.includes("ads-api.reddit.com"));
const flush = () => new Promise((r) => setTimeout(r, 20));

// ---- checkout: the signal reaches the session metadata ----
test("a Reddit visitor's ModernTex checkout carries reddit_ad and a validated click id", async () => {
  await post({ product: "moderntex", rdt: { c: "t3_abc-123.x" } }, "198.51.100.1");
  const p = stripeParams();
  assert.equal(p.get("metadata[reddit_ad]"), "1");
  assert.equal(p.get("metadata[reddit_click_id]"), "t3_abc-123.x");
});

test("a Reddit visitor without a click id still gets the flag; a bad click id is dropped", async () => {
  await post({ product: "moderntex", rdt: {} }, "198.51.100.2");
  assert.equal(stripeParams().get("metadata[reddit_ad]"), "1");
  assert.equal(stripeParams().get("metadata[reddit_click_id]"), null);
  calls = [];
  await post({ product: "moderntex", rdt: { c: "bad id <script>" + "x".repeat(200) } }, "198.51.100.3");
  assert.equal(stripeParams().get("metadata[reddit_click_id]"), null);
});

test("no rdt, other products: nothing new in the metadata", async () => {
  await post({ product: "moderntex" }, "198.51.100.4");
  assert.equal(stripeParams().get("metadata[reddit_ad]"), null);
  calls = [];
  await post({ product: "kit-clip", rdt: { c: "abc" } }, "198.51.100.5");
  assert.equal(stripeParams().get("metadata[reddit_ad]"), null);
});

// ---- browser: analytics.js sends rdt only for a Reddit visitor and never under Do Not Track ----
const analyticsSrc = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");
function browser({ dnt = "", search = "", stored = {} } = {}) {
  const ls = { ...stored };
  const sent = [];
  const sandbox = {
    navigator: { sendBeacon: () => true, doNotTrack: dnt }, Blob: class { constructor(p) { this.p = p; } },
    URL, URLSearchParams, Date, JSON, Math, String, RegExp, Object, Promise,
    document: { referrer: "", addEventListener() {}, createElement: () => ({}), head: { appendChild() {} } },
    location: { search, pathname: "/moderntex/", host: "purplelink.llc", hostname: "purplelink.llc" },
    localStorage: { getItem: (k) => ls[k] ?? null, setItem: (k, v) => { ls[k] = v; }, removeItem: (k) => { delete ls[k]; } },
    fetch: async (u, init) => { sent.push(JSON.parse(init.body)); return { ok: true }; },
  };
  sandbox.window = sandbox;
  vm.runInNewContext(analyticsSrc, sandbox);
  return { ls, buy: async () => { await sandbox.window.fetch("/.netlify/functions/checkout", { method: "POST", body: JSON.stringify({ product: "moderntex" }) }); return sent.at(-1); } };
}

test("browser: rdt_cid is sent with the checkout request", async () => {
  const b = browser({ search: "?utm_source=reddit&utm_medium=paid&rdt_cid=clk123" });
  assert.deepEqual((await b.buy()).rdt, { c: "clk123" });
});

test("browser: first-touch Reddit channel without a click id sends an empty marker", async () => {
  const b = browser({ search: "?utm_source=reddit&utm_medium=paid" });
  assert.deepEqual((await b.buy()).rdt, {});
});

test("browser: other visitors send nothing", async () => {
  assert.equal((await browser({ search: "?utm_source=google" }).buy()).rdt, undefined);
  assert.equal((await browser({ search: "" }).buy()).rdt, undefined);
});

test("browser: under Do Not Track nothing is stored or sent", async () => {
  const b = browser({ dnt: "1", search: "?utm_source=reddit&utm_medium=paid&rdt_cid=clk123" });
  assert.equal(b.ls.pl_rdt, undefined);
  assert.equal(b.ls.pl_attr, undefined);
});

// ---- webhook ----
const session = (over = {}, meta = {}) => ({
  id: "cs_live_abcdefghij1234", status: "complete", payment_status: "paid", amount_total: 1999, amount_subtotal: 1999, currency: "usd",
  customer_details: { email: "  Buyer@Example.COM " },
  metadata: { product: "moderntex", reddit_ad: "1", reddit_click_id: "clk123", ...meta }, ...over,
});
function signed(s, id = "evt_1") {
  const body = JSON.stringify({ id, type: "checkout.session.completed", data: { object: s } });
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", { method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body });
}

test("webhook: a Reddit ModernTex sale posts one Purchase with the session id, real amount and hashed email", async () => {
  env.REDDIT_CAPI_TOKEN = TOKEN;
  const res = await webhook(signed(session({ amount_total: 1499, currency: "eur" })));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "delivered_by_blobs");
  await flush();
  assert.equal(reddit().length, 1);
  const c = reddit()[0];
  assert.equal(c.url, "https://ads-api.reddit.com/api/v2.0/conversions/events/a2_jx9tsee4sm5h");
  assert.equal(c.opts.headers.Authorization, `Bearer ${TOKEN}`);
  const b = JSON.parse(c.opts.body);
  assert.equal(b.test_mode, false);
  const e = b.events[0];
  assert.equal(e.event_type.tracking_type, "Purchase");
  assert.equal(e.click_id, "clk123");
  assert.deepEqual(e.event_metadata, { conversion_id: "cs_live_abcdefghij1234", currency: "EUR", item_count: 1, value_decimal: 14.99 });
  assert.equal(e.user.email, createHash("sha256").update("buyer@example.com").digest("hex"));
  assert.ok(!Number.isNaN(Date.parse(e.event_at)));
  assert.equal(e.user.ip_address, undefined);
  assert.equal(e.user.user_agent, undefined);
});

test("webhook: env account id and test mode are honored", async () => {
  env.REDDIT_CAPI_TOKEN = TOKEN; env.REDDIT_AD_ACCOUNT_ID = "t2_acct1"; env.REDDIT_CAPI_TEST_MODE = "1";
  await webhook(signed(session()));
  await flush();
  assert.ok(reddit()[0].url.endsWith("/conversions/events/t2_acct1"));
  assert.equal(JSON.parse(reddit()[0].opts.body).test_mode, true);
});

test("webhook: no call when the token is unset, or the sale is not from Reddit, or not ModernTex, or free", async () => {
  await webhook(signed(session()));
  env.REDDIT_CAPI_TOKEN = TOKEN;
  await webhook(signed(session({}, { reddit_ad: undefined }), "evt_2"));
  await webhook(signed(session({ id: "cs_live_other1234567", metadata: { product: "keyfeel", reddit_ad: "1" } }), "evt_3"));
  await webhook(signed(session({ id: "cs_live_free12345678", payment_status: "no_payment_required", amount_total: 0 }), "evt_4"));
  await flush();
  assert.equal(reddit().length, 0);
});

test("webhook: a rejected, failing or hanging Reddit call changes neither the answer nor the delivery", async () => {
  env.REDDIT_CAPI_TOKEN = TOKEN;
  for (const [i, impl] of [
    async () => new Response("no", { status: 500 }),
    async () => { throw new Error("boom " + TOKEN); },
    () => new Promise(() => {}), // never answers
  ].entries()) {
    redditImpl = impl;
    const t0 = Date.now();
    const res = await webhook(signed(session({ id: `cs_live_fail${i}abcdefghij` }), `evt_f${i}`));
    assert.equal(res.status, 200);
    assert.equal((await res.json()).status, "delivered_by_blobs");
    assert.ok(Date.now() - t0 < 1500, "the webhook must not wait for Reddit");
    assert.ok(calls.some((c) => c.url.includes("api.resend.com")), "the license email still goes out");
  }
});

test("sendRedditPurchase: one retry at most, resolves, and the token and email never reach the logs", async () => {
  let n = 0;
  const r = await sendRedditPurchase(session(), {
    env: (k) => (k === "REDDIT_CAPI_TOKEN" ? TOKEN : undefined),
    fetchImpl: async () => { n++; throw Object.assign(new Error("fail " + TOKEN + " buyer@example.com"), { name: "TypeError" }); },
  });
  assert.equal(r, "failed");
  assert.equal(n, 2);
  assert.equal(await sendRedditPurchase(session(), { env: () => TOKEN, fetchImpl: async () => new Response("", { status: 400 }) }), "rejected");
  const all = logs.join("\n");
  assert.ok(!all.includes(TOKEN));
  assert.ok(!/buyer@example\.com/i.test(all));
});

test("buildEvent leaves out user and click id when the session has none", () => {
  const e = buildEvent({ id: "cs_1", amount_total: 1999, currency: "usd", metadata: { product: "moderntex" } });
  assert.equal(e.user, undefined);
  assert.equal(e.click_id, undefined);
});
