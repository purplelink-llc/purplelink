// Lenses delivery: three doors (purchase, public trial, token-gated Sparkle update channel). Stripe and Netlify Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/lenses-download.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    list: async () => ({ blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
    getWithMetadata: async (k) => (stores.has(`${name}/${k}`) ? { data: new Response(`bytes:${k}`).body, metadata: { size: 9 } } : null),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_SECRET_KEY: "sk_test_dummy", LENSES_UPDATE_TOKEN: "tok_lenses_test_0123456789" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const handler = (await import("../functions/lenses-download.mjs")).default;

const SESSION = "cs_live_abcdefghij1234";
let session;
let stripeCalls;

beforeEach(() => {
  stores.clear();
  stripeCalls = 0;
  stores.set("lenses-files/Lenses-1.0.0.dmg", "x");
  stores.set("lenses-files/Lenses-1.1.0.dmg", "x");
  stores.set("lenses-files/Lenses-1.10.0.dmg", "x");
  session = { id: SESSION, payment_status: "paid", payment_intent: "pi_test_1", metadata: { product: "lenses" } };
  globalThis.fetch = async (url) => {
    if (String(url).startsWith("https://api.stripe.com/v1/checkout/sessions/")) {
      stripeCalls++;
      return new Response(JSON.stringify(session), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
});

const call = (query, method = "GET") =>
  handler(new Request(`https://purplelink.llc/.netlify/functions/lenses-download?${query}`, {
    method, headers: { "x-nf-client-connection-ip": "198.51.100.5" },
  }), {});

test("a paid Lenses session lists the newest DMG and carries no license field", async () => {
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.product, "lenses");
  assert.equal(body.files.length, 1);
  assert.equal(body.files[0].key, "Lenses-1.10.0.dmg");
  assert.match(body.files[0].label, /Lenses 1\.10\.0 for macOS/);
  assert.match(body.files[0].url, /lenses-download\?session_id=cs_live_abcdefghij1234&file=Lenses-1\.10\.0\.dmg/);
  assert.ok(!("license" in body));
});

test("a paid session streams a named DMG, including an older release", async () => {
  const res = await call(`session_id=${SESSION}&file=Lenses-1.0.0.dmg`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/x-apple-diskimage");
  assert.match(res.headers.get("content-disposition"), /attachment; filename="Lenses-1\.0\.0\.dmg"/);
  assert.equal(await res.text(), "bytes:Lenses-1.0.0.dmg");
});

test("an unpaid session is refused", async () => {
  session.payment_status = "unpaid";
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "not_paid");
});

test("a fully refunded order is refused", async () => {
  stores.set("refunds/pi:pi_test_1", JSON.stringify({ reason: "refund" }));
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "refunded");
  const file = await call(`session_id=${SESSION}&file=Lenses-1.0.0.dmg`);
  assert.equal(file.status, 403);
});

test("a paid session for another product is refused", async () => {
  for (const product of ["moderntex", "outbound-veil", "legroom", "keyfeel", "tapefolio", "lenscrib", "kit-bundle", ""]) {
    session.metadata = product ? { product } : {};
    const res = await call(`session_id=${SESSION}`);
    assert.equal(res.status, 403, product);
    assert.equal((await res.json()).error, "not_entitled");
  }
});

test("a paid Mac Suite session can download Lenses", async () => {
  session.metadata = { product: "app-suite" };
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 200);
  const file = await call(`session_id=${SESSION}&file=Lenses-1.0.0.dmg`);
  assert.equal(file.status, 200);
});

test("a custom bundle that includes Lenses can download it, and one without Lenses cannot", async () => {
  for (const metadata of [{ product: "bundle-2", apps: "moderntex,lenses" }, { product: "bundle-3", apps: "keyfeel,lenses,panely" }]) {
    session.metadata = metadata;
    const res = await call(`session_id=${SESSION}`);
    assert.equal(res.status, 200, metadata.product);
  }
  for (const metadata of [{ product: "bundle-3", apps: "keyfeel,tapefolio,panely" }, { product: "bundle-2", apps: "moderntex,panely" }, { product: "bundle-2", apps: "lenses" }]) {
    session.metadata = metadata;
    const res = await call(`session_id=${SESSION}`);
    assert.equal(res.status, 403, JSON.stringify(metadata));
    assert.equal((await res.json()).error, "not_entitled");
  }
});

test("a session Stripe does not know is refused", async () => {
  globalThis.fetch = async () => new Response("{}", { status: 404 });
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "session_not_found");
});

test("a malformed or missing session id never reaches Stripe", async () => {
  for (const q of ["", "session_id=", "session_id=abc", "session_id=cs_x", `session_id=${SESSION}%2F..%2F`]) {
    const res = await call(q);
    assert.equal(res.status, 400, q);
  }
  assert.equal(stripeCalls, 0);
});

test("there is no open download door: without a session, a token or trial=1 the request is refused", async () => {
  const res = await call("download=1");
  assert.equal(res.status, 400);
  assert.equal(stripeCalls, 0);
});

// ---- trial door ----

