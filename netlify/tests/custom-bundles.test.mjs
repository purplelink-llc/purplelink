// Custom bundles of the Mac Suite (pick any 2 for $34.99, any 3 for $44.99): the price table and its copy on the page,
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
const bundle = (product, apps, over = {}) => ({ id: SID, status: "complete", payment_status: "paid", amount_total: 3499,
  customer_details: { email: "buyer@example.com" }, metadata: { product, apps }, ...over });

// ---- the price table and the helper ----

test("two prices, below the Suite, above the dearest single app, and the eight parts are the Suite's eight", () => {
  assert.deepEqual(lib.BUNDLES, { "bundle-2": { count: 2, cents: 3499 }, "bundle-3": { count: 3, cents: 4499 } });
  const dearestSingle = 2999;
  assert.ok(lib.BUNDLES["bundle-2"].cents > dearestSingle, "pick 2 costs more than any single app");
  assert.ok(lib.BUNDLES["bundle-2"].cents < lib.BUNDLES["bundle-3"].cents);
  assert.ok(lib.BUNDLES["bundle-3"].cents < 5999, "pick 3 stays under the Suite");
  assert.deepEqual(lib.BUNDLE_SLUGS, ["moderntex", "outbound-veil", "legroom", "keyfeel", "tapefolio", "panely", "summonly", "vitae-plus"]);
});

