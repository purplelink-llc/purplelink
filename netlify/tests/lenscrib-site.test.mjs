// The Lenscrib pages, checked as files: the offer in the structured data, the release gate
// (the trial link and Buy button stay dead until site/lenscrib/launch.js is flipped), the
// copy rules (what the page may and may not claim), and the success page's script run against
// a small fake DOM.
//
// Run with: node --test netlify/tests/lenscrib-site.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
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
/** The text a reader sees: no scripts, styles, comments or tags. */
const visibleText = (html) =>
  html.replace(/<script\b[\s\S]*?<\/script[^>]*>/gi, " ").replace(/<style\b[\s\S]*?<\/style[^>]*>/gi, " ").replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<[^>]+>/g, " ").replace(/&nbsp;|&middot;/g, " ").replace(/&rsquo;|&#39;/g, "'").replace(/&amp;/g, "&").replace(/\s+/g, " ");

// ---- product page --------------------------------------------------------------------

test("the Lenscrib page offers the app at $19.99 once, with a 14-day refund, for macOS 14 on Apple silicon, in valid JSON-LD", () => {
  const app = jsonLd(read("lenscrib/index.html")).find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Lenscrib");
  assert.equal(app.offers.price, "19.99");
  assert.equal(app.offers.priceCurrency, "USD");
  assert.equal(app.offers.hasMerchantReturnPolicy.merchantReturnDays, 14);
  assert.equal(app.operatingSystem, "macOS 14+");
  assert.equal(app.processorRequirements, "Apple silicon");
  assert.equal(app.offers.availability, undefined, "no availability is claimed in the markup");
  assert.ok(!("aggregateRating" in app) && !("review" in app), "no ratings or reviews are invented");
  const types = jsonLd(read("lenscrib/index.html")).map((n) => n["@type"]);
  assert.deepEqual(types.sort(), ["BreadcrumbList", "FAQPage", "SoftwareApplication"]);
});

test("the page is wired to the delivery and checkout functions and carries the shared head tags", () => {
  const html = read("lenscrib/index.html");
  assert.match(html, /data-lcb-href="\/\.netlify\/functions\/lenscrib-download\?download=1"/);
  assert.match(html, /id="checkout-btn" data-product="lenscrib"/);
  assert.match(html, /paid-tool-landing\.js/);
  assert.match(html, /\/lenscrib\/launch\.js/);
  assert.match(html, /\/trial-reminder\.js/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/lenscrib\/">/);
  assert.match(html, /\/theme\.js/);
  assert.match(html, /<link rel="stylesheet" href="\/lenscrib\/lenscrib\.css/);
});

test("the page has every section the brief asks for", () => {
  const html = read("lenscrib/index.html");
  for (const id of ["how-h", "does-h", "not-h", "privacy-h", "price-h", "req-h", "faq-heading"]) {
    assert.match(html, new RegExp(`id="${id}"`), id);
  }
  const text = visibleText(html);
  for (const heading of ["What it does", "What it will not do", "Privacy and what downloads", "Price and trial", "System requirements", "Frequently asked questions"]) {
    assert.ok(text.includes(heading), heading);
  }
});

// ---- the release gate ------------------------------------------------------------------

test("PRE-LAUNCH GUARD: the page ships switched off, unlisted, and says so (delete this test when launching)", () => {
  const src = read("lenscrib/launch.js");
  assert.match(src, /live: false,/);
  assert.match(src, /version: "",/);
  assert.match(src, /sizeMb: "",/);
  assert.match(src, /released: ""/);
  const html = read("lenscrib/index.html");
  const trialTags = [...html.matchAll(/<a\b[^>]*data-lcb-gated[^>]*>/g)].map((m) => m[0]);
  assert.ok(trialTags.length >= 2);
  for (const tag of trialTags) {
    assert.doesNotMatch(tag, /\shref=/, "no href until launch");
    assert.match(tag, /aria-disabled="true"/);
  }
  assert.match(html, /<button\b[^>]*id="checkout-btn"[^>]*\sdisabled/);
  assert.match(html, /Not released yet/);
  assert.match(html, /<meta name="robots" content="noindex, follow">/, "unlisted until the launch change flips it");
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
    pre: new FakeEl({ "data-lcb-pre-only": "" }),
    live: new FakeEl({ "data-lcb-live-only": "", hidden: "" }),
    trial: new FakeEl({ "data-lcb-gated": "", "data-lcb-href": "/.netlify/functions/lenscrib-download?download=1", "data-lcb-live-text": "Try it free for 7 days", "aria-disabled": "true", __text: "Free trial opens at release" }),
    buy: new FakeEl({ "data-lcb-gated": "", "data-lcb-live-text": "Buy Lenscrib", disabled: "", __text: "Buying opens at release" }),
    facts: new FakeEl({ "data-lcb-facts": "", __text: "placeholder" }),
    sticky: new FakeEl({ "data-lcb-sticky": "" }),
  };
  const by = { "[data-lcb-pre-only]": [els.pre], "[data-lcb-live-only]": [els.live], "[data-lcb-gated]": [els.trial, els.buy], "[data-lcb-facts]": [els.facts], "[data-lcb-sticky]": [els.sticky] };
  const warnings = [];
  const ctx = {
    window: { console: { warn: (m) => warnings.push(m) } },
    document: { readyState: "complete", querySelectorAll: (s) => by[s] || [], addEventListener() {} },
    console: { warn: (m) => warnings.push(m) },
    Date, String, Array,
  };
  ctx.window.LENSCRIB_LAUNCH = undefined;
  const src = read("lenscrib/launch.js").replace(/window\.LENSCRIB_LAUNCH = \{[\s\S]*?\};/, `window.LENSCRIB_LAUNCH = ${JSON.stringify(config)};`);
  vm.runInNewContext(src, ctx);
  return { els, warnings };
}

test("with live false the gated controls stay dead and the sticky bar is removed", () => {
  const { els } = runLaunch({ live: false, version: "1.0.0", sizeMb: "140", released: "2026-10-20" });
  assert.equal(els.trial.getAttribute("href"), null);
  assert.equal(els.trial.getAttribute("aria-disabled"), "true");
  assert.equal(els.buy.disabled, true);
  assert.equal(els.live.hidden, true);
  assert.equal(els.sticky.removed, true);
});

test("live true with every fact valid enables the trial link and Buy button and fills in the facts", () => {
  const { els } = runLaunch({ live: true, version: "1.0.0", sizeMb: "140", released: "2026-10-20" });
  assert.equal(els.trial.getAttribute("href"), "/.netlify/functions/lenscrib-download?download=1");
  assert.equal(els.trial.getAttribute("aria-disabled"), null);
  assert.equal(els.trial.textContent, "Try it free for 7 days");
  assert.equal(els.buy.disabled, false);
  assert.equal(els.buy.textContent, "Buy Lenscrib");
  assert.equal(els.live.hidden, false);
  assert.equal(els.pre.hidden, true);
  assert.equal(els.facts.textContent, "Version 1.0.0, released October 20, 2026. 140 MB disk image.");
  assert.ok(!els.sticky.removed);
});

test("live true with a missing or malformed fact stays switched off and says why", () => {
  for (const bad of [
    { live: true, version: "", sizeMb: "140", released: "2026-10-20" },
    { live: true, version: "1.0", sizeMb: "140", released: "2026-10-20" },
    { live: true, version: "1.0.0", sizeMb: "", released: "2026-10-20" },
    { live: true, version: "1.0.0", sizeMb: "140 MB", released: "2026-10-20" },
    { live: true, version: "1.0.0", sizeMb: "140", released: "" },
    { live: true, version: "1.0.0", sizeMb: "140", released: "20 Oct 2026" },
    { live: "true", version: "1.0.0", sizeMb: "140", released: "2026-10-20" },
  ]) {
    const { els, warnings } = runLaunch(bad);
    assert.equal(els.trial.getAttribute("href"), null, JSON.stringify(bad));
    assert.equal(els.buy.disabled, true, JSON.stringify(bad));
    if (bad.live === true) assert.ok(warnings.some((w) => /stays switched off/.test(w)), JSON.stringify(bad));
  }
});

// ---- copy rules ------------------------------------------------------------------------

test("the Lenscrib pages have no inline styles, em or en dashes or emoji", () => {
  for (const p of ["lenscrib/index.html", "lenscrib/success/index.html", "lenscrib/launch.js", "lenscrib/success.js", "lenscrib/lenscrib.css"]) {
    const src = read(p);
    if (p.endsWith(".html")) assert.doesNotMatch(src, /<[a-z][^>]*\sstyle\s*=/i, `${p} has an inline style`);
    assert.doesNotMatch(src, /[–—]/, `${p} has an em or en dash`);
    assert.doesNotMatch(src, /\p{Extended_Pictographic}/u, `${p} has an emoji`);
  }
});

test("the page says what it cannot do, in plain words", () => {
  const text = visibleText(read("lenscrib/index.html")).toLowerCase();
  assert.match(text, /the model can be wrong/);
  assert.match(text, /guesses species and places/);
  assert.match(text, /you review every field before saving/);
  assert.match(text, /does not upload for you/);
  assert.match(text, /does not decide whether an agency accepts a photo/);
  assert.match(text, /macos 14/);
  assert.match(text, /apple silicon/);
  assert.match(text, /about 3 gb/);
  assert.match(text, /14 days/);
  assert.match(text, /two of your macs/);
  assert.match(text, /\$19\.99/);
});

test("the page names the five agencies, the free tool, and claims nothing the app brief does not say", () => {
  const html = read("lenscrib/index.html");
  const text = visibleText(html);
  for (const agency of ["Adobe Stock", "Shutterstock", "Alamy", "Vecteezy", "Dreamstime"]) assert.ok(text.includes(agency), agency);
  assert.match(html, /href="\/tools\/stock-keyword-cleaner\/"/);
  assert.match(text, /IPTC and XMP/);
  assert.doesNotMatch(text, /guarantee|certified|100% (private|accurate|secure)|always accurate|never (wrong|misses)|accepted by|approved by/i);
  assert.doesNotMatch(text, /seamless|supercharge|streamline|world-class|cutting-edge|revolutionary|effortless|AI-powered|game-chang|magic|blazing|lightning/i);
  // The brief gives no accuracy figures, so the page carries none.
  assert.doesNotMatch(text, /\d+(?:\.\d+)?%/, "a percentage appeared on the page");
  // Not built or not decided: not named.
  for (const unbuilt of ["upload to your agency account", "cloud sync", "team", "collaborat", "intel"]) {
    const hit = text.toLowerCase().includes(unbuilt.toLowerCase());
    if (unbuilt === "intel") assert.match(text, /There is no Intel version/);
    else assert.ok(!hit, `the page mentions: ${unbuilt}`);
  }
});

test("the page is not in the Mac Suite or the bundles, and says nothing about either", () => {
  const html = read("lenscrib/index.html");
  const main = html.slice(html.indexOf("<main"), html.indexOf("</main>"));
  assert.doesNotMatch(main, /\/suite\/|Mac Suite|bundle/i);
});

test("every image on the page exists, has a size and alt text, and none is an invented screenshot", () => {
  for (const p of ["lenscrib/index.html", "lenscrib/success/index.html"]) {
    const html = read(p);
    for (const [tag, src] of [...html.matchAll(/<img\b[^>]*src="([^"]+)"[^>]*>/g)].map((m) => [m[0], m[1]])) {
      assert.ok(src.startsWith("/"), `${src} is not a local path`);
      assert.ok(existsSync(join(SITE, src.split("?")[0])), `${src} is missing`);
      assert.match(tag, /\swidth="\d+"/);
      assert.match(tag, /\sheight="\d+"/);
      assert.match(tag, /\salt="[^"]*"/);
    }
    assert.doesNotMatch(html, /\/lenscrib\/img\//, "no picture is referenced until it exists");
    assert.doesNotMatch(html, /lenscrib-icon|og\/lenscrib\.png/, "no icon or share card is referenced until it exists");
  }
});

test("the stylesheets, scripts and fonts the pages load all exist", () => {
  for (const p of ["lenscrib/index.html", "lenscrib/success/index.html"]) {
    const html = read(p);
    const refs = [...html.matchAll(/<(?:link|script)\b[^>]*?(?:href|src)="(\/[^"?#]+\.(?:css|js|woff2|json|svg|png))(?:\?[^"]*)?"/g)].map((m) => m[1]);
    assert.ok(refs.length >= 5, `${p} loads ${refs.length} files`);
    for (const ref of refs) assert.ok(existsSync(join(SITE, ref)), `${p} loads ${ref} which is missing`);
  }
});

test("the success page is noindex, loads its script and has the download and key boxes", () => {
  const html = read("lenscrib/success/index.html");
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.match(html, /src="\/lenscrib\/success\.js/);
  assert.match(html, /id="downloads"/);
  assert.match(html, /id="license"/);
  assert.match(html, /macOS 14/);
  assert.match(html, /about 3 GB/);
});

// ---- Terms and Privacy ------------------------------------------------------------------

test("the Terms carry Lenscrib's own section: price, refund, two Macs, drafts, liability cap, not in the Suite", () => {
  const html = read("terms/index.html");
  assert.match(html, /<h2>Lenscrib: additional terms<\/h2>/);
  const section = html.slice(html.indexOf("<h2>Lenscrib: additional terms</h2>"), html.indexOf("<h2>Panely: additional terms</h2>"));
  assert.match(section, /\$19\.99 USD, once/);
  assert.match(section, /within 14 days of purchase/);
  assert.match(section, /full \$19\.99/);
  assert.match(section, /up to two of your own Macs/);
  assert.match(section, /Descriptions are drafts/);
  assert.match(section, /not part of the Mac Suite/);
  assert.match(section, /Liability cap for Lenscrib/);
  assert.match(html, /Tapefolio, Lenscrib, Panely and Summonly Mac apps/);
});

test("the Privacy page says what Lenscrib sends and does not send, and names its trial emails and recovery", () => {
  const html = read("privacy/index.html");
  assert.match(html, /<strong>Lenscrib<\/strong> has no account and no analytics/);
  assert.match(html, /does not upload your photos, their metadata or their locations/);
  assert.match(html, /Lenscrib trial emails<\/strong>/);
  assert.match(html, /Tapefolio, Lenscrib, Panely, Summonly, Mac Suite and kit purchases/);
});

test("nothing links to /lenscrib/ yet: no nav, footer, home, products, pricing, sitemap, search index or llms file", () => {
  for (const p of ["index.html", "products/index.html", "pricing/index.html", "suite/index.html", "sitemap.xml", "llms.txt", "pricing.md", "tools/stock-keyword-cleaner/index.html"]) {
    if (!existsSync(join(SITE, p))) continue;
    assert.doesNotMatch(read(p), /\/lenscrib\//, `${p} links to the unreleased page`);
  }
  if (existsSync(join(SITE, "search-index.json"))) assert.doesNotMatch(read("search-index.json"), /\/lenscrib\//);
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
  vm.runInNewContext(readFileSync(join(SITE, "lenscrib/success.js"), "utf8"), ctx);
  return { nodes, fetched };
}
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const SID = "cs_live_abcdefghij1234";

test("/lenscrib/success/ asks lenscrib-download for the session and shows a download button", async () => {
  const { nodes, fetched } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { files: [{ key: "Lenscrib-1.0.0.dmg", label: "Lenscrib 1.0.0 for macOS (disk image)", url: "/.netlify/functions/lenscrib-download?session_id=x&file=Lenscrib-1.0.0.dmg" }] }),
  });
  await tick();
  assert.deepEqual(fetched, [`/.netlify/functions/lenscrib-download?session_id=${SID}`]);
  assert.match(nodes.downloads.innerHTML, /Download: Lenscrib 1\.0\.0 for macOS/);
  assert.match(nodes.downloads.innerHTML, /lenscrib-download\?session_id=x&amp;file=Lenscrib-1\.0\.0\.dmg/);
});

test("/lenscrib/success/ shows the license key from the server", async () => {
  const KEY = "LCB1-ABCDE-FGHJK";
  const { nodes } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { license: KEY, files: [{ key: "Lenscrib-1.0.0.dmg", label: "Lenscrib 1.0.0 for macOS (disk image)", url: "/x" }] }),
  });
  await tick();
  const code = nodes.license.children.find((c) => c.tagName === "code");
  assert.ok(code, "a code element holds the key");
  assert.equal(code.textContent, KEY);
  assert.equal(code.attrs["aria-label"], "Your Lenscrib license key");
});

test("/lenscrib/success/ shows the server's reason when refused, and never fetches for a bad id", async () => {
  const refused = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(403, { error: "not_entitled", detail: "This order is for a different product." }) });
  await tick();
  assert.match(refused.nodes.downloads.innerHTML, /This order is for a different product\./);
  const bad = runSuccess({ search: "?session_id=nope", fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.equal(bad.fetched.length, 0);
  assert.match(bad.nodes.downloads.innerHTML, /receipt email/);
});
