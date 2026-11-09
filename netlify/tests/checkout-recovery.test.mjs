// Checkout recovery (every one-time product since 2026-11-05): checkout.mjs adds the consent and recovery parameters (and retries without them if
// Stripe rejects them), and stripe-webhook.mjs sends one recovery email per consenting address. Stripe, Resend and
// Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/checkout-recovery.test.mjs

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

const env = {
  STRIPE_SECRET_KEY: "sk_test_dummy", STRIPE_WEBHOOK_SECRET: "whsec_test", BACKEND_WEBHOOK_SECRET: "backend",
  RESEND_API_KEY: "re_dummy", FOLLOWUP_UNSUBSCRIBE_SECRET: "unsub_secret",
  LENSCRIB_SALES_OPEN: "1",   // pre-launch switch (checkout.mjs openEnv); these tests buy every catalog product
};
globalThis.Netlify = { env: { get: (k) => (k.startsWith("STRIPE_PRICE_") ? "price_dummy" : env[k]) } };

const { default: checkout } = await import("../functions/checkout.mjs");
const { default: webhook } = await import("../functions/stripe-webhook.mjs");
const { RECOVERY_PRODUCTS, recoveryParams, recoveryEmail, isRecoveryParamError } = await import("../lib/checkout-recovery.mjs");
const { emailHash } = await import("../lib/followup.mjs");

let calls;
let stripeReply;
beforeEach(() => {
  store.clear();
  calls = [];
  delete env.CHECKOUT_RECOVERY;
  stripeReply = () => new Response(JSON.stringify({ id: "cs_test_1", url: "https://checkout.stripe.com/c/pay/cs_test_1" }), { status: 200 });
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (String(url).startsWith("https://api.stripe.com/")) return stripeReply(opts);
    return new Response("{}", { status: 200 });
  };
});

let ipN = 10;
const buy = (product, extra = {}) => checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
  method: "POST",
  headers: { "content-type": "application/json", "x-nf-client-connection-ip": `203.0.113.${ipN++}` },
  body: JSON.stringify({ product, ...extra }),
}));
const stripeBodies = () => calls.filter((c) => c.url.startsWith("https://api.stripe.com/v1/checkout/sessions")).map((c) => new URLSearchParams(c.opts.body));

test("a ModernTex checkout asks for consent and enables recovery without promotion codes", async () => {
  const res = await buy("moderntex");
  assert.equal(res.status, 200);
  const [p] = stripeBodies();
  assert.equal(p.get("consent_collection[promotions]"), "auto");
  assert.equal(p.get("after_expiration[recovery][enabled]"), "true");
  assert.equal(p.get("after_expiration[recovery][allow_promotion_codes]"), "false");
});

test("the price the recovery email states is the price checkout charges", async () => {
  await buy("moderntex");
  const [p] = stripeBodies();
  assert.equal(p.get("line_items[0][price_data][unit_amount]"), String(RECOVERY_PRODUCTS.moderntex.cents));
  assert.equal(RECOVERY_PRODUCTS.moderntex.price, `$${(RECOVERY_PRODUCTS.moderntex.cents / 100).toFixed(2)}`);
});

test("subscriptions and ModernTex seats get no recovery parameters", async () => {
  for (const product of ["vitae-plus-monthly", "paper-review-annual", "live-scholar"]) {
    calls = [];
    await buy(product);
    const [p] = stripeBodies();
    assert.equal(p.get("mode"), "subscription", product);
    assert.equal(p.get("consent_collection[promotions]"), null, product);
    assert.equal(p.get("after_expiration[recovery][enabled]"), null, product);
  }
  assert.deepEqual(recoveryParams("moderntex-seats"), {});
  assert.deepEqual(recoveryParams("vitae-plus-annual"), {});
});

test("if Stripe rejects the recovery parameters, checkout retries once without them and still returns a URL", async () => {
  let n = 0;
  stripeReply = () => (n++ === 0
    ? new Response(JSON.stringify({ error: { type: "invalid_request_error", param: "consent_collection[promotions]", message: "Not available" } }), { status: 400 })
    : new Response(JSON.stringify({ id: "cs_test_2", url: "https://checkout.stripe.com/c/pay/cs_test_2" }), { status: 200 }));
  const res = await buy("moderntex");
  assert.equal(res.status, 200);
  assert.equal((await res.json()).id, "cs_test_2");
  const bodies = stripeBodies();
  assert.equal(bodies.length, 2);
  assert.equal(bodies[1].get("consent_collection[promotions]"), null);
  const keys = calls.filter((c) => c.url.startsWith("https://api.stripe.com/v1/checkout/sessions")).map((c) => c.opts.headers["Idempotency-Key"]);
  assert.notEqual(keys[0], keys[1], "the retry needs its own idempotency key");
});

