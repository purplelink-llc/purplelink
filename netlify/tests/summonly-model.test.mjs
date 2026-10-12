// Summonly search model delivery: signed manifest and archive from the private store, a daily cap,
// and nothing else served. Netlify Blobs is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/summonly-model.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    getWithMetadata: async (k) => (stores.has(`${name}/${k}`) ? { data: new Response(`bytes:${k}`).body, metadata: { size: 9 } } : null),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const handler = (await import("../functions/summonly-model.mjs")).default;
const call = (query, method = "GET") => handler(new Request(`https://purplelink.llc/.netlify/functions/summonly-model?${query}`, { method }), {});
const MANIFEST = JSON.stringify({ id: "summonly-embed-1", version: "1", signature: "x" });

beforeEach(() => {
  stores.clear();
  stores.set("summonly-files/model/manifest.json", MANIFEST);
  stores.set("summonly-files/model/summonly-embed-1-1.zip", "zip");
});

test("the manifest is served as JSON with a short public cache", async () => {
  const res = await call("manifest=1");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /application\/json/);
  assert.match(res.headers.get("cache-control"), /max-age=300/);
  assert.equal(await res.text(), MANIFEST);
});

test("no manifest yet gives a plain 404, not a crash", async () => {
  stores.delete("summonly-files/model/manifest.json");
  const res = await call("manifest=1");
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error, "no_model");
});

test("the archive streams with its size and an immutable cache", async () => {
  const res = await call("file=summonly-embed-1-1.zip");
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/zip");
  assert.equal(res.headers.get("content-length"), "9");
  assert.match(res.headers.get("cache-control"), /immutable/);
  assert.equal(await res.text(), "bytes:model/summonly-embed-1-1.zip");
});

test("only archive names of the right shape are served, so the store cannot be browsed", async () => {
  for (const bad of ["../appcast.xml", "appcast.xml", "Summonly-1.0.0.dmg", "summonly-embed-1-1.zip/../x", "summonly-embed-1-1.txt", ""]) {
    const res = await call(`file=${encodeURIComponent(bad)}`);
    assert.equal(res.status, 400, bad);
  }
  assert.equal((await call("")).status, 400);
});

test("a missing archive is a 404 and does not use up the daily allowance", async () => {
  const res = await call("file=summonly-embed-9-9.zip");
  assert.equal(res.status, 404);
  assert.equal(stores.get(`summonly-stats/model-downloads:${new Date().toISOString().slice(0, 10)}`) ?? null, null);
});

test("the daily cap answers 429 with Retry-After", async () => {
  const day = new Date().toISOString().slice(0, 10);
  stores.set(`summonly-stats/model-downloads:${day}`, "300");
  const res = await call("file=summonly-embed-1-1.zip");
  assert.equal(res.status, 429);
  assert.equal(res.headers.get("retry-after"), "3600");
  assert.equal((await call("manifest=1")).status, 200, "the manifest is not capped");
});

test("only GET and HEAD are allowed", async () => {
  assert.equal((await call("manifest=1", "POST")).status, 405);
  assert.equal((await call("file=summonly-embed-1-1.zip", "HEAD")).status, 200);
});
