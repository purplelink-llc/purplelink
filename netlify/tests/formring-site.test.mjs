// The Formring pages, checked as files: the offer in the structured data, the release gate
// (the trial link and Buy button stay dead until site/formring/launch.js is flipped), the
// copy rules (what the page may and may not claim), and the success page's script run against
// a small fake DOM.
//
// Run with: node --test netlify/tests/formring-site.test.mjs

import "./_generated.mjs"; // builds search-index.json and llms-full.txt first
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const read = (p) => readFileSync(join(SITE, p), "utf8");
const jsonLd = (html) =>
  [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script[^>]*>/gi)].flatMap((m) => {
    const d = JSON.parse(m[1]);
    return d["@graph"] || [d];
  });
// Decoded in one pass, so "&amp;rsquo;" stays "&rsquo;" instead of being unescaped twice.
const ENTITIES = { nbsp: " ", middot: " ", rsquo: "'", "#39": "'", amp: "&" };
/** The text a reader sees: no scripts, styles, comments or tags. */
const visibleText = (html) =>
  html.replace(/<script\b[\s\S]*?<\/script[^>]*>/gi, " ").replace(/<style\b[\s\S]*?<\/style[^>]*>/gi, " ").replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<[^>]+>/g, " ").replace(/&(nbsp|middot|rsquo|#39|amp);/g, (_m, e) => ENTITIES[e]).replace(/\s+/g, " ");

// ---- product page --------------------------------------------------------------------

test("the Formring page offers the app at $14.99 once, with a 14-day refund, for macOS 14, in valid JSON-LD", () => {
  const nodes = jsonLd(read("formring/index.html"));
  const app = nodes.find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Formring");
  assert.equal(app.offers.price, "14.99");
  assert.equal(app.offers.priceCurrency, "USD");
  assert.equal(app.offers.hasMerchantReturnPolicy.merchantReturnDays, 14);
  assert.equal(app.operatingSystem, "macOS 14+");
  assert.equal(app.processorRequirements, undefined, "it runs on Apple silicon and Intel, so no processor is required");
  assert.equal(app.offers.availability, undefined, "no availability is claimed in the markup");
  assert.ok(!("aggregateRating" in app) && !("review" in app), "no ratings or reviews are invented");
  assert.deepEqual(nodes.map((n) => n["@type"]).sort(), ["BreadcrumbList", "FAQPage", "SoftwareApplication"]);
});

test("the page is wired to the delivery and checkout functions and carries the shared head tags", () => {
  const html = read("formring/index.html");
  assert.match(html, /data-fr-href="\/\.netlify\/functions\/formring-download\?trial=1"/);
  assert.match(html, /id="checkout-btn" data-product="formring"/);
  assert.match(html, /<video controls preload="none"[^>]*poster="\/assets\/video\/formring-poster\.webp"/, "the demo video does not load until played");
  assert.match(html, /paid-tool-landing\.js/);
  assert.match(html, /\/formring\/launch\.js/);
  assert.match(html, /\/trial-reminder\.js/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/formring\/">/);
  assert.match(html, /\/theme\.js/);
  assert.match(html, /<link rel="stylesheet" href="\/formring\/formring\.css/);
});

test("the page has every section the brief asks for", () => {
  const html = read("formring/index.html");
  for (const id of ["how-h", "tour-h", "does-h", "shots-h", "not-h", "privacy-h", "price-h", "req-h", "faq-heading"]) {
    assert.match(html, new RegExp(`id="${id}"`), id);
  }
  const text = visibleText(html);
  for (const heading of ["How it works", "What it does", "What it will not do", "Privacy and permissions", "Price and trial", "System requirements", "Frequently asked questions"]) {
    assert.ok(text.includes(heading), heading);
  }
});

// ---- the release gate ------------------------------------------------------------------

test("PRE-LAUNCH GUARD: the page ships switched off, unlisted, and says so (delete this test when launching)", () => {
  const src = read("formring/launch.js");
  assert.match(src, /live: false,/);
  assert.match(src, /version: "",/);
  assert.match(src, /sizeMb: "",/);
  assert.match(src, /released: ""/);
  const html = read("formring/index.html");
  const trialTags = [...html.matchAll(/<a\b[^>]*data-fr-gated[^>]*>/g)].map((m) => m[0]);
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
    pre: new FakeEl({ "data-fr-pre-only": "" }),
    live: new FakeEl({ "data-fr-live-only": "", hidden: "" }),
    trial: new FakeEl({ "data-fr-gated": "", "data-fr-href": "/.netlify/functions/formring-download?trial=1", "data-fr-live-text": "Try it free for 7 days", "aria-disabled": "true", __text: "Free trial opens at release" }),
    buy: new FakeEl({ "data-fr-gated": "", "data-fr-live-text": "Buy Formring", disabled: "", __text: "Buying opens at release" }),
    facts: new FakeEl({ "data-fr-facts": "", __text: "placeholder" }),
    sticky: new FakeEl({ "data-fr-sticky": "" }),
  };
  const by = { "[data-fr-pre-only]": [els.pre], "[data-fr-live-only]": [els.live], "[data-fr-gated]": [els.trial, els.buy], "[data-fr-facts]": [els.facts], "[data-fr-sticky]": [els.sticky] };
  const warnings = [];
  const ctx = {
    window: { console: { warn: (m) => warnings.push(m) } },
    document: { readyState: "complete", querySelectorAll: (s) => by[s] || [], addEventListener() {} },
    console: { warn: (m) => warnings.push(m) },
    Date, String, Array,
  };
  ctx.window.FORMRING_LAUNCH = undefined;
  const src = read("formring/launch.js").replace(/window\.FORMRING_LAUNCH = \{[\s\S]*?\};/, `window.FORMRING_LAUNCH = ${JSON.stringify(config)};`);
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
  assert.equal(els.trial.getAttribute("href"), "/.netlify/functions/formring-download?trial=1");
  assert.equal(els.trial.getAttribute("aria-disabled"), null);
  assert.equal(els.trial.textContent, "Try it free for 7 days");
  assert.equal(els.buy.disabled, false);
  assert.equal(els.buy.textContent, "Buy Formring");
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

test("the Formring pages have no inline styles, em or en dashes or emoji", () => {
  for (const p of ["formring/index.html", "formring/success/index.html", "formring/launch.js", "formring/success.js", "formring/formring.css"]) {
    const src = read(p);
    if (p.endsWith(".html")) assert.doesNotMatch(src, /<[a-z][^>]*\sstyle\s*=/i, `${p} has an inline style`);
    assert.doesNotMatch(src, /[–—]/, `${p} has an em or en dash`);
    assert.doesNotMatch(src, /\p{Extended_Pictographic}/u, `${p} has an emoji`);
  }
});

test("the page says what it cannot do, in plain words", () => {
  const text = visibleText(read("formring/index.html")).toLowerCase();
  assert.match(text, /the page layout is not kept/);
  assert.match(text, /background removal is poor on some images/);
  assert.match(text, /depend on what the mac supports/);
  assert.match(text, /nothing you drop on formring is uploaded/);
  assert.match(text, /renames the originals/);
  assert.match(text, /macos 14/);
  assert.match(text, /apple silicon or intel/);
  assert.match(text, /14 days/);
  assert.match(text, /two of your macs/);
  assert.match(text, /\$14\.99/);
  assert.match(text, /50 actions/);
});

test("the page claims nothing the app does not do, and uses none of the banned words", () => {
  const html = read("formring/index.html");
  const text = visibleText(html);
  assert.doesNotMatch(text, /guarantee|certified|100% (private|accurate|secure)|always accurate|never (wrong|misses)/i);
  assert.doesNotMatch(text, /seamless|supercharge|streamline|world-class|cutting-edge|revolutionary|effortless|AI-powered|game-chang|magic|blazing|lightning|powerful|best-in-class/i);
  assert.doesNotMatch(text, /\d+(?:\.\d+)?%/, "a percentage appeared on the page");
  // Not built in this version, so not promised.
  for (const unbuilt of ["powerpoint to pdf", "excel to pdf", "libreoffice", "watch folder", "shortcuts", "app store", "cloud sync", "ffmpeg"]) {
    assert.ok(!text.toLowerCase().includes(unbuilt), `the page mentions: ${unbuilt}`);
  }
  // The action count is the app's own catalog.
  assert.match(text, /50 actions/);
});

test("the page says nothing about the Mac Suite or the bundles (the Suite gate is a launch decision, see docs/products/formring.md)", () => {
  const html = read("formring/index.html");
  const main = html.slice(html.indexOf("<main"), html.indexOf("</main>"));
  assert.doesNotMatch(main, /\/suite\/|Mac Suite|bundle/i);
});

test("every image on the page exists, has a size and alt text, and none is an invented screenshot", () => {
  for (const p of ["formring/index.html", "formring/success/index.html"]) {
    const html = read(p);
    for (const [tag, src] of [...html.matchAll(/<img\b[^>]*src="([^"]+)"[^>]*>/g)].map((m) => [m[0], m[1]])) {
      assert.ok(src.startsWith("/"), `${src} is not a local path`);
      assert.ok(existsSync(join(SITE, src.split("?")[0])), `${src} is missing`);
      assert.match(tag, /\swidth="\d+"/);
      assert.match(tag, /\sheight="\d+"/);
      assert.match(tag, /\salt="[^"]*"/);
    }
    assert.doesNotMatch(html, /og\/formring\.png/, "no share card is referenced until it exists");
  }
});

test("the demo video and its poster exist, and the page describes the video in text", () => {
  const html = read("formring/index.html");
  const src = html.match(/<source src="([^"]+)" type="video\/mp4">/)[1];
  assert.ok(existsSync(join(SITE, src)), `${src} is missing`);
  assert.ok(existsSync(join(SITE, "assets/video/formring-poster.webp")));
  assert.match(html, /aria-describedby="fr-video-desc"/);
  assert.match(visibleText(html), /The video is silent and has its own captions/);
});

test("the stylesheets, scripts and fonts the pages load all exist", () => {
  for (const p of ["formring/index.html", "formring/success/index.html"]) {
    const html = read(p);
    const refs = [...html.matchAll(/<(?:link|script)\b[^>]*?(?:href|src)="(\/[^"?#]+\.(?:css|js|woff2|json|svg|png))(?:\?[^"]*)?"/g)].map((m) => m[1]);
    assert.ok(refs.length >= 5, `${p} loads ${refs.length} files`);
    for (const ref of refs) assert.ok(existsSync(join(SITE, ref)), `${p} loads ${ref} which is missing`);
  }
});

test("the success page is noindex, loads its script and has the download and key boxes", () => {
  const html = read("formring/success/index.html");
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.match(html, /src="\/formring\/success\.js/);
  assert.match(html, /id="downloads"/);
  assert.match(html, /macOS 14/);
  assert.match(html, /data-license-keys/);
  assert.match(html, /src="\/license-keys\.js/);
});

// ---- Terms and Privacy ------------------------------------------------------------------

test("the Terms carry Formring's own section: price, refund, two Macs, new files, liability cap", () => {
  const html = read("terms/index.html");
  assert.match(html, /<h2>Formring: additional terms<\/h2>/);
  const section = html.slice(html.indexOf("<h2>Formring: additional terms</h2>"), html.indexOf("<h2>Panely: additional terms</h2>"));
  assert.match(section, /\$14\.99 USD, once/);
  assert.match(section, /within 14 days of purchase/);
  assert.match(section, /full \$14\.99/);
  assert.match(section, /up to two of your own Macs/);
  assert.match(section, /Results are new files/);
  assert.match(section, /Liability cap for Formring/);
  assert.match(html, /Tapefolio, Lenscrib, Formring, Panely and Summonly Mac apps/);
});

test("the Privacy page says what Formring sends and does not send, and names its trial emails and recovery", () => {
  const html = read("privacy/index.html");
  assert.match(html, /<strong>Formring<\/strong> has no account and no analytics/);
  assert.match(html, /does not upload your files, their contents or their names/);
  assert.match(html, /Formring trial emails<\/strong>/);
  assert.match(html, /Lenscrib, Formring, Panely, Summonly, Mac Suite and kit purchases/);
});

test("nothing links to /formring/ yet: no nav, footer, home, products, pricing, sitemap, search index or llms file", () => {
  for (const p of ["index.html", "products/index.html", "pricing/index.html", "suite/index.html", "sitemap.xml", "llms.txt", "llms-full.txt", "pricing.md", "changelog/index.html", "support/index.html", "recover/index.html", "search/index.html", "lenscrib/index.html", "legroom/index.html"]) {
    if (!existsSync(join(SITE, p))) continue;
    assert.doesNotMatch(read(p), /\/formring\//, `${p} links to the unreleased page`);
  }
  if (existsSync(join(SITE, "search-index.json"))) assert.doesNotMatch(read("search-index.json"), /\/formring\//);
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
  vm.runInNewContext(readFileSync(join(SITE, "formring/success.js"), "utf8"), ctx);
  return { nodes, fetched };
}
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const SID = "cs_live_abcdefghij1234";

test("/formring/success/ asks formring-download for the session and shows a download button", async () => {
  const { nodes, fetched } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { files: [{ key: "Formring-1.0.0.dmg", label: "Formring 1.0.0 for macOS (disk image)", url: "/.netlify/functions/formring-download?session_id=x&file=Formring-1.0.0.dmg" }] }),
  });
  await tick();
  assert.deepEqual(fetched, [`/.netlify/functions/formring-download?session_id=${SID}`]);
  assert.match(nodes.downloads.innerHTML, /Download: Formring 1\.0\.0 for macOS/);
  assert.match(nodes.downloads.innerHTML, /formring-download\?session_id=x&amp;file=Formring-1\.0\.0\.dmg/);
});

test("/formring/success/ shows the server's reason when refused, and never fetches for a bad id", async () => {
  const refused = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(403, { error: "not_entitled", detail: "This order is for a different product." }) });
  await tick();
  assert.match(refused.nodes.downloads.innerHTML, /This order is for a different product\./);
  const bad = runSuccess({ search: "?session_id=nope", fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.equal(bad.fetched.length, 0);
  assert.match(bad.nodes.downloads.innerHTML, /receipt email/);
});
