// Trial Buy path: the d=<0-7> trial-day tag, the Suite sentence beside the ModernTex buy buttons,
// and the refund line on the Stripe Checkout page.
// Run with: node --experimental-test-module-mocks --test netlify/tests/trial-buy-path.test.mjs
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { test, mock } from "node:test";
import assert from "node:assert/strict";

const blobsModule = { getStore: () => ({ get: async () => null, set: async () => {} }) };
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = {
  env: { get: (k) => (k === "STRIPE_SECRET_KEY" ? "sk_test_dummy" : k.startsWith("STRIPE_PRICE_") ? "price_dummy" : undefined) },
};
const { default: handler } = await import("../functions/checkout.mjs");

const read = (p) => readFileSync(new URL(`../../${p}`, import.meta.url), "utf8");
const analyticsSrc = read("site/analytics.js");
const checkoutSrc = read("netlify/functions/checkout.mjs");

// ---- analytics.js: trial day -------------------------------------------------------------------------
function arrive(search) {
  const store = {};
  const sandbox = {
    navigator: { sendBeacon: () => true },
    Blob: class { constructor(p) { this.p = p; } },
    URL, URLSearchParams, Date, JSON, Math, String, RegExp, Object,
    window: {},
    document: { referrer: "", addEventListener() {} },
    location: { search, pathname: "/moderntex/", host: "purplelink.llc", hostname: "purplelink.llc" },
    localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; }, removeItem: (k) => { delete store[k]; } },
  };
  sandbox.window = sandbox;
  vm.runInNewContext(analyticsSrc, sandbox);
  return store.pl_attr ? JSON.parse(store.pl_attr) : null;
}

test("from=trial&d=3 is recorded as source from:trial with campaign trial-day-3", () => {
  const a = arrive("?from=trial&d=3");
  assert.equal(a.first.s, "from:trial");
  assert.equal(a.first.c, "trial-day-3");
  assert.equal(a.last.c, "trial-day-3");
});

test("every day 0 to 7 is accepted", () => {
  for (let d = 0; d <= 7; d++) assert.equal(arrive(`?from=trial&d=${d}`).first.c, `trial-day-${d}`);
});

test("anything but a single digit 0 to 7 is ignored, and from:trial is still recorded", () => {
  for (const bad of ["8", "-1", "3.5", "03", "1e1", "abc", "", " 3", "3 ", "9999", "%203", "3;drop"]) {
    const a = arrive(`?from=trial&d=${encodeURIComponent(bad)}`);
    assert.equal(a.first.s, "from:trial", `source for d=${bad}`);
    assert.ok(!a.first.c, `d=${bad} must be ignored`);
  }
});

test("d without from=trial records nothing", () => {
  assert.equal(arrive("?d=3"), null);
  const a = arrive("?from=other&d=3");
  assert.equal(a.first.s, "from:other");
  assert.ok(!a.first.c);
});

test("an explicit utm_campaign wins over the trial day", () => {
  const a = arrive("?from=trial&d=2&utm_campaign=spring");
  assert.equal(a.first.c, "spring");
});

