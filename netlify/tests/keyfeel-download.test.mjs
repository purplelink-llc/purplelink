// Keyfeel delivery: buyer door (paid session of keyfeel or app-suite), public trial with a daily
// cap, and the token-gated update channel. Stripe and Netlify Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/keyfeel-download.test.mjs

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

const TOKEN = "channel-token-for-tests-0123456789";
const env = { STRIPE_SECRET_KEY: "sk_test_dummy", KEYFEEL_UPDATE_TOKEN: TOKEN };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const handler = (await import("../functions/keyfeel-download.mjs")).default;

const SESSION = "cs_live_abcdefghij1234";
let session;
let stripeCalls;
const APPCAST = `<rss><channel><item><enclosure url="https://example.invalid/some/path/Keyfeel-1.0.0.dmg" sparkle:edSignature="sig" length="9"/></item></channel></rss>`;

beforeEach(() => {
  stores.clear();
  stripeCalls = 0;
  stores.set("keyfeel-files/Keyfeel-1.0.0.dmg", "x");
  stores.set("keyfeel-files/Keyfeel-1.1.0.dmg", "x");
  stores.set("keyfeel-files/Keyfeel-1.10.0.dmg", "x");
  stores.set("keyfeel-files/Keyfeel-Trial-1.0.0.dmg", "x");
  stores.set("keyfeel-files/Keyfeel-Trial-1.2.0.dmg", "x");
  stores.set("keyfeel-files/appcast.xml", APPCAST);
  env.KEYFEEL_UPDATE_TOKEN = TOKEN;
  session = { id: SESSION, payment_status: "paid", metadata: { product: "keyfeel" } };
  globalThis.fetch = async (url) => {
    if (String(url).startsWith("https://api.stripe.com/v1/checkout/sessions/")) {
      stripeCalls++;
      return new Response(JSON.stringify(session), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
});

const call = (query, headers = {}, method = "GET") =>
  handler(new Request(`https://purplelink.llc/.netlify/functions/keyfeel-download?${query}`, {
    method, headers: { "x-nf-client-connection-ip": "198.51.100.5", ...headers },
  }), {});

// --- buyer door ---------------------------------------------------------------------

test("a paid Keyfeel session lists the newest paid DMG, never the trial build", async () => {
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.files.length, 1);
  assert.equal(body.files[0].key, "Keyfeel-1.10.0.dmg");
  assert.match(body.files[0].label, /Keyfeel 1\.10\.0 for macOS/);
  assert.ok(!body.files.some((f) => /Trial/.test(f.key)));
  assert.match(body.files[0].url, /keyfeel-download\?session_id=cs_live_abcdefghij1234&file=Keyfeel-1\.10\.0\.dmg/);
});

test("a paid session streams a named DMG, including an older release", async () => {
  const res = await call(`session_id=${SESSION}&file=Keyfeel-1.0.0.dmg`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/x-apple-diskimage");
  assert.match(res.headers.get("content-disposition"), /attachment; filename="Keyfeel-1\.0\.0\.dmg"/);
  assert.equal(await res.text(), "bytes:Keyfeel-1.0.0.dmg");
});

test("an unpaid session is refused", async () => {
  session.payment_status = "unpaid";
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "not_paid");
});

test("a paid session for another product is refused", async () => {
  for (const product of ["moderntex", "outbound-veil", "legroom", "kit-bundle", ""]) {
    session.metadata = product ? { product } : {};
    const res = await call(`session_id=${SESSION}`);
    assert.equal(res.status, 403, product);
    assert.equal((await res.json()).error, "not_entitled");
  }
});

test("a paid Mac Suite session is accepted, so existing Suite buyers get Keyfeel", async () => {
  session.metadata.product = "app-suite";
  const list = await call(`session_id=${SESSION}`);
  assert.equal(list.status, 200);
  assert.equal((await list.json()).files[0].key, "Keyfeel-1.10.0.dmg");
  assert.equal((await call(`session_id=${SESSION}&file=Keyfeel-1.0.0.dmg`)).status, 200);
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

test("path traversal and trial or channel names in file= are not served", async () => {
  for (const file of ["../Keyfeel-1.0.0.dmg", "..%2Fkeyfeel-files%2FKeyfeel-1.0.0.dmg", "appcast.xml", "Keyfeel-Trial-1.2.0.dmg", "Keyfeel-1.0.0.dmg.bak", "Keyfeel-1.0.dmg", "keyfeel-1.0.0.dmg", "KeyFeel-1.0.0.dmg"]) {
    const res = await call(`session_id=${SESSION}&file=${file}`);
    assert.equal(res.status, 404, file);
    assert.equal((await res.json()).error, "unknown_file");
  }
});

test("a well-formed file name that is not in the store is a plain 404, not a crash", async () => {
  const res = await call(`session_id=${SESSION}&file=Keyfeel-9.9.9.dmg`);
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
  assert.equal((await call(`session_id=${SESSION}`, {}, "POST")).status, 405);
});

// --- trial door ---------------------------------------------------------------------

test("the trial is public and streams the newest trial DMG", async () => {
  const res = await call("trial=1");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-disposition"), /filename="Keyfeel-Trial-1\.2\.0\.dmg"/);
  assert.equal(await res.text(), "bytes:Keyfeel-Trial-1.2.0.dmg");
  assert.equal(stripeCalls, 0, "the trial never asks Stripe anything");
});

test("the trial is 404 when no trial build is staged", async () => {
  stores.delete("keyfeel-files/Keyfeel-Trial-1.0.0.dmg");
  stores.delete("keyfeel-files/Keyfeel-Trial-1.2.0.dmg");
  const res = await call("trial=1");
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error, "no_trial");
});

test("the trial allows 20 downloads per address per day, then 429; another address is unaffected", async () => {
  for (let i = 0; i < 20; i++) assert.equal((await call("trial=1")).status, 200, `download ${i + 1}`);
  const blocked = await call("trial=1");
  assert.equal(blocked.status, 429);
  assert.equal((await blocked.json()).error, "rate_limited");
  const other = await call("trial=1", { "x-nf-client-connection-ip": "198.51.100.77" });
  assert.equal(other.status, 200);
});

// --- update channel -----------------------------------------------------------------

test("the feed and the update download refuse a missing token", async () => {
  for (const q of ["feed=1", "update=Keyfeel-1.0.0.dmg", "stats=1"]) {
    const res = await call(q);
    assert.equal(res.status, 403, q);
    assert.equal((await res.json()).error, "forbidden");
  }
});

test("the feed and the update download refuse a wrong token, of any length", async () => {
  for (const bad of ["wrong", TOKEN.slice(0, -1), `${TOKEN}x`, TOKEN.toUpperCase(), "x".repeat(TOKEN.length)]) {
    for (const q of ["feed=1", "update=Keyfeel-1.0.0.dmg"]) {
      assert.equal((await call(q, { "x-keyfeel-channel": bad })).status, 403, `${q} with ${bad}`);
    }
  }
});

test("another product's channel header does not open the Keyfeel channel", async () => {
  assert.equal((await call("feed=1", { "x-outboundveil-channel": TOKEN })).status, 403);
  assert.equal((await call("feed=1", { "x-legroom-channel": TOKEN })).status, 403);
});

test("the channel stays closed when the token is not configured, even for an empty header", async () => {
  env.KEYFEEL_UPDATE_TOKEN = "";
  assert.equal((await call("feed=1", { "x-keyfeel-channel": "" })).status, 403);
  delete env.KEYFEEL_UPDATE_TOKEN;
  assert.equal((await call("feed=1", { "x-keyfeel-channel": "" })).status, 403);
});

test("the right token serves the appcast with every enclosure pointed at the update door", async () => {
  const res = await call("feed=1", { "x-keyfeel-channel": TOKEN });
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /rss\+xml/);
  const xml = await res.text();
  assert.match(xml, /url="https:\/\/purplelink\.llc\/\.netlify\/functions\/keyfeel-download\?update=Keyfeel-1\.0\.0\.dmg"/);
  assert.doesNotMatch(xml, /example\.invalid/);
  assert.match(xml, /sparkle:edSignature="sig"/, "the signature is left untouched");
});

test("the feed is a 404 when no appcast is staged", async () => {
  stores.delete("keyfeel-files/appcast.xml");
  assert.equal((await call("feed=1", { "x-keyfeel-channel": TOKEN })).status, 404);
});

test("the right token streams a DMG by name and counts the download", async () => {
  const res = await call("update=Keyfeel-1.1.0.dmg", { "x-keyfeel-channel": TOKEN });
  assert.equal(res.status, 200);
  assert.equal(await res.text(), "bytes:Keyfeel-1.1.0.dmg");
  assert.equal(stores.get("keyfeel-stats/downloads:Keyfeel-1.1.0.dmg"), "1");
  await call("update=Keyfeel-1.1.0.dmg", { "x-keyfeel-channel": TOKEN });
  assert.equal(stores.get("keyfeel-stats/downloads:Keyfeel-1.1.0.dmg"), "2");
});

test("the update door rejects traversal, trial builds and unknown names even with the right token", async () => {
  for (const file of ["../Keyfeel-1.0.0.dmg", "appcast.xml", "Keyfeel-Trial-1.2.0.dmg", "Keyfeel-1.0.dmg", "other.dmg"]) {
    const res = await call(`update=${file}`, { "x-keyfeel-channel": TOKEN });
    assert.equal(res.status, 400, file);
    assert.equal((await res.json()).error, "bad_file");
  }
  const missing = await call("update=Keyfeel-9.9.9.dmg", { "x-keyfeel-channel": TOKEN });
  assert.equal(missing.status, 404);
});

test("the token is never echoed in a response or written to the log", async () => {
  const logged = [];
  const orig = { log: console.log, error: console.error, warn: console.warn };
  console.log = console.error = console.warn = (...a) => logged.push(a.join(" "));
  try {
    const bodies = [];
    for (const [q, h] of [["feed=1", {}], ["feed=1", { "x-keyfeel-channel": "nope" }], ["feed=1", { "x-keyfeel-channel": TOKEN }], ["stats=1", { "x-keyfeel-channel": TOKEN }]]) {
      const r = await call(q, h);
      bodies.push(await r.text());
    }
    assert.ok(!bodies.slice(0, 2).some((b) => b.includes(TOKEN)));
  } finally {
    Object.assign(console, orig);
  }
  assert.ok(!logged.some((l) => l.includes(TOKEN)));
});
