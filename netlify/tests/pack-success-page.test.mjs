// The pack success page script (site/tools/paper-review/packs/success.js), run against a small fake
// DOM with the response shapes /paper-review/redeem-session gives: a plain pack (as sold today), a
// Publication Pack (groups), a lab plan, and a refunded or expired order.
//
// Run with: node --test netlify/tests/pack-success-page.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const SRC = readFileSync(join(SITE, "tools/paper-review/packs/success.js"), "utf8");
const HTML = readFileSync(join(SITE, "tools/paper-review/packs/success/index.html"), "utf8");

class FakeNode {
  constructor(tag, text = "") {
    this.tag = tag; this.textContent = text; this.innerHTML = ""; this.hidden = false;
    this.children = []; this.attrs = {}; this.className = ""; this.href = "";
    const classes = new Set();
    this.classList = { toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)), contains: (c) => classes.has(c) };
  }
  appendChild(n) { this.children.push(n); return n; }
  setAttribute(k, v) { this.attrs[k] = v; }
}

/** Runs the script with one canned redeem-session response and waits for the page to settle. */
async function run(response, { status = 200, search = "?session_id=cs_test_1", headers } = {}) {
  const ids = {
    "redeem-status": new FakeNode("p", "Loading your tokens…"),
    "tokens-pane": Object.assign(new FakeNode("div"), { hidden: true }),
    "tokens-table": new FakeNode("table"),
    "tokens-intro": new FakeNode("p", "INTRO"),
    "tokens-footnote": new FakeNode("p", "FOOTNOTE"),
    "groups-pane": Object.assign(new FakeNode("div"), { hidden: true }),
    "groups-list": new FakeNode("ul"),
  };
  const sel = {
    "main h1": new FakeNode("h1", "HEADING"),
    ".tools-hero p:not(.eyebrow)": new FakeNode("p", "LEDE"),
    ".tools-hero .eyebrow": new FakeNode("p", "EYEBROW"),
  };
  const calls = [];
  const ctx = {
    document: {
      getElementById: (id) => ids[id] || null,
      querySelector: (s) => sel[s] || null,
      createElement: (t) => new FakeNode(t),
    },
    window: { location: { search } },
    URLSearchParams,
    API_BASE: "https://api.test",
    escapeHtml: (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"),
    setTimeout: () => 0,
    fetch: async (url, init) => {
      calls.push({ url, body: JSON.parse(init.body) });
      return { status, ok: status >= 200 && status < 300, headers, json: async () => { if (response === null) throw new SyntaxError("not json"); return response; } };
    },
  };
  vm.runInNewContext(SRC, ctx);
  for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r));
  return { ids, sel, calls };
}

test("a pack sold today renders as before: the token table, direct_token links, and the page's own heading and text", async () => {
  const { ids, sel, calls } = await run({ tokens: ["tokA", "tokB"], unused_tokens: ["tokB"], product: "paper-review-pack-5" });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://api.test/paper-review/redeem-session");
  assert.equal(calls[0].body.session_id, "cs_test_1");
  const table = ids["tokens-table"].innerHTML;
  assert.match(table, /<td class="success-token">tokA<\/td><td>Used<\/td>/);
  assert.match(table, /Already used/);
  assert.match(table, /<td class="success-token">tokB<\/td><td>Unused<\/td>/);
  assert.match(table, /href="\/tools\/paper-review\/upload\/\?direct_token=tokB">Use this token<\/a>/);
  assert.doesNotMatch(table, /style=/, "no inline style");
  assert.equal(ids["tokens-pane"].hidden, false);
  assert.equal(ids["groups-pane"].hidden, true);
  assert.equal(ids["redeem-status"].hidden, true);
  // Nothing on the page is reworded for a plain pack.
  assert.equal(sel["main h1"].textContent, "HEADING");
  assert.equal(sel[".tools-hero p:not(.eyebrow)"].textContent, "LEDE");
  assert.equal(sel[".tools-hero .eyebrow"].textContent, "EYEBROW");
  assert.equal(ids["tokens-intro"].textContent, "INTRO");
  assert.equal(ids["tokens-footnote"].textContent, "FOOTNOTE");
});

