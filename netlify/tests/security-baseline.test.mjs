// Security baseline 2026-10-16: subscribe abuse limits, kit/photo download limiter,
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

const { default: subscribe, PER_IP_DAILY, PER_EMAIL_DAILY } = await import("../functions/subscribe.mjs");
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
    throw new Error(`Unexpected fetch to ${url}`);
  };
});

const sub = (email, { ip = "203.0.113.5", origin } = {}) => subscribe(new Request("https://purplelink.llc/.netlify/functions/subscribe", {
  method: "POST",
  headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip, ...(origin ? { origin } : {}) },
  body: JSON.stringify({ email }),
}));

test("subscribe: a normal sign-up works, with or without an Origin header", async () => {
  assert.equal((await sub("a@example.com")).status, 200);
  assert.equal((await sub("b@example.com", { origin: "https://purplelink.llc" })).status, 200);
  assert.ok(blobs.has("subscribers/a@example.com"));
});

test("subscribe: a foreign Origin is refused and nothing is stored", async () => {
  const r = await sub("c@example.com", { origin: "https://evil.example" });
  assert.equal(r.status, 403);
  assert.equal(blobs.has("subscribers/c@example.com"), false);
});

test("subscribe: one address is capped per day, another address is not", async () => {
  for (let i = 0; i < PER_EMAIL_DAILY; i++) assert.equal((await sub("d@example.com", { ip: `198.51.100.${i}` })).status, 200);
  assert.equal((await sub("d@example.com", { ip: "198.51.100.99" })).status, 429);
  assert.equal((await sub("e@example.com", { ip: "198.51.100.98" })).status, 200);
});

test("subscribe: one IP is capped per day", async () => {
  for (let i = 0; i < PER_IP_DAILY; i++) assert.equal((await sub(`u${i}@example.com`, { ip: "192.0.2.77" })).status, 200);
  assert.equal((await sub("late@example.com", { ip: "192.0.2.77" })).status, 429);
});

test("subscribe: an over-long address is rejected; a down limiter store fails open", async () => {
  assert.equal((await sub(`${"x".repeat(250)}@example.com`)).status, 400);
  storeDown = true;
  assert.equal((await sub("f@example.com")).status, 200);
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
