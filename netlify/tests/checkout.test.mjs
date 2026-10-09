// Regression test for the Origin-allowlist fix in checkout.mjs.
//
// Security finding: success_url/cancel_url were built from the raw request
// Origin header with no allowlist check, letting an attacker (e.g.
// https://evil.com) get back a genuine Stripe Checkout URL whose
// success_url points at their own domain — leaking the live session_id
// (a bearer credential for /paper-review/redeem-session) to them once the
// victim completes payment.
//
// This test stubs the Stripe API call and Netlify Blobs store, then asserts
// that an untrusted Origin header is ignored in favor of the hardcoded
// default, while an allowlisted origin is honored.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/checkout.test.mjs

import { readFileSync } from "node:fs";
import { test, mock } from "node:test";
import assert from "node:assert/strict";

// Stub @netlify/blobs so the rate-limit check doesn't need real credentials.
const blobsModule = {
  getStore: () => ({
    get: async () => null,
    set: async () => {},
  }),
};
// `exports` on newer Node (Node 26 rejects both together), `namedExports` on Node 22.
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

globalThis.Netlify = {
  env: {
    get: (key) => {
      if (key === "STRIPE_SECRET_KEY") return "sk_test_dummy";
      if (key.startsWith("STRIPE_PRICE_")) return "price_dummy";
      return undefined;
    },
  },
};

const { default: handler } = await import("../functions/checkout.mjs");

async function callHandler({ origin, ip = "203.0.113.1" }) {
  let capturedBody = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (String(url).includes("api.stripe.com")) {
      capturedBody = opts.body;
      return new Response(
        JSON.stringify({ id: "cs_test_123", url: "https://checkout.stripe.com/pay/cs_test_123" }),
        { status: 200 },
      );
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };

  try {
    const headers = { "content-type": "application/json", "x-nf-client-connection-ip": ip };
    if (origin !== undefined) headers.origin = origin;
    const req = new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers,
      body: JSON.stringify({ product: "paper-review-standard" }),
    });
    const res = await handler(req);
    return { res, capturedBody };
  } finally {
    globalThis.fetch = originalFetch;
  }
}

function paramFromBody(body, key) {
  const params = new URLSearchParams(body);
  return params.get(key);
}

test("rejects an attacker-controlled Origin and falls back to the default", async () => {
  const { res, capturedBody } = await callHandler({ origin: "https://evil.com", ip: "203.0.113.10" });
  assert.equal(res.status, 200);
  const successUrl = paramFromBody(capturedBody, "success_url");
  const cancelUrl = paramFromBody(capturedBody, "cancel_url");
  assert.ok(successUrl.startsWith("https://purplelink.llc/"), `expected default origin, got ${successUrl}`);
  assert.ok(cancelUrl.startsWith("https://purplelink.llc/"), `expected default origin, got ${cancelUrl}`);
  assert.ok(!successUrl.includes("evil.com"));
});

test("a canceled checkout returns to the product page, flagged", async () => {
  const { capturedBody } = await callHandler({ origin: "https://purplelink.llc", ip: "203.0.113.13" });
  const cancelUrl = new URL(paramFromBody(capturedBody, "cancel_url"));
  assert.equal(cancelUrl.searchParams.get("checkout"), "canceled");
  assert.ok(!/\/(upload|compose|success)\/$/.test(cancelUrl.pathname), `cancel lands on a paid page: ${cancelUrl.pathname}`);
});

test("honors an allowlisted Origin", async () => {
  const { capturedBody } = await callHandler({ origin: "https://www.purplelink.llc", ip: "203.0.113.11" });
  const successUrl = paramFromBody(capturedBody, "success_url");
  assert.ok(successUrl.startsWith("https://www.purplelink.llc/"), `expected allowlisted origin, got ${successUrl}`);
});

test("falls back to the default when Origin header is absent", async () => {
  const { capturedBody } = await callHandler({ origin: undefined, ip: "203.0.113.12" });
  const successUrl = paramFromBody(capturedBody, "success_url");
  assert.ok(successUrl.startsWith("https://purplelink.llc/"), `expected default origin, got ${successUrl}`);
});

