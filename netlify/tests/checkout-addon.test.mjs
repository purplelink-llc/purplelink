// Optional second app at 25% off inside Stripe Checkout (netlify/lib/addons.mjs): what checkout offers, what a paid
// add-on unlocks (keys, downloads, success page, email, recovery), and that nothing is unlocked by an offer alone.
// Stripe, Resend and Blobs are stubbed; the signing keys are throwaways.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/checkout-addon.test.mjs

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
  STRIPE_PRICE_OUTBOUND_VEIL: "price_ov_main",
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const addons = await import("../lib/addons.mjs");
const lib = await import("../lib/bundles.mjs");
const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook } = await import("../functions/stripe-webhook.mjs");
const { default: purchaseLicense } = await import("../functions/purchase-license.mjs");
const { default: ovDl } = await import("../functions/outbound-veil-download.mjs");
const { default: legroomDl } = await import("../functions/legroom-download.mjs");
const { default: mtxDl } = await import("../functions/moderntex-download.mjs");
const { default: keyfeelDl } = await import("../functions/keyfeel-download.mjs");
const { recoveryEmail } = await import("../functions/purchases-recover.mjs");

const SID = "cs_live_addon_0123456789";
let calls;
let session;
let pricesMode; // "ok" | "fail" | "empty"
let rejectOptional;
beforeEach(() => {
  store.clear();
  calls = [];
  session = null;
  pricesMode = "ok";
  rejectOptional = false;
  addons.resetAddonPriceCache();
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    if (u.startsWith("https://api.stripe.com/v1/prices")) {
      if (pricesMode === "fail") return new Response("{}", { status: 500 });
      if (pricesMode === "empty") return new Response(JSON.stringify({ data: [] }), { status: 200 });
      const keys = [...new URL(u).searchParams.getAll("lookup_keys[]")];
      const data = keys.map((k) => {
        const slug = k.replace(/^addon_/, "").replace(/_25$/, "");
        return { id: `price_${slug}`, active: true, currency: "usd", type: "one_time", unit_amount: addons.addonCents(slug), lookup_key: k, metadata: { addon_slug: slug } };
      });
      return new Response(JSON.stringify({ data }), { status: 200 });
    }
    if (u.includes("api.stripe.com/v1/checkout/sessions") && opts.method === "POST") {
      if (rejectOptional && String(opts.body).includes("optional_items")) {
        return new Response(JSON.stringify({ error: { message: "optional_items is not supported here" } }), { status: 400 });
      }
      return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
    }
    if (session && u.startsWith("https://api.stripe.com/v1/checkout/sessions/")) return new Response(JSON.stringify(session), { status: 200 });
    return new Response("{}", { status: 200 });
  };
});

let ipN = 0;
const post = (body) => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": `203.0.113.${100 + (ipN++ % 100)}` }, body: JSON.stringify(body),
}));
const sessionPost = () => calls.filter((c) => c.url.includes("/checkout/sessions") && c.opts.method === "POST");
const params = (i = 0) => new URLSearchParams(sessionPost()[i].opts.body);

const lineItem = (slug, cents) => ({ price: { id: `price_${slug}`, lookup_key: `addon_${slug}_25`, unit_amount: cents, metadata: { addon_slug: slug } }, quantity: 1 });
const mainItem = { price: null, quantity: 1 };
const paid = (product, extra = [], metadata = {}) => ({
  id: SID, status: "complete", payment_status: "paid", amount_total: 4000, customer_details: { email: "buyer@example.com" },
  metadata: { product, ...metadata }, line_items: { data: [mainItem, ...extra] },
});
const callDoor = (handler, name) => handler(new Request(`https://purplelink.llc/.netlify/functions/${name}?session_id=${SID}`, {
  headers: { "x-nf-client-connection-ip": "198.51.100.5" } }), {});
const signed = (event) => {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", { method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body });
};
const sentMail = () => JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);

// ---- checkout ----

test("no add-on bought is the old checkout: a single app offers up to two optional rows, nothing preselected", async () => {
  const res = await post({ product: "outbound-veil" });
  assert.equal(res.status, 200);
  const p = params();
  assert.equal(p.get("optional_items[0][price]"), "price_legroom");
  assert.equal(p.get("optional_items[1][price]"), "price_keyfeel");
  assert.equal(p.get("optional_items[2][price]"), null, "at most two rows");
  assert.equal(p.get("optional_items[0][quantity]"), "1");
  assert.equal(p.get("metadata[addon_offered]"), "legroom,keyfeel");
  assert.equal(p.get("metadata[product]"), "outbound-veil");
  assert.equal(p.get("mode"), "payment");
});

