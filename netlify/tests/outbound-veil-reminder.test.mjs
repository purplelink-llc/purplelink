// Outbound Veil trial emails: the signup, the one-click unsubscribe, and the daily reminder run
// (due, not yet due, already bought, buyer check unavailable, too old). Blobs, Resend and Stripe are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/outbound-veil-reminder.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
    list: async () => ({ blobs: [...store.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { RESEND_API_KEY: "re_dummy", STRIPE_SECRET_KEY: "sk_test_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };
const { default: handler, sendDueReminders, REMIND_AFTER_DAYS } = await import("../functions/outbound-veil-reminder.mjs");

let calls, stripeSessions, stripeStatus, resendStatus;
beforeEach(() => {
  store.clear();
  calls = [];
  stripeSessions = [];
  stripeStatus = 200;
  resendStatus = 200;
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    if (u.startsWith("https://api.stripe.com/")) {
      return new Response(JSON.stringify({ data: stripeSessions }), { status: stripeStatus });
    }
    return new Response("{}", { status: resendStatus });
  };
});

const post = (body, headers = {}) => new Request("https://purplelink.llc/.netlify/functions/outbound-veil-reminder", {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": "203.0.113.9", ...headers }, body: JSON.stringify(body),
});
const mails = () => calls.filter((c) => c.url.startsWith("https://api.resend.com/")).map((c) => JSON.parse(c.opts.body));
const DAY = 86400000;
// Everything kept for the reminders, not the shared per-day rate-limit counters.
const kept = () => [...store.keys()].filter((k) => !k.startsWith("rate-limits/"));
const seed = (email, ageDays, token = "a".repeat(48)) => {
  const created = Date.now() - ageDays * DAY;
  store.set(`ov-trial-reminders/${email}`, JSON.stringify({
    email, createdAt: new Date(created).toISOString(), remindAt: new Date(created + REMIND_AFTER_DAYS * DAY).toISOString(), unsubscribeToken: token,
  }));
  store.set(`ov-trial-reminder-tokens/${token}`, email);
};

test("a signup stores a record and sends the setup email with an unsubscribe link", async () => {
  const res = await handler(post({ email: "Reader@Example.org" }));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  const [mail] = mails();
  assert.deepEqual(mail.to, ["reader@example.org"]);
  assert.match(mail.text, /outbound-veil\/start\//);
  assert.match(mail.text, /outbound-veil-reminder\?u=[a-f0-9]{48}/);
  assert.match(mail.headers["List-Unsubscribe-Post"], /One-Click/);
  // One download: the trial copy takes the key itself, so the email never sends anyone to a second download.
  assert.match(mail.text, /asks for a license key/);
  assert.match(mail.text, /no second download/);
  assert.doesNotMatch(mail.text, /full (app|download)|separate|install it (over|in place)/i);
  const record = JSON.parse(store.get("ov-trial-reminders/reader@example.org"));
  assert.equal(Date.parse(record.remindAt) - Date.parse(record.createdAt), REMIND_AFTER_DAYS * DAY);
});

test("bad addresses, the honeypot and a repeat within a day send nothing", async () => {
  assert.equal((await handler(post({ email: "not-an-email" }))).status, 400);
  const bot = await handler(post({ email: "bot@example.org", website: "http://spam" }));
  assert.equal(bot.status, 200);
  assert.deepEqual(kept(), []);
  await handler(post({ email: "twice@example.org" }));
  const again = await handler(post({ email: "twice@example.org" }));
  assert.deepEqual(await again.json(), { ok: true, already: true });
  assert.equal(mails().length, 1);
});

test("a foreign origin is refused, and a failed send keeps nobody", async () => {
  assert.equal((await handler(post({ email: "a@example.org" }, { origin: "https://evil.example" }))).status, 403);
  resendStatus = 500;
  const res = await handler(post({ email: "b@example.org" }));
  assert.equal(res.status, 502);
  assert.deepEqual(kept(), []);
});

test("one-click unsubscribe deletes the record and answers the same for an unknown token", async () => {
  seed("gone@example.org", 1, "b".repeat(48));
  const url = `https://purplelink.llc/.netlify/functions/outbound-veil-reminder?u=${"b".repeat(48)}`;
  assert.equal((await handler(new Request(url, { method: "POST" }))).status, 200);
  assert.deepEqual(kept(), []);
  const unknown = await handler(new Request(`https://purplelink.llc/.netlify/functions/outbound-veil-reminder?u=${"c".repeat(48)}`));
  assert.equal(unknown.status, 200);
});

test("the daily run sends due reminders, deletes their records, and leaves the rest", async () => {
  seed("due@example.org", 5.5, "d".repeat(48));
  seed("early@example.org", 2, "e".repeat(48));
  const result = await sendDueReminders();
  assert.equal(result.sent, 1);
  assert.deepEqual(mails().map((m) => m.to[0]), ["due@example.org"]);
  assert.match(mails()[0].text, /\$29\.99 once/);
  assert.match(mails()[0].text, /Enter license key\u2026/);
  assert.match(mails()[0].text, /purplelink\.llc\/recover\//);
  assert.match(mails()[0].html, /Enter license key\u2026/);
  assert.doesNotMatch(mails()[0].text, /full (app|download)|separate|install it (over|in place)/i);
  assert.equal(store.has("ov-trial-reminders/due@example.org"), false);
  assert.equal(store.has(`ov-trial-reminder-tokens/${"d".repeat(48)}`), false);
  assert.equal(store.has("ov-trial-reminders/early@example.org"), true);
});

test("a buyer gets no reminder and their record is deleted", async () => {
  seed("buyer@example.org", 6, "f".repeat(48));
  stripeSessions = [{ metadata: { product: "app-suite" }, payment_status: "paid" }];
  const result = await sendDueReminders();
  assert.equal(result.skippedBuyers, 1);
  assert.equal(mails().length, 0);
  assert.deepEqual(kept(), []);
});

test("when Stripe cannot be asked the record waits for tomorrow", async () => {
  seed("wait@example.org", 6);
  stripeStatus = 500;
  const result = await sendDueReminders();
  assert.equal(result.deferred, 1);
  assert.equal(mails().length, 0);
  assert.equal(store.has("ov-trial-reminders/wait@example.org"), true);
});

test("records older than two weeks are dropped without an email", async () => {
  seed("old@example.org", 20);
  const result = await sendDueReminders();
  assert.equal(result.expired, 1);
  assert.equal(mails().length, 0);
  assert.deepEqual(kept(), []);
});