test("an unrelated Stripe error is not retried", async () => {
  stripeReply = () => new Response(JSON.stringify({ error: { type: "card_error", message: "Your account cannot currently make live charges." } }), { status: 400 });
  const res = await buy("moderntex");
  assert.equal(res.status, 502);
  assert.equal(stripeBodies().length, 1);
  assert.equal(isRecoveryParamError({ error: { param: "line_items[0][price]" } }), false);
});

// --- webhook ------------------------------------------------------------------------------------------------
function signed(event) {
  const body = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
  return new Request("https://purplelink.llc/.netlify/functions/stripe-webhook", {
    method: "POST", headers: { "stripe-signature": `t=${t},v1=${v1}` }, body,
  });
}
const expired = ({ id = "cs_exp_1", product = "moderntex", consent = "opt_in", email = "lead@example.edu", url = "https://buy.stripe.com/r/live_abc" } = {}) => ({
  id: `evt_${id}`, type: "checkout.session.expired",
  data: { object: {
    id, status: "expired", payment_status: "unpaid", metadata: { product },
    consent: consent ? { promotions: consent } : null,
    customer_details: email ? { email } : null,
    after_expiration: url ? { recovery: { enabled: true, url, expires_at: 0 } } : null,
  } },
});
const resendCalls = () => calls.filter((c) => c.url.startsWith("https://api.resend.com/"));

test("a consenting ModernTex lead gets exactly one plain recovery email with the recovery link and an unsubscribe", async () => {
  const res = await webhook(signed(expired()));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, "recovery_sent");
  const sent = resendCalls();
  assert.equal(sent.length, 1);
  const mail = JSON.parse(sent[0].opts.body);
  assert.deepEqual(mail.to, ["lead@example.edu"]);
  assert.match(mail.text, /https:\/\/buy\.stripe\.com\/r\/live_abc/);
  assert.match(mail.text, /\$19\.99/);
  assert.match(mail.text, /nothing was charged/);
  assert.match(mail.text, /followup-unsubscribe\?u=/);
  assert.ok(mail.headers["List-Unsubscribe"]);
  assert.doesNotMatch(mail.text, /—/, "no em dashes");

  // Stripe redelivers the same event: no second email.
  await webhook(signed(expired()));
  assert.equal(resendCalls().length, 1);
  // A second abandoned checkout from the same address inside 30 days: still no second email.
  const again = await webhook(signed(expired({ id: "cs_exp_2" })));
  assert.equal((await again.json()).status, "recovery_quiet");
  assert.equal(resendCalls().length, 1);
});

test("no email without consent, without an address, without a recovery URL, or for another product", async () => {
  for (const [opts, status] of [
    [{ consent: "none" }, "recovery_no_consent"],
    [{ consent: null }, "recovery_no_consent"],
    [{ email: "" }, "recovery_no_email"],
    [{ url: "" }, "recovery_no_recovery_url"],
    [{ product: "vitae-plus-monthly" }, "recovery_not_recovery_product"],
  ]) {
    const res = await webhook(signed(expired(opts)));
    assert.equal((await res.json()).status, status);
  }
  assert.equal(resendCalls().length, 0);
});

test("no email to someone who already bought ModernTex or unsubscribed from follow-ups", async () => {
  const paid = {
    id: "evt_paid", type: "checkout.session.completed",
    data: { object: { id: "cs_live_mtx_abcdefghij", status: "complete", payment_status: "paid", amount_total: 1999,
      customer_details: { email: "Buyer@Example.edu" }, metadata: { product: "moderntex" } } },
  };
  await webhook(signed(paid));
  calls = [];
  const res = await webhook(signed(expired({ email: "buyer@example.edu" })));
  assert.equal((await res.json()).status, "recovery_already_bought");

  store.set(`followup-suppressed/${emailHash("gone@example.edu")}`, "2026-10-01T00:00:00Z");
  const res2 = await webhook(signed(expired({ id: "cs_exp_9", email: "gone@example.edu" })));
  assert.equal((await res2.json()).status, "recovery_suppressed");
  assert.equal(resendCalls().length, 0);
});

