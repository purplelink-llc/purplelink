// First-touch attribution for direct visits (2026-10-28): a first visit with no campaign tag, outside referrer or ad
// click stores a placeholder (x: 1) with the landing page and date, a later tagged arrival replaces it, and checkout
// keeps the page and date. Before this, such orders carried no attribution at all.
// Run with: node --experimental-test-module-mocks --test netlify/tests/attribution-direct.test.mjs
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { test, mock } from "node:test";
import assert from "node:assert/strict";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {} }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: (k) => (k === "STRIPE_SECRET_KEY" ? "sk_test_dummy" : k.startsWith("STRIPE_PRICE_") ? "price_dummy" : undefined) } };
const { default: handler } = await import("../functions/checkout.mjs");
const analyticsSrc = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");

// One browser: the same storage across visits.
function browser() {
  const store = {};
  return {
    store,
    visit(path, search = "", referrer = "") {
      const sandbox = {
        navigator: { sendBeacon: () => true }, Blob: class { constructor(p) { this.p = p; } },
        URL, URLSearchParams, Date, JSON, Math, String, RegExp, Object, window: {},
        document: { referrer, addEventListener() {} },
        location: { search, pathname: path, host: "purplelink.llc", hostname: "purplelink.llc" },
        localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; }, removeItem: (k) => { delete store[k]; } },
      };
      sandbox.window = sandbox;
      vm.runInNewContext(analyticsSrc, sandbox);
      return { attr: store.pl_attr ? JSON.parse(store.pl_attr) : null, firstTouch: sandbox.window.plFirstTouch && sandbox.window.plFirstTouch() };
    },
  };
}

test("a direct first visit stores only the landing page and date, and reads as direct", () => {
  const b = browser();
  const { attr, firstTouch } = b.visit("/keyfeel/");
  assert.equal(attr.first.x, 1);
  assert.equal(attr.first.l, "/keyfeel/");
  assert.match(attr.first.d, /^\d{4}-\d\d-\d\d$/);
  assert.ok(!attr.first.s && !attr.first.r && !attr.first.g);
  assert.equal(attr.last, null);
  assert.equal(firstTouch, "direct");
});

test("a later tagged arrival replaces the direct placeholder, so the channel means what it did before", () => {
  const b = browser();
  b.visit("/keyfeel/");
  const { attr, firstTouch } = b.visit("/guides/x/", "", "https://www.google.com/");
  assert.equal(attr.first.r, "www.google.com");
  assert.ok(!attr.first.x);
  assert.equal(firstTouch, "www.google.com");
});

test("a tagged first touch is never replaced by a later direct visit", () => {
  const b = browser();
  b.visit("/moderntex/", "?utm_source=reddit&utm_campaign=x");
  const { attr } = b.visit("/moderntex/");
  assert.equal(attr.first.s, "reddit");
  assert.equal(attr.last.s, "reddit");
});

test("internal pages after a direct landing keep the landing page", () => {
  const b = browser();
  b.visit("/tools/latex-diff/");
  const { attr } = b.visit("/moderntex/", "", "https://purplelink.llc/tools/latex-diff/");
  assert.equal(attr.first.l, "/tools/latex-diff/");
});

test("checkout stores the direct placeholder's page and date, and drops the marker", async () => {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    captured = opts.body;
    return new Response(JSON.stringify({ id: "cs_test_direct", url: "https://checkout.stripe.com/pay/cs_test_direct" }), { status: 200 });
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.91" },
      body: JSON.stringify({ product: "keyfeel", attr: { first: { x: 1, l: "/keyfeel/", d: "2026-10-28" }, last: null } }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  const p = new URLSearchParams(captured);
  assert.deepEqual(JSON.parse(p.get("metadata[attr_first]")), { l: "/keyfeel/", d: "2026-10-28" });
  assert.equal(p.get("metadata[attr_last]"), null);
});
