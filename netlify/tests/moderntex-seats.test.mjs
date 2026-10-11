// Multi-seat ModernTex: the price table, checkout validation, one key per seat, the purchase email and the
// success-page key endpoint. Stripe, Resend and Blobs are stubbed; the signing key is a throwaway.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/moderntex-seats.test.mjs

import { readFileSync } from "node:fs";
import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac, generateKeyPairSync } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { privateKey } = generateKeyPairSync("ed25519");
const jwk = privateKey.export({ format: "jwk" });
const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend",
  RESEND_API_KEY: "re_dummy", MODERNTEX_LICENSE_PRIVATE_KEY: Buffer.from(jwk.d, "base64url").toString("base64"),
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { SEAT_PACKS, SEAT_BULK, MAX_SEATS, seatUnitCents, seatTotalCents, parseSeats } = await import("../lib/seats.mjs");
const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook, licenseKeysForSession } = await import("../functions/stripe-webhook.mjs");
const { default: purchaseLicense } = await import("../functions/purchase-license.mjs");

let calls;
beforeEach(() => {
  store.clear();
  calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (String(url).includes("api.stripe.com/v1/checkout/sessions") && opts.method === "POST") {
      return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  };
});

const post = (body, ip = "203.0.113.9") => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": ip }, body: JSON.stringify(body),
}));
const stripeParams = () => new URLSearchParams(calls.find((c) => c.url.includes("/checkout/sessions")).opts.body);

test("the price table: packs, the 25-and-over price, and counts that are not offered", () => {
  assert.deepEqual(SEAT_PACKS.map((p) => p.seats), [5, 10, 15, 20]);
  assert.equal(seatUnitCents(5), 1399);
  assert.equal(seatTotalCents(10), 12490);
  assert.equal(seatTotalCents(20), 20980);
  assert.equal(seatTotalCents(25), 24975);
  // 32 seats are all charged the 25-and-over price.
  assert.equal(seatUnitCents(32), SEAT_BULK.unitCents);
  assert.equal(seatTotalCents(32), 32 * 999);
  assert.equal(seatTotalCents(MAX_SEATS), MAX_SEATS * 999);
  for (const bad of [0, 1, 4, 6, 7, 11, 21, 24, 501, 1000, -5, 5.5, NaN, null, undefined, "5"]) assert.equal(seatUnitCents(bad), null, String(bad));
  // Per-seat price never rises with the count, and the larger pack never costs more per seat.
  const units = [5, 10, 15, 20, 25, 40].map(seatUnitCents);
  for (let i = 1; i < units.length; i++) assert.ok(units[i] <= units[i - 1]);
  assert.equal(parseSeats("12"), 12);
  assert.equal(parseSeats(12), 12);
  assert.equal(parseSeats("1e3"), null);
  assert.equal(parseSeats("12abc"), null);
  assert.equal(parseSeats(""), null);
});

