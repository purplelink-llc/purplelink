// Reddit conversion pixel (2026-10-29): it loads only for a visitor who first arrived from a Reddit ad and does not send
// Do Not Track, reports a trial download, a Buy click and a purchase, and the CSP lets exactly its hosts through.
// Run with: node --test netlify/tests/reddit-pixel.test.mjs
import { readFileSync } from "node:fs";
import vm from "node:vm";
import test from "node:test";
import assert from "node:assert/strict";

const analyticsSrc = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");
const pixelFile = readFileSync(new URL("../../site/reddit-pixel.js", import.meta.url), "utf8");
const withId = pixelFile.replace('var PIXEL_ID = "";', 'var PIXEL_ID = "a2_test";');

// The pixel's queued calls as plain data (objects made inside the vm sandbox never compare equal to ours).
const queue = (sb) => (sb.rdt ? JSON.parse(JSON.stringify(sb.rdt.callQueue.map((a) => [...a]))) : []);

// One browser, so first-touch attribution carries from the landing visit to the success page.
function browser({ dnt = "" } = {}) {
  const store = {};
  return {
    visit(path, search = "", src = withId) {
      const appended = [];
      const listeners = [];
      const sandbox = {
        navigator: { sendBeacon: () => true, doNotTrack: dnt }, Blob: class { constructor(p) { this.p = p; } },
        URL, URLSearchParams, Date, JSON, Math, String, RegExp, Object,
        document: {
          referrer: "", addEventListener: (type, fn) => listeners.push([type, fn]),
          createElement: () => ({}), head: { appendChild: (el) => appended.push(el) },
        },
        location: { search, pathname: path, host: "purplelink.llc", hostname: "purplelink.llc" },
        localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; }, removeItem: (k) => { delete store[k]; } },
      };
      sandbox.window = sandbox;
      vm.runInNewContext(analyticsSrc, sandbox);
      vm.runInNewContext(src, sandbox);
      const calls = queue(sandbox);
      const click = (attrs) => {
        const el = { getAttribute: (k) => attrs[k] ?? null };
        el.closest = () => el;
        for (const [type, fn] of listeners) if (type === "click") fn({ target: el });
        return queue(sandbox);
      };
      return { appended, calls, click };
    },
  };
}

const AD = "?utm_source=reddit&utm_medium=paid&utm_campaign=moderntex-latex-2026-11";

test("with no pixel id the script does nothing, even for a Reddit ad click", () => {
  const v = browser().visit("/moderntex/", AD + "&rdt_cid=abc", pixelFile);
  assert.equal(v.appended.length, 0);
  assert.deepEqual(v.calls, []);
});

test("a visitor from Google or typing the address never loads Reddit", () => {
  for (const search of ["", "?utm_source=google"]) {
    const v = browser().visit("/moderntex/", search);
    assert.equal(v.appended.length, 0, search);
  }
});

test("Do Not Track keeps it off for a Reddit ad click", () => {
  const v = browser({ dnt: "1" }).visit("/moderntex/", AD + "&rdt_cid=abc");
  assert.equal(v.appended.length, 0);
});

test("a Reddit ad click loads the pixel and records the page visit", () => {
  for (const search of [AD, "?rdt_cid=abc"]) {
    const v = browser().visit("/moderntex/", search);
    assert.equal(v.appended.length, 1, search);
    assert.equal(v.appended[0].src, "https://www.redditstatic.com/ads/pixel.js");
    assert.deepEqual(v.calls.slice(0, 2), [["init", "a2_test"], ["track", "PageVisit"]]);
  }
});

test("the trial download is a Lead and a Buy click is AddToCart", () => {
  const v = browser().visit("/moderntex/", AD);
  assert.deepEqual(v.click({ href: "/.netlify/functions/moderntex-download?trial=1" }).at(-1), ["track", "Lead"]);
  assert.deepEqual(v.click({ "data-product": "moderntex" }).at(-1), ["track", "AddToCart", { currency: "USD", value: 19.99, itemCount: 1 }]);
  assert.equal(v.click({ href: "/guides/" }).length, 4);
});

test("a Reddit ad visitor's purchase is reported once per Stripe session", () => {
  const b = browser();
  b.visit("/moderntex/", AD);
  const v = b.visit("/moderntex/success/", "?session_id=cs_test_123");
  assert.deepEqual(v.calls.at(-1), ["track", "Purchase", { currency: "USD", value: 19.99, itemCount: 1, conversionId: "cs_test_123" }]);
});

test("a purchase by someone who did not come from a Reddit ad is not reported", () => {
  const b = browser();
  b.visit("/moderntex/", "?utm_source=google");
  assert.equal(b.visit("/moderntex/success/", "?session_id=cs_test_123").appended.length, 0);
});

test("every ModernTex page that loads the pixel loads analytics.js first, and the CSP allows Reddit's hosts", () => {
  for (const page of ["moderntex/index.html", "moderntex/buy/index.html", "moderntex/success/index.html"]) {
    const html = readFileSync(new URL(`../../site/${page}`, import.meta.url), "utf8");
    const a = html.indexOf("/analytics.js"), r = html.indexOf("/reddit-pixel.js");
    assert.ok(a > 0 && r > a, page);
  }
  const csp = readFileSync(new URL("../../netlify.toml", import.meta.url), "utf8").split("\n").find((l) => l.trim().startsWith("Content-Security-Policy"));
  const dir = (name) => csp.split(";").find((d) => d.trim().startsWith(name + " "));
  assert.match(dir("script-src"), /https:\/\/www\.redditstatic\.com/);
  assert.match(dir("connect-src"), /https:\/\/alb\.reddit\.com/);
  assert.match(dir("connect-src"), /https:\/\/pixel-config\.reddit\.com/);
  assert.match(dir("img-src"), /https:\/\/alb\.reddit\.com/);
});
