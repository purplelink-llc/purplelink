// The Undershelf waitlist (undershelf-waitlist.mjs, docs/designs/undershelf-waitlist.md): double opt-in, the same
// answer whether or not an address is on the list, stateless unsubscribe that suppresses the address, and the
// checklist confirmation unchanged. Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/undershelf-waitlist.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const blobs = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => blobs.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { blobs.set(`${name}/${k}`, v); },
    setJSON: async (k, v) => { blobs.set(`${name}/${k}`, v); },
    delete: async (k) => { blobs.delete(`${name}/${k}`); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const SECRET = "unit-test-secret";
process.env.SUBSCRIBE_SECRET = SECRET;
process.env.RESEND_API_KEY = "re_dummy";
globalThis.Netlify = { env: { get: (k) => process.env[k] } };

const waitlistMod = await import("../functions/undershelf-waitlist.mjs");
const waitlist = waitlistMod.default;
const { cleanFields, suppressionKey, unsubscribeToken } = waitlistMod;
const checklist = (await import("../functions/checklist-signup.mjs")).default;
const confirm = (await import("../functions/confirm-signup.mjs")).default;
const { signConfirmToken, CONFIRM_LINK_SECONDS } = await import("../lib/confirm-token.mjs");

const fn = "https://purplelink.llc/.netlify/functions";
let sent;
let resendOk;
beforeEach(() => {
  blobs.clear();
  sent = [];
  resendOk = true;
  globalThis.fetch = async (url, init = {}) => {
    if (String(url).startsWith("https://api.resend.com/")) {
      sent.push(JSON.parse(init.body));
      return new Response("{}", { status: resendOk ? 200 : 500 });
    }
    return new Response("not a pdf", { status: 404 });
  };
});

const post = (body, { ip = "203.0.113.1", origin } = {}) => waitlist(new Request(`${fn}/undershelf-waitlist`, {
  method: "POST",
  headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip, ...(origin ? { origin } : {}) },
  body: typeof body === "string" ? body : JSON.stringify(body),
}));
const linkIn = (mail) => mail.text.match(/confirm-signup\?t=(\S+)/)[1];
const confirmReq = (t, method = "POST") => confirm(new Request(`${fn}/confirm-signup${method === "GET" ? `?t=${t}` : ""}`, {
  method,
  ...(method === "POST" ? { body: new URLSearchParams({ t: decodeURIComponent(t) }), headers: { "content-type": "application/x-www-form-urlencoded" } } : {}),
}));
const unsub = (email, token, method) => waitlist(new Request(
  `${fn}/undershelf-waitlist?u=${token}&e=${encodeURIComponent(email)}`, { method }));
const stored = (email) => blobs.get(`undershelf-waitlist/${email}`);
const suppressed = (email) => blobs.has(`undershelf-suppressed/${suppressionKey(email)}`);

