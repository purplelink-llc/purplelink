// Unsubscribe and billing-portal links (security baseline 2026-10-16):
//  - a GET never unsubscribes or cancels; only a POST does (form button or RFC 8058 one-click)
//  - the old permanent portal token opens nothing; a portal opens only from an emailed 30-minute token
//  - the live-sheet portal action emails the order's address instead of returning a Stripe URL
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/unsubscribe-portal-links.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const blobs = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => blobs.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { blobs.set(`${name}/${k}`, v); },
    delete: async (k) => { blobs.delete(`${name}/${k}`); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const SECRET = "unit-test-secret";
process.env.SUBSCRIBE_SECRET = SECRET;
process.env.STRIPE_SECRET_KEY = "sk_test_dummy";
process.env.RESEND_API_KEY = "re_dummy";
globalThis.Netlify = { env: { get: (k) => process.env[k] } };

const unsubscribe = (await import("../functions/unsubscribe.mjs")).default;
const portal = (await import("../functions/subscription-portal.mjs")).default;
const liveSheet = (await import("../functions/live-sheet.mjs")).default;
const { signPortalToken, verifyPortalToken, PORTAL_LINK_SECONDS } = await import("../lib/portal-link.mjs");

const EMAIL = "paid@example.com";
const legacyToken = (email) => createHmac("sha256", SECRET).update(email).digest("hex");
const fn = "https://purplelink.llc/.netlify/functions";

let fetchCalls;
let sentMail;
beforeEach(() => {
  blobs.clear();
  fetchCalls = [];
  sentMail = [];
  blobs.set(`subscribers/${EMAIL}`, JSON.stringify({ email: EMAIL, tier: "paid", stripe_customer_id: "cus_1", stripe_subscription_id: "sub_1" }));
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    fetchCalls.push({ url: u, method: init.method || "GET", body: init.body });
    if (u.includes("api.resend.com")) { sentMail.push(JSON.parse(init.body)); return new Response("{}", { status: 200 }); }
    if (u.endsWith("/billing_portal/configurations")) return new Response(JSON.stringify({ id: "bpc_1" }), { status: 200 });
    if (u.endsWith("/billing_portal/sessions")) return new Response(JSON.stringify({ url: "https://billing.stripe.com/p/session/abc" }), { status: 200 });
    if (u.includes("/checkout/sessions/")) {
      return new Response(JSON.stringify({ customer: "cus_live", metadata: { product: "live-scholar" }, customer_details: { email: "buyer@example.com" } }), { status: 200 });
    }
    if (init.method === "DELETE" && u.includes("/subscriptions/")) return new Response("{}", { status: 200 });
    return new Response("{}", { status: 404 });
  };
});

const stripeCancels = () => fetchCalls.filter((c) => c.method === "DELETE");

test("GET unsubscribe shows a confirm page and changes nothing", async () => {
  const url = `${fn}/unsubscribe?email=${encodeURIComponent(EMAIL)}&token=${legacyToken(EMAIL)}`;
  const res = await unsubscribe(new Request(url));
  const html = await res.text();
  assert.equal(res.status, 200);
  assert.ok(html.includes('method="post"'));
  assert.ok(blobs.has(`subscribers/${EMAIL}`), "record still there");
  assert.equal(stripeCancels().length, 0, "no Stripe cancellation on GET");
});

test("POST from the confirm page unsubscribes and cancels the paid subscription", async () => {
  const body = new URLSearchParams({ email: EMAIL, token: legacyToken(EMAIL) });
  const res = await unsubscribe(new Request(`${fn}/unsubscribe`, { method: "POST", body, headers: { "content-type": "application/x-www-form-urlencoded" } }));
  assert.equal(res.status, 200);
  assert.equal(blobs.has(`subscribers/${EMAIL}`), false);
  assert.equal(stripeCancels().length, 1);
});

test("RFC 8058 one-click POST (token in the URL) works without a page", async () => {
  const url = `${fn}/unsubscribe?email=${encodeURIComponent(EMAIL)}&token=${legacyToken(EMAIL)}`;
  const res = await unsubscribe(new Request(url, { method: "POST", body: "List-Unsubscribe=One-Click", headers: { "content-type": "application/x-www-form-urlencoded" } }));
  assert.equal(res.status, 200);
  assert.equal(blobs.has(`subscribers/${EMAIL}`), false);
});

test("a bad token neither confirms nor unsubscribes, on GET or POST", async () => {
  const url = `${fn}/unsubscribe?email=${encodeURIComponent(EMAIL)}&token=${"0".repeat(64)}`;
  assert.equal((await unsubscribe(new Request(url))).status, 400);
  assert.equal((await unsubscribe(new Request(url, { method: "POST" }))).status, 400);
  assert.ok(blobs.has(`subscribers/${EMAIL}`));
  assert.equal((await unsubscribe(new Request(url, { method: "PUT" }))).status, 405);
});

