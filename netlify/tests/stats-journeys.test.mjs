// stats.mjs journeys: visitors grouped by their first page of the day (guide, tool, product, other) and how many of
// them reached a product page later that day. The blob store is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/stats-journeys.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const store = new Map();
const blobsModule = {
  getStore: () => ({
    list: async ({ prefix }) => ({ blobs: [...store.keys()].filter((k) => k.startsWith(prefix)).map((key) => ({ key })) }),
    get: async (k) => store.get(k) ?? null,
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

globalThis.Netlify = { env: { get: (k) => ({ STATS_TOKEN: "tok" })[k] } };
const { default: handler, entryKind, productOf, journeysOf } = await import("../functions/stats.mjs");

const TODAY = new Date().toISOString().slice(0, 10);
let n = 0;
const view = (vid, path, ts, host = "purplelink.llc") =>
  store.set(`ev/${TODAY}/${String(++n).padStart(6, "0")}`, { type: "pageview", path, host, vid, ts });
const call = async (query = "") => (await handler(new Request(`https://purplelink.llc/.netlify/functions/stats?token=tok&days=1${query}`))).json();

beforeEach(() => { store.clear(); n = 0; });

test("entry pages are classed by their first path segment", () => {
  assert.equal(entryKind("/guides/overleaf-alternatives/"), "guide");
  assert.equal(entryKind("/tools/word-counter/"), "tool");
  assert.equal(entryKind("/moderntex/"), "product");
  assert.equal(entryKind("/"), "other");
  assert.equal(productOf("/legroom/success/"), "legroom");
  assert.equal(productOf("/guides/x/"), "");
});

test("a guide reader who later opens a product page counts once per product, in time order", async () => {
  view("g1", "/moderntex/", 3000);              // later view, stored first
  view("g1", "/guides/latex-on-mac/", 1000);    // entry
  view("g1", "/moderntex/buy/", 4000);          // same product again
  view("g1", "/keyfeel/", 5000);
  view("g2", "/guides/latex-on-mac/", 1000);    // never reaches a product
  view("t1", "/tools/word-counter/", 1000);
  view("t1", "/vitae/", 2000);
  view("p1", "/moderntex/", 1000);              // lands on a product
  view("o1", "/", 1000);
  view("r1", "rubblefront.com/", 1000, "rubblefront.com"); // another site: excluded
  const body = await call();
  const j = body.journeysByDay[TODAY];
  assert.deepEqual(j.guide, { visitors: 2, reachedProduct: 1, byProduct: { moderntex: 1, keyfeel: 1 } });
  assert.deepEqual(j.tool, { visitors: 1, reachedProduct: 1, byProduct: { vitae: 1 } });
  assert.equal(j.product.visitors, 1);
  assert.deepEqual(j.other, { visitors: 1, reachedProduct: 0, byProduct: {} });
});

test("?host= responses carry no journeys", async () => {
  view("r1", "rubblefront.com/", 1000, "rubblefront.com");
  const body = await call("&host=rubblefront.com");
  assert.equal(body.journeysByDay, undefined);
});

test("journeysOf ignores nothing it was given and never double-counts a visitor", () => {
  const m = new Map([["a", [{ ts: 2, path: "/suite/" }, { ts: 1, path: "/guides/x/" }, { ts: 3, path: "/suite/" }]]]);
  assert.deepEqual(journeysOf(m), { guide: { visitors: 1, reachedProduct: 1, byProduct: { suite: 1 } } });
});