test("CHECKOUT_RECOVERY=off sends nothing", async () => {
  env.CHECKOUT_RECOVERY = "off";
  const res = await webhook(signed(expired()));
  assert.equal((await res.json()).status, "recovery_off");
  assert.equal(resendCalls().length, 0);
});

test("a failed send returns 502 so Stripe retries, and the retry sends", async () => {
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    return new Response("{}", { status: 500 });
  };
  const res = await webhook(signed(expired()));
  assert.equal(res.status, 502);
  globalThis.fetch = async (url, opts = {}) => { calls.push({ url: String(url), opts }); return new Response("{}", { status: 200 }); };
  const retry = await webhook(signed(expired()));
  assert.equal((await retry.json()).status, "recovery_sent");
});

test("the recovery URL is escaped in the HTML part", () => {
  const mail = recoveryEmail({ to: "a@b.co", product: "moderntex", url: "https://buy.stripe.com/r/x?a=1&b=<2>", secret: "s" });
  assert.match(mail.html, /a=1&amp;b=&lt;2&gt;/);
  assert.doesNotMatch(mail.html, /<2>/);
});

// ---- Every one-time product (2026-11-05, docs/designs/buyer-revenue-program.md piece 3) ----

const { readFileSync } = await import("node:fs");
const repo = new URL("../../", import.meta.url);
const read = (rel) => readFileSync(new URL(rel, repo), "utf8");
const EXTRA = { "bundle-2": { apps: "moderntex,legroom" }, "bundle-3": { apps: "moderntex,legroom,keyfeel" } };
const extraFor = (product) => ({ ...(EXTRA[product] || {}), ...(product.startsWith("photo-license") ? { photo: "DSC_0001" } : {}) });