test("the trial door is public, never asks Stripe, and serves the newest DMG", async () => {
  const res = await call("trial=1");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-disposition"), /filename="Lenses-1\.10\.0\.dmg"/);
  assert.equal(await res.text(), "bytes:Lenses-1.10.0.dmg");
  assert.equal(stripeCalls, 0);
});

test("the trial door never serves 1.0.0, which had no trial and no license check", async () => {
  stores.clear();
  stores.set("lenses-files/Lenses-1.0.0.dmg", "x");
  const res = await call("trial=1");
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error, "no_trial");
});

test("the trial door answers 404 while no DMG is staged", async () => {
  stores.clear();
  assert.equal((await call("trial=1")).status, 404);
});

test("the trial door is capped per address per day", async () => {
  for (let i = 0; i < 20; i++) assert.equal((await call("trial=1")).status, 200);
  const res = await call("trial=1");
  assert.equal(res.status, 429);
  assert.equal((await res.json()).error, "rate_limited");
});

// ---- update channel (Sparkle) ----

const withToken = (query, token = "tok_lenses_test_0123456789") =>
  handler(new Request(`https://purplelink.llc/.netlify/functions/lenses-download?${query}`, {
    headers: token === null ? {} : { "x-lenses-channel": token },
  }), {});

test("the appcast, an update DMG and the stats need the channel token", async () => {
  stores.set("lenses-files/appcast.xml", '<rss><enclosure url="https://x/y/Lenses-1.1.0.dmg"/></rss>');
  for (const q of ["feed=1", "update=Lenses-1.1.0.dmg", "stats=1"]) {
    for (const token of [null, "", "wrong", "tok_lenses_test_012345678"]) {
      const res = await withToken(q, token);
      assert.equal(res.status, 403, `${q} with ${JSON.stringify(token)}`);
    }
  }
  assert.equal(stripeCalls, 0);
});

test("with no LENSES_UPDATE_TOKEN configured the update channel stays closed, even for an empty header", async () => {
  delete env.LENSES_UPDATE_TOKEN;
  try {
    assert.equal((await withToken("feed=1", "")).status, 403);
    assert.equal((await withToken("feed=1", "anything")).status, 403);
  } finally {
    env.LENSES_UPDATE_TOKEN = "tok_lenses_test_0123456789";
  }
});

test("with the token the feed is served and its enclosure URLs point at the update door", async () => {
  stores.set("lenses-files/appcast.xml", '<rss><enclosure url="https://x/y/Lenses-1.1.0.dmg" length="1"/></rss>');
  const res = await withToken("feed=1");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /rss\+xml/);
  assert.match(await res.text(), /url="https:\/\/purplelink\.llc\/\.netlify\/functions\/lenses-download\?update=Lenses-1\.1\.0\.dmg"/);
});

test("a signed feed is served byte for byte", async () => {
  const xml = '<rss><enclosure url="https://x/y/Lenses-1.1.0.dmg"/></rss>\n<!-- sparkle-signatures:\nedSignature: abc\n-->';
  stores.set("lenses-files/appcast.xml", xml);
  assert.equal(await (await withToken("feed=1")).text(), xml);
});

test("with the token an update DMG streams and is counted; a bad name is refused", async () => {
  const res = await withToken("update=Lenses-1.1.0.dmg");
  assert.equal(res.status, 200);
  assert.equal(await res.text(), "bytes:Lenses-1.1.0.dmg");
  assert.equal((await withToken("update=Lenses-1.1.0.dmg")).status, 200);
  const stats = await (await withToken("stats=1")).json();
  assert.equal(stats.downloads["Lenses-1.1.0.dmg"], 2);
  assert.equal((await withToken("update=..%2Fappcast.xml")).status, 400);
  assert.equal((await withToken("update=Lenses-1.1.dmg")).status, 400);
});

test("a missing appcast is a plain 404", async () => {
  assert.equal((await withToken("feed=1")).status, 404);
});

test("path traversal and other names in file= are not served", async () => {
  for (const file of ["../Lenses-1.0.0.dmg", "..%2Flenses-files%2FLenses-1.0.0.dmg", "appcast.xml", "Lenses-Trial-1.2.0.dmg", "Lenses-1.0.0.dmg.bak", "Lenses-1.0.dmg", "lenses-1.0.0.dmg", "Lenscrib-1.0.0.dmg"]) {
    const res = await call(`session_id=${SESSION}&file=${file}`);
    assert.equal(res.status, 404, file);
    assert.equal((await res.json()).error, "unknown_file");
  }
});

test("a well-formed file name that is not in the store is a plain 404, not a crash", async () => {
  const res = await call(`session_id=${SESSION}&file=Lenses-9.9.9.dmg`);
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error, "file_unavailable");
});

test("with no release staged the buyer list says so rather than listing nothing", async () => {
  stores.clear();
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 500);
  assert.equal((await res.json()).error, "file_unavailable");
});

test("methods other than GET and HEAD are refused", async () => {
  const res = await call(`session_id=${SESSION}`, "POST");
  assert.equal(res.status, 405);
});
