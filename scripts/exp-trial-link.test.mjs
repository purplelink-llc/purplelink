// Tests for site/exp-trial-link.js (day-level switchback, trial link in the header).
// Run: node --test scripts/exp-trial-link.test.mjs
// The script runs in a vm sandbox with a fake document and a fake clock; nothing touches a network.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = fs.readFileSync(path.join(ROOT, "site/exp-trial-link.js"), "utf8");
const SITE_JS = fs.readFileSync(path.join(ROOT, "site/site.js"), "utf8");
const SCHEDULE = SRC.match(/var SCHEDULE = "([AB]+)"/)[1];
const START = SRC.match(/var START = "(\d{4}-\d{2}-\d{2})"/)[1];

function run(iso, { nav = true, broken = false } = {}) {
  const added = [];
  const navEl = {
    children: added,
    querySelector: (sel) => added.find((a) => sel.includes("data-exp-trial-link") && a.attrs["data-exp-trial-link"] !== undefined) || null,
    appendChild: (a) => added.push(a),
  };
  const document = {
    documentElement: { dataset: {} },
    querySelector: (sel) => {
      if (broken) throw new Error("boom");
      assert.match(sel, /nav\[aria-label="Primary navigation"\]/);
      return nav ? navEl : null;
    },
    createElement: (tag) => {
      const el = { tag, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } };
      return el;
    },
  };
  const ms = Date.parse(iso);
  const sandbox = { document, Date: { now: () => ms, parse: Date.parse } };
  vm.runInNewContext(SRC, sandbox);
  return { document, added };
}

test("schedule is 70 days, 35 A and 35 B, one of each in every pair", () => {
  assert.equal(SCHEDULE.length, 70);
  assert.equal([...SCHEDULE].filter((c) => c === "A").length, 35);
  assert.equal([...SCHEDULE].filter((c) => c === "B").length, 35);
  for (let i = 0; i < 70; i += 2) assert.notEqual(SCHEDULE[i], SCHEDULE[i + 1], `pair ${i / 2 + 1}`);
});

test("start is a UTC Monday and the window is 70 days", () => {
  assert.equal(new Date(START + "T00:00:00Z").getUTCDay(), 1);
  const last = new Date(Date.parse(START + "T00:00:00Z") + 69 * 86400000).toISOString().slice(0, 10);
  assert.equal(last, "2026-12-27");
});

test("A day: nothing is added, attribute says A", () => {
  assert.equal(SCHEDULE[0], "A");
  const { document, added } = run("2026-10-19T12:00:00Z");
  assert.equal(added.length, 0);
  assert.equal(document.documentElement.dataset.expTrialLink, "A");
});

test("B day: one link, pointing at the trial section of the ModernTex page", () => {
  assert.equal(SCHEDULE[1], "B");
  const { document, added } = run("2026-10-20T12:00:00Z");
  assert.equal(document.documentElement.dataset.expTrialLink, "B");
  assert.equal(added.length, 1);
  const a = added[0];
  assert.equal(a.tag, "a");
  assert.equal(a.href, "/moderntex/#buy");
  assert.equal(a.textContent, "Free trial");
  assert.match(a.attrs["aria-label"], /^Free trial/);
  assert.ok(!a.href.includes("download"), "must not link to the binary");
  assert.equal(a.attrs.style, undefined, "no inline style");
});

test("day boundaries are UTC", () => {
  assert.equal(run("2026-10-19T23:59:59.999Z").document.documentElement.dataset.expTrialLink, "A");
  assert.equal(run("2026-10-20T00:00:00.000Z").document.documentElement.dataset.expTrialLink, "B");
  // 2026-10-19 20:00 in New York is already 2026-10-20 00:00 UTC; the clock is read in UTC.
  assert.equal(run("2026-10-19T20:00:00-04:00").document.documentElement.dataset.expTrialLink, "B");
});

test("every day matches its schedule character", () => {
  for (let i = 0; i < 70; i++) {
    const iso = new Date(Date.parse(START + "T00:00:00Z") + i * 86400000 + 3600000).toISOString();
    const { added } = run(iso);
    assert.equal(added.length, SCHEDULE[i] === "B" ? 1 : 0, `day ${i + 1} ${iso}`);
  }
});

test("before the start and after the end the header is untouched", () => {
  for (const iso of ["2026-10-18T23:59:59Z", "2026-01-01T00:00:00Z", "2026-12-28T00:00:00Z", "2027-03-01T00:00:00Z", "2030-06-01T00:00:00Z"]) {
    const { document, added } = run(iso);
    assert.equal(added.length, 0, iso);
    assert.equal(document.documentElement.dataset.expTrialLink, "off", iso);
  }
});

test("no navigation element, or a throwing document: no error, no link", () => {
  assert.doesNotThrow(() => run("2026-10-20T12:00:00Z", { nav: false }));
  assert.doesNotThrow(() => run("2026-10-20T12:00:00Z", { broken: true }));
});

test("the script is external-safe: no inline styles, no network, no storage, no tracking", () => {
  for (const banned of [/\.style\b/, /setAttribute\("style"/, /fetch\(/, /XMLHttpRequest/, /sendBeacon/, /localStorage/, /sessionStorage/, /cookie/, /plTrack/, /innerHTML/, /eval\(/]) {
    assert.ok(!banned.test(SRC), String(banned));
  }
});

test("site.js loads the script from the same origin and stops after 2027-01-01", () => {
  assert.match(SITE_JS, /s\.src = '\/exp-trial-link\.js'/);
  assert.match(SITE_JS, /Date\.UTC\(2027, 0, 1\)/);
});
