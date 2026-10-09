// The Tapefolio pages, checked as files: the offer in the structured data, the release gate
// (the trial link and Buy button stay dead until site/tapefolio/launch.js is flipped), the
// copy rules (what the page may and may not claim), and the success page's script run against
// a small fake DOM.
//
// Run with: node --test netlify/tests/tapefolio-site.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
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

test("LAUNCHED: launch.js ships live with valid facts, and the static page already says the live wording", () => {
  const src = read("tapefolio/launch.js");
  assert.match(src, /live: true,/);
  assert.match(src, /version: "1\.0\.0",/);
  assert.match(src, /sizeMb: "43",/);
  assert.match(src, /released: "2026-10-09"/);
  const cfg = JSON.parse(src.match(/window\.TAPEFOLIO_LAUNCH = (\{[\s\S]*?\});/)[1].replace(/(\w+):/g, '"$1":'));
  assert.equal(cfg.live, true);
  assert.match(cfg.version, /^\d+\.\d+\.\d+$/);
  assert.match(cfg.sizeMb, /^\d{1,4}$/);
  assert.match(cfg.released, /^\d{4}-\d{2}-\d{2}$/);
  const html = read("tapefolio/index.html");
  const gated = [...html.matchAll(/<a\b[^>]*data-tf-gated[^>]*>/g)].map((m) => m[0]);
  assert.ok(gated.length >= 2);
  for (const tag of gated) {
    assert.match(tag, /\shref="\/\.netlify\/functions\/tapefolio-download\?download=1"/);
    assert.doesNotMatch(tag, /aria-disabled/);
  }
  assert.doesNotMatch(html, /<button\b[^>]*id="checkout-btn"[^>]*\sdisabled/);
  assert.match(html, /id="checkout-btn" data-product="tapefolio"[^>]*>Buy Tapefolio<\/button>/);
  assert.doesNotMatch(html, /Not released yet|opens at release|are listed here when|data-tf-pre-only/);
  assert.doesNotMatch(html, /data-tf-live-only hidden/);
  assert.match(html, /<span data-tf-facts>Version 1\.0\.0, released October 9, 2026\. 43 MB disk image\.<\/span>/);
  assert.equal([...html.matchAll(/>Try it free for 7 days<\/a>/g)].length, 2);
  // What launch.js would write into the page is exactly what the static page already says.
  assert.equal(`Version ${cfg.version}, released October 9, 2026. ${cfg.sizeMb} MB disk image.`, "Version 1.0.0, released October 9, 2026. 43 MB disk image.");
  // The size is the published DMG's: 43,259,154 bytes is 43 MB to the nearest whole megabyte.
  assert.equal(Math.round(43259154 / 1e6), Number(cfg.sizeMb));
  const llms = read("llms.txt");
  assert.match(llms.slice(llms.indexOf("### Tapefolio")), /\*\*Status:\*\* Shipping, version 1\.0\.0/);
  assert.doesNotMatch(llms, /Not yet released/);
  const log = read("changelog/index.html");
  assert.match(log, /<span class="changelog-date">October 9, 2026<\/span>\s*<div class="changelog-content">\s*<span class="changelog-tag tag-launch">Launch<\/span>\s*<h2>Tapefolio 1\.0<\/h2>/);
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/tapefolio\/<\/loc>\s*<lastmod>2026-10-09<\/lastmod>/);
});

