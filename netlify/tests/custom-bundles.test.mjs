// Custom bundles of the Mac Suite (any 2 parts 25% off, any 3 parts 40% off): the price table and its copy on the page,
// checkout validation, which download doors a bundle opens, which keys it gets, the purchase email, the success-page
// key endpoint and the recovery email. Stripe, Resend and Blobs are stubbed; the signing keys are throwaways.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/custom-bundles.test.mjs

import { readFileSync } from "node:fs";
import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac, generateKeyPairSync } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    list: async () => ({ blobs: [...store.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
    getWithMetadata: async (k) => (store.has(`${name}/${k}`) ? { data: new Response(`bytes:${k}`).body, metadata: { size: 9 } } : null),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { privateKey } = generateKeyPairSync("ed25519");
const jwk = privateKey.export({ format: "jwk" });
const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");
const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", RESEND_API_KEY: "re_dummy",
  MODERNTEX_LICENSE_PRIVATE_KEY: Buffer.from(jwk.d, "base64url").toString("base64"),
  PURPLELINK_LICENSE_PRIVATE_KEY: b64(jwk.d), PURPLELINK_LICENSE_PUBLIC_KEY: b64(jwk.x),
  KEYFEEL_LICENSE_PRIVATE_KEY: Buffer.alloc(32, 9).toString("base64"),
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const lib = await import("../lib/bundles.mjs");
const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook, licenseKeysForSession, BLOB_DELIVERED_PRODUCTS } = await import("../functions/stripe-webhook.mjs");
const { default: purchaseLicense } = await import("../functions/purchase-license.mjs");
const { default: legroomDl } = await import("../functions/legroom-download.mjs");
const { default: keyfeelDl } = await import("../functions/keyfeel-download.mjs");
const { default: tapefolioDl } = await import("../functions/tapefolio-download.mjs");
const { default: ovDl } = await import("../functions/outbound-veil-download.mjs");
const { default: mtxDl } = await import("../functions/moderntex-download.mjs");
const { recoveryEmail } = await import("../functions/purchases-recover.mjs");

let calls;
let session;
beforeEach(() => {
  store.clear();
  calls = [];
  session = null;
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    const u = String(url);
    if (u.includes("api.stripe.com/v1/checkout/sessions") && opts.method === "POST") {
      return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
    }
    if (session && u.startsWith("https://api.stripe.com/v1/checkout/sessions/")) return new Response(JSON.stringify(session), { status: 200 });
    return new Response("{}", { status: 200 });
  };
});

const SID = "cs_live_bundle_0123456789";
const bundle = (product, apps, over = {}) => ({ id: SID, status: "complete", payment_status: "paid", amount_total: 3749,
  customer_details: { email: "buyer@example.com" }, metadata: { product, apps }, ...over });

// ---- the price table and the helper ----

test("two percent tiers, and the ten parts are the Suite's ten", () => {
  assert.deepEqual(lib.BUNDLES, { "bundle-2": { count: 2, percent: 25 }, "bundle-3": { count: 3, percent: 40 } });
  assert.ok(lib.BUNDLES["bundle-2"].percent < lib.BUNDLES["bundle-3"].percent);
  assert.deepEqual(lib.BUNDLE_SLUGS, ["moderntex", "outbound-veil", "legroom", "keyfeel", "tapefolio", "panely", "summonly", "nee", "lenses", "vitae-plus"]);
  assert.deepEqual(Object.keys(lib.PART_CENTS), lib.BUNDLE_SLUGS);
  // The ten parts add up to the Suite's own first-year price stack ($163.90, shown as "$164+" on /suite/).
  assert.equal(Object.values(lib.PART_CENTS).reduce((a, b) => a + b, 0), 16390);
  assert.ok(Object.values(lib.PART_CENTS).reduce((a, b) => a + b, 0) > 5999, "the Suite is cheaper than the parts");
});

test("bundleCents: a pair is 25% off the two prices, a triple 40% off the three", () => {
  assert.equal(lib.bundleCents(["moderntex", "outbound-veil"]), 3749, "$49.98 less 25%");
  assert.equal(lib.bundleCents(["outbound-veil", "moderntex"]), 3749, "order does not matter");
  assert.equal(lib.bundleCents(["moderntex", "outbound-veil", "tapefolio"]), 4798, "$79.97 less 40% = 47.982");
  assert.equal(lib.bundleCents(["legroom", "keyfeel", "lenses"]), 1498, "$24.97 less 40% = 14.982");
});

test("bundleCents: a cheap pair the old fixed price blocked is now sold", () => {
  assert.equal(lib.bundleCents(["lenses", "legroom"]), 1124, "$14.98 less 25% = 11.235 rounds to the cent");
  assert.ok(lib.bundleCents(["lenses", "legroom"]) < 499 + 999, "always cheaper than buying separately");
});

test("bundleCents: rounds half up to the cent, and every pair and triple is cheaper than its parts", () => {
  assert.equal(lib.bundleCents(["panely", "summonly"]), 1499, "1998 x 0.75 = 1498.5 rounds up");
  const slugs = lib.BUNDLE_SLUGS;
  for (const a of slugs) for (const b of slugs) {
    if (a >= b) continue;
    const c = lib.bundleCents([a, b]);
    assert.ok(Number.isInteger(c) && c < lib.PART_CENTS[a] + lib.PART_CENTS[b], `${a}+${b}`);
    for (const d of slugs) {
      if (b >= d) continue;
      const t = lib.bundleCents([a, b, d]);
      assert.ok(Number.isInteger(t) && t < lib.PART_CENTS[a] + lib.PART_CENTS[b] + lib.PART_CENTS[d], `${a}+${b}+${d}`);
    }
  }
});

test("bundleCents: invalid input has no price", () => {
  for (const bad of [[], ["moderntex"], ["moderntex", "moderntex"], ["moderntex", "nope"], ["moderntex", 5], "moderntex,legroom", null, undefined, {},
    ["moderntex", "legroom", "keyfeel", "tapefolio"], ["moderntex", "moderntex", "legroom"]]) {
    assert.equal(lib.bundleCents(bad), null, JSON.stringify(bad));
  }
});

test("the page's tables are the server's", () => {
  const src = readFileSync(new URL("../../site/suite/bundle.js", import.meta.url), "utf8");
  const percent = JSON.parse(src.match(/var BUNDLE_PERCENT = (\{.*?\});/)[1]);
  assert.deepEqual(percent, { 2: lib.BUNDLES["bundle-2"].percent, 3: lib.BUNDLES["bundle-3"].percent });
  assert.equal(Number(src.match(/var SUITE_CENTS = (\d+);/)[1]), 5999);
  const parts = JSON.parse(src.match(/var PART_PRICE = (\{.*?\});/)[1]);
  assert.deepEqual(parts, lib.PART_CENTS);
  assert.deepEqual(Object.keys(parts), lib.BUNDLE_SLUGS);
  // The four-or-more message names the Suite's part count; it said "all six" after the Suite grew to eight.
  const words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
  const said = src.match(/the Suite has all (\w+) for/)[1];
  assert.equal(said, words[lib.BUNDLE_SLUGS.length], `the Suite message says "all ${said}"`);
  const html = readFileSync(new URL("../../site/suite/index.html", import.meta.url), "utf8");
  for (const slug of lib.BUNDLE_SLUGS) assert.ok(html.includes(`name="apps" value="${slug}"`), `${slug} is a choice on the page`);
  assert.ok(html.includes("Any 2:</strong> 25% off") && html.includes("Any 3:</strong> 40% off") && html.includes("$59.99"));
  assert.ok(!html.includes("$34.99") && !html.includes("$44.99"), "the old fixed prices are gone");
  const checkout = readFileSync(new URL("../functions/checkout.mjs", import.meta.url), "utf8");
  assert.match(checkout, /"bundle-2":\s+\{ bundle: true,/);
  assert.match(checkout, /bundleCents\(bundleParts\)/);
});

test("parsing: exactly the right number of different, known parts, in the canonical order", () => {
  assert.deepEqual(lib.parseBundleParts(["legroom", "moderntex"], 2), ["moderntex", "legroom"]);
  assert.deepEqual(lib.parseBundleParts("vitae-plus, keyfeel,tapefolio", 3), ["keyfeel", "tapefolio", "vitae-plus"]);
  for (const bad of [[], ["moderntex"], ["moderntex", "moderntex"], ["moderntex", "nope"], ["moderntex", 5], "moderntex", null, undefined, {}, ["moderntex", "legroom", "keyfeel"]]) {
    assert.equal(lib.parseBundleParts(bad, 2), null, JSON.stringify(bad));
  }
  assert.equal(lib.parseBundleParts(["moderntex", "legroom"], 3), null);
  assert.equal(lib.parseBundleParts(["moderntex", "moderntex", "legroom"], 3), null, "a duplicate cannot pad the count");
});

test("entitlements: the Suite is all ten, a bundle its parts, a single app itself, a mismatched bundle nothing", () => {
  assert.equal(lib.entitledParts("app-suite", {}).size, 10);
  assert.deepEqual([...lib.entitledParts("bundle-2", { apps: "legroom,keyfeel" })], ["legroom", "keyfeel"]);
  assert.deepEqual([...lib.entitledParts("legroom", {})], ["legroom"]);
  assert.deepEqual([...lib.entitledParts("moderntex-seats", {})], ["moderntex"]);
  assert.equal(lib.entitledParts("bundle-2", { apps: "legroom,keyfeel,tapefolio" }).size, 0, "three parts on a pick-2 order entitle nothing");
  assert.equal(lib.entitledParts("bundle-3", { apps: "" }).size, 0);
  assert.equal(lib.entitledParts("digest-monthly", { apps: "legroom,keyfeel" }).size, 0);
  assert.equal(lib.bundleHasPart("bundle-2", { apps: "legroom,keyfeel" }, "keyfeel"), true);
  assert.equal(lib.bundleHasPart("bundle-2", { apps: "legroom,keyfeel" }, "tapefolio"), false);
  assert.equal(lib.bundleHasPart("app-suite", {}, "tapefolio"), false, "the Suite is handled by its own check, not this one");
  assert.equal(lib.partsSentence(["moderntex", "legroom", "vitae-plus"]), "ModernTex, Legroom and Vitae Plus for life");
});

// ---- checkout ----

const post = (body, ip = "203.0.113.9") => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": ip }, body: JSON.stringify(body),
}));
const stripeParams = () => new URLSearchParams(calls.find((c) => c.url.includes("/checkout/sessions")).opts.body);

