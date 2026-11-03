// The Née pages, checked as files: the offer in the structured data, the release gate
// (launch.js is switched on and the static page says the same), the
// copy rules (what the page may and may not claim), and the success page's script run against
// a small fake DOM.
//
// Run with: node --test netlify/tests/nee-site.test.mjs

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

test("the Née page offers the app at $14.99 once, with a 14-day refund, for macOS 14, in valid JSON-LD", () => {
  const nodes = jsonLd(read("nee/index.html"));
  const app = nodes.find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Née");
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
  const html = read("nee/index.html");
  assert.match(html, /data-nee-href="\/\.netlify\/functions\/nee-download\?trial=1"/);
  assert.match(html, /id="checkout-btn" data-product="nee"/);
  assert.match(html, /<video controls preload="none"[^>]*poster="\/assets\/video\/nee-poster\.webp"/, "the demo video does not load until played");
  assert.match(html, /paid-tool-landing\.js/);
  assert.match(html, /\/nee\/launch\.js/);
  assert.match(html, /\/trial-reminder\.js/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/nee\/">/);
  assert.match(html, /\/theme\.js/);
  assert.match(html, /<link rel="stylesheet" href="\/nee\/nee\.css/);
});

test("the page has every section the brief asks for", () => {
  const html = read("nee/index.html");
  for (const id of ["how-h", "tour-h", "does-h", "shots-h", "not-h", "privacy-h", "price-h", "req-h", "faq-heading"]) {
    assert.match(html, new RegExp(`id="${id}"`), id);
  }
  const text = visibleText(html);
  for (const heading of ["How it works", "What it does", "What it will not do", "Privacy and permissions", "Price and trial", "System requirements", "Frequently asked questions"]) {
    assert.ok(text.includes(heading), heading);
  }
});

// ---- the release gate ------------------------------------------------------------------

test("LAUNCHED: launch.js ships live with valid facts, and the static page already says the live wording", () => {
  const src = read("nee/launch.js");
  const cfg = JSON.parse(src.match(/window\.NEE_LAUNCH = (\{[\s\S]*?\});/)[1].replace(/(\w+):/g, '"$1":'));
  assert.equal(cfg.live, true);
  assert.match(cfg.version, /^\d+\.\d+\.\d+$/);
  assert.match(cfg.sizeMb, /^\d{1,4}$/);
  assert.match(cfg.released, /^\d{4}-\d{2}-\d{2}$/);
  // The staged 1.0.0 disk image is 5,060,892 bytes, 5 MB to the nearest whole megabyte.
  if (cfg.version === "1.0.0") assert.equal(Math.round(5060892 / 1e6), Number(cfg.sizeMb));
  const html = read("nee/index.html");
  const gated = [...html.matchAll(/<a\b[^>]*data-nee-gated[^>]*>/g)].map((m) => m[0]);
  assert.ok(gated.length >= 2);
  for (const tag of gated) {
    assert.match(tag, /\shref="\/\.netlify\/functions\/nee-download\?trial=1"/);
    assert.doesNotMatch(tag, /aria-disabled/);
  }
  assert.doesNotMatch(html, /<button\b[^>]*id="checkout-btn"[^>]*\sdisabled/);
  assert.match(html, /id="checkout-btn" data-product="nee"[^>]*>Buy Née<\/button>/);
  assert.doesNotMatch(html, /Not released yet|opens at release|are listed here when|data-nee-pre-only/);
  assert.doesNotMatch(html, /data-nee-live-only hidden/);
  assert.equal([...html.matchAll(/>Try it free for 7 days<\/a>/g)].length, 2);
  // What launch.js would write into the page is exactly what the static page already says.
  const nice = new Date(cfg.released + "T00:00:00Z").toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
  const facts = `Version ${cfg.version}, released ${nice}. ${cfg.sizeMb} MB disk image.`;
  assert.ok(html.includes(`<span data-nee-facts>${facts}</span>`), "the static facts match launch.js");
  assert.match(html, /<meta name="robots" content="index, follow">/);
  const llms = read("llms.txt");
  assert.ok(llms.slice(llms.indexOf("### Née (macOS)")).includes(`**Status:** Shipping, version ${cfg.version}`));
  const sm = read("sitemap.xml").match(/<loc>https:\/\/purplelink\.llc\/nee\/<\/loc>\s*<lastmod>(\d{4}-\d{2}-\d{2})<\/lastmod>/);
  assert.ok(sm, "nee is listed in the sitemap with a lastmod");
  assert.ok(sm[1] >= "2026-11-02", `nee lastmod ${sm[1]} is on or after the launch day`);
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
    pre: new FakeEl({ "data-nee-pre-only": "" }),
    live: new FakeEl({ "data-nee-live-only": "", hidden: "" }),
    trial: new FakeEl({ "data-nee-gated": "", "data-nee-href": "/.netlify/functions/nee-download?trial=1", "data-nee-live-text": "Try it free for 7 days", "aria-disabled": "true", __text: "Free trial opens at release" }),
    buy: new FakeEl({ "data-nee-gated": "", "data-nee-live-text": "Buy Née", disabled: "", __text: "Buying opens at release" }),
    facts: new FakeEl({ "data-nee-facts": "", __text: "placeholder" }),
    sticky: new FakeEl({ "data-nee-sticky": "" }),
  };
  const by = { "[data-nee-pre-only]": [els.pre], "[data-nee-live-only]": [els.live], "[data-nee-gated]": [els.trial, els.buy], "[data-nee-facts]": [els.facts], "[data-nee-sticky]": [els.sticky] };
  const warnings = [];
  const ctx = {
    window: { console: { warn: (m) => warnings.push(m) } },
    document: { readyState: "complete", querySelectorAll: (s) => by[s] || [], addEventListener() {} },
    console: { warn: (m) => warnings.push(m) },
    Date, String, Array,
  };
  ctx.window.NEE_LAUNCH = undefined;
  const src = read("nee/launch.js").replace(/window\.NEE_LAUNCH = \{[\s\S]*?\};/, `window.NEE_LAUNCH = ${JSON.stringify(config)};`);
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
  assert.equal(els.trial.getAttribute("href"), "/.netlify/functions/nee-download?trial=1");
  assert.equal(els.trial.getAttribute("aria-disabled"), null);
  assert.equal(els.trial.textContent, "Try it free for 7 days");
  assert.equal(els.buy.disabled, false);
  assert.equal(els.buy.textContent, "Buy Née");
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

test("the Née pages have no inline styles, em or en dashes or emoji", () => {
  for (const p of ["nee/index.html", "nee/success/index.html", "nee/launch.js", "nee/success.js", "nee/nee.css"]) {
    const src = read(p);
    if (p.endsWith(".html")) assert.doesNotMatch(src, /<[a-z][^>]*\sstyle\s*=/i, `${p} has an inline style`);
    assert.doesNotMatch(src, /[–—]/, `${p} has an em or en dash`);
    assert.doesNotMatch(src, /\p{Extended_Pictographic}/u, `${p} has an emoji`);
  }
});

test("the page says what it cannot do, in plain words", () => {
  const text = visibleText(read("nee/index.html")).toLowerCase();
  assert.match(text, /the page layout is not kept/);
  assert.match(text, /background removal is poor on some images/);
  assert.match(text, /depend on what the mac supports/);
  assert.match(text, /nothing you drop on née is uploaded/);
  assert.match(text, /renames the originals/);
  assert.match(text, /macos 14/);
  assert.match(text, /apple silicon or intel/);
  assert.match(text, /14 days/);
  assert.match(text, /two of your macs/);
  assert.match(text, /\$14\.99/);
  assert.match(text, /51 actions/);
});

test("the page claims nothing the app does not do, and uses none of the banned words", () => {
  const html = read("nee/index.html");
  const text = visibleText(html);
  assert.doesNotMatch(text, /guarantee|certified|100% (private|accurate|secure)|always accurate|never (wrong|misses)/i);
  assert.doesNotMatch(text, /seamless|supercharge|streamline|world-class|cutting-edge|revolutionary|effortless|AI-powered|game-chang|magic|blazing|lightning|powerful|best-in-class/i);
  assert.doesNotMatch(text, /\d+(?:\.\d+)?%/, "a percentage appeared on the page");
  // Not built in this version, so not promised.
  for (const unbuilt of ["powerpoint to pdf", "excel to pdf", "libreoffice", "watch folder", "shortcuts", "app store", "cloud sync", "ffmpeg"]) {
    assert.ok(!text.toLowerCase().includes(unbuilt), `the page mentions: ${unbuilt}`);
  }
  // The action count is the app's own catalog.
  assert.match(text, /51 actions/);
});

test("the page says Née is in the Mac Suite, links the Suite, and no longer says it is sold on its own", () => {
  const html = read("nee/index.html");
  const main = html.slice(html.indexOf("<main"), html.indexOf("</main>"));
  assert.match(main, /Also in the <a href="\/suite\/">Mac Suite<\/a>: [^<]*\bNée[^<]*\$59\.99 once/);
  assert.doesNotMatch(visibleText(html), /sold on its own|not (part of|in) the (Mac )?Suite/i);
});

test("every image on the page exists, has a size and alt text, and none is an invented screenshot", () => {
  for (const p of ["nee/index.html", "nee/success/index.html"]) {
    const html = read(p);
    for (const [tag, src] of [...html.matchAll(/<img\b[^>]*src="([^"]+)"[^>]*>/g)].map((m) => [m[0], m[1]])) {
      assert.ok(src.startsWith("/"), `${src} is not a local path`);
      assert.ok(existsSync(join(SITE, src.split("?")[0])), `${src} is missing`);
      assert.match(tag, /\swidth="\d+"/);
      assert.match(tag, /\sheight="\d+"/);
      assert.match(tag, /\salt="[^"]*"/);
    }
  }
  const page = read("nee/index.html");
  assert.match(page, /<meta property="og:image" content="https:\/\/purplelink\.llc\/assets\/og\/nee\.png">/);
  assert.match(page, /<meta name="twitter:image" content="https:\/\/purplelink\.llc\/assets\/og\/nee\.png">/);
  assert.match(page, /<meta name="twitter:card" content="summary_large_image">/);
  const card = readFileSync(join(SITE, "assets/og/nee.png"));
  assert.equal(card.readUInt32BE(16), 1200);
  assert.equal(card.readUInt32BE(20), 630);
});

test("the demo video and its poster exist, and the page describes the video in text", () => {
  const html = read("nee/index.html");
  const src = html.match(/<source src="([^"]+)" type="video\/mp4">/)[1];
  assert.ok(existsSync(join(SITE, src)), `${src} is missing`);
  assert.ok(existsSync(join(SITE, "assets/video/nee-poster.webp")));
  assert.match(html, /aria-describedby="nee-video-desc"/);
  assert.match(visibleText(html), /The video is silent and has its own captions/);
});

test("the stylesheets, scripts and fonts the pages load all exist", () => {
  for (const p of ["nee/index.html", "nee/success/index.html"]) {
    const html = read(p);
    const refs = [...html.matchAll(/<(?:link|script)\b[^>]*?(?:href|src)="(\/[^"?#]+\.(?:css|js|woff2|json|svg|png))(?:\?[^"]*)?"/g)].map((m) => m[1]);
    assert.ok(refs.length >= 5, `${p} loads ${refs.length} files`);
    for (const ref of refs) assert.ok(existsSync(join(SITE, ref)), `${p} loads ${ref} which is missing`);
  }
});

test("the success page is noindex, loads its script and has the download and key boxes", () => {
  const html = read("nee/success/index.html");
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.match(html, /src="\/nee\/success\.js/);
  assert.match(html, /id="downloads"/);
  assert.match(html, /macOS 14/);
  assert.match(html, /data-license-keys/);
  assert.match(html, /src="\/license-keys\.js/);
});

// ---- Terms and Privacy ------------------------------------------------------------------

test("the Terms carry Née's own section: price, refund, two Macs, new files, liability cap", () => {
  const html = read("terms/index.html");
  assert.match(html, /<h2>Née: additional terms<\/h2>/);
  const section = html.slice(html.indexOf("<h2>Née: additional terms</h2>"), html.indexOf("<h2>Panely: additional terms</h2>"));
  assert.match(section, /\$14\.99 USD, once/);
  assert.match(section, /within 14 days of purchase/);
  assert.match(section, /full \$14\.99/);
  assert.match(section, /up to two of your own Macs/);
  assert.match(section, /Results are new files/);
  assert.match(section, /Liability cap for Née/);
  assert.match(html, /Tapefolio, Lenscrib, Née, Panely and Summonly Mac apps/);
});

test("the Privacy page says what Née sends and does not send, and names its trial emails and recovery", () => {
  const html = read("privacy/index.html");
  assert.match(html, /<strong>Née<\/strong> has no account and no analytics/);
  assert.match(html, /does not upload your files, their contents or their names/);
  assert.match(html, /Née trial emails<\/strong>/);
  assert.match(html, /Lenscrib, Née, Panely, Summonly, Mac Suite and kit purchases/);
});

test("Née is linked where the other live Mac apps are: nav, footer, home, products, pricing, Suite, sitemap, search index, llms files", () => {
  for (const p of ["index.html", "products/index.html", "pricing/index.html", "suite/index.html", "sitemap.xml", "llms.txt", "pricing.md", "legroom/index.html", "404.html"]) {
    assert.match(read(p), /\/nee\//, `${p} does not link /nee/`);
  }
  assert.match(read("site.js"), /\/nee\//);
  assert.match(read("analytics.js"), /nee-download\?trial=1[\s\S]{0,120}nee_trial_download/);
  assert.match(read("analytics.js"), /\|nee_trial_download\|/);
  assert.match(read("llms-full.txt"), /https:\/\/purplelink\.llc\/nee\//);
  assert.match(read("search-index.json"), /\/nee\//);
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
  vm.runInNewContext(readFileSync(join(SITE, "nee/success.js"), "utf8"), ctx);
  return { nodes, fetched };
}
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const SID = "cs_live_abcdefghij1234";

test("/nee/success/ asks nee-download for the session and shows a download button", async () => {
  const { nodes, fetched } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { files: [{ key: "Nee-1.0.0.dmg", label: "Née 1.0.0 for macOS (disk image)", url: "/.netlify/functions/nee-download?session_id=x&file=Nee-1.0.0.dmg" }] }),
  });
  await tick();
  assert.deepEqual(fetched, [`/.netlify/functions/nee-download?session_id=${SID}`]);
  assert.match(nodes.downloads.innerHTML, /Download: Née 1\.0\.0 for macOS/);
  assert.match(nodes.downloads.innerHTML, /nee-download\?session_id=x&amp;file=Nee-1\.0\.0\.dmg/);
});

test("/nee/success/ shows the server's reason when refused, and never fetches for a bad id", async () => {
  const refused = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(403, { error: "not_entitled", detail: "This order is for a different product." }) });
  await tick();
  assert.match(refused.nodes.downloads.innerHTML, /This order is for a different product\./);
  const bad = runSuccess({ search: "?session_id=nope", fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.equal(bad.fetched.length, 0);
  assert.match(bad.nodes.downloads.innerHTML, /receipt email/);
});

// ---- spelling: "Née" for people, ASCII "nee" for machines (Ben, 2026-11-02) ------------------
test("the product name reads Née, and every URL, id and file name uses ASCII nee", () => {
  for (const p of ["nee/index.html", "nee/success/index.html", "guides/free-offline-file-converters-mac/index.html", "suite/index.html"]) {
    const html = read(p);
    const text = visibleText(html);
    assert.match(text, /Née/, `${p}: the name is shown as Née`);
    assert.doesNotMatch(text, /\bNee\b(?!-\d)/, `${p}: no unaccented "Nee" in visible text (file names like Nee-1.0.0.dmg are ASCII on purpose)`);
    assert.doesNotMatch(text, /\bAKA\b/, `${p}: the old name is gone`);
    for (const m of html.matchAll(/(?:href|src|action|content)="([^"]*)"/g)) {
      if (/^(https?:\/\/purplelink\.llc)?\//.test(m[1])) assert.doesNotMatch(m[1], /[éÉ]|%C3%A9/i, `${p}: URL ${m[1]} is ASCII`);
    }
  }
  assert.ok(existsSync(join(SITE, "nee", "index.html")) && !existsSync(join(SITE, "aka")), "the page lives at /nee/, not /aka/");
});
