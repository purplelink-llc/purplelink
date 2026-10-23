// Instagram link-in-bio page: read-only, one fixed key, only purplelink.llc and YouTube links, escaped, with a
// fallback list when the store is empty. Netlify Blobs is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/instagram-links.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

let stored = null;
let fail = false;
const reads = [];
const blobsModule = {
  getStore: (name) => ({
    get: async (k, opts) => {
      reads.push(`${name}/${k}/${opts && opts.type}`);
      if (fail) throw new Error("down");
      return stored;
    },
    list: async () => { throw new Error("list must never be called"); },
    set: async () => { throw new Error("set must never be called"); },
    delete: async () => { throw new Error("delete must never be called"); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const mod = await import("../functions/instagram-links.mjs");
const handler = mod.default;
const req = (method = "GET") => new Request("https://purplelink.llc/instagram/", { method });

beforeEach(() => { stored = null; fail = false; reads.length = 0; });

test("lists the stored links, newest first, from the one fixed key", async () => {
  stored = [
    { title: "How to cite a dataset", url: "https://purplelink.llc/guides/cite/?utm_source=instagram&utm_medium=social&utm_campaign=daily-guide", date: "2026-10-23" },
    { title: "Spotlight fix", url: "https://www.youtube.com/watch?v=XAyZ2nzNB1w&utm_source=instagram", date: "2026-10-22" },
  ];
  const r = await handler(req());
  assert.equal(r.status, 200);
  assert.match(r.headers.get("content-type"), /text\/html/);
  const html = await r.text();
  assert.ok(html.indexOf("How to cite a dataset") < html.indexOf("Spotlight fix"));
  assert.match(html, /utm_source=instagram&amp;utm_medium=social&amp;utm_campaign=daily-guide/);
  assert.deepEqual(reads, ["instagram-links/latest.json/json"]);
});

test("drops links to other hosts and escapes titles", async () => {
  stored = [
    { title: "<script>x</script>", url: "https://purplelink.llc/a/" },
    { title: "Elsewhere", url: "https://evil.example/" },
    { title: "Sneaky", url: "javascript:alert(1)" },
  ];
  const html = await (await handler(req())).text();
  assert.ok(!html.includes("<script>x"));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(!html.includes("evil.example") && !html.includes("javascript:"));
});

test("falls back to the main sections when the store is empty or down", async () => {
  for (const state of [null, "down"]) {
    stored = null;
    fail = state === "down";
    const html = await (await handler(req())).text();
    assert.match(html, /\/guides\/\?utm_source=instagram&amp;utm_medium=social&amp;utm_campaign=bio/);
  }
});

test("only GET and HEAD", async () => {
  assert.equal((await handler(req("POST"))).status, 405);
  const h = await handler(req("HEAD"));
  assert.equal(h.status, 200);
  assert.equal(await h.text(), "");
});