test("checkout prices a bundle from the chosen parts, names the discount and the parts, and records them", async () => {
  const res = await post({ product: "bundle-2", apps: ["outbound-veil", "moderntex"], amount: 1, unit_amount: 1 });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "3749");
  assert.equal(p.get("line_items[0][quantity]"), "1");
  assert.equal(p.get("metadata[product]"), "bundle-2");
  assert.equal(p.get("metadata[apps]"), "moderntex,outbound-veil");
  assert.match(p.get("line_items[0][price_data][product_data][name]"), /^Purplelink Mac Suite bundle, 25% off: ModernTex and Outbound Veil$/);
  assert.match(p.get("success_url"), /\/suite\/success\/\?session_id=/);
  assert.equal(p.get("mode"), "payment");
});

test("a pick-3 is 40% off the three chosen prices, so it follows the parts", async () => {
  const sets = [[["keyfeel", "legroom", "moderntex"], 2398], [["outbound-veil", "tapefolio", "vitae-plus"], 5038], [["moderntex", "outbound-veil", "tapefolio"], 4798]];
  for (const [i, [apps, cents]] of sets.entries()) {
    calls = [];
    assert.equal((await post({ product: "bundle-3", apps }, `198.51.100.${i + 1}`)).status, 200);
    const p = stripeParams();
    assert.equal(p.get("line_items[0][price_data][unit_amount]"), String(cents));
    assert.equal(cents, lib.bundleCents(apps));
    assert.match(p.get("line_items[0][price_data][product_data][name]"), /^Purplelink Mac Suite bundle, 40% off: /);
  }
});

