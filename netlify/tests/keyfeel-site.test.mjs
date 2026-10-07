// The Keyfeel pages, checked as files: the offer in the structured data, the release gate
// (the trial link and Buy button stay dead until site/keyfeel/launch.js is flipped), the
// copy rules, the listings, and the success page's script run against a small fake DOM.
//
// Run with: node --test netlify/tests/keyfeel-site.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const read = (p) => readFileSync(join(SITE, p), "utf8");
const jsonLd = (html) =>
  [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].flatMap((m) => {
    const d = JSON.parse(m[1]);
    return d["@graph"] || [d];
  });

// ---- product page --------------------------------------------------------------------

test("the Keyfeel page offers the app at $9.99 once, with a 14-day refund, for macOS 13, in valid JSON-LD", () => {
  const app = jsonLd(read("keyfeel/index.html")).find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Keyfeel");
  assert.equal(app.offers.price, "9.99");
  assert.equal(app.offers.priceCurrency, "USD");
  assert.equal(app.offers.hasMerchantReturnPolicy.merchantReturnDays, 14);
  assert.equal(app.operatingSystem, "macOS 13+");
  assert.equal(app.offers.availability, undefined, "no availability is claimed in the markup");
});

test("the page is wired to the delivery and checkout functions and carries the shared head tags", () => {
  const html = read("keyfeel/index.html");
  assert.match(html, /data-kf-href="\/\.netlify\/functions\/keyfeel-download\?download=1"/);
  assert.match(html, /id="checkout-btn" data-product="keyfeel"/);
  assert.match(html, /paid-tool-landing\.js/);
  assert.match(html, /\/keyfeel\/launch\.js/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/keyfeel\/">/);
  assert.match(html, /<meta name="robots" content="index, follow">/);
  assert.match(html, /<meta property="og:image" content="https:\/\/purplelink\.llc\/assets\/og\/keyfeel\.png">/);
  assert.match(html, /\/theme\.js/);
});

// ---- the release gate ------------------------------------------------------------------

test("after launch, the static page already shows the live wording and the trial link works", () => {
  const html = read("keyfeel/index.html");
  const trialTags = [...html.matchAll(/<a\b[^>]*data-kf-gated[^>]*>/g)].map((m) => m[0]);
  assert.ok(trialTags.length >= 2);
  for (const tag of trialTags) {
    assert.match(tag, /\shref="\/\.netlify\/functions\/keyfeel-download\?download=1"/);
    assert.doesNotMatch(tag, /aria-disabled/);
  }
  assert.doesNotMatch(html, /<button\b[^>]*id="checkout-btn"[^>]*\sdisabled/);
  assert.doesNotMatch(html, /Not released yet|opens at release/);
  assert.match(html, /Version 1\.1\.1, released October 7, 2026\. 7 MB disk image\./);
});

test("launch.js ships switched on with valid facts", () => {
  const src = read("keyfeel/launch.js");
  assert.match(src, /live: true,/);
  assert.match(src, /version: "1\.1\.1",/);
  assert.match(src, /sizeMb: "7",/);
  assert.match(src, /released: "2026-10-07"/);
});

class FakeEl {
  constructor(attrs = {}) {
    this.attrs = { ...attrs };
    this.hidden = "hidden" in attrs;
    this.disabled = "disabled" in attrs;
    this.textContent = attrs.__text || "";
    this.parentNode = { removeChild: (el) => { el.removed = true; } };
  }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  setAttribute(k, v) { this.attrs[k] = v; }
  removeAttribute(k) { delete this.attrs[k]; if (k === "disabled") this.disabled = false; }
}

function runLaunch(config) {
  const els = {
    pre: new FakeEl({ "data-kf-pre-only": "" }),
    live: new FakeEl({ "data-kf-live-only": "", hidden: "" }),
    trial: new FakeEl({ "data-kf-gated": "", "data-kf-href": "/.netlify/functions/keyfeel-download?download=1", "data-kf-live-text": "Try it free for 7 days", "aria-disabled": "true", __text: "Free trial opens at release" }),
    buy: new FakeEl({ "data-kf-gated": "", "data-kf-live-text": "Buy Keyfeel", disabled: "", __text: "Buying opens at release" }),
    facts: new FakeEl({ "data-kf-facts": "", __text: "placeholder" }),
    sticky: new FakeEl({ "data-kf-sticky": "" }),
  };
  const by = { "[data-kf-pre-only]": [els.pre], "[data-kf-live-only]": [els.live], "[data-kf-gated]": [els.trial, els.buy], "[data-kf-facts]": [els.facts], "[data-kf-sticky]": [els.sticky] };
  const warnings = [];
  const ctx = {
    window: { console: { warn: (m) => warnings.push(m) } },
    document: { readyState: "complete", querySelectorAll: (s) => by[s] || [], addEventListener() {} },
    console: { warn: (m) => warnings.push(m) },
    Date, String, Array,
  };
  ctx.window.KEYFEEL_LAUNCH = undefined;
  const src = read("keyfeel/launch.js").replace(/window\.KEYFEEL_LAUNCH = \{[\s\S]*?\};/, `window.KEYFEEL_LAUNCH = ${JSON.stringify(config)};`);
  vm.runInNewContext(src, ctx);
  return { els, warnings };
}

test("with live false the gated controls stay dead and the sticky bar is removed", () => {
  const { els } = runLaunch({ live: false, version: "1.0.0", sizeMb: "14", released: "2026-10-20" });
  assert.equal(els.trial.getAttribute("href"), null);
  assert.equal(els.trial.getAttribute("aria-disabled"), "true");
  assert.equal(els.buy.disabled, true);
  assert.equal(els.live.hidden, true);
  assert.equal(els.sticky.removed, true);
});

test("live true with every fact valid enables the trial link and Buy button and fills in the facts", () => {
  const { els } = runLaunch({ live: true, version: "1.0.0", sizeMb: "14", released: "2026-10-20" });
  assert.equal(els.trial.getAttribute("href"), "/.netlify/functions/keyfeel-download?download=1");
  assert.equal(els.trial.getAttribute("aria-disabled"), null);
  assert.equal(els.trial.textContent, "Try it free for 7 days");
  assert.equal(els.buy.disabled, false);
  assert.equal(els.buy.textContent, "Buy Keyfeel");
  assert.equal(els.live.hidden, false);
  assert.equal(els.pre.hidden, true);
  assert.equal(els.facts.textContent, "Version 1.0.0, released October 20, 2026. 14 MB disk image.");
  assert.ok(!els.sticky.removed);
});

test("live true with a missing or malformed fact stays switched off and says why", () => {
  for (const bad of [
    { live: true, version: "", sizeMb: "14", released: "2026-10-20" },
    { live: true, version: "1.0", sizeMb: "14", released: "2026-10-20" },
    { live: true, version: "1.0.0", sizeMb: "", released: "2026-10-20" },
    { live: true, version: "1.0.0", sizeMb: "14 MB", released: "2026-10-20" },
    { live: true, version: "1.0.0", sizeMb: "14", released: "" },
    { live: true, version: "1.0.0", sizeMb: "14", released: "20 Oct 2026" },
    { live: "true", version: "1.0.0", sizeMb: "14", released: "2026-10-20" },
  ]) {
    const { els, warnings } = runLaunch(bad);
    assert.equal(els.trial.getAttribute("href"), null, JSON.stringify(bad));
    assert.equal(els.buy.disabled, true, JSON.stringify(bad));
    if (bad.live === true) assert.ok(warnings.some((w) => /stays switched off/.test(w)), JSON.stringify(bad));
  }
});

// ---- copy rules ------------------------------------------------------------------------

test("the Keyfeel pages have no inline styles, em or en dashes or emoji, and no unbuilt features", () => {
  for (const p of ["keyfeel/index.html", "keyfeel/success/index.html"]) {
    const html = read(p);
    assert.doesNotMatch(html, /<[a-z][^>]*\sstyle\s*=/i, `${p} has an inline style`);
    assert.doesNotMatch(html, /[–—]/, `${p} has an em or en dash`);
    assert.doesNotMatch(html, /\p{Extended_Pictographic}/u, `${p} has an emoji`);
  }
  const page = read("keyfeel/index.html").toLowerCase();
  for (const unbuilt of ["accessibility permission", "sound pack store", "sync across", "equalizer", "keylogger protection", "signed and notarized"]) {
    assert.ok(!page.includes(unbuilt), `the page mentions: ${unbuilt}`);
  }
  assert.match(page, /only while a finger is on the trackpad/);
  assert.match(page, /key codes?, never the characters|key code, not the character/);
  assert.match(page, /password field/);
  assert.match(page, /input monitoring/);
  assert.match(page, /macos 13/);
  assert.match(page, /\$9\.99/);
  assert.match(page, /14 days/);
});

test("every image on the page exists, has a size and real alt text, and is small", () => {
  const html = read("keyfeel/index.html");
  const imgs = [...html.matchAll(/<img\b[^>]*src="(\/(?:keyfeel\/img|assets)\/[^"]+)"[^>]*>/g)].filter((m) => /keyfeel/.test(m[1]));
  assert.ok(imgs.length >= 6, `found ${imgs.length}`);
  for (const [tag, src] of imgs) {
    assert.ok(existsSync(join(SITE, src)), `${src} is missing`);
    assert.ok(statSync(join(SITE, src)).size < 250 * 1024, `${src} is over 250 KB`);
    assert.match(tag, /\swidth="\d+"/);
    assert.match(tag, /\sheight="\d+"/);
    assert.match(tag, /\salt="[^"]*"/);
  }
  for (const [tag, src] of imgs.filter((m) => /\/keyfeel\/img\//.test(m[1]))) assert.match(tag, /\salt="[^"]{40,}"/, `${src} needs real alt text`);
  assert.match(html, /not a screenshot/i, "illustrations are labelled as illustrations");
});

test("the share image is 1200 by 630 and the icon exists at both sizes", () => {
  const png = readFileSync(join(SITE, "assets/og/keyfeel.png"));
  assert.equal(png.readUInt32BE(16), 1200);
  assert.equal(png.readUInt32BE(20), 630);
  for (const f of ["assets/keyfeel-icon.webp", "assets/keyfeel-icon-128.webp"]) assert.ok(existsSync(join(SITE, f)), f);
});

test("the success page is noindex, loads its script and has the download box", () => {
  const html = read("keyfeel/success/index.html");
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.match(html, /src="\/keyfeel\/success\.js/);
  assert.match(html, /id="downloads"/);
  assert.match(html, /Input Monitoring/);
});

// ---- listings --------------------------------------------------------------------------

test("the sitemap, llms.txt, the search index, the products and pricing pages and the footer list Keyfeel", () => {
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/keyfeel\/<\/loc>/);
  assert.doesNotMatch(read("sitemap.xml"), /keyfeel\/success/);
  assert.match(read("llms.txt"), /https:\/\/purplelink\.llc\/keyfeel\//);
  assert.ok(JSON.parse(read("search-index.json")).some((e) => e.u === "/keyfeel/"));
  assert.match(read("products/index.html"), /<a class="catalog-card" href="\/keyfeel\/">/);
  assert.match(read("products/index.html"), /"name": "Keyfeel", "url": "https:\/\/purplelink\.llc\/keyfeel\/"/);
  assert.match(read("pricing/index.html"), /Keyfeel for Mac/);
  assert.match(read("index.html"), /<li><a href="\/keyfeel\/">Keyfeel<\/a><\/li>/);
  assert.match(read("terms/index.html"), /<h2>Keyfeel: additional terms<\/h2>/);
  assert.match(read("privacy/index.html"), /<strong>Keyfeel<\/strong> has no account/);
});

test("the Suite page lists Keyfeel with its own price and a card", () => {
  const html = read("suite/index.html");
  assert.match(html, /<h3>Keyfeel<\/h3>/);
  assert.match(html, /href="\/keyfeel\/">See Keyfeel/);
  assert.match(html, /macOS 13\+/);
  assert.match(html, /Keyfeel needs macOS 13 or later/);
});

// ---- the success page's script, against a fake DOM ---------------------------------------

class FakeNode {
  constructor(tag = "div") { this.tagName = tag; this.children = []; this.attrs = {}; this.textContent = ""; this.className = ""; this.href = ""; }
  appendChild(c) { this.children.push(c); return c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener() {}
}
function runSuccess({ search, fetchImpl }) {
  const nodes = { downloads: new FakeNode(), "dl-status": new FakeNode(), license: new FakeNode() };
  const fetched = [];
  const ctx = {
    document: { getElementById: (id) => nodes[id] || null, createElement: (t) => new FakeNode(t) },
    navigator: {},
    window: { location: { search } },
    URLSearchParams, encodeURIComponent,
    fetch: (url) => { fetched.push(url); return fetchImpl(url); },
    Promise,
  };
  vm.runInNewContext(readFileSync(join(SITE, "keyfeel/success.js"), "utf8"), ctx);
  return { nodes, fetched };
}
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const SID = "cs_live_abcdefghij1234";

test("/keyfeel/success/ asks keyfeel-download for the session and shows a download button", async () => {
  const { nodes, fetched } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { files: [{ key: "Keyfeel-1.0.0.dmg", label: "Keyfeel 1.0.0 for macOS (disk image)", url: "/.netlify/functions/keyfeel-download?session_id=x&file=Keyfeel-1.0.0.dmg" }] }),
  });
  await tick();
  assert.deepEqual(fetched, [`/.netlify/functions/keyfeel-download?session_id=${SID}`]);
  assert.match(nodes.downloads.innerHTML, /Download: Keyfeel 1\.0\.0 for macOS/);
  assert.match(nodes.downloads.innerHTML, /keyfeel-download\?session_id=x&amp;file=Keyfeel-1\.0\.0\.dmg/);
});

test("/keyfeel/success/ shows the license key from the server", async () => {
  const KEY = "KFL1-ABCDE-FGHJK";
  const { nodes } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { license: KEY, files: [{ key: "Keyfeel-1.0.0.dmg", label: "Keyfeel 1.0.0 for macOS (disk image)", url: "/x" }] }),
  });
  await tick();
  const code = nodes.license.children.find((c) => c.tagName === "code");
  assert.ok(code, "a code element holds the key");
  assert.equal(code.textContent, KEY);
});

test("/keyfeel/success/ shows the server's reason when refused, and never fetches for a bad id", async () => {
  const refused = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(403, { error: "not_entitled", detail: "This order is for a different product." }) });
  await tick();
  assert.match(refused.nodes.downloads.innerHTML, /This order is for a different product\./);
  const bad = runSuccess({ search: "?session_id=nope", fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.equal(bad.fetched.length, 0);
  assert.match(bad.nodes.downloads.innerHTML, /receipt email/);
});