test("the page's price tables are the server's", () => {
  const src = readFileSync(new URL("../../site/suite/bundle.js", import.meta.url), "utf8");
  const pricing = JSON.parse(src.match(/var BUNDLE_PRICING = (\{.*?\});/)[1]);
  assert.deepEqual(pricing, { 2: lib.BUNDLES["bundle-2"].cents, 3: lib.BUNDLES["bundle-3"].cents, suite: 5999 });
  const parts = JSON.parse(src.match(/var PART_PRICE = (\{.*?\});/)[1]);
  assert.deepEqual(Object.keys(parts), lib.BUNDLE_SLUGS);
  // The four-or-more message names the Suite's part count; it said "all six" after the Suite grew to eight.
  const words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
  const said = src.match(/which has all (\w+) for/)[1];
  assert.equal(said, words[lib.BUNDLE_SLUGS.length], `the Suite message says "all ${said}"`);
  const html = readFileSync(new URL("../../site/suite/index.html", import.meta.url), "utf8");
  for (const slug of lib.BUNDLE_SLUGS) assert.ok(html.includes(`name="apps" value="${slug}"`), `${slug} is a choice on the page`);
  assert.ok(html.includes("$34.99") && html.includes("$44.99") && html.includes("$59.99"));
  const checkout = readFileSync(new URL("../functions/checkout.mjs", import.meta.url), "utf8");
  assert.match(checkout, /"bundle-2":\s+\{ amount: BUNDLES\["bundle-2"\]\.cents/);
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

test("entitlements: the Suite is all eight, a bundle its parts, a single app itself, a mismatched bundle nothing", () => {
  assert.equal(lib.entitledParts("app-suite", {}).size, 8);
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

test("checkout prices a bundle from its count alone, names the parts and records them", async () => {
  const res = await post({ product: "bundle-2", apps: ["tapefolio", "outbound-veil"], amount: 1, unit_amount: 1 });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "3499");
  assert.equal(p.get("line_items[0][quantity]"), "1");
  assert.equal(p.get("metadata[product]"), "bundle-2");
  assert.equal(p.get("metadata[apps]"), "outbound-veil,tapefolio");
  assert.match(p.get("line_items[0][price_data][product_data][name]"), /custom bundle \(any 2\): Outbound Veil and Tapefolio/);
  assert.match(p.get("success_url"), /\/suite\/success\/\?session_id=/);
  assert.equal(p.get("mode"), "payment");
});

test("a pick-3 costs the same whichever three parts are chosen", async () => {
  const sets = [["keyfeel", "legroom", "moderntex"], ["outbound-veil", "tapefolio", "vitae-plus"], ["moderntex", "outbound-veil", "tapefolio"]];
  for (const [i, apps] of sets.entries()) {
    calls = [];
    assert.equal((await post({ product: "bundle-3", apps }, `198.51.100.${i + 1}`)).status, 200);
    assert.equal(stripeParams().get("line_items[0][price_data][unit_amount]"), "4499");
  }
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
  session = bundle("bundle-3", "legroom,keyfeel,vitae-plus", { amount_total: 4499 });
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
  assert.equal(body.keys.length, 3);
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
  const event = { id: "evt_b1", type: "checkout.session.completed", data: { object: bundle("bundle-3", "moderntex,keyfeel,vitae-plus", { amount_total: 4499 }) } };
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
function runPicker(picked) {
  const handlers = {};
  const clicks = [];
  const mk = () => ({ textContent: "", disabled: false, classList: { toggle() {} }, addEventListener: (t, f) => { clicks.push([t, f]); } });
  const summary = mk(), buy = mk(), statusEl = mk();
  const form = {
    addEventListener: (t, f) => { handlers[t] = f; },
    querySelectorAll: () => picked.map((value) => ({ value })),
  };
  const sent = [];
  const ctx = {
    document: { getElementById: (id) => ({ "bundle-form": form, "bundle-summary": summary, "bundle-buy": buy, "bundle-status": statusEl })[id] || null },
    window: { location: { search: "", assign: (u) => sent.push(["assign", u]) } },
    URLSearchParams, Array, Math, Boolean, Promise, JSON, Number, String,
    fetch: (url, opts) => { sent.push([url, JSON.parse(opts.body)]); return Promise.resolve({ ok: true, json: () => Promise.resolve({ url: "https://checkout.stripe.com/x" }) }); },
  };
  vm.runInNewContext(readFileSync(new URL("../../site/suite/bundle.js", import.meta.url), "utf8"), ctx);
  return { summary, buy, sent, click: () => clicks.find(([t]) => t === "click")[1]() };
}

test("the picker: nothing or one part cannot be bought", () => {
  assert.equal(runPicker([]).buy.disabled, true);
  const one = runPicker(["moderntex"]);
  assert.equal(one.buy.disabled, true);
  assert.match(one.summary.textContent, /cheaper on its own/);
});

test("the picker: a pair that costs less apart is not sold as a bundle", () => {
  const cheap = runPicker(["keyfeel", "legroom"]);
  assert.equal(cheap.buy.disabled, true);
  assert.match(cheap.summary.textContent, /cost \$19\.98, which is less than the \$34\.99 bundle/);
  const cheap3 = runPicker(["keyfeel", "legroom", "moderntex"]);
  assert.equal(cheap3.buy.disabled, true);
  assert.match(cheap3.summary.textContent, /\$39\.97, which is less than the \$44\.99 bundle/);
});

test("the picker: a pair and a triple show the price and the saving, and send only the parts", async () => {
  const pair = runPicker(["outbound-veil", "tapefolio"]);
  assert.equal(pair.buy.disabled, false);
  assert.equal(pair.buy.textContent, "Buy these 2, $34.99");
  assert.match(pair.summary.textContent, /Bought separately: \$59\.98, so you save \$24\.99/);
  pair.click();
  await new Promise((r) => setTimeout(r, 5));
  assert.deepEqual(pair.sent[0], ["/.netlify/functions/checkout", { product: "bundle-2", ref: "", apps: ["outbound-veil", "tapefolio"] }]);
  const triple = runPicker(["moderntex", "outbound-veil", "vitae-plus"]);
  assert.equal(triple.buy.textContent, "Buy these 3, $44.99");
  assert.match(triple.summary.textContent, /\$73\.97, so you save \$28\.98/);
});

test("the picker: four or more parts point to the Suite instead", async () => {
  const four = runPicker(["moderntex", "outbound-veil", "legroom", "tapefolio"]);
  assert.equal(four.buy.disabled, false);
  assert.equal(four.buy.textContent, "Buy the Suite, $59.99");
  assert.match(four.summary.textContent, /Suite is the better buy/);
  four.click();
  await new Promise((r) => setTimeout(r, 5));
  assert.deepEqual(four.sent[0], ["/.netlify/functions/checkout", { product: "app-suite", ref: "" }]);
});
