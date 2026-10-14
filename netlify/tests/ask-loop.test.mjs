// The ask loop: trial day on the Buy path, the count-only signal function and its owner read path, the why-not page,
// the trial-download poll, and the two optional ModernTex checkout questions.
// Run with: node --experimental-test-module-mocks --test netlify/tests/ask-loop.test.mjs
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    setJSON: async (k, v) => { stores.set(`${name}/${k}`, v); },
    list: async ({ prefix = "" } = {}) => ({
      blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/${prefix}`)).map((k) => ({ key: k.slice(name.length + 1) })),
    }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = {
  env: { get: (k) => (k === "STRIPE_SECRET_KEY" ? "sk_test_dummy" : k === "STATS_TOKEN" ? "tok-123" : k.startsWith("STRIPE_PRICE_") ? "price_dummy" : undefined) },
};

const { default: checkout, cleanTrialDay, cleanAppSource } = await import("../functions/checkout.mjs");
const { default: signal, MAX_BODY_BYTES, DAILY_LIMIT } = await import("../functions/signal.mjs");
const { default: stats } = await import("../functions/stats.mjs");
const { isoWeek, tdBucket, parseTd, ALLOWLIST } = await import("../lib/signals.mjs");

const read = (p) => readFileSync(new URL(`../../${p}`, import.meta.url), "utf8");
beforeEach(() => stores.clear());

// ---- checkout: trial day and app source ----------------------------------------------------------------
let ipN = 0;
async function createSession(body) {
  let captured = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    captured = new URLSearchParams(opts.body);
    return new Response(JSON.stringify({ id: "cs_test_x", url: "https://checkout.stripe.com/pay/cs_test_x" }), { status: 200 });
  };
  try {
    const res = await checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
      method: "POST",
      headers: { "content-type": "application/json", "x-nf-client-connection-ip": `198.51.100.${++ipN}` },
      body: JSON.stringify(body),
    }));
    assert.equal(res.status, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
  return captured;
}

test("td of 3 and utm_source moderntex-app reach the session metadata, first-touch metadata is kept", async () => {
  const touch = { s: "moderntex-app", m: "trial-screen", c: "expired", l: "/moderntex/buy/", d: "2026-10-14" };
  const p = await createSession({ product: "moderntex", td: "3", src: "moderntex-app", attr: { first: touch, last: touch } });
  assert.equal(p.get("metadata[trial_day]"), "3");
  assert.equal(p.get("metadata[app_source]"), "moderntex-app");
  assert.equal(JSON.parse(p.get("metadata[attr_first]")).s, "moderntex-app");
});

test("td accepts 0, 30 and unknown, as a number or a string", async () => {
  for (const [sent, stored] of [[0, "0"], ["0", "0"], [30, "30"], ["30", "30"], ["unknown", "unknown"], [7, "7"]]) {
    assert.equal((await createSession({ product: "moderntex", td: sent })).get("metadata[trial_day]"), stored);
  }
});

test("td=abc, -1, 31, 99, 03, 3.5, a very long value and non-strings are dropped, and the session is still created", async () => {
  for (const bad of ["abc", "-1", "31", "99", "03", "3.5", "1e1", " 3", "3 ", "UNKNOWN", "x".repeat(5000), -1, 99, 3.5, null, {}, [3], true]) {
    const p = await createSession({ product: "moderntex", td: bad });
    assert.equal(p.get("metadata[trial_day]"), null, `td=${String(bad).slice(0, 20)}`);
  }
  assert.equal(cleanTrialDay("30"), "30");
  assert.equal(cleanTrialDay("31"), "");
});

test("app_source keeps only a short lowercase tag; trial_day and app_source are ModernTex only", async () => {
  for (const bad of ["MODERNTEX-APP", "a b", "x".repeat(41), "<s>", 5, null]) {
    assert.equal((await createSession({ product: "moderntex", src: bad })).get("metadata[app_source]"), null);
  }
  assert.equal(cleanAppSource("moderntex-app"), "moderntex-app");
  const p = await createSession({ product: "keyfeel", td: "3", src: "moderntex-app" });
  assert.equal(p.get("metadata[trial_day]"), null);
  assert.equal(p.get("metadata[app_source]"), null);
});

// ---- checkout: role and field questions -----------------------------------------------------------------
function fields(p) {
  const out = [];
  for (let i = 0; p.get(`custom_fields[${i}][key]`); i++) {
    const opts = [];
    for (let j = 0; p.get(`custom_fields[${i}][dropdown][options][${j}][value]`); j++) {
      opts.push({ label: p.get(`custom_fields[${i}][dropdown][options][${j}][label]`), value: p.get(`custom_fields[${i}][dropdown][options][${j}][value]`) });
    }
    out.push({ key: p.get(`custom_fields[${i}][key]`), label: p.get(`custom_fields[${i}][label][custom]`), optional: p.get(`custom_fields[${i}][optional]`), type: p.get(`custom_fields[${i}][type]`), opts });
  }
  return out;
}

test("ModernTex checkout has heard, role and field: three optional dropdowns within Stripe's limits", async () => {
  const f = fields(await createSession({ product: "moderntex" }));
  assert.deepEqual(f.map((x) => x.key), ["heard", "role", "field"]);
  assert.ok(f.length <= 3);
  for (const x of f) {
    assert.equal(x.optional, "true");
    assert.equal(x.type, "dropdown");
    assert.ok(x.label.length <= 50, `label ${x.label}`);
    assert.ok(x.opts.length >= 2 && x.opts.length <= 200);
    for (const o of x.opts) {
      assert.ok(o.label.length <= 100 && o.value.length <= 100);
      assert.match(o.value, /^[a-z0-9]+$/);
    }
    assert.equal(new Set(x.opts.map((o) => o.value)).size, x.opts.length);
  }
  const by = Object.fromEntries(f.map((x) => [x.key, x]));
  assert.equal(by.role.label, "Which best describes you?");
  assert.deepEqual(by.role.opts.map((o) => o.label), ["Graduate student", "Faculty or researcher", "Industry researcher", "Other"]);
  assert.equal(by.field.label, "Your main field?");
  assert.deepEqual(by.field.opts.map((o) => o.label), ["Computer science or engineering", "Mathematics, statistics or physics", "Economics or finance", "Social sciences", "Humanities", "Life sciences", "Other"]);
});

test("other products keep only the heard question (or none), with no role or field", async () => {
  for (const product of ["keyfeel", "outbound-veil", "app-suite", "moderntex-seats", "paper-review-standard", "sheet-submission"]) {
    const body = product === "moderntex-seats" ? { product, seats: 5 } : { product };
    const f = fields(await createSession(body));
    assert.ok(!f.some((x) => x.key === "role" || x.key === "field"), product);
  }
});

// ---- signal function ---------------------------------------------------------------------------------------
const post = (body, ip = "203.0.113.5", headers = {}) => signal(new Request("https://purplelink.llc/.netlify/functions/signal", {
  method: "POST",
  headers: { "user-agent": "Mozilla/5.0", "x-nf-client-connection-ip": ip, ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body),
}));
const counters = () => [...stores.keys()].filter((k) => k.startsWith("signals/"));

test("GET and other methods are 405", async () => {
  for (const method of ["GET", "PUT", "DELETE"]) {
    const r = await signal(new Request("https://purplelink.llc/.netlify/functions/signal", { method }));
    assert.equal(r.status, 405);
  }
});

test("every allowlisted value is counted and answered 204", async () => {
  let n = 0;
  for (const [kind, values] of Object.entries(ALLOWLIST)) {
    for (const value of values) {
      const r = await post({ kind, value }, `203.0.113.${100 + n++}`);
      assert.equal(r.status, 204);
    }
  }
  assert.equal(counters().length, 12);
});

test("values outside the allowlist, wrong kinds and malformed bodies are rejected and store nothing", async () => {
  const bad = [
    { kind: "whynot", value: "paper" }, { kind: "trialpoll", value: "price" }, { kind: "other", value: "price" },
    { kind: "whynot" }, { value: "price" }, { kind: "whynot", value: "Price" }, { kind: "whynot", value: ["price"] },
    { kind: "__proto__", value: "price" }, { kind: "whynot", value: "price", td: "abc" }, { kind: "whynot", value: "price", td: 31 },
    { kind: "whynot", value: "price", td: -1 }, { kind: "whynot", value: "price", td: "9".repeat(500) }, [], "nope", "{bad json",
  ];
  for (const b of bad) assert.equal((await post(typeof b === "string" ? b : b)).status, 400, JSON.stringify(b));
  assert.equal(counters().length, 0);
});

test("a body over 2 KB is refused, by header and by actual length", async () => {
  const big = { kind: "whynot", value: "price", pad: "x".repeat(MAX_BODY_BYTES + 10) };
  assert.equal((await post(big)).status, 413);
  assert.equal((await post({ kind: "whynot", value: "price" }, "203.0.113.5", { "content-length": String(MAX_BODY_BYTES + 1) })).status, 413);
  assert.equal(counters().length, 0);
});

test("per-IP daily limit: the answer after the limit is 429 and not counted; another address still counts", async () => {
  for (let i = 0; i < DAILY_LIMIT; i++) assert.equal((await post({ kind: "trialpoll", value: "paper" }, "203.0.113.7")).status, 204);
  assert.equal((await post({ kind: "trialpoll", value: "paper" }, "203.0.113.7")).status, 429);
  assert.equal((await post({ kind: "trialpoll", value: "paper" }, "203.0.113.8")).status, 204);
  const key = counters().find((k) => k.endsWith("/trialpoll/paper"));
  assert.equal(stores.get(key), String(DAILY_LIMIT + 1));
});

test("no PII is stored: no IP, user agent or timestamp in any key or value", async () => {
  await post({ kind: "whynot", value: "price", td: 5 }, "203.0.113.77", { "user-agent": "Mozilla/5.0 SecretBrowser/9" });
  const all = JSON.stringify([...stores.entries()]);
  assert.ok(!all.includes("203.0.113.77"), "IP in storage");
  assert.ok(!all.includes("SecretBrowser"), "user agent in storage");
  // the counter store holds only week/kind/value[/bucket] keys with integer values
  for (const k of counters()) {
    assert.match(k, /^signals\/\d{4}-W\d{2}\/(whynot|trialpoll)\/[a-z-]+(\/(0-3|4-7|8\+|unknown))?$/);
    assert.match(stores.get(k), /^\d+$/);
  }
  // the limiter key is a hash, not the address
  const rl = [...stores.keys()].filter((k) => k.startsWith("rate-limits/rl:signal:"));
  assert.equal(rl.length, 1);
  assert.match(rl[0], /^rate-limits\/rl:signal:\d{4}-\d{2}-\d{2}:[0-9a-f]{16}$/);
});

test("bots are answered 204 and not counted", async () => {
  assert.equal((await post({ kind: "whynot", value: "price" }, "203.0.113.9", { "user-agent": "Googlebot/2.1" })).status, 204);
  assert.equal(counters().length, 0);
});

test("whynot is keyed by ISO week, kind, value and trial-day bucket; trialpoll has no bucket", async () => {
  const week = isoWeek();
  const sends = [["whynot", "price", 0], ["whynot", "price", 3], ["whynot", "price", 4], ["whynot", "price", 7], ["whynot", "price", 8], ["whynot", "price", 30], ["whynot", "price", "unknown"], ["whynot", "price", undefined]];
  let n = 0;
  for (const [kind, value, td] of sends) await post({ kind, value, td }, `203.0.113.${150 + n++}`);
  await post({ kind: "trialpoll", value: "thesis", td: 2 }, "203.0.113.200");
  assert.equal(stores.get(`signals/${week}/whynot/price/0-3`), "2");
  assert.equal(stores.get(`signals/${week}/whynot/price/4-7`), "2");
  assert.equal(stores.get(`signals/${week}/whynot/price/8+`), "2");
  assert.equal(stores.get(`signals/${week}/whynot/price/unknown`), "2");
  assert.equal(stores.get(`signals/${week}/trialpoll/thesis`), "1");
});

test("isoWeek and tdBucket edge cases", () => {
  assert.equal(isoWeek(new Date("2026-10-14T12:00:00Z")), "2026-W42");
  assert.equal(isoWeek(new Date("2026-01-01T00:00:00Z")), "2026-W01");
  assert.equal(isoWeek(new Date("2027-01-01T00:00:00Z")), "2026-W53");
  assert.equal(isoWeek(new Date("2026-10-12T00:00:00Z")), "2026-W42"); // Monday
  assert.equal(isoWeek(new Date("2026-10-11T23:59:59Z")), "2026-W41"); // Sunday
  assert.deepEqual(["0", "3", "4", "7", "8", "30", "unknown", null].map((v) => tdBucket(v)), ["0-3", "0-3", "4-7", "4-7", "8+", "8+", "unknown", "unknown"]);
  assert.equal(parseTd(undefined), null);
  assert.equal(parseTd("x"), "bad");
});

// ---- owner read path -----------------------------------------------------------------------------------------
const getStats = (qs, headers = {}) => stats(new Request(`https://purplelink.llc/.netlify/functions/stats?${qs}`, { headers }));

test("stats?section=signals needs the owner token", async () => {
  assert.equal((await getStats("section=signals")).status, 401);
  assert.equal((await getStats("section=signals", { authorization: "Bearer wrong" })).status, 401);
  assert.equal((await getStats("section=signals&token=wrong")).status, 401);
});

test("stats?section=signals returns weekly counts, whynot by trial-day bucket", async () => {
  await post({ kind: "whynot", value: "price", td: 2 }, "203.0.113.31");
  await post({ kind: "whynot", value: "price", td: 9 }, "203.0.113.32");
  await post({ kind: "whynot", value: "deciding" }, "203.0.113.33");
  await post({ kind: "trialpoll", value: "replace-overleaf" }, "203.0.113.34");
  await post({ kind: "trialpoll", value: "replace-overleaf" }, "203.0.113.35");
  stores.set(`signals/${isoWeek()}/whynot/bogus`, "9"); // unknown keys are ignored
  const r = await getStats("section=signals&weeks=4", { authorization: "Bearer tok-123" });
  assert.equal(r.status, 200);
  const body = await r.json();
  const w = body.signals[isoWeek()];
  assert.deepEqual(w.whynot.price, { total: 2, "0-3": 1, "8+": 1 });
  assert.deepEqual(w.whynot.deciding, { total: 1, unknown: 1 });
  assert.equal(w.trialpoll["replace-overleaf"], 2);
  assert.ok(!("bogus" in w.whynot));
});

// ---- pages and scripts ---------------------------------------------------------------------------------------
test("buy.js sends a valid td and utm_source, drops an invalid td, and starts checkout for the app link", () => {
  const src = read("site/moderntex/buy/buy.js");
  function run(search) {
    const sent = [];
    const btn = { disabled: false, addEventListener() {} };
    const sandbox = {
      URLSearchParams, JSON, Promise,
      document: { getElementById: (id) => (id === "checkout-btn" ? btn : null) },
      window: { location: { search, assign() {} } },
      fetch: (u, o) => { sent.push(JSON.parse(o.body)); return new Promise(() => {}); },
    };
    vm.runInNewContext(src, sandbox);
    return sent;
  }
  const ok = run("?utm_source=moderntex-app&utm_medium=trial-screen&utm_campaign=expired&td=3");
  assert.deepEqual(ok, [{ product: "moderntex", td: "3", src: "moderntex-app" }]);
  for (const bad of ["abc", "-1", "99", "x".repeat(500), "3.5"]) {
    const s = run(`?utm_source=moderntex-app&td=${bad}`);
    assert.equal(s.length, 1);
    assert.equal(s[0].td, undefined, `td=${bad.slice(0, 10)}`);
  }
  assert.deepEqual(run("?utm_source=moderntex-app&td=unknown")[0].td, "unknown");
  assert.equal(run("?utm_source=newsletter").length, 0, "other visits do not auto-start");
  assert.equal(run("").length, 0);
});

test("/moderntex/not-now/ is noindex, has no ad or analytics script and no inline script or style, and posts to signal", () => {
  const html = read("site/moderntex/not-now/index.html");
  assert.match(html, /<meta name="robots" content="noindex/);
  assert.ok(!/adsbygoogle|googlesyndication|analytics\.js/.test(html));
  assert.ok(!/\sstyle=/.test(html));
  assert.ok(!/<script(?![^>]*\ssrc=)[^>]*>/.test(html.replace(/<script[^>]*src=[^>]*><\/script>/g, "")), "no inline script");
  assert.match(html, /\/moderntex\/not-now\/not-now\.js/);
  assert.match(html, /href="\/moderntex\/"/);
  assert.match(html, /href="\/moderntex\/start\/"/);
  assert.ok(!/<link rel="canonical"/.test(html));
  assert.ok(!read("site/sitemap.xml").includes("/moderntex/not-now/"));
});

test("not-now.js sends only the why code and a valid td, once per tab", () => {
  const src = read("site/moderntex/not-now/not-now.js");
  function run(search, seen = {}) {
    const sent = [];
    const sandbox = {
      URLSearchParams, JSON, Number, Promise, Blob: class {},
      document: { getElementById: () => ({ textContent: "" }) },
      sessionStorage: { getItem: (k) => seen[k] ?? null, setItem: (k, v) => { seen[k] = v; } },
      window: { location: { search } },
      navigator: {},
      fetch: (u, o) => { sent.push({ u, body: JSON.parse(o.body) }); return Promise.resolve({ ok: true }); },
    };
    vm.runInNewContext(src, sandbox);
    return sent;
  }
  assert.deepEqual(run("?why=price&td=3")[0], { u: "/.netlify/functions/signal", body: { kind: "whynot", value: "price", td: 3 } });
  assert.deepEqual(run("?why=other&td=unknown")[0].body, { kind: "whynot", value: "other", td: "unknown" });
  assert.deepEqual(run("?why=price&td=99")[0].body, { kind: "whynot", value: "price" });
  assert.equal(run("?why=nope&td=3").length, 0);
  assert.equal(run("?td=3").length, 0);
  assert.equal(run("?why=price", { pl_whynot_sent: "price" }).length, 0);
});

test("the trial poll on /moderntex/: seven radio choices, Send and Skip, hidden until a download click, no inline style", () => {
  const html = read("site/moderntex/index.html");
  const forms = html.match(/<form class="ask-poll"[\s\S]*?<\/form>/g) || [];
  assert.ok(forms.length >= 1);
  const labels = ["Write a paper", "Write a thesis or dissertation", "Work with co-authors", "Replace Overleaf", "Course notes or lecture slides", "Just looking", "Something else"];
  const codes = ALLOWLIST.trialpoll;
  for (const f of forms) {
    assert.match(f, /^<form class="ask-poll" data-ask-poll hidden/);
    assert.equal((f.match(/type="radio"/g) || []).length, 7);
    labels.forEach((l, i) => { assert.ok(f.includes(`<span>${l}</span>`), l); assert.ok(f.includes(`value="${codes[i]}"`), codes[i]); });
    assert.match(f, />Send</);
    assert.match(f, />Skip</);
    assert.ok(!/type="email"|name="email"/.test(f));
    assert.ok(!/\sstyle=/.test(f));
    assert.match(f, /<legend/);
  }
  assert.match(html, /\/moderntex\/poll\.js/);
  const js = read("site/moderntex/poll.js");
  assert.match(js, /Thanks\. Counted\./);
  assert.match(js, /kind: "trialpoll"/);
  assert.ok(!/body:[^\n]*email/i.test(js), "the poll sends no email");
});

test("the poll values the page offers are the ones signal accepts", () => {
  const js = read("site/moderntex/poll.js");
  const codes = JSON.parse(js.match(/var CODES = (\[.*?\]);/)[1]);
  assert.deepEqual(codes, ALLOWLIST.trialpoll);
  const nn = read("site/moderntex/not-now/not-now.js");
  assert.deepEqual(JSON.parse(nn.match(/var WHY = (\[.*?\]);/)[1]), ALLOWLIST.whynot);
});
