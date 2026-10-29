// Stripe Adaptive Pricing is on for the Mac-app checkout (2026-10-29): Stripe shows the buyer the price in their
// local currency, converted from the USD base. It only applies while a session stays plain: a USD price, no
// currency_options, no manual capture, no switch that turns it off. This test pins the session parameters of
// every Mac app product to that shape, and keeps the amounts equal to the catalog and netlify/lib/seats.mjs.
// See docs/products/moderntex-intl.md.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/checkout-adaptive-pricing.test.mjs

import { readFileSync } from "node:fs";
import { test, mock } from "node:test";
import assert from "node:assert/strict";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {} }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

globalThis.Netlify = {
  env: {
    get: (key) => {
      if (key === "STRIPE_SECRET_KEY") return "sk_test_dummy";
      if (key.startsWith("STRIPE_PRICE_")) return "price_dummy";
      return undefined; // STRIPE_MANAGED_PAYMENTS unset: the plain session
    },
  },
};

const { default: handler } = await import("../functions/checkout.mjs");
const { seatUnitCents, seatTotalCents } = await import("../lib/seats.mjs");
const { BUNDLES } = await import("../lib/bundles.mjs");

// product key -> { body, cents } where cents is the expected unit amount, or null for a product priced by a
// Stripe Price (Outbound Veil, Legroom), which the session cannot show.
const MAC_APPS = {
  "moderntex": { body: {}, cents: 1999 },
  "keyfeel": { body: {}, cents: 999 },
  "tapefolio": { body: {}, cents: 2999 },
  "panely": { body: {}, cents: 999 },
  "summonly": { body: {}, cents: 999 },
  "app-suite": { body: {}, cents: 5999 },
  "bundle-2": { body: { apps: ["moderntex", "keyfeel"] }, cents: BUNDLES["bundle-2"].cents },
  "bundle-3": { body: { apps: ["moderntex", "keyfeel", "panely"] }, cents: BUNDLES["bundle-3"].cents },
  "moderntex-seats": { body: { seats: 5 }, cents: seatUnitCents(5) },
  "outbound-veil": { body: {}, cents: null },
  "legroom": { body: {}, cents: null },
};

let n = 0;
async function session(product, extra) {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    const u = new URL(String(url));
    if (u.hostname === "api.stripe.com" && u.pathname === "/v1/checkout/sessions") {
      captured = opts.body;
      return new Response(JSON.stringify({ id: "cs_test_ap", url: "https://checkout.stripe.com/pay/cs_test_ap" }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": `198.51.100.${++n}` },
      body: JSON.stringify({ product, ...extra }),
    }));
    assert.equal(res.status, 200, product);
  } finally {
    globalThis.fetch = originalFetch;
  }
  return new URLSearchParams(captured);
}

for (const [product, { body, cents }] of Object.entries(MAC_APPS)) {
  test(`${product}: the session stays Adaptive Pricing compatible`, async () => {
    const p = await session(product, body);
    const keys = [...p.keys()];
    assert.equal(p.get("mode"), "payment");
    // Payment methods: card (with Apple Pay and Google Pay) and Link, nothing else.
    assert.deepEqual(keys.filter((k) => k.startsWith("payment_method_types[")).map((k) => p.get(k)).sort(), ["card", "link"]);
    // Nothing that opts a session out of Adaptive Pricing or fixes its currency by hand.
    assert.deepEqual(keys.filter((k) => /currency_options/.test(k)), [], "currency_options");
    assert.deepEqual(keys.filter((k) => /capture_method/.test(k)), [], "manual capture");
    assert.deepEqual(keys.filter((k) => k.startsWith("adaptive_pricing")), [], "adaptive_pricing must not be set here");
    assert.equal(p.get("currency"), null, "no top-level currency");
    assert.equal(p.get("line_items[0][price_data][currency]") ?? "usd", "usd");
    assert.equal(keys.filter((k) => /^line_items\[\d+\]/.test(k) && !k.startsWith("line_items[0]")).length, 0, "one line item");
    if (cents === null) {
      assert.equal(p.get("line_items[0][price]"), "price_dummy");
      assert.equal(p.get("line_items[0][price_data][unit_amount]"), null);
    } else {
      assert.equal(p.get("line_items[0][price_data][currency]"), "usd");
      assert.equal(p.get("line_items[0][price_data][unit_amount]"), String(cents));
    }
  });
}

test("ModernTex is 19.99 USD in the catalog and in the session", async () => {
  const p = await session("moderntex", {});
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "1999");
  const src = readFileSync(new URL("../functions/checkout.mjs", import.meta.url), "utf8");
  assert.match(src, /"moderntex":\s*\{ amount: 1999,/);
});

test("the inline amounts in the catalog equal the ones this test expects", () => {
  const src = readFileSync(new URL("../functions/checkout.mjs", import.meta.url), "utf8");
  for (const [product, { cents }] of Object.entries(MAC_APPS)) {
    if (cents === null || product.startsWith("bundle-") || product === "moderntex-seats") continue;
    const m = src.match(new RegExp(`"${product}":\\s*\\{ amount: (\\d+),`));
    assert.ok(m, `${product} is not priced inline in PRODUCT_CATALOG`);
    assert.equal(Number(m[1]), cents, product);
  }
  assert.match(src, /"bundle-2":\s*\{ amount: BUNDLES\["bundle-2"\]\.cents,/);
  assert.match(src, /"bundle-3":\s*\{ amount: BUNDLES\["bundle-3"\]\.cents,/);
});

test("seat packs charge the seats.mjs unit price, in USD, for every offered count", async () => {
  for (const seats of [5, 10, 15, 20, 25, 100]) {
    const p = await session("moderntex-seats", { seats });
    assert.equal(p.get("line_items[0][price_data][unit_amount]"), String(seatUnitCents(seats)), `${seats} seats`);
    assert.equal(p.get("line_items[0][quantity]"), String(seats));
    assert.equal(p.get("line_items[0][price_data][currency]"), "usd");
    assert.equal(seatTotalCents(seats), seatUnitCents(seats) * seats);
  }
});
