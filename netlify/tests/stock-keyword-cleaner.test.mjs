// The Stock Photo Keyword Cleaner: the core functions (cleaning, agency limits, the Vecteezy fold, the editorial
// caption line) and the page as files (structured data that matches the visible text, the CSP rules, the notify-me
// form, and the listings).
//
// Run with: node --test netlify/tests/stock-keyword-cleaner.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const read = (p) => readFileSync(join(SITE, p), "utf8");
const DIR = "tools/stock-keyword-cleaner/";
const html = read(DIR + "index.html");

const mod = { exports: {} };
new Function("module", "exports", read(DIR + "stock-keyword-cleaner-core.js")).call(mod.exports, mod, mod.exports);
const SK = mod.exports;

const decode = (s) =>
  s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, "&");
const removeAll = (s, re) => {
  let prev;
  do {
    prev = s;
    s = s.replace(re, "");
  } while (s !== prev);
  return s;
};
const stripTags = (s) => decode(removeAll(s, /<[^>]*>/g));

// ---------- core ----------

test("split: commas, semicolons, pipes, tabs and line breaks separate; spaces and case inside a keyword are tidied", () => {
  assert.deepEqual(SK.split(' Hyde  Park ,London;"Big Ben"|uk\tEngland\n\nautumn, ,'), ["hyde park", "london", "big ben", "uk", "england", "autumn"]);
  assert.deepEqual(SK.split(""), []);
});

test("clean: lowercases, removes duplicates and the generic words, keeps the first-seen order", () => {
  const r = SK.clean("Hyde Park, travel, London, hyde park, Nature, LONDON, rowing boats");
  assert.deepEqual(r.keywords, ["hyde park", "london", "rowing boats"]);
  assert.deepEqual(r.duplicates, ["hyde park", "london"]);
  assert.deepEqual(r.generic, ["travel", "nature"]);
  assert.equal(r.input, 7);
  assert.deepEqual(SK.clean("travel, nature", { dropGeneric: false }).keywords, ["travel", "nature"]);
});

test("the generic list is ALAMY_ZERO_DEMAND in scripts/platform-keywords.py", () => {
  const py = readFileSync(join(SITE, "..", "scripts", "platform-keywords.py"), "utf8");
  const set = /ALAMY_ZERO_DEMAND = \{([\s\S]*?)\}/.exec(py)[1].match(/"([^"]+)"/g).map((s) => s.slice(1, -1));
  assert.deepEqual([...SK.GENERIC].sort(), set.sort());
});

test("agency limits: Adobe 49, Shutterstock 7 to 50, Alamy 5 to 50, Vecteezy 5 to 50, Dreamstime uncut", () => {
  const many = Array.from({ length: 60 }, (_, i) => "kw" + i);
  const n = (id) => SK.forAgency(many, id).keywords.length;
  assert.equal(n("adobe"), 49);
  assert.equal(n("shutterstock"), 50);
  assert.equal(n("alamy"), 50);
  assert.equal(n("vecteezy"), 50);
  assert.equal(n("dreamstime"), 60);
  const adobe = SK.forAgency(many, "adobe");
  assert.deepEqual(adobe.cut, many.slice(49));
  assert.deepEqual(adobe.keywords, many.slice(0, 49), "order is kept and the cut comes off the end");
  assert.equal(SK.forAgency(["a", "b"], "shutterstock").under, 5);
  assert.equal(SK.forAgency(["a", "b"], "alamy").under, 3);
  assert.equal(SK.forAgency(["a", "b"], "adobe").under, 0);
});

test("Vecteezy: accents fold, other characters become spaces, collisions merge", () => {
  assert.equal(SK.plain("café terrace"), "cafe terrace");
  assert.equal(SK.plain("speakers’ corner"), "speakers corner");
  assert.equal(SK.plain("straße"), "strasse");
  assert.equal(SK.plain("zürich – old town"), "zurich old town");
  assert.equal(SK.plain("東京"), "");
  const r = SK.forAgency(["café", "cafe", "東京", "rock-climbing"], "vecteezy");
  assert.deepEqual(r.keywords, ["cafe", "rock climbing"]);
  assert.deepEqual(r.merged, ["cafe"]);
  assert.deepEqual(r.dropped, ["東京"]);
  r.keywords.forEach((k) => assert.match(k, /^[a-z0-9 ]+$/));
});

test("editorial caption: Place - Month YYYY: with an optional day, replacing an existing line", () => {
  assert.equal(SK.captionPrefix({ city: "Atlanta", country: "Georgia", month: 10, year: "2026" }), "Atlanta, Georgia - October 2026:");
  assert.equal(SK.captionPrefix({ city: "Tucson", country: "Arizona", day: "5", month: 2, year: "2022" }), "Tucson, Arizona - February 5, 2022:");
  assert.equal(SK.captionPrefix({ city: "", country: "", month: 2, year: "2022" }), "");
  assert.equal(SK.captionPrefix({ city: "Atlanta", month: 2, year: "22" }), "");
  assert.equal(SK.editorialCaption("Atlanta, Georgia - October 2026:", "Fans walk past the stadium."), "Atlanta, Georgia - October 2026: Fans walk past the stadium.");
  assert.equal(
    SK.editorialCaption("Atlanta, Georgia - October 2026:", "Southern Arizona - July 2022: A man sits in the shade."),
    "Atlanta, Georgia - October 2026: A man sits in the shade."
  );
  assert.equal(SK.hasPrefix("Southern Arizona - July 2022: A man sits."), true);
  assert.equal(SK.hasPrefix("A man sits: in the shade."), false);
});

