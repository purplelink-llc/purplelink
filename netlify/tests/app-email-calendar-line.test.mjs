// Holiday 2026: the app download emails carry one approved line about the printable 2027 photo calendars,
// until 2027-01-15. Photo, calendar, kit and sheet buyers never get it.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/app-email-calendar-line.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

globalThis.Netlify = { env: { get: () => undefined } };
const { calendarOffer, CALENDAR_LINE_LAST_DAY_MS } = await import("../functions/stripe-webhook.mjs");

const before = Date.UTC(2026, 10, 3);
const APPROVED =
  "If you need a small gift this season: I also make printable 2027 wall calendars from my travel photographs " +
  "(Iceland, Japan, Switzerland and four more), $7 each or all seven for $19.";

test("every app product gets the approved line and a tagged link", () => {
  for (const k of ["moderntex", "moderntex-seats", "outbound-veil", "legroom", "keyfeel", "tapefolio", "panely", "summonly",
    "app-suite", "bundle-2", "bundle-3"]) {
    const o = calendarOffer(k, before);
    assert.ok(o.text.startsWith(APPROVED), k);
    assert.match(o.text, /https:\/\/purplelink\.llc\/photography\/calendars\/\?utm_source=app-email&utm_medium=email&utm_campaign=holiday-2026&utm_content=app-email-calendars/);
    assert.ok(o.html.includes(APPROVED), k);
  }
});

test("photo, calendar, kit and sheet buyers get nothing", () => {
  for (const k of ["photo-license-web", "photo-calendar-iceland", "photo-calendar-bundle", "kit-bundle", "sheet-bundle", "live-scholar"]) {
    assert.deepEqual(calendarOffer(k, before), { text: "", html: "" }, k);
  }
});

test("the line drops out after January 15, 2027", () => {
  assert.notEqual(calendarOffer("moderntex", CALENDAR_LINE_LAST_DAY_MS).text, "");
  assert.deepEqual(calendarOffer("moderntex", CALENDAR_LINE_LAST_DAY_MS + 1), { text: "", html: "" });
});

test("no em dashes, no emoji in the copy", () => {
  const o = calendarOffer("legroom", before);
  assert.doesNotMatch(o.text + o.html, /[—]|\p{Extended_Pictographic}/u);
});
