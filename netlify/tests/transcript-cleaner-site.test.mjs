// The Transcript Cleaner page, checked as files: head tags, structured data that matches the visible
// text, the copy rules, the CSP rules (no inline styles or scripts, own assets only), the promise that
// the code makes no network request of its own, and the listings (tools index, sitemap, llms.txt,
// llms-full.txt, search index, share image, tool card images).
//
// Run with: node --test netlify/tests/transcript-cleaner-site.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const read = (p) => readFileSync(join(SITE, p), "utf8");
const PAGE = "tools/transcript-cleaner/index.html";
const html = read(PAGE);
const jsonLd = () =>
  [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].flatMap((m) => {
    const d = JSON.parse(m[1]);
    return d["@graph"] || [d];
  });
const decode = (s) =>
  s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, "&");
const stripTags = (s) => decode(s.replace(/<[^>]+>/g, ""));
const body = html.replace(/<script\b[\s\S]*?<\/script>/g, "").replace(/<style\b[\s\S]*?<\/style>/g, "");
const visibleText = stripTags(body).replace(/\s+/g, " ");

test("head: title, description, canonical, robots and share tags", () => {
  assert.match(html, /<title>Clean a Zoom or Teams Transcript \(VTT\) in Your Browser \| Purplelink<\/title>/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/tools\/transcript-cleaner\/">/);
  assert.match(html, /<meta name="robots" content="index, follow">/);
  const desc = /<meta name="description" content="([^"]*)"/.exec(html)[1];
  assert.ok(desc.length >= 100 && desc.length <= 175, "description length " + desc.length);
  assert.match(html, /<meta property="og:image" content="https:\/\/purplelink\.llc\/assets\/og\/transcript-cleaner\.png">/);
  assert.match(html, /<meta name="twitter:image" content="https:\/\/purplelink\.llc\/assets\/og\/transcript-cleaner\.png">/);
  assert.match(html, /\/theme\.js/);
});

test("structured data: WebApplication is free, HowTo and FAQ text matches the visible page exactly", () => {
  const nodes = jsonLd();
  const types = nodes.map((n) => n["@type"]);
  assert.deepEqual(types, ["WebApplication", "HowTo", "FAQPage", "BreadcrumbList"]);
  const app = nodes[0];
  assert.equal(app.offers.price, "0");
  assert.equal(app.url, "https://purplelink.llc/tools/transcript-cleaner/");
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
});

test("the page says plainly that it does not summarise, correct or reword, and that nothing is uploaded", () => {
  assert.match(visibleText, /does not summarise, correct or reword anything/);
  assert.match(visibleText, /Your file is never uploaded/);
  assert.match(visibleText, /built and tested on sample files written from the published formats, not on real exports/);
});

test("copy rules: no emoji, no em dash, none of the banned words, no mention of an unreleased product", () => {
  const files = [PAGE, "tools/transcript-cleaner/transcript-cleaner.js", "tools/transcript-cleaner/transcript-cleaner.css", "tools/transcript-cleaner/transcript-cleaner-core.js", "tools/transcript-cleaner/transcript-cleaner-worker.js"];
  for (const f of files) {
    const t = read(f);
    assert.doesNotMatch(t, /\p{Extended_Pictographic}/u, f + " has an emoji");
    assert.doesNotMatch(t, /—/, f + " has an em dash");
    // The shared site footer lists every product; the page itself must not promote Tapefolio.
    assert.doesNotMatch(t.replace(/<footer class="footer">[\s\S]*?<\/footer>/, ""), /tapefolio/i, f + " mentions Tapefolio");
  }
  assert.doesNotMatch(visibleText, /\b(streamline|supercharge|seamless|world-class|game-changer|AI-powered|revolutionary|effortless)\b/i);
});

