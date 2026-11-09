// Trial clicks with under 1.5 s on the page and no interaction are labelled suspect and counted apart; nothing is dropped.
// track.mjs stores dwell_ms and interacted, stats.mjs puts suspect trials in trialSuspect instead of trial.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/track-trial-suspect.test.mjs

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

const { default: track, isSuspectTrial } = await import("../functions/track.mjs");
const stats = (await import("../functions/stats.mjs")).default;

const post = (body) => track(new Request("https://purplelink.llc/.netlify/functions/track", {
  method: "POST", headers: { "user-agent": "Mozilla/5.0", "x-nf-client-connection-ip": `198.51.100.${++n}` }, body: JSON.stringify(body),
}));
const read = async () => (await stats(new Request("https://purplelink.llc/.netlify/functions/stats?token=tok&days=2"))).json();
const events = () => [...stores.entries()].filter(([k]) => k.startsWith("analytics/ev/")).map(([, v]) => v);
const trial = (extra, t = "sm_trial_download", m = "summonly") =>
  post({ t, p: "/summonly/", h: "purplelink.llc", m, ft: "youtube", fc: "summonly-yt-261108", ...extra });

beforeEach(() => { stores.clear(); n = 0; });

test("a hand click after a pause (3000 ms, interacted) counts as a trial", async () => {
  await trial({ dwell_ms: 3000, interacted: true });
  const [rec] = events();
  assert.equal(rec.dwell_ms, 3000);
  assert.equal(rec.interacted, true);
  assert.ok(!("suspect" in rec));
  const out = await read();
  assert.deepEqual(out.funnelByChannel.youtube.trial, { summonly: 1 });
  assert.deepEqual(out.funnelByChannel.youtube.trialSuspect, {});
  assert.deepEqual(out.funnelByContent["summonly-yt-261108"].trial, { summonly: 1 });
});

test("a scripted click under 500 ms with no interaction counts as trial_suspect, and is not dropped", async () => {
  await trial({ dwell_ms: 400, interacted: false });
  const [rec] = events();
  assert.equal(rec.suspect, true);
  assert.equal(rec.dwell_ms, 400);
  const out = await read();
  assert.deepEqual(out.funnelByChannel.youtube.trial, {});
  assert.deepEqual(out.funnelByChannel.youtube.trialSuspect, { summonly: 1 });
  assert.deepEqual(out.funnelByContent["summonly-yt-261108"].trialSuspect, { summonly: 1 });
  // Nothing is dropped: the all-clicks total still counts it.
  assert.equal(out.totals.smTrialDownloads, 1);
});

test("the rule is under 1500 ms and no interaction; either one alone is a real trial", async () => {
  assert.equal(isSuspectTrial({ dwell_ms: 1499, interacted: false }), true);
  assert.equal(isSuspectTrial({ dwell_ms: 1500, interacted: false }), false);
  assert.equal(isSuspectTrial({ dwell_ms: 200, interacted: true }), false);
  assert.equal(isSuspectTrial({}), false);
});

test("a trial beacon without the fields (a cached older page) is a plain trial", async () => {
  await trial({});
  const [rec] = events();
  assert.ok(!("dwell_ms" in rec) && !("interacted" in rec) && !("suspect" in rec));
  assert.deepEqual((await read()).funnelByChannel.youtube.trial, { summonly: 1 });
});

test("bad values are ignored, big ones clipped, and other event types never carry the fields", async () => {
  await trial({ dwell_ms: "400", interacted: false });
  await trial({ dwell_ms: 400, interacted: "no" });
  await trial({ dwell_ms: 9e15, interacted: false });
  await post({ t: "pageview", p: "/summonly/", h: "purplelink.llc", ft: "youtube", dwell_ms: 10, interacted: false });
  const recs = events();
  assert.equal(recs.filter((r) => r.suspect).length, 0);
  assert.equal(recs.filter((r) => "dwell_ms" in r).length, 1);
  assert.equal(recs.find((r) => "dwell_ms" in r).dwell_ms, 86400000);
  assert.ok(!recs.some((r) => r.type === "pageview" && "dwell_ms" in r));
});

test("analytics.js sends dwell_ms and the interacted flag on trial beacons only, with no identifier", () => {
  const src = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");
  assert.match(src, /ev\.dwell_ms = /);
  assert.match(src, /ev\.interacted = interacted/);
  assert.match(src, /\["pointerdown", "keydown", "scroll"\]/);
  assert.match(src, /if \(\/_\?trial_download\$\/\.test\(type \|\| ""\)/);
});
