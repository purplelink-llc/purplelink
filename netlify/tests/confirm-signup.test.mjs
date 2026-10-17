// Double opt-in for the digest (subscribe.mjs) and the researcher checklist (checklist-signup.mjs):
// nothing is stored or sent until the signed link is confirmed with a POST. Resend and Blobs are stubbed.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/confirm-signup.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

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

const subscribe = (await import("../functions/subscribe.mjs")).default;
const checklist = (await import("../functions/checklist-signup.mjs")).default;
const confirm = (await import("../functions/confirm-signup.mjs")).default;
const { signConfirmToken, verifyConfirmToken, CONFIRM_LINK_SECONDS } = await import("../lib/confirm-token.mjs");

const fn = "https://purplelink.llc/.netlify/functions";
let sent;
let resendOk;
beforeEach(() => {
  blobs.clear();
  sent = [];
  resendOk = true;
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    if (u.startsWith("https://api.resend.com/")) {
      sent.push(JSON.parse(init.body));
      return new Response("{}", { status: resendOk ? 200 : 500 });
    }
    return new Response("not a pdf", { status: 404 }); // the checklist PDF fetch: send without the attachment
  };
});

const post = (name, body, ip = "203.0.113.1") => (name === "subscribe" ? subscribe : checklist)(new Request(`${fn}/${name}`, {
  method: "POST", headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip }, body: JSON.stringify(body),
}));
const linkIn = (mail) => mail.text.match(/confirm-signup\?t=(\S+)/)[1];
const confirmPost = (t) => confirm(new Request(`${fn}/confirm-signup`, {
  method: "POST", body: new URLSearchParams({ t: decodeURIComponent(t) }), headers: { "content-type": "application/x-www-form-urlencoded" },
}));

test("digest: a signup stores nothing and emails a confirmation link to that address", async () => {
  const res = await post("subscribe", { email: "new@example.com" });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true, confirm: true });
  assert.equal(blobs.has("subscribers/new@example.com"), false);
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].to, ["new@example.com"]);
  assert.match(sent[0].text, /Confirm|confirm/);
});

test("digest: GET on the link changes nothing; the POST adds the subscriber once, with the referral", async () => {
  blobs.set("referral-index/abc1234567", "referrer@example.com");
  await post("subscribe", { email: "new@example.com", ref: "abc1234567" });
  const t = linkIn(sent[0]);
  const page = await confirm(new Request(`${fn}/confirm-signup?t=${t}`));
  assert.equal(page.status, 200);
  assert.ok((await page.text()).includes('method="post"'));
  assert.equal(blobs.has("subscribers/new@example.com"), false, "a scanner's GET must not confirm");

  const done = await confirmPost(t);
  assert.equal(done.status, 200);
  const rec = JSON.parse(blobs.get("subscribers/new@example.com"));
  assert.equal(rec.tier, "free");
  assert.equal(rec.token, createHmac("sha256", SECRET).update("new@example.com").digest("hex"), "unsubscribe token as the mailer signs it");
  assert.ok(rec.confirmedAt);
  assert.ok(blobs.has("referral-credits/abc1234567:new@example.com"));
  const again = await confirmPost(t);
  assert.equal(again.status, 200);
});

test("digest: an address already subscribed gets the same answer, no email, and is unaffected", async () => {
  const before = JSON.stringify({ email: "old@example.com", tier: "paid", referralCode: "r", token: "x", stripe_customer_id: "cus_1" });
  blobs.set("subscribers/old@example.com", before);
  const res = await post("subscribe", { email: "old@example.com" });
  assert.deepEqual(await res.json(), { ok: true, confirm: true });
  assert.equal(sent.length, 0);
  assert.equal(blobs.get("subscribers/old@example.com"), before);
});

test("digest: a failed confirmation email is a 502 and stores nothing", async () => {
  resendOk = false;
  const res = await post("subscribe", { email: "new@example.com" });
  assert.equal(res.status, 502);
  assert.equal(blobs.has("subscribers/new@example.com"), false);
});

test("tokens: expired, tampered, wrong-kind and unsigned links confirm nothing", async () => {
  const good = signConfirmToken("digest-confirm", { e: "x@example.com", r: "" }, SECRET);
  const old = signConfirmToken("digest-confirm", { e: "x@example.com", r: "" }, SECRET, Math.floor(Date.now() / 1000) - CONFIRM_LINK_SECONDS - 5);
  const [enc, exp, sig] = good.split(".");
  const swapped = `${Buffer.from(JSON.stringify({ e: "victim@example.com", r: "" })).toString("base64url")}.${exp}.${sig}`;
  for (const t of [old, swapped, "garbage", "", createHmac("sha256", SECRET).update("x@example.com").digest("hex")]) {
    assert.equal((await confirmPost(encodeURIComponent(t))).status, 400, t.slice(0, 20));
  }
  assert.equal(blobs.size, 0);
  assert.equal(verifyConfirmToken("checklist-confirm", good, SECRET), null, "kind is part of the signature");
  assert.ok(enc.length > 0);
});

test("checklist: a signup stores nothing and sends no PDF, only a confirmation link", async () => {
  const res = await post("checklist-signup", { email: "r@example.com", page: "/guides/x/" });
  assert.deepEqual(await res.json(), { ok: true, confirm: true });
  assert.equal(blobs.has("researcher-list/r@example.com"), false);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].attachments, undefined);
  assert.equal(sent[0].headers, undefined, "no unsubscribe header: the address is not on the list yet");
  assert.match(sent[0].subject, /Confirm/);
});

test("checklist: confirming with POST stores the record and sends the checklist with an unsubscribe link", async () => {
  await post("checklist-signup", { email: "r@example.com", page: "/guides/x/" });
  const t = linkIn(sent[0]);
  const get = await confirm(new Request(`${fn}/confirm-signup?t=${t}`));
  assert.equal(get.status, 200);
  assert.equal(blobs.has("researcher-list/r@example.com"), false, "GET changes nothing");
  assert.equal(sent.length, 1);

  const res = await confirmPost(t);
  assert.equal(res.status, 200);
  const rec = JSON.parse(blobs.get("researcher-list/r@example.com"));
  assert.equal(rec.source, "/guides/x/");
  assert.ok(rec.confirmedAt && rec.unsubscribeToken);
  assert.equal(sent.length, 2);
  assert.equal(sent[1].subject, "Your submission checklist");
  assert.ok(sent[1].headers["List-Unsubscribe"].includes(rec.unsubscribeToken));

  await confirmPost(t); // a double click does not send it twice
  assert.equal(sent.length, 2);
});

test("checklist: a confirmed address asking again within a day gets 'already', no email", async () => {
  await post("checklist-signup", { email: "r@example.com" });
  await confirmPost(linkIn(sent[0]));
  sent.length = 0;
  const res = await post("checklist-signup", { email: "r@example.com" });
  assert.deepEqual(await res.json(), { ok: true, already: true });
  assert.equal(sent.length, 0);
});

test("checklist: if the checklist email fails at confirm, nobody is kept", async () => {
  await post("checklist-signup", { email: "r@example.com" });
  const t = linkIn(sent[0]);
  resendOk = false;
  const res = await confirmPost(t);
  assert.equal(res.status, 502);
  assert.equal(blobs.has("researcher-list/r@example.com"), false);
});