test("the old permanent portal link opens no portal and offers the email flow", async () => {
  const url = `${fn}/subscription-portal?email=${encodeURIComponent(EMAIL)}&token=${legacyToken(EMAIL)}`;
  const res = await portal(new Request(url));
  const html = await res.text();
  assert.equal(res.status, 200);
  assert.ok(html.includes('name="email"') && html.includes('method="post"'));
  assert.equal(fetchCalls.filter((c) => c.url.includes("billing_portal")).length, 0);
});

test("the permanent unsubscribe token is not accepted as a portal token", async () => {
  const res = await portal(new Request(`${fn}/subscription-portal?t=${legacyToken(EMAIL)}`));
  assert.equal(res.status, 200);
  assert.equal(fetchCalls.filter((c) => c.url.includes("billing_portal")).length, 0);
});

test("requesting a link emails it to a paid subscriber, with the same answer for strangers", async () => {
  const ask = (email) => portal(new Request(`${fn}/subscription-portal`, {
    method: "POST", body: new URLSearchParams({ email }), headers: { "content-type": "application/x-www-form-urlencoded", "x-nf-client-connection-ip": "203.0.113.9" },
  }));
  const known = await ask(EMAIL);
  const knownHtml = await known.text();
  assert.equal(known.status, 200);
  assert.equal(sentMail.length, 1);
  assert.deepEqual(sentMail[0].to, [EMAIL]);
  assert.match(sentMail[0].text, /subscription-portal\?t=/);
  const unknown = await ask("nobody@example.com");
  assert.equal(unknown.status, 200);
  assert.equal(sentMail.length, 1, "no mail for an address without a paid subscription");
  assert.ok((await unknown.text()).includes("has a paid Daily Digest subscription"));
  assert.ok(knownHtml.includes("has a paid Daily Digest subscription"));
});

test("a free subscriber gets no portal link", async () => {
  blobs.set("subscribers/free@example.com", JSON.stringify({ email: "free@example.com", tier: "free" }));
  await portal(new Request(`${fn}/subscription-portal`, { method: "POST", body: new URLSearchParams({ email: "free@example.com" }) }));
  assert.equal(sentMail.length, 0);
});

test("a fresh emailed token opens a restricted portal; expired or tampered tokens do not", async () => {
  const token = signPortalToken("digest-portal", EMAIL, SECRET);
  const ok = await portal(new Request(`${fn}/subscription-portal?t=${encodeURIComponent(token)}`));
  assert.equal(ok.status, 303);
  assert.equal(ok.headers.get("location"), "https://billing.stripe.com/p/session/abc");
  const config = fetchCalls.find((c) => c.url.endsWith("/billing_portal/configurations"));
  assert.ok(String(config.body).includes("subscription_update%5D%5Benabled%5D=false"));
  const session = fetchCalls.find((c) => c.url.endsWith("/billing_portal/sessions"));
  assert.ok(String(session.body).includes("customer=cus_1") && String(session.body).includes("configuration=bpc_1"));

  const old = signPortalToken("digest-portal", EMAIL, SECRET, Math.floor(Date.now() / 1000) - PORTAL_LINK_SECONDS - 5);
  assert.equal((await portal(new Request(`${fn}/subscription-portal?t=${encodeURIComponent(old)}`))).status, 200);
  const [enc, exp, sig] = token.split(".");
  const other = Buffer.from("other@example.com").toString("base64url");
  assert.equal(verifyPortalToken("digest-portal", `${other}.${exp}.${sig}`, SECRET), null);
  assert.equal(verifyPortalToken("live-portal", token, SECRET), null, "kind is part of the signature");
  assert.equal(verifyPortalToken("digest-portal", token, "another-secret"), null);
  assert.equal(verifyPortalToken("digest-portal", token, SECRET), EMAIL);
  assert.ok(enc.length > 0);
});

test("live-sheet portal action emails the order address and returns no Stripe URL", async () => {
  const res = await liveSheet(new Request(`${fn}/live-sheet`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ action: "portal", session_id: "cs_live_abcdefghijk1234" }),
  }));
  const body = await res.json();
  assert.equal(res.status, 200);
  assert.equal(body.status, "emailed");
  assert.equal(body.url, undefined);
  assert.equal(fetchCalls.filter((c) => c.url.includes("billing_portal")).length, 0);
  assert.deepEqual(sentMail[0].to, ["buyer@example.com"]);
  const link = sentMail[0].text.match(/live-sheet\?portal=(\S+)/)[1];
  assert.equal(verifyPortalToken("live-portal", decodeURIComponent(link), SECRET), "cus_live");

  const open = await liveSheet(new Request(`${fn}/live-sheet?portal=${link}`));
  assert.equal(open.status, 303);
  assert.equal(open.headers.get("location"), "https://billing.stripe.com/p/session/abc");
  const bad = await liveSheet(new Request(`${fn}/live-sheet?portal=garbage`));
  assert.equal(bad.status, 303);
  assert.ok(bad.headers.get("location").includes("portal=expired"));
});