test("a price sent by the client is ignored, and a cheap pair the old fixed price blocked can be bought", async () => {
  assert.equal((await post({ product: "bundle-2", apps: ["lenses", "legroom"], amount: 1, unit_amount: 1, cents: 1 }, "198.51.100.30")).status, 200);
  assert.equal(stripeParams().get("line_items[0][price_data][unit_amount]"), "1124");
});

test("checkout refuses a wrong count, a duplicate, an unknown part or no parts, and creates no session", async () => {
  const cases = [
    ["bundle-2", ["moderntex"]], ["bundle-2", ["moderntex", "legroom", "keyfeel"]], ["bundle-3", ["moderntex", "legroom"]],
    ["bundle-2", ["moderntex", "moderntex"]], ["bundle-2", ["moderntex", "paper-review"]], ["bundle-2", undefined], ["bundle-3", []],
    ["bundle-2", "moderntex,legroom,keyfeel"], ["bundle-2", [1, 2]],
  ];
  for (const [i, [product, apps]] of cases.entries()) {
    calls = [];
    const res = await post({ product, apps }, `198.51.100.${40 + i}`);
    assert.equal(res.status, 400, JSON.stringify([product, apps]));
    assert.equal((await res.json()).error, "invalid_apps");
    assert.equal(calls.some((c) => c.url.includes("/checkout/sessions")), false);
  }
});

