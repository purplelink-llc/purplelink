// The PII Checker page, checked as files: head tags, structured data that matches the visible text, the copy rules,
// the CSP rules (no inline styles or scripts, own assets only), the promise that the code makes no network request of
// its own, the limits text, and the listings (tools index, sitemap, llms.txt, llms-full.txt, search index, share image,
// tool card images).
//
// Run with: node --test netlify/tests/pii-checker-site.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const read = (p) => readFileSync(join(SITE, p), "utf8");
const PAGE = "tools/pii-checker/index.html";
const html = read(PAGE);
const jsonLd = () =>
  [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].flatMap((m) => {
    const d = JSON.parse(m[1]);
    return d["@graph"] || [d];
  });
const decode = (s) =>
  s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, "&");
// Repeat each removal until nothing changes, so a nested or split tag cannot survive one pass.
const removeAll = (s, re) => {
  let prev;
  do {
    prev = s;
    s = s.replace(re, "");
  } while (s !== prev);
  return s;
};
const stripTags = (s) => decode(removeAll(s, /<[^>]*>/g));
const body = removeAll(removeAll(html, /<script\b[\s\S]*?<\/script\s*>/gi), /<style\b[\s\S]*?<\/style\s*>/gi);
const visibleText = stripTags(body).replace(/\s+/g, " ");
const FILES = [PAGE, "tools/pii-checker/pii-checker.js", "tools/pii-checker/pii-checker.css", "tools/pii-checker/pii-checker-core.js", "tools/pii-checker/pii-checker-worker.js"];

const LIMITS = "This check uses patterns. It finds numbers and addresses that follow a format and will miss others. It does not find names, and it cannot tell when a detail identifies someone only in context, such as a rare job in a small town.";

test("head: title, description, canonical, robots, h1 and share tags", () => {
  assert.match(html, /<title>Check Text for Personal Information, in Your Browser \| Purplelink<\/title>/);
  assert.match(html, /<meta name="description" content="Paste text and see the email addresses, phone numbers, ID and card numbers it contains\. The check runs in your browser and nothing is uploaded\.">/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/tools\/pii-checker\/">/);
  assert.match(html, /<meta name="robots" content="index, follow">/);
  assert.match(html, /<h1>Check text for personal information<\/h1>/);
  const desc = /<meta name="description" content="([^"]*)"/.exec(html)[1];
  assert.ok(desc.length >= 100 && desc.length <= 175, "description length " + desc.length);
  assert.match(html, /<meta property="og:image" content="https:\/\/purplelink\.llc\/assets\/og\/pii-checker\.png">/);
  assert.match(html, /<meta name="twitter:image" content="https:\/\/purplelink\.llc\/assets\/og\/pii-checker\.png">/);
  assert.match(html, /\/theme\.js/);
});

test("structured data: WebApplication is free, HowTo and FAQ text matches the visible page exactly", () => {
  const nodes = jsonLd();
  assert.deepEqual(nodes.map((n) => n["@type"]), ["WebApplication", "HowTo", "FAQPage", "BreadcrumbList"]);
  const app = nodes[0];
  assert.equal(app.offers.price, "0");
  assert.equal(app.url, "https://purplelink.llc/tools/pii-checker/");
  assert.equal(app.description, /<meta name="description" content="([^"]*)"/.exec(html)[1]);

  const howto = nodes[1];
  const lis = [...html.matchAll(/<section class="tool-howto">[\s\S]*?<\/section>/g)][0][0].match(/<li>[\s\S]*?<\/li>/g).map(stripTags);
  assert.equal(lis.length, howto.step.length);
  howto.step.forEach((s, i) => assert.equal(lis[i], `${s.name}. ${s.text}`, "step " + (i + 1)));

  const faq = nodes[2].mainEntity;
  const details = [...html.matchAll(/<details><summary>([\s\S]*?)<\/summary><div class="faq-body">([\s\S]*?)<\/div><\/details>/g)];
  assert.equal(details.length, faq.length);
  faq.forEach((q, i) => {
    assert.equal(stripTags(details[i][1]), q.name);
    assert.equal(stripTags(details[i][2]), q.acceptedAnswer.text);
  });
  assert.deepEqual(faq.slice(0, 4).map((q) => q.name), [
    "Is my text uploaded?", "What does it find?", "Why does it not find names?", "Does a clean result mean the text is safe to share?",
  ]);
});

test("the limits sentence is on the page, inside the results block, and names are said not to be found", () => {
  const block = /<section class="pc-results"[\s\S]*?<\/section>/.exec(html)[0];
  assert.ok(stripTags(block).replace(/\s+/g, " ").includes(LIMITS));
  assert.match(visibleText, /It does not find names\./);
  assert.match(visibleText, /Your text is never uploaded/);
  assert.match(visibleText, /It is not a compliance check and it is not legal advice/);
});

