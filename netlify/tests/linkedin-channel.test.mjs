// LinkedIn is one channel, "linkedin", however the visit arrives: any linkedin.com host, lnkd.in, the Android app
// referrer (android-app://com.linkedin.android, or com.linkedin.android as a bare host), or utm_source=linkedin in any
// case. Checked in the browser script (site/analytics.js, which writes the first-touch label) and in stats.mjs
// (which folds old records stored under the separate labels). Every other channel keeps its label.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/linkedin-channel.test.mjs

import { readFileSync } from "node:fs";
import vm from "node:vm";
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
const { default: handler, isLinkedin, foldChannel } = await import("../functions/stats.mjs");

const analyticsSrc = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");

// Run analytics.js for one arrival and return the pageview event it sends (it carries ft).
function arrive({ search = "", referrer = "" } = {}) {
  const sent = [];
  const ls = {};
  const sandbox = {
    navigator: { sendBeacon: (_u, blob) => { sent.push(JSON.parse(blob.p[0])); return true; } },
    Blob: class { constructor(p) { this.p = p; } },
    URL, URLSearchParams, Date, JSON, Math, String, RegExp, Object,
    window: {},
    document: { referrer, addEventListener() {} },
    location: { search, pathname: "/moderntex/", host: "purplelink.llc", hostname: "purplelink.llc" },
    localStorage: { getItem: (k) => ls[k] ?? null, setItem: (k, v) => { ls[k] = v; }, removeItem: (k) => { delete ls[k]; } },
  };
  sandbox.window = sandbox;
  vm.runInNewContext(analyticsSrc, sandbox);
  return sent.find((e) => e.t === "pageview");
}

const LINKEDIN_REFERRERS = [
  "https://www.linkedin.com/",
  "https://linkedin.com/feed/",
  "https://m.linkedin.com/",
  "https://de.linkedin.com/posts/x",
  "https://lnkd.in/abc123",
  "android-app://com.linkedin.android",
  "android-app://com.linkedin.android/",
];

for (const referrer of LINKEDIN_REFERRERS) {
  test(`analytics.js: referrer ${referrer} is channel linkedin`, () => {
    assert.equal(arrive({ referrer }).ft, "linkedin");
  });
}

test("analytics.js: utm_source=linkedin in any case is channel linkedin", () => {
  for (const q of ["?utm_source=linkedin&utm_medium=social&utm_campaign=li-moderntex", "?utm_source=LinkedIn", "?utm_source=LINKEDIN"]) {
    assert.equal(arrive({ search: q }).ft, "linkedin", q);
  }
});

test("analytics.js: a referrer that only mentions linkedin in its path or query is not linkedin", () => {
  for (const referrer of ["https://example.com/?ref=linkedin", "https://example.com/linkedin.com/", "https://notlinkedin.com/", "https://linkedin.com.evil.example/", "https://example.com/?u=lnkd.in"]) {
    const ev = arrive({ referrer });
    assert.notEqual(ev.ft, "linkedin", referrer);
  }
});

test("analytics.js: other channels are unchanged", () => {
  assert.equal(arrive({ referrer: "https://www.reddit.com/r/latex/" }).ft, "www.reddit.com");
  assert.equal(arrive({ search: "?utm_source=newsletter" }).ft, "newsletter");
  assert.equal(arrive({}).ft, "direct");
  assert.equal(arrive({ search: "?utm_source=linkedin&utm_medium=cpc" }).ft, "paid:linkedin");
  assert.equal(arrive({ search: "?utm_source=google&utm_medium=cpc" }).ft, "paid:google");
});

test("isLinkedin matches the hostname only", () => {
  for (const v of ["www.linkedin.com", "linkedin.com", "lnkd.in", "com.linkedin.android", "android-app://com.linkedin.android", "LinkedIn", "https://www.linkedin.com/feed/"]) assert.equal(isLinkedin(v), true, v);
  for (const v of ["https://example.com/?ref=linkedin", "example.com/linkedin", "notlinkedin.com", "linkedin.com.evil.example", "google.com", "", undefined, "paid:linkedin"]) assert.equal(isLinkedin(v), false, String(v));
  assert.equal(foldChannel("reddit.com"), "reddit.com");
});

// ---- stats.mjs folds history at read time ------------------------------------------------------------------
const TODAY = new Date().toISOString().slice(0, 10);
let n = 0;
const put = (rec) => store.set(`ev/${TODAY}/${String(++n).padStart(6, "0")}`, { ts: Date.now(), host: "purplelink.llc", ...rec });
beforeEach(() => { store.clear(); n = 0; });

test("stats.mjs counts the old separate LinkedIn labels under linkedin, and leaves other labels alone", async () => {
  for (const ft of ["www.linkedin.com", "lnkd.in", "com.linkedin.android", "android-app://com.linkedin.android", "LinkedIn", "linkedin"]) {
    put({ type: "pageview", path: "/moderntex/", ft, vid: "v" });
  }
  put({ type: "trial_download", path: "/moderntex/", meta: "moderntex", ft: "lnkd.in", vid: "v" });
  put({ type: "pageview", path: "/moderntex/", ft: "reddit.com", vid: "w" });
  put({ type: "pageview", path: "/", refHost: "www.linkedin.com", utm: "", vid: "a" });
  put({ type: "pageview", path: "/", refHost: "lnkd.in", utm: "LinkedIn", vid: "b" });
  put({ type: "pageview", path: "/", refHost: "com.linkedin.android", utm: "linkedin", vid: "c" });
  put({ type: "pageview", path: "/", refHost: "example.com", utm: "", vid: "d" });
  const res = await handler(new Request("https://purplelink.llc/.netlify/functions/stats?token=tok&days=2"));
  const out = await res.json();
  const f = out.funnelByChannel;
  assert.equal(f.linkedin.pageviews, 6);
  assert.equal(f.linkedin.trial.moderntex, 1);
  assert.equal(f["reddit.com"].pageviews, 1);
  for (const old of ["www.linkedin.com", "lnkd.in", "com.linkedin.android", "LinkedIn"]) assert.equal(f[old], undefined, old);
  const refs = Object.fromEntries(out.topReferrers.map((r) => [r.key, r.count]));
  assert.equal(refs.linkedin, 3);
  assert.equal(refs["example.com"], 1);
  const utm = Object.fromEntries(out.topUtm.map((r) => [r.key, r.count]));
  assert.equal(utm.linkedin, 2);
});
