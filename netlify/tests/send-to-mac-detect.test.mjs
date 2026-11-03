// "Send to my Mac" detection (site/send-to-mac.js): the block shows only when the visitor is clearly not on macOS.
// The script runs in a bare sandbox, the way it runs in <head> before the body exists.
//
// Run with: node --test netlify/tests/send-to-mac-detect.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const src = readFileSync(new URL("../../site/send-to-mac.js", import.meta.url), "utf8");

function run(navigator) {
  const classes = new Set();
  const listeners = [];
  const window = {};
  const document = {
    documentElement: { classList: { add: (c) => classes.add(c) } },
    addEventListener: (type) => listeners.push(type),
  };
  vm.runInNewContext(src, { window, document, navigator });
  return { on: classes.has("s2m"), notMac: window.plSendToMac.notMac, waits: listeners.includes("DOMContentLoaded") };
}

const UA = {
  mac: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
  win: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
  android: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36",
  iphone: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
  ipadOld: "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
  crOS: "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
  linux: "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
  odd: "SomeTV/1.0",
};

test("a Mac sees nothing: no class, nothing waiting for the page", () => {
  for (const nav of [
    { userAgent: UA.mac, maxTouchPoints: 0 },
    { userAgent: UA.mac, maxTouchPoints: 1 },
    { userAgent: UA.win, userAgentData: { platform: "macOS" } }, // Client Hints win over the UA string
  ]) {
    const r = run(nav);
    assert.equal(r.on, false, JSON.stringify(nav));
    assert.equal(r.waits, false);
  }
});

test("Windows, Android, iPhone, iPad, ChromeOS and Linux get the block", () => {
  for (const nav of [
    { userAgent: UA.win },
    { userAgent: UA.android },
    { userAgent: UA.iphone, maxTouchPoints: 5 },
    { userAgent: UA.ipadOld, maxTouchPoints: 5 },
    { userAgent: UA.mac, maxTouchPoints: 5 }, // iPadOS Safari reports a Mac User-Agent
    { userAgent: UA.crOS },
    { userAgent: UA.linux },
    { userAgent: UA.mac, userAgentData: { platform: "Windows" } },
    { userAgent: "", userAgentData: { platform: "Android" } },
    { userAgent: "", userAgentData: { platform: "Chrome OS" } },
  ]) {
    const r = run(nav);
    assert.equal(r.on, true, JSON.stringify(nav));
    assert.equal(r.waits, true);
  }
});

test("an unclear platform counts as a Mac, so the page stays as it is", () => {
  for (const nav of [
    { userAgent: UA.odd },
    { userAgent: "" },
    { userAgent: UA.odd, userAgentData: { platform: "" } },
    { userAgent: UA.mac, userAgentData: { platform: "Unknown" }, maxTouchPoints: 0 },
    {},
  ]) assert.equal(run(nav).on, false, JSON.stringify(nav));
});

test("a navigator that throws leaves the page alone", () => {
  const nav = {};
  Object.defineProperty(nav, "userAgentData", { get() { throw new Error("blocked"); } });
  assert.equal(run(nav).on, false);
});
