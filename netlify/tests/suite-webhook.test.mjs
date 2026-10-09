// The Mac Suite purchase email: one link to the suite page, the ModernTex key in the body,
// and no second email when Stripe delivers the same event twice. Stripe, Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/suite-webhook.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", RESEND_API_KEY: "re_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };
const { default: handler, BLOB_DELIVERED_PRODUCTS } = await import("../functions/stripe-webhook.mjs");

let calls;
beforeEach(() => {
  store.clear();
  calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    return new Response("{}", { status: 200 });
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
const completed = (product, id = "evt_1") => ({
  id, type: "checkout.session.completed",
  data: { object: { id: "cs_live_suite_abcdefghij", status: "complete", payment_status: "paid", amount_total: 5499,
    customer_details: { email: "buyer@example.com" }, metadata: { product } } },
});

test("the Suite is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("app-suite").successPath, "/suite/success/");
});

test("a paid Suite order is acknowledged and emails the suite page link once", async () => {
  const res = await handler(signed(completed("app-suite")));
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, "delivered_by_blobs");
  assert.equal(body.product, "app-suite");
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.subject, /Purplelink Mac Suite/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/suite\/success\/\?session_id=cs_live_suite_abcdefghij/);
  assert.match(mail.text, /That page has six things: the ModernTex, Outbound Veil, Legroom, Keyfeel and Tapefolio downloads, and your Vitae Plus key/);
  assert.match(mail.html, /ModernTex, Outbound Veil, Legroom, Keyfeel and Tapefolio downloads/);
  assert.match(mail.html, /\/suite\/success\//);
});

test("Stripe delivering the same event twice sends one email", async () => {
  await handler(signed(completed("app-suite", "evt_dup")));
  const again = await handler(signed(completed("app-suite", "evt_dup")));
  assert.equal((await again.json()).status, "duplicate_event_ignored");
  assert.equal(calls.filter((c) => c.url.startsWith("https://api.resend.com/")).length, 1);
});

test("Legroom is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("legroom").successPath, "/legroom/success/");
});

test("a paid Legroom order emails the download page and the one-sentence review ask, with no signing secret configured it still delivers, without a key", async () => {
  const res = await handler(signed({ ...completed("legroom", "evt_lg"), data: { object: { ...completed("legroom").data.object, id: "cs_live_legroom_abcdefg1", amount_total: 999 } } }));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.subject, /Legroom for macOS download/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/legroom\/success\/\?session_id=cs_live_legroom_abcdefg1/);
  assert.match(mail.text, /If Legroom is useful, reply to this email with one sentence/);
  assert.doesNotMatch(mail.text, /license key|MTX1|Vitae/i);
  assert.doesNotMatch(mail.text, /—|–/);
  assert.match(mail.html, /legroom\/success\//);
});

test("the Suite email mentions Legroom but carries no Legroom review ask", async () => {
  await handler(signed(completed("app-suite", "evt_s2")));
  const suiteMail = JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);
  assert.doesNotMatch(suiteMail.text, /If Legroom is useful/);
  assert.match(suiteMail.text, /Legroom/);
});

test("Keyfeel is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("keyfeel").successPath, "/keyfeel/success/");
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("keyfeel").name, "Keyfeel for macOS");
});

test("a paid Keyfeel order emails the download page, the Input Monitoring note and the Keyfeel license key", async () => {
  env.KEYFEEL_LICENSE_PRIVATE_KEY = Buffer.alloc(32, 9).toString("base64");
  const res = await handler(signed({ ...completed("keyfeel", "evt_kf"), data: { object: { ...completed("keyfeel").data.object, id: "cs_live_keyfeel_abcdefg1", amount_total: 999 } } }));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.subject, /Keyfeel for macOS download/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/keyfeel\/success\/\?session_id=cs_live_keyfeel_abcdefg1/);
  assert.match(mail.text, /Input Monitoring/);
  assert.match(mail.text, /never the characters/);
  assert.match(mail.text, /Your Keyfeel license key[^\n]*\nKFL1-/);
  assert.doesNotMatch(mail.text, /MTX1|Vitae|Outbound Veil/i);
  assert.doesNotMatch(mail.text, /—|–/);
  assert.match(mail.html, /keyfeel\/success\//);
  assert.match(mail.html, /KFL1-/);
  delete env.KEYFEEL_LICENSE_PRIVATE_KEY;
});

