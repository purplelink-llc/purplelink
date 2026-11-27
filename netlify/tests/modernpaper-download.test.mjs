// ModernPaper delivery: buyer door (paid session of modernpaper; app-suite only once ModernPaper is in the Suite), public trial with a daily
// cap, and the token-gated update channel. Stripe and Netlify Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/modernpaper-download.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";

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
const env = { STRIPE_SECRET_KEY: "sk_test_dummy", MODERNPAPER_UPDATE_TOKEN: TOKEN };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const handler = (await import("../functions/modernpaper-download.mjs")).default;
const { verifyLicense, LICENSED_PRODUCTS } = await import("../lib/license.mjs");
const { licenseKeysForSession } = await import("../functions/stripe-webhook.mjs");

const SESSION = "cs_live_abcdefghij1234";
let session;
let stripeCalls;
const APPCAST = `<rss><channel><item><enclosure url="https://example.invalid/some/path/ModernPaper-1.0.0.dmg" sparkle:edSignature="sig" length="9"/></item></channel></rss>`;

beforeEach(() => {
  stores.clear();
  stripeCalls = 0;
  stores.set("modernpaper-files/ModernPaper-1.0.0.dmg", "x");
  stores.set("modernpaper-files/ModernPaper-1.1.0.dmg", "x");
  stores.set("modernpaper-files/ModernPaper-1.10.0.dmg", "x");
  stores.set("modernpaper-files/appcast.xml", APPCAST);
  env.MODERNPAPER_UPDATE_TOKEN = TOKEN;
  session = { id: SESSION, payment_status: "paid", payment_intent: "pi_test_1", metadata: { product: "modernpaper" } };
  globalThis.fetch = async (url) => {
    if (String(url).startsWith("https://api.stripe.com/v1/checkout/sessions/")) {
      stripeCalls++;
      return new Response(JSON.stringify(session), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${url}`);
  };
});

const call = (query, headers = {}, method = "GET") =>
  handler(new Request(`https://purplelink.llc/.netlify/functions/modernpaper-download?${query}`, {
    method, headers: { "x-nf-client-connection-ip": "198.51.100.5", ...headers },
  }), {});

// --- buyer door ---------------------------------------------------------------------

test("a paid ModernPaper session lists the newest paid DMG, never the trial build", async () => {
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.files.length, 1);
  assert.equal(body.files[0].key, "ModernPaper-1.10.0.dmg");
  assert.match(body.files[0].label, /ModernPaper 1\.10\.0 for macOS/);
  assert.ok(!body.files.some((f) => /Trial/.test(f.key)));
  assert.match(body.files[0].url, /modernpaper-download\?session_id=cs_live_abcdefghij1234&file=ModernPaper-1\.10\.0\.dmg/);
});

test("a paid session streams a named DMG, including an older release", async () => {
  const res = await call(`session_id=${SESSION}&file=ModernPaper-1.0.0.dmg`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/x-apple-diskimage");
  assert.match(res.headers.get("content-disposition"), /attachment; filename="ModernPaper-1\.0\.0\.dmg"/);
  assert.equal(await res.text(), "bytes:ModernPaper-1.0.0.dmg");
});

test("an unpaid session is refused", async () => {
  session.payment_status = "unpaid";
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "not_paid");
});

test("a paid session for another product is refused", async () => {
  for (const product of ["moderntex", "outbound-veil", "legroom", "keyfeel", "tapefolio", "nee", "lenses", "kit-bundle", ""]) {
    session.metadata = product ? { product } : {};
    const res = await call(`session_id=${SESSION}`);
    assert.equal(res.status, 403, product);
    assert.equal((await res.json()).error, "not_entitled");
  }
});

test("a Mac Suite session is refused while ModernPaper is outside the Suite, and accepted once inSuite is removed", async () => {
  session.metadata.product = "app-suite";
  const closed = await call(`session_id=${SESSION}`);
  assert.equal(closed.status, 403);
  assert.equal((await closed.json()).error, "not_entitled");
  // The public-launch flip: delete `inSuite: false` from the modernpaper entry in netlify/lib/license.mjs.
  const entry = LICENSED_PRODUCTS.modernpaper;
  const was = entry.inSuite;
  delete entry.inSuite;
  try {
    const list = await call(`session_id=${SESSION}`);
    assert.equal(list.status, 200);
    assert.equal((await list.json()).files[0].key, "ModernPaper-1.10.0.dmg");
    assert.equal((await call(`session_id=${SESSION}&file=ModernPaper-1.0.0.dmg`)).status, 200);
  } finally {
    entry.inSuite = was;
  }
});

test("a fully refunded or disputed order is refused, for the list and for the file", async () => {
  stores.set("refunds/pi:pi_test_1", JSON.stringify({ reason: "refund" }));
  const res = await call(`session_id=${SESSION}`);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "refunded");
  assert.equal((await call(`session_id=${SESSION}&file=ModernPaper-1.0.0.dmg`)).status, 403);
  stores.set("refunds/pi:pi_test_1", JSON.stringify({ reason: "dispute" }));
  assert.equal((await call(`session_id=${SESSION}`)).status, 403);
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
  for (const file of ["../ModernPaper-1.0.0.dmg", "..%2Fmodernpaper-files%2FModernPaper-1.0.0.dmg", "appcast.xml", "ModernPaper-Trial-1.2.0.dmg", "ModernPaper-1.0.0.dmg.bak", "ModernPaper-1.0.dmg", "modernpaper-1.0.0.dmg", "KeyFeel-1.0.0.dmg"]) {
    const res = await call(`session_id=${SESSION}&file=${file}`);
    assert.equal(res.status, 404, file);
    assert.equal((await res.json()).error, "unknown_file");
  }
});

