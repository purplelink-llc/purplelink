// A failed Stripe lookup in the download functions returns a fixed message, never the raw error text (S-10).
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/download-errors.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";

const blobsModule = {
  getStore: () => ({
    get: async () => null,
    set: async () => {},
    list: async () => ({ blobs: [] }),
    getWithMetadata: async () => null,
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: (k) => ({ STRIPE_SECRET_KEY: "sk_test_dummy" }[k]) } };

const NAMES = [
  "keyfeel", "legroom", "moderntex", "outbound-veil", "panely", "summonly", "tapefolio", "kit", "photo",
];
const LEAK = "connect ECONNREFUSED 10.0.0.7:443 internal-host-detail";

for (const name of NAMES) {
  test(`${name}-download hides the raw error on a Stripe failure`, async () => {
    const handler = (await import(`../functions/${name}-download.mjs`)).default;
    globalThis.fetch = async () => { throw new Error(LEAK); };
    const origErr = console.error;
    console.error = () => {};
    let res;
    try {
      res = await handler(new Request(`https://purplelink.llc/.netlify/functions/${name}-download?session_id=cs_live_abcdefghij1234`));
    } finally { console.error = origErr; }
    const text = await res.text();
    assert.equal(res.status, 502, text);
    assert.equal(text.includes("ECONNREFUSED"), false);
    assert.equal(text.includes("internal-host"), false);
  });
}
