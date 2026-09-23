// Tests for vitae-license.mjs: key recovery by email and the limited billing portal.
// Stripe, Resend and Netlify Blobs are stubbed; a throwaway Ed25519 key signs the keys.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/vitae-license.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, verify } from "node:crypto";

const blobs = new Map();
mock.module("@netlify/blobs", {
  exports: {
    getStore: (name) => ({
      get: async (k) => blobs.get(`${name}/${k}`) ?? null,
      set: async (k, v) => { blobs.set(`${name}/${k}`, v); },
    }),
  },
});

const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const PEM = privateKey.export({ type: "pkcs8", format: "pem" });
const env = { STRIPE_SECRET_KEY: "sk_test_dummy", VITAE_LICENSE_PRIVATE_KEY: PEM, RESEND_API_KEY: "re_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const { default: handler } = await import("../functions/vitae-license.mjs");

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

function post(body, ip = "198.51.100.7") {
  return handler(new Request("https://purplelink.llc/.netlify/functions/vitae-license", {
    method: "POST",
    headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip },
    body: JSON.stringify(body),
  }));
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

test("recover reports a failed send instead of claiming success", async () => {
  stripe["/customers?email="] = { data: [{ id: "cus_1" }] };
  stripe["/subscriptions?customer=cus_1"] = { data: [plusSub("sub_live", "active", "vitae-plus-annual", "year")] };
  resendStatus = 500;
  assert.equal((await post({ recover: "buyer@example.com" })).status, 502);
});

test("manage opens the portal with the limited configuration only", async () => {
  blobs.set("vitae-plus/0123456789abcdef", JSON.stringify({ subscription: "sub_live", plan: "monthly" }));
  stripe["/subscriptions/sub_live"] = plusSub("sub_live", "active");
  const res = await post({ manage: "0123456789abcdef" });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).url, "https://billing.stripe.com/p/session/test");
  const config = calls.find((c) => c.url.endsWith("/billing_portal/configurations"));
  const params = new URLSearchParams(config.opts.body);
  assert.equal(params.get("features[customer_update][enabled]"), "false");
  assert.equal(params.get("features[subscription_update][enabled]"), "false");
  assert.equal(params.get("features[subscription_cancel][mode]"), "at_period_end");
  const session = calls.find((c) => c.url.endsWith("/billing_portal/sessions"));
  assert.equal(new URLSearchParams(session.opts.body).get("configuration"), "bpc_limited");
  // Created once, then reused.
  await post({ manage: "0123456789abcdef" }, "198.51.100.8");
  assert.equal(calls.filter((c) => c.url.endsWith("/billing_portal/configurations")).length, 1);
});

test("manage refuses rather than opening an unrestricted portal", async () => {
  blobs.set("vitae-plus/0123456789abcdef", JSON.stringify({ subscription: "sub_live", plan: "monthly" }));
  stripe["/subscriptions/sub_live"] = plusSub("sub_live", "active");
  const base = globalThis.fetch;
  globalThis.fetch = async (url, opts) =>
    String(url).endsWith("/billing_portal/configurations") ? new Response("{}", { status: 400 }) : base(url, opts);
  const res = await post({ manage: "0123456789abcdef" });
  assert.equal(res.status, 502);
  assert.equal(calls.filter((c) => c.url.endsWith("/billing_portal/sessions")).length, 0);
});