test("the page is indexable and the success page is not", () => {
  assert.match(read("tapefolio/index.html"), /<meta name="robots" content="index, follow">/);
  assert.match(read("tapefolio/success/index.html"), /<meta name="robots" content="noindex, nofollow">/);
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

test("the models table: Apple's recognition by default, then Parakeet, Whisper base, Whisper large-v3 turbo and Nemotron 3 Diarization as downloads", () => {
  const text = visibleText(read("tapefolio/index.html"));
  for (const name of ["Apple's speech recognition", "NVIDIA Parakeet", "Whisper base", "Whisper large-v3 turbo", "NVIDIA Nemotron 3 Diarization"]) assert.ok(text.includes(name), name);
  assert.match(text, /About 470 MB/);
  assert.match(text, /About 150 MB/);
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
  assert.match(gen, /"mac-suite":\s+\{[^}]*Six Mac apps/);
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

// ---- listings (the commit that links Tapefolio from the rest of the site) ----------------------

test("the sitemap, llms.txt, the search index, the products and pricing pages, the home page and the changelog list Tapefolio", () => {
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/tapefolio\/<\/loc>/);
  assert.doesNotMatch(read("sitemap.xml"), /tapefolio\/success/);
  const llms = read("llms.txt");
  assert.match(llms, /### Tapefolio \(macOS\)/);
  assert.match(llms, /https:\/\/purplelink\.llc\/tapefolio\//);
  assert.match(llms, /It does not anonymize a transcript/);
  assert.ok(JSON.parse(read("search-index.json")).some((e) => e.u === "/tapefolio/"));
  assert.match(read("products/index.html"), /<a class="catalog-card" href="\/tapefolio\/">/);
  assert.match(read("products/index.html"), /"name": "Tapefolio", "url": "https:\/\/purplelink\.llc\/tapefolio\/"/);
  assert.match(read("products/index.html"), /Six Mac apps, a set of pay-per-use/);
  assert.match(read("pricing/index.html"), /Tapefolio for Mac/);
  assert.match(read("pricing/index.html"), /\$29\.99 once/);
  assert.match(read("index.html"), /<a href="\/tapefolio\/">Tapefolio<\/a>, after a 7-day trial/);
  const log = read("changelog/index.html");
  assert.match(log, /<h2>Tapefolio 1\.0<\/h2>/);
  assert.match(log, /It will mishear words and miss some identifiers/);
});

test("every shared footer that links Keyfeel also links Tapefolio, and the layout generator and the digest publisher agree", () => {
  const missing = [];
  const walk = (dir) => {
    for (const name of readdirSync(join(SITE, dir))) {
      const rel = dir ? `${dir}/${name}` : name;
      if (rel.startsWith("blog/digest") || rel.startsWith("assets") || rel === "node_modules") continue;
      if (statSync(join(SITE, rel)).isDirectory()) walk(rel);
      else if (rel.endsWith(".html")) {
        const html = read(rel);
        const footer = html.match(/<footer class="footer">[\s\S]*?<\/footer>/);
        if (footer && footer[0].includes('<li><a href="/keyfeel/">Keyfeel</a></li>') && !footer[0].includes('<li><a href="/tapefolio/">Tapefolio</a></li>')) missing.push(rel);
      }
    }
  };
  walk("");
  assert.deepEqual(missing, []);
  const gen = readFileSync(join(SITE, "..", "scripts", "apply_layout.py"), "utf8");
  assert.match(gen, /\("Tapefolio", "\/tapefolio\/"\)/);
  assert.match(gen, /"keyfeel\/", "tapefolio\/"/);
  const publisher = readFileSync(join(SITE, "..", "backend", "digest", "publisher.py"), "utf8");
  assert.equal(publisher.split('<a href="/tapefolio/">Tapefolio</a>').length - 1, 2);
  assert.match(readFileSync(join(SITE, "..", "scripts", "gen_llms_full.py"), "utf8"), /"tapefolio\/",/);
});

test("the home page dock has an eighth tile for Tapefolio with its icon, and the dock CSS lays eight out", () => {
  const home = read("index.html");
  const tiles = [...home.matchAll(/<a class="dock-app" href="([^"]+)"/g)].map((m) => m[1]);
  assert.deepEqual(tiles, ["/moderntex/", "/outbound-veil/", "/legroom/", "/keyfeel/", "/tapefolio/", "/vitae/", "/scholar-utility-belt/", "/globepin/"]);
  assert.match(home, /<a class="dock-app" href="\/tapefolio\/" data-track="home_cta" data-track-meta="dock-tapefolio">\s*<span class="dock-art"><img src="\/assets\/tapefolio-icon\.webp" alt="" width="96" height="96" decoding="async"><\/span>\s*<strong class="dock-name">Tapefolio<\/strong>/);
  assert.match(home, /Free for 7 days, \$29\.99/);
  const css = read("home.css");
  assert.match(css, /\.dock \{[^}]*grid-template-columns: repeat\(8, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media \(max-width: 1599px\) \{\s*\.dock \{ grid-template-columns: repeat\(4, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media \(max-width: 560px\) \{\s*\.dock \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(css, /\.dock > li:nth-child\(8\) \{ animation-delay/);
  assert.match(css, /\.dock > li:nth-child\(8\) \.dock-art \{ animation-delay/);
  assert.doesNotMatch(css, /repeat\(7,/);
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

// ---- the Mac Suite --------------------------------------------------------------------------

test("the Suite page lists Tapefolio with its own price and card, keeps the $54.99 price, and warns about macOS 26", () => {
  const html = read("suite/index.html");
  assert.match(html, /<h3>Tapefolio<\/h3>/);
  assert.match(html, /href="\/tapefolio\/">See Tapefolio/);
  assert.match(html, /<span class="suite-row-name">Tapefolio<\/span><span class="suite-row-price">\$29\.99 once<\/span>/);
  assert.match(html, /Tapefolio needs macOS 26 or later and Apple silicon, with no Intel version/);
  assert.match(html, /Six Mac apps, one \$54\.99 payment/);
  assert.doesNotMatch(html, /\bfive Mac apps\b|Five Mac apps/i);
  assert.match(html, /<img class="suite-app-icon" src="\/assets\/tapefolio-icon\.webp" alt="" width="56" height="56" loading="lazy">\s*<h3>Tapefolio<\/h3>/);
  assert.match(html, /<img src="\/assets\/tapefolio-icon\.webp" alt="" width="72" height="72">/);
  assert.equal([...html.matchAll(/class="suite-icons"[\s\S]*?<\/div>/g)][0][0].match(/<img /g).length, 6, "six icons in the row");
  assert.ok(existsSync(join(SITE, "assets/tapefolio-icon.webp")));
  const app = jsonLd(html).find((n) => n["@type"] === "Product").hasPart.find((a) => a.name === "Tapefolio");
  assert.equal(app.operatingSystem, "macOS 26+");
  assert.equal(app.url, "https://purplelink.llc/tapefolio/");
});

test("every page that names the Suite's contents names Tapefolio, and none still says the old total or app count", () => {
  for (const p of ["suite/index.html", "terms/index.html", "llms.txt", "index.html", "products/index.html", "site.js", "vitae/plus/index.html", "outbound-veil/index.html", "outbound-veil/start/index.html", "moderntex/index.html", "legroom/index.html", "keyfeel/index.html", "tapefolio/index.html"]) {
    const src = read(p);
    for (const m of src.matchAll(/[^.<>]{0,120}Keyfeel[^.<>]{0,40}Vitae Plus[^.<>]{0,40}/g)) {
      assert.match(m[0], /Tapefolio/, `${p}: ${m[0].trim()}`);
    }
  }
  assert.match(read("products/index.html"), /Bought separately they come to \$124 the first year/);
  assert.doesNotMatch(read("products/index.html"), /come to \$94 the first year/);
  assert.match(read("suite/index.html"), /\$124/);
});

test("the Suite success page has a Tapefolio section and the script shows its key with the right label", async () => {
  const html = read("suite/success/index.html");
  assert.match(html, /id="dl-tf"/);
  assert.match(html, /Tapefolio&rsquo;s keys are with their downloads below/);
  const nodes = Object.fromEntries(["dl-moderntex", "dl-ov", "dl-lg", "dl-kf", "dl-tf", "license"].map((id) => [id, new FakeNode()]));
  const ctx = {
    document: { getElementById: (id) => nodes[id] || null, createElement: (t) => new FakeNode(t), createRange: () => ({}), body: new FakeNode("body") },
    window: { location: { search: `?session_id=${SID}` }, getSelection: () => ({}) },
    navigator: {}, URLSearchParams, encodeURIComponent, setTimeout: () => 0, Promise,
    fetch: (url) => {
      if (String(url).includes("tapefolio-download")) return reply(200, { license: "TFL1-ABCDE-FGHJK", files: [{ url: "/x", label: "Tapefolio 1.0.0 for macOS (disk image)" }] });
      if (String(url).includes("vitae-license")) return reply(200, { key: "VITAE-KEY" });
      return reply(200, { files: [{ url: "/x", label: "App" }] });
    },
  };
  // FakeNode in this file has no removeChild or firstChild; the Suite script clears boxes with them.
  FakeNode.prototype.removeChild = function (c) { this.children = this.children.filter((x) => x !== c); return c; };
  Object.defineProperty(FakeNode.prototype, "firstChild", { get() { return this.children[0] || null; }, configurable: true });
  vm.runInNewContext(readFileSync(join(SITE, "suite/success.js"), "utf8"), ctx);
  await tick();
  const box = nodes["dl-tf"];
  assert.equal(box.children[0].textContent, "Download: Tapefolio 1.0.0 for macOS (disk image)");
  assert.equal(box.children[1].textContent, "Your Tapefolio license key:");
  const holder = box.children[2];
  const code = holder.children.find((c) => c.tagName === "code");
  assert.equal(code.textContent, "TFL1-ABCDE-FGHJK");
  assert.equal(code.attrs["aria-label"], "Your Tapefolio license key");
});

// ---- updates and the update check -------------------------------------------------------------

test("every Tapefolio statement about updates is a plain promise of all updates, with no version or time limit", () => {
  const page = visibleText(read("tapefolio/index.html"));
  assert.match(page, /Every update is included\./);
  assert.match(page, /with every update included/);
  assert.match(page, /Are updates included\? Yes, all of them\. The price is a single payment\./);
  const ld = jsonLd(read("tapefolio/index.html")).find((n) => n["@type"] === "FAQPage").mainEntity.find((q) => q.name === "Are updates included?");
  assert.match(ld.acceptedAnswer.text, /^Yes, all of them\. The price is a single payment\./);
  const terms = read("terms/index.html");
  const section = terms.slice(terms.indexOf("<h2>Tapefolio: additional terms</h2>"), terms.indexOf("<h2>Mac Suite: additional terms</h2>"));
  assert.match(section, /<strong>Updates\.<\/strong> The purchase includes all updates to Tapefolio\. The app checks for updates and asks before installing one\.<\/li>/);
  const reminder = readFileSync(join(SITE, "..", "netlify", "functions", "tapefolio-reminder.mjs"), "utf8");
  assert.match(reminder, /with every update included/);
  for (const [name, text] of [["page", page], ["terms section", section], ["reminder", reminder]]) {
    assert.doesNotMatch(text, /version (you|of Tapefolio you) (buy|bought)|later major version|has not decided|major version/i, `${name} still limits updates`);
  }
});

test("the update check is described the same way everywhere: app name, version, macOS version and update token; models from Hugging Face; no analytics, no account", () => {
  const page = read("tapefolio/index.html");
  const text = visibleText(page);
  assert.match(text, /the app's name, its version, the macOS version and the app's update token to purplelink\.llc/);
  assert.match(text, /come from Hugging Face, once each/);
  assert.match(text, /macOS itself may download Apple's own speech model once if you use Apple's speech recognition/);
  assert.match(text, /There is no analytics and no account/);
  assert.doesNotMatch(text, /carries the app's name and version and nothing/);
  const faq = jsonLd(page).find((n) => n["@type"] === "FAQPage").mainEntity.find((q) => q.name === "Do my recordings leave my Mac?");
  assert.match(faq.acceptedAnswer.text, /app's name, its version, the macOS version and the app's update token/);
  assert.match(faq.acceptedAnswer.text, /Hugging Face/);
  assert.match(faq.acceptedAnswer.text, /macOS itself, which may download Apple's own speech model once/);
  assert.match(faq.acceptedAnswer.text, /nothing from your files is sent anywhere/);
  const privacy = read("privacy/index.html");
  const para = privacy.slice(privacy.indexOf("<strong>Tapefolio</strong> has no account"), privacy.indexOf("<strong>Find a purchase.</strong>"));
  assert.match(para, /no account and no analytics/);
  assert.match(para, /which come from Hugging Face/);
  assert.match(para, /Apart from three things it does not use the network/);
  assert.match(para, /macOS may download Apple's own speech model once/);
  assert.match(para, /Nothing you open in the app is in any of these requests/);
  assert.match(para, /the app's name, its version, the macOS version and an update token/);
  assert.match(read("terms/index.html"), /are downloaded from Hugging Face, come from their publishers/);
});

test("the Suite page, the Suite terms and llms.txt say the same about updates and the update check", () => {
  const terms = read("terms/index.html");
  assert.match(terms, /all updates to Keyfeel and Tapefolio, updates to the version of Legroom you receive/);
  assert.match(read("suite/index.html"), /so is every Keyfeel and Tapefolio update\. Legroom updates to the version you buy are included/);
  assert.match(read("suite/index.html"), /its check for a new version, which sends the app's name, its version and the macOS version, and macOS itself/);
});

test("the site promo card offers Tapefolio with its real icon, and never on its own page or the Suite page", () => {
  const src = read("site.js");
  const entry = src.match(/\{ id: 'tapefolio'[\s\S]*?own: \[[^\]]*\] \}/)[0];
  assert.match(entry, /icon: '\/assets\/tapefolio-icon-128\.webp'/);
  assert.match(entry, /\$29\.99/);
  assert.match(entry, /own: \['\/tapefolio\/', '\/suite\/'\]/);
  assert.doesNotMatch(entry, /[–—]/);
  assert.ok(existsSync(join(SITE, "assets/tapefolio-icon-128.webp")));
});

// ---- no bundled speech model ------------------------------------------------------------------

test("no Tapefolio text says a speech model is built in, works with no download, or that Hugging Face and the update check are the only network use", () => {
  const page = read("tapefolio/index.html");
  const terms = read("terms/index.html");
  const privacy = read("privacy/index.html");
  const tapefolioTerms = terms.slice(terms.indexOf("<h2>Tapefolio: additional terms</h2>"), terms.indexOf("<h2>Mac Suite: additional terms</h2>"));
  const tapefolioPrivacy = privacy.slice(privacy.indexOf("<strong>Tapefolio</strong> has no account"), privacy.indexOf("<strong>Find a purchase.</strong>"));
  const reminder = readFileSync(join(SITE, "..", "netlify", "functions", "tapefolio-reminder.mjs"), "utf8");
  const webhook = readFileSync(join(SITE, "..", "netlify", "functions", "stripe-webhook.mjs"), "utf8");
  const tapefolioMail = webhook.slice(webhook.indexOf("const tapefolioText"), webhook.indexOf("const text =\n"));
  const sources = {
    page: page.replace(/<script[^>]*src=[^>]*><\/script>/g, ""),
    success: read("tapefolio/success/index.html"),
    terms: tapefolioTerms, privacy: tapefolioPrivacy, reminder, mail: tapefolioMail,
  };
  for (const [name, text] of Object.entries(sources)) {
    assert.doesNotMatch(text, /built in\b(?! to)|built-in|works? with no download|so you can start with no download\b(?! from)|no download\b(?! from)|the moment it is installed|small speech model|One small/i, `${name} says a model is built in`);
    assert.doesNotMatch(text, /only (other )?(use|things)[^.]{0,40}(internet|network)|only network use/i, `${name} says the network use is only the downloads and the update check`);
  }
  // The default engine and its one-time fetch by macOS are stated where the network use is.
  for (const [name, text] of Object.entries({ page: visibleText(page), privacy: tapefolioPrivacy })) {
    assert.match(text, /Apple's (own )?(on-device )?speech (model|recognition)/, name);
    assert.match(text, /macOS (itself )?may (download|fetch) Apple's own (speech )?model once|macOS may download Apple's own speech model once/, name);
  }
  // Measured error rates, exactly as measured: Apple, Parakeet and Whisper large 21% to 29%; Whisper base 29% to 39%.
  const text = visibleText(page);
  assert.match(text, /between 21% and 29% for Apple's engine, Parakeet and Whisper large-v3 turbo, and between 29% and 39% for Whisper base, the small optional download/);
  const faq = jsonLd(page).find((n) => n["@type"] === "FAQPage").mainEntity.find((q) => q.name === "How accurate is it?");
  assert.match(faq.acceptedAnswer.text, /between 21% and 29% for Apple's speech recognition, Parakeet and Whisper large-v3 turbo, and between 29% and 39% for the small Whisper base model/);
  const features = jsonLd(page).find((n) => n["@type"] === "SoftwareApplication").featureList.join(" ");
  assert.match(features, /Apple's on-device speech recognition until you download a speech model/);
  assert.doesNotMatch(features, /built in|no download/i);
  // The first-run wait is per model.
  assert.match(text, /The first time each model runs on a Mac, it can take a few minutes while macOS prepares the model for the Neural Engine/);
  assert.match(text, /macOS prepares a speech model for the Neural Engine the first time that model runs on a Mac/);
  assert.match(read("tapefolio/success/index.html"), /The first time each model runs on a Mac, it can take a few minutes while macOS prepares it for the Neural Engine/);
  // The speaker models that ship with the app are named as such; Nemotron stays optional.
  assert.match(text, /standard speaker-separation models that come with the app/);
  assert.match(text, /The app is about 40 MB/);
});

test("the Suite pages do not say a model is built in, and describe the network use as three things", () => {
  const suite = read("suite/index.html");
  const success = read("suite/success/index.html");
  const faq = suite.match(/Does Tapefolio send my recordings anywhere\?[\s\S]{0,900}/g).join(" ");
  assert.doesNotMatch(faq, /built in\b(?! to)|built-in|no download\b(?! from)|small speech model|One small|only the optional model downloads/i);
  assert.doesNotMatch(success, /built in\b(?! to)|built-in|small speech model|One small/i);
  assert.equal((suite.match(/macOS itself, which may download Apple's own speech model once\. Nothing from your files is sent\./g) || []).length, 2, "HTML and JSON-LD");
  assert.match(success, /The first time each model runs on a Mac, it can take a few minutes while macOS prepares it for the Neural Engine/);
  assert.match(success, /Tapefolio uses Apple's on-device speech recognition/);
});

test("llms.txt does not say a model is built in, and states the measured error rates and the network use", () => {
  const llms = read("llms.txt");
  const block = llms.slice(llms.indexOf("### Tapefolio"), llms.indexOf("### Mac Suite"));
  assert.doesNotMatch(block, /built in\b(?! to)|built-in|no download\b(?! from)|small speech model|One small/i);
  assert.match(block, /No speech model is bundled \(the app is about 40 MB\)/);
  assert.match(block, /Apple's on-device speech recognition, and macOS may download Apple's own model once/);
  assert.match(block, /Whisper base \(English, about 150 MB\)/);
  assert.match(block, /between 21% and 29% for Apple's recognition, Parakeet and Whisper large-v3 turbo, and between 29% and 39% for Whisper base/);
  assert.match(block, /Nothing from your files is sent/);
  assert.match(block, /then \$29\.99 once, every update included/);
  assert.match(block, /sends its name, its version, the macOS version and its update token to purplelink\.llc/);
  assert.match(block, /from Hugging Face/);
  assert.doesNotMatch(block, /version (you|of Tapefolio you) (buy|bought)|major version/i);
});
