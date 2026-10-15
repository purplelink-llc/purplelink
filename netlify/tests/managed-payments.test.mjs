// Stripe Managed Payments in checkout.mjs: off unless STRIPE_MANAGED_PAYMENTS names the product, and when on, the
// session carries managed_payments[enabled], a tax code on inline prices, and none of the parameters Stripe rejects.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/managed-payments.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {} }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

let mpFlag = "";
globalThis.Netlify = {
  env: {
    get: (key) => {
      if (key === "STRIPE_SECRET_KEY") return "sk_test_dummy";
      if (key === "STRIPE_MANAGED_PAYMENTS") return mpFlag;
      if (key.startsWith("STRIPE_PRICE_")) return "price_dummy";
      return undefined;
    },
  },
};

const { default: handler } = await import("../functions/checkout.mjs");
const { managedPaymentsOn, applyManagedPayments, MP_TAX_CODES } = await import("../lib/managed-payments.mjs");

let ipCounter = 10;
async function checkout(product, flag) {
  mpFlag = flag;
  let body = null;
  let idem = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (String(url).includes("api.stripe.com")) {
      body = new URLSearchParams(opts.body);
      idem = opts.headers["Idempotency-Key"];
      return new Response(JSON.stringify({ id: "cs_test_mp", url: "https://checkout.stripe.com/pay/cs_test_mp" }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": `203.0.113.${ipCounter++}` },
      body: JSON.stringify({ product }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
    mpFlag = "";
  }
  return { body, idem };
}

test("the flag is off unless it names the product (or says all) and the product has a tax code", () => {
  for (const off of ["", undefined, "off", "0", "false", "keyfeel"]) assert.equal(managedPaymentsOn("moderntex", off), false, String(off));
  assert.equal(managedPaymentsOn("moderntex", "all"), true);
  assert.equal(managedPaymentsOn("moderntex", " ALL "), true);
  assert.equal(managedPaymentsOn("moderntex", "keyfeel, moderntex"), true);
  assert.equal(managedPaymentsOn("sheet-submission", "all"), false, "products without a tax code never switch on");
  assert.equal(managedPaymentsOn("paper-review-standard", "paper-review-standard"), false);
});

test("every tax code is one of Stripe's eligible downloadable-software codes", () => {
  for (const [product, code] of Object.entries(MP_TAX_CODES)) {
    assert.match(code, /^txcd_1020200[03]$/, product);
  }
});

test("applyManagedPayments removes the parameters Stripe rejects and keeps everything else", () => {
  const p = applyManagedPayments({
    mode: "payment",
    "payment_method_types[0]": "card",
    "payment_method_types[1]": "link",
    "automatic_tax[enabled]": "true",
    "payment_intent_data[receipt_email]": "a@b.c",
    "payment_intent_data[statement_descriptor_suffix]": "X",
    "line_items[0][price_data][product_data][name]": "ModernTex for macOS",
    "metadata[product]": "moderntex",
    "custom_fields[0][key]": "heard",
    allow_promotion_codes: "true",
  }, "moderntex");
  assert.deepEqual(Object.keys(p).sort(), [
    "allow_promotion_codes", "custom_fields[0][key]", "line_items[0][price_data][product_data][name]",
    "line_items[0][price_data][product_data][tax_code]", "managed_payments[enabled]", "metadata[product]", "mode",
  ]);
  assert.equal(p["managed_payments[enabled]"], "true");
  assert.equal(p["line_items[0][price_data][product_data][tax_code]"], "txcd_10202000");
});

test("flag off: ModernTex checkout is exactly as before (card and Link, no managed_payments, no tax code)", async () => {
  const { body } = await checkout("moderntex", "");
  assert.equal(body.get("payment_method_types[0]"), "card");
  assert.equal(body.get("payment_method_types[1]"), "link");
  assert.equal(body.get("managed_payments[enabled]"), null);
  assert.equal(body.get("line_items[0][price_data][product_data][tax_code]"), null);
});

test("flag on for ModernTex: managed, tax-coded inline price, no payment_method_types, metadata and questions kept", async () => {
  const { body } = await checkout("moderntex", "moderntex");
  assert.equal(body.get("managed_payments[enabled]"), "true");
  assert.equal(body.get("line_items[0][price_data][product_data][tax_code]"), "txcd_10202000");
  assert.equal(body.get("line_items[0][price_data][unit_amount]"), "1999");
  assert.equal(body.get("payment_method_types[0]"), null);
  assert.equal(body.get("metadata[product]"), "moderntex");
  assert.equal(body.get("custom_fields[0][key]"), "heard");
  assert.equal(body.get("allow_promotion_codes"), "true");
  assert.equal(body.get("customer_creation"), "if_required");
});

test("flag all: a Stripe-Price product (Legroom) is managed but gets no inline tax code (it lives on the Stripe product)", async () => {
  const { body } = await checkout("legroom", "all");
  assert.equal(body.get("managed_payments[enabled]"), "true");
  assert.equal(body.get("line_items[0][price]"), "price_dummy");
  assert.equal(body.get("line_items[0][price_data][product_data][tax_code]"), null);
  assert.equal(body.get("payment_method_types[0]"), null);
});

test("flag all: products outside the list (a spreadsheet) are untouched", async () => {
  const { body } = await checkout("sheet-submission", "all");
  assert.equal(body.get("managed_payments[enabled]"), null);
  assert.equal(body.get("payment_method_types[0]"), "card");
});

test("the idempotency key differs between a managed and an unmanaged session, so Stripe never sees one key with two param sets", async () => {
  const off = await checkout("keyfeel", "");
  ipCounter -= 1; // same client IP for both calls
  const on = await checkout("keyfeel", "keyfeel");
  assert.notEqual(off.idem, on.idem);
});