// Products whose price lives in a Stripe Price (an env var), not in checkout.mjs: where the price is checked instead.
const backendAmounts = (() => {
  const out = {};
  for (const m of read("backend/app.py").matchAll(/^\s+"([a-z0-9-]+)":\s+\{[^\n]*"amount": (\d+)/gm)) out[m[1]] = Number(m[2]);
  return out;
})();
const PAGE_PRICE = {
  "outbound-veil": ["site/outbound-veil/index.html", "$29.99"],
  "legroom": ["site/legroom/index.html", "$9.99"],
  "lenses": ["site/lenses/index.html", "$4.99"],
  "kit-faceless": ["site/kits/index.html", "$49"],
  "kit-monetization": ["site/kits/index.html", "$29"],
  "kit-clip": ["site/kits/index.html", "$10"],
  "kit-bundle": ["site/kits/index.html", "$59"],
};

test("every one-time product in checkout has a recovery entry, and nothing else does", async () => {
  const src = read("netlify/functions/checkout.mjs");
  const start = src.indexOf("const PRODUCT_CATALOG = {");
  const catalog = src.slice(start, src.indexOf("\n};", start));
  const keys = [...catalog.matchAll(/^\s+"([a-z0-9-]+)":\s+\{/gm)].map((m) => m[1]);
  assert.ok(keys.length > 40, "parsed the catalog");
  for (const product of keys) {
    if (product === "moderntex-seats") continue; // priced by seat count, deliberately not recovered
    calls = [];
    const res = await buy(product, extraFor(product));
    assert.equal(res.status, 200, product);
    const [p] = stripeBodies();
    const oneTime = p.get("mode") === "payment";
    assert.equal(Object.hasOwn(RECOVERY_PRODUCTS, product), oneTime, `${product}: recovery entry iff one-time`);
    if (oneTime) assert.equal(p.get("after_expiration[recovery][enabled]"), "true", product);
  }
  for (const product of Object.keys(RECOVERY_PRODUCTS)) assert.ok(keys.includes(product), `${product} is a checkout product`);
});

test("every price a recovery email states is the price that product is sold at", async () => {
  for (const [product, entry] of Object.entries(RECOVERY_PRODUCTS)) {
    if (entry.percent) continue; // bundles: priced from the chosen apps, see the bundle recovery test below
    assert.equal(entry.price, `$${(entry.cents / 100).toFixed(2)}`, product);
    calls = [];
    await buy(product, extraFor(product));
    const [p] = stripeBodies();
    const inline = p.get("line_items[0][price_data][unit_amount]");
    if (inline !== null) {
      assert.equal(inline, String(entry.cents), `${product}: checkout.mjs inline amount`);
    } else if (Object.hasOwn(backendAmounts, product)) {
      assert.equal(backendAmounts[product], entry.cents, `${product}: PAID_PRODUCTS in backend/app.py`);
    } else {
      assert.ok(PAGE_PRICE[product], `${product}: env-priced, so it needs a page price to check against`);
      const [page, shown] = PAGE_PRICE[product];
      assert.ok(read(page).includes(shown), `${product}: ${page} shows ${shown}`);
      assert.equal(Math.round(Number(shown.slice(1)) * 100), entry.cents, `${product}: ${shown}`);
    }
  }
});

test("app emails say updates are included; other products only say once", () => {
  const url = "https://checkout.stripe.com/c/pay/x";
  const app = recoveryEmail({ to: "a@example.edu", product: "keyfeel", url, secret: "s" });
  assert.match(app.text, /\(\$9\.99, once, with updates included\)/);
  assert.equal(app.subject, "Your Keyfeel checkout");
  const review = recoveryEmail({ to: "a@example.edu", product: "paper-review-standard", url, secret: "s" });
  assert.match(review.text, /You started buying a Paper Review \(Standard\) on purplelink\.llc/);
  assert.match(review.text, /\(\$9\.00, once\)/);
  assert.doesNotMatch(review.text, /updates/);
  assert.equal(review.subject, "Your Paper Review (Standard) checkout");
  assert.equal(recoveryEmail({ to: "a@example.edu", product: "bundle-2", url, secret: "s" }).subject, "Your Purplelink bundle checkout");
  assert.equal(recoveryEmail({ to: "a@example.edu", product: "lenses", url, secret: "s" }).text.includes("updates"), false);
});

const url = "https://buy.stripe.com/r/live_abc";
test("a bundle recovery email states the session's own amount, or the percent off when there is none", () => {
  const two = recoveryEmail({ to: "a@example.edu", product: "bundle-2", url, secret: "s", cents: 3749 });
  assert.match(two.text, /\(\$37\.49, once, with updates included\)/);
  const noAmount = recoveryEmail({ to: "a@example.edu", product: "bundle-2", url, secret: "s" });
  assert.match(noAmount.text, /\(25% off the apps' own prices, once, with updates included\)/);
  assert.doesNotMatch(noAmount.text, /34\.99/);
  assert.match(recoveryEmail({ to: "a@example.edu", product: "bundle-3", url, secret: "s" }).text, /40% off/);
  assert.match(recoveryEmail({ to: "a@example.edu", product: "bundle-3", url, secret: "s", cents: 0 }).text, /40% off/);
});

test("a bundle purchase counts as buying each app in it", async () => {
  const paid = {
    id: "evt_paid_bundle", type: "checkout.session.completed",
    data: { object: { id: "cs_live_bundle_abcdefghij", status: "complete", payment_status: "paid", amount_total: 3749,
      customer_details: { email: "pair@example.edu" }, metadata: { product: "bundle-2", apps: "moderntex,legroom" } } },
  };
  await webhook(signed(paid));
  const h = emailHash("pair@example.edu");
  assert.ok(store.get(`checkout-recovery/bought:bundle-2:${h}`));
  assert.ok(store.get(`checkout-recovery/bought:moderntex:${h}`));
  assert.ok(store.get(`checkout-recovery/bought:legroom:${h}`));
  assert.equal(store.get(`checkout-recovery/bought:keyfeel:${h}`), undefined);
});

test("a Paper Review purchase (forwarded to Modal) is recorded as bought too", async () => {
  const paid = {
    id: "evt_paid_pr", type: "checkout.session.completed",
    data: { object: { id: "cs_live_review_abcdefghij", status: "complete", payment_status: "paid", amount_total: 900, amount_subtotal: 900,
      customer_details: { email: "author@example.edu" }, metadata: { product: "paper-review-standard" } } },
  };
  await webhook(signed(paid));
  assert.ok(store.get(`checkout-recovery/bought:paper-review-standard:${emailHash("author@example.edu")}`));
});