test("CSP: no inline styles, no inline scripts or handlers, and every asset is the site's own", () => {
  assert.doesNotMatch(body, /<[a-zA-Z][^>]*\sstyle\s*=/);
  assert.doesNotMatch(html, /<style\b/);
  assert.doesNotMatch(html, /\son[a-z]+\s*=\s*"/);
  const scripts = [...html.matchAll(/<script\b([^>]*)>/g)].map((m) => m[1]);
  for (const a of scripts) assert.ok(/src="\//.test(a) || /type="application\/ld\+json"/.test(a), "inline script: " + a);
  for (const m of html.matchAll(/(?:src|href)="(https?:\/\/[^"]+)"/g)) {
    assert.match(m[1], /^https:\/\/(purplelink\.llc\/|buymeacoffee\.com\/bampel)/, "external reference " + m[1]);
  }
  assert.doesNotMatch(html, /<script[^>]+src="https?:/);
});

test("the code makes no network request of its own: core and worker have none, the page only counts them", () => {
  const net = /\b(fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource|importScripts\s*\(\s*["']https?:|import\s*\()/;
  assert.doesNotMatch(read("tools/transcript-cleaner/transcript-cleaner-core.js"), net);
  const worker = read("tools/transcript-cleaner/transcript-cleaner-worker.js");
  assert.doesNotMatch(worker.replace(/importScripts\("\/tools\/transcript-cleaner\/transcript-cleaner-core\.js" \+ cv\);/, ""), /fetch|XMLHttpRequest|sendBeacon|WebSocket|importScripts/);
  const page = read("tools/transcript-cleaner/transcript-cleaner.js");
  assert.doesNotMatch(page, /\bfetch\s*\(/, "the page script never calls fetch itself");
  assert.doesNotMatch(page, /new XMLHttpRequest|new WebSocket|new EventSource/);
  // The only thing the page reports is the file type, through the shared analytics function.
  const tracks = page.match(/plTrack\([^)]*\)/g);
  assert.deepEqual(tracks, ['plTrack("tool_use", "transcript-cleaner:" + next.res.stats.format)']);
});

test("file text is written to the page only with textContent or a textarea value", () => {
  const page = read("tools/transcript-cleaner/transcript-cleaner.js");
  assert.doesNotMatch(page, /innerHTML|insertAdjacentHTML|document\.write|outerHTML/);
});

test("accessibility basics: labelled controls, status region, native buttons, reduced motion", () => {
  assert.match(html, /<input id="tc-file"[^>]*aria-label="Transcript files"/);
  assert.match(html, /<p class="tc-status" id="tc-status" role="status" aria-live="polite">/);
  assert.match(html, /<button type="button" class="btn btn-primary tc-small" id="tc-choose">/);
  assert.match(html, /<label for="tc-paste-in">/);
  assert.match(html, /<legend>Show as<\/legend>/);
  const css = read("tools/transcript-cleaner/transcript-cleaner.css");
  const motion = css.match(/animation\s*:/g) || [];
  const gated = (css.match(/@media \(prefers-reduced-motion: no-preference\) \{[\s\S]*?\n\}/) || [""])[0].match(/animation\s*:/g) || [];
  assert.equal(motion.length, gated.length, "every animation sits inside the no-preference query");
  assert.doesNotMatch(css, /prefers-color-scheme/);
  assert.match(css, /:focus-visible/);
});

test("the before and after example on the page is what the cleaner really produces", async () => {
  const { default: fs } = await import("node:fs");
  const mod = { exports: {} };
  new Function("module", "exports", fs.readFileSync(join(SITE, "tools/transcript-cleaner/transcript-cleaner-core.js"), "utf8"))(mod, mod.exports);
  const panes = [...html.matchAll(/<pre>([\s\S]*?)<\/pre>/g)].map((m) => decode(m[1]));
  assert.equal(panes.length, 2);
  const out = mod.exports.clean(panes[0], "example.vtt", { speakers: true, timestamps: false, paragraphs: true, tags: false }).txt;
  assert.equal(out.trimEnd(), panes[1]);
});

test("listed in the tools index, sitemap, llms.txt, llms-full.txt and the search index", () => {
  const idx = read("tools/index.html");
  assert.match(idx, /"position": 17, "name": "Transcript Cleaner", "url": "https:\/\/purplelink\.llc\/tools\/transcript-cleaner\/"/);
  assert.match(idx, /<a class="tool-card" href="\/tools\/transcript-cleaner\/">/);
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/tools\/transcript-cleaner\/<\/loc>/);
  assert.match(read("llms.txt"), /- Transcript Cleaner: https:\/\/purplelink\.llc\/tools\/transcript-cleaner\/ - /);
  assert.match(read("llms-full.txt"), /### Transcript Cleaner/);
  const search = JSON.parse(read("search-index.json")).find((e) => e.u === "/tools/transcript-cleaner/");
  assert.ok(search);
  assert.equal(search.t, "Clean a Zoom or Teams Transcript (VTT) in Your Browser");
  assert.equal(search.s, "Tool");
});

test("share image and tool card images exist and are not empty", () => {
  for (const f of ["assets/og/transcript-cleaner.png", "assets/tool-shots/transcript-cleaner.webp", "assets/tool-shots/transcript-cleaner-800.webp"]) {
    assert.ok(existsSync(join(SITE, f)), f);
    assert.ok(statSync(join(SITE, f)).size > 5000, f + " is too small");
  }
  assert.match(read("assets/og/_gen.html"), /"transcript-cleaner": \{/);
});

test("the page's local assets exist and carry a content hash", () => {
  for (const m of html.matchAll(/(?:src|href)="(\/tools\/transcript-cleaner\/[^"?]+)\?v=([0-9a-f]{10})"/g)) {
    assert.ok(existsSync(join(SITE, m[1])), m[1]);
  }
  assert.match(html, /transcript-cleaner-core\.js\?v=[0-9a-f]{10}/);
});
