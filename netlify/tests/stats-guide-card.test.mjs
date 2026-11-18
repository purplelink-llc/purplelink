// stats.mjs: exact guide app-card clicks (pageviews whose utm_source is exactly "guide-card") and per-guide pageviews.
// The blob store is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/stats-guide-card.test.mjs

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
const { default: handler } = await import("../functions/stats.mjs");

const TODAY = new Date().toISOString().slice(0, 10);
let n = 0;
const view = (path, extra = {}) =>
  store.set(`ev/${TODAY}/${String(++n).padStart(6, "0")}`, { type: "pageview", path, host: "purplelink.llc", vid: `v${n}`, ts: 1000 + n, ...extra });
const call = async (query = "") => (await handler(new Request(`https://purplelink.llc/.netlify/functions/stats?token=tok&days=1${query}`))).json();

beforeEach(() => { store.clear(); n = 0; });

test("card clicks count by landing path, only for utm_source exactly guide-card", async () => {
  view("/moderntex/", { utm: "guide-card" });
  view("/moderntex/", { utm: "guide-card" });
  view("/keyfeel/", { utm: "guide-card" });
  view("/moderntex/", { utm: "guide-cards" });
  view("/moderntex/", { utm: "Guide-Card" });
  view("/moderntex/", { utm: "google" });
  view("/moderntex/");
  const body = await call();
  assert.deepEqual(body.guideCardClicksByPath, { "/moderntex/": 2, "/keyfeel/": 1 });
});

test("guide pageviews count per exact path, other pages are left out", async () => {
  view("/guides/a/"); view("/guides/a/"); view("/guides/b/");
  view("/moderntex/"); view("/tools/word-counter/");
  const body = await call();
  assert.deepEqual(body.guidePageviewsByPath, { "/guides/a/": 2, "/guides/b/": 1 });
});

test("self-test pageviews and other hosts are not counted", async () => {
  view("/guides/a/", { meta: "__selftest" });
  view("/moderntex/", { utm: "guide-card", meta: "__selftest" });
  view("rubblefront.com/guides/x/", { host: "rubblefront.com", utm: "guide-card" });
  view("/guides/a/");
  const body = await call();
  assert.deepEqual(body.guideCardClicksByPath, {});
  assert.deepEqual(body.guidePageviewsByPath, { "/guides/a/": 1 });
});

test("both objects are capped at 400 paths, busiest kept", async () => {
  for (let i = 0; i < 405; i++) view(`/guides/g${i}/`, { utm: "guide-card" });
  view("/guides/g7/");
  const body = await call();
  assert.equal(Object.keys(body.guidePageviewsByPath).length, 400);
  assert.equal(Object.keys(body.guideCardClicksByPath).length, 400);
  assert.equal(body.guidePageviewsByPath["/guides/g7/"], 2);
});

test("the fields are empty objects when there is no traffic", async () => {
  const body = await call();
  assert.deepEqual(body.guideCardClicksByPath, {});
  assert.deepEqual(body.guidePageviewsByPath, {});
});
