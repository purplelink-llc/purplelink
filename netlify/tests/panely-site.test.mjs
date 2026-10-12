// The Panely pages, checked as files: the offer in the structured data, the release gate (the trial link and
// Buy button stay dead until site/panely/launch.js is flipped), the copy rules, and the success page's script run
// against a small fake DOM. The page is unlisted and noindex until launch day; the listing checks (sitemap,
// llms.txt, products, pricing, footer, Suite) belong to the launch-day commit.
//
// Run with: node --test netlify/tests/panely-site.test.mjs

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

test("the Panely page offers the app at $9.99 once, with a 14-day refund, for macOS 14, in valid JSON-LD", () => {
  const nodes = jsonLd(read("panely/index.html"));
  const app = nodes.find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Panely");
  assert.equal(app.offers.price, "9.99");
  assert.equal(app.offers.priceCurrency, "USD");
  assert.equal(app.offers.hasMerchantReturnPolicy.merchantReturnDays, 14);
  assert.equal(app.operatingSystem, "macOS 14+");
  assert.equal(app.offers.availability, "https://schema.org/PreOrder", "not on sale yet: the page must not claim InStock");
  assert.ok(nodes.some((n) => n["@type"] === "FAQPage" && n.mainEntity.length >= 8));
  assert.ok(nodes.some((n) => n["@type"] === "BreadcrumbList"));
});