// ---------- page ----------

test("head: title, description, canonical, robots, h1 and share image", () => {
  assert.match(html, /<title>Stock Photo Keyword Cleaner: Adobe, Shutterstock, Alamy limits \| Purplelink<\/title>/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/tools\/stock-keyword-cleaner\/">/);
  assert.match(html, /<meta name="robots" content="index, follow">/);
  assert.match(html, /<h1>Stock Photo Keyword Cleaner<\/h1>/);
  const desc = /<meta name="description" content="([^"]*)"/.exec(html)[1];
  assert.ok(desc.length >= 100 && desc.length <= 175, "description length " + desc.length);
  assert.match(html, /<meta property="og:image" content="https:\/\/purplelink\.llc\/assets\/og\/stock-keyword-cleaner\.png">/);
});

test("structured data: free WebApplication, and HowTo and FAQ text match the visible page exactly", () => {
  const nodes = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].flatMap((m) => JSON.parse(m[1])["@graph"]);
  assert.deepEqual(nodes.map((n) => n["@type"]), ["WebApplication", "HowTo", "FAQPage", "BreadcrumbList"]);
  assert.equal(nodes[0].offers.price, "0");
  assert.equal(nodes[0].description, decode(/<meta name="description" content="([^"]*)"/.exec(html)[1]));
  const lis = /<section class="tool-howto">[\s\S]*?<\/section>/.exec(html)[0].match(/<li>[\s\S]*?<\/li>/g).map(stripTags);
  assert.equal(lis.length, nodes[1].step.length);
  nodes[1].step.forEach((s, i) => assert.equal(lis[i], `${s.name}. ${s.text}`));
  const details = [...html.matchAll(/<details><summary>([\s\S]*?)<\/summary><div class="faq-body">([\s\S]*?)<\/div><\/details>/g)];
  assert.equal(details.length, nodes[2].mainEntity.length);
  nodes[2].mainEntity.forEach((q, i) => {
    assert.equal(stripTags(details[i][1]), q.name);
    assert.equal(stripTags(details[i][2]), q.acceptedAnswer.text);
  });
});

test("the limits stated in the text agree with the core", () => {
  const faq = stripTags(/<section class="tool-faq">[\s\S]*?<\/section>/.exec(html)[0]);
  const by = Object.fromEntries(SK.AGENCIES.map((a) => [a.id, a]));
  assert.match(faq, new RegExp(`Adobe Stock allows up to ${by.adobe.max} keywords`));
  assert.match(faq, new RegExp(`Shutterstock needs ${by.shutterstock.min} to ${by.shutterstock.max}`));
  assert.match(faq, new RegExp(`Alamy allows ${by.alamy.max} tags, needs at least ${by.alamy.min}`));
  assert.match(faq, new RegExp(`Vecteezy needs ${by.vecteezy.min} to ${by.vecteezy.max}`));
  SK.GENERIC.forEach((w) => assert.ok(faq.includes(w), w));
});

test("CSP: no inline styles or scripts, own assets only", () => {
  assert.doesNotMatch(html, /\sstyle=/i);
  assert.doesNotMatch(html, /<style/i);
  assert.doesNotMatch(html, /\son[a-z]+=/i);
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script[^>]*>/gi)];
  scripts.forEach(([, attrs, body]) => {
    if (/application\/ld\+json/.test(attrs)) return;
    assert.equal(body.trim(), "", "inline script");
    assert.match(attrs, /src="\/[^/]/, "own-origin script");
  });
  for (const f of ["stock-keyword-cleaner.js", "stock-keyword-cleaner-core.js"]) {
    const js = read(DIR + f);
    assert.doesNotMatch(js, /innerHTML|insertAdjacentHTML|document\.write|eval\(/, f);
    assert.doesNotMatch(js, /\.style\./, f);
  }
});

test("the only request the page script makes is the notify-me form post to Netlify Forms", () => {
  const js = read(DIR + "stock-keyword-cleaner.js");
  assert.deepEqual(js.match(/fetch\(/g), ["fetch("]);
  assert.match(js, /fetch\("\/", \{ method: "POST"/);
  assert.doesNotMatch(read(DIR + "stock-keyword-cleaner-core.js"), /fetch|XMLHttpRequest|sendBeacon|localStorage/);
  const form = /<form class="sk-notify"[\s\S]*?<\/form>/.exec(html)[0];
  assert.match(form, /name="stockroom-notify" method="POST" data-netlify="true" data-netlify-honeypot="bot-field"/);
  assert.match(form, /<input type="hidden" name="form-name" value="stockroom-notify">/);
  assert.match(form, /It does not exist yet\./);
});

test("listings: tools index, sitemap, llms.txt, tool counts, share image and card images", () => {
  assert.match(read("tools/index.html"), /href="\/tools\/stock-keyword-cleaner\/"/);
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/tools\/stock-keyword-cleaner\/<\/loc>/);
  assert.match(read("llms.txt"), /https:\/\/purplelink\.llc\/tools\/stock-keyword-cleaner\//);
  assert.match(readFileSync(join(SITE, "..", "netlify", "lib", "tool-counts.mjs"), "utf8"), /"stock-keyword-cleaner"/);
  for (const f of ["assets/og/stock-keyword-cleaner.png", "assets/tool-shots/stock-keyword-cleaner.webp", "assets/tool-shots/stock-keyword-cleaner-800.webp"]) {
    assert.ok(existsSync(join(SITE, f)), f);
  }
});
