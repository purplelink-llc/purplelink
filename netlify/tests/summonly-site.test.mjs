// The Summonly pages, checked as files: the offer in the structured data, the release gate (the trial link and
// Buy button stay dead until site/summonly/launch.js is flipped), the copy rules, and the success page's script run
// against a small fake DOM. Until the gate is switched on the page is noindex and says PreOrder; the listing checks (sitemap,
// llms.txt, products, pricing, footer, Suite) are in the launch-day commit, and the gate flip makes the page live.
//
// Run with: node --test netlify/tests/summonly-site.test.mjs

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

test("the Summonly page offers the app at $9.99 once, with a 14-day refund, for macOS 14, in valid JSON-LD", () => {
  const nodes = jsonLd(read("summonly/index.html"));
  const app = nodes.find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Summonly");
  assert.equal(app.offers.price, "9.99");
  assert.equal(app.offers.priceCurrency, "USD");
  assert.equal(app.offers.hasMerchantReturnPolicy.merchantReturnDays, 14);
  assert.equal(app.operatingSystem, "macOS 14+");
  const live = /live: true,/.test(read("summonly/launch.js"));
  assert.equal(app.offers.availability, live ? "https://schema.org/InStock" : "https://schema.org/PreOrder", "the page claims InStock only once the gate is on");
  assert.ok(nodes.some((n) => n["@type"] === "FAQPage" && n.mainEntity.length >= 8));
  assert.ok(nodes.some((n) => n["@type"] === "BreadcrumbList"));
});