test("the page is wired to the delivery and checkout functions and carries the shared head tags", () => {
  const html = read("panely/index.html");
  assert.match(html, /data-pf-href="\/\.netlify\/functions\/panely-download\?download=1"/);
  assert.match(html, /id="checkout-btn" data-product="panely"/);
  assert.match(html, /paid-tool-landing\.js/);
  assert.match(html, /\/panely\/launch\.js/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/panely\/">/);
  assert.match(html, /<meta name="robots" content="noindex, follow">/, "unlisted until launch day");
  assert.match(html, /<meta property="og:image" content="https:\/\/purplelink\.llc\/assets\/og\/panely\.png">/);
  assert.match(html, /\/theme\.js/);
});

// ---- the release gate ------------------------------------------------------------------

test("before launch, the static page is dead and says so, whether or not scripts run", () => {
  const html = read("panely/index.html");
  const gated = [...html.matchAll(/<a\b[^>]*data-pf-gated[^>]*>/g)].map((m) => m[0]);
  assert.ok(gated.length >= 2);
  for (const tag of gated) {
    assert.doesNotMatch(tag, /\shref=/);
    assert.match(tag, /aria-disabled="true"/);
  }
  assert.match(html, /<button\b[^>]*id="checkout-btn"[^>]*\sdisabled/);
  assert.match(html, /Not released yet/);
  assert.doesNotMatch(html, /Version \d+\.\d+\.\d+, released/);
});

test("launch.js ships switched OFF with no facts, so nothing can sell by accident", () => {
  const src = read("panely/launch.js");
  assert.match(src, /live: false,/);
  assert.match(src, /version: "",/);
  assert.match(src, /sizeMb: "",/);
  assert.match(src, /released: ""/);
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
    pre: new FakeEl({ "data-pf-pre-only": "" }),
    live: new FakeEl({ "data-pf-live-only": "", hidden: "" }),
    trial: new FakeEl({ "data-pf-gated": "", "data-pf-href": "/.netlify/functions/panely-download?download=1", "data-pf-live-text": "Try it free for 7 days", "aria-disabled": "true", __text: "Free trial opens at release" }),
    buy: new FakeEl({ "data-pf-gated": "", "data-pf-live-text": "Buy Panely", disabled: "", __text: "Buying opens at release" }),
    facts: new FakeEl({ "data-pf-facts": "", __text: "placeholder" }),
    sticky: new FakeEl({ "data-pf-sticky": "" }),
  };
  const by = { "[data-pf-pre-only]": [els.pre], "[data-pf-live-only]": [els.live], "[data-pf-gated]": [els.trial, els.buy], "[data-pf-facts]": [els.facts], "[data-pf-sticky]": [els.sticky] };
  const warnings = [];
  const ctx = {
    window: { console: { warn: (m) => warnings.push(m) } },
    document: { readyState: "complete", querySelectorAll: (s) => by[s] || [], addEventListener() {} },
    console: { warn: (m) => warnings.push(m) },
    Date, String, Array,
  };
  ctx.window.PANELY_LAUNCH = undefined;
  const src = read("panely/launch.js").replace(/window\.PANELY_LAUNCH = \{[\s\S]*?\};/, `window.PANELY_LAUNCH = ${JSON.stringify(config)};`);
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
  assert.equal(els.trial.getAttribute("href"), "/.netlify/functions/panely-download?download=1");
  assert.equal(els.trial.getAttribute("aria-disabled"), null);
  assert.equal(els.trial.textContent, "Try it free for 7 days");
  assert.equal(els.buy.disabled, false);
  assert.equal(els.buy.textContent, "Buy Panely");
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

test("the Panely pages have no inline styles, em or en dashes or emoji, and no unbuilt features", () => {
  for (const p of ["panely/index.html", "panely/success/index.html"]) {
    const html = read(p);
    assert.doesNotMatch(html, /<[a-z][^>]*\sstyle\s*=/i, `${p} has an inline style`);
    assert.doesNotMatch(html, /[–—]/, `${p} has an em or en dash`);
    assert.doesNotMatch(html, /\p{Extended_Pictographic}/u, `${p} has an emoji`);
  }
  const page = read("panely/index.html").toLowerCase();
  for (const unbuilt of ['sync across', 'stage manager', 'record your own shortcuts', 'automatic tiling by default', 'drag windows between spaces'].map((x) => x)) assert.ok(!page.includes(unbuilt), `the page mentions: ${unbuilt}`);
  assert.match(page, /accessibility/);
  assert.match(page, /what is inside a window/);
  assert.match(page, /language model/);
  assert.match(page, /input monitoring/);
  assert.match(page, /macos 14/);
  assert.match(page, /\$9\.99/);
  assert.match(page, /14 days/);
  assert.match(page, /current space/);
});

test("every image on the page exists, has a size and real alt text, and is small", () => {
  const html = read("panely/index.html");
  const imgs = [...html.matchAll(/<img\b[^>]*src="(\/(?:panely\/img|assets)\/[^"]+)"[^>]*>/g)].filter((m) => /panely/.test(m[1]));
  assert.ok(imgs.length >= 2, `found ${imgs.length}`);
  for (const [tag, src] of imgs) {
    assert.ok(existsSync(join(SITE, src)), `${src} is missing`);
    assert.ok(statSync(join(SITE, src)).size < 250 * 1024, `${src} is over 250 KB`);
    assert.match(tag, /\swidth="\d+"/);
    assert.match(tag, /\sheight="\d+"/);
    assert.match(tag, /\salt="[^"]*"/);
  }
  for (const [tag, src] of imgs.filter((m) => /\/panely\/img\//.test(m[1]))) assert.match(tag, /\salt="[^"]{40,}"/, `${src} needs real alt text`);
  assert.match(html, /not a screenshot/i, "the hero image is labelled for what it is");
});

test("the share image is 1200 by 630 and the icon exists at both sizes", () => {
  const png = readFileSync(join(SITE, "assets/og/panely.png"));
  assert.equal(png.readUInt32BE(16), 1200);
  assert.equal(png.readUInt32BE(20), 630);
  for (const f of ["assets/panely-icon.webp", "assets/panely-icon-128.webp"]) assert.ok(existsSync(join(SITE, f)), f);
});

test("the success page is noindex, loads its script and has the download box", () => {
  const html = read("panely/success/index.html");
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.match(html, /src="\/panely\/success\.js/);
  assert.match(html, /id="downloads"/);
  assert.match(html.toLowerCase(), /accessibility/);
});

test("the page is not listed anywhere yet: not in the sitemap, llms.txt or the products page", () => {
  for (const f of ["sitemap.xml", "llms.txt", "products/index.html"]) assert.doesNotMatch(read(f), /purplelink\.llc\/panely\/|href="\/panely\/"/, `${f} must not list Panely before launch day`);
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
  vm.runInNewContext(readFileSync(join(SITE, "panely/success.js"), "utf8"), ctx);
  return { nodes, fetched };
}
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const SID = "cs_live_abcdefghij1234";

test("/panely/success/ asks panely-download for the session and shows a download button", async () => {
  const { nodes, fetched } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { files: [{ key: "Panely-1.0.0.dmg", label: "Panely 1.0.0 for macOS (disk image)", url: "/.netlify/functions/panely-download?session_id=x&file=Panely-1.0.0.dmg" }] }),
  });
  await tick();
  assert.deepEqual(fetched, [`/.netlify/functions/panely-download?session_id=${SID}`]);
  assert.match(nodes.downloads.innerHTML, /Download: Panely 1\.0\.0 for macOS/);
  assert.match(nodes.downloads.innerHTML, /panely-download\?session_id=x&amp;file=Panely-1\.0\.0\.dmg/);
});

test("/panely/success/ shows the license key from the server", async () => {
  const KEY = "PNL1-ABCDE-FGHJK";
  const { nodes } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { license: KEY, files: [{ key: "Panely-1.0.0.dmg", label: "Panely 1.0.0 for macOS (disk image)", url: "/x" }] }),
  });
  await tick();
  const code = nodes.license.children.find((c) => c.tagName === "code");
  assert.ok(code, "a code element holds the key");
  assert.equal(code.textContent, KEY);
});

test("/panely/success/ shows the server's reason when refused, and never fetches for a bad id", async () => {
  const refused = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(403, { error: "not_entitled", detail: "This order is for a different product." }) });
  await tick();
  assert.match(refused.nodes.downloads.innerHTML, /This order is for a different product\./);
  const bad = runSuccess({ search: "?session_id=nope", fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.equal(bad.fetched.length, 0);
  assert.match(bad.nodes.downloads.innerHTML, /receipt email/);
});
