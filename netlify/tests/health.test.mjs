// health.mjs is the uptime probe: 200 when Blobs answers a read, 503 when it does not, no writes.
// Run with: node --experimental-test-module-mocks --test netlify/tests/health.test.mjs
import { test, mock } from "node:test";
import assert from "node:assert/strict";

let fail = false;
const writes = [];
const blobsModule = {
  getStore: () => ({
    get: async () => { if (fail) throw new Error("blobs down"); return null; },
    set: async (k) => { writes.push(k); },
    delete: async (k) => { writes.push(k); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
const health = (await import("../functions/health.mjs")).default;
const url = "https://purplelink.llc/.netlify/functions/health";

test("200 and ok when Blobs answers; nothing is written", async () => {
  const res = await health(new Request(url));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  assert.deepEqual(writes, []);
});

test("503 when the Blobs read fails", async () => {
  fail = true;
  const res = await health(new Request(url));
  assert.equal(res.status, 503);
  fail = false;
});

test("only GET and HEAD are answered", async () => {
  assert.equal((await health(new Request(url, { method: "POST" }))).status, 405);
});