test("the Suite and the single apps are unchanged by bundles", async () => {
  await post({ product: "app-suite", apps: ["moderntex", "legroom"] }, "198.51.100.80");
  let p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "5999");
  assert.equal(p.get("metadata[apps]"), null);
  calls = [];
  await post({ product: "keyfeel", apps: ["moderntex", "legroom"] }, "198.51.100.81");
  p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "999");
  assert.equal(p.get("metadata[apps]"), null);
});

// ---- the download doors ----

const callDoor = (handler, name) => handler(new Request(`https://purplelink.llc/.netlify/functions/${name}?session_id=${SID}`, {
  headers: { "x-nf-client-connection-ip": "198.51.100.5" } }), {});

test("a bundle opens the doors of the apps it names and closes the others", async () => {
  session = bundle("bundle-3", "legroom,keyfeel,vitae-plus", { amount_total: 3298 });
  store.set("legroom-files/Legroom-1.1.0.dmg", "x");
  const open = await callDoor(legroomDl, "legroom-download");
  assert.equal(open.status, 200);
  assert.equal((await open.json()).files[0].key, "Legroom-1.1.0.dmg");
  const keyfeelOpen = await callDoor(keyfeelDl, "keyfeel-download");
  assert.notEqual((await keyfeelOpen.json()).error, "not_entitled", "Keyfeel is in the bundle, so it is not refused as not entitled");
  for (const [handler, name] of [[tapefolioDl, "tapefolio-download"], [ovDl, "outbound-veil-download"], [mtxDl, "moderntex-download"]]) {
    const res = await callDoor(handler, name);
    assert.equal(res.status, 403, name);
    assert.equal((await res.json()).error, "not_entitled", name);
  }
});

test("a bundle whose metadata does not match its count opens nothing", async () => {
  session = bundle("bundle-2", "legroom,keyfeel,tapefolio");
  for (const [handler, name] of [[legroomDl, "legroom-download"], [keyfeelDl, "keyfeel-download"], [tapefolioDl, "tapefolio-download"]]) {
    assert.equal((await callDoor(handler, name)).status, 403, name);
  }
  session = bundle("bundle-2", "legroom,keyfeel", { payment_status: "unpaid" });
  assert.equal((await callDoor(legroomDl, "legroom-download")).status, 403, "an unpaid bundle opens nothing");
});

