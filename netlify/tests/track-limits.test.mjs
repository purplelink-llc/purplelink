// track.mjs abuse limits: body size cap, event-type shape, per-IP daily cap (S-06).
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/track-limits.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
let limiterDown = false;
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => { if (limiterDown && name === "rate-limits") throw new Error("down"); return stores.get(`${name}/${k}`) ?? null; },
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    setJSON: async (k, v) => { stores.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { default: track, MAX_BODY_BYTES, DAILY_EVENT_LIMIT } = await import("../functions/track.mjs");

const post = (body, ip = "203.0.113.9", headers = {}) => track(new Request("https://purplelink.llc/.netlify/functions/track", {
  method: "POST",
  headers: { "user-agent": "Mozilla/5.0", "x-nf-client-connection-ip": ip, ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body),
}), {});
const events = () => [...stores.keys()].filter((k) => k.startsWith("analytics/ev/"));

beforeEach(() => stores.clear());

test("a normal beacon is recorded and answered 204", async () => {
  const r = await post({ t: "pageview", p: "/", h: "purplelink.llc" });
  assert.equal(r.status, 204);
  assert.equal(events().length, 1);
});

test("an oversized body is dropped, by header and by actual length", async () => {
  const big = { t: "pageview", p: "/", m: "x".repeat(MAX_BODY_BYTES + 10) };
  assert.equal((await post(big)).status, 204);
  assert.equal((await post({ t: "pageview" }, "203.0.113.9", { "content-length": String(MAX_BODY_BYTES + 1) })).status, 204);
  assert.equal(events().length, 0);
});

test("event types must be short lowercase words; others are dropped", async () => {
  for (const t of ["Pageview", "a b", "x".repeat(33), "<script>", "../x", ["a"]]) {
    await post({ t, p: "/" });
  }
  assert.equal(events().length, 0);
  await post({ t: "ov_trial_download", p: "/" });
  await post({ p: "/" }); // no type still defaults to pageview
  assert.equal(events().length, 2);
});

test("null, array and non-JSON bodies do not throw", async () => {
  for (const b of ["null", "[]", "not json", "5", ""]) assert.equal((await post(b)).status, 204);
  assert.equal(events().length, 0);
});

test("one address is capped per day; another address is unaffected; the key is hashed", async () => {
  for (let i = 0; i < DAILY_EVENT_LIMIT + 20; i++) await post({ t: "pageview", p: "/" }, "198.51.100.7");
  assert.equal(events().length, DAILY_EVENT_LIMIT);
  await post({ t: "pageview", p: "/" }, "198.51.100.8");
  assert.equal(events().length, DAILY_EVENT_LIMIT + 1);
  const limiterKeys = [...stores.keys()].filter((k) => k.startsWith("rate-limits/"));
  assert.equal(limiterKeys.some((k) => k.includes("198.51.100")), false);
});

test("a limiter failure still records the event", async () => {
  limiterDown = true;
  try { await post({ t: "pageview", p: "/" }); } finally { limiterDown = false; }
  assert.equal(events().length, 1);
});
