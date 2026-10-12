// RubbleFront double opt-in list: subscribe, confirm, unsubscribe and the broadcast endpoint.
// Blobs and Resend are stubbed; nothing is sent.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/rubblefront-list.test.mjs

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

const env = { RESEND_API_KEY: "re_dummy", RUBBLEFRONT_BROADCAST_SECRET: "test-secret" };
globalThis.Netlify = { env: { get: (k) => env[k] } };
const { default: subscribe } = await import("../functions/rubblefront-subscribe.mjs");
const { default: confirm } = await import("../functions/rubblefront-confirm.mjs");
const { default: unsubscribe } = await import("../functions/rubblefront-unsubscribe.mjs");
const { default: broadcast, BATCH_SIZE } = await import("../functions/rubblefront-broadcast.mjs");
const { POSTAL_ADDRESS, hashEmail } = await import("../lib/rubblefront-list.mjs");

let calls, resendStatus, logs;
const realError = console.error;
beforeEach(() => {
  store.clear();
  calls = [];
  logs = [];
  resendStatus = 200;
  console.error = (...a) => logs.push(a.join(" "));
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    return new Response("{}", { status: resendStatus });
  };
});
process.on("exit", () => { console.error = realError; });

const DAY = 86400000;
const post = (body, headers = {}) => new Request("https://purplelink.llc/.netlify/functions/rubblefront-subscribe", {
  method: "POST",
  headers: { "Content-Type": "application/json", origin: "https://rubblefront.com", "x-nf-client-connection-ip": "203.0.113.9", ...headers },
  body: JSON.stringify(body),
});
const singles = () => calls.filter((c) => c.url === "https://api.resend.com/emails").map((c) => JSON.parse(c.opts.body));
const batches = () => calls.filter((c) => c.url.endsWith("/emails/batch")).map((c) => JSON.parse(c.opts.body));
const record = (email) => JSON.parse(store.get(`rf-list/${email}`));
const kept = () => [...store.keys()].filter((k) => !k.startsWith("rate-limits/"));
const confirmReq = (t) => new Request(`https://purplelink.llc/.netlify/functions/rubblefront-confirm?t=${t}`);
const unsubReq = (u, method = "GET") => new Request(`https://purplelink.llc/.netlify/functions/rubblefront-unsubscribe?u=${u}`, { method });
const signupAndConfirm = async (email) => {
  await subscribe(post({ email, source: "hero" }));
  await confirm(confirmReq(record(email).confirmToken));
};

test("signup stores a pending record and sends one confirmation email, with CORS for rubblefront.com", async () => {
  const res = await subscribe(post({ email: "Reader@Example.org", source: "footer" }));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  assert.equal(res.headers.get("access-control-allow-origin"), "https://rubblefront.com");
  const rec = record("reader@example.org");
  assert.equal(rec.status, "pending");
  assert.equal(rec.source, "footer");
  assert.match(rec.confirmToken, /^[a-f0-9]{48}$/);
  assert.equal(store.get(`rf-list-tokens/c:${rec.confirmToken}`), "reader@example.org");
  const [mail] = singles();
  assert.deepEqual(mail.to, ["reader@example.org"]);
  assert.equal(mail.from, "RubbleFront <news@purplelink.llc>");
  assert.equal(mail.reply_to, "ben@purplelink.llc");
  assert.equal(mail.subject, "Confirm your email for RubbleFront news");
  assert.match(mail.text, new RegExp(`rubblefront-confirm\\?t=${rec.confirmToken}`));
  assert.match(mail.text, /ignore this email and nothing happens/);
  assert.ok(mail.text.includes(POSTAL_ADDRESS));
  assert.doesNotMatch(mail.text + mail.html, /reader@example\.org/); // links carry no address
  assert.match(mail.headers["List-Unsubscribe-Post"], /One-Click/);
});

test("preflight is answered for rubblefront.com and refused for others", async () => {
  const ok = await subscribe(new Request("https://purplelink.llc/.netlify/functions/rubblefront-subscribe", { method: "OPTIONS", headers: { origin: "https://www.rubblefront.com" } }));
  assert.equal(ok.status, 204);
  assert.equal(ok.headers.get("access-control-allow-origin"), "https://www.rubblefront.com");
  const bad = await subscribe(new Request("https://purplelink.llc/.netlify/functions/rubblefront-subscribe", { method: "OPTIONS", headers: { origin: "https://evil.example" } }));
  assert.equal(bad.status, 403);
});

test("bad origin, bad address and the honeypot send nothing and store nothing", async () => {
  assert.equal((await subscribe(post({ email: "a@example.org" }, { origin: "https://evil.example" }))).status, 403);
  assert.equal((await subscribe(post({ email: "nope" }))).status, 400);
  const bot = await subscribe(post({ email: "bot@example.org", website: "http://spam" }));
  assert.equal(bot.status, 200);
  assert.deepEqual(kept(), []);
  assert.equal(calls.length, 0);
});

