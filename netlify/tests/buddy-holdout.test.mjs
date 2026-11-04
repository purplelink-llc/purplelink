// Tests for the Buddy chat holdout in site/buddy-chat/loader.js (docs/designs/buddy-chat.md, "Conversion pass",
// section 3): a paired-day switchback that leaves the launcher off on A days.
// The loader runs in a vm sandbox with a fake document and a fake clock; nothing touches a network.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SRC = fs.readFileSync(path.join(ROOT, "site/buddy-chat/loader.js"), "utf8");
const SCHEDULE = SRC.match(/var SCHEDULE = "([AB]+)"/)[1];
const START = SRC.match(/var START = "(\d{4}-\d{2}-\d{2})"/)[1];
const DAY = 86400000;

function run(when, { schedule } = {}) {
  const head = [];
  const body = [];
  const el = (tag) => ({ tag, classList: { add() {}, contains: () => false }, setAttribute() {}, addEventListener() {} });
  const document = {
    readyState: "complete",
    documentElement: { dataset: {} },
    head: { appendChild: (n) => head.push(n) },
    body: { appendChild: (n) => body.push(n), classList: { contains: () => false } },
    createElement: el,
    addEventListener() {},
  };
  const now = typeof when === "function" ? when : () => Date.parse(when);
  const src = schedule === undefined ? SRC : SRC.replace(/var SCHEDULE = "[AB]+"/, `var SCHEDULE = "${schedule}"`);
  const sandbox = { window: {}, document, Date: { now, parse: Date.parse } };
  vm.runInNewContext(src, sandbox);
  // The stylesheet is added first; the button follows once it loads.
  const css = head.find((n) => n.tag === "link");
  if (css && css.onload) css.onload();
  return { arm: document.documentElement.dataset.expBuddyChat, css: !!css, launcher: body.length === 1 };
}

const dayOf = (i) => new Date(Date.parse(START + "T12:00:00Z") + i * DAY).toISOString();

test("schedule: 56 days from Monday 2026-12-28, one A and one B in every pair", () => {
  assert.equal(START, "2026-12-28");
  assert.equal(new Date(START + "T00:00:00Z").getUTCDay(), 1);
  assert.equal(SCHEDULE.length, 56);
  for (let i = 0; i < 56; i += 2) assert.notEqual(SCHEDULE[i], SCHEDULE[i + 1], `pair ${i / 2 + 1}`);
  assert.equal(new Date(Date.parse(START + "T00:00:00Z") + 55 * DAY).toISOString().slice(0, 10), "2027-02-21");
});

test("schedule: every UTC weekday has 3 to 5 B days out of 8", () => {
  const counts = Array(7).fill(0);
  [...SCHEDULE].forEach((a, i) => { if (a === "B") counts[new Date(Date.parse(START + "T00:00:00Z") + i * DAY).getUTCDay()]++; });
  for (const c of counts) assert.ok(c >= 3 && c <= 5, String(counts));
});

test("every day of the window: A draws nothing, B draws the launcher", () => {
  for (let i = 0; i < SCHEDULE.length; i++) {
    const r = run(dayOf(i));
    assert.equal(r.arm, SCHEDULE[i], dayOf(i));
    assert.equal(r.css, SCHEDULE[i] === "B", `stylesheet on ${dayOf(i)}`);
    assert.equal(r.launcher, SCHEDULE[i] === "B", `launcher on ${dayOf(i)}`);
  }
});

test("before and after the window the chat shows as before", () => {
  for (const when of ["2026-11-04T12:00:00Z", "2026-12-27T23:59:59.999Z", "2027-02-22T00:00:00Z", "2027-06-01T08:00:00Z"]) {
    const r = run(when);
    assert.equal(r.arm, "off", when);
    assert.ok(r.css && r.launcher, when);
  }
});

test("day boundaries are UTC", () => {
  assert.equal(run("2026-12-28T00:00:00.000Z").arm, SCHEDULE[0]);
  assert.equal(run("2026-12-28T23:59:59.999Z").arm, SCHEDULE[0]);
  assert.equal(run("2026-12-29T00:00:00.000Z").arm, SCHEDULE[1]);
  // 2026-12-28 19:00 in New York is already 2026-12-29 in UTC.
  assert.equal(run("2026-12-28T19:00:00-05:00").arm, SCHEDULE[1]);
});

test("a failing clock or a malformed schedule falls back to showing the chat", () => {
  const broken = run(() => { throw new Error("clock"); });
  assert.equal(broken.arm, "off");
  assert.ok(broken.launcher);
  const malformed = run(dayOf(1), { schedule: "AB?" });
  assert.equal(malformed.arm, "off");
  assert.ok(malformed.launcher);
});

test("stopping early: an all-B schedule shows the chat every day", () => {
  const allB = "B".repeat(56);
  for (let i = 0; i < 56; i++) assert.ok(run(dayOf(i), { schedule: allB }).launcher);
});