test("the Suite still opens every door", async () => {
  session = { id: SID, payment_status: "paid", metadata: { product: "app-suite" } };
  for (const [handler, name] of [[legroomDl, "legroom-download"], [keyfeelDl, "keyfeel-download"], [tapefolioDl, "tapefolio-download"], [ovDl, "outbound-veil-download"], [mtxDl, "moderntex-download"]]) {
    const res = await callDoor(handler, name);
    assert.notEqual((await res.json()).error, "not_entitled", name);
  }
});

// ---- keys ----

test("a bundle gets keys only for its apps, and they are the Suite's keys for that session", () => {
  const suite = Object.fromEntries(licenseKeysForSession("app-suite", SID).map((k) => [k.slug, k.key]));
  const mine = licenseKeysForSession("bundle-3", SID, { apps: "moderntex,legroom,vitae-plus" });
  assert.deepEqual(mine.map((k) => k.slug), ["moderntex", "legroom"]);
  for (const k of mine) assert.equal(k.key, suite[k.slug]);
  assert.deepEqual(licenseKeysForSession("bundle-2", SID, { apps: "keyfeel,tapefolio" }), [], "Keyfeel and Tapefolio keys come from the buyer's address, not the session");
  assert.deepEqual(licenseKeysForSession("bundle-2", SID, { apps: "outbound-veil,vitae-plus" }).map((k) => k.slug), ["outbound-veil"]);
  assert.deepEqual(licenseKeysForSession("bundle-2", SID, { apps: "nonsense" }), []);
});

test("purchase-license returns a bundle's keys and its parts, and the Suite's keys with no parts", async () => {
  const ask = () => purchaseLicense(new Request(`https://purplelink.llc/.netlify/functions/purchase-license?session_id=${SID}`, {
    headers: { "x-nf-client-connection-ip": "203.0.113.50" } }));
  session = bundle("bundle-2", "moderntex,legroom");
  let body = await (await ask()).json();
  assert.deepEqual(body.parts, ["moderntex", "legroom"]);
  assert.deepEqual(body.keys.map((k) => k.product), ["moderntex", "legroom"]);
  session = bundle("bundle-2", "keyfeel,tapefolio");
  body = await (await ask()).json();
  assert.deepEqual(body.parts, ["keyfeel", "tapefolio"]);
  assert.deepEqual(body.keys, []);
  session = { id: SID, payment_status: "paid", metadata: { product: "app-suite" } };
  body = await (await ask()).json();
  assert.equal(body.parts, undefined);
  assert.equal(body.keys.length, 4, "ModernTex, Outbound Veil, Legroom and Née");
  session = bundle("bundle-2", "moderntex,legroom,keyfeel");
  assert.equal((await ask()).status, 403, "a bundle with a bad parts list is refused");
});

// ---- the purchase email ----

function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", { method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body });
}
const sentMail = () => JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);

test("both bundles are blob-delivered on the Suite page", () => {
  for (const k of ["bundle-2", "bundle-3"]) assert.equal(BLOB_DELIVERED_PRODUCTS.get(k).successPath, "/suite/success/");
});

test("the email for a bundle carries only the chosen parts' keys and says what the page holds", async () => {
  const event = { id: "evt_b1", type: "checkout.session.completed", data: { object: bundle("bundle-3", "moderntex,keyfeel,vitae-plus", { amount_total: 3298 }) } };
  const res = await webhook(signed(event));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = sentMail();
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.subject, /custom bundle/);
  assert.match(mail.text, /\/suite\/success\/\?session_id=cs_live_bundle_0123456789/);
  assert.match(mail.text, /Your bundle: ModernTex, Keyfeel and Vitae Plus for life\./);
  assert.match(mail.text, /lifetime Vitae Plus key/);
  assert.match(mail.text, /MTX1-/);
  assert.match(mail.text, /KFL1-/);
  assert.doesNotMatch(mail.text, /Outbound Veil|Legroom|Tapefolio|TFL1|OV1-|LG1-/);
  assert.doesNotMatch(mail.text, /—|–/);
  // A duplicate delivery of the same event sends nothing more.
  calls = [];
  await webhook(signed(event));
  assert.equal(calls.some((c) => c.url.startsWith("https://api.resend.com/")), false);
});

