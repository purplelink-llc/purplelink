// First-touch channel on funnel events: track.mjs stores ft, stats.mjs groups funnel counts by channel.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/track-funnel.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

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

test("funnel events carry the first-touch channel and stats groups them", async () => {
  await post({ t: "pageview", p: "/moderntex/", h: "purplelink.llc", ft: "paid:google" });
  await post({ t: "pageview", p: "/moderntex/", h: "purplelink.llc", ft: "paid:google" });
  await post({ t: "pageview", p: "/moderntex/", h: "purplelink.llc", ft: "direct" });
  await post({ t: "trial_download", p: "/moderntex/", h: "purplelink.llc", m: "moderntex", ft: "paid:google" });
  await post({ t: "ov_trial_download", p: "/outbound-veil/", h: "purplelink.llc", m: "outbound-veil", ft: "reddit.com" });
  await post({ t: "checkout_click", p: "/moderntex/", h: "purplelink.llc", m: "moderntex", ft: "paid:google" });
  const out = await read();
  const g = out.funnelByChannel["paid:google"];
  assert.equal(g.pageviews, 2);
  assert.equal(g.pageviewsByPath["/moderntex/"], 2);
  assert.equal(g.trial.moderntex, 1);
  assert.equal(g.checkout.moderntex, 1);
  assert.equal(out.funnelByChannel["reddit.com"].trial["outbound-veil"], 1);
  assert.equal(out.funnelByChannel.direct.pageviews, 1);
});

test("the channel label is clipped and stripped to a safe charset; events without one are not grouped", async () => {
  await post({ t: "pageview", p: "/", h: "purplelink.llc", ft: "<script>x</script>" + "a".repeat(80) });
  await post({ t: "pageview", p: "/", h: "purplelink.llc" });
  const out = await read();
  const keys = Object.keys(out.funnelByChannel);
  assert.equal(keys.length, 1);
  assert.ok(keys[0].length <= 40 && !/[<>]/.test(keys[0]));
});
