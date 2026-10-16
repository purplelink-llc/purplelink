// Refunded and disputed orders: the webhook records them, and the download doors, purchase-license and
// purchases-recover stop handing out links and keys for them. A partial refund changes nothing.
// Stripe, Resend and Netlify Blobs are stubbed; a throwaway Ed25519 key signs ModernTex keys.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/refunds.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac, generateKeyPairSync } from "node:crypto";

const blobs = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => blobs.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { blobs.set(`${name}/${k}`, v); },
    delete: async (k) => { blobs.delete(`${name}/${k}`); },
    list: async () => ({ blobs: [] }),
    getWithMetadata: async () => null,
  }),
};
// `exports` on newer Node (Node 26 rejects both together), `namedExports` on Node 22.
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const { privateKey } = generateKeyPairSync("ed25519");
const env = {
  STRIPE_WEBHOOK_SECRET: "whsec_test",
  BACKEND_WEBHOOK_SECRET: "backend",
  STRIPE_SECRET_KEY: "sk_test_dummy",
  RESEND_API_KEY: "re_dummy",
  MODERNTEX_LICENSE_PRIVATE_KEY: Buffer.from(privateKey.export({ format: "jwk" }).d, "base64url").toString("base64"),
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: webhook } = await import("../functions/stripe-webhook.mjs");
const { default: mtxDownload } = await import("../functions/moderntex-download.mjs");
const { default: purchaseLicense } = await import("../functions/purchase-license.mjs");
const { default: recoverHandler } = await import("../functions/purchases-recover.mjs");
const { revocationFor, REVOKED_DETAIL } = await import("../lib/refunds.mjs");

