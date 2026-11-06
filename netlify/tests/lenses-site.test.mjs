// The Lenses pages, checked as files: the offer in the structured data, the copy rules,
// the Buy button wiring, the success page script run against a small fake DOM, and the guide.
//
// Run with: node --test netlify/tests/lenses-site.test.mjs

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
const ENTITIES = { nbsp: " ", middot: " ", rsquo: "'", ldquo: '"', rdquo: '"', "#39": "'", amp: "&" };
const visibleText = (html) =>
  html.replace(/<script\b[\s\S]*?<\/script[^>]*>/gi, " ").replace(/<style\b[\s\S]*?<\/style[^>]*>/gi, " ").replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<[^>]+>/g, " ").replace(/&(nbsp|middot|rsquo|ldquo|rdquo|#39|amp);/g, (_m, e) => ENTITIES[e]).replace(/\s+/g, " ");
const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F2FF}]/u;

const PAGES = ["lenses/index.html", "lenses/success/index.html", "guides/ar-glasses-mac-setup/index.html"];

test("the pages exist", () => {
  for (const p of PAGES) assert.ok(existsSync(join(SITE, p)), p);
  assert.ok(existsSync(join(SITE, "lenses/success.js")));
  assert.ok(existsSync(join(SITE, "assets/og/lenses.png")));
});

test("the Lenses page offers the app at $4.99 once, in stock, with a 14-day refund, for macOS 14, in valid JSON-LD", () => {
  const nodes = jsonLd(read("lenses/index.html"));
  const app = nodes.find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Lenses");
  assert.equal(app.offers.price, "4.99");
  assert.equal(app.offers.priceCurrency, "USD");
  assert.equal(app.offers.hasMerchantReturnPolicy.merchantReturnDays, 14);
  assert.equal(app.operatingSystem, "macOS 14+");
  assert.ok(!("aggregateRating" in app) && !("review" in app));
  assert.deepEqual(nodes.map((n) => n["@type"]).sort(), ["BreadcrumbList", "FAQPage", "SoftwareApplication", "VideoObject"]);
});

test("the page is indexed, canonical and posts product lenses to checkout", () => {
  const html = read("lenses/index.html");
  assert.match(html, /<meta name="robots" content="index, follow">/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/lenses\/">/);
  assert.match(html, /id="checkout-btn"[^>]*data-product="lenses"/);
  assert.doesNotMatch(html, /id="checkout-btn"[^>]*disabled/);
  assert.match(html, /paid-tool-landing\.js/);
  const js = read("tools/paper-review/paid-tool-landing.js");
  assert.match(js, /\/\.netlify\/functions\/checkout/);
  assert.match(js, /data-product/);
});

test("the page carries the required claims", () => {
  const text = visibleText(read("lenses/index.html"));
  assert.ok(text.includes("Tested on RayNeo Air."));
  assert.match(text, /collects nothing/);
  assert.match(text, /only network request it makes is the update check/);
  assert.match(text, /\$4\.99/);
  assert.match(text, /XREAL and VITURE/);
  assert.ok(text.includes('Use this display as my glasses'));
  assert.match(text, /macOS 14/);
  assert.match(text, /Apple silicon/);
  assert.match(text, /14 days/);
  assert.match(text, /7-day trial/);
  assert.match(text, /license key/i);
});

test("no page has an emoji, an inline style, a launch gate or an em dash", () => {
  for (const p of PAGES.concat(["lenses/success.js", "lenses/lenses.css"])) {
    const src = read(p);
    assert.ok(!EMOJI.test(src), `${p} has an emoji`);
    if (p.endsWith(".html")) {
      assert.doesNotMatch(src.replace(/<script\b[\s\S]*?<\/script[^>]*>/gi, " "), /\sstyle="/, `${p} has an inline style`);
      assert.doesNotMatch(visibleText(src), /—/, `${p} has an em dash`);
    }
  }
  assert.doesNotMatch(read("lenses/index.html"), /data-pf-|launch\.js/);
});

test("the success page calls lenses-download and shows the license key", () => {
  const html = read("lenses/success/index.html");
  const js = read("lenses/success.js");
  assert.match(html, /\/lenses\/success\.js/);
  assert.match(html, /id="downloads"/);
  assert.match(js, /\/\.netlify\/functions\/lenses-download\?session_id=/);
  assert.doesNotMatch(visibleText(html), /license key is/i);
  assert.match(html, /<meta name="robots" content="noindex/);
});

class FakeBox { constructor() { this.innerHTML = ""; } }

function runSuccess(search, fetchImpl) {
  const box = new FakeBox();
  const ctx = {
    document: { getElementById: (id) => (id === "downloads" ? box : null) },
    window: { location: { search } },
    URLSearchParams, encodeURIComponent, String, RegExp,
    fetch: fetchImpl,
  };
  vm.runInNewContext(read("lenses/success.js"), ctx);
  return box;
}

test("the success script lists the returned files, and rejects a bad session id without a request", async () => {
  let calls = [];
  const box = runSuccess("?session_id=cs_live_abcdefghij1234", (url) => {
    calls.push(url);
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ files: [{ url: "/dl/Lenses-1.0.0.dmg", label: "Lenses 1.0.0 (disk image)" }] }) });
  });
  await new Promise((r) => setTimeout(r, 10));
  assert.deepEqual(calls, ["/.netlify/functions/lenses-download?session_id=cs_live_abcdefghij1234"]);
  assert.match(box.innerHTML, /Download: Lenses 1\.0\.0 \(disk image\)/);
  assert.match(box.innerHTML, /href="\/dl\/Lenses-1\.0\.0\.dmg"/);

  calls = [];
  const bad = runSuccess("?session_id=nope", (u) => { calls.push(u); return Promise.reject(new Error("no")); });
  assert.equal(calls.length, 0);
  assert.match(bad.innerHTML, /receipt email/);
});

test("the guide has the 8 steps in order, links to /lenses/ and mentions RayNeo Air", () => {
  const html = read("guides/ar-glasses-mac-setup/index.html");
  const heads = [...html.matchAll(/<h2>Step (\d)\./g)].map((m) => Number(m[1]));
  assert.deepEqual(heads, [1, 2, 3, 4, 5, 6, 7, 8]);
  const step8 = html.slice(html.indexOf("<h2>Step 8."));
  assert.match(step8, /href="\/lenses\/"/);
  assert.match(step8, /RayNeo Air/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/guides\/ar-glasses-mac-setup\/">/);
  const types = jsonLd(html).map((n) => n["@type"]).sort();
  assert.deepEqual(types, ["Article", "BreadcrumbList", "FAQPage"]);
});

test("the listings include Lenses and the guide, and the Suite page lists it too", () => {
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/lenses\/<\/loc>/);
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/guides\/ar-glasses-mac-setup\/<\/loc>/);
  assert.match(read("llms.txt"), /### Lenses \(macOS\)/);
  assert.match(read("products/index.html"), /href="\/lenses\/"/);
  assert.match(read("pricing/index.html"), /href="\/lenses\/"/);
  assert.match(read("guides/index.html"), /\/guides\/ar-glasses-mac-setup\//);
  assert.match(read("suite/index.html"), /\/lenses\/[^>]*>See Lenses|>Lenses</);
});
