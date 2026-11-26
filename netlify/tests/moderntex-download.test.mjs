// ModernTex trial door: before 1.4.0 it serves the retired Trial-named DMG; from 1.4.0 (one download, key after
// 7 days) it serves the newest buyer DMG. Stripe and Netlify Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/moderntex-download.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    list: async () => ({ blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
    getWithMetadata: async (k) => (stores.has(`${name}/${k}`) ? { data: new Response(`bytes:${k}`).body, metadata: { size: 9 } } : null),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

globalThis.Netlify = { env: { get: (k) => (k === "MODERNTEX_UPDATE_TOKEN" ? "test-channel-token" : "") } };
const handler = (await import("../functions/moderntex-download.mjs")).default;

const trial = () =>
  handler(new Request("https://purplelink.llc/.netlify/functions/moderntex-download?trial=1", {
    headers: { "x-nf-client-connection-ip": "198.51.100.9" },
  }), {});

beforeEach(() => {
  stores.clear();
  stores.set("moderntex-files/ModernTex-1.3.6.dmg", "x");
  stores.set("moderntex-files/ModernTex-Trial-1.3.6.dmg", "x");
});

test("while the newest build is older than 1.4.0 the trial door serves the retired trial DMG", async () => {
  const res = await trial();
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-disposition"), /ModernTex-Trial-1\.3\.6\.dmg/);
});

test("from 1.4.0 the trial door serves the same newest DMG buyers get", async () => {
  stores.set("moderntex-files/ModernTex-1.4.0.dmg", "x");
  const res = await trial();
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-disposition"), /filename="ModernTex-1\.4\.0\.dmg"/);
  assert.equal(await res.text(), "bytes:ModernTex-1.4.0.dmg");
});

test("version compare is numeric, so 1.10.0 beats 1.4.0 and 1.3.12 does not count as unified", async () => {
  stores.set("moderntex-files/ModernTex-1.3.12.dmg", "x");
  let res = await trial();
  assert.match(res.headers.get("content-disposition"), /ModernTex-Trial-1\.3\.6\.dmg/);
  stores.set("moderntex-files/ModernTex-1.10.0.dmg", "x");
  res = await trial();
  assert.match(res.headers.get("content-disposition"), /filename="ModernTex-1\.10\.0\.dmg"/);
});

// Betas are named x.y.z-beta.N ("ModernTex-3.5.0-beta.1.dmg"): Sparkle fetches them by name through the update door,
// and the trial and buyer doors never hand them out as "the newest" (even when the appcast cannot be read).
const update = (file) =>
  handler(new Request(`https://purplelink.llc/.netlify/functions/moderntex-download?update=${encodeURIComponent(file)}`, {
    headers: { "x-moderntex-channel": "test-channel-token" },
  }), {});

test("a -beta.N DMG is served by name through the update door", async () => {
  stores.set("moderntex-files/ModernTex-3.4.7.dmg", "x");
  stores.set("moderntex-files/ModernTex-3.5.0-beta.1.dmg", "x");
  const res = await update("ModernTex-3.5.0-beta.1.dmg");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-disposition"), /filename="ModernTex-3\.5\.0-beta\.1\.dmg"/);
  assert.equal(await res.text(), "bytes:ModernTex-3.5.0-beta.1.dmg");
});

test("malformed beta names are still refused at the update door", async () => {
  for (const bad of ["ModernTex-3.5.0-beta.dmg", "ModernTex-3.5.0-rc.1.dmg", "ModernTex-3.5.0 beta 1.dmg"]) {
    const res = await update(bad);
    assert.equal(res.status, 400, bad);
  }
});

test("the newest-DMG pick skips a -beta.N DMG, with or without the appcast", async () => {
  stores.set("moderntex-files/ModernTex-3.4.7.dmg", "x");
  stores.set("moderntex-files/ModernTex-3.5.0-beta.1.dmg", "x");
  let res = await trial();
  assert.match(res.headers.get("content-disposition"), /filename="ModernTex-3\.4\.7\.dmg"/);
  stores.set("moderntex-files/appcast.xml",
    '<rss><channel><item><enclosure url="https://purplelink.llc/.netlify/functions/moderntex-download?update=ModernTex-3.5.0-beta.1.dmg"/><sparkle:channel>beta</sparkle:channel></item>' +
    '<item><enclosure url="https://purplelink.llc/.netlify/functions/moderntex-download?update=ModernTex-3.4.7.dmg"/></item></channel></rss>');
  res = await trial();
  assert.match(res.headers.get("content-disposition"), /filename="ModernTex-3\.4\.7\.dmg"/);
});

test("the feed rewrite points a beta enclosure at the update door", async () => {
  stores.set("moderntex-files/appcast.xml",
    '<rss><item><enclosure url="https://purplelink.llc/.netlify/functions/ModernTex-3.5.0-beta.1.dmg"/></item></rss>');
  const res = await handler(new Request("https://purplelink.llc/.netlify/functions/moderntex-download?feed=1", {
    headers: { "x-moderntex-channel": "test-channel-token" },
  }), {});
  assert.equal(res.status, 200);
  assert.match(await res.text(), /url="https:\/\/purplelink\.llc\/\.netlify\/functions\/moderntex-download\?update=ModernTex-3\.5\.0-beta\.1\.dmg"/);
});