test("ModernTex offers one row: Tapefolio, 25% off", async () => {
  await post({ product: "moderntex" });
  const p = params();
  assert.equal(p.get("optional_items[0][price]"), "price_tapefolio");
  assert.equal(p.get("optional_items[1][price]"), null);
  assert.equal(addons.addonCents("tapefolio"), 2249, "75% of $29.99, to the cent");
});

test("out-of-scope products carry no optional_items", async () => {
  for (const body of [{ product: "app-suite" }, { product: "bundle-2", apps: ["moderntex", "keyfeel"] }, { product: "moderntex-seats", seats: 5 }, { product: "paper-review-standard" }, { product: "vitae-plus" }]) {
    const res = await post(body);
    const made = sessionPost();
    if (res.status === 200 && made.length) {
      const p = new URLSearchParams(made.at(-1).opts.body);
      assert.equal([...p.keys()].some((k) => k.startsWith("optional_items")), false, body.product);
      assert.equal(p.get("metadata[addon_offered]"), null, body.product);
    }
    calls = [];
  }
});

test("a buyer code or friend discount leaves the add-on out", async () => {
  await post({ product: "outbound-veil", code: "NOTACODE" });
  for (const c of sessionPost()) assert.equal(String(c.opts.body).includes("optional_items"), false);
});

test("the Price lookup failing, or finding nothing, still sells the app with no add-on", async () => {
  for (const mode of ["fail", "empty"]) {
    calls = [];
    pricesMode = mode;
    addons.resetAddonPriceCache();
    const res = await post({ product: "keyfeel" });
    assert.equal(res.status, 200, mode);
    const p = params();
    assert.equal(p.get("optional_items[0][price]"), null, mode);
    assert.equal(p.get("metadata[addon_offered]"), null, mode);
    assert.equal(p.get("metadata[product]"), "keyfeel");
  }
});

test("a wrong-amount Price is never offered", async () => {
  const real = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (String(url).startsWith("https://api.stripe.com/v1/prices")) {
      return new Response(JSON.stringify({ data: [{ id: "price_bad", active: true, currency: "usd", type: "one_time", unit_amount: 1, lookup_key: "addon_tapefolio_25" }] }), { status: 200 });
    }
    return real(url, opts);
  };
  await post({ product: "moderntex" });
  assert.equal(params().get("optional_items[0][price]"), null);
});

test("if Stripe refuses the optional rows, checkout retries plain and still succeeds", async () => {
  rejectOptional = true;
  const res = await post({ product: "outbound-veil" });
  assert.equal(res.status, 200);
  assert.equal(sessionPost().length, 2);
  const retry = params(1);
  assert.equal([...retry.keys()].some((k) => k.startsWith("optional_items")), false);
  assert.equal(retry.get("metadata[addon_offered]"), null);
});

// ---- entitlements ----

test("addonsFromSession reads paid line items only, ignores the main product, forged metadata and out-of-scope products", () => {
  assert.deepEqual(addons.addonsFromSession(paid("moderntex", [lineItem("tapefolio", 2249)])), ["tapefolio"]);
  assert.deepEqual(addons.addonsFromSession(paid("moderntex")), []);
  assert.deepEqual(addons.addonsFromSession(paid("moderntex", [lineItem("moderntex", 1499)])), [], "not the main product");
  assert.deepEqual(addons.addonsFromSession(paid("bundle-2", [lineItem("keyfeel", 749)], { apps: "moderntex,legroom" })), [], "bundles take no add-ons");
  assert.deepEqual(addons.addonsFromSession(paid("moderntex", [], { addons: "tapefolio,keyfeel" })), [], "metadata cannot grant one");
  const forged = addons.withAddons(paid("moderntex", [], { addons: "tapefolio" }));
  assert.equal(forged.metadata.addons, undefined, "withAddons replaces whatever metadata said");
  assert.equal(addons.withAddons(paid("moderntex", [lineItem("tapefolio", 2249)])).metadata.addons, "tapefolio");
  assert.deepEqual(lib.entitledParts("moderntex", { addons: "legroom" }), new Set(["moderntex", "legroom"]));
  assert.deepEqual(lib.entitledParts("moderntex", {}), new Set(["moderntex"]));
});

