// stats.mjs host split: another site's records (rubblefront.com) share the analytics store, so they must never change
// Purplelink's own numbers, and ?host= must return that host alone in the same shape. The blob store is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/stats-host.test.mjs

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

const env = { STATS_TOKEN: "tok" };
globalThis.Netlify = { env: { get: (k) => env[k] } };
const { default: handler, normalizeHost, EXTERNAL_HOSTS } = await import("../functions/stats.mjs");

const TODAY = new Date().toISOString().slice(0, 10);
let n = 0;
const put = (rec) => store.set(`ev/${TODAY}/${String(++n).padStart(6, "0")}`, { ts: Date.now(), ...rec });
const call = async (query = "") => {
  const res = await handler(new Request(`https://purplelink.llc/.netlify/functions/stats?token=tok&days=2${query}`));
  return { status: res.status, body: await res.json() };
};

const ownEvents = () => {
  put({ type: "pageview", path: "/", host: "purplelink.llc", refHost: "google.com", utm: "", vid: "a1" });
  put({ type: "pageview", path: "/suite/", host: "purplelink.llc", refHost: "", utm: "newsletter", vid: "a2" });
  put({ type: "pageview", path: "/moderntex/", host: "", refHost: "bing.com", utm: "", vid: "a1" });
  put({ type: "tool_use", path: "/tools/word-counter/", host: "purplelink.llc", vid: "a2" });
  put({ type: "checkout_click", path: "/suite/", host: "purplelink.llc", meta: "app-suite", vid: "a2" });
  put({ type: "trial_download", path: "/moderntex/", host: "purplelink.llc", vid: "a1" });
};
const rubbleEvents = () => {
  put({ type: "pageview", path: "rubblefront.com/", host: "rubblefront.com", refHost: "reddit.com", utm: "steam", vid: "r1" });
  put({ type: "pageview", path: "rubblefront.com/", host: "rubblefront.com", refHost: "reddit.com", utm: "", vid: "r2" });
  put({ type: "pageview", path: "rubblefront.com/press/", host: "www.RubbleFront.com", refHost: "", utm: "", vid: "r1" });
  put({ type: "steam_click", path: "rubblefront.com/", host: "rubblefront.com", meta: "store.steampowered.com", vid: "r1" });
  put({ type: "steam_click", path: "rubblefront.com/", host: "rubblefront.com", meta: "store.steampowered.com", vid: "r2" });
  put({ type: "outbound_click", path: "rubblefront.com/", host: "rubblefront.com", meta: "discord.gg", vid: "r1" });
  put({ type: "download", path: "rubblefront.com/press/", host: "rubblefront.com", meta: "presskit.zip", vid: "r2" });
  put({ type: "newsletter_submit", path: "rubblefront.com/", host: "rubblefront.com", meta: "home", vid: "r1" });
};

beforeEach(() => { store.clear(); n = 0; });

const strip = (b) => { const { generatedAt, excludedHosts, ...rest } = b; return rest; };

test("a rubblefront event never changes Purplelink's numbers", async () => {
  ownEvents();
  const before = await call();
  rubbleEvents();
  const after = await call();
  assert.equal(before.status, 200);
  assert.deepEqual(strip(after.body), strip(before.body), "totals, days, paths, referrers, utm and hosts are identical");
  assert.equal(after.body.totals.pageviews, 3);
  assert.equal(after.body.totals.events, 6);
  assert.equal(after.body.byHost.some((h) => /rubblefront/.test(h.key)), false);
  assert.equal(after.body.topPaths.some((p) => /rubblefront/.test(p.key)), false);
  assert.equal(after.body.topReferrers.some((r) => r.key === "reddit.com"), false);
  assert.equal(after.body.otherEvents.some((e) => ["steam_click", "outbound_click", "download", "newsletter_submit"].includes(e.key)), false);
});

test("the default response says how many rubblefront records it left out, including a www. spelling", async () => {
  ownEvents(); rubbleEvents();
  const { body } = await call();
  assert.deepEqual(body.excludedHosts, { "rubblefront.com": 8 });
  assert.equal(body.host, undefined);
});

