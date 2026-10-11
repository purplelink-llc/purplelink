// The day-14 follow-up: which orders are due, who is skipped, the email, the unsubscribe link, and that it does
// nothing at all until it is switched on. Stripe, Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/post-purchase-followup.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_SECRET_KEY: "sk_test_dummy", RESEND_API_KEY: "re_dummy", STRIPE_WEBHOOK_SECRET: "whsec_unit", POST_PURCHASE_FOLLOWUP: "on" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const lib = await import("../lib/followup.mjs");
const { runFollowups } = await import("../functions/post-purchase-followup.mjs");
const { default: unsubscribe } = await import("../functions/followup-unsubscribe.mjs");

const NOW = 1_800_000_000;
let orders, mails;
const session = (id, product, email, extra = {}) => ({
  id, payment_status: "paid", metadata: { product, ...(extra.seats ? { seats: String(extra.seats) } : {}) },
  customer_details: { email }, payment_intent: extra.charge ? { latest_charge: extra.charge } : null,
});
beforeEach(() => {
  store.clear();
  mails = [];
  orders = [];
  env.POST_PURCHASE_FOLLOWUP = "on";
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    if (u.includes("api.stripe.com/v1/checkout/sessions")) {
      return new Response(JSON.stringify({ data: orders, has_more: false }), { status: 200 });
    }
    if (u.startsWith("https://api.resend.com/")) {
      mails.push(JSON.parse(opts.body));
      return new Response("{}", { status: 200 });
    }
    return new Response("{}", { status: 404 });
  };
});

test("the window starts at 14 days and reaches back two more", () => {
  const w = lib.windowFor(NOW);
  assert.equal(w.lte, NOW - 14 * 86400);
  assert.equal(w.gte, NOW - 16 * 86400);
});

