// track.mjs stores a two-letter country code only (cc); stats.mjs ?host= adds country, device, scroll and engaged-time
// breakdowns without touching any existing number.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/track-geo.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
let n = 0;
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    setJSON: async (k, v) => { stores.set(`${name}/${k}`, v); },
    list: async ({ prefix = "" } = {}) => ({ blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/${prefix}`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: (k) => (k === "STATS_TOKEN" ? "tok" : undefined) } };

const { default: track, countryCode } = await import("../functions/track.mjs");
const stats = (await import("../functions/stats.mjs")).default;

const post = (body, context, headers = {}) => track(new Request("https://purplelink.llc/.netlify/functions/track", {
  method: "POST",
  headers: { "user-agent": "Mozilla/5.0", "x-nf-client-connection-ip": `198.51.100.${++n}`, ...headers },
  body: JSON.stringify(body),
}), context);
const ctx = (code, extra = {}) => ({ geo: { city: "Springfield", subdivision: { code: "IL" }, latitude: 1, longitude: 2, country: { code, name: "X" }, ...extra } });
const records = () => [...stores.entries()].filter(([k]) => k.startsWith("analytics/ev/")).map(([, v]) => v);
const call = async (q = "") => (await stats(new Request(`https://purplelink.llc/.netlify/functions/stats?token=tok&days=2${q}`))).json();

beforeEach(() => { stores.clear(); n = 0; });

test("cc is the upper-case two-letter country and nothing else from geo or the IP is stored", async () => {
  await post({ t: "pageview", p: "/", h: "purplelink.llc" }, ctx("DE"));
  const [r] = records();
  assert.equal(r.cc, "DE");
  assert.deepEqual(Object.keys(r).sort(), ["cc", "host", "meta", "path", "refHost", "ts", "type", "utm", "vid"]);
  const text = JSON.stringify(r);
  assert.equal(/Springfield|IL|198\.51\.100/.test(text), false);
});

test("absent geo leaves cc empty and the event is still recorded", async () => {
  await post({ t: "pageview", p: "/", h: "purplelink.llc" });
  await post({ t: "pageview", p: "/", h: "purplelink.llc" }, {});
  await post({ t: "pageview", p: "/", h: "purplelink.llc" }, { geo: {} });
  await post({ t: "pageview", p: "/", h: "purplelink.llc" }, { geo: { country: {} } });
  assert.deepEqual(records().map((r) => r.cc), ["", "", "", ""]);
});

test("malformed codes are dropped: lower case is normalised, 3 letters, digits and non-strings are not stored", async () => {
  assert.equal(countryCode(new Request("https://x"), ctx("us")), "US");
  assert.equal(countryCode(new Request("https://x"), ctx(" gb ")), "GB");
  for (const bad of ["USA", "U", "", "1A", "U-", "<script>", null, undefined, 5, { a: 1 }, ["US"]]) {
    assert.equal(countryCode(new Request("https://x"), ctx(bad)), "", JSON.stringify(bad));
  }
});

test("the x-nf-geo header is a fallback, and a broken one is ignored", async () => {
  const h = (o) => ({ "x-nf-geo": Buffer.from(JSON.stringify(o)).toString("base64") });
  await post({ t: "pageview", p: "/", h: "x" }, undefined, h({ country: { code: "fr" }, city: "Paris" }));
  await post({ t: "pageview", p: "/", h: "x" }, undefined, { "x-nf-geo": "%%%not-base64-json" });
  await post({ t: "pageview", p: "/", h: "x" }, ctx("JP"), h({ country: { code: "FR" } }));
  assert.deepEqual(records().map((r) => r.cc), ["FR", "", "JP"], "the context wins over the header");
});

test("the daily-salted visitor hash is unchanged by geo", async () => {
  await post({ t: "pageview", p: "/", h: "x" }, ctx("DE"), { "x-nf-client-connection-ip": "203.0.113.9" });
  await post({ t: "pageview", p: "/", h: "x" }, ctx("FR"), { "x-nf-client-connection-ip": "203.0.113.9" });
  const [a, b] = records();
  assert.equal(a.vid, b.vid);
  assert.equal(a.vid.length, 16);
});

const rf = (type, meta, cc, extra = {}) => ({ type, path: "rubblefront.com/", host: "rubblefront.com", meta, ts: Date.now(), vid: `v${++n}`, cc, ...extra });
const seed = () => {
  const day = new Date().toISOString().slice(0, 10);
  let i = 0;
  const put = (r) => stores.set(`analytics/ev/${day}/${String(++i).padStart(5, "0")}`, r);
  put(rf("pageview", "mobile", "US")); put(rf("pageview", "mobile", "US")); put(rf("pageview", "desktop", "DE"));
  put(rf("pageview", "tablet", ""));                       // no cc recorded
  put(rf("pageview", "", undefined));                      // old record: no cc, no meta
  put(rf("pageview", "watch", "GB"));                      // unknown device value
  put(rf("scroll_depth", "0", "US")); put(rf("scroll_depth", "50", "US")); put(rf("scroll_depth", "100", "DE")); put(rf("scroll_depth", "33", "DE"));
  put(rf("engaged_time", "0-10s", "US")); put(rf("engaged_time", "3m-plus", "DE")); put(rf("engaged_time", "9h", "DE"));
  put(rf("scroll_depth", "__selftest", "US"));
  put({ type: "pageview", path: "/", host: "purplelink.llc", meta: "", ts: Date.now(), vid: "p1", cc: "US" });
};

test("?host= adds the four breakdowns; scroll and engaged events are not pageviews", async () => {
  seed();
  const b = await call("&host=rubblefront.com");
  assert.deepEqual(b.byCountry, { top: [{ key: "US", count: 2 }, { key: "DE", count: 1 }, { key: "GB", count: 1 }], other: 0, unknown: 2 });
  assert.deepEqual(b.device, { mobile: 2, tablet: 1, desktop: 1 });
  assert.deepEqual(b.scrollDepth, { 0: 1, 25: 0, 50: 1, 75: 0, 100: 1 });
  assert.deepEqual(b.engagedTime, { "0-10s": 1, "10-30s": 0, "30-60s": 0, "1-3m": 0, "3m-plus": 1 });
  assert.equal(b.totals.pageviews, 6);
});

test("country top 15 keeps the rest as other", async () => {
  const day = new Date().toISOString().slice(0, 10);
  const letters = "ABCDEFGHIJKLMNOPQRST";
  for (let i = 0; i < 20; i++) stores.set(`analytics/ev/${day}/${i}`, rf("pageview", "mobile", "Q" + letters[i]));
  const b = await call("&host=rubblefront.com");
  assert.equal(b.byCountry.top.length, 15);
  assert.equal(b.byCountry.other, 5);
  assert.equal(b.byCountry.unknown, 0);
});

test("the default response has none of the new fields and ignores scroll and engaged records of other hosts", async () => {
  seed();
  const d = await call();
  for (const k of ["byCountry", "device", "scrollDepth", "engagedTime"]) assert.equal(k in d, false, k);
  assert.equal(d.totals.pageviews, 1);
  assert.equal(d.totals.events, 1);
  assert.deepEqual(d.excludedHosts, { "rubblefront.com": 14 });
});

test("adding cc, scroll_depth and engaged_time records changes no existing number for Purplelink or the host", async () => {
  const day = new Date().toISOString().slice(0, 10);
  const strip = (b) => { const { generatedAt, byCountry, device, scrollDepth, engagedTime, ...rest } = b; return rest; };
  const base = (cc) => {
    stores.clear();
    const r = (t, m) => ({ type: t, path: "rubblefront.com/", host: "rubblefront.com", meta: m, ts: 1, vid: "v1", ...(cc === undefined ? {} : { cc }) });
    stores.set(`analytics/ev/${day}/1`, r("pageview", "mobile"));
    stores.set(`analytics/ev/${day}/2`, r("steam_click", "store.steampowered.com"));
  };
  base(undefined); const old = await call("&host=rubblefront.com");
  base("US"); const withCc = await call("&host=rubblefront.com");
  assert.deepEqual(strip(withCc), strip(old));
  // scroll_depth and engaged_time already surfaced as otherEvents before; still the same.
  stores.set(`analytics/ev/${day}/3`, rf("scroll_depth", "50", "US"));
  const after = await call("&host=rubblefront.com");
  assert.equal(after.totals.pageviews, old.totals.pageviews);
  assert.deepEqual(after.otherEvents.find((e) => e.key === "scroll_depth"), { key: "scroll_depth", count: 1 });
});