test("a Publication Pack shows its three links, with a used one marked instead of linked", async () => {
  const groups = [
    { category: "paper_review", name: "Paper Review", url: "/tools/paper-review/upload/?direct_token=a", used: false },
    { category: "revision_review", name: "Revision Review", url: "/tools/revision-review/upload/?direct_token=b", used: true },
    { category: "response_draft", name: "Response letter draft", url: "/tools/response-review/draft/upload/?direct_token=c", used: false },
  ];
  const { ids, sel } = await run({ groups, product: "publication-pack", status: "unused" });
  const items = ids["groups-list"].children;
  assert.equal(items.length, 3);
  assert.deepEqual(items.map((li) => li.children[0].textContent), ["Paper Review", "Revision Review", "Response letter draft"]);
  assert.equal(items[0].children[1].href, groups[0].url);
  assert.equal(items[0].children[1].textContent, "Start");
  assert.equal(items[1].children[1].textContent, "Used");
  assert.equal(items[1].children[1].href, "", "a used link is not offered again");
  assert.equal(ids["groups-pane"].hidden, false);
  assert.equal(ids["tokens-pane"].hidden, true);
  assert.equal(sel["main h1"].textContent, "Your three links");
});

test("a lab plan names the plan and the use-by date exactly as the backend sends it", async () => {
  const { ids, sel } = await run({ tokens: ["t1", "t2"], unused_tokens: ["t1", "t2"], lab_plan: true, plan_name: "Lab Plus", valid_until: "13 December 2026" });
  assert.equal(sel["main h1"].textContent, "Your Lab Plus plan is active");
  assert.match(sel[".tools-hero p:not(.eyebrow)"].textContent, /Use them by 13 December 2026\./);
  assert.match(ids["tokens-table"].innerHTML, /direct_token=t1/);
  assert.equal(ids["tokens-pane"].hidden, false);
  assert.notEqual(ids["tokens-intro"].textContent, "INTRO");
});

test("a lab plan with no date leaves the date sentence out", async () => {
  const { sel } = await run({ tokens: ["t1"], lab_plan: true });
  assert.equal(sel["main h1"].textContent, "Your Lab plan is active");
  assert.doesNotMatch(sel[".tools-hero p:not(.eyebrow)"].textContent, /Use them by|undefined|Invalid/);
});

test("a refunded order and an expired one each get their own message", async () => {
  const revoked = await run({ error: "revoked" }, { status: 410 });
  assert.match(revoked.ids["redeem-status"].textContent, /refunded or disputed/);
  assert.equal(revoked.ids["redeem-status"].classList.contains("error"), true);
  assert.equal(revoked.ids["tokens-pane"].hidden, true);
  const expired = await run({ error: "expired" }, { status: 410 });
  assert.match(expired.ids["redeem-status"].textContent, /This link has expired/);
});

test("a 429 says how long to wait instead of \"Could not load tokens.\"", async () => {
  const soon = await run({ error: "rate_limited", retry_after: 600 }, { status: 429 });
  const msg = soon.ids["redeem-status"].textContent;
  assert.match(msg, /Too many link checks from your network\. Reload this page in about 10 minutes\./);
  assert.match(msg, /do not need to pay again/);
  assert.doesNotMatch(msg, /Could not load tokens/);
  assert.equal(soon.ids["redeem-status"].classList.contains("error"), true);
  const one = await run({ error: "rate_limited", retry_after: 30 }, { status: 429 });
  assert.match(one.ids["redeem-status"].textContent, /about 1 minute\./);
  const tomorrow = await run({ error: "rate_limited", retry_after: 40000 }, { status: 429 });
  assert.match(tomorrow.ids["redeem-status"].textContent, /Reload this page tomorrow, or email ben@purplelink\.llc/);
  // A 429 from a proxy in front of the API: no JSON body, only a Retry-After header.
  const proxy = await run(null, { status: 429, headers: { get: (h) => (h === "Retry-After" ? "120" : null) } });
  assert.match(proxy.ids["redeem-status"].textContent, /about 2 minutes\./);
  const bare = await run(null, { status: 429 });
  assert.match(bare.ids["redeem-status"].textContent, /Reload this page in a few minutes\./);
});

test("the page links only stylesheets that exist and carries the nodes the script fills", () => {
  for (const m of HTML.matchAll(/<link rel="stylesheet" href="(\/[^"?]+)/g)) {
    assert.doesNotThrow(() => readFileSync(join(SITE, m[1])), m[1] + " is linked but missing");
  }
  for (const id of ["redeem-status", "tokens-pane", "tokens-table", "tokens-intro", "tokens-footnote", "groups-pane", "groups-list"]) {
    assert.match(HTML, new RegExp('id="' + id + '"'));
  }
  const css = readFileSync(join(SITE, "tools/paper-review/paper-review.css"), "utf8");
  for (const cls of ["success-token", "success-groups", "success-group", "success-group-name", "success-group-used"]) {
    assert.match(css, new RegExp("\\." + cls + "\\s*\\{"), cls + " is styled");
  }
});