test("the page is wired to the delivery and checkout functions and carries the shared head tags", () => {
  const html = read("summonly/index.html");
  assert.match(html, /data-lf-href="\/\.netlify\/functions\/summonly-download\?download=1"/);
  assert.match(html, /id="checkout-btn" data-product="summonly"/);
  assert.match(html, /paid-tool-landing\.js/);
  assert.match(html, /\/summonly\/launch\.js/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/summonly\/">/);
  const live = /live: true,/.test(read("summonly/launch.js"));
  assert.match(html, live ? /<meta name="robots" content="index, follow">/ : /<meta name="robots" content="noindex, follow">/, "noindex until the gate is switched on, indexed after");
  assert.match(html, /<meta property="og:image" content="https:\/\/purplelink\.llc\/assets\/og\/summonly\.png">/);
  assert.match(html, /\/theme\.js/);
});

// ---- the release gate ------------------------------------------------------------------

test("the static page matches the gate: dead and saying so before launch, live after", () => {
  const html = read("summonly/index.html");
  const live = /live: true,/.test(read("summonly/launch.js"));
  const gated = [...html.matchAll(/<a\b[^>]*data-lf-gated[^>]*>/g)].map((m) => m[0]);
  assert.ok(gated.length >= 2);
  for (const tag of gated) {
    if (live) { assert.match(tag, /\shref="\/\.netlify\/functions\/summonly-download\?download=1"/); assert.doesNotMatch(tag, /aria-disabled/); }
    else { assert.doesNotMatch(tag, /\shref=/); assert.match(tag, /aria-disabled="true"/); }
  }
  if (live) {
    assert.doesNotMatch(html, /<button\b[^>]*id="checkout-btn"[^>]*\sdisabled/);
    assert.doesNotMatch(html, /Not released yet/);
    assert.match(html, /Version \d+\.\d+\.\d+, released [A-Z][a-z]+ \d{1,2}, \d{4}\. \d+ MB disk image\./);
  } else {
    assert.match(html, /<button\b[^>]*id="checkout-btn"[^>]*\sdisabled/);
    assert.match(html, /Not released yet/);
    assert.doesNotMatch(html, /Version \d+\.\d+\.\d+, released/);
  }
});

test("launch.js is either fully off with no facts, or on with valid facts", () => {
  const src = read("summonly/launch.js");
  if (/live: true,/.test(src)) {
    assert.match(src, /version: "\d+\.\d+\.\d+",/); assert.match(src, /sizeMb: "\d{1,4}",/); assert.match(src, /released: "\d{4}-\d{2}-\d{2}"/);
  } else {
    assert.match(src, /live: false,/); assert.match(src, /version: "",/); assert.match(src, /sizeMb: "",/); assert.match(src, /released: ""/);
  }
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
    pre: new FakeEl({ "data-lf-pre-only": "" }),
    live: new FakeEl({ "data-lf-live-only": "", hidden: "" }),
    trial: new FakeEl({ "data-lf-gated": "", "data-lf-href": "/.netlify/functions/summonly-download?download=1", "data-lf-live-text": "Try it free for 7 days", "aria-disabled": "true", __text: "Free trial opens at release" }),
    buy: new FakeEl({ "data-lf-gated": "", "data-lf-live-text": "Buy Summonly", disabled: "", __text: "Buying opens at release" }),
    facts: new FakeEl({ "data-lf-facts": "", __text: "placeholder" }),
    sticky: new FakeEl({ "data-lf-sticky": "" }),
  };
  const by = { "[data-lf-pre-only]": [els.pre], "[data-lf-live-only]": [els.live], "[data-lf-gated]": [els.trial, els.buy], "[data-lf-facts]": [els.facts], "[data-lf-sticky]": [els.sticky] };
  const warnings = [];
  const ctx = {
    window: { console: { warn: (m) => warnings.push(m) } },
    document: { readyState: "complete", querySelectorAll: (s) => by[s] || [], addEventListener() {} },
    console: { warn: (m) => warnings.push(m) },
    Date, String, Array,
  };
  ctx.window.SUMMONLY_LAUNCH = undefined;
  const src = read("summonly/launch.js").replace(/window\.SUMMONLY_LAUNCH = \{[\s\S]*?\};/, `window.SUMMONLY_LAUNCH = ${JSON.stringify(config)};`);
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
  assert.equal(els.trial.getAttribute("href"), "/.netlify/functions/summonly-download?download=1");
  assert.equal(els.trial.getAttribute("aria-disabled"), null);
  assert.equal(els.trial.textContent, "Try it free for 7 days");
  assert.equal(els.buy.disabled, false);
  assert.equal(els.buy.textContent, "Buy Summonly");
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

test("the Summonly pages have no inline styles, em or en dashes or emoji, and no unbuilt features", () => {
  for (const p of ["summonly/index.html", "summonly/success/index.html"]) {
    const html = read(p);
    assert.doesNotMatch(html, /<[a-z][^>]*\sstyle\s*=/i, `${p} has an inline style`);
    assert.doesNotMatch(html, /[–—]/, `${p} has an em or en dash`);
    assert.doesNotMatch(html, /\p{Extended_Pictographic}/u, `${p} has an emoji`);
  }
  const page = read("summonly/index.html").toLowerCase();
  for (const unbuilt of ['sync across', 'icloud sync', 'plugin store', 'workflow editor', 'chat with your files'].map((x) => x)) assert.ok(!page.includes(unbuilt), `the page mentions: ${unbuilt}`);
  assert.match(page, /option-space/);
  assert.match(page, /clipboard history/);
  assert.match(page, /password manager/);
  assert.match(page, /full disk access/);
  assert.match(page, /macos 14/);
  assert.match(page, /\$9\.99/);
  assert.match(page, /14 days/);
  assert.match(page, /found by name only/);
});

test("every image on the page exists, has a size and real alt text, and is small", () => {
  const html = read("summonly/index.html");
  const imgs = [...html.matchAll(/<img\b[^>]*src="(\/(?:summonly\/img|assets)\/[^"]+)"[^>]*>/g)].filter((m) => /summonly/.test(m[1]));
  assert.ok(imgs.length >= 2, `found ${imgs.length}`);
  for (const [tag, src] of imgs) {
    assert.ok(existsSync(join(SITE, src)), `${src} is missing`);
    assert.ok(statSync(join(SITE, src)).size < 250 * 1024, `${src} is over 250 KB`);
    assert.match(tag, /\swidth="\d+"/);
    assert.match(tag, /\sheight="\d+"/);
    assert.match(tag, /\salt="[^"]*"/);
  }
  for (const [tag, src] of imgs.filter((m) => /\/summonly\/img\//.test(m[1]))) assert.match(tag, /\salt="[^"]{40,}"/, `${src} needs real alt text`);
  assert.match(html, /not real files/i, "the hero image is labelled for what it is");
});

test("the share image is 1200 by 630 and the icon exists at both sizes", () => {
  const png = readFileSync(join(SITE, "assets/og/summonly.png"));
  assert.equal(png.readUInt32BE(16), 1200);
  assert.equal(png.readUInt32BE(20), 630);
  for (const f of ["assets/summonly-icon.webp", "assets/summonly-icon-128.webp"]) assert.ok(existsSync(join(SITE, f)), f);
});

test("the success page is noindex, loads its script and has the download box", () => {
  const html = read("summonly/success/index.html");
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.match(html, /src="\/summonly\/success\.js/);
  assert.match(html, /id="downloads"/);
  assert.match(html.toLowerCase(), /folder access/);
});

test("the sitemap, llms.txt, the products and pricing pages and the footer list Summonly, and the Suite includes it", () => {
  const live = /live: true,/.test(read("summonly/launch.js"));
  assert.equal(/<loc>https:\/\/purplelink\.llc\/summonly\/<\/loc>/.test(read("sitemap.xml")), live, "in the sitemap exactly when the gate is on (noindex pages must not be listed)");
  assert.doesNotMatch(read("sitemap.xml"), /summonly\/success/);
  assert.match(read("llms.txt"), /### Summonly \(macOS\)/);
  assert.match(read("llms.txt"), /https:\/\/purplelink\.llc\/summonly\//);
  assert.match(read("products/index.html"), /href="\/summonly\/"/);
  assert.match(read("pricing/index.html"), /href="\/summonly\/"/);
  assert.match(read("terms/index.html"), /<h2>Summonly: additional terms<\/h2>/);
  const suite = read("suite/index.html");
  assert.match(suite, /<span class="suite-row-name">Summonly<\/span><span class="suite-row-price">\$9\.99 once<\/span>/);
  assert.match(suite, /name="apps" value="summonly"/);
  assert.match(suite, /<h3>Summonly<\/h3>/);
  assert.match(read("suite/success/index.html"), /id="dl-lf"/);
  for (const f of ["index.html", "keyfeel/index.html", "moderntex/index.html"]) assert.match(read(f), /href="\/summonly\/"/, `${f} footer links Summonly`);
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
  vm.runInNewContext(readFileSync(join(SITE, "summonly/success.js"), "utf8"), ctx);
  return { nodes, fetched };
}
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const SID = "cs_live_abcdefghij1234";

test("/summonly/success/ asks summonly-download for the session and shows a download button", async () => {
  const { nodes, fetched } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { files: [{ key: "Summonly-1.0.0.dmg", label: "Summonly 1.0.0 for macOS (disk image)", url: "/.netlify/functions/summonly-download?session_id=x&file=Summonly-1.0.0.dmg" }] }),
  });
  await tick();
  assert.deepEqual(fetched, [`/.netlify/functions/summonly-download?session_id=${SID}`]);
  assert.match(nodes.downloads.innerHTML, /Download: Summonly 1\.0\.0 for macOS/);
  assert.match(nodes.downloads.innerHTML, /summonly-download\?session_id=x&amp;file=Summonly-1\.0\.0\.dmg/);
});

test("/summonly/success/ shows the license key from the server", async () => {
  const KEY = "SML1-ABCDE-FGHJK";
  const { nodes } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { license: KEY, files: [{ key: "Summonly-1.0.0.dmg", label: "Summonly 1.0.0 for macOS (disk image)", url: "/x" }] }),
  });
  await tick();
  const code = nodes.license.children.find((c) => c.tagName === "code");
  assert.ok(code, "a code element holds the key");
  assert.equal(code.textContent, KEY);
});

test("/summonly/success/ shows the server's reason when refused, and never fetches for a bad id", async () => {
  const refused = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(403, { error: "not_entitled", detail: "This order is for a different product." }) });
  await tick();
  assert.match(refused.nodes.downloads.innerHTML, /This order is for a different product\./);
  const bad = runSuccess({ search: "?session_id=nope", fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.equal(bad.fetched.length, 0);
  assert.match(bad.nodes.downloads.innerHTML, /receipt email/);
});

// ---- regressions found in review ----------------------------------------------------------

test("the Summonly page has no broken link and no stale 'not in this version' answer", () => {
  const html = read("summonly/index.html");
  assert.doesNotMatch(html, /href=&(amp;)?quot;/, "an href written with entities resolves to a bogus path");
  assert.match(html, /<a href="\/terms\/">terms<\/a>/);
  assert.doesNotMatch(html, /not in this version/i, "the shortcut recorder exists, so the page must not say it does not");
});

test("/summonly/success/ never leaves the key section on 'Preparing' when the order cannot be read", async () => {
  const failed = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(500, { error: "boom" }) });
  await tick();
  assert.match(failed.nodes.license.innerHTML, /receipt email/);
  assert.match(failed.nodes.license.innerHTML, /\/recover\//);
  const bad = runSuccess({ search: "?session_id=nope", fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.match(bad.nodes.license.innerHTML, /receipt email/);
});

test("/summonly/success/ labels the key with its heading, not with an aria-label that replaces the key", async () => {
  const { nodes } = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(200, { license: "KEY-1", files: [{ key: "a", label: "A", url: "/x" }] }) });
  await tick();
  const code = nodes.license.children.find((c) => c.tagName === "code");
  assert.equal(code.attrs["aria-labelledby"], "key-h");
  assert.equal(code.attrs["aria-label"], undefined);
});

test("the Summonly page does not claim to catch passwords the rules cannot see", () => {
  const html = read("summonly/index.html");
  assert.doesNotMatch(html, /looks like a password/i);
  assert.doesNotMatch(html, /private by default/i, "clipboard history is on from the first launch");
  assert.doesNotMatch(html, /lock the screen/i, "the command turns the display off");
});

test("the Terms describe Summonly's clipboard filter the way the product page does, without promising it catches passwords", () => {
  const terms = read("terms/index.html");
  assert.doesNotMatch(terms, /looks like a password/i);
  assert.match(terms, /one-time code/);
  assert.match(terms, /these rules are not perfect/);
});
