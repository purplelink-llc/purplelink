// Tool-page offers: the tool-<slug> first-touch channel (analytics.js and stats.mjs), and the per-tool, count-only
// statistics (track.mjs writes, stats.mjs?section=tools reads).
// Run with: node --experimental-test-module-mocks --test netlify/tests/tool-offers.test.mjs

import { readFileSync, readdirSync, existsSync } from "node:fs";
import vm from "node:vm";
import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k, opts) => {
      const v = stores.get(`${name}/${k}`);
      if (v === undefined) return null;
      return opts && opts.type === "json" && typeof v === "string" ? JSON.parse(v) : v;
    },
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    setJSON: async (k, v) => { stores.set(`${name}/${k}`, structuredClone(v)); },
    list: async ({ prefix = "" } = {}) => ({
      blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/${prefix}`)).map((k) => ({ key: k.slice(name.length + 1) })),
    }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
globalThis.Netlify = { env: { get: (k) => (k === "STATS_TOKEN" ? "tok" : undefined) } };

const { default: track, DAILY_EVENT_LIMIT, MAX_BODY_BYTES } = await import("../functions/track.mjs");
const { default: stats, toolChannel, foldSource } = await import("../functions/stats.mjs");
const lib = await import("../lib/tool-counts.mjs");

const analyticsSrc = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");
const TODAY = new Date().toISOString().slice(0, 10);
beforeEach(() => stores.clear());

// ---- analytics.js ---------------------------------------------------------------------------------------------
function run({ search = "", referrer = "", pathname = "/moderntex/", fetchImpl, observer, offerEl } = {}) {
  const sent = [];
  const ls = {};
  const sandbox = {
    navigator: { sendBeacon: (_u, blob) => { sent.push(JSON.parse(blob.p[0])); return true; } },
    Blob: class { constructor(p) { this.p = p; } },
    URL, URLSearchParams, Date, JSON, Math, String, RegExp, Object, Promise,
    window: {},
    document: { referrer, addEventListener() {}, querySelector: (sel) => (sel === "[data-offer]" ? offerEl || null : null) },
    location: { search, pathname, host: "purplelink.llc", hostname: "purplelink.llc" },
    localStorage: { getItem: (k) => ls[k] ?? null, setItem: (k, v) => { ls[k] = v; }, removeItem: (k) => { delete ls[k]; } },
  };
  sandbox.window = sandbox;
  if (fetchImpl) sandbox.fetch = fetchImpl;
  if (observer) sandbox.IntersectionObserver = observer;
  vm.runInNewContext(analyticsSrc, sandbox);
  return { sent, sandbox };
}
const pv = (o) => run(o).sent.find((e) => e.t === "pageview");

test("analytics.js: utm_source=tool-<slug> is channel tool:<slug>", () => {
  assert.equal(pv({ search: "?utm_source=tool-latex-diff&utm_medium=tool&utm_campaign=moderntex" }).ft, "tool:latex-diff");
  assert.equal(pv({ search: "?utm_source=Tool-Bib-Validator&utm_medium=tool&utm_campaign=moderntex" }).ft, "tool:bib-validator");
  const { sandbox } = run({ search: "?utm_source=tool-transcript-cleaner&utm_medium=tool&utm_campaign=tapefolio" });
  assert.equal(sandbox.plFirstTouch(), "tool:transcript-cleaner");
});

test("analytics.js: a referrer or source that merely contains tool is not the tool channel", () => {
  for (const referrer of ["https://www.tools-for-x.com/", "https://tool-time.example/", "https://example.com/tool-latex-diff", "https://example.com/?utm_source=tool-latex-diff"]) {
    assert.ok(!pv({ referrer }).ft.startsWith("tool:"), referrer);
  }
  assert.equal(pv({ referrer: "https://tool-time.example/" }).ft, "tool-time.example");
  for (const q of ["?utm_source=tools", "?utm_source=mytool-x", "?utm_source=tool", "?utm_source=toolbox", "?utm_source=tool-"]) {
    assert.ok(!pv({ search: q }).ft.startsWith("tool:"), q);
  }
});

test("analytics.js: paid tags and every other channel read as before", () => {
  assert.equal(pv({ search: "?utm_source=google&utm_medium=cpc" }).ft, "paid:google");
  assert.equal(pv({ search: "?utm_source=tool-latex-diff&utm_medium=cpc" }).ft, "paid:tool-latex-diff");
  assert.equal(pv({ search: "?gclid=abc" }).ft, "paid:google");
  assert.equal(pv({ search: "?utm_source=linkedin&utm_medium=social" }).ft, "linkedin");
  assert.equal(pv({ referrer: "https://www.reddit.com/r/latex/" }).ft, "www.reddit.com");
  assert.equal(pv({ search: "?utm_source=newsletter" }).ft, "newsletter");
  assert.equal(pv({}).ft, "direct");
});

const fakeResponse = (status, ctype, body) => ({
  ok: status >= 200 && status < 300, status,
  headers: { get: (h) => (h.toLowerCase() === "content-type" ? ctype : null) },
  clone() { return fakeResponse(status, ctype, body); },
  json: async () => body,
});
async function outcomeFor(resp) {
  const { sent, sandbox } = run({ pathname: "/tools/latex-to-pdf/", fetchImpl: async () => resp });
  await sandbox.fetch("https://ben-ampel--purplelink-latextools-web.modal.run/compile", { method: "POST" });
  await new Promise((r) => setTimeout(r, 5));
  return { use: sent.filter((e) => e.t === "tool_use"), out: sent.filter((e) => e.t === "tool_outcome") };
}

test("analytics.js: a backend tool run sends tool_use once and one outcome: ok, error or limit", async () => {
  let r = await outcomeFor(fakeResponse(200, "application/pdf", null));
  assert.equal(r.use.length, 1); assert.deepEqual(r.out.map((e) => e.m), ["ok"]);
  r = await outcomeFor(fakeResponse(400, "application/json", { errors: [{ line: 1, message: "x" }] }));
  assert.deepEqual(r.out.map((e) => e.m), ["error"]);
  r = await outcomeFor(fakeResponse(500, "text/html", null));
  assert.deepEqual(r.out.map((e) => e.m), ["error"]);
  r = await outcomeFor(fakeResponse(429, "application/json", {}));
  assert.deepEqual(r.out.map((e) => e.m), ["limit"]);
  r = await outcomeFor(fakeResponse(413, "application/json", {}));
  assert.deepEqual(r.out.map((e) => e.m), ["limit"]);
  r = await outcomeFor(fakeResponse(422, "application/json", { error: "timeout" }));
  assert.deepEqual(r.out.map((e) => e.m), ["limit"]);
});

test("analytics.js: a network failure is an error outcome and still rejects for the tool's own code", async () => {
  const { sent, sandbox } = run({ pathname: "/tools/latex-to-pdf/", fetchImpl: async () => { throw new Error("offline"); } });
  await assert.rejects(sandbox.fetch("https://ben-ampel--purplelink-latextools-web.modal.run/compile"));
  await new Promise((r) => setTimeout(r, 5));
  assert.deepEqual(sent.filter((e) => e.t === "tool_outcome").map((e) => e.m), ["error"]);
});

test("analytics.js: other fetches send no outcome", async () => {
  const { sent, sandbox } = run({ fetchImpl: async () => fakeResponse(200, "application/json", {}) });
  await sandbox.fetch("/somewhere");
  await new Promise((r) => setTimeout(r, 5));
  assert.equal(sent.filter((e) => e.t === "tool_outcome").length, 0);
});

test("analytics.js: the offer card is counted once, when it is on screen", () => {
  const observed = [];
  let cb;
  class IO { constructor(f) { cb = f; this.f = f; } observe(el) { observed.push(el); } disconnect() { this.gone = true; } }
  const el = { getAttribute: (n) => (n === "data-offer" ? "moderntex" : null) };
  const { sent } = run({ pathname: "/tools/latex-diff/", observer: IO, offerEl: el });
  assert.equal(observed.length, 1);
  assert.equal(sent.filter((e) => e.t === "offer_view").length, 0);
  cb([{ isIntersecting: false }]);
  assert.equal(sent.filter((e) => e.t === "offer_view").length, 0);
  cb([{ isIntersecting: true }]);
  const views = sent.filter((e) => e.t === "offer_view");
  assert.equal(views.length, 1);
  assert.equal(views[0].m, "moderntex");
  assert.equal(views[0].p, "/tools/latex-diff/");
});

test("analytics.js: no offer card or no IntersectionObserver means no offer_view and no error", () => {
  assert.equal(run({}).sent.filter((e) => e.t === "offer_view").length, 0);
  const el = { getAttribute: () => "moderntex" };
  assert.equal(run({ offerEl: el }).sent.filter((e) => e.t === "offer_view").length, 0);
});

// ---- the allowlist -------------------------------------------------------------------------------------------
test("TOOL_SLUGS is exactly the tool directories that hold a page", () => {
  const dir = new URL("../../site/tools/", import.meta.url);
  const dirs = readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && existsSync(new URL(`${d.name}/index.html`, dir))).map((d) => d.name).sort();
  assert.deepEqual([...lib.TOOL_SLUGS].sort(), dirs);
});

test("toolSlugFromPath accepts only /tools/<allowlisted slug>/", () => {
  assert.equal(lib.toolSlugFromPath("/tools/latex-diff/"), "latex-diff");
  assert.equal(lib.toolSlugFromPath("/tools/latex-diff"), "latex-diff");
  for (const p of ["/tools/", "/tools/nope/", "/tools/latex-diff/extra", "/tools/../etc/", "/guides/latex-diff/", "tools/latex-diff/", "/tools/LATEX-DIFF/", "", null, undefined, "/tools/latex-diff/?x=1", "/tools/<b>/"]) {
    assert.equal(lib.toolSlugFromPath(p), "", String(p));
  }
});

// ---- track.mjs -----------------------------------------------------------------------------------------------
let ipN = 0;
const post = (body, { ip, headers = {} } = {}) => track(new Request("https://purplelink.llc/.netlify/functions/track", {
  method: "POST",
  headers: { "user-agent": "Mozilla/5.0", "x-nf-client-connection-ip": ip || `203.0.113.${++ipN % 250}`, ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body),
}), {});
const counts = (slug) => stores.get(`tool-counts/d/${TODAY}/${slug}`);
const countKeys = () => [...stores.keys()].filter((k) => k.startsWith("tool-counts/"));
const events = () => [...stores.keys()].filter((k) => k.startsWith("analytics/ev/"));

test("tool_use on an allowlisted tool page bumps runs and is still stored as an event, as before", async () => {
  await post({ t: "tool_use", p: "/tools/latex-diff/", h: "purplelink.llc", m: "/diff" });
  await post({ t: "tool_use", p: "/tools/latex-diff/", h: "purplelink.llc", m: "/diff" });
  assert.equal(counts("latex-diff").runs, 2);
  assert.equal(events().length, 2);
});

test("tool_use from a page that is not an allowlisted tool is stored but never counted per tool", async () => {
  await post({ t: "tool_use", p: "/tools/nope/" });
  await post({ t: "tool_use", p: "/blog/x/" });
  await post({ t: "tool_use", p: "/tools/" });
  assert.equal(countKeys().length, 0);
  assert.equal(events().length, 3);
});

test("outcomes ok, error and limit each bump their own counter; no event record is written", async () => {
  for (const m of ["ok", "ok", "error", "limit"]) await post({ t: "tool_outcome", p: "/tools/latex-to-pdf/", m });
  const c = counts("latex-to-pdf");
  assert.deepEqual({ ok: c.ok, error: c.error, limit: c.limit, runs: c.runs }, { ok: 2, error: 1, limit: 1, runs: 0 });
  assert.equal(events().length, 0);
});

test("offer_view and offer_click are counted by tool, and only for the four apps", async () => {
  await post({ t: "offer_view", p: "/tools/latex-diff/", m: "moderntex" });
  await post({ t: "offer_click", p: "/tools/latex-diff/", m: "moderntex" });
  await post({ t: "offer_view", p: "/tools/metadata-cleaner/", m: "outbound-veil" });
  assert.deepEqual([counts("latex-diff").offerViews, counts("latex-diff").offerClicks], [1, 1]);
  assert.equal(counts("metadata-cleaner").offerViews, 1);
  for (const m of ["keyfeel", "legroom", "MODERNTEX", "", "x".repeat(200), "<script>"]) {
    await post({ t: "offer_view", p: "/tools/latex-diff/", m });
    await post({ t: "offer_click", p: "/tools/latex-diff/", m });
  }
  assert.equal(counts("latex-diff").offerViews, 1);
  assert.equal(counts("latex-diff").offerClicks, 1);
});

test("allowlist rejection: bad slug, bad outcome, missing meta and wrong page drop the event and create no key", async () => {
  for (const p of ["/tools/evil/", "/tools/../x/", "/blog/", "/", "/tools/latex-diff/extra/", "/tools/%2e%2e/"]) {
    await post({ t: "tool_outcome", p, m: "ok" });
    await post({ t: "offer_view", p, m: "moderntex" });
  }
  for (const m of ["fine", "OK", "", undefined, 5, null, "ok ", "ok\n"]) await post({ t: "tool_outcome", p: "/tools/latex-diff/", m });
  assert.equal(countKeys().length, 0);
  assert.equal(events().length, 0);
});

test("free text never becomes a key or a value: only the allowlisted slug and numbers are stored", async () => {
  await post({ t: "tool_outcome", p: "/tools/latex-diff/", m: "ok", u: "secret@example.com", r: "evil.example", extra: "my thesis text" });
  assert.deepEqual(countKeys(), [`tool-counts/d/${TODAY}/latex-diff`]);
  const v = counts("latex-diff");
  assert.deepEqual(Object.keys(v).sort(), [...lib.COUNT_FIELDS].sort());
  for (const n of Object.values(v)) assert.ok(Number.isInteger(n) && n >= 0);
});

test("no PII: no IP, user agent, visitor id or timestamp anywhere in the stored count records", async () => {
  await post({ t: "tool_use", p: "/tools/latex-diff/" }, { ip: "198.51.100.77", headers: { "user-agent": "Mozilla/5.0 SecretBrowser/9" } });
  await post({ t: "tool_outcome", p: "/tools/latex-diff/", m: "ok" }, { ip: "198.51.100.77", headers: { "user-agent": "Mozilla/5.0 SecretBrowser/9" } });
  for (const k of countKeys()) {
    const dump = k + JSON.stringify(stores.get(k));
    assert.ok(!/198\.51\.100|SecretBrowser|vid|ts|cc/.test(JSON.stringify(stores.get(k))), dump);
    assert.ok(!dump.includes("198.51.100.77"));
  }
});

test("the same limits apply: body cap, per-address daily cap, Do Not Track and bots", async () => {
  const big = { t: "tool_outcome", p: "/tools/latex-diff/", m: "ok", pad: "x".repeat(MAX_BODY_BYTES) };
  await post(big);
  await post({ t: "tool_outcome", p: "/tools/latex-diff/", m: "ok" }, { headers: { "content-length": String(MAX_BODY_BYTES + 1) } });
  await post({ t: "tool_outcome", p: "/tools/latex-diff/", m: "ok" }, { headers: { dnt: "1" } });
  await post({ t: "tool_outcome", p: "/tools/latex-diff/", m: "ok" }, { headers: { "user-agent": "Googlebot/2.1" } });
  assert.equal(countKeys().length, 0);
  for (let i = 0; i < DAILY_EVENT_LIMIT + 25; i++) await post({ t: "offer_view", p: "/tools/latex-diff/", m: "moderntex" }, { ip: "198.51.100.9" });
  assert.equal(counts("latex-diff").offerViews, DAILY_EVENT_LIMIT);
  await post({ t: "offer_view", p: "/tools/latex-diff/", m: "moderntex" }, { ip: "198.51.100.10" });
  assert.equal(counts("latex-diff").offerViews, DAILY_EVENT_LIMIT + 1);
});

test("aggregation keys are d/<day>/<slug> and a slug's tools stay apart", async () => {
  await post({ t: "tool_use", p: "/tools/latex-diff/" });
  await post({ t: "tool_use", p: "/tools/bib-validator/" });
  assert.deepEqual(countKeys().sort(), [`tool-counts/d/${TODAY}/bib-validator`, `tool-counts/d/${TODAY}/latex-diff`]);
  assert.equal(lib.countKey("2026-10-14", "latex-diff"), "d/2026-10-14/latex-diff");
});

test("bumpToolCount refuses a slug or field that is not allowlisted", async () => {
  const store = blobsModule.getStore("tool-counts");
  assert.equal(await lib.bumpToolCount(store, TODAY, "../x", "runs"), false);
  assert.equal(await lib.bumpToolCount(store, TODAY, "latex-diff", "ip"), false);
  assert.equal(countKeys().length, 0);
});

// ---- stats.mjs: read path ------------------------------------------------------------------------------------
const get = (qs, token = "tok") => stats(new Request(`https://purplelink.llc/.netlify/functions/stats?${qs}${token ? `&token=${token}` : ""}`));
const put = (rec) => stores.set(`analytics/ev/${TODAY}/${String(stores.size).padStart(6, "0")}`, { ts: Date.now(), host: "purplelink.llc", ...rec });

test("section=tools needs the owner token", async () => {
  assert.equal((await get("section=tools", "")).status, 401);
  assert.equal((await get("section=tools", "wrong")).status, 401);
  const viaHeader = await stats(new Request("https://purplelink.llc/.netlify/functions/stats?section=tools", { headers: { authorization: "Bearer tok" } }));
  assert.equal(viaHeader.status, 200);
  assert.equal((await get("section=tools")).status, 200);
});

test("section=tools returns per-week, per-tool counts and the attributed funnel", async () => {
  for (const m of ["ok", "ok", "error", "limit"]) await post({ t: "tool_outcome", p: "/tools/latex-diff/", m });
  for (let i = 0; i < 3; i++) await post({ t: "tool_use", p: "/tools/latex-diff/" });
  await post({ t: "offer_view", p: "/tools/latex-diff/", m: "moderntex" });
  await post({ t: "offer_click", p: "/tools/latex-diff/", m: "moderntex" });
  stores.set(`tool-counts/d/${TODAY}/old-tool`, { runs: 99 }); // not an allowlisted slug: ignored

  put({ type: "pageview", path: "/moderntex/", ft: "tool:latex-diff", vid: "a" });
  put({ type: "pageview", path: "/moderntex/", ft: "tool-latex-diff", vid: "a" });   // a cached older script's label
  put({ type: "pageview", path: "/moderntex/", ft: "tool:latex-diff", vid: "b" });
  put({ type: "trial_download", path: "/moderntex/", meta: "moderntex", ft: "tool:latex-diff", vid: "a" });
  put({ type: "checkout_click", path: "/moderntex/", meta: "moderntex", ft: "tool:latex-diff", vid: "a" });
  put({ type: "pageview", path: "/moderntex/", ft: "tool:made-up", vid: "c" });
  put({ type: "pageview", path: "/moderntex/", ft: "direct", vid: "d" });
  put({ type: "checkout_click", path: "/moderntex/", meta: "__selftest", ft: "tool:latex-diff", vid: "z" });

  const body = await (await get("section=tools&weeks=8")).json();
  assert.equal(body.weeks.length >= 8, true);
  const week = Object.keys(body.tools)[0];
  const r = body.tools[week]["latex-diff"];
  assert.deepEqual({ runs: r.runs, ok: r.ok, error: r.error, limit: r.limit, offerViews: r.offerViews, offerClicks: r.offerClicks },
    { runs: 3, ok: 2, error: 1, limit: 1, offerViews: 1, offerClicks: 1 });
  assert.deepEqual(r.attributed, { pageviews: 3, dayVisitors: 2, trialDownloads: 1, checkoutClicks: 1 });
  assert.equal(body.tools[week]["(other)"].attributed.pageviews, 1);
  assert.equal(body.tools[week]["old-tool"], undefined);
  assert.ok(Array.isArray(body.notes) && body.notes.length >= 3);
});

test("section=tools clamps weeks and reads no event records for other sections", async () => {
  assert.equal((await get("section=tools&weeks=0")).status, 200);
  assert.equal((await get("section=tools&weeks=9999")).status, 200);
  assert.equal((await get("section=tools&weeks=abc")).status, 200);
  const body = await (await get("section=tools&weeks=9999")).json();
  assert.ok(body.weeks.length <= 18);
});

// ---- stats.mjs: tool channel fold ------------------------------------------------------------------------------
test("toolChannel and foldSource fold only utm-style tool-<slug> labels", () => {
  assert.equal(toolChannel("tool-latex-diff"), "tool:latex-diff");
  assert.equal(toolChannel("Tool-Word-Counter"), "tool:word-counter");
  for (const v of ["tool", "tool-", "tools-x", "mytool-x", "tool-time.example", "tool:latex-diff", "https://tool-x/", "paid:tool-x", "", undefined]) {
    assert.equal(toolChannel(v), "", String(v));
  }
  assert.equal(foldSource("LinkedIn"), "linkedin");
  assert.equal(foldSource("reddit.com"), "reddit.com");
  assert.equal(foldSource("tool-bib-builder"), "tool:bib-builder");
});

test("default stats shows tool channels in the funnel and campaign sources, leaves referrers and paid labels alone", async () => {
  put({ type: "pageview", path: "/moderntex/", ft: "tool:latex-diff", utm: "tool-latex-diff", refHost: "", vid: "a" });
  put({ type: "pageview", path: "/moderntex/", ft: "tool-bib-validator", utm: "tool-bib-validator", vid: "b" });
  put({ type: "pageview", path: "/", ft: "tool-time.example", refHost: "tool-time.example", utm: "", vid: "c" });
  put({ type: "pageview", path: "/", ft: "paid:google", utm: "google", vid: "d" });
  put({ type: "pageview", path: "/", ft: "linkedin", refHost: "www.linkedin.com", vid: "e" });
  put({ type: "trial_download", path: "/moderntex/", meta: "moderntex", ft: "tool:latex-diff", vid: "a" });
  const out = await (await get("days=2")).json();
  assert.equal(out.funnelByChannel["tool:latex-diff"].pageviews, 1);
  assert.equal(out.funnelByChannel["tool:latex-diff"].trial.moderntex, 1);
  assert.equal(out.funnelByChannel["tool:bib-validator"].pageviews, 1);
  assert.equal(out.funnelByChannel["tool-time.example"].pageviews, 1);
  assert.equal(out.funnelByChannel["paid:google"].pageviews, 1);
  assert.equal(out.funnelByChannel.linkedin.pageviews, 1);
  assert.equal(out.funnelByChannel["tool-bib-validator"], undefined);
  const utm = Object.fromEntries(out.topUtm.map((r) => [r.key, r.count]));
  assert.equal(utm["tool:latex-diff"], 1);
  assert.equal(utm["tool:bib-validator"], 1);
  const refs = Object.fromEntries(out.topReferrers.map((r) => [r.key, r.count]));
  assert.equal(refs["tool-time.example"], 1);
  assert.equal(refs.linkedin, 1);
});
