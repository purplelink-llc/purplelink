// Tests for vitae-license.mjs: key recovery by email and the limited billing portal.
// Stripe, Resend and Netlify Blobs are stubbed; a throwaway Ed25519 key signs the keys.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/vitae-license.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, verify } from "node:crypto";

const blobs = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => blobs.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { blobs.set(`${name}/${k}`, v); },
  }),
};
// `exports` on newer Node, `namedExports` on Node 22.
mock.module("@netlify/blobs", { exports: blobsModule, namedExports: blobsModule });

const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const PEM = privateKey.export({ type: "pkcs8", format: "pem" });
const env = { STRIPE_SECRET_KEY: "sk_test_dummy", VITAE_LICENSE_PRIVATE_KEY: PEM, RESEND_API_KEY: "re_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: handler, portalToken, verifyPortalToken } = await import("../functions/vitae-license.mjs");

const NOW = Math.floor(Date.now() / 1000);
const plusSub = (id, status, product = "vitae-plus-monthly", interval = "month") => ({
  id, status, metadata: { product }, current_period_end: NOW + 20 * 86400,
  customer: "cus_1", items: { data: [{ price: { recurring: { interval } } }] },
});

let calls;
let stripe;   // path -> JSON body
let resendStatus;

beforeEach(() => {
  blobs.clear();
  calls = [];
  resendStatus = 200;
  stripe = {};
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    if (u.startsWith("https://api.resend.com/")) return new Response("{}", { status: resendStatus });
    if (u.startsWith("https://api.stripe.com/v1")) {
      const path = u.slice("https://api.stripe.com/v1".length);
      if (path === "/billing_portal/configurations") return new Response(JSON.stringify({ id: "bpc_limited" }), { status: 200 });
      if (path === "/billing_portal/sessions") {
        return new Response(JSON.stringify({ url: "https://billing.stripe.com/p/session/test" }), { status: 200 });
      }
      for (const [prefix, body] of Object.entries(stripe)) {
        if (path.startsWith(prefix)) return new Response(JSON.stringify(body), { status: 200 });
      }
      return new Response(JSON.stringify({ data: [] }), { status: 200 });
    }
    throw new Error(`Unexpected fetch to ${u}`);
  };
});

// Background work (context.waitUntil) is collected and awaited, as Netlify would finish it.
let pending = [];
async function post(body, ip = "198.51.100.7") {
  const res = await handler(new Request("https://purplelink.llc/.netlify/functions/vitae-license", {
    method: "POST",
    headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip },
    body: JSON.stringify(body),
  }), { waitUntil: (p) => pending.push(p) });
  await Promise.all(pending.splice(0));
  return res;
}

function get(pathAndQuery, ip = "198.51.100.9") {
  return handler(new Request(`https://purplelink.llc/.netlify/functions/vitae-license${pathAndQuery}`, {
    headers: { "x-nf-client-connection-ip": ip },
  }), {});
}

const resendCalls = () => calls.filter((c) => c.url.startsWith("https://api.resend.com/"));

function keyFromEmail(call) {
  const text = JSON.parse(call.opts.body).text;
  const m = text.match(/VP2-[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/);
  assert.ok(m, "the email contains a key");
  return m[0];
}

test("recover emails a verifiable key for a live subscription, to that address only", async () => {
  stripe["/customers?email="] = { data: [{ id: "cus_1" }] };
  stripe["/subscriptions?customer=cus_1"] = { data: [plusSub("sub_live", "trialing")] };
  const res = await post({ recover: "Buyer@Example.com" });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "sent_if_found" });
  const sent = resendCalls();
  assert.equal(sent.length, 1);
  assert.deepEqual(JSON.parse(sent[0].opts.body).to, ["Buyer@Example.com"]);
  const key = keyFromEmail(sent[0]);
  const [payload, sig] = key.slice(4).split(".");
  assert.ok(verify(null, Buffer.from(payload, "base64url"), publicKey, Buffer.from(sig, "base64url")));
  const decoded = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
  assert.deepEqual(Object.keys(decoded), ["exp", "iat", "id", "p", "plan", "v"]);
  assert.equal(decoded.plan, "monthly");
  // The mapping is restored so the recovered key can refresh.
  assert.ok(blobs.get(`vitae-plus/${decoded.id}`)?.includes("sub_live"));
});

test("recover answers the same and sends nothing when nothing matches", async () => {
  stripe["/customers?email="] = { data: [{ id: "cus_1" }] };
  stripe["/subscriptions?customer=cus_1"] = { data: [plusSub("sub_old", "canceled"), plusSub("sub_x", "active", "digest-pro")] };
  const res = await post({ recover: "nobody@example.com" });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "sent_if_found" });
  assert.equal(resendCalls().length, 0);
});

test("recover rejects a malformed address and limits requests per address", async () => {
  assert.equal((await post({ recover: "not-an-email" })).status, 400);
  for (let i = 0; i < 3; i++) assert.equal((await post({ recover: "a@b.co" }, `198.51.100.${20 + i}`)).status, 200);
  assert.equal((await post({ recover: "A@B.co" }, "198.51.100.40")).status, 429, "the per-address limit ignores case");
});

