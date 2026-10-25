// Vitae new-user downloads: counters, the per-download event (daily visitor hash + client class) and the own-IP
// exclusion. Netlify Blobs and Netlify.env are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/vitae-download.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

const stores = new Map();
const store = (name) => ({
  get: async (k) => { const v = stores.get(`${name}/${k}`); return v === undefined ? null : v; },
  set: async (k, v) => { stores.set(`${name}/${k}`, v); },
  setJSON: async (k, v) => { stores.set(`${name}/${k}`, JSON.stringify(v)); },
  list: async () => ({
    blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })),
  }),
  getMetadata: async (k) => (stores.has(`${name}/${k}`) ? {} : null),
  getWithMetadata: async (k) => (stores.has(`${name}/${k}`) ? { data: stores.get(`${name}/${k}`), metadata: {} } : null),
});
const blobsModule = { getStore: store };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const handler = (await import("../functions/vitae-download.mjs")).default;
const { clientClass, isOwnIp, visitorId } = await import("../lib/visitor.mjs");

const SAFARI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15";
const day = () => new Date().toISOString().slice(0, 10);

beforeEach(() => {
  stores.clear();
  for (const k of Object.keys(env)) delete env[k];
  stores.set("vitae-files/Vitae-1.8.2.dmg", "dmg");
});

const download = (ip, ua = SAFARI) =>
  handler(new Request("https://purplelink.llc/.netlify/functions/vitae-download", {
    headers: { "user-agent": ua, "x-nf-client-connection-ip": ip },
  }));

const events = () =>
  [...stores.entries()].filter(([k]) => k.startsWith(`vitae-stats/ev:${day()}:`)).map(([, v]) => JSON.parse(v));

test("a browser download is counted and writes one event with the beacon's visitor hash", async () => {
  const res = await download("203.0.113.7");
  assert.equal(res.status, 200);
  assert.equal(stores.get(`vitae-stats/day:${day()}`), "1");
  assert.equal(stores.get("vitae-stats/downloads:Vitae-1.8.2.dmg"), "1");
  const ev = events();
  assert.equal(ev.length, 1);
  const beaconVid = createHash("sha256").update(`${day()}|pl|203.0.113.7`).digest("hex").slice(0, 16);
  assert.deepEqual({ ...ev[0], ts: 0 }, { ts: 0, file: "Vitae-1.8.2.dmg", vid: beaconVid, cls: "browser", counted: true, own: false });
});

test("a crawler is served, not counted, and recorded as a crawler", async () => {
  const res = await download("198.51.100.1", "Googlebot/2.1 (+http://www.google.com/bot.html)");
  assert.equal(res.status, 200);
  assert.equal(stores.get(`vitae-stats/day:${day()}`), undefined);
  assert.equal(events()[0].cls, "crawler");
  assert.equal(events()[0].counted, false);
});

test("our own IPv4 and IPv6 /64 are served but not counted", async () => {
  env.PURPLELINK_OWN_IPS = "192.0.2.10, 2001:db8:2c93:f880::/64";
  for (const ip of ["192.0.2.10", "2001:db8:2c93:f880:bc:d39c:157b:7639", "2001:DB8:2C93:F880::1"]) {
    assert.equal((await download(ip)).status, 200, ip);
  }
  assert.equal(stores.get(`vitae-stats/day:${day()}`), undefined);
  const ev = events();
  assert.equal(ev.length, 3);
  assert.ok(ev.every((e) => e.own === true && e.counted === false));
});

test("an address outside the own list still counts", async () => {
  env.PURPLELINK_OWN_IPS = "192.0.2.10,2001:db8:2c93:f880::/64";
  await download("192.0.2.11");
  await download("2001:db8:2c93:f881::1");
  assert.equal(stores.get(`vitae-stats/day:${day()}`), "2");
});

test("HEAD and update downloads write no event", async () => {
  await handler(new Request("https://purplelink.llc/.netlify/functions/vitae-download", { method: "HEAD", headers: { "user-agent": SAFARI } }));
  await handler(new Request("https://purplelink.llc/.netlify/functions/vitae-download?update=Vitae-1.8.2.dmg", { headers: { "user-agent": "Vitae/28 Sparkle/2.6" } }));
  assert.equal(events().length, 0);
});

test("a failing event write never blocks the download", async () => {
  const realSet = Map.prototype.set;
  stores.set = function (k, v) {
    if (String(k).startsWith("vitae-stats/ev:")) throw new Error("blobs down");
    return realSet.call(this, k, v);
  };
  try {
    const res = await download("203.0.113.9");
    assert.equal(res.status, 200);
    assert.equal(stores.get(`vitae-stats/day:${day()}`), "1");
  } finally {
    delete stores.set;
  }
});

test("helpers: class buckets, own-IP edge cases and the hash", () => {
  assert.equal(clientClass(SAFARI), "browser");
  assert.equal(clientClass(""), "crawler");
  assert.equal(clientClass("curl/8.7.1"), "crawler");
  assert.equal(clientClass("Go-http-client/2.0"), "other");
  assert.equal(clientClass("Vitae/28 CFNetwork/1568 Darwin/25.0.0"), "other");
  assert.equal(isOwnIp("unknown", "unknown"), false);
  assert.equal(isOwnIp("192.0.2.10", ""), false);
  assert.equal(isOwnIp("192.0.2.10", "2001:db8::/64"), false);
  assert.equal(isOwnIp("2001:db8:0:0::5", "2001:db8::/64"), true);
  assert.equal(visitorId("2026-10-25", "203.0.113.7").length, 16);
});
