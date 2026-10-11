// The ModernTex purchase email carries one line about Paper Review and the PRSTART code, for single copies only,
// until the code expires on 2026-12-15.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/moderntex-email-paper-review.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

globalThis.Netlify = { env: { get: () => undefined } };
const { paperReviewOffer, PRSTART_LAST_DAY_MS } = await import("../functions/stripe-webhook.mjs");

const before = Date.UTC(2026, 9, 20);

test("single ModernTex copy gets the line with the code and a tagged link", () => {
  const o = paperReviewOffer("moderntex", before);
  assert.match(o.text, /PRSTART/);
  assert.match(o.text, /December 15/);
  assert.match(o.text, /https:\/\/purplelink\.llc\/tools\/paper-review\/\?utm_source=moderntex/);
  assert.match(o.html, /<a href="https:\/\/purplelink\.llc\/tools\/paper-review\/\?utm_source=moderntex">/);
});

test("other products get nothing", () => {
  for (const k of ["moderntex-seats", "app-suite", "outbound-veil", "legroom", "keyfeel", "tapefolio"]) {
    assert.deepEqual(paperReviewOffer(k, before), { text: "", html: "" });
  }
});

test("the line drops out after the code expires", () => {
  assert.notEqual(paperReviewOffer("moderntex", PRSTART_LAST_DAY_MS).text, "");
  assert.deepEqual(paperReviewOffer("moderntex", PRSTART_LAST_DAY_MS + 1), { text: "", html: "" });
});

test("no em dashes, no semicolons, no emoji in the copy", () => {
  const o = paperReviewOffer("moderntex", before);
  assert.doesNotMatch(o.text + o.html, /[—;]|\p{Extended_Pictographic}/u);
});
