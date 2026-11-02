// Formring delivery: buyer door (a paid formring session; app-suite only after the launch gate flips), public
// trial with a daily cap, and the token-gated update channel. Stripe and Netlify Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/formring-download.test.mjs

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
const env = { STRIPE_SECRET_KEY: "sk_test_dummy", FORMRING_UPDATE_TOKEN: TOKEN };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const handler = (await import("../functions/formring-download.mjs")).default;
const { LICENSED_PRODUCTS } = await import("../lib/license.mjs");

const SESSION = "cs_live_abcdefghij1234";
let session;
let stripeCalls;
const APPCAST = `<rss><channel><item><enclosure url="https://example.invalid/some/path/Formring-1.0.0.dmg" sparkle:edSignature="sig" length="9"/></item></channel></rss>`;

beforeEach(() => {
  stores.clear();
  stripeCalls = 0;
  stores.set("formring-files/Formring-1.0.0.dmg", "x");
  stores.set("formring-files/Formring-1.1.0.dmg", "x");
  stores.set("formring-files/Formring-1.10.0.dmg", "x");
  stores.set("formring-files/appcast.xml", APPCAST);
  env.FORMRING_UPDATE_TOKEN = TOKEN;
  session = { id: SESSION, payment_status: "paid", metadata: { product: "formring" } };
  globalThis.fetch = async (url) => {
    if (String(url).startsWith("https://api.stripe.com/v1/checkout/sessions/")) {
      stripeCalls++;
      return new Response(JSON.stringify(session), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
});

const call = (query, headers = {}, method = "GET") =>
  handler(new Request(`https://purplelink.llc/.netlify/functions/formring-download?${query}`, {
    method, headers: { "x-nf-client-connection-ip": "198.51.100.5", ...headers },
  }), {});

// --- buyer door ---------------------------------------------------------------------

test("a paid Formring session lists the newest DMG", async () => {
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.files.length, 1);
  assert.equal(body.files[0].key, "Formring-1.10.0.dmg");
  assert.match(body.files[0].label, /Formring 1\.10\.0 for macOS/);
  assert.match(body.files[0].url, /formring-download\?session_id=cs_live_abcdefghij1234&file=Formring-1\.10\.0\.dmg/);
});

test("a paid session streams a named DMG, including an older release", async () => {
  const res = await call(`session_id=${SESSION}&file=Formring-1.0.0.dmg`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/x-apple-diskimage");
  assert.match(res.headers.get("content-disposition"), /attachment; filename="Formring-1\.0\.0\.dmg"/);
  assert.equal(await res.text(), "bytes:Formring-1.0.0.dmg");
});

test("an unpaid session is refused", async () => {
  session.payment_status = "unpaid";
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "not_paid");
});

test("a paid session for another product is refused", async () => {
  for (const product of ["moderntex", "outbound-veil", "legroom", "lenscrib", "kit-bundle", "bundle-2", "bundle-3", ""]) {
    session.metadata = product ? { product } : {};
    const res = await call(`session_id=${SESSION}`);
    assert.equal(res.status, 403, product);
    assert.equal((await res.json()).error, "not_entitled");
  }
});

test("a paid Mac Suite session is refused while the launch gate is closed, so Suite buyers do not get Formring yet", async () => {
  assert.equal(LICENSED_PRODUCTS.formring.inSuite, false, "the shipped state is gated");
  session.metadata.product = "app-suite";
  const list = await call(`session_id=${SESSION}`);
  assert.equal(list.status, 403);
  assert.equal((await list.json()).error, "not_entitled");
  assert.equal((await call(`session_id=${SESSION}&file=Formring-1.0.0.dmg`)).status, 403);
});

test("a paid Mac Suite session is accepted once the launch gate is flipped", async () => {
  LICENSED_PRODUCTS.formring.inSuite = true;
  try {
    session.metadata.product = "app-suite";
    const list = await call(`session_id=${SESSION}`);
    assert.equal(list.status, 200);
    assert.equal((await list.json()).files[0].key, "Formring-1.10.0.dmg");
  } finally {
    LICENSED_PRODUCTS.formring.inSuite = false;
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

test("path traversal and channel names in file= are not served", async () => {
  for (const file of ["../Formring-1.0.0.dmg", "..%2Fformring-files%2FFormring-1.0.0.dmg", "appcast.xml", "Formring-1.0.0.dmg.bak", "Formring-1.0.dmg", "formring-1.0.0.dmg"]) {
    const res = await call(`session_id=${SESSION}&file=${file}`);
    assert.equal(res.status, 404, file);
    assert.equal((await res.json()).error, "unknown_file");
  }
});

test("a well-formed file name that is not in the store is a plain 404, not a crash", async () => {
  const res = await call(`session_id=${SESSION}&file=Formring-9.9.9.dmg`);
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

test("the trial is public and streams the newest DMG, the same file buyers get", async () => {
  const res = await call("trial=1");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-disposition"), /filename="Formring-1\.10\.0\.dmg"/);
  assert.equal(await res.text(), "bytes:Formring-1.10.0.dmg");
  assert.equal(stripeCalls, 0, "the trial never asks Stripe anything");
});

test("the trial door stays closed (404) while no release is staged", async () => {
  stores.clear();
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
  for (const q of ["feed=1", "update=Formring-1.0.0.dmg", "stats=1"]) {
    const res = await call(q);
    assert.equal(res.status, 403, q);
    assert.equal((await res.json()).error, "forbidden");
  }
});

test("the feed and the update download refuse a wrong token, of any length", async () => {
  for (const bad of ["wrong", TOKEN.slice(0, -1), `${TOKEN}x`, TOKEN.toUpperCase(), "x".repeat(TOKEN.length)]) {
    for (const q of ["feed=1", "update=Formring-1.0.0.dmg"]) {
      assert.equal((await call(q, { "x-formring-channel": bad })).status, 403, `${q} with ${bad}`);
    }
  }
});

test("another product's channel header does not open the Formring channel", async () => {
  assert.equal((await call("feed=1", { "x-legroom-channel": TOKEN })).status, 403);
});

test("the channel stays closed when the token is not configured, even for an empty header", async () => {
  env.FORMRING_UPDATE_TOKEN = "";
  assert.equal((await call("feed=1", { "x-formring-channel": "" })).status, 403);
  delete env.FORMRING_UPDATE_TOKEN;
  assert.equal((await call("feed=1", { "x-formring-channel": "" })).status, 403);
});

test("the right token serves the appcast with every enclosure pointed at the update door", async () => {
  const res = await call("feed=1", { "x-formring-channel": TOKEN });
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /rss\+xml/);
  const xml = await res.text();
  assert.match(xml, /url="https:\/\/purplelink\.llc\/\.netlify\/functions\/formring-download\?update=Formring-1\.0\.0\.dmg"/);
  assert.doesNotMatch(xml, /example\.invalid/);
  assert.match(xml, /sparkle:edSignature="sig"/, "the signature is left untouched");
});

test("a signed feed is served byte for byte, never rewritten", async () => {
  const signed = APPCAST.replace(/url="[^"]*"/g, 'url="https://cdn.example/Formring-1.0.0.dmg"') +
    "<!-- sparkle-signatures:\nedSignature: AAAA\nlength: 10\n-->";
  stores.set("formring-files/appcast.xml", signed);
  const res = await call("feed=1", { "x-formring-channel": TOKEN });
  assert.equal(res.status, 200);
  assert.equal(await res.text(), signed);
});

test("the feed is a 404 when no appcast is staged", async () => {
  stores.delete("formring-files/appcast.xml");
  assert.equal((await call("feed=1", { "x-formring-channel": TOKEN })).status, 404);
});

test("the right token streams a DMG by name and counts the download", async () => {
  const res = await call("update=Formring-1.1.0.dmg", { "x-formring-channel": TOKEN });
  assert.equal(res.status, 200);
  assert.equal(await res.text(), "bytes:Formring-1.1.0.dmg");
  assert.equal(stores.get("formring-stats/downloads:Formring-1.1.0.dmg"), "1");
  await call("update=Formring-1.1.0.dmg", { "x-formring-channel": TOKEN });
  assert.equal(stores.get("formring-stats/downloads:Formring-1.1.0.dmg"), "2");
});

test("the update door rejects traversal, trial builds and unknown names even with the right token", async () => {
  for (const file of ["../Formring-1.0.0.dmg", "appcast.xml", "Formring-1.0.dmg", "other.dmg"]) {
    const res = await call(`update=${file}`, { "x-formring-channel": TOKEN });
    assert.equal(res.status, 400, file);
    assert.equal((await res.json()).error, "bad_file");
  }
  const missing = await call("update=Formring-9.9.9.dmg", { "x-formring-channel": TOKEN });
  assert.equal(missing.status, 404);
});

test("the token is never echoed in a response or written to the log", async () => {
  const logged = [];
  const orig = { log: console.log, error: console.error, warn: console.warn };
  console.log = console.error = console.warn = (...a) => logged.push(a.join(" "));
  try {
    const bodies = [];
    for (const [q, h] of [["feed=1", {}], ["feed=1", { "x-formring-channel": "nope" }], ["feed=1", { "x-formring-channel": TOKEN }], ["stats=1", { "x-formring-channel": TOKEN }]]) {
      const r = await call(q, h);
      bodies.push(await r.text());
    }
    assert.ok(!bodies.slice(0, 2).some((b) => b.includes(TOKEN)));
  } finally {
    Object.assign(console, orig);
  }
  assert.ok(!logged.some((l) => l.includes(TOKEN)));
});
