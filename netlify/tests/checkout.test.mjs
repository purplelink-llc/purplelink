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

import { test, mock } from "node:test";
import assert from "node:assert/strict";

// Stub @netlify/blobs so the rate-limit check doesn't need real credentials.
mock.module("@netlify/blobs", {
  exports: {
    getStore: () => ({
      get: async () => null,
      set: async () => {},
    }),
  },
});

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
