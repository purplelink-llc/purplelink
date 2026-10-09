// The Tapefolio pages, checked as files: the offer in the structured data, the release gate
// (the trial link and Buy button stay dead until site/tapefolio/launch.js is flipped), the
// copy rules (what the page may and may not claim), and the success page's script run against
// a small fake DOM.
//
// Run with: node --test netlify/tests/tapefolio-site.test.mjs

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
  html.replace(/<script\b[\s\S]*?<\/script>/gi, " ").replace(/<style\b[\s\S]*?<\/style>/gi, " ").replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<[^>]+>/g, " ").replace(/&nbsp;|&middot;/g, " ").replace(/&amp;/g, "&").replace(/&rsquo;|&#39;/g, "'").replace(/\s+/g, " ");

// ---- product page --------------------------------------------------------------------

test("the Tapefolio page offers the app at $29.99 once, with a 14-day refund, for macOS 26 on Apple silicon, in valid JSON-LD", () => {
  const app = jsonLd(read("tapefolio/index.html")).find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Tapefolio");
  assert.equal(app.offers.price, "29.99");
  assert.equal(app.offers.priceCurrency, "USD");
  assert.equal(app.offers.hasMerchantReturnPolicy.merchantReturnDays, 14);
  assert.equal(app.operatingSystem, "macOS 26+");
  assert.equal(app.processorRequirements, "Apple silicon");
  assert.equal(app.offers.availability, undefined, "no availability is claimed in the markup");
  assert.ok(!("aggregateRating" in app) && !("review" in app), "no ratings or reviews are invented");
  const types = jsonLd(read("tapefolio/index.html")).map((n) => n["@type"]);
  assert.deepEqual(types.sort(), ["BreadcrumbList", "FAQPage", "SoftwareApplication"]);
});

test("the page is wired to the delivery and checkout functions and carries the shared head tags", () => {
  const html = read("tapefolio/index.html");
  assert.match(html, /data-tf-href="\/\.netlify\/functions\/tapefolio-download\?download=1"/);
  assert.match(html, /id="checkout-btn" data-product="tapefolio"/);
  assert.match(html, /paid-tool-landing\.js/);
  assert.match(html, /\/tapefolio\/launch\.js/);
  assert.match(html, /\/trial-reminder\.js/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/tapefolio\/">/);
  assert.match(html, /\/theme\.js/);
  assert.match(html, /<link rel="stylesheet" href="\/tapefolio\/tapefolio\.css/);
});

test("the page has every section the brief asks for", () => {
  const html = read("tapefolio/index.html");
  for (const id of ["how-h", "does-h", "not-h", "measured-h", "privacy-h", "price-h", "req-h", "faq-heading"]) {
    assert.match(html, new RegExp(`id="${id}"`), id);
  }
  const text = visibleText(html);
  for (const heading of ["What it does", "What it will not do", "Privacy and what downloads", "Price and trial", "System requirements", "Frequently asked questions"]) {
    assert.ok(text.includes(heading), heading);
  }
});

// ---- the release gate ------------------------------------------------------------------

test("PRE-LAUNCH GUARD: the page ships switched off, unlisted, and says so (delete this test when launching)", () => {
  const src = read("tapefolio/launch.js");
  assert.match(src, /live: false,/);
  assert.match(src, /version: "",/);
  assert.match(src, /sizeMb: "",/);
  assert.match(src, /released: ""/);
  const html = read("tapefolio/index.html");
  const trialTags = [...html.matchAll(/<a\b[^>]*data-tf-gated[^>]*>/g)].map((m) => m[0]);
  assert.ok(trialTags.length >= 2);
  for (const tag of trialTags) {
    assert.doesNotMatch(tag, /\shref=/, "no href until launch");
    assert.match(tag, /aria-disabled="true"/);
  }
  assert.match(html, /<button\b[^>]*id="checkout-btn"[^>]*\sdisabled/);
  assert.match(html, /Not released yet/);
  assert.match(html, /<meta name="robots" content="noindex, follow">/, "unlisted until the launch commit flips it");
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
    pre: new FakeEl({ "data-tf-pre-only": "" }),
    live: new FakeEl({ "data-tf-live-only": "", hidden: "" }),
    trial: new FakeEl({ "data-tf-gated": "", "data-tf-href": "/.netlify/functions/tapefolio-download?download=1", "data-tf-live-text": "Try it free for 7 days", "aria-disabled": "true", __text: "Free trial opens at release" }),
    buy: new FakeEl({ "data-tf-gated": "", "data-tf-live-text": "Buy Tapefolio", disabled: "", __text: "Buying opens at release" }),
    facts: new FakeEl({ "data-tf-facts": "", __text: "placeholder" }),
    sticky: new FakeEl({ "data-tf-sticky": "" }),
  };
  const by = { "[data-tf-pre-only]": [els.pre], "[data-tf-live-only]": [els.live], "[data-tf-gated]": [els.trial, els.buy], "[data-tf-facts]": [els.facts], "[data-tf-sticky]": [els.sticky] };
  const warnings = [];
  const ctx = {
    window: { console: { warn: (m) => warnings.push(m) } },
    document: { readyState: "complete", querySelectorAll: (s) => by[s] || [], addEventListener() {} },
    console: { warn: (m) => warnings.push(m) },
    Date, String, Array,
  };
  ctx.window.TAPEFOLIO_LAUNCH = undefined;
  const src = read("tapefolio/launch.js").replace(/window\.TAPEFOLIO_LAUNCH = \{[\s\S]*?\};/, `window.TAPEFOLIO_LAUNCH = ${JSON.stringify(config)};`);
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
  assert.equal(els.trial.getAttribute("href"), "/.netlify/functions/tapefolio-download?download=1");
  assert.equal(els.trial.getAttribute("aria-disabled"), null);
  assert.equal(els.trial.textContent, "Try it free for 7 days");
  assert.equal(els.buy.disabled, false);
  assert.equal(els.buy.textContent, "Buy Tapefolio");
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

test("the Tapefolio pages have no inline styles, em or en dashes or emoji", () => {
  for (const p of ["tapefolio/index.html", "tapefolio/success/index.html", "tapefolio/launch.js", "tapefolio/success.js", "tapefolio/tapefolio.css"]) {
    const src = read(p);
    if (p.endsWith(".html")) assert.doesNotMatch(src, /<[a-z][^>]*\sstyle\s*=/i, `${p} has an inline style`);
    assert.doesNotMatch(src, /[–—]/, `${p} has an em or en dash`);
    assert.doesNotMatch(src, /\p{Extended_Pictographic}/u, `${p} has an emoji`);
  }
});

test("the page says what it cannot do, in plain words", () => {
  const text = visibleText(read("tapefolio/index.html")).toLowerCase();
  assert.match(text, /mishear words and mislabel speakers/);
  assert.match(text, /check any text you plan to quote against the recording/);
  assert.match(text, /it misses some/);
  assert.match(text, /read (every transcript|the result) before you share/);
  assert.match(text, /does not make a study compliant/);
  assert.match(text, /ethics board/);
  assert.match(text, /replace or keep each one/);
  assert.match(text, /key file/);
  assert.match(text, /consent note/);
  assert.match(text, /stored encrypted on your mac/);
  assert.match(text, /only suggests matches/);
  assert.match(text, /real handwriting and real phone photos .{0,20}have not been tested/);
  assert.match(text, /macos 26/);
  assert.match(text, /apple silicon/);
  assert.match(text, /a few minutes/);
  assert.match(text, /14 days/);
  assert.match(text, /two of your macs/);
});

test("the page never claims anonymization, guaranteed compliance, or anything the README does not back", () => {
  const html = read("tapefolio/index.html");
  const text = visibleText(html);
  // The word "anonymize" may appear only as the question or the denial.
  for (const m of text.matchAll(/anonymi[sz]\w*/gi)) {
    const around = text.slice(Math.max(0, m.index - 30), m.index + 60);
    assert.match(around, /(Anonymize a transcript|Does it anonymize a transcript\?)/, `unexpected use: ${around}`);
  }
  assert.doesNotMatch(text, /guarantee|HIPAA|GDPR|FERPA|certified|100% (private|accurate|secure)|fully (private|anonymous|compliant)|IRB[- ]approved|never (mishears|misses)/i);
  assert.doesNotMatch(text, /seamless|supercharge|streamline|world-class|cutting-edge|revolutionary|effortless|AI-powered|game-chang|magic|blazing|lightning/i);
  // Every percentage on the page is one the README states.
  const allowed = new Set(["21%", "29%", "39%", "87%", "94%", "1.5%"]);
  for (const m of text.matchAll(/\d+(?:\.\d+)?%/g)) assert.ok(allowed.has(m[0]), `unexpected figure ${m[0]}`);
  // Features that are not built are not named.
  for (const unbuilt of ["live captions", "real-time transcription", "cloud sync", "sync across", "team", "collaborat", "translation", "summar", "read-aloud", "ChatGPT", "OpenAI API"]) {
    assert.ok(!text.toLowerCase().includes(unbuilt.toLowerCase()), `the page mentions: ${unbuilt}`);
  }
});

test("the models table matches the README: built in, Parakeet, Whisper large-v3 turbo, Nemotron 3 Diarization", () => {
  const text = visibleText(read("tapefolio/index.html"));
  for (const name of ["NVIDIA Parakeet", "Whisper large-v3 turbo", "NVIDIA Nemotron 3 Diarization", "Small speech model"]) assert.ok(text.includes(name), name);
  assert.match(text, /About 470 MB/);
  assert.match(text, /About 650 MB/);
  assert.match(text, /About 190 MB/);
  assert.match(text, /Parakeet TDT 0\.6B v2 \(CC BY 4\.0\)/, "the CC BY credit is on the page");
  assert.match(text, /AMI Meeting Corpus \(CC BY 4\.0\)/);
});

test("every image on the page exists, has a size and alt text, and none is an invented screenshot", () => {
  for (const p of ["tapefolio/index.html", "tapefolio/success/index.html"]) {
    const html = read(p);
    for (const [tag, src] of [...html.matchAll(/<img\b[^>]*src="([^"]+)"[^>]*>/g)].map((m) => [m[0], m[1]])) {
      assert.ok(src.startsWith("/"), `${src} is not a local path`);
      assert.ok(existsSync(join(SITE, src)), `${src} is missing`);
      assert.match(tag, /\swidth="\d+"/);
      assert.match(tag, /\sheight="\d+"/);
      assert.match(tag, /\salt="[^"]*"/);
    }
    assert.doesNotMatch(html, /\/tapefolio\/img\//, "no picture is referenced until it exists");
  }
});

test("the hero shows the real app icon, sized, with alt text, and the icon files are square webp at 240 and 128", () => {
  const html = read("tapefolio/index.html");
  assert.match(html, /<img class="app-hero-icon" src="\/assets\/tapefolio-icon\.webp" width="120" height="120" fetchpriority="high" alt="Tapefolio app icon">/);
  for (const [f, px] of [["assets/tapefolio-icon.webp", 240], ["assets/tapefolio-icon-128.webp", 128]]) {
    const b = readFileSync(join(SITE, f));
    assert.equal(b.subarray(0, 4).toString(), "RIFF");
    assert.equal(b.subarray(8, 12).toString(), "WEBP");
    assert.ok(b.length < 40 * 1024, `${f} is ${b.length} bytes`);
    // Lossy VP8X files keep the canvas size in bytes 24 to 29 (width-1, height-1, 24-bit little endian).
    if (b.subarray(12, 16).toString() === "VP8X") {
      assert.equal(b.readUIntLE(24, 3) + 1, px);
      assert.equal(b.readUIntLE(27, 3) + 1, px);
    }
  }
});

test("the share card is 1200 by 630, is what the page's meta tags and JSON-LD point at, and the Suite card is current", () => {
  const html = read("tapefolio/index.html");
  assert.match(html, /<meta property="og:image" content="https:\/\/purplelink\.llc\/assets\/og\/tapefolio\.png">/);
  assert.match(html, /<meta name="twitter:image" content="https:\/\/purplelink\.llc\/assets\/og\/tapefolio\.png">/);
  assert.equal(jsonLd(html).find((n) => n["@type"] === "SoftwareApplication").image, "https://purplelink.llc/assets/og/tapefolio.png");
  for (const f of ["tapefolio", "mac-suite"]) {
    const png = readFileSync(join(SITE, `assets/og/${f}.png`));
    assert.equal(png.readUInt32BE(16), 1200, f);
    assert.equal(png.readUInt32BE(20), 630, f);
    assert.ok(png.length > 20000, f);
  }
  const gen = read("assets/og/_gen.html");
  assert.match(gen, /"tapefolio":\s+\{[^}]*title: "Tapefolio"/);
});

test("the stylesheets, scripts and fonts the pages load all exist", () => {
  for (const p of ["tapefolio/index.html", "tapefolio/success/index.html"]) {
    const html = read(p);
    const refs = [...html.matchAll(/<(?:link|script)\b[^>]*?(?:href|src)="(\/[^"?#]+\.(?:css|js|woff2|json|svg|png))(?:\?[^"]*)?"/g)].map((m) => m[1]);
    assert.ok(refs.length >= 5, `${p} loads ${refs.length} files`);
    for (const ref of refs) assert.ok(existsSync(join(SITE, ref)), `${p} loads ${ref} which is missing`);
  }
});

test("the success page is noindex, loads its script and has the download and key boxes", () => {
  const html = read("tapefolio/success/index.html");
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.match(html, /src="\/tapefolio\/success\.js/);
  assert.match(html, /id="downloads"/);
  assert.match(html, /id="license"/);
  assert.match(html, /macOS 26/);
  assert.match(html, /Neural Engine/);
});

// ---- Terms and Privacy ------------------------------------------------------------------

test("the Terms carry Tapefolio's own section: price, refund, two Macs, drafts, consent, liability cap", () => {
  const html = read("terms/index.html");
  assert.match(html, /<h2>Tapefolio: additional terms<\/h2>/);
  const section = html.slice(html.indexOf("<h2>Tapefolio: additional terms</h2>"), html.indexOf("<h2>Mac Suite: additional terms</h2>"));
  assert.match(section, /\$29\.99 USD, once/);
  assert.match(section, /within 14 days of purchase/);
  assert.match(section, /up to two of your own Macs/);
  assert.match(section, /Transcripts are drafts/);
  assert.match(section, /does not anonymize a transcript/);
  assert.match(section, /Consent/);
  assert.match(section, /Liability cap for Tapefolio/);
  assert.match(html, /the ModernTex, Outbound Veil, Legroom, Keyfeel and Tapefolio Mac apps/);
});

test("the Privacy page says what Tapefolio sends and does not send, and names its trial emails and recovery", () => {
  const html = read("privacy/index.html");
  assert.match(html, /<strong>Tapefolio<\/strong> has no account and no analytics/);
  assert.match(html, /does not upload your recordings, transcripts, images or key files/);
  assert.match(html, /Tapefolio trial emails<\/strong>/);
  assert.match(html, /Keyfeel, Tapefolio, Mac Suite and kit purchases/);
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
  vm.runInNewContext(readFileSync(join(SITE, "tapefolio/success.js"), "utf8"), ctx);
  return { nodes, fetched };
}
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const SID = "cs_live_abcdefghij1234";

test("/tapefolio/success/ asks tapefolio-download for the session and shows a download button", async () => {
  const { nodes, fetched } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { files: [{ key: "Tapefolio-1.0.0.dmg", label: "Tapefolio 1.0.0 for macOS (disk image)", url: "/.netlify/functions/tapefolio-download?session_id=x&file=Tapefolio-1.0.0.dmg" }] }),
  });
  await tick();
  assert.deepEqual(fetched, [`/.netlify/functions/tapefolio-download?session_id=${SID}`]);
  assert.match(nodes.downloads.innerHTML, /Download: Tapefolio 1\.0\.0 for macOS/);
  assert.match(nodes.downloads.innerHTML, /tapefolio-download\?session_id=x&amp;file=Tapefolio-1\.0\.0\.dmg/);
});

test("/tapefolio/success/ shows the license key from the server", async () => {
  const KEY = "TFL1-ABCDE-FGHJK";
  const { nodes } = runSuccess({
    search: `?session_id=${SID}`,
    fetchImpl: () => reply(200, { license: KEY, files: [{ key: "Tapefolio-1.0.0.dmg", label: "Tapefolio 1.0.0 for macOS (disk image)", url: "/x" }] }),
  });
  await tick();
  const code = nodes.license.children.find((c) => c.tagName === "code");
  assert.ok(code, "a code element holds the key");
  assert.equal(code.textContent, KEY);
  assert.equal(code.attrs["aria-label"], "Your Tapefolio license key");
});

test("/tapefolio/success/ shows the server's reason when refused, and never fetches for a bad id", async () => {
  const refused = runSuccess({ search: `?session_id=${SID}`, fetchImpl: () => reply(403, { error: "not_entitled", detail: "This order is for a different product." }) });
  await tick();
  assert.match(refused.nodes.downloads.innerHTML, /This order is for a different product\./);
  const bad = runSuccess({ search: "?session_id=nope", fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.equal(bad.fetched.length, 0);
  assert.match(bad.nodes.downloads.innerHTML, /receipt email/);
});
