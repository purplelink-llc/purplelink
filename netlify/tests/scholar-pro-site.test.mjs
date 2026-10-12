// The Scholar Utility Belt Pro page, checked as a file: the facts it states (prices, trial, the early-install
// promise), the structured data (valid, matches the visible FAQ, no invented ratings), the copy rules (no emoji, no
// em dash, no inline style), the first-party click tags, and registration in the sitemap, llms.txt and the llms-full list.
//
// Run with: node --test netlify/tests/scholar-pro-site.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SITE = join(ROOT, "site");
const PAGE = "scholar-utility-belt/pro/index.html";
const read = (p) => readFileSync(join(SITE, p), "utf8");
const jsonLd = (html) =>
  [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].flatMap((m) => {
    const d = JSON.parse(m[1]);
    return d["@graph"] || [d];
  });
const visibleText = (html) =>
  html.replace(/<script\b[\s\S]*?<\/script>/gi, " ").replace(/<style\b[\s\S]*?<\/style>/gi, " ").replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, " ");
const STORE = "https://chromewebstore.google.com/detail/scholar-utility-belt/omcogfcgldfmihfogbffflbocdbjockn";

test("the page exists with the shared head tags and a canonical URL", () => {
  assert.ok(existsSync(join(SITE, PAGE)));
  const html = read(PAGE);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/scholar-utility-belt\/pro\/">/);
  assert.match(html, /<meta name="robots" content="index, follow">/);
  assert.match(html, /\/theme\.js/);
  assert.match(html, /\/styles\.css/);
  assert.match(html, /\/analytics\.js/);
  assert.match(html, /<h1>Scholar Utility Belt Pro<\/h1>/);
  const title = html.match(/<title>([^<]+)<\/title>/)[1];
  assert.ok(title.length <= 70, `title is ${title.length} characters`);
  const desc = html.match(/<meta name="description" content="([^"]+)"/)[1];
  assert.ok(desc.length >= 80 && desc.length <= 175, `description is ${desc.length} characters`);
});

test("it states exactly the prices, the 14-day trial and the early-install promise", () => {
  const text = visibleText(read(PAGE));
  assert.match(text, /\$40 once/);
  assert.match(text, /\$3 a month/);
  assert.match(text, /\$20 a year/);
  assert.match(text, /14-day trial/);
  assert.match(text, /App Pass/);
  assert.match(text, /before Pro/i);
  for (const f of ["Author compare", "Citation lineage", "Narrative CV", "Publish-or-Perish", "Citation-graph overlay", "Systematic-review workspace"]) {
    assert.ok(text.includes(f), f);
  }
  assert.ok(text.includes("There is no checkout on this site"));
  const prices = [...text.matchAll(/\$(\d+(?:\.\d+)?)/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(prices)].sort(), ["20", "3", "40"], "no other price appears on the page");
});

test("honest limits are stated", () => {
  const text = visibleText(read(PAGE));
  assert.match(text, /No institution has reviewed it/);
  assert.match(text, /AI is optional/);
  assert.match(text, /hedged/);
});

test("structured data is valid, has no ratings or reviews, and its FAQ matches the visible FAQ", () => {
  const html = read(PAGE);
  const nodes = jsonLd(html);
  assert.deepEqual(nodes.map((n) => n["@type"]).sort(), ["BreadcrumbList", "FAQPage", "WebPage"]);
  assert.ok(!/aggregateRating|ratingValue|reviewCount|"review"/.test(html), "no ratings or reviews");
  const faq = nodes.find((n) => n["@type"] === "FAQPage").mainEntity;
  assert.ok(faq.length >= 5);
  const visible = [...html.matchAll(/<details><summary>([\s\S]*?)<\/summary><div class="faq-body">([\s\S]*?)<\/div><\/details>/g)]
    .map((m) => [m[1], m[2]].map((s) => s.replace(/&amp;/g, "&").replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"')));
  assert.equal(visible.length, faq.length);
  faq.forEach((q, i) => {
    assert.equal(q.name, visible[i][0]);
    assert.equal(q.acceptedAnswer.text, visible[i][1]);
  });
  const crumbs = nodes.find((n) => n["@type"] === "BreadcrumbList").itemListElement;
  assert.equal(crumbs.at(-1).item, "https://purplelink.llc/scholar-utility-belt/pro/");
});

test("copy rules: no emoji, no em dash, no inline style, no third-party loads", () => {
  const html = read(PAGE);
  assert.ok(!/\p{Extended_Pictographic}/u.test(visibleText(html).replace(/[←-⇿]/g, "")), "no emoji");
  assert.ok(!html.includes("—"), "no em dash");
  assert.ok(!/<[a-z][^>]*\sstyle\s*=/i.test(html), "no inline style");
  const srcs = [...html.matchAll(/<(?:script|link)\b[^>]*(?:src|href)="(https?:[^"]+)"/g)].map((m) => m[1]).filter((u) => !u.includes("purplelink.llc"));
  assert.deepEqual(srcs, [], "no external scripts or stylesheets");
  for (const word of ["supercharge", "seamless", "streamline", "world-class", "unlock your", "game-chang"]) {
    assert.ok(!visibleText(html).toLowerCase().includes(word), word);
  }
});

test("links: the Web Store listing, the privacy section and the main page, with first-party click tags", () => {
  const html = read(PAGE);
  assert.ok(html.includes(`href="${STORE}"`));
  assert.ok(html.includes('href="/privacy/#scholar-utility-belt"'));
  assert.ok(html.includes('href="/scholar-utility-belt/"'));
  assert.ok(existsSync(join(SITE, "privacy/index.html")) && /id="scholar-utility-belt"/.test(read("privacy/index.html")));
  // Every outbound or CTA link the page counts goes through the site's own data-track beacon (analytics.js); nothing else is added.
  const tagged = [...html.matchAll(/<a\b[^>]*data-track="([^"]+)"[^>]*data-track-meta="([^"]+)"/g)];
  assert.ok(tagged.length >= 6);
  for (const [, ev] of tagged) assert.equal(ev, "pro_page_click");
  for (const m of html.matchAll(/<a\b[^>]*href="https?:[^"]*"[^>]*>/g)) {
    if (!m[0].includes("purplelink.llc")) assert.match(m[0], /rel="noopener noreferrer"/, m[0]);
  }
  assert.ok(!/google-analytics|googletagmanager|facebook\.net|plausible|hotjar/i.test(html));
});

test("the page is registered: sitemap, llms.txt, the llms-full list, and the main product page links to it", () => {
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/scholar-utility-belt\/pro\/<\/loc>/);
  assert.match(read("llms.txt"), /https:\/\/purplelink\.llc\/scholar-utility-belt\/pro\//);
  assert.match(readFileSync(join(ROOT, "scripts/gen_llms_full.py"), "utf8"), /"scholar-utility-belt\/pro\/",/);
  assert.ok(read("scholar-utility-belt/index.html").includes('href="/scholar-utility-belt/pro/"'));
});

test("the prices on the Pro page match the main product page's structured data", () => {
  const app = jsonLd(read("scholar-utility-belt/index.html")).find((n) => n["@type"] === "SoftwareApplication");
  const prices = app.offers.map((o) => o.price || o.priceSpecification?.price).sort();
  assert.deepEqual(prices, ["0", "20", "3", "40"]);
});
