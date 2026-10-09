// A Mac Suite session unlocks the ModernTex, Outbound Veil, Legroom, Keyfeel and Tapefolio purchase downloads, and
// nothing else does. Stripe and Netlify Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/suite-entitlement.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    list: async () => ({ blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
    getWithMetadata: async (k) => (stores.has(`${name}/${k}`) ? { data: new Response("dmg-bytes").body, metadata: { size: 9 } } : null),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

globalThis.Netlify = { env: { get: (k) => (k === "STRIPE_SECRET_KEY" ? "sk_test_dummy" : undefined) } };

const mtx = (await import("../functions/moderntex-download.mjs")).default;
const ov = (await import("../functions/outbound-veil-download.mjs")).default;
const lg = (await import("../functions/legroom-download.mjs")).default;
const kf = (await import("../functions/keyfeel-download.mjs")).default;
const tf = (await import("../functions/tapefolio-download.mjs")).default;

let session;
beforeEach(() => {
  stores.clear();
  stores.set("moderntex-files/ModernTex-1.3.0.dmg", "x");
  stores.set("outbound-veil-files/OutboundVeil-1.0.0.dmg", "x");
  stores.set("legroom-files/Legroom-1.0.0.dmg", "x");
  stores.set("keyfeel-files/Keyfeel-1.0.0.dmg", "x");
  stores.set("tapefolio-files/Tapefolio-1.0.0.dmg", "x");
  session = { id: "cs_live_abcdefghij1234", payment_status: "paid", metadata: { product: "app-suite" } };
  globalThis.fetch = async (url) => {
    if (String(url).startsWith("https://api.stripe.com/v1/checkout/sessions/")) return new Response(JSON.stringify(session), { status: 200 });
    throw new Error(`Unexpected fetch to ${url}`);
  };
});

const call = (fn, fnName, query) =>
  fn(new Request(`https://purplelink.llc/.netlify/functions/${fnName}?${query}`, { headers: { "x-nf-client-connection-ip": "198.51.100.5" } }), {});

for (const [label, fn, fnName, file] of [
  ["ModernTex", mtx, "moderntex-download", "ModernTex-1.3.0.dmg"],
  ["Outbound Veil", ov, "outbound-veil-download", "OutboundVeil-1.0.0.dmg"],
  ["Legroom", lg, "legroom-download", "Legroom-1.0.0.dmg"],
  ["Keyfeel", kf, "keyfeel-download", "Keyfeel-1.0.0.dmg"],
  ["Tapefolio", tf, "tapefolio-download", "Tapefolio-1.0.0.dmg"],
]) {
  test(`${label}: a paid Mac Suite session lists and downloads the app`, async () => {
    const list = await call(fn, fnName, "session_id=cs_live_abcdefghij1234");
    assert.equal(list.status, 200);
    assert.equal((await list.json()).files[0].key, file);
    const dl = await call(fn, fnName, `session_id=cs_live_abcdefghij1234&file=${file}`);
    assert.equal(dl.status, 200);
  });

  test(`${label}: its own product session still works`, async () => {
    session.metadata.product = { ModernTex: "moderntex", "Outbound Veil": "outbound-veil", Legroom: "legroom", Keyfeel: "keyfeel", Tapefolio: "tapefolio" }[label];
    assert.equal((await call(fn, fnName, "session_id=cs_live_abcdefghij1234")).status, 200);
  });

  test(`${label}: an unpaid Suite session or another product is refused`, async () => {
    session.payment_status = "unpaid";
    assert.equal((await call(fn, fnName, "session_id=cs_live_abcdefghij1234")).status, 403);
    session.payment_status = "paid";
    session.metadata.product = "kit-bundle";
    const res = await call(fn, fnName, "session_id=cs_live_abcdefghij1234");
    assert.equal(res.status, 403);
    assert.equal((await res.json()).error, "not_entitled");
  });
}

test("each app's own purchase does not unlock the other apps", async () => {
  const doors = [[mtx, "moderntex-download", "moderntex"], [ov, "outbound-veil-download", "outbound-veil"], [lg, "legroom-download", "legroom"], [kf, "keyfeel-download", "keyfeel"], [tf, "tapefolio-download", "tapefolio"]];
  for (const [, , bought] of doors) {
    session.metadata.product = bought;
    for (const [fn, fnName, product] of doors) {
      const status = (await call(fn, fnName, "session_id=cs_live_abcdefghij1234")).status;
      assert.equal(status, product === bought ? 200 : 403, `${bought} session at ${fnName}`);
    }
  }
});
