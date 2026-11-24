// Fixed Stripe products for single Mac apps (netlify/lib/app-products.mjs): checkout names the app's fixed product
// when its `app_<slug>` Price is found at the same amount, so a promotion code limited to the Mac apps can apply, and
// falls back to the inline product on any miss. Stripe and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/checkout-app-products.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {}, list: async () => ({ blobs: [] }) }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_PRICE_OUTBOUND_VEIL: "price_ov_main" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const appProducts = await import("../lib/app-products.mjs");
const { default: checkout } = await import("../functions/checkout.mjs");

const CENTS = { moderntex: 1999, keyfeel: 999, tapefolio: 2999, lenscrib: 1999, nee: 1499, panely: 999, summonly: 999 };
let calls;
let mode; // "ok" | "fail" | "wrong-amount" | "inactive"
beforeEach(() => {
  calls = [];
  mode = "ok";
  delete env.STRIPE_MANAGED_PAYMENTS;
  appProducts.resetAppProductCache();
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    if (u.startsWith("https://api.stripe.com/v1/prices")) {
      const keys = new URL(u).searchParams.getAll("lookup_keys[]");
      if (!keys.some((k) => k.startsWith("app_"))) return new Response(JSON.stringify({ data: [] }), { status: 200 });
      if (mode === "fail") return new Response("{}", { status: 500 });
      const data = keys.map((k) => {
        const slug = k.replace(/^app_/, "");
        return {
          id: `price_full_${slug}`, product: `prod_${slug}`, lookup_key: k, type: "one_time", currency: "usd",
          active: mode !== "inactive", unit_amount: mode === "wrong-amount" ? 1 : CENTS[slug],
        };
      });
      return new Response(JSON.stringify({ data }), { status: 200 });
    }
    if (u.includes("api.stripe.com/v1/checkout/sessions") && opts.method === "POST") {
      return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  };
});

let ipN = 0;
const post = (body) => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": `198.51.100.${10 + (ipN++ % 200)}` }, body: JSON.stringify(body),
}));
const sessionParams = () => {
  const c = calls.filter((x) => x.url.includes("/checkout/sessions") && x.opts.method === "POST");
  assert.equal(c.length, 1, "one session created");
  return new URLSearchParams(c[0].opts.body);
};

test("a single Mac app names its fixed product and keeps the catalog amount and the promotion-code box", async () => {
  const r = await post({ product: "moderntex" });
  assert.equal(r.status, 200);
  const p = sessionParams();
  assert.equal(p.get("line_items[0][price_data][product]"), "prod_moderntex");
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "1999");
  assert.equal(p.get("line_items[0][price_data][product_data][name]"), null);
  assert.equal(p.get("allow_promotion_codes"), "true");
});

test("every listed app with an inline price uses its fixed product", async () => {
  for (const slug of ["keyfeel", "tapefolio", "nee", "panely", "summonly"]) {
    calls = [];
    const r = await post({ product: slug });
    assert.equal(r.status, 200, slug);
    assert.equal(sessionParams().get("line_items[0][price_data][product]"), `prod_${slug}`, slug);
  }
});

for (const m of ["fail", "wrong-amount", "inactive"]) {
  test(`lookup ${m}: checkout falls back to the inline product exactly as before`, async () => {
    mode = m;
    const r = await post({ product: "moderntex" });
    assert.equal(r.status, 200);
    const p = sessionParams();
    assert.equal(p.get("line_items[0][price_data][product]"), null);
    assert.ok(p.get("line_items[0][price_data][product_data][name]"));
    assert.equal(p.get("line_items[0][price_data][unit_amount]"), "1999");
  });
}

test("bundles, seat packs and env-Price apps never take a fixed app product", async () => {
  for (const body of [{ product: "bundle-2", parts: ["moderntex", "keyfeel"] }, { product: "moderntex-seats", seats: 5 }, { product: "outbound-veil" }]) {
    calls = [];
    await post(body);
    const sessions = calls.filter((x) => x.url.includes("/checkout/sessions") && x.opts.method === "POST");
    for (const s of sessions) assert.equal(new URLSearchParams(s.opts.body).get("line_items[0][price_data][product]"), null, body.product);
  }
});

test("Managed Payments: a fixed product carries no inline tax code (the product has its own)", async () => {
  env.STRIPE_MANAGED_PAYMENTS = "all";
  const r = await post({ product: "keyfeel" });
  assert.equal(r.status, 200);
  const p = sessionParams();
  assert.equal(p.get("line_items[0][price_data][product]"), "prod_keyfeel");
  assert.equal(p.get("line_items[0][price_data][product_data][tax_code]"), null);
});

test("appProductId: unknown slug, bad amount or no key give null without a request", async () => {
  const fetchFn = async () => { throw new Error("must not fetch"); };
  assert.equal(await appProducts.appProductId("sk_test_x", "app-suite", 999, { fetchFn }), null);
  assert.equal(await appProducts.appProductId("sk_test_x", "moderntex", 0, { fetchFn }), null);
  assert.equal(await appProducts.appProductId("", "moderntex", 1999, { fetchFn }), null);
});

test("appProductId: the cache is per secret key", async () => {
  let n = 0;
  const fetchFn = async () => { n++; return new Response(JSON.stringify({ data: [{ lookup_key: "app_moderntex", product: `prod_${n}`, active: true, currency: "usd", type: "one_time", unit_amount: 1999 }] }), { status: 200 }); };
  assert.equal(await appProducts.appProductId("sk_a", "moderntex", 1999, { fetchFn }), "prod_1");
  assert.equal(await appProducts.appProductId("sk_a", "moderntex", 1999, { fetchFn }), "prod_1");
  assert.equal(await appProducts.appProductId("sk_b", "moderntex", 1999, { fetchFn }), "prod_2");
});
