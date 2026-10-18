// Social poster image host: public, read-only, strict key pattern, content-sniffed. Netlify Blobs is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/social-media.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const opened = [];
const blobsModule = {
  getStore: (name) => {
    opened.push(name);
    return {
      get: async (k) => {
        const v = stores.get(`${name}/${k}`);
        return v === undefined ? null : v.buffer.slice(v.byteOffset, v.byteOffset + v.byteLength);
      },
      list: async () => { throw new Error("list must never be called"); },
      set: async () => { throw new Error("set must never be called"); },
      delete: async () => { throw new Error("delete must never be called"); },
    };
  },
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const handler = (await import("../functions/social-media.mjs")).default;

const PNG_KEY = "a".repeat(40) + ".png";
const JPG_KEY = "b".repeat(40) + ".jpg";
const PNG_BYTES = Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3]);
const JPG_BYTES = Uint8Array.from([0xff, 0xd8, 0xff, 0xe0, 9, 9]);

beforeEach(() => {
  stores.clear();
  opened.length = 0;
  stores.set(`social-media/${PNG_KEY}`, PNG_BYTES);
  stores.set(`social-media/${JPG_KEY}`, JPG_BYTES);
  stores.set(`social-media/${"c".repeat(40)}.png`, new TextEncoder().encode("<html>not an image</html>"));
});

const call = (path, method = "GET") => handler(new Request(`https://purplelink.llc${path}`, { method }), {});

test("a PNG is served with its type, length and a long immutable cache", async () => {
  const res = await call(`/social-media/${PNG_KEY}`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "image/png");
  assert.equal(res.headers.get("content-length"), String(PNG_BYTES.length));
  assert.match(res.headers.get("cache-control"), /immutable/);
  assert.equal(res.headers.get("x-content-type-options"), "nosniff");
  assert.deepEqual(new Uint8Array(await res.arrayBuffer()), PNG_BYTES);
});

test("a JPEG is served as image/jpeg", async () => {
  const res = await call(`/social-media/${JPG_KEY}`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "image/jpeg");
});

test("HEAD returns the headers without a body", async () => {
  const res = await call(`/social-media/${PNG_KEY}`, "HEAD");
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-length"), String(PNG_BYTES.length));
  assert.equal(await res.text(), "");
});

test("the rewrite form ?file= works", async () => {
  assert.equal((await call(`/.netlify/functions/social-media?file=${PNG_KEY}`)).status, 200);
});

test("anything that is not a 40-hex key plus an image extension is a 404", async () => {
  for (const p of [
    "/social-media/", "/social-media", "/social-media/..%2Fsecret.png", "/social-media/../x.png",
    `/social-media/${"a".repeat(39)}.png`, `/social-media/${"a".repeat(41)}.png`, `/social-media/${"A".repeat(40)}.png`,
    `/social-media/${"a".repeat(40)}.svg`, `/social-media/${"a".repeat(40)}.png/extra`, `/social-media/${PNG_KEY}%00`,
    "/social-media/%E0%A4%A", "/other/" + PNG_KEY, "/social-media/index",
  ]) {
    const res = await call(p);
    assert.equal(res.status, 404, p);
  }
  assert.equal((await call("/.netlify/functions/social-media?file=../../etc/passwd")).status, 404);
  assert.equal((await call("/.netlify/functions/social-media")).status, 404);
});

test("a key that is not in the store is a 404", async () => {
  assert.equal((await call(`/social-media/${"d".repeat(40)}.png`)).status, 404);
});

test("a blob whose bytes are not an image is never served", async () => {
  assert.equal((await call(`/social-media/${"c".repeat(40)}.png`)).status, 404);
});

test("only GET and HEAD are allowed", async () => {
  for (const m of ["POST", "PUT", "DELETE", "PATCH"]) {
    const res = await handler(new Request(`https://purplelink.llc/social-media/${PNG_KEY}`, { method: m, body: m === "DELETE" ? undefined : "x" }), {});
    assert.equal(res.status, 405, m);
    assert.equal(res.headers.get("allow"), "GET, HEAD");
  }
});

test("only the social-media store is ever opened, and it is only read", async () => {
  await call(`/social-media/${PNG_KEY}`);
  await call(`/social-media/${JPG_KEY}`);
  assert.ok(opened.length > 0);
  assert.ok(opened.every((n) => n === "social-media"));
});