test("recover answers the same even when the email fails", async () => {
  stripe["/customers?email="] = { data: [{ id: "cus_1" }] };
  stripe["/subscriptions?customer=cus_1"] = { data: [plusSub("sub_live", "active", "vitae-plus-annual", "year")] };
  resendStatus = 500;
  const res = await post({ recover: "buyer@example.com" });
  assert.equal(res.status, 200, "no status difference reveals a subscriber");
  assert.deepEqual(await res.json(), { status: "sent_if_found" });
});

test("manage emails a portal link to the Stripe customer's own address, not the caller", async () => {
  blobs.set("vitae-plus/0123456789abcdef", JSON.stringify({ subscription: "sub_live", plan: "monthly" }));
  stripe["/subscriptions/sub_live"] = plusSub("sub_live", "active");
  stripe["/customers/cus_1"] = { id: "cus_1", email: "owner@example.com" };
  const res = await post({ manage: "0123456789abcdef" });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "emailed" });
  const mail = JSON.parse(resendCalls()[0].opts.body);
  assert.deepEqual(mail.to, ["owner@example.com"]);
  const link = mail.text.match(/https:\/\/purplelink\.llc\/\.netlify\/functions\/vitae-license\/portal\/\S+/)[0];
  assert.equal(new URL(link).search, "", "the token is in the path, never the query");
  assert.equal(calls.filter((c) => c.url.endsWith("/billing_portal/sessions")).length, 0, "no portal until the link is used");

  // Opening the link creates a limited portal session and redirects to it.
  const opened = await get(new URL(link).pathname.replace("/.netlify/functions/vitae-license", ""));
  assert.equal(opened.status, 302);
  assert.equal(opened.headers.get("location"), "https://billing.stripe.com/p/session/test");
  const config = calls.find((c) => c.url.endsWith("/billing_portal/configurations"));
  const params = new URLSearchParams(config.opts.body);
  assert.equal(params.get("features[customer_update][enabled]"), "false");
  assert.equal(params.get("features[subscription_update][enabled]"), "false");
  assert.equal(params.get("features[subscription_cancel][mode]"), "at_period_end");
  const session = calls.find((c) => c.url.endsWith("/billing_portal/sessions"));
  assert.equal(new URLSearchParams(session.opts.body).get("configuration"), "bpc_limited");
  assert.equal(new URLSearchParams(session.opts.body).get("customer"), "cus_1");
});

test("portal tokens are bound to the customer, signed and expire", () => {
  const now = Math.floor(Date.now() / 1000);
  const t = portalToken("cus_ABC123", now + 60, PEM);
  assert.equal(verifyPortalToken(t, PEM, now), "cus_ABC123");
  assert.equal(verifyPortalToken(t, PEM, now + 61), null, "expired");
  const [c, e, sig] = t.split(".");
  assert.equal(verifyPortalToken(`cus_OTHER99.${e}.${sig}`, PEM, now), null, "other customer");
  assert.equal(verifyPortalToken(`${c}.${Number(e) + 1000}.${sig}`, PEM, now), null, "extended expiry");
  const otherPem = generateKeyPairSync("ed25519").privateKey.export({ type: "pkcs8", format: "pem" });
  assert.equal(verifyPortalToken(t, otherPem, now), null, "other secret");
  assert.equal(verifyPortalToken("garbage", PEM, now), null);
});

test("a bad or expired portal link goes to the help page and opens nothing", async () => {
  const res = await get("/portal/cus_ABC123.1000000000.bad");
  assert.equal(res.status, 302);
  assert.equal(res.headers.get("location"), "https://purplelink.llc/vitae/plus/manage/");
  assert.equal(calls.filter((c) => c.url.includes("billing_portal")).length, 0);
});

test("the portal refuses rather than opening an unrestricted session", async () => {
  const base = globalThis.fetch;
  globalThis.fetch = async (url, opts) =>
    String(url).endsWith("/billing_portal/configurations") ? new Response("{}", { status: 400 }) : base(url, opts);
  const token = portalToken("cus_ABC123", Math.floor(Date.now() / 1000) + 600, PEM);
  const res = await get(`/portal/${encodeURIComponent(token)}`);
  assert.equal(res.headers.get("location"), "https://purplelink.llc/vitae/plus/manage/");
  assert.equal(calls.filter((c) => c.url.endsWith("/billing_portal/sessions")).length, 0);
});

test("manage emails each subscriber at most 3 times a day", async () => {
  blobs.set("vitae-plus/0123456789abcdef", JSON.stringify({ subscription: "sub_live", plan: "monthly" }));
  stripe["/subscriptions/sub_live"] = plusSub("sub_live", "active");
  stripe["/customers/cus_1"] = { id: "cus_1", email: "owner@example.com" };
  for (let i = 0; i < 3; i++) assert.equal((await post({ manage: "0123456789abcdef" }, `198.51.100.${60 + i}`)).status, 200);
  assert.equal((await post({ manage: "0123456789abcdef" }, "198.51.100.70")).status, 429);
  assert.equal(resendCalls().length, 3);
});