test("?host=rubblefront.com returns that host alone, in the same shape, with its event counts", async () => {
  ownEvents(); rubbleEvents();
  const { status, body } = await call("&host=rubblefront.com");
  assert.equal(status, 200);
  assert.equal(body.host, "rubblefront.com");
  assert.equal(body.totals.pageviews, 3);
  assert.equal(body.totals.events, 8);
  assert.deepEqual({ s: body.totals.steamClicks, o: body.totals.outboundClicks, d: body.totals.downloads, n: body.totals.newsletterSubmits },
    { s: 2, o: 1, d: 1, n: 1 });
  const day = body.byDay[TODAY];
  assert.equal(day.pageviews, 3);
  assert.equal(day.uniques, 2, "two different visitors");
  assert.deepEqual({ s: day.steamClicks, o: day.outboundClicks, d: day.downloads, n: day.newsletterSubmits }, { s: 2, o: 1, d: 1, n: 1 });
  assert.deepEqual(body.topPaths.map((p) => p.key).sort(), ["rubblefront.com/", "rubblefront.com/press/"]);
  assert.deepEqual(body.topReferrers, [{ key: "reddit.com", count: 2 }]);
  assert.deepEqual(body.topUtm, [{ key: "steam", count: 1 }]);
  assert.deepEqual(body.byHost, [{ key: "rubblefront.com", count: 7 }, { key: "www.RubbleFront.com", count: 1 }]);
  assert.deepEqual(body.otherEvents.map((e) => [e.key, e.count]).sort(), [["download", 1], ["newsletter_submit", 1], ["outbound_click", 1], ["steam_click", 2]]);
  assert.ok(body.otherEventDetail.some((e) => e.key === "steam_click: store.steampowered.com" && e.count === 2));
  // None of Purplelink's own events are in it.
  assert.equal(body.totals.toolRuns, 0);
  assert.equal(body.totals.checkoutClicks, 0);
  assert.equal(body.totals.trialDownloads, 0);
  assert.equal(body.excludedHosts, undefined);
});

test("a host with no records answers with zeros, not an error, and the host spelling is normalised", async () => {
  ownEvents();
  const empty = await call("&host=rubblefront.com");
  assert.equal(empty.status, 200);
  assert.equal(empty.body.totals.pageviews, 0);
  assert.equal(empty.body.totals.steamClicks, 0);
  rubbleEvents();
  const a = await call("&host=WWW.RubbleFront.com");
  assert.equal(a.body.totals.pageviews, 3);
  assert.equal(a.body.host, "rubblefront.com");
  assert.equal(normalizeHost(" WWW.Example.com "), "example.com");
  assert.deepEqual(EXTERNAL_HOSTS, ["rubblefront.com"]);
});

test("asking for purplelink.llc by host returns its own records, and a bad host or token is refused", async () => {
  ownEvents(); rubbleEvents();
  const own = await call("&host=purplelink.llc");
  assert.equal(own.body.totals.pageviews, 2, "the pageview with no host is not matched by a host filter");
  assert.equal((await call("&host=bad%20host")).status, 400);
  assert.equal((await call("&host=")).status, 400);
  const res = await handler(new Request("https://purplelink.llc/.netlify/functions/stats?token=wrong"));
  assert.equal(res.status, 401);
});

test("guide ModernTex card clicks get their own counts and stay out of trialDownloads", async () => {
  ownEvents();
  put({ type: "guide_mtx_trial", path: "/guides/best-mac-latex-editors/", host: "purplelink.llc", meta: "editors-guide:top", ft: "search:google", vid: "g1" });
  put({ type: "guide_mtx_trial", path: "/guides/synctex-on-mac/", host: "purplelink.llc", meta: "synctex-on-mac", vid: "g2" });
  put({ type: "guide_mtx_click", path: "/guides/best-mac-latex-editors/", host: "purplelink.llc", meta: "editors-guide:top-page", vid: "g1" });
  put({ type: "guide_mtx_click", path: "/guides/best-mac-latex-editors/", host: "purplelink.llc", meta: "__selftest", vid: "g3" });
  const { body } = await call();
  assert.equal(body.totals.guideTrialClicks, 2);
  assert.equal(body.totals.guidePageClicks, 1, "the self-test click is ignored");
  assert.equal(body.totals.trialDownloads, 1, "guide trials do not move the product-page trial count");
  assert.equal(body.byDay[TODAY].guideTrialClicks, 2);
  assert.deepEqual(body.guidePageByPlacement, [{ key: "editors-guide:top-page", count: 1 }]);
  assert.equal(body.guideTrialByPlacement.length, 2);
  assert.ok(!body.otherEvents.some((x) => x.key.startsWith("guide_mtx")), "not double counted in otherEvents");
});
