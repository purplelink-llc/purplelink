// The social poster's channels (scripts/social) are one label each in stats.mjs: bluesky, threads, x, mastodon,
// devto, however the visit arrives (the utm_source its short links carry, or the referring host). Host match only.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/social-channels.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const store = new Map();
const blobsModule = {
  getStore: () => ({
    list: async ({ prefix }) => ({ blobs: [...store.keys()].filter((k) => k.startsWith(prefix)).map((key) => ({ key })) }),
    get: async (k) => store.get(k) ?? null,
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: (k) => (k === "STATS_TOKEN" ? "tok" : undefined) } };
const { default: handler, socialChannel, foldChannel, foldSource } = await import("../functions/stats.mjs");

const CASES = {
  bluesky: ["bluesky", "Bluesky", "bsky.app", "https://bsky.app/profile/x", "go.bsky.app", "bsky.social"],
  threads: ["threads", "threads.net", "www.threads.net", "threads.com", "l.threads.com", "https://www.threads.com/@a"],
  x: ["x", "X", "twitter", "t.co", "https://t.co/abc", "x.com", "twitter.com", "mobile.twitter.com"],
  mastodon: ["mastodon", "mastodon.social", "fosstodon.org", "hachyderm.io", "https://mas.to/@a"],
  devto: ["devto", "dev.to", "https://dev.to/purplelink/post"],
};

for (const [name, labels] of Object.entries(CASES)) {
  test(`socialChannel folds ${name}`, () => {
    for (const v of labels) assert.equal(socialChannel(v), name, v);
    for (const v of labels) assert.equal(foldChannel(v), name, v);
  });
}

test("socialChannel matches the host only and leaves other labels alone", () => {
  for (const v of ["example.com/?ref=bsky.app", "notx.com", "x.com.evil.example", "devto.example", "reddit.com", "paid:x", "tool:x", "", undefined, "linkedin"]) {
    assert.equal(socialChannel(v), "", String(v));
  }
  assert.equal(foldChannel("www.linkedin.com"), "linkedin");
  assert.equal(foldChannel("reddit.com"), "reddit.com");
  assert.equal(foldSource("tool-word-counter"), "tool:word-counter");
});

const TODAY = new Date().toISOString().slice(0, 10);
let n = 0;
const put = (rec) => store.set(`ev/${TODAY}/${String(++n).padStart(6, "0")}`, { ts: Date.now(), host: "purplelink.llc", ...rec });
beforeEach(() => { store.clear(); n = 0; });

test("stats.mjs counts poster channels under one label in the funnel, referrers and utm tables", async () => {
  put({ type: "pageview", path: "/legroom/", ft: "bluesky", vid: "a" });
  put({ type: "pageview", path: "/legroom/", ft: "bsky.app", vid: "b" });
  put({ type: "pageview", path: "/legroom/", ft: "t.co", vid: "c" });
  put({ type: "trial_download", path: "/legroom/", meta: "legroom", ft: "x.com", vid: "c" });
  put({ type: "pageview", path: "/", refHost: "l.threads.com", utm: "threads", vid: "d" });
  put({ type: "pageview", path: "/", refHost: "dev.to", utm: "devto", vid: "e" });
  const res = await handler(new Request("https://purplelink.llc/.netlify/functions/stats?token=tok&days=2"));
  const out = await res.json();
  const f = out.funnelByChannel;
  assert.equal(f.bluesky.pageviews, 2);
  assert.equal(f.x.pageviews, 1);
  assert.equal(f.x.trial.legroom, 1);
  for (const old of ["bsky.app", "t.co", "x.com"]) assert.equal(f[old], undefined, old);
  const refs = Object.fromEntries(out.topReferrers.map((r) => [r.key, r.count]));
  assert.equal(refs.threads, 1);
  assert.equal(refs.devto, 1);
  const utm = Object.fromEntries(out.topUtm.map((r) => [r.key, r.count]));
  assert.equal(utm.threads, 1);
  assert.equal(utm.devto, 1);
});
