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

globalThis.Netlify = { env: { get: () => "" } };
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