test("checkout keeps the campaign field, so the trial day reaches the Stripe order", async () => {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    captured = opts.body;
    return new Response(JSON.stringify({ id: "cs_test_d", url: "https://checkout.stripe.com/pay/cs_test_d" }), { status: 200 });
  };
  try {
    const touch = { s: "from:trial", c: "trial-day-5", l: "/moderntex/buy/", d: "2026-10-12" };
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.71" },
      body: JSON.stringify({ product: "moderntex", attr: { first: touch, last: touch } }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  const meta = JSON.parse(new URLSearchParams(captured).get("metadata[attr_first]"));
  assert.equal(meta.s, "from:trial");
  assert.equal(meta.c, "trial-day-5");
});

test("the link tag (utm_content) is stored with the arrival and reaches the Stripe order", async () => {
  assert.equal(arrive("?utm_source=macmenubar&utm_content=keyfeel-directory-261024").first.t, "keyfeel-directory-261024");
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    captured = opts.body;
    return new Response(JSON.stringify({ id: "cs_test_t", url: "https://checkout.stripe.com/pay/cs_test_t" }), { status: 200 });
  };
  try {
    const touch = { s: "macmenubar", t: "keyfeel-directory-261024<script>", d: "2026-10-24" };
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.72" },
      body: JSON.stringify({ product: "keyfeel", attr: { first: touch, last: touch } }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  const meta = JSON.parse(new URLSearchParams(captured).get("metadata[attr_first]"));
  assert.equal(meta.s, "macmenubar");
  assert.equal(meta.t, "keyfeel-directory-261024script");
});

test("with every field at its cap the attribution still fits Stripe's 500 characters and keeps the link tag", async () => {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    captured = opts.body;
    return new Response(JSON.stringify({ id: "cs_test_m", url: "https://checkout.stripe.com/pay/cs_test_m" }), { status: 200 });
  };
  const big = (n) => "x".repeat(n);
  try {
    const touch = { s: big(60), m: big(40), c: big(80), r: big(80), l: "/" + big(119), d: "2026-10-24", g: 1, t: big(60) };
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": "203.0.113.73" },
      body: JSON.stringify({ product: "keyfeel", attr: { first: touch, last: touch } }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  for (const k of ["metadata[attr_first]", "metadata[attr_last]"]) {
    const raw = new URLSearchParams(captured).get(k);
    assert.ok(raw.length <= 500, `${k} is ${raw.length} characters`);
    const meta = JSON.parse(raw);
    assert.equal(meta.t, big(60));
    assert.equal(meta.s, big(60));
    assert.ok(meta.l.length < 120);
  }
});

// ---- buy page -----------------------------------------------------------------------------------------
test("/moderntex/buy/ is noindex, loads analytics before its own script, and auto-starts only with from=trial", () => {
  const html = read("site/moderntex/buy/index.html");
  assert.match(html, /<meta name="robots" content="noindex/);
  assert.ok(html.indexOf("/analytics.js") < html.indexOf("/moderntex/buy/buy.js"), "analytics.js must wrap fetch first");
  assert.ok(!/\sstyle=/.test(html), "no inline styles");
  const js = read("site/moderntex/buy/buy.js");
  assert.match(js, /get\("from"\) === "trial"/);
  assert.match(js, /product: "moderntex"/);
});

// ---- Suite sentence -----------------------------------------------------------------------------------
const suiteCents = Number(checkoutSrc.match(/"app-suite":\s+\{ amount: (\d+),/)[1]);
const suitePrice = `$${(suiteCents / 100).toFixed(2)}`;

test("the Suite sentence sits right under the ModernTex buy buttons and uses the catalog price", () => {
  const html = read("site/moderntex/index.html");
  const at = html.indexOf('id="checkout-btn"');
  const sentence = html.match(/<p class="buy-suite">(.*?)<\/p>/s);
  assert.ok(sentence, "buy-suite paragraph present");
  assert.ok(html.indexOf('class="buy-suite"') > at && html.indexOf('class="buy-suite"') - at < 800, "directly under the buttons");
  assert.ok(sentence[1].includes(`${suitePrice} once`), `says ${suitePrice}`);
  assert.ok(sentence[1].includes('href="/suite/"'));
});

test("the ModernTex success page and buy page name the Suite at the catalog price", () => {
  for (const p of ["site/moderntex/success/index.html", "site/moderntex/buy/index.html"]) {
    const html = read(p);
    assert.match(html, /Mac Suite<\/a>/, p);
    assert.ok(html.includes(`${suitePrice} once`), `${p} says ${suitePrice}`);
    assert.ok(!/\$(\d+\.\d\d) once/.test(html.replace(`${suitePrice} once`, "")), `${p} names no other once-price`);
  }
});

// ---- Refund line --------------------------------------------------------------------------------------
async function sessionParams(product, ip) {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    captured = opts.body;
    return new Response(JSON.stringify({ id: "cs_test_r", url: "https://checkout.stripe.com/pay/cs_test_r" }), { status: 200 });
  };
  try {
    const res = await handler(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": ip },
      body: JSON.stringify({ product }),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  return new URLSearchParams(captured);
}

const TERMS = read("site/terms/index.html");
function termsRefund(heading) {
  const sec = TERMS.split("<h2>").find((s) => s.startsWith(`${heading}: additional terms`));
  const li = sec.match(/<li><strong>Refunds\.<\/strong>(.*?)<\/li>/s)[1];
  return li.replace(/<[^>]+>/g, "").replace(/&#39;|&rsquo;/g, "'").replace(/\s+/g, " ").trim();
}
const APPS = {
  moderntex: "ModernTex", "outbound-veil": "Outbound Veil", legroom: "Legroom", keyfeel: "Keyfeel",
  tapefolio: "Tapefolio", panely: "Panely", summonly: "Summonly", "app-suite": "Mac Suite",
};

let n = 80;
for (const [product, heading] of Object.entries(APPS)) {
  test(`${product}: the checkout page carries the refund sentence from /terms/ word for word`, async () => {
    const p = await sessionParams(product, `203.0.113.${n++}`);
    const msg = p.get("custom_text[submit][message]");
    assert.ok(msg, "refund line present");
    assert.equal(msg, termsRefund(heading));
    assert.ok(msg.length <= 1200, "within Stripe's 1200-character limit");
  });
}

test("products whose terms differ get no refund line (nothing invented)", async () => {
  for (const [i, product] of ["paper-review-standard", "kit-clip", "moderntex-seats", "vitae-plus-monthly"].entries()) {
    if (product === "moderntex-seats") continue; // needs a seat count; no no-reason policy in the terms either way
    const p = await sessionParams(product, `203.0.113.${120 + i}`);
    assert.equal(p.get("custom_text[submit][message]"), null, product);
  }
});