test("a repeat within a day sends nothing new; after a day a fresh link replaces the old one", async () => {
  await subscribe(post({ email: "twice@example.org", source: "hero" }));
  const first = record("twice@example.org");
  const again = await subscribe(post({ email: "twice@example.org", source: "hero" }));
  assert.deepEqual(await again.json(), { ok: true });
  assert.equal(singles().length, 1);
  store.set("rf-list/twice@example.org", JSON.stringify({ ...first, createdAt: new Date(Date.now() - 2 * DAY).toISOString() }));
  await subscribe(post({ email: "twice@example.org", source: "hero" }));
  assert.equal(singles().length, 2);
  assert.notEqual(record("twice@example.org").confirmToken, first.confirmToken);
  assert.equal(store.has(`rf-list-tokens/c:${first.confirmToken}`), false);
});

test("confirming marks the record confirmed and redirects; a second click still lands on success", async () => {
  await subscribe(post({ email: "c@example.org", source: "hero" }));
  const t = record("c@example.org").confirmToken;
  const res = await confirm(confirmReq(t));
  assert.equal(res.status, 302);
  assert.equal(res.headers.get("location"), "https://rubblefront.com/confirmed/");
  const rec = record("c@example.org");
  assert.equal(rec.status, "confirmed");
  assert.ok(Date.parse(rec.confirmedAt) > 0);
  assert.equal(rec.source, "hero");
  assert.equal((await confirm(confirmReq(t))).headers.get("location"), "https://rubblefront.com/confirmed/");
});

test("unknown, malformed and expired confirm tokens go to the error page; the expired record is deleted", async () => {
  assert.equal((await confirm(confirmReq("zzz"))).headers.get("location"), "https://rubblefront.com/confirmed/?error=1");
  assert.equal((await confirm(confirmReq("a".repeat(48)))).headers.get("location"), "https://rubblefront.com/confirmed/?error=1");
  await subscribe(post({ email: "old@example.org", source: "hero" }));
  const rec = record("old@example.org");
  store.set("rf-list/old@example.org", JSON.stringify({ ...rec, createdAt: new Date(Date.now() - 8 * DAY).toISOString() }));
  assert.equal((await confirm(confirmReq(rec.confirmToken))).headers.get("location"), "https://rubblefront.com/confirmed/?error=1");
  assert.equal(store.has("rf-list/old@example.org"), false);
  assert.equal(store.has(`rf-list-tokens/c:${rec.confirmToken}`), false);
});

test("an already confirmed address gets the same neutral 200 and no email", async () => {
  await signupAndConfirm("known@example.org");
  calls.length = 0;
  const res = await subscribe(post({ email: "known@example.org", source: "footer" }));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  assert.equal(calls.length, 0);
  assert.equal(record("known@example.org").status, "confirmed");
});

test("if Resend refuses, nothing is kept and the answer is 502", async () => {
  resendStatus = 500;
  const res = await subscribe(post({ email: "f@example.org", source: "hero" }));
  assert.equal(res.status, 502);
  assert.deepEqual(kept(), []);
});

test("rate limits: per address and per IP", async () => {
  for (let i = 0; i < 3; i++) await subscribe(post({ email: "same@example.org" }));
  assert.equal((await subscribe(post({ email: "same@example.org" }))).status, 429);
  store.clear();
  let last;
  for (let i = 0; i < 21; i++) last = await subscribe(post({ email: `u${i}@example.org` }));
  assert.equal(last.status, 429);
});

test("GET unsubscribe changes nothing and redirects to the confirm page; POST unsubscribes", async () => {
  await signupAndConfirm("gone@example.org");
  const u = record("gone@example.org").unsubscribeToken;
  const get = await unsubscribe(unsubReq(u));
  assert.equal(get.status, 302);
  assert.equal(get.headers.get("location"), `https://rubblefront.com/unsubscribe/?u=${u}`);
  assert.equal(record("gone@example.org").status, "confirmed"); // a mail scanner following the link did nothing
  assert.equal(store.has(`rf-list-suppressed/${hashEmail("gone@example.org")}`), false);
  // The page's button: a fetch POST from rubblefront.com.
  const res = await unsubscribe(new Request(unsubReq(u).url, { method: "POST", headers: { origin: "https://rubblefront.com" } }));
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("access-control-allow-origin"), "https://rubblefront.com");
  assert.deepEqual(kept(), [`rf-list-suppressed/${hashEmail("gone@example.org")}`]);
  assert.doesNotMatch(kept().join(" "), /gone@example/);
  // Unknown token: same answers.
  assert.equal((await unsubscribe(unsubReq("c".repeat(48)))).status, 302);
  assert.equal((await unsubscribe(unsubReq("c".repeat(48), "POST"))).status, 200);
  assert.equal((await unsubscribe(unsubReq("junk"))).headers.get("location"), "https://rubblefront.com/unsubscribe/");
});

