// A click on lenses-download?trial=1 is counted as a lenses_trial_download event, the way Née's is.
// analytics.js fires it and lists it in FUNNEL; track.mjs stores it; stats.mjs counts it in totals and byDay.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/lenses-trial-event.test.mjs

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

const track = (await import("../functions/track.mjs")).default;
const stats = (await import("../functions/stats.mjs")).default;

const post = (body) => track(new Request("https://purplelink.llc/.netlify/functions/track", {
  method: "POST", headers: { "user-agent": "Mozilla/5.0", "x-nf-client-connection-ip": `198.51.100.${++n}` }, body: JSON.stringify(body),
}));
const read = async () => (await stats(new Request("https://purplelink.llc/.netlify/functions/stats?token=tok&days=2"))).json();

beforeEach(() => { stores.clear(); n = 0; });

test("analytics.js fires lenses_trial_download for lenses-download?trial=1 and lists it in FUNNEL", () => {
  const js = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");
  assert.match(js, /lenses-download\?trial=1[\s\S]{0,120}lenses_trial_download/);
  assert.match(js, /\|lenses_trial_download\|/);
});

test("stats.mjs counts lenses_trial_download in totals and byDay, apart from the other apps", async () => {
  await post({ t: "lenses_trial_download", p: "/lenses/", h: "purplelink.llc", m: "lenses", dwell_ms: 5000, interacted: true });
  await post({ t: "nee_trial_download", p: "/nee/", h: "purplelink.llc", m: "nee", dwell_ms: 5000, interacted: true });
  const out = await read();
  assert.equal(out.totals.lensesTrialDownloads, 1);
  assert.equal(out.totals.neeTrialDownloads, 1);
  assert.equal(Object.values(out.byDay).reduce((s, d) => s + d.lensesTrialDownloads, 0), 1);
});