test("the page names no category the code does not detect, and detects every category it names", async () => {
  const { default: fs } = await import("node:fs");
  const mod = { exports: {} };
  new Function("module", "exports", fs.readFileSync(join(SITE, "tools/pii-checker/pii-checker-core.js"), "utf8"))(mod, mod.exports);
  const P = mod.exports;
  assert.equal(P.LABELS.length, 9);
  const q = /<summary>What does it find\?<\/summary><div class="faq-body">([^<]*)<\/div>/.exec(html)[1];
  assert.match(q, /^Nine types\./);
  for (const w of ["Social Security", "Card numbers", "IBANs", "Email addresses", "Phone numbers", "Dates of birth", "Medical record numbers", "IP and MAC", "Web addresses"]) assert.ok(q.includes(w), w);
  const sample = "ssn 472-81-0094 card 4111 1111 1111 1111 iban GB82 WEST 1234 5698 7654 32 mail a@b.co call (404) 555-0182 dob 03/14/1981 mrn 4482910 ip 192.168.1.10 link https://x.example/r?t=1";
  assert.deepEqual(P.detect(sample).map((s) => s.label).sort(), [...P.LABELS].sort());
});

test("the sample text on the page is checked as the page says: names untouched, traps not marked", async () => {
  const { default: fs } = await import("node:fs");
  const mod = { exports: {} };
  new Function("module", "exports", fs.readFileSync(join(SITE, "tools/pii-checker/pii-checker-core.js"), "utf8"))(mod, mod.exports);
  const page = read("tools/pii-checker/pii-checker.js");
  const lines = [...page.match(/var SAMPLE = \[([\s\S]*?)\]\.join/)[1].matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((m) => JSON.parse('"' + m[1] + '"'));
  const sample = lines.join("\n");
  const r = mod.exports.check(sample);
  assert.equal(r.total, 9);
  assert.ok(r.redacted.includes("Jordan Sample"), "names are not found");
  for (const kept of ["Order #84-2291", "2026-10-21", "version 2.4.1", "978-3-16-148410-0"]) assert.ok(r.redacted.includes(kept), kept);
});

test("copy rules: no emoji, no em dash, none of the banned words, Outbound Veil only where the offer and the names answer need it", () => {
  for (const f of FILES) {
    const t = read(f);
    assert.doesNotMatch(t, /\p{Extended_Pictographic}/u, f + " has an emoji");
    assert.doesNotMatch(t, /—/, f + " has an em dash");
  }
  assert.doesNotMatch(visibleText, /\b(streamline|supercharge|seamless|world-class|game-changer|AI-powered|revolutionary|effortless|leverage|robust|cutting-edge)\b/i);
  assert.doesNotMatch(visibleText, /\b(HIPAA|GDPR|compliant with|guarantee)\b/);
  // Outbound Veil appears in the footer list, its one offer card and the answer about names, and nowhere else.
  const rest = html.replace(/<footer class="footer">[\s\S]*?<\/footer>/, "").replace(/<!-- tool-offer -->[\s\S]*?<!-- \/tool-offer -->/, "")
    .replace(/<details><summary>Why does it not find names\?<\/summary>[\s\S]*?<\/details>/, "")
    .replace(/"name": "Why does it not find names\?"[\s\S]*?"text": "[^"]*"/, "");
  assert.doesNotMatch(rest, /outbound veil/i);
});

test("links the two guides", () => {
  assert.match(html, /<a href="\/guides\/before-you-paste-client-notes-into-chatgpt\/">/);
  assert.match(html, /<a href="\/guides\/best-pii-redaction-tools-for-chatgpt\/">/);
});

test("CSP: no inline styles, no inline scripts or handlers, and every asset is the site's own", () => {
  assert.doesNotMatch(body, /<[a-zA-Z][^>]*\sstyle\s*=/);
  assert.doesNotMatch(html, /<style\b/);
  assert.doesNotMatch(html, /\son[a-z]+\s*=\s*"/);
  const scripts = [...html.matchAll(/<script\b([^>]*)>/gi)].map((m) => m[1]);
  for (const a of scripts) assert.ok(/src="\//.test(a) || /type="application\/ld\+json"/.test(a), "inline script: " + a);
  for (const m of html.matchAll(/(?:src|href)="(https?:\/\/[^"]+)"/g)) {
    assert.match(m[1], /^https:\/\/(purplelink\.llc\/|buymeacoffee\.com\/bampel|www\.linkedin\.com\/company\/purplelink-llc\/$)/, "external reference " + m[1]);
  }
  assert.doesNotMatch(html, /<script[^>]+src="https?:/);
  const js = read("tools/pii-checker/pii-checker.js");
  assert.doesNotMatch(js, /\.style\b|setAttribute\(\s*["']style/, "the page script sets no inline style");
});

test("the code makes no network request of its own: core and worker have none, the page only counts them", () => {
  const net = /\b(fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource|importScripts\s*\(\s*["']https?:|import\s*\()/;
  assert.doesNotMatch(read("tools/pii-checker/pii-checker-core.js"), net);
  const worker = read("tools/pii-checker/pii-checker-worker.js");
  assert.doesNotMatch(worker.replace(/importScripts\("\/tools\/pii-checker\/pii-checker-core\.js" \+ cv\);/, ""), /fetch|XMLHttpRequest|sendBeacon|WebSocket|importScripts/);
  const page = read("tools/pii-checker/pii-checker.js");
  assert.doesNotMatch(page, /\bfetch\s*\(/, "the page script never calls fetch itself");
  assert.doesNotMatch(page, /new XMLHttpRequest|new WebSocket|new EventSource/);
  // The only thing the page reports is how the text got there, through the shared analytics function.
  const tracks = page.match(/plTrack\([^)]*\)/g);
  assert.deepEqual(tracks, ['plTrack("tool_use", "pii-checker:" + source)']);
  const sources = [...page.matchAll(/source = "([a-z]+)"/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(sources)].sort(), ["file", "paste", "sample", "typed"]);
});

test("the usage count is accepted: the slug is on the allowlist of the count function", () => {
  const counts = readFileSync(join(SITE, "..", "netlify/lib/tool-counts.mjs"), "utf8");
  assert.match(counts, /"pii-checker"/);
});

test("text is written to the page only with textContent, text nodes or a textarea value", () => {
  const page = read("tools/pii-checker/pii-checker.js");
  assert.doesNotMatch(page, /innerHTML|insertAdjacentHTML|document\.write|outerHTML/);
});

test("accessibility basics: labelled controls, status region, native buttons, reduced motion, no colour-only marks", () => {
  assert.match(html, /<label for="pc-input">Text to check<\/label>/);
  assert.match(html, /<input id="pc-file"[^>]*aria-label="Text file"/);
  assert.match(html, /<p class="pc-status" id="pc-status" role="status" aria-live="polite">/);
  assert.match(html, /<button type="button" class="btn btn-ghost pc-small" id="pc-choose">/);
  const css = read("tools/pii-checker/pii-checker.css");
  const motion = css.match(/animation\s*:/g) || [];
  const gated = (css.match(/@media \(prefers-reduced-motion: no-preference\) \{[\s\S]*?\n\}/) || [""])[0].match(/animation\s*:/g) || [];
  assert.equal(motion.length, gated.length, "every animation sits inside the no-preference query");
  assert.doesNotMatch(css, /prefers-color-scheme/);
  assert.match(css, /:focus-visible/);
  assert.match(css, /\.pc-mark::after \{ content: attr\(data-label\)/, "each mark carries its type as text");
});

test("listed in the tools index, sitemap, llms.txt, llms-full.txt and the search index", () => {
  const idx = read("tools/index.html");
  assert.match(idx, /"position": 20, "name": "PII Checker", "url": "https:\/\/purplelink\.llc\/tools\/pii-checker\/"/);
  assert.match(idx, /<a class="tool-card" href="\/tools\/pii-checker\/">/);
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/tools\/pii-checker\/<\/loc>/);
  assert.match(read("llms.txt"), /- PII Checker: https:\/\/purplelink\.llc\/tools\/pii-checker\/ - /);
  assert.match(read("llms-full.txt"), /### PII Checker/);
  const search = JSON.parse(read("search-index.json")).find((e) => e.u === "/tools/pii-checker/");
  assert.ok(search);
  assert.equal(search.t, "Check Text for Personal Information, in Your Browser");
  assert.equal(search.s, "Tool");
});

test("share image and tool card images exist and are not empty", () => {
  for (const f of ["assets/og/pii-checker.png", "assets/tool-shots/pii-checker.webp", "assets/tool-shots/pii-checker-800.webp"]) {
    assert.ok(existsSync(join(SITE, f)), f);
    assert.ok(statSync(join(SITE, f)).size > 5000, f + " is too small");
  }
  assert.match(read("assets/og/_gen.html"), /"pii-checker":\s+\{/);
});

test("the page's local assets exist and carry a content hash", () => {
  const refs = [...html.matchAll(/(?:src|href)="(\/tools\/pii-checker\/[^"?]+)\?v=([0-9a-f]{10})"/g)];
  assert.equal(refs.length, 4);
  for (const m of refs) assert.ok(existsSync(join(SITE, m[1])), m[1]);
  assert.doesNotMatch(html, /\?v=0000000000/);
});
