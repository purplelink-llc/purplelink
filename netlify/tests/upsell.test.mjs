// Thank-you upsell (netlify/lib/upsell.mjs): the hand-picked pairs, the rules that drop a suggestion, the prices,
// and the success-page endpoint that returns them next to the code.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/upsell.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { UPSELL, PAGES, MAX_SUGGESTIONS, suggestionsFor, discounted, money } = await import("../lib/upsell.mjs");
const { RECOVERY_PRODUCTS } = await import("../lib/checkout-recovery.mjs");
const { EXCLUDED, familyOf } = await import("../lib/buyer-codes.mjs");
const { default: offers } = await import("../functions/buyer-offers.mjs");

const site = fileURLToPath(new URL("../../site/", import.meta.url));

test("every suggested product has a price, a page that exists and sells it, and can take a code", () => {
  const all = new Set(Object.values(UPSELL).flat());
  for (const p of all) {
    assert.ok(RECOVERY_PRODUCTS[p], `${p} has no price`);
    assert.ok(PAGES[p], `${p} has no page`);
    assert.ok(!EXCLUDED.has(p), `${p} cannot take a code`);
    const file = `${site}${PAGES[p].slice(1)}index.html`;
    assert.ok(existsSync(file), `${PAGES[p]} is missing`);
    assert.match(readFileSync(file, "utf8"), /checkout-btn|data-product=|buy-btn/, `${PAGES[p]} has no buy button`);
  }
});

test("the price with the code is 30% off, rounded to the cent", () => {
  assert.equal(money(discounted(1999)), "$13.99");
  assert.equal(money(discounted(999)), "$6.99");
  assert.equal(money(discounted(900)), "$6.30");
  assert.equal(money(discounted(600)), "$4.20");
});

test("ModernTex suggests a Standard review and the submission tracker", () => {
  const s = suggestionsFor({ source_product: "moderntex", family: "moderntex", owned_parts: [] });
  assert.deepEqual(s, [
    { product: "paper-review-standard", name: "Paper Review (Standard)", path: "/tools/paper-review/", price: "$9.00", price_with_code: "$6.30" },
    { product: "sheet-submission", name: "Journal Submission & R&R Tracker", path: "/sheets/submission-tracker/", price: "$12.00", price_with_code: "$8.40" },
  ]);
});

test("every Paper Review tier uses the family's list and never suggests Paper Review", () => {
  for (const tier of ["paper-review-standard", "paper-review-deep", "paper-review-pack-5"]) {
    const s = suggestionsFor({ source_product: tier, family: "paper-review", owned_parts: [] });
    assert.deepEqual(s.map((x) => x.product), ["moderntex", "response-review"]);
  }
});

test("a bundle never suggests an app it already includes", () => {
  const s = suggestionsFor({ source_product: "bundle-2", family: "bundle-2", owned_parts: ["moderntex", "tapefolio"] });
  assert.deepEqual(s.map((x) => x.product), ["paper-review-standard", "response-review"]);
  const suite = suggestionsFor({ source_product: "app-suite", family: "app-suite", owned_parts: ["moderntex", "legroom"] });
  assert.ok(suite.every((x) => x.product !== "moderntex"));
});

test("at most two, none from the order's own family, unknown products get none", () => {
  for (const source of Object.keys(UPSELL)) {
    const s = suggestionsFor({ source_product: source, family: familyOf(source), owned_parts: [] });
    assert.ok(s.length <= MAX_SUGGESTIONS);
    assert.ok(s.every((x) => familyOf(x.product) !== familyOf(source)), source);
  }
  assert.deepEqual(suggestionsFor({ source_product: "kit-clip" }), []);
  assert.deepEqual(suggestionsFor(null), []);
});

test("the success page gets the suggestions with the code", async () => {
  store.clear();
  const sid = "cs_live_upsellabcdefg1";
  const expires = Math.floor(Date.now() / 1000) + 86400 * 10;
  store.set(`buyer-codes/session/${sid}`, "PL-ABCDEFGH");
  store.set("buyer-codes/code/PL-ABCDEFGH", JSON.stringify({
    coupon: "xs-pl-abcdefgh", source_product: "outbound-veil", family: "outbound-veil", owned_parts: [], expires,
  }));
  const res = await offers(new Request(`https://purplelink.llc/.netlify/functions/buyer-offers?session_id=${sid}`));
  const body = await res.json();
  assert.equal(body.code, "PL-ABCDEFGH");
  assert.deepEqual(body.suggestions.map((x) => [x.product, x.price, x.price_with_code]),
    [["legroom", "$9.99", "$6.99"], ["keyfeel", "$9.99", "$6.99"]]);
});