test("the email asks one question, names the app, and carries an opt-out, the address and a List-Unsubscribe header", () => {
  const m = lib.followupEmail({ to: "a@b.edu", product: "tapefolio", secret: "s" });
  assert.equal(lib.followupEmail({ to: "a@b.edu", product: "moderntex", secret: "s" }), null, "single ModernTex copies keep the backend sequence only");
  assert.equal(m.subject, "How is Tapefolio working out?");
  assert.match(m.text, /what do you use it for\?/);
  assert.match(m.text, /without a yes/);
  assert.match(m.text, /reply "stop"/);
  assert.match(m.text, /Atlanta, GA 30350/);
  assert.ok(!/https?:\/\/\S+review/i.test(m.text), "no review link until one is configured");
  assert.match(m.headers["List-Unsubscribe"], /followup-unsubscribe\?u=/);
  assert.equal(m.headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
  assert.deepEqual(m.to, ["a@b.edu"]);
  assert.ok(!m.text.includes("—"), "no em dash");
  assert.match(lib.followupEmail({ to: "a@b.edu", product: "moderntex-seats", seats: 12, secret: "s" }).text, /12 copies for your lab or department/);
  assert.equal(lib.followupEmail({ to: "a@b.edu", product: "kit-bundle", secret: "s" }), null);
  assert.equal(lib.followupEmail({ to: "a@b.edu", product: "app-suite", secret: "s" }).subject, "How is the Mac Suite working out?");
});

test("unsubscribe tokens round-trip, ignore case, and fail when changed or signed with another secret", () => {
  const t = lib.unsubscribeToken("Reader@Example.edu", "secret-1");
  assert.equal(lib.verifyUnsubscribeToken(t, "secret-1"), "reader@example.edu");
  assert.equal(lib.verifyUnsubscribeToken(t, "secret-2"), null);
  assert.equal(lib.verifyUnsubscribeToken(t.slice(0, -1) + (t.endsWith("0") ? "1" : "0"), "secret-1"), null);
  assert.equal(lib.verifyUnsubscribeToken("garbage", "secret-1"), null);
  assert.equal(lib.verifyUnsubscribeToken("", "secret-1"), null);
  assert.equal(lib.verifyUnsubscribeToken(undefined, "secret-1"), null);
});

test("switched off: it counts who is due and sends nothing, and remembers nothing", async () => {
  env.POST_PURCHASE_FOLLOWUP = "";
  orders = [session("cs_1", "outbound-veil", "a@x.edu"), session("cs_2", "keyfeel", "b@x.edu")];
  const r = await runFollowups({ nowS: NOW });
  assert.equal(r.ok, true);
  assert.equal(r.would_send, 2);
  assert.equal(r.sent, 0);
  assert.equal(r.enabled, false);
  assert.equal(mails.length, 0);
  assert.equal(store.size, 0);
});

test("switched on: one email per buyer, remembered by session, never twice", async () => {
  orders = [session("cs_1", "outbound-veil", "a@x.edu"), session("cs_2", "legroom", "b@x.edu")];
  const r = await runFollowups({ nowS: NOW });
  assert.equal(r.sent, 2);
  assert.equal(mails.length, 2);
  const again = await runFollowups({ nowS: NOW + 86400 });
  assert.equal(again.sent, 0);
  assert.equal(again.already, 2);
  assert.equal(mails.length, 2);
});

test("the same address buying two apps gets one email", async () => {
  orders = [session("cs_1", "legroom", "Same@x.edu"), session("cs_2", "keyfeel", "same@X.edu")];
  const r = await runFollowups({ nowS: NOW });
  assert.equal(r.sent, 1);
  assert.equal(r.quiet, 1);
  assert.equal(mails.length, 1);
  // A later purchase inside the quiet period is not emailed either.
  orders = [session("cs_3", "tapefolio", "same@x.edu")];
  const later = await runFollowups({ nowS: NOW + 30 * 86400 });
  assert.equal(later.sent, 0);
  assert.equal(later.quiet, 1);
});

test("refunded, disputed, unpaid, unknown-product and unsubscribed orders are skipped", async () => {
  orders = [
    session("cs_ref", "legroom", "r@x.edu", { charge: { refunded: true } }),
    session("cs_part", "legroom", "p@x.edu", { charge: { refunded: false, amount_refunded: 500 } }),
    session("cs_disp", "legroom", "d@x.edu", { charge: { disputed: true } }),
    { ...session("cs_unpaid", "legroom", "u@x.edu"), payment_status: "unpaid" },
    session("cs_kit", "kit-bundle", "k@x.edu"),
    session("cs_mtx", "moderntex", "m@x.edu"),
    session("cs_unsub", "legroom", "gone@x.edu"),
    { id: "cs_noemail", payment_status: "paid", metadata: { product: "legroom" }, customer_details: {} },
    session("cs_ok", "legroom", "ok@x.edu", { charge: { refunded: false, amount_refunded: 0 } }),
  ];
  store.set(`followup-suppressed/${lib.emailHash("gone@x.edu")}`, "2026-10-01");
  const r = await runFollowups({ nowS: NOW });
  assert.equal(r.sent, 1);
  assert.equal(r.suppressed, 1);
  assert.deepEqual(mails.map((m) => m.to[0]), ["ok@x.edu"]);
});

test("a send that Resend refuses is retried next run, not marked sent", async () => {
  orders = [session("cs_1", "legroom", "a@x.edu")];
  const real = globalThis.fetch;
  globalThis.fetch = async (url, opts) => (String(url).startsWith("https://api.resend.com/") ? new Response("no", { status: 500 }) : real(url, opts));
  const r = await runFollowups({ nowS: NOW });
  assert.equal(r.failed, 1);
  assert.equal(r.sent, 0);
  globalThis.fetch = real;
  const retry = await runFollowups({ nowS: NOW + 86400 });
  assert.equal(retry.sent, 1);
});

test("a run never sends more than the per-run limit", async () => {
  orders = Array.from({ length: lib.MAX_PER_RUN + 10 }, (_, i) => session(`cs_${i}`, "legroom", `u${i}@x.edu`));
  const r = await runFollowups({ nowS: NOW });
  assert.equal(r.sent, lib.MAX_PER_RUN);
});

test("an unsubscribe link records a suppression, and a bad one records nothing", async () => {
  const token = lib.unsubscribeToken("someone@x.edu", env.STRIPE_WEBHOOK_SECRET);
  const get = (t) => unsubscribe(new Request(`https://purplelink.llc/.netlify/functions/followup-unsubscribe?u=${encodeURIComponent(t)}`));
  const res = await get(token);
  assert.equal(res.status, 200);
  assert.match(await res.text(), /no more follow-up email/);
  assert.ok(store.get(`followup-suppressed/${lib.emailHash("someone@x.edu")}`));
  store.clear();
  const bad = await get("nope");
  assert.equal(bad.status, 200);
  assert.equal(store.size, 0);
  const post = await unsubscribe(new Request(`https://purplelink.llc/.netlify/functions/followup-unsubscribe?u=${encodeURIComponent(token)}`, { method: "POST" }));
  assert.equal((await post.json()).ok, true);
  assert.ok(store.get(`followup-suppressed/${lib.emailHash("someone@x.edu")}`));
  // Suppressed addresses are then skipped by the sender.
  orders = [session("cs_1", "legroom", "someone@x.edu")];
  const run = await runFollowups({ nowS: NOW });
  assert.equal(run.suppressed, 1);
  assert.equal(run.sent, 0);
});
