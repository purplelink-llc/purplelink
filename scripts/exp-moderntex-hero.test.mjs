// Tests for site/exp-moderntex-hero.js (day-level switchback, ModernTex hero screenshot).
// Run: node --test scripts/exp-moderntex-hero.test.mjs
// The script runs in a vm sandbox with a fake document and a fake clock; nothing touches a network.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = fs.readFileSync(path.join(ROOT, "site/exp-moderntex-hero.js"), "utf8");
const HEADER_SRC = fs.readFileSync(path.join(ROOT, "site/exp-trial-link.js"), "utf8");
const PAGE = fs.readFileSync(path.join(ROOT, "site/moderntex/index.html"), "utf8");
const SCHEDULE = SRC.match(/var SCHEDULE = "([AB]+)"/)[1];
const START = SRC.match(/var START = "(\d{4}-\d{2}-\d{2})"/)[1];
const HEADER = HEADER_SRC.match(/var SCHEDULE = "([AB]+)"/)[1];
const DAY = 86400000;

function run(iso, { markup = true, broken = false } = {}) {
  const classes = new Set();
  const tagline = { classList: { added: [], add(c) { this.added.push(c); } } };
  const hero = {
    moved: [],
    classList: { add: (c) => classes.add(c) },
    querySelector: (sel) => {
      if (broken) throw new Error("boom");
      if (!markup) return null;
      if (sel === ".app-hero-copy > .app-hero-tagline") return tagline;
      if (sel === ".app-hero-window") return {};
      throw new Error("unexpected selector " + sel);
    },
    appendChild(el) { this.moved.push(el); },
  };
  const document = {
    documentElement: { dataset: {} },
    querySelector: (sel) => {
      assert.equal(sel, ".app-hero");
      return hero;
    },
  };
  const ms = Date.parse(iso);
  vm.runInNewContext(SRC, { document, Date: { now: () => ms, parse: Date.parse } });
  return { arm: document.documentElement.dataset.expModerntexHero, hero, tagline, classes };
}

test("schedule is 56 days, 28 A and 28 B, one of each in every pair", () => {
  assert.equal(SCHEDULE.length, 56);
  assert.equal([...SCHEDULE].filter((c) => c === "B").length, 28);
  for (let i = 0; i < 56; i += 2) assert.notEqual(SCHEDULE[i], SCHEDULE[i + 1], `pair ${i / 2 + 1}`);
});

test("start is a UTC Monday inside the header test window and the window is 56 days", () => {
  const t = Date.parse(START + "T00:00:00Z");
  assert.equal(new Date(t).getUTCDay(), 1);
  assert.equal(new Date(t + 55 * DAY).toISOString().slice(0, 10), "2026-12-13");
  assert.equal(START, HEADER_SRC.match(/var START = "(\d{4}-\d{2}-\d{2})"/)[1]);
});

test("each weekday has 3 to 5 B days", () => {
  const n = new Array(7).fill(0);
  [...SCHEDULE].forEach((c, i) => { if (c === "B") n[new Date(Date.parse(START + "T00:00:00Z") + i * DAY).getUTCDay()]++; });
  n.forEach((k, d) => assert.ok(k >= 3 && k <= 5, `weekday ${d} has ${k}`));
});

test("the four cells formed with the header test each have 12 to 16 days", () => {
  const cell = {};
  [...SCHEDULE].forEach((c, i) => { const k = HEADER[i] + c; cell[k] = (cell[k] || 0) + 1; });
  for (const k of ["AA", "AB", "BA", "BB"]) assert.ok(cell[k] >= 12 && cell[k] <= 16, `${k}: ${cell[k]}`);
});

test("A day: page untouched, attribute says A", () => {
  assert.equal(SCHEDULE[0], "A");
  const r = run("2026-10-19T12:00:00Z");
  assert.equal(r.arm, "A");
  assert.equal(r.hero.moved.length, 0);
  assert.equal(r.classes.size, 0);
});

test("B day: tagline moves to the end of the hero and the hero gets its class", () => {
  assert.equal(SCHEDULE[1], "B");
  const r = run("2026-10-20T23:59:59Z");
  assert.equal(r.arm, "B");
  assert.deepEqual(r.hero.moved, [r.tagline]);
  assert.deepEqual(r.tagline.classList.added, ["app-hero-tagline-lower"]);
  assert.deepEqual([...r.classes], ["exp-hero-shot"]);
});

test("the day rolls over at UTC midnight", () => {
  assert.equal(run("2026-10-20T23:59:59Z").arm, "B");
  assert.equal(run("2026-10-21T00:00:00Z").arm, "A");
});

test("outside the window the page is untouched, on both sides", () => {
  for (const iso of ["2026-10-18T23:59:59Z", "2026-12-14T00:00:00Z", "2027-03-01T00:00:00Z"]) {
    const r = run(iso);
    assert.equal(r.arm, "off", iso);
    assert.equal(r.hero.moved.length, 0);
  }
});

test("missing markup or a thrown error leaves the page as it is and says so", () => {
  const a = run("2026-10-20T12:00:00Z", { markup: false });
  assert.equal(a.arm, "error");
  assert.equal(a.hero.moved.length, 0);
  assert.equal(a.classes.size, 0);
  assert.equal(run("2026-10-20T12:00:00Z", { broken: true }).arm, "error");
});

test("the page loads the script once, after the hero, and the buy button is a filled button", () => {
  assert.equal(PAGE.split('src="/exp-moderntex-hero.js').length - 1, 1);
  assert.ok(PAGE.indexOf("exp-moderntex-hero.js") > PAGE.indexOf("app-hero-window"));
  assert.match(PAGE, /class="btn btn-primary pr-checkout-btn" id="checkout-btn"/);
  assert.doesNotMatch(PAGE, /<script[^>]*exp-moderntex-hero[^>]*>\s*[^<\s]/);
});