test("the page's price table is the server's price table", () => {
  const src = readFileSync(new URL("../../site/moderntex/seats.js", import.meta.url), "utf8");
  const table = JSON.parse(src.match(/var SEAT_PRICING = (\{.*?\});/)[1]);
  assert.deepEqual(table.packs, SEAT_PACKS.map((p) => [p.seats, p.unitCents]));
  assert.equal(table.bulkMin, SEAT_BULK.minSeats);
  assert.equal(table.bulkUnit, SEAT_BULK.unitCents);
  assert.equal(table.max, MAX_SEATS);
  const html = readFileSync(new URL("../../site/moderntex/index.html", import.meta.url), "utf8");
  for (const p of SEAT_PACKS) {
    const total = `$${(seatTotalCents(p.seats) / 100).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
    assert.ok(html.includes(`value="${p.seats}"`) && html.includes(total), `${p.seats} seats ${total} on the page`);
  }
});

test("checkout prices a seat order from the count alone and records the seats", async () => {
  const res = await post({ product: "moderntex-seats", seats: 10, amount: 1, unit_amount: 1 });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "1249");
  assert.equal(p.get("line_items[0][quantity]"), "10");
  assert.equal(p.get("metadata[product]"), "moderntex-seats");
  assert.equal(p.get("metadata[seats]"), "10");
  assert.equal(p.get("mode"), "payment");
  assert.match(p.get("success_url"), /\/moderntex\/success\/\?session_id=/);
});

test("32 seats are charged the 25-and-over price each", async () => {
  await post({ product: "moderntex-seats", seats: "32" }, "203.0.113.10");
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "999");
  assert.equal(p.get("line_items[0][quantity]"), "32");
});

test("checkout refuses seat counts that are not offered, and leaves the single copy alone", async () => {
  for (const [i, seats] of [1, 4, 6, 24, 501, "abc", null, undefined, 9.5].entries()) {
    calls = [];
    const res = await post({ product: "moderntex-seats", seats }, `198.51.100.${i + 1}`);
    assert.equal(res.status, 400, String(seats));
    assert.equal((await res.json()).error, "invalid_seats");
    assert.equal(calls.some((c) => c.url.includes("/checkout/sessions")), false, "no Stripe session for a bad count");
  }
  calls = [];
  await post({ product: "moderntex", seats: 50 }, "198.51.100.77");
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "1999");
  assert.equal(p.get("line_items[0][quantity]"), "1");
  assert.equal(p.get("metadata[seats]"), null);
});

test("one key per seat: distinct, repeatable for a purchase, and different from a single copy's key", () => {
  const sid = "cs_live_seats_0123456789";
  const keys = licenseKeysForSession("moderntex-seats", sid, { seats: 12 });
  assert.equal(keys.length, 12);
  assert.equal(new Set(keys.map((k) => k.key)).size, 12);
  assert.deepEqual(keys.map((k) => k.label).slice(0, 2), ["ModernTex seat 1", "ModernTex seat 2"]);
  assert.ok(keys.every((k) => k.slug === "moderntex-seat" && /^MTX1-(?:[0-9A-Z]{5}-){21}[0-9A-Z]{4}$/.test(k.key)));
  assert.deepEqual(licenseKeysForSession("moderntex-seats", sid, { seats: 12 }).map((k) => k.key), keys.map((k) => k.key));
  assert.equal(licenseKeysForSession("moderntex-seats", sid, { seats: 0 }).length, 0);
  assert.equal(licenseKeysForSession("moderntex-seats", sid).length, 0);
  assert.equal(licenseKeysForSession("moderntex-seats", sid, { seats: 99999 }).length, 500);
  const single = licenseKeysForSession("moderntex", sid)[0].key;
  assert.ok(!keys.some((k) => k.key === single));
  // A single copy's key is unchanged by this feature.
  assert.equal(licenseKeysForSession("moderntex", sid)[0].key, single);
});

function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", {
    method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body,
  });
}

test("the purchase email lists every seat's key and the page link", async () => {
  const event = { id: "evt_seats_1", type: "checkout.session.completed", data: { object: {
    id: "cs_live_seats_email_0123", status: "complete", payment_status: "paid", amount_total: 12490,
    customer_details: { email: "pi@example.edu" }, metadata: { product: "moderntex-seats", seats: "6" } } } };
  const res = await webhook(signed(event));
  assert.equal(res.status, 200);
  const mail = JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);
  const keys = mail.text.match(/MTX1-(?:[0-9A-Z]{5}-){21}[0-9A-Z]{4}/g) ?? [];
  assert.equal(keys.length, 6);
  assert.equal(new Set(keys).size, 6);
  assert.match(mail.text, /Your 6 ModernTex license keys/);
  assert.match(mail.text, /1\. MTX1-/);
  assert.match(mail.text, /\/moderntex\/success\/\?session_id=cs_live_seats_email_0123/);
  assert.deepEqual(keys, licenseKeysForSession("moderntex-seats", "cs_live_seats_email_0123", { seats: 6 }).map((k) => k.key));
  // A duplicate delivery of the same event sends nothing more.
  calls = [];
  await webhook(signed(event));
  assert.equal(calls.some((c) => c.url.startsWith("https://api.resend.com/")), false);
});

test("the success-page endpoint returns one key per seat for a paid seat session", async () => {
  const sid = "cs_live_seats_page_0123456";
  globalThis.fetch = async (url) => {
    if (String(url).includes(`/checkout/sessions/${sid}`)) {
      return new Response(JSON.stringify({ payment_status: "paid", metadata: { product: "moderntex-seats", seats: "4" } }), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  };
  const res = await purchaseLicense(new Request(`https://purplelink.llc/.netlify/functions/purchase-license?session_id=${sid}`, {
    headers: { "x-nf-client-connection-ip": "203.0.113.50" } }));
  assert.equal(res.status, 200);
  const { keys } = await res.json();
  assert.equal(keys.length, 4);
  assert.deepEqual(keys.map((k) => k.key), licenseKeysForSession("moderntex-seats", sid, { seats: 4 }).map((k) => k.key));
});
