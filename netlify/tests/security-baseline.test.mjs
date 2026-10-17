// Security baseline 2026-10-16: kit/photo download limiter,
// indexnow token compare, spreadsheet-safe cells in live-sheet.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/security-baseline.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const blobs = new Map();
let storeDown = false;
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => { if (storeDown && name === "rate-limits") throw new Error("down"); return blobs.get(`${name}/${k}`) ?? null; },
    set: async (k, v) => { blobs.set(`${name}/${k}`, v); },
    setJSON: async (k, v) => { blobs.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_SECRET_KEY: "sk_test_dummy", INDEXNOW_WEBHOOK_TOKEN: "right-token", SUBSCRIBE_SECRET: "s3cret-for-tests" };
globalThis.Netlify = { env: { get: (k) => env[k] } };
process.env.SUBSCRIBE_SECRET = env.SUBSCRIBE_SECRET;
process.env.RESEND_API_KEY = "re_dummy";

const { default: kit, DAILY_LIMIT: KIT_LIMIT } = await import("../functions/kit-download.mjs");
const { default: photo, DAILY_LIMIT: PHOTO_LIMIT } = await import("../functions/photo-download.mjs");
const { default: indexnow } = await import("../functions/indexnow-ping.mjs");
const { csvCell } = await import("../functions/live-sheet.mjs");

let stripeCalls;
beforeEach(() => {
  blobs.clear();
  storeDown = false;
  stripeCalls = 0;
  globalThis.fetch = async (url) => {
    if (String(url).startsWith("https://api.stripe.com/")) { stripeCalls++; return new Response("{}", { status: 404 }); }
    if (String(url).startsWith("https://api.resend.com/")) return new Response("{}", { status: 200 });
    throw new Error(`Unexpected fetch to ${url}`);
  };
});

for (const [name, handler, limit] of [["kit-download", kit, KIT_LIMIT], ["photo-download", photo, PHOTO_LIMIT]]) {
  test(`${name}: an address that keeps asking is stopped before it reaches Stripe`, async () => {
    const get = (ip) => handler(new Request(`https://purplelink.llc/.netlify/functions/${name}?session_id=cs_live_abcdefghijklmnop`, {
      headers: { "x-nf-client-connection-ip": ip },
    }));
    for (let i = 0; i < limit; i++) assert.equal((await get("203.0.113.40")).status, 403);
    assert.equal(stripeCalls, limit);
    assert.equal((await get("203.0.113.40")).status, 429);
    assert.equal(stripeCalls, limit, "the throttled request made no Stripe call");
    assert.equal((await get("203.0.113.41")).status, 403, "another address is unaffected");
  });
}

test("indexnow-ping: wrong or missing token is 401, right token passes the check", async () => {
  const call = (q) => indexnow(new Request(`https://purplelink.llc/.netlify/functions/indexnow-ping${q}`, { method: "POST" }), {});
  assert.equal((await call("?token=wrong")).status, 401);
  assert.equal((await call("")).status, 401);
  const ok = await call("?token=right-token");
  assert.notEqual(ok.status, 401);
});

test("live-sheet csvCell keeps formula-looking text as text", () => {
  for (const v of ["=1+1", "+1", "-1+1", "@SUM(A1)"]) assert.ok(csvCell(v).startsWith(" "), v);
  assert.equal(csvCell("plain"), "plain");
  assert.equal(csvCell('a,"b"'), '"a,""b"""');
});