test("the Mac Suite is sold at $54.99 with its own success page and product metadata", async () => {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (String(url).includes("api.stripe.com")) {
      captured = opts.body;
      return new Response(JSON.stringify({ id: "cs_test_suite", url: "https://checkout.stripe.com/pay/cs_test_suite" }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.50" },
      body: JSON.stringify({ product: "app-suite" }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(paramFromBody(captured, "line_items[0][price_data][unit_amount]"), "5499");
  assert.equal(paramFromBody(captured, "line_items[0][price_data][currency]"), "usd");
  assert.equal(paramFromBody(captured, "metadata[product]"), "app-suite");
  assert.ok(paramFromBody(captured, "success_url").startsWith("https://purplelink.llc/suite/success/"));
  assert.equal(paramFromBody(captured, "mode"), "payment");
  assert.ok(!paramFromBody(captured, "line_items[0][price_data][recurring][interval]"), "one-time, not a subscription");
});

test("Legroom checks out with its Stripe price, its own success page and product metadata", async () => {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (String(url).includes("api.stripe.com")) {
      captured = opts.body;
      return new Response(JSON.stringify({ id: "cs_test_legroom", url: "https://checkout.stripe.com/pay/cs_test_legroom" }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.51" },
      body: JSON.stringify({ product: "legroom" }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(paramFromBody(captured, "line_items[0][price]"), "price_dummy");
  assert.equal(paramFromBody(captured, "metadata[product]"), "legroom");
  assert.ok(paramFromBody(captured, "success_url").startsWith("https://purplelink.llc/legroom/success/"));
  assert.ok(paramFromBody(captured, "cancel_url").startsWith("https://purplelink.llc/legroom/?checkout=canceled"));
  assert.equal(paramFromBody(captured, "mode"), "payment");
});

test("the Mac Suite checkout line names all six apps", async () => {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (String(url).includes("api.stripe.com")) {
      captured = opts.body;
      return new Response(JSON.stringify({ id: "cs_test_suite5", url: "https://checkout.stripe.com/pay/cs_test_suite5" }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.52" },
      body: JSON.stringify({ product: "app-suite" }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  const name = paramFromBody(captured, "line_items[0][price_data][product_data][name]");
  for (const app of ["ModernTex", "Outbound Veil", "Legroom", "Keyfeel", "Tapefolio", "Vitae Plus"]) assert.ok(name.includes(app), `${app} missing from "${name}"`);
});

test("Keyfeel checks out at $9.99, priced inline, with its own success page and product metadata", async () => {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (String(url).includes("api.stripe.com")) {
      captured = opts.body;
      return new Response(JSON.stringify({ id: "cs_test_keyfeel", url: "https://checkout.stripe.com/pay/cs_test_keyfeel" }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.53" },
      body: JSON.stringify({ product: "keyfeel" }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(paramFromBody(captured, "line_items[0][price_data][unit_amount]"), "999");
  assert.equal(paramFromBody(captured, "line_items[0][price_data][currency]"), "usd");
  assert.equal(paramFromBody(captured, "line_items[0][price_data][product_data][name]"), "Keyfeel for macOS");
  assert.ok(!paramFromBody(captured, "line_items[0][price]"), "inline price, no Stripe Price id");
  assert.equal(paramFromBody(captured, "metadata[product]"), "keyfeel");
  assert.ok(paramFromBody(captured, "success_url").startsWith("https://purplelink.llc/keyfeel/success/"));
  assert.ok(paramFromBody(captured, "cancel_url").startsWith("https://purplelink.llc/keyfeel/?checkout=canceled"));
  assert.equal(paramFromBody(captured, "mode"), "payment");
});

test("Tapefolio checks out at $29.99, priced inline, with its own success page, product metadata and promotion codes", async () => {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (String(url).includes("api.stripe.com")) {
      captured = opts.body;
      return new Response(JSON.stringify({ id: "cs_test_tapefolio", url: "https://checkout.stripe.com/pay/cs_test_tapefolio" }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.54" },
      body: JSON.stringify({ product: "tapefolio" }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(paramFromBody(captured, "line_items[0][price_data][unit_amount]"), "2999");
  assert.equal(paramFromBody(captured, "line_items[0][price_data][currency]"), "usd");
  assert.equal(paramFromBody(captured, "line_items[0][price_data][product_data][name]"), "Tapefolio for macOS");
  assert.ok(!paramFromBody(captured, "line_items[0][price]"), "inline price, no Stripe Price id");
  assert.equal(paramFromBody(captured, "metadata[product]"), "tapefolio");
  assert.ok(paramFromBody(captured, "success_url").startsWith("https://purplelink.llc/tapefolio/success/"));
  assert.ok(paramFromBody(captured, "cancel_url").startsWith("https://purplelink.llc/tapefolio/?checkout=canceled"));
  assert.equal(paramFromBody(captured, "mode"), "payment");
  assert.equal(paramFromBody(captured, "allow_promotion_codes"), "true", "a 100%-off test code can be entered");
});

test("the Suite price did not move when Tapefolio joined: still $54.99", async () => {
  const src = readFileSync(new URL("../functions/checkout.mjs", import.meta.url), "utf8");
  assert.match(src, /"app-suite":\s+\{ amount: 5499,/);
});

async function postRaw(body) {
  const req = new Request("https://purplelink.llc/.netlify/functions/checkout", {
    method: "POST",
    headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.77" },
    body,
  });
  return handler(req);
}

for (const [label, raw] of [
  ["a body that is not JSON", "not json"],
  ["an empty body", ""],
  ["an empty object", "{}"],
  ["a JSON array", "[]"],
  ["a non-string product", JSON.stringify({ product: 5 })],
  ["a prototype-key product", JSON.stringify({ product: "__proto__" })],
]) {
  test(`rejects ${label} with a 400 and no Stripe call`, async () => {
    const originalFetch = globalThis.fetch;
    let called = false;
    globalThis.fetch = async () => { called = true; throw new Error("unexpected fetch"); };
    try {
      const res = await postRaw(raw);
      assert.equal(res.status, 400);
      assert.equal(called, false);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
}