test("other products' emails do not carry the Keyfeel permission note", async () => {
  await handler(signed(completed("legroom", "evt_lg2")));
  const mail = JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);
  assert.doesNotMatch(mail.text, /Input Monitoring/);
});

// ---- Tapefolio ----
// The handler signs with the production public key compiled into netlify/lib/tapefolio-license.mjs, so these tests
// sign with a seed Node accepts beside it (Node 24 does). A Node that checks the pair would return no key, and the
// key tests are skipped there; the signing itself is covered in tapefolio-license.test.mjs.
const { issueTapefolioLicense } = await import("../lib/tapefolio-license.mjs");
const TF_SEED = Buffer.alloc(32, 5).toString("base64");
const tfCanSign = issueTapefolioLicense("probe@example.org", (k) => (k === "TAPEFOLIO_LICENSE_PRIVATE_KEY" ? TF_SEED : undefined)) !== null;
const tfSkip = !tfCanSign && "this Node rejects a seed that does not match the production public key";
const tfCompleted = (id = "evt_tf") => ({ ...completed("tapefolio", id), data: { object: { ...completed("tapefolio").data.object, id: "cs_live_tapefolio_abcdefg1", amount_total: 2999 } } });
const resendMail = () => JSON.parse(calls.find((c) => c.url.startsWith("https://api.resend.com/")).opts.body);

test("Tapefolio is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("tapefolio").successPath, "/tapefolio/success/");
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("tapefolio").name, "Tapefolio for macOS");
});

test("a paid Tapefolio order emails the download page, the first-run note and the Tapefolio license key", { skip: tfSkip }, async () => {
  env.TAPEFOLIO_LICENSE_PRIVATE_KEY = TF_SEED;
  const res = await handler(signed(tfCompleted()));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const sent = calls.filter((c) => c.url.startsWith("https://api.resend.com/"));
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.subject, /Tapefolio for macOS download/);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/tapefolio\/success\/\?session_id=cs_live_tapefolio_abcdefg1/);
  assert.match(mail.text, /Your Tapefolio license key[^\n]*\nTFL1-/);
  assert.match(mail.text, /two of your Macs/);
  assert.match(mail.text, /macOS 26 or later on an Apple silicon Mac/);
  assert.match(mail.text, /a few minutes while macOS prepares its models for the Neural Engine/);
  assert.match(mail.text, /mishear some words and mislabel some speakers/);
  assert.doesNotMatch(mail.text, /MTX1|KFL1|Vitae|Outbound Veil|Keyfeel|Input Monitoring/i);
  assert.doesNotMatch(mail.text, /—|–/);
  assert.match(mail.html, /tapefolio\/success\//);
  assert.match(mail.html, /TFL1-/);
  delete env.TAPEFOLIO_LICENSE_PRIVATE_KEY;
});

test("a Tapefolio order with no signing secret still delivers the link, without a key", async () => {
  delete env.TAPEFOLIO_LICENSE_PRIVATE_KEY;
  const res = await handler(signed(tfCompleted("evt_tf2")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = resendMail();
  assert.match(mail.text, /tapefolio\/success\//);
  assert.doesNotMatch(mail.text, /TFL1-/);
});

test("the Suite email carries a Tapefolio key and the first-run note, and the Tapefolio key matches the one a Tapefolio-only buyer gets", { skip: tfSkip }, async () => {
  env.TAPEFOLIO_LICENSE_PRIVATE_KEY = TF_SEED;
  await handler(signed(completed("app-suite", "evt_s3")));
  const suiteMail = resendMail();
  calls.length = 0;
  await handler(signed(tfCompleted("evt_tf3")));
  const aloneMail = resendMail();
  delete env.TAPEFOLIO_LICENSE_PRIVATE_KEY;
  const keyIn = (t) => t.match(/TFL1-(?:[0-9A-Z]{5}-){21}[0-9A-Z]{4}/)?.[0];
  assert.ok(keyIn(suiteMail.text), "the Suite email has a Tapefolio key");
  assert.equal(keyIn(suiteMail.text), keyIn(aloneMail.text));
  assert.match(suiteMail.text, /Neural Engine/);
});

test("other products' emails carry no Tapefolio note or key", async () => {
  env.TAPEFOLIO_LICENSE_PRIVATE_KEY = TF_SEED;
  await handler(signed(completed("legroom", "evt_lg3")));
  const mail = resendMail();
  delete env.TAPEFOLIO_LICENSE_PRIVATE_KEY;
  assert.doesNotMatch(mail.text, /Tapefolio|Neural Engine|TFL1-/);
});
