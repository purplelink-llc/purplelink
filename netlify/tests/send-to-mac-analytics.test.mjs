// "Send to my Mac" in site/analytics.js: the first-touch details handed to the form, the funnel event, the trial
// clicks it turns into pointers ("moderntex-not-mac", not tagged), and the trial on the Mac after the email
// ("moderntex-s2m", tagged with the same ad). The click id here is made up and never reaches Reddit.
//
// Run with: node --test netlify/tests/send-to-mac-analytics.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const src = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");
const CLICK_ID = "TEST_CLICK_ID.not-real";

function page({ search = "", dnt = "", store = {} } = {}) {
  const listeners = [];
  const beacons = [];
  const sb = {
    navigator: { sendBeacon: (_u, blob) => { beacons.push(JSON.parse(blob.parts[0])); return true; }, doNotTrack: dnt },
    Blob: class { constructor(parts) { this.parts = parts; } },
    URL, URLSearchParams, Date, JSON, Math, String, RegExp, Object,
    document: { referrer: "", addEventListener: (t, f) => listeners.push([t, f]) },
    location: { search, pathname: "/moderntex/", host: "purplelink.llc", hostname: "purplelink.llc", href: `https://purplelink.llc/moderntex/${search}`, origin: "https://purplelink.llc" },
    localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; }, removeItem: (k) => { delete store[k]; } },
  };
  sb.window = sb;
  vm.runInNewContext(src, sb);
  const click = (extra = {}) => {
    const attrs = { href: "/.netlify/functions/moderntex-download?trial=1", ...extra };
    const a = { href: `https://purplelink.llc${attrs.href}`, getAttribute: (k) => attrs[k], setAttribute: (k, v) => { attrs[k] = v; }, closest: () => a };
    for (const [t, f] of listeners) if (t === "click") f({ target: a });
    return attrs.href;
  };
  return { sb, beacons, click, store };
}

const AD = `?utm_source=reddit&utm_medium=paid&utm_content=mtx-ad-test&rdt_cid=${CLICK_ID}`;

test("plAttribution hands the form the channel, link tag and click id; under Do Not Track it does not exist", () => {
  const p = page({ search: AD });
  assert.deepEqual({ ...p.sb.window.plAttribution() }, { ft: "paid:reddit", fc: "mtx-ad-test", rdt: CLICK_ID });
  assert.equal(page({ search: AD, dnt: "1" }).sb.window.plAttribution, undefined);
});

test("send_to_mac is a funnel event: it carries the channel and the link tag", () => {
  const p = page({ search: AD });
  p.sb.window.plTrack("send_to_mac", "moderntex");
  const ev = p.beacons.at(-1);
  assert.equal(ev.t, "send_to_mac");
  assert.equal(ev.m, "moderntex");
  assert.equal(ev.ft, "paid:reddit");
  assert.equal(ev.fc, "mtx-ad-test");
});

test("a trial click turned into a pointer counts as moderntex-not-mac and the link is not tagged", () => {
  const p = page({ search: AD });
  const href = p.click({ "data-s2m-intercept": "1" });
  assert.equal(p.beacons.at(-1).t, "trial_download");
  assert.equal(p.beacons.at(-1).m, "moderntex-not-mac");
  assert.equal(href, "/.netlify/functions/moderntex-download?trial=1");
  const real = p.click();
  assert.equal(p.beacons.at(-1).m, "moderntex");
  assert.match(real, /ach=paid%3Areddit/);
});

test("on the Mac, a trial after the email counts as moderntex-s2m and keeps the ad for the purchase", () => {
  // The link in the email: see attributionQuery in netlify/functions/send-to-mac.mjs.
  const mac = page({ search: `?utm_source=reddit&utm_medium=paid&utm_campaign=send-to-mac&utm_content=mtx-ad-test&rdt_cid=${CLICK_ID}` });
  assert.equal(mac.beacons[0].ft, "paid:reddit");
  const href = mac.click();
  assert.equal(mac.beacons.at(-1).m, "moderntex-s2m");
  const u = new URL(href, "https://purplelink.llc");
  assert.equal(u.searchParams.get("ach"), "paid:reddit");
  assert.equal(u.searchParams.get("arc"), CLICK_ID);
  assert.equal(u.searchParams.get("atg"), "mtx-ad-test");
});