test("unsubscribe preflight is allowed for rubblefront.com only", async () => {
  const mk = (o) => new Request("https://purplelink.llc/.netlify/functions/rubblefront-unsubscribe?u=x", { method: "OPTIONS", headers: { origin: o } });
  assert.equal((await unsubscribe(mk("https://rubblefront.com"))).status, 204);
  assert.equal((await unsubscribe(mk("https://evil.example"))).status, 403);
});

const form = (fields, headers = {}) => new Request("https://purplelink.llc/.netlify/functions/rubblefront-subscribe", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded", origin: "https://rubblefront.com", "x-nf-client-connection-ip": "203.0.113.9", ...headers },
  body: new URLSearchParams(fields).toString(),
});

test("form POST: success is a 303 to /thanks/ and sends the confirmation; repeats and confirmed addresses look the same", async () => {
  const res = await subscribe(form({ email: "Form@Example.org", source: "hero", website: "" }));
  assert.equal(res.status, 303);
  assert.equal(res.headers.get("location"), "https://rubblefront.com/thanks/");
  assert.equal(record("form@example.org").source, "hero");
  assert.equal(singles().length, 1);
  const again = await subscribe(form({ email: "form@example.org", source: "hero" }));
  assert.equal(again.headers.get("location"), "https://rubblefront.com/thanks/");
  assert.equal(singles().length, 1);
  await confirm(confirmReq(record("form@example.org").confirmToken));
  const known = await subscribe(form({ email: "form@example.org", source: "hero" }));
  assert.equal(known.headers.get("location"), "https://rubblefront.com/thanks/");
  assert.equal(singles().length, 1);
});

test("form POST: invalid address, rate limit and a Resend failure go to /thanks/?error=1", async () => {
  const bad = await subscribe(form({ email: "nope", source: "hero" }));
  assert.equal(bad.status, 303);
  assert.equal(bad.headers.get("location"), "https://rubblefront.com/thanks/?error=1");
  resendStatus = 500;
  const failed = await subscribe(form({ email: "f@example.org", source: "hero" }));
  assert.equal(failed.headers.get("location"), "https://rubblefront.com/thanks/?error=1");
  assert.deepEqual(kept(), []);
  resendStatus = 200;
  for (let i = 0; i < 3; i++) await subscribe(form({ email: "same@example.org" }));
  const limited = await subscribe(form({ email: "same@example.org" }));
  assert.equal(limited.headers.get("location"), "https://rubblefront.com/thanks/?error=1");
});

test("form POST: the honeypot looks like success but stores and sends nothing; a bad origin is refused", async () => {
  const bot = await subscribe(form({ email: "bot@example.org", website: "http://spam" }));
  assert.equal(bot.status, 303);
  assert.equal(bot.headers.get("location"), "https://rubblefront.com/thanks/");
  assert.deepEqual(kept(), []);
  assert.equal(calls.length, 0);
  assert.equal((await subscribe(form({ email: "a@example.org" }, { origin: "https://evil.example" }))).status, 403);
  assert.equal(calls.length, 0);
});

test("the JSON path is unchanged: 200 JSON on success, 400 JSON on a bad address", async () => {
  const ok = await subscribe(post({ email: "json@example.org", source: "hero" }));
  assert.equal(ok.status, 200);
  assert.deepEqual(await ok.json(), { ok: true });
  const bad = await subscribe(post({ email: "nope" }));
  assert.equal(bad.status, 400);
  assert.deepEqual(await bad.json(), { error: "invalid_email" });
});

test("emails link to the unsubscribe page; the header keeps the one-click function URL", async () => {
  await subscribe(post({ email: "links@example.org", source: "hero" }));
  const [mail] = singles();
  const u = record("links@example.org").unsubscribeToken;
  assert.ok(mail.text.includes(`https://rubblefront.com/unsubscribe/?u=${u}`));
  assert.ok(mail.html.includes(`href="https://rubblefront.com/unsubscribe/?u=${u}"`));
  assert.ok(mail.headers["List-Unsubscribe"].includes(`/.netlify/functions/rubblefront-unsubscribe?u=${u}`));
});

test("RFC 8058 one-click POST returns 200 and unsubscribes", async () => {
  await signupAndConfirm("one@example.org");
  const u = record("one@example.org").unsubscribeToken;
  const res = await unsubscribe(unsubReq(u, "POST"));
  assert.equal(res.status, 200);
  assert.equal(store.has("rf-list/one@example.org"), false);
});