test("an add-on opens its own download door and the main app's; others stay shut", async () => {
  session = paid("moderntex", [lineItem("outbound-veil", 2249)]);
  store.set("outbound-veil-files/OutboundVeil-1.0.0.dmg", "x");
  const ov = await callDoor(ovDl, "outbound-veil-download");
  assert.notEqual((await ov.json()).error, "not_entitled", "the add-on is entitled");
  const mtx = await callDoor(mtxDl, "moderntex-download");
  assert.notEqual((await mtx.json()).error, "not_entitled", "the main app still is");
  for (const [handler, name] of [[legroomDl, "legroom-download"], [keyfeelDl, "keyfeel-download"]]) {
    const res = await callDoor(handler, name);
    assert.equal(res.status, 403, name);
    assert.equal((await res.json()).error, "not_entitled", name);
  }
});

test("an add-on that was offered but not bought opens nothing", async () => {
  session = paid("moderntex", [], { addon_offered: "tapefolio" });
  const res = await callDoor(ovDl, "outbound-veil-download");
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "not_entitled");
});

test("purchase-license returns both apps' keys and parts for an order with an add-on, one app's for a plain one", async () => {
  const ask = () => purchaseLicense(new Request(`https://purplelink.llc/.netlify/functions/purchase-license?session_id=${SID}`, {
    headers: { "x-nf-client-connection-ip": "203.0.113.50" } }));
  session = paid("moderntex", [lineItem("outbound-veil", 2249)]);
  let body = await (await ask()).json();
  assert.deepEqual(body.parts, ["moderntex", "outbound-veil"]);
  assert.deepEqual(body.keys.map((k) => k.product).sort(), ["moderntex", "outbound-veil"]);
  session = paid("moderntex", [], { addon_offered: "outbound-veil" });
  body = await (await ask()).json();
  assert.equal(body.parts, undefined);
  assert.deepEqual(body.keys.map((k) => k.product), ["moderntex"]);
});

// ---- the purchase email ----

test("the webhook reads the paid line items and emails both keys and the add-on line", async () => {
  session = paid("moderntex", [lineItem("outbound-veil", 2249)], { addon_offered: "outbound-veil" });
  const event = { id: "evt_a1", type: "checkout.session.completed", data: { object: { ...session, line_items: undefined } } };
  const res = await webhook(signed(event));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  assert.ok(calls.some((c) => /checkout\/sessions\/cs_live_addon_0123456789\?.*expand/.test(c.url) || c.url.includes("expand[]=line_items")), "line items were read");
  const mail = sentMail();
  assert.match(mail.text, /MTX1-/);
  assert.match(mail.text, /OV1-/);
  assert.match(mail.text, /Outbound Veil, added at checkout/);
  assert.doesNotMatch(mail.text, /—|–/);
});

test("offered but not bought: one key, no add-on line", async () => {
  session = paid("moderntex", [], { addon_offered: "outbound-veil" });
  const event = { id: "evt_a2", type: "checkout.session.completed", data: { object: { ...session, line_items: undefined } } };
  await webhook(signed(event));
  const mail = sentMail();
  assert.match(mail.text, /MTX1-/);
  assert.doesNotMatch(mail.text, /OV1-|added at checkout/);
});

test("no add-on was offered: the webhook does not read line items", async () => {
  session = paid("moderntex");
  const event = { id: "evt_a3", type: "checkout.session.completed", data: { object: { ...session, line_items: undefined } } };
  await webhook(signed(event));
  assert.equal(calls.some((c) => c.url.includes("expand[]=line_items")), false);
  assert.match(sentMail().text, /MTX1-/);
});

test("line items unreadable for an add-on order: 502 so Stripe retries, no mail", async () => {
  session = null;
  const base = paid("moderntex", [], { addon_offered: "outbound-veil" });
  const event = { id: "evt_a4", type: "checkout.session.completed", data: { object: { ...base, line_items: undefined } } };
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    return new Response("{}", { status: String(url).includes("/checkout/sessions/") ? 500 : 200 });
  };
  const res = await webhook(signed(event));
  assert.equal(res.status, 502);
  assert.equal(calls.some((c) => c.url.startsWith("https://api.resend.com/")), false);
});

// ---- recovery ----

test("the recovery email lists the add-on beside a single app", () => {
  const purchase = { product: "outbound-veil", session_id: SID, addons: "legroom", date: "2026-11-06" };
  const mail = recoveryEmail ? recoveryEmail([purchase], {}) : null;
  const text = JSON.stringify(mail);
  assert.match(text, /Legroom/);
});
