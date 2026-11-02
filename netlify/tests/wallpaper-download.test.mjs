// Free Mac wallpaper pack: JPEGs and zips streamed from the wallpaper-files Blobs store, counted in wallpaper-stats.
// Netlify Blobs is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/wallpaper-download.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    getWithMetadata: async (k, opts) => {
      const v = stores.get(`${name}/${k}`);
      if (v === undefined) return null;
      assert.equal(opts?.type, "stream");
      return { data: new Blob([v]).stream(), metadata: { size: Buffer.byteLength(v) } };
    },
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const handler = (await import("../functions/wallpaper-download.mjs")).default;

const BROWSER = { "user-agent": "Mozilla/5.0 (Macintosh) Safari/605.1.15" };
const BASE = "/photography/wallpapers/files/";

beforeEach(() => {
  stores.clear();
  stores.set("wallpaper-files/purplelink-waipio-valley-6k.jpg", "jpegbytes");
  stores.set("wallpaper-files/purplelink-matterhorn-riffelsee-macbook.jpg", "jpeg2");
  stores.set("wallpaper-files/purplelink-wallpapers-6k.zip", "zipbytes");
});

const call = (path, method = "GET", headers = BROWSER) =>
  handler(new Request(`https://purplelink.llc${path}`, { method, headers }), {});

test("a wallpaper is a JPEG attachment with its length", async () => {
  const res = await call(`${BASE}purplelink-waipio-valley-6k.jpg`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "image/jpeg");
  assert.equal(res.headers.get("content-length"), String(Buffer.byteLength("jpegbytes")));
  assert.match(res.headers.get("content-disposition"), /^attachment; filename="purplelink-waipio-valley-6k\.jpg"$/);
  assert.equal(await res.text(), "jpegbytes");
});

test("the pack is a zip; the rewrite's ?file= form works too", async () => {
  const res = await call(`/.netlify/functions/wallpaper-download?file=purplelink-wallpapers-6k.zip`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/zip");
  assert.equal(await res.text(), "zipbytes");
});

test("invalid names and traversal are 404", async () => {
  stores.set("wallpaper-files/secret.txt", "nope");
  const bad = [
    `${BASE}secret.txt`,
    `${BASE}purplelink-waipio-valley-4k.jpg`,
    `${BASE}purplelink-waipio-valley-6k.jpeg`,
    `${BASE}purplelink-wallpapers-all.zip`,
    `${BASE}Purplelink-waipio-valley-6k.jpg`,
    `${BASE}..%2Fsecret.txt`,
    `${BASE}sub/purplelink-waipio-valley-6k.jpg`,
    `${BASE}purplelink-waipio-valley-6k.jpg%00.txt`,
    `${BASE}`,
    "/other/purplelink-waipio-valley-6k.jpg",
  ];
  for (const p of bad) assert.equal((await call(p)).status, 404, p);
});

test("a store miss is 404 and other methods are 405", async () => {
  assert.equal((await call(`${BASE}purplelink-hozu-gorge-kyoto-6k.jpg`)).status, 404);
  assert.equal((await call(`${BASE}purplelink-wallpapers-6k.zip`, "POST")).status, 405);
});

test("downloads are counted per file and per day; HEAD and crawlers are not", async () => {
  await call(`${BASE}purplelink-waipio-valley-6k.jpg`);
  await call(`${BASE}purplelink-wallpapers-6k.zip`);
  await call(`${BASE}purplelink-wallpapers-6k.zip`);
  const head = await call(`${BASE}purplelink-wallpapers-6k.zip`, "HEAD");
  assert.equal(head.status, 200);
  assert.equal(await head.text(), "");
  await call(`${BASE}purplelink-wallpapers-6k.zip`, "GET", { "user-agent": "Googlebot/2.1" });
  assert.equal(stores.get("wallpaper-stats/downloads:purplelink-wallpapers-6k.zip"), "2");
  assert.equal(stores.get("wallpaper-stats/downloads:purplelink-waipio-valley-6k.jpg"), "1");
  const day = [...stores.keys()].find((k) => k.startsWith("wallpaper-stats/day:"));
  assert.match(day, /^wallpaper-stats\/day:\d{4}-\d{2}-\d{2}$/);
  assert.equal(stores.get(day), "3");
});
