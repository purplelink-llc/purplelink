#!/usr/bin/env node
// Test-mode smoke test for Stripe Managed Payments (netlify/lib/managed-payments.mjs).
//
// Runs the real netlify/functions/checkout.mjs handler against Stripe's TEST API with STRIPE_MANAGED_PAYMENTS=all and
// prints one hosted Checkout URL per product, so a person can open it, try billing addresses in different countries
// to see the tax Stripe adds, and pay with the test card 4242 4242 4242 4242.
//
// Prerequisites (both in Stripe's TEST mode or a sandbox):
//   1. Managed Payments enabled and its terms accepted: https://dashboard.stripe.com/test/settings/managed-payments
//   2. A test secret key in the macOS keychain (never in a file or the repo):
//        security add-generic-password -a purplelink -s stripe-test-secret -w
//      (it prompts for the key; paste the sk_test_... value there)
//
// Usage:
//   node --experimental-test-module-mocks scripts/stripe-mp-smoke.mjs [product ...]
// Default products: the inline-priced Mac apps (moderntex keyfeel tapefolio panely summonly app-suite bundle-2
// moderntex-seats). Outbound Veil and Legroom sell through live Stripe Price ids that do not exist in test mode.
//
// It refuses any key that is not sk_test_ or rk_test_, so it can never create a live session.

import { execFileSync } from "node:child_process";
import { mock } from "node:test";

const key = (() => {
  try {
    return execFileSync("security", ["find-generic-password", "-a", "purplelink", "-s", "stripe-test-secret", "-w"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "";
  }
})();
if (!/^(sk|rk)_test_/.test(key)) {
  console.error("No Stripe TEST key in the keychain (service stripe-test-secret), or it is not a test key. Nothing was sent.");
  process.exit(2);
}

// Blobs are only used for rate limiting; a no-op store keeps this run off the production stores.
const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {}, setJSON: async () => {}, getWithMetadata: async () => null }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

globalThis.Netlify = {
  env: {
    get: (k) => (k === "STRIPE_SECRET_KEY" ? key : k === "STRIPE_MANAGED_PAYMENTS" ? "all" : undefined),
  },
};

const { default: handler } = await import("../netlify/functions/checkout.mjs");

const BODIES = {
  "bundle-2": { apps: ["moderntex", "keyfeel"] },
  "moderntex-seats": { seats: 5 },
};
const products = process.argv.slice(2).length
  ? process.argv.slice(2)
  : ["moderntex", "keyfeel", "tapefolio", "panely", "summonly", "app-suite", "bundle-2", "moderntex-seats"];

let failures = 0;
for (const [i, product] of products.entries()) {
  const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
    method: "POST",
    headers: { "content-type": "application/json", origin: "https://purplelink.llc", "x-nf-client-connection-ip": `198.51.100.${i + 1}` },
    body: JSON.stringify({ product, attempt: `mpsmoke${Date.now()}${i}`, ...(BODIES[product] || {}) }),
  }));
  const data = await res.json().catch(() => ({}));
  if (res.status === 200 && data.url) {
    console.log(`OK   ${product.padEnd(16)} ${data.url}`);
  } else {
    failures += 1;
    console.log(`FAIL ${product.padEnd(16)} HTTP ${res.status} ${JSON.stringify(data).slice(0, 300)}`);
  }
}
process.exit(failures ? 1 : 0);
