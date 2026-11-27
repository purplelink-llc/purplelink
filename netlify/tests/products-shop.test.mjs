// The /products/ storefront (site/products/index.html + shop.js): every Buy button names a real catalog key, shows that
// key's price, and falls back to a page that exists; the bundle tray's display tables equal the server's.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/products-shop.test.mjs

import { readFileSync, existsSync } from "node:fs";
import { test, mock } from "node:test";
import assert from "node:assert/strict";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {}, list: async () => ({ blobs: [] }) }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: () => undefined } };

const { PRODUCT_CATALOG } = await import("../functions/checkout.mjs");
const lib = await import("../lib/bundles.mjs");

const root = new URL("../../site/", import.meta.url);
const html = readFileSync(new URL("products/index.html", root), "utf8");
const shopJs = readFileSync(new URL("products/shop.js", root), "utf8");

// Catalog entries priced only by a Stripe Price id carry no inline amount; their prices as sold today.
const ENV_PRICED = {
  "kit-faceless": 4900, "kit-monetization": 2900, "kit-clip": 1000, "kit-bundle": 5900,
  "outbound-veil": 2999, "legroom": 999, "vitae-plus-monthly": 299, "vitae-plus-annual": 2399,
  "cover-letter": 200, "anonymity-check": 200, "citation-gap": 300, "resume-review": 500,
};
const cents = (key) => PRODUCT_CATALOG[key].amount ?? ENV_PRICED[key];
const dollars = (s) => Math.round(parseFloat(s.replace(/,/g, "")) * 100);

const buys = [...html.matchAll(/<a class="[^"]*shop-buy[^"]*" href="([^"]+)" data-buy="([^"]+)">([^<]+)<\/a>/g)]
  .map((m) => ({ href: m[1], key: m[2], label: m[3], at: m.index }));

test("every data-buy anchor is a well-formed shop-buy link", () => {
  assert.equal(buys.length, (html.match(/data-buy=/g) || []).length);
  assert.ok(buys.length >= 40, `only ${buys.length} Buy buttons`);
  assert.doesNotMatch(html, /id="checkout-btn"|data-checkout/);
});

test("every Buy key is in PRODUCT_CATALOG and shows its price", () => {
  for (const b of buys) {
    assert.ok(PRODUCT_CATALOG[b.key], `${b.key} is not a catalog key`);
    const want = cents(b.key);
    assert.ok(Number.isInteger(want), `no known price for ${b.key}`);
    let shown = b.label.match(/\$([\d,.]+)/);
    if (!shown) {
      // A trial button ("Try 7 days free") takes its price from the shelf item's price line.
      const li = html.lastIndexOf('<li class="shop-shelf-item"', b.at);
      const price = html.slice(li, b.at).match(/class="shop-shelf-price">[^<]*\$([\d,.]+)/);
      assert.ok(price, `${b.key}: no price shown`);
      shown = price;
    }
    assert.equal(dollars(shown[1]), want, `${b.key} shows $${shown[1]}`);
  }
});

test("every Buy link falls back to a page that exists", () => {
  for (const b of buys) {
    const path = b.href.split("#")[0];
    assert.match(path, /^\/[a-z0-9/-]*\/$/, `${b.key}: ${b.href}`);
    assert.ok(existsSync(new URL(`.${path}index.html`, root)), `${b.key}: ${path} has no page`);
  }
});

test("every paid app, the Suite and Vitae Plus can be bought from the store", () => {
  const keys = new Set(buys.map((b) => b.key));
  for (const k of [...lib.BUNDLE_SLUGS.filter((s) => s !== "vitae-plus"), "app-suite", "vitae-plus-annual", "vitae-plus-monthly"]) {
    assert.ok(keys.has(k), `no Buy button for ${k}`);
  }
  const bundled = new Set([...html.matchAll(/data-bundle="([^"]+)"/g)].map((m) => m[1]));
  assert.deepEqual([...bundled].sort(), [...lib.BUNDLE_SLUGS].sort());
});

test("shop.js display tables equal bundles.mjs", () => {
  const table = (name) => JSON.parse(shopJs.match(new RegExp(`var ${name} = (\\{[^;]*\\});`))[1]);
  assert.deepEqual(table("PART_PRICE"), lib.PART_CENTS);
  assert.deepEqual(Object.keys(table("PART_NAME")).sort(), [...lib.BUNDLE_SLUGS].sort());
  const pct = Object.fromEntries(Object.values(lib.BUNDLES).map((b) => [String(b.count), b.percent]));
  assert.deepEqual(table("BUNDLE_PERCENT"), pct);
  assert.equal(Number(shopJs.match(/var SUITE_CENTS = (\d+);/)[1]), PRODUCT_CATALOG["app-suite"].amount ?? 5999);
});