test("a well-formed file name that is not in the store is a plain 404, not a crash", async () => {
  const res = await call(`session_id=${SESSION}&file=ModernPaper-9.9.9.dmg`);
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

test("the public download streams the newest DMG without asking Stripe anything", async () => {
  for (const q of ["download=1", "trial=1"]) {
    const res = await call(q);
    assert.equal(res.status, 200, q);
    assert.match(res.headers.get("content-disposition"), /filename="ModernPaper-1\.10\.0\.dmg"/);
    assert.equal(await res.text(), "bytes:ModernPaper-1.10.0.dmg");
  }
  assert.equal(stripeCalls, 0);
});

test("the public download is 404 when nothing is staged", async () => {
  for (const k of [...stores.keys()]) if (/\.dmg$/.test(k)) stores.delete(k);
  const res = await call("download=1");
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error, "no_release");
});

test("the public download allows 20 per address per day, then 429; another address is unaffected", async () => {
  for (let i = 0; i < 20; i++) assert.equal((await call("download=1")).status, 200, `download ${i + 1}`);
  const blocked = await call("download=1");
  assert.equal(blocked.status, 429);
  assert.equal((await blocked.json()).error, "rate_limited");
  const other = await call("download=1", { "x-nf-client-connection-ip": "198.51.100.77" });
  assert.equal(other.status, 200);
});

// The key is the shared PurplelinkLicenseV1 scheme (netlify/lib/license.mjs), derived from the session id, so it equals
// the one the receipt email and purchase-license carry. The test signs with its own key pair via PURPLELINK_LICENSE_PUBLIC_KEY.
function testPair() {
  const { privateKey } = generateKeyPairSync("ed25519");
  const j = privateKey.export({ format: "jwk" });
  const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");
  return { seedB64: b64(j.d), publicB64: b64(j.x) };
}
const pair = testPair();
const KEY_SHAPE = /^MP1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/;
const withSigning = () => { env.PURPLELINK_LICENSE_PRIVATE_KEY = pair.seedB64; env.PURPLELINK_LICENSE_PUBLIC_KEY = pair.publicB64; };
const withoutSigning = () => { delete env.PURPLELINK_LICENSE_PRIVATE_KEY; delete env.PURPLELINK_LICENSE_PUBLIC_KEY; };

test("a purchase returns the buyer's MP1 key, the same every time, and null when signing is not configured", async () => {
  assert.equal((await (await call(`session_id=${SESSION}`)).json()).license, null);
  withSigning();
  const a = (await (await call(`session_id=${SESSION}`)).json()).license;
  const b = (await (await call(`session_id=${SESSION}`)).json()).license;
  withoutSigning();
  assert.match(a ?? "", KEY_SHAPE);
  assert.equal(a, b);
  assert.equal(verifyLicense("modernpaper", a, { publicB64: pair.publicB64 }), true);
  assert.equal(verifyLicense("nee", a, { publicB64: pair.publicB64 }), false);
});

test("the returned key is the one the receipt email and the success page carry", async () => {
  withSigning();
  const fromDoor = (await (await call(`session_id=${SESSION}`)).json()).license;
  const mine = licenseKeysForSession("modernpaper", SESSION, {}).find((k) => k.slug === "modernpaper");
  withoutSigning();
  assert.equal(fromDoor, mine?.key);
});

test("the key follows the session, not the address", async () => {
  withSigning();
  const a = (await (await call(`session_id=${SESSION}`)).json()).license;
  session.id = "cs_live_zzzzzzzzzz9999";
  const other = (await (await call(`session_id=cs_live_zzzzzzzzzz9999`)).json()).license;
  withoutSigning();
  assert.notEqual(a, other);
});

test("another product's signing secret does not make a ModernPaper key", async () => {
  session.customer_details = { email: "buyer@example.com" };
  env.KEYFEEL_LICENSE_PRIVATE_KEY = pair.seedB64;
  env.MODERNPAPER_LICENSE_PRIVATE_KEY = pair.seedB64;
  const body = await (await call(`session_id=${SESSION}`)).json();
  delete env.KEYFEEL_LICENSE_PRIVATE_KEY;
  delete env.MODERNPAPER_LICENSE_PRIVATE_KEY;
  assert.equal(body.license, null);
});

test("the key is never returned by the public download or the update door", async () => {
  withSigning();
  const dl = await (await call("download=1")).text();
  const feed = await (await call("feed=1", { "x-modernpaper-channel": TOKEN })).text();
  withoutSigning();
  for (const body of [dl, feed]) assert.doesNotMatch(body, /MP1-/);
});

// --- update channel -----------------------------------------------------------------

test("the feed and the update download refuse a missing token", async () => {
  for (const q of ["feed=1", "update=ModernPaper-1.0.0.dmg", "stats=1"]) {
    const res = await call(q);
    assert.equal(res.status, 403, q);
    assert.equal((await res.json()).error, "forbidden");
  }
});

test("the feed and the update download refuse a wrong token, of any length", async () => {
  for (const bad of ["wrong", TOKEN.slice(0, -1), `${TOKEN}x`, TOKEN.toUpperCase(), "x".repeat(TOKEN.length)]) {
    for (const q of ["feed=1", "update=ModernPaper-1.0.0.dmg"]) {
      assert.equal((await call(q, { "x-modernpaper-channel": bad })).status, 403, `${q} with ${bad}`);
    }
  }
});

test("another product's channel header does not open the ModernPaper channel", async () => {
  assert.equal((await call("feed=1", { "x-outboundveil-channel": TOKEN })).status, 403);
  assert.equal((await call("feed=1", { "x-legroom-channel": TOKEN })).status, 403);
  assert.equal((await call("feed=1", { "x-keyfeel-channel": TOKEN })).status, 403);
});

test("the channel stays closed when the token is not configured, even for an empty header", async () => {
  env.MODERNPAPER_UPDATE_TOKEN = "";
  assert.equal((await call("feed=1", { "x-modernpaper-channel": "" })).status, 403);
  delete env.MODERNPAPER_UPDATE_TOKEN;
  assert.equal((await call("feed=1", { "x-modernpaper-channel": "" })).status, 403);
});

test("the right token serves the appcast with every enclosure pointed at the update door", async () => {
  const res = await call("feed=1", { "x-modernpaper-channel": TOKEN });
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /rss\+xml/);
  const xml = await res.text();
  assert.match(xml, /url="https:\/\/purplelink\.llc\/\.netlify\/functions\/modernpaper-download\?update=ModernPaper-1\.0\.0\.dmg"/);
  assert.doesNotMatch(xml, /example\.invalid/);
  assert.match(xml, /sparkle:edSignature="sig"/, "the signature is left untouched");
});

