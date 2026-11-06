// Barroom update channel: token-gated Sparkle feed and DMG door; no purchase or trial door yet. Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/barroom-download.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    list: async ({ prefix = "" } = {}) => ({
      blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/${prefix}`)).map((k) => ({ key: k.slice(name.length + 1) })),
    }),
    getWithMetadata: async (k) => (stores.has(`${name}/${k}`) ? { data: new Response(`bytes:${k}`).body, metadata: { size: 9 } } : null),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const TOKEN = "tok_barroom_test_0123456789";
const env = { BARROOM_UPDATE_TOKEN: TOKEN };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const handler = (await import("../functions/barroom-download.mjs")).default;

beforeEach(() => {
  stores.clear();
  env.BARROOM_UPDATE_TOKEN = TOKEN;
  stores.set("barroom-files/Barroom-0.1.0.dmg", "x");
  stores.set("barroom-files/appcast.xml",
    '<rss><item><enclosure url="https://purplelink.llc/.netlify/functions/Barroom-0.1.0.dmg" sparkle:edSignature="s"/></item></rss>');
});

const call = (query, token = TOKEN, method = "GET") =>
  handler(new Request(`https://purplelink.llc/.netlify/functions/barroom-download?${query}`, {
    method, headers: token ? { "x-barroom-channel": token } : {},
  }), {});

test("the feed needs the channel token", async () => {
  assert.equal((await call("feed=1", "")).status, 403);
  assert.equal((await call("feed=1", "wrong_token_wrong_token_00")).status, 403);
});

test("an unset server token refuses everyone", async () => {
  env.BARROOM_UPDATE_TOKEN = "";
  assert.equal((await call("feed=1", "")).status, 403);
});

test("the feed is served with enclosures pointed at the update door", async () => {
  const res = await call("feed=1");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /rss\+xml/);
  assert.match(await res.text(), /url="https:\/\/purplelink\.llc\/\.netlify\/functions\/barroom-download\?update=Barroom-0\.1\.0\.dmg"/);
});

test("a signed feed is served byte for byte", async () => {
  const signed = '<rss><enclosure url="https://x/Barroom-0.1.0.dmg"/></rss>\n<!-- sparkle-signatures:\nabc -->';
  stores.set("barroom-files/appcast.xml", signed);
  assert.equal(await (await call("feed=1")).text(), signed);
});

test("no feed staged answers 404", async () => {
  stores.delete("barroom-files/appcast.xml");
  assert.equal((await call("feed=1")).status, 404);
});

test("an update streams the DMG and counts it", async () => {
  const res = await call("update=Barroom-0.1.0.dmg");
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/x-apple-diskimage");
  assert.equal(await res.text(), "bytes:Barroom-0.1.0.dmg");
  const stats = await (await call("stats=1")).json();
  assert.deepEqual(stats.downloads, { "Barroom-0.1.0.dmg": 1 });
});

test("only versioned Barroom DMG names are served", async () => {
  assert.equal((await call("update=../appcast.xml")).status, 400);
  assert.equal((await call("update=Lenses-1.0.0.dmg")).status, 400);
  assert.equal((await call("update=Barroom-9.9.9.dmg")).status, 404);
});

test("there is no purchase or trial door yet", async () => {
  assert.equal((await call("trial=1", "")).status, 404);
  assert.equal((await call("session_id=cs_live_abcdefghij1234", "")).status, 404);
  assert.equal((await call("feed=1", TOKEN, "POST")).status, 405);
});
