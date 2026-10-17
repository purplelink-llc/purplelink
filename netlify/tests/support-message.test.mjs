// support-message.mjs: the "write to Ben" box. Validation, honeypot, timing, origin, rate limits,
// the Resend payload (Reply-To, subject, plain body), provider failure and no logging of content.
// Blobs and Resend are stubbed; nothing is sent.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/support-message.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const store = new Map();
let limiterDown = false;
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => { if (limiterDown) throw new Error("down"); return store.get(`${name}/${k}`) ?? null; },
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { RESEND_API_KEY: "re_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };
const { default: handler, PER_IP_HOURLY, PER_IP_DAILY, GLOBAL_DAILY, MAX_MESSAGE } = await import("../functions/support-message.mjs");

let calls, resendStatus, resendThrows, logged;
const realLog = console.log;
const realError = console.error;
const realWarn = console.warn;
beforeEach(() => {
  store.clear();
  calls = [];
  logged = [];
  resendStatus = 200;
  resendThrows = false;
  limiterDown = false;
  console.log = (...a) => logged.push(a.join(" "));
  console.error = (...a) => logged.push(a.join(" "));
  console.warn = (...a) => logged.push(a.join(" "));
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (resendThrows) throw new Error("network down");
    return new Response(resendStatus >= 400 ? '{"message":"provider detail that must not leak"}' : "{}", { status: resendStatus });
  };
});
test.afterEach(() => { console.log = realLog; console.error = realError; console.warn = realWarn; });

const good = { email: "reader@example.org", message: "The compile button does nothing after the update.", topic: "moderntex", page: "/moderntex/", website: "", t: 8000 };
const post = (body, headers = {}, ip = "203.0.113.9") => handler(new Request("https://purplelink.llc/.netlify/functions/support-message", {
  method: "POST",
  headers: { "Content-Type": "application/json", origin: "https://purplelink.llc", "x-nf-client-connection-ip": ip, ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body),
}));
const mails = () => calls.filter((c) => c.url === "https://api.resend.com/emails").map((c) => JSON.parse(c.opts.body));

test("a valid message is sent to Ben with Reply-To set to the visitor", async () => {
  const res = await post(good);
  assert.equal(res.status, 204);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].opts.headers.Authorization, "Bearer re_dummy");
  const [mail] = mails();
  assert.deepEqual(mail.to, ["ben@purplelink.llc"]);
  assert.equal(mail.reply_to, "reader@example.org");
  assert.equal(mail.from, "Purplelink LLC <orders@purplelink.llc>");
  assert.equal(mail.subject, "Support: ModernTex");
  assert.equal(mail.html, undefined);
  assert.match(mail.text, /^From: reader@example\.org\nTopic: ModernTex\nPage: \/moderntex\/\n\nThe compile button does nothing after the update\./);
});

test("no topic means General; the subject never carries visitor text", async () => {
  await post({ ...good, topic: undefined, message: "Subject: injected\nBcc: x@example.org\nplease read this" });
  const [mail] = mails();
  assert.equal(mail.subject, "Support: General");
  assert.equal(mail.bcc, undefined);
  assert.equal(mail.subject.includes("injected"), false);
});

test("an unknown topic is refused with its field", async () => {
  for (const topic of ["nope", "<b>x</b>", ["moderntex"], 7, "__proto__", "constructor"]) {
    const res = await post({ ...good, topic });
    assert.equal(res.status, 400);
    assert.deepEqual(await res.json(), { error: "invalid_topic", field: "topic" });
  }
  assert.equal(calls.length, 0);
});

test("control characters are stripped and markup stays literal text", async () => {
  await post({ ...good, message: "Line one\u0000\u0007\u202e\r\nLine two <script>alert(1)</script>\u2028end" });
  const [mail] = mails();
  assert.equal(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u2028\u2029]/.test(mail.text), false);
  assert.ok(mail.text.includes("Line two <script>alert(1)</script>"));
  assert.equal(mail.html, undefined);
});

test("page is a clipped site path with no query string; a foreign page value is dropped", async () => {
  await post({ ...good, page: "/moderntex/?utm=x#top" });
  await post({ ...good, page: "https://evil.example/x" });
  await post({ ...good, page: "/" + "a".repeat(400) });
  const [a, b, c] = mails();
  assert.match(a.text, /Page: \/moderntex\/\n/);
  assert.equal(b.text.includes("Page:"), false);
  assert.ok(c.text.split("\n")[2].length <= "Page: ".length + 120);
});

test("a filled honeypot is answered 204 and sends nothing", async () => {
  const res = await post({ ...good, website: "https://spam.example" });
  assert.equal(res.status, 204);
  assert.equal(calls.length, 0);
  assert.equal(store.size, 0);
});

test("a form submitted in under three seconds, or with no timing, is refused", async () => {
  for (const t of [0, 2999, -5, "9000", null, undefined, NaN]) {
    const res = await post({ ...good, t });
    assert.equal(res.status, 400);
    assert.equal((await res.json()).error, "too_fast");
  }
  assert.equal((await post({ ...good, t: 3000 })).status, 204);
});

test("a bad email is refused with its field", async () => {
  for (const email of ["", "plain", "a@b", "a b@example.org", "a@example.org\nBcc: x@example.org", "<a@example.org>", "a@example.org,b@example.org", "x".repeat(300) + "@example.org", 42, null]) {
    const res = await post({ ...good, email });
    assert.equal(res.status, 400, String(email));
    assert.deepEqual(await res.json(), { error: "invalid_email", field: "email" });
  }
  assert.equal(calls.length, 0);
});