test("a bundle of two apps with no signed key still gets its page link", async () => {
  const event = { id: "evt_b2", type: "checkout.session.completed", data: { object: bundle("bundle-2", "outbound-veil,legroom") } };
  await webhook(signed(event));
  const mail = sentMail();
  assert.match(mail.text, /Your bundle: Outbound Veil and Legroom\./);
  assert.match(mail.text, /the Outbound Veil and Legroom downloads/);
  // Key prefixes must start a token: a random Legroom key can contain "MTX1" mid-string.
  assert.doesNotMatch(mail.text, /Vitae|\bMTX1-|\bKFL1-|Keyfeel|ModernTex/);
});

// ---- recovery ----

test("the recovery email lists a bundle's parts and keeps the keys of the others out", () => {
  const purchases = [{ sessionId: SID, product: "bundle-2", created: 1, seats: 0, apps: "moderntex,legroom" }];
  const keysBySession = new Map([[SID, licenseKeysForSession("bundle-2", SID, { apps: "moderntex,legroom" }).filter((k) => k.slug !== "moderntex")]]);
  const mail = recoveryEmail(purchases, "MTX1-TESTKEY", "KFL1-SHOULD-NOT-APPEAR", keysBySession, "TFL1-SHOULD-NOT-APPEAR");
  assert.match(mail.text, /Your bundle: ModernTex and Legroom\./);
  assert.match(mail.text, /\/suite\/success\/\?session_id=cs_live_bundle_0123456789/);
  assert.match(mail.text, /ModernTex license key[^\n]*MTX1-TESTKEY/);
  assert.match(mail.text, /Legroom: LG1-/);
  assert.doesNotMatch(mail.text, /KFL1-SHOULD|TFL1-SHOULD/);
});

// ---- the picker on /suite/ ----

import vm from "node:vm";
// A small fake DOM: text nodes and elements, with textContent that flattens, and <s> kept visible as "~~x~~".
const textNode = (t) => ({ nodeType: 3, text: t });
function fakeEl(tag = "div") {
  const el = { tag, children: [], disabled: false, classList: { toggle() {} }, _text: "", addEventListener: () => {} };
  Object.defineProperty(el, "textContent", {
    get() { return el.children.length ? el.children.map((c) => (c.nodeType === 3 ? c.text : c.tag === "s" ? `~~${c.textContent}~~` : c.textContent)).join("") : el._text; },
    set(v) { el.children = []; el._text = v; },
  });
  el.appendChild = (c) => { el.children.push(c); return c; };
  return el;
}
function runPicker(picked) {
  const handlers = {};
  const clicks = [];
  const mk = () => { const e = fakeEl(); e.addEventListener = (t, f) => { clicks.push([t, f]); }; return e; };
  const summary = mk(), buy = mk(), statusEl = mk();
  const form = {
    addEventListener: (t, f) => { handlers[t] = f; },
    querySelectorAll: () => picked.map((value) => ({ value })),
  };
  const sent = [];
  const ctx = {
    document: {
      getElementById: (id) => ({ "bundle-form": form, "bundle-summary": summary, "bundle-buy": buy, "bundle-status": statusEl })[id] || null,
      createElement: (tag) => fakeEl(tag), createTextNode: textNode,
    },
    window: { location: { search: "", assign: (u) => sent.push(["assign", u]) } },
    URLSearchParams, Array, Math, Boolean, Promise, JSON, Number, String, Object,
    fetch: (url, opts) => { sent.push([url, JSON.parse(opts.body)]); return Promise.resolve({ ok: true, json: () => Promise.resolve({ url: "https://checkout.stripe.com/x" }) }); },
  };
  vm.runInNewContext(readFileSync(new URL("../../site/suite/bundle.js", import.meta.url), "utf8"), ctx);
  return { summary, buy, sent, click: () => clicks.find(([t]) => t === "click")[1]() };
}