let calls;
let sessions;   // Checkout Session list answered for any /checkout/sessions?… query
let single;     // id -> Checkout Session answered for /checkout/sessions/<id>
beforeEach(() => {
  blobs.clear();
  calls = [];
  sessions = [];
  single = {};
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    if (u.startsWith("https://api.resend.com/")) return new Response("{}", { status: 200 });
    const one = u.match(/^https:\/\/api\.stripe\.com\/v1\/checkout\/sessions\/(cs_[A-Za-z0-9_]+)/);
    if (one) {
      const s = single[one[1]];
      return s ? new Response(JSON.stringify(s), { status: 200 }) : new Response("{}", { status: 404 });
    }
    if (u.startsWith("https://api.stripe.com/v1/checkout/sessions")) {
      return new Response(JSON.stringify({ data: sessions, has_more: false }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${u}`);
  };
});

function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", {
    method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body,
  });
}
const send = async (event) => (await webhook(signed(event))).json();
const refundEvent = (charge, id = "evt_refund") => ({ id, type: "charge.refunded", data: { object: { id: "ch_1", object: "charge", ...charge } } });
const disputeEvent = (type, dispute, id = "evt_dispute") => ({ id, type, data: { object: { id: "dp_1", object: "dispute", charge: "ch_1", ...dispute } } });
const isRevoked = async (pi) => Boolean(await revocationFor({ payment_intent: pi }));

const session = (id, product, over = {}) => ({
  id, status: "complete", payment_status: "paid", payment_intent: `pi_${id.slice(3)}`, created: 100,
  customer_details: { email: "buyer@example.com" }, metadata: { product }, ...over,
});

// ---- webhook ----

test("a full refund is recorded against the payment intent", async () => {
  const res = await send(refundEvent({ payment_intent: "pi_full", amount: 1999, amount_refunded: 1999, refunded: true }));
  assert.equal(res.status, "refund_recorded");
  assert.ok(await isRevoked("pi_full"));
  const record = JSON.parse(blobs.get("refunds/pi:pi_full"));
  assert.equal(record.reason, "refund");
  assert.equal(record.charge, "ch_1");
  assert.match(record.recorded_at, /^\d{4}-\d{2}-\d{2}T/);
});

test("a partial refund is not recorded, so access stays", async () => {
  const res = await send(refundEvent({ payment_intent: "pi_part", amount: 1999, amount_refunded: 500, refunded: false }));
  assert.equal(res.status, "partial_refund_ignored");
  assert.equal(await isRevoked("pi_part"), false);
});

test("a refunded charge with no payment intent is acknowledged and ignored", async () => {
  const res = await send(refundEvent({ payment_intent: null, amount: 1999, amount_refunded: 1999, refunded: true }));
  assert.equal(res.status, "ignored_no_payment_intent");
});

test("a dispute is recorded, and winning it restores access", async () => {
  assert.equal((await send(disputeEvent("charge.dispute.created", { payment_intent: "pi_dsp", status: "needs_response" }))).status, "dispute_recorded");
  assert.ok(await isRevoked("pi_dsp"));
  assert.equal((await send(disputeEvent("charge.dispute.closed", { payment_intent: "pi_dsp", status: "won" }, "evt_won"))).status, "dispute_cleared");
  assert.equal(await isRevoked("pi_dsp"), false);
});

test("a lost dispute keeps the record", async () => {
  await send(disputeEvent("charge.dispute.created", { payment_intent: "pi_lost" }));
  assert.equal((await send(disputeEvent("charge.dispute.closed", { payment_intent: "pi_lost", status: "lost" }, "evt_lost"))).status, "dispute_closed");
  assert.ok(await isRevoked("pi_lost"));
});

test("a won dispute never clears a refund, and a later dispute does not overwrite it", async () => {
  await send(refundEvent({ payment_intent: "pi_both", amount: 1999, amount_refunded: 1999, refunded: true }));
  await send(disputeEvent("charge.dispute.created", { payment_intent: "pi_both" }));
  assert.equal(JSON.parse(blobs.get("refunds/pi:pi_both")).reason, "refund");
  await send(disputeEvent("charge.dispute.closed", { payment_intent: "pi_both", status: "won" }, "evt_won2"));
  assert.ok(await isRevoked("pi_both"));
});

test("other event types are still ignored", async () => {
  assert.equal((await send({ id: "evt_x", type: "invoice.paid", data: { object: {} } })).status, "ignored");
});

// ---- download door ----

const download = (id) => mtxDownload(new Request(`https://purplelink.llc/.netlify/functions/moderntex-download?session_id=${id}`));

test("the download door refuses a refunded order with a clear message", async () => {
  single.cs_live_mtxrefund12345 = session("cs_live_mtxrefund12345", "moderntex");
  await send(refundEvent({ payment_intent: "pi_live_mtxrefund12345", amount: 1999, amount_refunded: 1999, refunded: true }));
  const res = await download("cs_live_mtxrefund12345");
  assert.equal(res.status, 403);
  const body = await res.json();
  assert.equal(body.error, "refunded");
  assert.equal(body.detail, REVOKED_DETAIL);
});

test("the download door still serves an order that was only partly refunded", async () => {
  single.cs_live_mtxpartial1234 = session("cs_live_mtxpartial1234", "moderntex");
  await send(refundEvent({ payment_intent: "pi_live_mtxpartial1234", amount: 1999, amount_refunded: 999, refunded: false }));
  const body = await (await download("cs_live_mtxpartial1234")).json();
  assert.notEqual(body.error, "refunded");
  assert.notEqual(body.error, "not_paid");
});

// ---- purchase-license ----

const license = (id, ip) => purchaseLicense(new Request(`https://purplelink.llc/.netlify/functions/purchase-license?session_id=${id}`, {
  headers: { "x-nf-client-connection-ip": ip },
}));

test("purchase-license answers a paid order and refuses it once disputed", async () => {
  single.cs_live_keyorder123456 = session("cs_live_keyorder123456", "moderntex");
  const ok = await license("cs_live_keyorder123456", "203.0.113.1");
  assert.equal(ok.status, 200);
  assert.match((await ok.json()).keys[0].key, /^MTX1-/);
  await send(disputeEvent("charge.dispute.created", { payment_intent: "pi_live_keyorder123456" }));
  const no = await license("cs_live_keyorder123456", "203.0.113.1");
  assert.equal(no.status, 403);
  const body = await no.json();
  assert.equal(body.error, "refunded");
  assert.equal(body.keys, undefined);
});

// ---- purchases-recover ----

const recover = (email, ip) => recoverHandler(new Request("https://purplelink.llc/.netlify/functions/purchases-recover", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": ip }, body: JSON.stringify({ email }),
}));
const sentMail = () => calls.filter((c) => c.url.startsWith("https://api.resend.com/")).map((c) => JSON.parse(c.opts.body));

test("recovery leaves out a refunded order and says so, but keeps the others", async () => {
  sessions = [
    session("cs_refunded_kit", "kit-clip", { created: 300 }),
    session("cs_kept_mtx", "moderntex", { created: 200 }),
  ];
  await send(refundEvent({ payment_intent: "pi_refunded_kit", amount: 1999, amount_refunded: 1999, refunded: true }));
  assert.equal((await recover("buyer@example.com", "203.0.113.2")).status, 200);
  const mails = sentMail();
  assert.equal(mails.length, 1);
  assert.match(mails[0].text, /cs_kept_mtx/);
  assert.match(mails[0].text, /MTX1-/);
  assert.doesNotMatch(mails[0].text, /cs_refunded_kit/);
  assert.match(mails[0].text, /refunded or disputed/);
});

test("recovery for an address whose only order was refunded sends no links or keys", async () => {
  sessions = [session("cs_only_mtx", "moderntex")];
  await send(refundEvent({ payment_intent: "pi_only_mtx", amount: 1999, amount_refunded: 1999, refunded: true }));
  const res = await recover("buyer@example.com", "203.0.113.3");
  assert.deepEqual(await res.json(), { status: "sent_if_found" });
  const mails = sentMail();
  assert.equal(mails.length, 1);
  assert.match(mails[0].text, /refunded or disputed/);
  assert.doesNotMatch(mails[0].text, /MTX1-|session_id=/);
});

test("recovery is unchanged when nothing was refunded", async () => {
  sessions = [session("cs_plain_mtx", "moderntex")];
  await recover("buyer@example.com", "203.0.113.4");
  const [mail] = sentMail();
  assert.match(mail.text, /cs_plain_mtx/);
  assert.doesNotMatch(mail.text, /refunded or disputed/);
});

// ---- every download door that serves a paid file ----

const DOORS = [
  ["keyfeel", "keyfeel"], ["legroom", "legroom"], ["moderntex", "moderntex"], ["outbound-veil", "outbound-veil"],
  ["panely", "panely"], ["summonly", "summonly"], ["tapefolio", "tapefolio"], ["kit", "kit-clip"], ["photo", "photo-license-web"],
];
for (const [door, product] of DOORS) {
  test(`${door}-download refuses a refunded order`, async () => {
    const handler = (await import(`../functions/${door}-download.mjs`)).default;
    const id = `cs_live_door${door.replace(/-/g, "")}12345`;
    single[id] = session(id, product);
    await send(refundEvent({ payment_intent: `pi_${id.slice(3)}`, amount: 999, amount_refunded: 999, refunded: true }));
    const res = await handler(new Request(`https://purplelink.llc/.netlify/functions/${door}-download?session_id=${id}`));
    assert.equal(res.status, 403);
    assert.equal((await res.json()).error, "refunded");
  });
}