test("a message under 10 or over 5000 characters is refused", async () => {
  for (const message of ["", "short", "         x         ", 5, null]) {
    const res = await post({ ...good, message });
    assert.equal(res.status, 400);
    assert.deepEqual(await res.json(), { error: "message_short", field: "message" });
  }
  const long = await post({ ...good, message: "x".repeat(MAX_MESSAGE + 1) });
  assert.equal(long.status, 400);
  assert.deepEqual(await long.json(), { error: "message_long", field: "message" });
  assert.equal((await post({ ...good, message: "x".repeat(MAX_MESSAGE) })).status, 204);
});

test("bad JSON, arrays and a huge body are 400", async () => {
  for (const body of ["not json", "[]", "null", "5", "", JSON.stringify({ message: "x".repeat(30000) })]) {
    assert.equal((await post(body)).status, 400);
  }
  assert.equal(calls.length, 0);
});

test("a foreign Origin is refused before anything is read or sent", async () => {
  const res = await post(good, { origin: "https://evil.example" });
  assert.equal(res.status, 403);
  assert.equal(calls.length, 0);
  assert.equal(store.size, 0);
  const pre = await handler(new Request("https://purplelink.llc/.netlify/functions/support-message", { method: "OPTIONS", headers: { origin: "https://evil.example" } }));
  assert.equal(pre.status, 403);
  const ok = await handler(new Request("https://purplelink.llc/.netlify/functions/support-message", { method: "OPTIONS", headers: { origin: "https://www.purplelink.llc" } }));
  assert.equal(ok.status, 204);
  assert.equal(ok.headers.get("access-control-allow-origin"), "https://www.purplelink.llc");
});

test("GET is 405", async () => {
  const res = await handler(new Request("https://purplelink.llc/.netlify/functions/support-message"));
  assert.equal(res.status, 405);
});

test("one address gets five messages an hour, then 429; another address is unaffected", async () => {
  for (let i = 0; i < PER_IP_HOURLY; i++) assert.equal((await post(good, {}, "198.51.100.7")).status, 204);
  const res = await post(good, {}, "198.51.100.7");
  assert.equal(res.status, 429);
  assert.deepEqual(await res.json(), { error: "rate_limited" });
  assert.equal(mails().length, PER_IP_HOURLY);
  assert.equal((await post(good, {}, "198.51.100.8")).status, 204);
  const keys = [...store.keys()].filter((k) => k.startsWith("rate-limits/"));
  assert.ok(keys.length >= 3);
  assert.equal(keys.some((k) => k.includes("198.51.100")), false);
});

test("the daily per-address cap holds when the hour counter is fresh", async () => {
  const day = new Date().toISOString().slice(0, 10);
  const { createHash } = await import("node:crypto");
  const digest = createHash("sha256").update(`${day}|pl-signal|198.51.100.20`).digest("hex").slice(0, 16);
  store.set(`rate-limits/rl:support-day:${day}:${digest}`, String(PER_IP_DAILY));
  assert.equal((await post(good, {}, "198.51.100.20")).status, 429);
  assert.equal(calls.length, 0);
});

test("the global daily cap stops every address", async () => {
  const day = new Date().toISOString().slice(0, 10);
  store.set(`rate-limits/rl:support-all:${day}`, String(GLOBAL_DAILY));
  assert.equal((await post(good, {}, "192.0.2.1")).status, 429);
  assert.equal(calls.length, 0);
});

test("if the limiter cannot be read the message is not sent", async () => {
  limiterDown = true;
  const res = await post(good);
  assert.equal(res.status, 502);
  assert.equal(calls.length, 0);
});

test("a Resend refusal is 502 with generic text and no provider detail", async () => {
  resendStatus = 422;
  const res = await post(good);
  assert.equal(res.status, 502);
  const text = await res.text();
  assert.deepEqual(JSON.parse(text), { error: "send_failed" });
  assert.equal(text.includes("provider detail"), false);
});

test("a network failure to Resend is 502; a missing API key is 502", async () => {
  resendThrows = true;
  assert.equal((await post(good)).status, 502);
  resendThrows = false;
  delete env.RESEND_API_KEY;
  try { assert.equal((await post(good, {}, "192.0.2.77")).status, 502); } finally { env.RESEND_API_KEY = "re_dummy"; }
});

test("nothing is stored but counters, and nothing logs the message or the address", async () => {
  const secret = "my-very-private-sentence-12345";
  const addr = "private.person@example.org";
  await post({ ...good, email: addr, message: `${secret} and more words` });
  resendStatus = 500;
  await post({ ...good, email: addr, message: `${secret} and more words` });
  limiterDown = true;
  await post({ ...good, email: addr, message: `${secret} and more words` });
  const everything = [...store.entries()].flat().join("\n");
  assert.equal(everything.includes(secret), false);
  assert.equal(everything.includes("private.person"), false);
  assert.equal([...store.keys()].every((k) => k.startsWith("rate-limits/")), true);
  const log = logged.join("\n");
  assert.ok(log.length > 0, "failures are logged by code");
  assert.equal(log.includes(secret), false);
  assert.equal(log.includes("private.person"), false);
});
