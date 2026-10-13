// Owner-token checks: constant-time compare, header or query token (S-07), bearer secret compare (S-08).
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/owner-auth.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";

const blobsModule = {
  getStore: () => ({
    get: async () => null,
    set: async () => {},
    setJSON: async () => {},
    list: async () => ({ blobs: [] }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: (k) => (k === "STATS_TOKEN" ? "tok-123" : undefined) } };
process.env.SUBSCRIBE_SECRET = "sub-secret";

const { safeEqual, ownerToken, bearerMatches } = await import("../lib/auth.mjs");
const stats = (await import("../functions/stats.mjs")).default;
const sales = (await import("../functions/sales.mjs")).default;
const subscribersList = (await import("../functions/subscribers-list.mjs")).default;

const req = (path, headers = {}) => new Request(`https://purplelink.llc/.netlify/functions/${path}`, { headers });

test("safeEqual: equal, different, different length, empty and non-string", () => {
  assert.equal(safeEqual("abc", "abc"), true);
  assert.equal(safeEqual("abd", "abc"), false);
  assert.equal(safeEqual("abcd", "abc"), false);
  assert.equal(safeEqual("", ""), false);
  assert.equal(safeEqual("x", undefined), false);
  assert.equal(safeEqual(undefined, "x"), false);
});

test("ownerToken reads Bearer, x-stats-token, then the query parameter", () => {
  assert.equal(ownerToken(req("stats", { authorization: "Bearer abc" })), "abc");
  assert.equal(ownerToken(req("stats", { "x-stats-token": "def" })), "def");
  assert.equal(ownerToken(req("stats?token=ghi")), "ghi");
  assert.equal(ownerToken(req("stats")), "");
});

test("stats accepts the token in a header or the query, rejects others", async () => {
  assert.equal((await stats(req("stats?days=1"))).status, 401);
  assert.equal((await stats(req("stats?days=1&token=wrong"))).status, 401);
  assert.equal((await stats(req("stats?days=1", { authorization: "Bearer wrong" }))).status, 401);
  assert.equal((await stats(req("stats?days=1", { authorization: "Bearer tok-123" }))).status, 200);
  assert.equal((await stats(req("stats?days=1", { "x-stats-token": "tok-123" }))).status, 200);
  assert.equal((await stats(req("stats?days=1&token=tok-123"))).status, 200);
});

test("sales rejects a wrong or missing token and checks before touching Stripe", async () => {
  assert.equal((await sales(req("sales"))).status, 401);
  assert.equal((await sales(req("sales?token=nope"))).status, 401);
  assert.equal((await sales(req("sales", { "x-stats-token": "nope" }))).status, 401);
  // A right token passes auth and then stops at the missing Stripe key (500), not at 401.
  assert.equal((await sales(req("sales", { authorization: "Bearer tok-123" }))).status, 500);
});

test("bearer secret compare", async () => {
  assert.equal(bearerMatches(req("x", { authorization: "Bearer sub-secret" }), "sub-secret"), true);
  assert.equal(bearerMatches(req("x", { authorization: "Bearer sub-secreT" }), "sub-secret"), false);
  assert.equal(bearerMatches(req("x"), "sub-secret"), false);
  assert.equal((await subscribersList(req("subscribers-list"))).status, 401);
  assert.equal((await subscribersList(req("subscribers-list", { authorization: "Bearer bad" }))).status, 401);
  assert.notEqual((await subscribersList(req("subscribers-list", { authorization: "Bearer sub-secret" }))).status, 401);
});
