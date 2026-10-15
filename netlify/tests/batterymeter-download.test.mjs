// BatteryMeter delivery: public appcast and release zips served from the batterymeter-files Blobs store.
// Netlify Blobs is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/batterymeter-download.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k, opts) => {
      const v = stores.get(`${name}/${k}`);
      if (v === undefined) return null;
      if (opts?.type === "arrayBuffer") return new TextEncoder().encode(v).buffer;
      return v;
    },
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const handler = (await import("../functions/batterymeter-download.mjs")).default;

const APPCAST = `<rss><channel><item><enclosure url="https://purplelink.llc/batterymeter/BatteryMeter-1.2.1.zip"/></item></channel></rss>`;
const BROWSER = { "user-agent": "Mozilla/5.0 (Macintosh) Safari/605.1.15" };

beforeEach(() => {
  stores.clear();
  stores.set("batterymeter-files/appcast.xml", APPCAST);
  stores.set("batterymeter-files/BatteryMeter-1.2.1.zip", "zipbytes-1.2.1");
});

const call = (path, method = "GET", headers = BROWSER) =>
  handler(new Request(`https://purplelink.llc${path}`, { method, headers }), {});

test("the appcast is XML with a short cache", async () => {
  const res = await call("/batterymeter/appcast.xml");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /^application\/xml/);
  assert.match(res.headers.get("cache-control"), /max-age=300/);
  assert.doesNotMatch(res.headers.get("cache-control"), /immutable/);
  assert.equal(await res.text(), APPCAST);
});

test("a valid zip name is served as an attachment with length and a long cache", async () => {
  const res = await call("/batterymeter/BatteryMeter-1.2.1.zip");
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/zip");
  assert.equal(res.headers.get("content-length"), String(Buffer.byteLength("zipbytes-1.2.1")));
  assert.match(res.headers.get("content-disposition"), /^attachment; filename="BatteryMeter-1\.2\.1\.zip"$/);
  assert.match(res.headers.get("cache-control"), /max-age=31536000/);
  assert.equal(await res.text(), "zipbytes-1.2.1");
});

test("two, three and four part versions match", async () => {
  for (const v of ["1.0", "1.2.1", "1.2.1.4"]) {
    stores.set(`batterymeter-files/BatteryMeter-${v}.zip`, "x");
    assert.equal((await call(`/batterymeter/BatteryMeter-${v}.zip`)).status, 200, v);
  }
});

test("invalid names and traversal are 404", async () => {
  stores.set("batterymeter-files/secret.txt", "nope");
  stores.set("batterymeter-files/BatteryMeter-1.2.1.zip.sha256", "nope");
  const bad = [
    "/batterymeter/secret.txt",
    "/batterymeter/BatteryMeter-1.2.1.zip.sha256",
    "/batterymeter/BatteryMeter-1.zip",
    "/batterymeter/BatteryMeter-1.2.1.5.6.zip",
    "/batterymeter/BatteryMeter-x.y.zip",
    "/batterymeter/batterymeter-1.2.1.zip",
    "/batterymeter/",
    "/batterymeter/..%2Fsecret.txt",
    "/batterymeter/%2e%2e/BatteryMeter-1.2.1.zip",
    "/batterymeter/sub/BatteryMeter-1.2.1.zip",
    "/batterymeter/sub%2FBatteryMeter-1.2.1.zip",
    "/batterymeter/BatteryMeter-1.2.1.zip%00.txt",
    "/batterymeter/appcast.xml/extra",
    "/other/BatteryMeter-1.2.1.zip",
  ];
  for (const p of bad) assert.equal((await call(p)).status, 404, p);
});

test("HEAD returns the same headers with no body", async () => {
  const z = await call("/batterymeter/BatteryMeter-1.2.1.zip", "HEAD");
  assert.equal(z.status, 200);
  assert.equal(z.headers.get("content-length"), String(Buffer.byteLength("zipbytes-1.2.1")));
  assert.equal(await z.text(), "");
  const a = await call("/batterymeter/appcast.xml", "HEAD");
  assert.equal(a.status, 200);
  assert.match(a.headers.get("content-type"), /^application\/xml/);
  assert.equal(await a.text(), "");
});

test("a store miss is 404", async () => {
  assert.equal((await call("/batterymeter/BatteryMeter-9.9.9.zip")).status, 404);
  stores.delete("batterymeter-files/appcast.xml");
  assert.equal((await call("/batterymeter/appcast.xml")).status, 404);
});

test("other methods are 405", async () => {
  assert.equal((await call("/batterymeter/appcast.xml", "POST")).status, 405);
});

test("zip downloads are counted without personal data; HEAD, appcast and crawlers are not", async () => {
  await call("/batterymeter/BatteryMeter-1.2.1.zip");
  await call("/batterymeter/BatteryMeter-1.2.1.zip");
  await call("/batterymeter/BatteryMeter-1.2.1.zip", "HEAD");
  await call("/batterymeter/BatteryMeter-1.2.1.zip", "GET", { "user-agent": "Googlebot/2.1" });
  await call("/batterymeter/appcast.xml");
  const stats = [...stores.entries()].filter(([k]) => k.startsWith("batterymeter-stats/"));
  assert.equal(stores.get("batterymeter-stats/downloads:BatteryMeter-1.2.1.zip"), "2");
  assert.equal(stats.length, 2);
  for (const [k, v] of stats) assert.match(`${k}=${v}`, /^batterymeter-stats\/(downloads:BatteryMeter-1\.2\.1\.zip|day:\d{4}-\d{2}-\d{2})=\d+$/);
});
