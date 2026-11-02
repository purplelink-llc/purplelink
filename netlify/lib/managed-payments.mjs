// Stripe Managed Payments (Stripe as merchant of record): Stripe collects and remits VAT, GST and US sales tax,
// handles fraud and disputes, and answers transaction-level support questions. Off unless the Netlify env var
// STRIPE_MANAGED_PAYMENTS names the product ("all" turns it on for every product in MP_TAX_CODES, or a
// comma-separated list of product keys turns on just those). Any other product, or an empty variable, builds the
// session exactly as before.
//
// Requirements (docs.stripe.com/payments/managed-payments/update-checkout, read 2026-10-14):
//   - Managed Payments enabled and its terms accepted in the Stripe Dashboard, in the same mode as the key
//     (test and live are separate). Without that Stripe rejects the session and checkout returns 502.
//   - API version 2025-03-31.basil or later (the account default was 2026-06-24.dahlia on 2026-10-14).
//   - Every product has an eligible tax code. Inline prices get it here; products sold through a Stripe Price
//     (Outbound Veil, Legroom) need it set on the Stripe product once per mode: scripts/stripe-mp-tax-codes.mjs.
//   - These Checkout parameters are not allowed and are removed: payment_method_types (Stripe picks the methods),
//     automatic_tax, tax_id_collection, invoice_creation, payment_intent_data.receipt_email and statement
//     descriptors. checkout.mjs only sends payment_method_types today.
//
// Tax codes come from Stripe's eligible list. All of these are desktop apps the buyer downloads with permanent use,
// so "Downloadable Software - personal use". The business/personal split matters only for US sales; confirm the
// choice with the accountant before going live.

export const MP_TAX_CODES = Object.freeze({
  "moderntex": "txcd_10202000",
  "moderntex-seats": "txcd_10202003", // seat packs are bought by labs and departments: business use
  "outbound-veil": "txcd_10202000",
  "legroom": "txcd_10202000",
  "keyfeel": "txcd_10202000",
  "tapefolio": "txcd_10202000",
  "lenscrib": "txcd_10202000",
  "panely": "txcd_10202000",
  "summonly": "txcd_10202000",
  "app-suite": "txcd_10202000",
  "bundle-2": "txcd_10202000",
  "bundle-3": "txcd_10202000",
});

/** True when STRIPE_MANAGED_PAYMENTS turns Managed Payments on for this product key. */
export function managedPaymentsOn(product, flag) {
  if (!Object.hasOwn(MP_TAX_CODES, product)) return false;
  const v = String(flag || "").trim().toLowerCase();
  if (!v || v === "off" || v === "0" || v === "false") return false;
  if (v === "all") return true;
  return v.split(",").map((s) => s.trim()).includes(product);
}

/**
 * Turn a Checkout Session parameter map into a Managed Payments one, in place. Removes the parameters Stripe
 * rejects under Managed Payments and puts the tax code on an inline price. Returns the same object.
 */
export function applyManagedPayments(params, product) {
  for (const k of Object.keys(params)) {
    if (k.startsWith("payment_method_types[") || k.startsWith("automatic_tax[") || k.startsWith("tax_id_collection[")
      || k.startsWith("invoice_creation[") || k === "payment_intent_data[receipt_email]"
      || k.startsWith("payment_intent_data[statement_descriptor")) {
      delete params[k];
    }
  }
  params["managed_payments[enabled]"] = "true";
  if ("line_items[0][price_data][product_data][name]" in params) {
    params["line_items[0][price_data][product_data][tax_code]"] = MP_TAX_CODES[product];
  }
  return params;
}
