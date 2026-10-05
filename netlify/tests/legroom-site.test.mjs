// The Legroom pages and the Suite page, checked as files: the offer in the structured data,
// the wiring of the buttons, the screenshots, and the success pages' scripts run against a
// small fake DOM and a stubbed fetch.
//
// Run with: node --test netlify/tests/legroom-site.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync, existsSync } from "node:fs";
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

// ---- product page --------------------------------------------------------------------

test("the Legroom page offers the app at $9 once, with a 14-day refund, in valid JSON-LD", () => {
  const app = jsonLd(read("legroom/index.html")).find((n) => n["@type"] === "SoftwareApplication");
  assert.equal(app.name, "Legroom");
  assert.equal(app.offers.price, "9.00");
  assert.equal(app.offers.priceCurrency, "USD");
  assert.equal(app.offers.hasMerchantReturnPolicy.merchantReturnDays, 14);
  assert.equal(app.operatingSystem, "macOS 14+");
});

test("the trial button and the buy button are wired to the delivery and checkout functions", () => {
  const html = read("legroom/index.html");
  assert.match(html, /href="\/\.netlify\/functions\/legroom-download\?trial=1"/);
  assert.match(html, /id="checkout-btn" data-product="legroom"/);
  assert.match(html, /paid-tool-landing\.js/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/legroom\/">/);
  assert.match(html, /<meta name="robots" content="index, follow">/);
});

test("the Legroom page has no inline styles, em or en dashes, emoji or unreleased features", () => {
  for (const p of ["legroom/index.html", "legroom/success/index.html"]) {
    const html = read(p);
    assert.doesNotMatch(html, /<[a-z][^>]*\sstyle\s*=/i, `${p} has an inline style`);
    assert.doesNotMatch(html, /[–—]/, `${p} has an em or en dash`);
    assert.doesNotMatch(html, /\p{Extended_Pictographic}/u, `${p} has an emoji`);
  }
  const page = read("legroom/index.html").toLowerCase();
  for (const planned of ["uninstaller", "widget", "command-line tool", "command line tool"]) {
    assert.ok(!page.includes(planned), `the page advertises a planned feature: ${planned}`);
  }
});

test("every screenshot on the page exists, has a size and alt text, and is under 250 KB", () => {
  const html = read("legroom/index.html");
  const imgs = [...html.matchAll(/<img\b[^>]*src="(\/legroom\/img\/[^"]+)"[^>]*>/g)];
  assert.ok(imgs.length >= 4 && imgs.length <= 6, `expected 4 to 6 screenshots, found ${imgs.length}`);
  for (const [tag, src] of imgs) {
    assert.ok(existsSync(join(SITE, src)), `${src} is missing`);
    assert.ok(statSync(join(SITE, src)).size < 250 * 1024, `${src} is over 250 KB`);
    assert.match(tag, /\swidth="\d+"/);
    assert.match(tag, /\sheight="\d+"/);
    assert.match(tag, /\salt="[^"]{40,}"/, `${src} needs real alt text`);
  }
  assert.ok((html.match(/Sample data/g) || []).length >= imgs.length, "each screenshot is captioned as sample data");
});

test("the share image and the icon exist, and the share image is 1200 by 630", () => {
  const png = readFileSync(join(SITE, "assets/og/legroom.png"));
  assert.equal(png.readUInt32BE(16), 1200);
  assert.equal(png.readUInt32BE(20), 630);
  assert.ok(existsSync(join(SITE, "assets/legroom-icon.webp")));
});

test("the success page is noindex and loads its script", () => {
  const html = read("legroom/success/index.html");
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.match(html, /src="\/legroom\/success\.js/);
  assert.match(html, /id="downloads"/);
});

test("the sitemap, llms.txt and the search index list Legroom, and the success page is not listed", () => {
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/legroom\/<\/loc>/);
  assert.doesNotMatch(read("sitemap.xml"), /legroom\/success/);
  assert.match(read("llms.txt"), /https:\/\/purplelink\.llc\/legroom\//);
  assert.ok(JSON.parse(read("search-index.json")).some((e) => e.u === "/legroom/"));
});

// ---- suite page ----------------------------------------------------------------------

test("the Suite page sells four apps at $49 and no longer says $39", () => {
  const html = read("suite/index.html");
  const product = jsonLd(html).find((n) => n["@type"] === "Product");
  assert.equal(product.offers.price, "49.00");
  assert.deepEqual(product.hasPart.map((a) => a.name), ["ModernTex", "Outbound Veil", "Legroom", "Vitae Plus"]);
  assert.match(html, /Buy the Suite, \$49/);
  assert.match(html, /<span id="price">\$49<\/span>/);
  assert.match(html, /data-product="app-suite"/);
  assert.doesNotMatch(html, /\$39/);
  assert.doesNotMatch(html, /[–—]/);
});

test("the Suite's separate prices are the real ones, and the first-year total adds up", () => {
  const html = read("suite/index.html");
  for (const row of ["ModernTex</span><span class=\"suite-row-price\">$19.99 once", "Outbound Veil</span><span class=\"suite-row-price\">$29 once",
                     "Legroom</span><span class=\"suite-row-price\">$9 once", "Vitae Plus</span><span class=\"suite-row-price\">$24 a year"]) {
    assert.ok(html.includes(row), row);
  }
  assert.match(html, /suite-sum-amount">\$82</); // 19.99 + 29 + 9 + 24 = 81.99
});

test("the Terms, llms.txt and the products page carry the $49 Suite", () => {
  assert.match(read("terms/index.html"), /Mac Suite is one payment of \$49 USD/);
  assert.match(read("terms/index.html"), /<h2>Legroom: additional terms<\/h2>/);
  assert.match(read("llms.txt"), /Mac Suite \(macOS, \$49 once: ModernTex, Outbound Veil, Legroom and Vitae Plus/);
  assert.match(read("products/index.html"), /<span class="catalog-card-price">\$49 once<\/span>/);
  for (const p of ["llms.txt", "products/index.html", "terms/index.html", "vitae/plus/index.html", "outbound-veil/index.html", "outbound-veil/start/index.html"]) {
    assert.doesNotMatch(read(p), /(Mac Suite[^.]{0,120}\$39|\$39[^.]{0,40}Mac Suite)/, `${p} still prices the Suite at $39`);
  }
});

// ---- the success pages' scripts, against a fake DOM ------------------------------------

class FakeNode {
  constructor(tag = "div") { this.tagName = tag; this.children = []; this.attrs = {}; this.textContent = ""; this.className = ""; this.href = ""; }
  get firstChild() { return this.children[0] || null; }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener() {}
}

function runScript(file, { search, ids, fetchImpl }) {
  const nodes = Object.fromEntries(ids.map((id) => [id, new FakeNode()]));
  const fetched = [];
  const ctx = {
    document: { getElementById: (id) => nodes[id] || null, createElement: (t) => new FakeNode(t), createRange: () => ({}), body: new FakeNode("body") },
    window: { location: { search }, getSelection: () => ({}) },
    navigator: {},
    URLSearchParams,
    encodeURIComponent,
    setTimeout: () => 0,
    fetch: (url) => { fetched.push(url); return fetchImpl(url); },
    Promise,
  };
  vm.runInNewContext(readFileSync(join(SITE, file), "utf8"), ctx);
  return { nodes, fetched };
}
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const SID = "cs_live_abcdefghij1234";

test("/legroom/success/ asks legroom-download for the session and shows a download button", async () => {
  const { nodes, fetched } = runScript("legroom/success.js", {
    search: `?session_id=${SID}`, ids: ["downloads", "dl-status"],
    fetchImpl: () => reply(200, { files: [{ key: "Legroom-1.0.0.dmg", label: "Legroom 1.0.0 for macOS (disk image)", url: "/.netlify/functions/legroom-download?session_id=x&file=Legroom-1.0.0.dmg" }] }),
  });
  await tick();
  assert.deepEqual(fetched, [`/.netlify/functions/legroom-download?session_id=${SID}`]);
  assert.match(nodes.downloads.innerHTML, /Download: Legroom 1\.0\.0 for macOS/);
  assert.match(nodes.downloads.innerHTML, /legroom-download\?session_id=x&amp;file=Legroom-1\.0\.0\.dmg/);
});

test("/legroom/success/ shows the server's reason when the session is refused, and never fetches for a bad id", async () => {
  const refused = runScript("legroom/success.js", {
    search: `?session_id=${SID}`, ids: ["downloads", "dl-status"],
    fetchImpl: () => reply(403, { error: "not_entitled", detail: "This order is for a different product." }),
  });
  await tick();
  assert.match(refused.nodes.downloads.innerHTML, /This order is for a different product\./);

  const bad = runScript("legroom/success.js", { search: "?session_id=nope", ids: ["downloads", "dl-status"], fetchImpl: () => assert.fail("fetched") });
  await tick();
  assert.equal(bad.fetched.length, 0);
  assert.match(bad.nodes.downloads.innerHTML, /receipt email/);
});

test("/suite/success/ fetches all four parts: three downloads and the Vitae key", async () => {
  const { fetched } = runScript("suite/success.js", {
    search: `?session_id=${SID}`, ids: ["dl-moderntex", "dl-ov", "dl-lg", "license"],
    fetchImpl: (url) => (String(url).includes("vitae-license") ? reply(200, { key: "VITAE-KEY" }) : reply(200, { files: [{ url: "/x", label: "App" }] })),
  });
  await tick();
  assert.deepEqual(fetched.map((u) => u.split("?")[0]).sort(), [
    "/.netlify/functions/legroom-download",
    "/.netlify/functions/moderntex-download",
    "/.netlify/functions/outbound-veil-download",
    "/.netlify/functions/vitae-license",
  ]);
  assert.ok(fetched.every((u) => u.endsWith(`session_id=${SID}`)));
});

test("/suite/success/ keeps working for the other parts when the Legroom part fails", async () => {
  const { nodes } = runScript("suite/success.js", {
    search: `?session_id=${SID}`, ids: ["dl-moderntex", "dl-ov", "dl-lg", "license"],
    fetchImpl: (url) => {
      if (String(url).includes("legroom-download")) return reply(500, { detail: "The file is temporarily unavailable." });
      if (String(url).includes("vitae-license")) return reply(200, { key: "VITAE-KEY" });
      return reply(200, { files: [{ url: "/x", label: "App" }] });
    },
  });
  await tick();
  assert.equal(nodes["dl-moderntex"].children[0].textContent, "Download: App");
  assert.equal(nodes["dl-ov"].children[0].textContent, "Download: App");
  assert.equal(nodes["dl-lg"].children[0].textContent, "The file is temporarily unavailable.");
});

test("the Suite success page has a Legroom section for the script to fill", () => {
  const html = read("suite/success/index.html");
  assert.match(html, /id="dl-lg"/);
  assert.match(html, /ModernTex, Outbound Veil and Legroom downloads/);
});