test("the picker: nothing or one part cannot be bought, and one part names the discount", () => {
  assert.equal(runPicker([]).buy.disabled, true);
  const one = runPicker(["moderntex"]);
  assert.equal(one.buy.disabled, true);
  assert.match(one.summary.textContent, /Choose one more for 25% off both\. Two apps get 25% off, three get 40% off\./);
});

test("the picker: a pair shows the struck-through separate total, the price, the saving and the next tier", async () => {
  const pair = runPicker(["moderntex", "outbound-veil"]);
  assert.equal(pair.buy.disabled, false);
  assert.equal(pair.buy.textContent, "Buy these 2, $37.49");
  assert.ok(pair.summary.textContent.startsWith("2 apps: ~~$49.98~~ $37.49, 25% off, you save $12.49."), pair.summary.textContent);
  // The strike is a real <s> element, not text with markup in it.
  assert.equal(pair.summary.children.filter((c) => c.tag === "s").length, 1);
  assert.ok(pair.summary.children.every((c) => c.nodeType === 3 || c.tag === "s"));
  // Next tier: Lenses ($4.99) is the lowest-priced app left; 40% off $54.97 saves $21.99, 25% off $49.98 saves $12.49.
  assert.match(pair.summary.textContent, /Add a third app for 40% off all three\. With Lenses \(\$4\.99\) your saving goes up by \$9\.50\./);
  pair.click();
  await new Promise((r) => setTimeout(r, 5));
  assert.deepEqual(pair.sent[0], ["/.netlify/functions/checkout", { product: "bundle-2", ref: "", apps: ["moderntex", "outbound-veil"] }]);
});

test("the picker: a cheap pair is sold too, and the nudge skips an app already chosen", () => {
  const cheap = runPicker(["lenses", "legroom"]);
  assert.equal(cheap.buy.disabled, false);
  assert.equal(cheap.buy.textContent, "Buy these 2, $11.24");
  assert.ok(cheap.summary.textContent.startsWith("2 apps: ~~$14.98~~ $11.24, 25% off, you save $3.74."), cheap.summary.textContent);
  assert.match(cheap.summary.textContent, /With Keyfeel \(\$9\.99\)/, "Lenses is taken, so the next cheapest is a $9.99 app");
});

test("the picker: a triple shows 40% off and no further nudge", () => {
  const triple = runPicker(["moderntex", "outbound-veil", "vitae-plus"]);
  assert.equal(triple.buy.textContent, "Buy these 3, $44.38");
  assert.equal(triple.summary.textContent, "3 apps: ~~$73.97~~ $44.38, 40% off, you save $29.59.");
});

test("the picker: four or more offer the Suite, and say so honestly when the apps cost less on their own", async () => {
  const dear = runPicker(["moderntex", "outbound-veil", "legroom", "tapefolio"]);
  assert.equal(dear.buy.disabled, false);
  assert.equal(dear.buy.textContent, "Buy the Suite, $59.99");
  assert.equal(dear.summary.textContent, "For four or more, the Suite has all ten for $59.99. Bought on their own, these would cost $89.96.");
  dear.click();
  await new Promise((r) => setTimeout(r, 5));
  assert.deepEqual(dear.sent[0], ["/.netlify/functions/checkout", { product: "app-suite", ref: "" }]);
  const cheap = runPicker(["legroom", "keyfeel", "panely", "summonly"]);
  assert.equal(cheap.summary.textContent, "For four or more, the Suite has all ten for $59.99, or buy these on their own for $39.96.");
  assert.doesNotMatch(cheap.summary.textContent, /cost more than the Suite/);
});
