// Two measurement fixes in the channel funnel. Nothing is dropped; this changes how events are counted, not traffic.
//  1. Free-app "download" clicks are counted per first-touch channel in freeDownload, apart from trials.
//  2. A trial click from a visitor whose OS is known and is not a Mac is labelled suspect and counted in trialSuspect.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/track-funnel-measurement.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const stores = new Map();
let n = 0;
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    setJSON: async (k, v) => { stores.set(`${name}/${k}`, v); },
    list: async ({ prefix = "" } = {}) => ({ blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/${prefix}`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: (k) => (k === "STATS_TOKEN" ? "tok" : undefined) } };

const { default: track, isNonMacTrial } = await import("../functions/track.mjs");
const stats = (await import("../functions/stats.mjs")).default;

const WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36";
const MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15";
const post = (body, ua = MAC) => track(new Request("https://purplelink.llc/.netlify/functions/track", {
  method: "POST", headers: { "user-agent": ua, "x-nf-client-connection-ip": `198.51.100.${++n}` }, body: JSON.stringify(body),
}));
const read = async () => (await stats(new Request("https://purplelink.llc/.netlify/functions/stats?token=tok&days=2"))).json();
const events = () => [...stores.entries()].filter(([k]) => k.startsWith("analytics/ev/")).map(([, v]) => v);
const trial = (ua, extra = {}, m = "summonly") =>
  post({ t: "sm_trial_download", p: "/summonly/", h: "purplelink.llc", m, ft: "youtube", fc: "summonly-yt-261115", dwell_ms: 5000, interacted: true, ...extra }, ua);

beforeEach(() => { stores.clear(); n = 0; });

test("a free download with a first touch is counted per app in freeDownload and never in trial", async () => {
  await post({ t: "download", p: "/batterymeter/", h: "purplelink.llc", m: "batterymeter", ft: "chatgpt.com" });
  const out = await read();
  assert.deepEqual(out.funnelByChannel["chatgpt.com"].freeDownload, { batterymeter: 1 });
  assert.deepEqual(out.funnelByChannel["chatgpt.com"].trial, {});
  assert.deepEqual(out.funnelByChannel["chatgpt.com"].trialSuspect, {});
});

test("a download meta of the form group:file is counted under the group", async () => {
  await post({ t: "download", p: "/photography/wallpapers/", h: "purplelink.llc", m: "wallpapers:pack-6k", ft: "direct" });
  assert.deepEqual((await read()).funnelByChannel.direct.freeDownload, { wallpapers: 1 });
});

test("a download without a first touch is not part of any channel", async () => {
  await post({ t: "download", p: "/batterymeter/", h: "purplelink.llc", m: "batterymeter" });
  assert.deepEqual((await read()).funnelByChannel, {});
});

test("analytics.js sends a first touch with download events", () => {
  const js = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");
  assert.match(js, /var FUNNEL = \/\^\([^)]*\bdownload\b/);
});

test("a Windows trial click with a long dwell and an interaction is suspect, kept, and counted apart", async () => {
  await trial(WIN);
  const [rec] = events();
  assert.equal(rec.os, "windows");
  assert.equal(rec.suspect, true);
  const out = await read();
  assert.deepEqual(out.funnelByChannel.youtube.trial, {});
  assert.deepEqual(out.funnelByChannel.youtube.trialSuspect, { summonly: 1 });
  assert.equal(out.totals.smTrialDownloads, 1);   // nothing dropped
});

test("the same click from a Mac is a plain trial", async () => {
  await trial(MAC);
  const [rec] = events();
  assert.ok(!("suspect" in rec));
  const out = await read();
  assert.deepEqual(out.funnelByChannel.youtube.trial, { summonly: 1 });
  assert.deepEqual(out.funnelByChannel.youtube.trialSuspect, {});
});

test("a Windows trial click without dwell fields (older cached page) is still suspect", async () => {
  await trial(WIN, { dwell_ms: undefined, interacted: undefined });
  assert.equal(events()[0].suspect, true);
});

test("a not-mac pointer click is not relabelled, and a trial with no first touch has no OS rule", async () => {
  await trial(WIN, {}, "summonly-not-mac");
  await post({ t: "sm_trial_download", p: "/summonly/", h: "purplelink.llc", m: "summonly" }, WIN);
  const recs = events();
  assert.ok(!("suspect" in recs[0]));
  assert.ok(!("suspect" in recs[1]));
  assert.equal(isNonMacTrial({ os: "mac", meta: "x" }), false);
  assert.equal(isNonMacTrial({ meta: "x" }), false);
  assert.equal(isNonMacTrial({ os: "other", meta: "x" }), false);   // an unreadable User-Agent is not evidence
  assert.equal(isNonMacTrial({ os: "linux", meta: "x" }), true);
});
