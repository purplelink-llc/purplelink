// pl_attr cookie (2026-10-29): the server sets it at a ModernTex trial download for ad/campaign visitors, checkout
// falls back to it, and the success page learns reddit_ad from the order. Stripe and Blobs are stubbed.
// Run with: node --experimental-test-module-mocks --test netlify/tests/attr-cookie.test.mjs
import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const stores = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => stores.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { stores.set(`${name}/${k}`, v); },
    list: async () => ({ blobs: [...stores.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
    getWithMetadata: async (k) => (stores.has(`${name}/${k}`) ? { data: new Response(`bytes:${k}`).body, metadata: { size: 9 } } : null),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { STRIPE_SECRET_KEY: "sk_test_x", STRIPE_PRICE_MODERNTEX: "price_mtx", STRIPE_PRICE_PAPER_REVIEW_STANDARD: "price_pr" };
globalThis.Netlify = { env: { get: (k) => env[k] || "" } };
const download = (await import("../functions/moderntex-download.mjs")).default;
const checkout = (await import("../functions/checkout.mjs")).default;
const lib = await import("../lib/attr-cookie.mjs");

const TRIAL = "https://purplelink.llc/.netlify/functions/moderntex-download?trial=1";
const trial = (qs = "", headers = {}) =>
  download(new Request(TRIAL + qs, { headers: { "x-nf-client-connection-ip": "198.51.100.9", ...headers } }), {});
const today = new Date().toISOString().slice(0, 10);

beforeEach(() => {
  stores.clear();
  stores.set("moderntex-files/ModernTex-1.10.0.dmg", "x");
});

test("an ad visitor's trial download sets pl_attr with the right attributes", async () => {
  const res = await trial(`&ach=paid:reddit&arc=abc123_-.x&ad=${today}`);
  assert.equal(res.status, 200);
  assert.equal(await res.text(), "bytes:ModernTex-1.10.0.dmg");
  assert.match(res.headers.get("content-disposition"), /ModernTex-1\.10\.0\.dmg/);
  const c = res.headers.get("set-cookie");
  assert.equal(c, `pl_attr=v2~paid:reddit~abc123_-.x~~${today}; Path=/; Max-Age=7776000; HttpOnly; Secure; SameSite=Lax`);
});

test("a campaign visitor without a click id gets a cookie; the first-seen date falls back to today when absent or bad", async () => {
  let c = (await trial("&ach=newsletter")).headers.get("set-cookie");
  assert.match(c, new RegExp(`^pl_attr=v2~newsletter~~~${today};`));
  c = (await trial("&ach=newsletter&ad=2099-01-01")).headers.get("set-cookie");
  assert.match(c, new RegExp(`~${today};`));
  c = (await trial("&ach=newsletter&ad=2020-01-01")).headers.get("set-cookie");
  assert.match(c, new RegExp(`~${today};`));
});

test("no cookie for a direct visitor, no params, or Do Not Track", async () => {
  assert.equal((await trial()).headers.get("set-cookie"), null);
  assert.equal((await trial("&ach=direct")).headers.get("set-cookie"), null);
  const dnt = await trial("&ach=paid:reddit&arc=abc", { dnt: "1" });
  assert.equal(dnt.status, 200);
  assert.equal(dnt.headers.get("set-cookie"), null);
});

test("no cookie on non-trial downloads (update channel, purchase door)", async () => {
  globalThis.Netlify = { env: { get: (k) => (k === "MODERNTEX_UPDATE_TOKEN" ? "tok" : env[k] || "") } };
  const res = await download(new Request("https://purplelink.llc/.netlify/functions/moderntex-download?update=ModernTex-1.10.0.dmg&ach=paid:reddit&arc=abc", {
    headers: { "x-moderntex-channel": "tok" },
  }), {});
  globalThis.Netlify = { env: { get: (k) => env[k] || "" } };
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("set-cookie"), null);
});

test("the earliest cookie is kept: an existing valid pl_attr means no new Set-Cookie", async () => {
  const res = await trial("&ach=paid:google&arc=zzz", { cookie: `other=1; pl_attr=v1~paid:reddit~abc~2026-10-01` });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("set-cookie"), null);
  // an invalid existing cookie does not count as one
  const res2 = await trial("&ach=paid:google", { cookie: "pl_attr=garbage" });
  assert.match(res2.headers.get("set-cookie"), /^pl_attr=v2~paid:google~~~/);
});

test("invalid params are ignored and the download still works", async () => {
  for (const qs of ["&ach=" + encodeURIComponent("x\r\nSet-Cookie: evil=1"), "&ach=" + "a".repeat(200), "&ach=a;b", "&arc=" + encodeURIComponent("a b;c"), "&ach=%E0%A4%A"]) {
    const res = await trial(qs);
    assert.equal(res.status, 200, qs);
    assert.equal(await res.text(), "bytes:ModernTex-1.10.0.dmg");
    assert.equal(res.headers.get("set-cookie"), null, qs);
  }
  // a bad click id with a good channel keeps the channel only
  const res = await trial("&ach=paid:reddit&arc=" + encodeURIComponent("bad id;"));
  assert.match(res.headers.get("set-cookie"), new RegExp(`^pl_attr=v2~paid:reddit~~~${today};`));
});

test("the cookie holds only channel, click id and a date (nothing personal)", async () => {
  const res = await trial("&ach=paid:reddit&arc=abc&ad=" + today, { "x-forwarded-for": "203.0.113.7", "user-agent": "UA-secret", referer: "https://example.com/me@x.com" });
  const c = res.headers.get("set-cookie");
  const value = c.split(";")[0].slice("pl_attr=".length);
  assert.equal(value, `v2~paid:reddit~abc~~${today}`);
  assert.doesNotMatch(c, /203\.0\.113|198\.51\.100|UA-secret|@/);
  assert.deepEqual(lib.decodeValue(value), { channel: "paid:reddit", rdt: "abc", tag: "", date: today });
  assert.equal(lib.decodeValue("v1~a;b~~2026-01-01"), null);
  assert.equal(lib.decodeValue("v1~paid:reddit~abc~2026-13-45"), null);
});

// ---- checkout ----
let sessions;
function stubStripe() {
  sessions = [];
  globalThis.fetch = async (url, init) => {
    if (String(url).includes("api.stripe.com/v1/checkout/sessions")) {
      const params = new URLSearchParams(init.body);
      sessions.push(Object.fromEntries(params));
      return new Response(JSON.stringify({ id: "cs_live_x", url: "https://checkout.stripe.com/c/pay/cs_live_x" }), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  };
}
let n = 0;
const buy = (body, cookie) =>
  checkout(new Request("https://purplelink.llc/.netlify/functions/checkout", {
    method: "POST",
    headers: { "content-type": "application/json", origin: "https://purplelink.llc", "x-nf-client-connection-ip": `198.51.100.${(n++ % 200) + 1}`, ...(cookie ? { cookie } : {}) },
    body: JSON.stringify(body),
  }), {});
const COOKIE = "pl_attr=v1~paid:reddit~clickabc~2026-10-20";

test("checkout falls back to pl_attr: first touch and Reddit metadata filled for ModernTex", async () => {
  stubStripe();
  const res = await buy({ product: "moderntex" }, COOKIE);
  assert.equal(res.status, 200, await res.clone().text());
  const p = sessions[0];
  assert.deepEqual(JSON.parse(p["metadata[attr_first]"]), { d: "2026-10-20", c: "attr-cookie", s: "reddit", m: "cpc" });
  assert.equal(p["metadata[reddit_ad]"], "1");
  assert.equal(p["metadata[reddit_click_id]"], "clickabc");
});

test("the funnel reads the cookie-derived first touch as the same channel (paid:reddit)", async () => {
  const t = lib.touchFromCookie(lib.decodeValue("v1~paid:reddit~clickabc~2026-10-20"));
  assert.equal(t.s, "reddit");
  assert.equal(t.m, "cpc");
  assert.equal(lib.touchFromCookie({ channel: "tool:word-counter", rdt: "", date: "2026-10-20" }).s, "tool-word-counter");
  assert.equal(lib.touchFromCookie({ channel: "newsletter", rdt: "", date: "2026-10-20" }).s, "newsletter");
});

test("body data wins over the cookie", async () => {
  stubStripe();
  await buy({ product: "moderntex", attr: { first: { s: "bluesky", d: "2026-10-27" } }, rdt: { c: "bodyclick" } }, COOKIE);
  const p = sessions[0];
  assert.equal(JSON.parse(p["metadata[attr_first]"]).s, "bluesky");
  assert.equal(p["metadata[reddit_click_id]"], "bodyclick");
});

test("a placeholder first touch from the body (no source) is filled from the cookie", async () => {
  stubStripe();
  await buy({ product: "moderntex", attr: { first: { x: 1, l: "/moderntex/", d: "2026-11-01" } } }, COOKIE);
  assert.equal(JSON.parse(sessions[0]["metadata[attr_first]"]).s, "reddit");
});

test("reddit_ad from the cookie is set for ModernTex only", async () => {
  stubStripe();
  await buy({ product: "paper-review-standard" }, COOKIE);
  assert.equal(sessions[0]["metadata[reddit_ad]"], undefined);
  assert.equal(sessions[0]["metadata[reddit_click_id]"], undefined);
});

test("no cookie and a malformed cookie change nothing", async () => {
  stubStripe();
  await buy({ product: "moderntex" });
  assert.equal(sessions[0]["metadata[reddit_ad]"], undefined);
  assert.equal(sessions[0]["metadata[attr_first]"], undefined);
  await buy({ product: "moderntex" }, "pl_attr=v1~paid:reddit;evil~x~2026-10-20");
  assert.equal(sessions[1]["metadata[reddit_ad]"], undefined);
});

// ---- success page ----
test("the purchase door reports reddit_ad from the session metadata", async () => {
  const sid = "cs_live_abcdefghij1234";
  for (const flag of ["1", undefined]) {
    globalThis.fetch = async () => new Response(JSON.stringify({ payment_status: "paid", metadata: { product: "moderntex", ...(flag ? { reddit_ad: flag } : {}) } }), { status: 200 });
    const res = await download(new Request(`https://purplelink.llc/.netlify/functions/moderntex-download?session_id=${sid}`), {});
    const b = await res.json();
    assert.equal(res.status, 200);
    assert.equal(b.reddit_ad, flag === "1");
  }
});

// ---- client scripts ----
const analyticsSrc = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");
function page({ search = "", dnt = "", store = {} } = {}) {
  const listeners = [];
  const sb = {
    navigator: { sendBeacon: () => true, doNotTrack: dnt }, Blob: class {},
    URL, URLSearchParams, Date, JSON, Math, String, RegExp, Object,
    document: { referrer: "", addEventListener: (t, f) => listeners.push([t, f]) },
    location: { search, pathname: "/moderntex/", host: "purplelink.llc", hostname: "purplelink.llc", href: "https://purplelink.llc/moderntex/", origin: "https://purplelink.llc" },
    localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; }, removeItem: (k) => { delete store[k]; } },
  };
  sb.window = sb;
  vm.runInNewContext(analyticsSrc, sb);
  const clickTrial = () => {
    const attrs = { href: "/.netlify/functions/moderntex-download?trial=1" };
    const a = { href: "https://purplelink.llc" + attrs.href, getAttribute: (k) => attrs[k], setAttribute: (k, v) => { attrs[k] = v; }, closest: () => a };
    for (const [t, f] of listeners) if (t === "click") f({ target: a });
    return attrs.href;
  };
  return { clickTrial };
}

test("analytics.js tags the trial link for a Reddit ad visitor, and leaves it alone for direct visitors and DNT", () => {
  const ad = page({ search: "?utm_source=reddit&utm_medium=paid&rdt_cid=abc123" }).clickTrial();
  const u = new URL(ad, "https://purplelink.llc");
  assert.equal(u.searchParams.get("trial"), "1");
  assert.equal(u.searchParams.get("ach"), "paid:reddit");
  assert.equal(u.searchParams.get("arc"), "abc123");
  assert.match(u.searchParams.get("ad"), /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(page().clickTrial(), "/.netlify/functions/moderntex-download?trial=1");
  assert.equal(page({ search: "?utm_source=reddit&utm_medium=paid&rdt_cid=abc123", dnt: "1" }).clickTrial(), "/.netlify/functions/moderntex-download?trial=1");
});

test("reddit-pixel.js: on the success page an order marked reddit_ad fires Purchase even without stored attribution", () => {
  const pixel = readFileSync(new URL("../../site/reddit-pixel.js", import.meta.url), "utf8").replace(/var PIXEL_ID = "[^"]*";/, 'var PIXEL_ID = "a2_test";');
  const run = (path, { early = false, dnt = "" } = {}) => {
    const sb = {
      navigator: { doNotTrack: dnt }, URLSearchParams, Object, String,
      document: { addEventListener() {}, createElement: () => ({}), head: { appendChild() {} } },
      location: { search: "?session_id=cs_live_abcdefghij1234", pathname: path },
    };
    sb.window = sb;
    if (early) sb.plRedditAd = true;
    vm.runInNewContext(pixel, sb);
    return sb;
  };
  const events = (sb) => (sb.rdt ? [...sb.rdt.callQueue].map((a) => a[1]) : []);
  let sb = run("/moderntex/success/");
  assert.deepEqual(events(sb), []);
  sb.plRedditPurchase();
  sb.plRedditPurchase();
  assert.deepEqual(events(sb), ["a2_test", "PageVisit", "Purchase"]);
  assert.deepEqual(events(run("/moderntex/success/", { early: true })), ["a2_test", "PageVisit", "Purchase"]);
  assert.equal(run("/moderntex/").plRedditPurchase, undefined);
  assert.deepEqual(events(run("/moderntex/success/", { early: true, dnt: "1" })), []);
});

// ---- the ad tag (utm_content), 2026-10-29 ----
test("the trial link carries the first touch's ad tag, and the cookie keeps it (v2)", async () => {
  const href = page({ search: "?utm_source=reddit&utm_medium=cpc&utm_content=moderntex-reddit-261027-a&rdt_cid=abc" }).clickTrial();
  assert.equal(new URL(href, "https://purplelink.llc").searchParams.get("atg"), "moderntex-reddit-261027-a");
  // no tag on the link: no atg parameter
  assert.equal(new URL(page({ search: "?utm_source=reddit&utm_medium=cpc&rdt_cid=abc" }).clickTrial(), "https://purplelink.llc").searchParams.get("atg"), null);
  const c = (await trial(`&ach=paid:reddit&arc=abc&atg=moderntex-reddit-261027-a&ad=${today}`)).headers.get("set-cookie");
  assert.equal(c.split(";")[0], `pl_attr=v2~paid:reddit~abc~moderntex-reddit-261027-a~${today}`);
  assert.deepEqual(lib.decodeValue(`v2~paid:reddit~abc~moderntex-reddit-261027-a~${today}`),
    { channel: "paid:reddit", rdt: "abc", tag: "moderntex-reddit-261027-a", date: today });
  // a bad tag is dropped, the rest is kept
  const bad = (await trial(`&ach=paid:reddit&atg=${encodeURIComponent("a b;c")}`)).headers.get("set-cookie");
  assert.match(bad, new RegExp(`^pl_attr=v2~paid:reddit~~~${today};`));
});

test("cookies written before the tag (v1) still read, with no tag", () => {
  assert.deepEqual(lib.decodeValue("v1~paid:reddit~abc~2026-10-20"), { channel: "paid:reddit", rdt: "abc", tag: "", date: "2026-10-20" });
});

test("checkout restores the ad tag from the cookie into the first touch", async () => {
  stubStripe();
  await buy({ product: "moderntex" }, "pl_attr=v2~paid:reddit~clickabc~moderntex-reddit-261027-b~2026-10-20");
  assert.deepEqual(JSON.parse(sessions[0]["metadata[attr_first]"]),
    { d: "2026-10-20", c: "attr-cookie", s: "reddit", m: "cpc", t: "moderntex-reddit-261027-b" });
  assert.equal(sessions[0]["metadata[reddit_click_id]"], "clickabc");
});
