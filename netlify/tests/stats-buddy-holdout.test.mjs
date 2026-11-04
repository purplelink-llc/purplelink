// stats.mjs: the per-day appPageviews and appConversions the Buddy chat holdout is read from
// (docs/designs/buddy-chat.md, "Conversion pass", section 3). The blob store is stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/stats-buddy-holdout.test.mjs

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

globalThis.Netlify = { env: { get: (k) => ({ STATS_TOKEN: "tok" })[k] } };
const { default: handler, isChatAppPage } = await import("../functions/stats.mjs");

const TODAY = new Date().toISOString().slice(0, 10);
let n = 0;
const ev = (type, path, meta = "", host = "purplelink.llc") =>
  store.set(`ev/${TODAY}/${String(++n).padStart(6, "0")}`, { type, path, meta, host, vid: "v" + n, ts: 1000 + n });
const call = async () =>
  (await handler(new Request("https://purplelink.llc/.netlify/functions/stats?token=tok&days=1"))).json();

beforeEach(() => { store.clear(); n = 0; });

test("only the ten Mac-app pages themselves count, localized or not", () => {
  for (const p of ["/moderntex/", "/moderntex", "/de/moderntex/", "/zh-cn/moderntex/", "/nee/", "/suite/", "/outbound-veil/"]) {
    assert.ok(isChatAppPage(p), p);
  }
  for (const p of ["/legroom/success/", "/moderntex/buy/", "/guides/moderntex/", "/vitae/", "/batterymeter/", "/", "", null]) {
    assert.ok(!isChatAppPage(p), String(p));
  }
});

test("views and conversions on app pages are counted per day", async () => {
  ev("pageview", "/moderntex/");
  ev("pageview", "/de/moderntex/");
  ev("pageview", "/guides/latex-on-mac/");            // not an app page
  ev("trial_download", "/moderntex/", "moderntex");
  ev("lg_trial_download", "/legroom/", "legroom");
  ev("checkout_click", "/suite/", "suite");
  ev("lg_trial_download", "/legroom/", "legroom-not-mac"); // a send-to-Mac pointer: no download
  ev("checkout_click", "/tools/paper-review/", "paper-review"); // not an app page
  ev("pageview", "/moderntex/", "", "rubblefront.com");      // another site
  const day = (await call()).byDay[TODAY];
  assert.equal(day.appPageviews, 2);
  assert.equal(day.appConversions, 3);
});