test("an unsubscribed address can sign up again, and confirming clears the marker", async () => {
  await signupAndConfirm("back@example.org");
  await unsubscribe(unsubReq(record("back@example.org").unsubscribeToken, "POST"));
  await signupAndConfirm("back@example.org");
  assert.equal(record("back@example.org").status, "confirmed");
  assert.equal(store.has(`rf-list-suppressed/${hashEmail("back@example.org")}`), false);
});

const bc = (body, auth = "Bearer test-secret") => new Request("https://purplelink.llc/.netlify/functions/rubblefront-broadcast", {
  method: "POST", headers: { "Content-Type": "application/json", authorization: auth }, body: JSON.stringify(body),
});
const msg = { subject: "Demo news", text: "The demo is out.", html: "<p>The demo is out.</p>" };

test("broadcast needs the secret", async () => {
  assert.equal((await broadcast(bc({ action: "count" }, "Bearer wrong"))).status, 401);
  assert.equal((await broadcast(bc({ action: "count" }, ""))).status, 401);
});

test("broadcast counts only confirmed, unsuppressed addresses and excludes unsubscribed ones", async () => {
  await signupAndConfirm("a@example.org");
  await signupAndConfirm("b@example.org");
  await subscribe(post({ email: "pending@example.org" }));
  await unsubscribe(unsubReq(record("b@example.org").unsubscribeToken, "POST"));
  // A stale confirmed record that somehow survived with a suppression marker is still excluded.
  await signupAndConfirm("stale@example.org");
  store.set(`rf-list-suppressed/${hashEmail("stale@example.org")}`, "x");
  const res = await broadcast(bc({ action: "count" }));
  assert.deepEqual(await res.json(), { count: 1 });
});

test("broadcast send: headers, per-recipient links, postal line, resume without double sends, no address in logs", async () => {
  await signupAndConfirm("a@example.org");
  await signupAndConfirm("b@example.org");
  calls.length = 0;
  const first = await broadcast(bc({ action: "send", broadcastId: "test-broadcast-1", expect: 2, ...msg }));
  assert.deepEqual(await first.json(), { sent: 2, remaining: 0, total: 2 });
  const [batch] = batches();
  assert.equal(batch.length, 2);
  const a = batch.find((m) => m.to[0] === "a@example.org");
  assert.match(a.headers["List-Unsubscribe"], /^<https:\/\/purplelink\.llc\/\.netlify\/functions\/rubblefront-unsubscribe\?u=[a-f0-9]{48}>, <mailto:ben@purplelink\.llc/);
  assert.equal(a.headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
  assert.ok(a.text.includes(`https://rubblefront.com/unsubscribe/?u=${record("a@example.org").unsubscribeToken}`));
  assert.ok(a.html.includes(POSTAL_ADDRESS));
  assert.notEqual(a.text, batch.find((m) => m.to[0] === "b@example.org").text);
  // Running the same broadcast again sends nobody.
  const again = await broadcast(bc({ action: "send", broadcastId: "test-broadcast-1", ...msg }));
  assert.deepEqual(await again.json(), { sent: 0, remaining: 0, total: 2 });
  assert.equal(batches().length, 1);
  assert.doesNotMatch(logs.join("\n"), /example\.org/);
});

test("broadcast send refuses a changed count, and batches large lists", async () => {
  await signupAndConfirm("a@example.org");
  const wrong = await broadcast(bc({ action: "send", broadcastId: "test-broadcast-2", expect: 5, ...msg }));
  assert.equal(wrong.status, 409);
  assert.equal(batches().length, 0);
  for (let i = 0; i < BATCH_SIZE + 5; i++) {
    const email = `n${String(i).padStart(3, "0")}@example.org`;
    store.set(`rf-list/${email}`, JSON.stringify({ email, status: "confirmed", unsubscribeToken: String(i).padStart(48, "0"), confirmToken: "x" }));
  }
  const res = await (await broadcast(bc({ action: "send", broadcastId: "test-broadcast-3", ...msg }))).json();
  assert.equal(res.sent, BATCH_SIZE);
  assert.equal(res.remaining, 6);
});

test("broadcast test mode sends one copy to one address; a Resend failure is a 502", async () => {
  const res = await broadcast(bc({ action: "test", to: "ben@purplelink.llc", ...msg }));
  assert.equal(res.status, 200);
  const [mail] = singles();
  assert.deepEqual(mail.to, ["ben@purplelink.llc"]);
  assert.match(mail.subject, /^\[TEST\]/);
  resendStatus = 500;
  assert.equal((await broadcast(bc({ action: "test", to: "ben@purplelink.llc", ...msg }))).status, 502);
});

test("no function logs an address, even when storage or Resend fails", async () => {
  resendStatus = 500;
  await subscribe(post({ email: "secret.person@example.org" }));
  assert.ok(logs.length > 0);
  assert.doesNotMatch(logs.join("\n"), /secret\.person|example\.org/);
});
