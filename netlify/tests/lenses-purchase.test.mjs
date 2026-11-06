// Selling Lenses: the checkout catalog (inline $4.99, no Stripe Price), the refund line against /terms/, the purchase
// email (download link, one plain note, no license key), and the recovery email. Stripe, Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/lenses-purchase.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
    list: async () => ({ blobs: [] }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend", RESEND_API_KEY: "re_dummy",
};
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook, BLOB_DELIVERED_PRODUCTS } = await import("../functions/stripe-webhook.mjs");
const { recoveryEmail } = await import("../functions/purchases-recover.mjs");

let calls;
beforeEach(() => {
  store.clear(); calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    const u = String(url);
    if (u.includes("api.stripe.com/v1/checkout/sessions") && opts.method === "POST") return new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/pay/cs_test_1" }), { status: 200 });
    return new Response("{}", { status: 200 });
  };
});

const post = (body, ip = "203.0.113.9") => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": ip }, body: JSON.stringify(body) }));
const stripeParams = () => new URLSearchParams(calls.find((c) => c.url.includes("/checkout/sessions")).opts.body);

function signed(event) {
  const body = JSON.stringify(event); const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", { method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body });
}
const paid = (metadata, amount, id, sid) => ({ id, type: "checkout.session.completed", data: { object: { id: sid, status: "complete", payment_status: "paid", amount_total: amount,
  customer_details: { email: "buyer@example.com" }, metadata } } });
const mailOf = () => JSON.parse(calls.filter((c) => c.url.startsWith("https://api.resend.com/"))[0].opts.body);

// ---- checkout ----

test("without STRIPE_PRICE_LENSES, checkout sells Lenses at $4.99 inline, with its own success page and refund line", async () => {
  const res = await post({ product: "lenses", amount: 1 });
  assert.equal(res.status, 200);
  const p = stripeParams();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), "499", "the price comes from the catalog, not the request");
  assert.equal(p.get("line_items[0][price_data][product_data][name]"), "Lenses for macOS");
  assert.equal(p.get("line_items[0][price]"), null, "no Stripe Price when the env var is unset");
  assert.match(p.get("success_url"), /\/lenses\/success\/\?session_id=/);
  assert.equal(p.get("metadata[product]"), "lenses");
  assert.match(p.get("custom_text[submit][message]") || "", /full \$4\.99/);
});

test("with STRIPE_PRICE_LENSES set, checkout uses that Stripe Price", async () => {
  env.STRIPE_PRICE_LENSES = "price_lenses_test";
  try {
    const res = await post({ product: "lenses" });
    assert.equal(res.status, 200);
    const p = stripeParams();
    assert.equal(p.get("line_items[0][price]"), "price_lenses_test");
    assert.equal(p.get("line_items[0][price_data][unit_amount]"), null);
    assert.equal(p.get("metadata[product]"), "lenses");
  } finally { delete env.STRIPE_PRICE_LENSES; }
});

test("the checkout refund sentence matches the Lenses section of /terms/ word for word", async () => {
  await post({ product: "lenses" });
  const msg = stripeParams().get("custom_text[submit][message]");
  const terms = readFileSync(new URL("../../site/terms/index.html", import.meta.url), "utf8");
  const sec = terms.split("<h2>").find((s) => s.startsWith("Lenses: additional terms"));
  const li = sec.match(/<li><strong>Refunds\.<\/strong>(.*?)<\/li>/s)[1];
  let bare = li;
  for (let prev = ""; prev !== bare; ) { prev = bare; bare = bare.replace(/<[^>]*>/g, ""); }
  const text = bare.replace(/&#39;|&rsquo;/g, "'").replace(/\s+/g, " ").trim();
  assert.equal(msg, text);
});

test("Lenses is not a custom bundle part, and the Suite line does not name it", async () => {
  const bad = await post({ product: "bundle-2", apps: ["lenses", "panely"] });
  assert.equal(bad.status, 400);
  await post({ product: "app-suite" });
  assert.doesNotMatch(stripeParams().get("line_items[0][price_data][product_data][name]"), /Lenses/);
});

// ---- delivery ----

test("Lenses is a blob-delivered product with its own success page", () => {
  assert.equal(BLOB_DELIVERED_PRODUCTS.get("lenses").successPath, "/lenses/success/");
});

test("a paid Lenses order emails the page link and one note, and no license key", async () => {
  const res = await webhook(signed(paid({ product: "lenses" }, 499, "evt_ls", "cs_live_ls_abcdefghij")));
  assert.equal((await res.json()).status, "delivered_by_blobs");
  const mail = mailOf();
  assert.deepEqual(mail.to, ["buyer@example.com"]);
  assert.match(mail.text, /https:\/\/purplelink\.llc\/lenses\/success\/\?session_id=cs_live_ls_abcdefghij/);
  assert.match(mail.text, /macOS 14 or later on an Apple silicon Mac/);
  assert.doesNotMatch(mail.text + mail.html, /license key|LCB1|TFL1|Enter License/i);
  assert.doesNotMatch(mail.text + mail.html, /Lenscrib|Tapefolio/);
  assert.doesNotMatch(mail.text + mail.html, /—/);
});

test("a paid Suite order carries no Lenses text", async () => {
  await webhook(signed(paid({ product: "app-suite" }, 5999, "evt_su", "cs_live_su_abcdefghij")));
  const mail = mailOf();
  assert.doesNotMatch(mail.text + mail.html, /Lenses/);
});

// ---- recovery ----

test("the recovery email lists a Lenses purchase as a download page with no key line", () => {
  const only = recoveryEmail([{ sessionId: "cs_ls", product: "lenses", created: 5 }], null, null, new Map(), null, null, null, null);
  assert.match(only.text, /Lenses for macOS/);
  assert.match(only.text, /\/lenses\/success\/\?session_id=cs_ls/);
  assert.doesNotMatch(only.text, /license key/i);
});