test("sign-up sends one confirmation and stores nothing; the confirm POST stores the record once", async () => {
  const res = await post({ email: "Ann@Example.com", version: "carbon", page: "/undershelf/?x=1", utm: "nl-nov" });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  assert.equal(sent.length, 1);
  assert.match(sent[0].subject, /Undershelf waitlist/);
  assert.ok(sent[0].headers["List-Unsubscribe"].includes("undershelf-waitlist?u="));
  assert.equal(sent[0].headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
  assert.match(sent[0].text, /Atlanta, Georgia/);
  assert.equal(blobs.size, 2, "only the two rate-limit counters");

  const t = linkIn(sent[0]);
  const page = await confirmReq(t, "GET");
  assert.match(await page.text(), /the Undershelf waitlist/);
  assert.equal(stored("ann@example.com"), undefined, "GET changes nothing");

  const done = await confirmReq(t);
  assert.equal(done.status, 200);
  assert.match(await done.text(), /You are on the Undershelf waitlist/);
  const rec = JSON.parse(stored("ann@example.com"));
  assert.equal(rec.version, "carbon");
  assert.equal(rec.page, "/undershelf/");
  assert.equal(rec.utm, "nl-nov");
  assert.ok(rec.confirmedAt);

  const again = await confirmReq(t);
  assert.equal(again.status, 200);
  assert.equal(JSON.parse(stored("ann@example.com")).confirmedAt, rec.confirmedAt, "confirming twice changes nothing");
  assert.equal(sent.length, 1, "confirming sends no email");
});

test("an address already on the list gets the same answer and no email", async () => {
  await post({ email: "bo@example.com" });
  await confirmReq(linkIn(sent[0]));
  const res = await post({ email: "bo@example.com" }, { ip: "203.0.113.9" });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  assert.equal(sent.length, 1);
});

test("honeypot, bad JSON, bad email, foreign origin, wrong method", async () => {
  const bot = await post({ email: "x@example.com", website: "spam.example" });
  assert.deepEqual(await bot.json(), { ok: true });
  assert.equal(sent.length, 0);
  assert.equal((await post("{not json")).status, 400);
  assert.equal((await (await post({ email: "nope" })).json()).error, "invalid_email");
  assert.equal((await post({ email: "c@example.com" }, { origin: "https://evil.example" })).status, 403);
  assert.equal((await waitlist(new Request(`${fn}/undershelf-waitlist`, { method: "GET" }))).status, 405);
  const pre = await waitlist(new Request(`${fn}/undershelf-waitlist`, { method: "OPTIONS", headers: { origin: "https://purplelink.llc" } }));
  assert.equal(pre.status, 204);
});

test("rate limit: the fourth try for one address in a day is refused", async () => {
  for (let i = 0; i < 3; i++) assert.equal((await post({ email: "d@example.com" }, { ip: `198.51.100.${i}` })).status, 200);
  assert.equal((await post({ email: "d@example.com" }, { ip: "198.51.100.99" })).status, 429);
});

test("Resend refusing gives 502 and keeps nothing", async () => {
  resendOk = false;
  const res = await post({ email: "e@example.com" });
  assert.equal(res.status, 502);
  assert.equal(stored("e@example.com"), undefined);
});

test("fields are cleaned on the server", () => {
  assert.deepEqual(cleanFields({ version: "gold", utm: "Bad Tag!", page: "//evil" }), { version: "unsure", utm: "", page: "" });
  assert.deepEqual(cleanFields({ version: "standard", utm: "a".repeat(65), page: "/undershelf/#x" }),
    { version: "standard", utm: "", page: "/undershelf/" });
});

test("confirmation tokens: other kinds, tampering and expiry are rejected", async () => {
  const forged = encodeURIComponent(signConfirmToken("checklist-confirm", { e: "f@example.com" }, "other-secret"));
  assert.equal((await confirmReq(forged)).status, 400);
  const old = signConfirmToken("undershelf-confirm", { e: "f@example.com", v: "standard" }, SECRET,
    Math.floor(Date.now() / 1000) - CONFIRM_LINK_SECONDS - 10);
  assert.equal((await confirmReq(encodeURIComponent(old))).status, 400);
  assert.equal(stored("f@example.com"), undefined);
});

test("unsubscribe: GET changes nothing, POST deletes and suppresses, works before confirming, bad token is harmless", async () => {
  await post({ email: "g@example.com" });
  const t = linkIn(sent[0]);
  await confirmReq(t);
  const token = unsubscribeToken("g@example.com", SECRET);

  const view = await unsub("g@example.com", token, "GET");
  assert.equal(view.status, 200);
  assert.ok(stored("g@example.com"), "GET does not unsubscribe (mail scanners)");

  assert.equal((await unsub("g@example.com", "0".repeat(64), "POST")).status, 400);
  assert.ok(stored("g@example.com"));

  assert.equal((await unsub("g@example.com", token, "POST")).status, 200);
  assert.equal(stored("g@example.com"), undefined);
  assert.ok(suppressed("g@example.com"));

  // a suppressed address gets the same answer, no email, and an old confirmation link does not re-add it
  const before = sent.length;
  assert.deepEqual(await (await post({ email: "g@example.com" }, { ip: "192.0.2.5" })).json(), { ok: true });
  assert.equal(sent.length, before);
  const re = await confirmReq(t);
  assert.match(await re.text(), /unsubscribed/);
  assert.equal(stored("g@example.com"), undefined);

  // from the confirmation email, before any record exists
  await unsub("h@example.com", unsubscribeToken("h@example.com", SECRET), "POST");
  assert.ok(suppressed("h@example.com"));
  assert.ok(![...blobs.keys()].some((k) => k.includes("h@example.com")), "no address kept in the suppression store");
});

test("regression: the checklist confirmation still works and shows its own text", async () => {
  const res = await checklist(new Request(`${fn}/checklist-signup`, {
    method: "POST", headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.50" },
    body: JSON.stringify({ email: "k@example.com", page: "/checklist/" }),
  }));
  assert.equal(res.status, 200);
  const page = await confirmReq(linkIn(sent[0]), "GET");
  assert.match(await page.text(), /submission checklist/);
});