test("the feed is a 404 when no appcast is staged", async () => {
  stores.delete("modernpaper-files/appcast.xml");
  assert.equal((await call("feed=1", { "x-modernpaper-channel": TOKEN })).status, 404);
});

test("the right token streams a DMG by name and counts the download", async () => {
  const res = await call("update=ModernPaper-1.1.0.dmg", { "x-modernpaper-channel": TOKEN });
  assert.equal(res.status, 200);
  assert.equal(await res.text(), "bytes:ModernPaper-1.1.0.dmg");
  assert.equal(stores.get("modernpaper-stats/downloads:ModernPaper-1.1.0.dmg"), "1");
  await call("update=ModernPaper-1.1.0.dmg", { "x-modernpaper-channel": TOKEN });
  assert.equal(stores.get("modernpaper-stats/downloads:ModernPaper-1.1.0.dmg"), "2");
});

test("the update door rejects traversal, trial builds and unknown names even with the right token", async () => {
  for (const file of ["../ModernPaper-1.0.0.dmg", "appcast.xml", "ModernPaper-Trial-1.2.0.dmg", "ModernPaper-1.0.dmg", "other.dmg"]) {
    const res = await call(`update=${file}`, { "x-modernpaper-channel": TOKEN });
    assert.equal(res.status, 400, file);
    assert.equal((await res.json()).error, "bad_file");
  }
  const missing = await call("update=ModernPaper-9.9.9.dmg", { "x-modernpaper-channel": TOKEN });
  assert.equal(missing.status, 404);
});

test("the token is never echoed in a response or written to the log", async () => {
  const logged = [];
  const orig = { log: console.log, error: console.error, warn: console.warn };
  console.log = console.error = console.warn = (...a) => logged.push(a.join(" "));
  try {
    const bodies = [];
    for (const [q, h] of [["feed=1", {}], ["feed=1", { "x-modernpaper-channel": "nope" }], ["feed=1", { "x-modernpaper-channel": TOKEN }], ["stats=1", { "x-modernpaper-channel": TOKEN }]]) {
      const r = await call(q, h);
      bodies.push(await r.text());
    }
    assert.ok(!bodies.slice(0, 2).some((b) => b.includes(TOKEN)));
  } finally {
    Object.assign(console, orig);
  }
  assert.ok(!logged.some((l) => l.includes(TOKEN)));
});
