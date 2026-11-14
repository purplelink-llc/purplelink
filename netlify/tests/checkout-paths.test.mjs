// Every product's success and cancel pages exist in site/. The response-draft cancel URL pointed at
// /tools/response-review/draft/, a page that was never built, so a buyer who backed out of Stripe landed on a 404
// (found on live 2026-11-14). Lab plans now return to /labs/, where their buy buttons are.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/checkout-paths.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {} }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: () => undefined } };

const { PRODUCT_CATALOG, cancelPathFor } = await import("../functions/checkout.mjs");
const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const page = (p) => existsSync(join(SITE, p, "index.html"));

test("every catalog entry's success page exists", () => {
  for (const [key, entry] of Object.entries(PRODUCT_CATALOG)) {
    assert.ok(page(entry.successPath), `${key}: ${entry.successPath} has no page`);
  }
});

test("every catalog entry's cancel page exists and is not a paid page", () => {
  for (const [key, entry] of Object.entries(PRODUCT_CATALOG)) {
    const p = cancelPathFor(entry);
    assert.ok(page(p), `${key}: canceled checkout returns to ${p}, which has no page`);
    assert.doesNotMatch(p, /\/(upload|compose|success|subscribed|setup)\/$/, `${key}: cancel lands on a paid page`);
  }
});

test("lab plans return to /labs/ and response-draft to the Response Review page", () => {
  for (const k of ["lab-monthly", "lab-annual", "lab-plus-monthly", "lab-plus-annual"]) assert.equal(cancelPathFor(PRODUCT_CATALOG[k]), "/labs/");
  assert.equal(cancelPathFor(PRODUCT_CATALOG["response-draft"]), "/tools/response-review/");
  assert.equal(cancelPathFor(PRODUCT_CATALOG["paper-review-deep"]), "/tools/paper-review/");
});
