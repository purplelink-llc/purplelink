// The "newest release" pick shared by the app download functions: beta-channel versions stay out.
//
// Run with: node --test netlify/tests/release-pick.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { dmgVersion, compareVersions, channelVersions, pickLatestDmg } from "../lib/release-pick.mjs";

const item = (file, channel) =>
  `<item><title>x</title><enclosure url="https://purplelink.llc/.netlify/functions/app-download?update=${file}" sparkle:edSignature="s" length="1"/>${channel ? `<sparkle:channel>${channel}</sparkle:channel>` : ""}</item>`;
const feed = (...items) => `<?xml version="1.0"?><rss><channel>${items.join("\n")}</channel></rss>`;

test("versions are read from the file name, paid or trial, two or three parts", () => {
  assert.deepEqual(dmgVersion("Keyfeel-1.10.0.dmg"), [1, 10, 0]);
  assert.deepEqual(dmgVersion("ModernTex-Trial-3.2.0.dmg"), [3, 2, 0]);
  assert.deepEqual(dmgVersion("Vitae-0.2.dmg"), [0, 2]);
  assert.equal(dmgVersion("appcast.xml"), null);
  assert.equal(compareVersions([1, 0], [1, 0, 0]), 0);
  assert.ok(compareVersions([1, 10, 0], [1, 9, 9]) > 0);
});

test("with no beta in the feed the newest DMG wins, as before", () => {
  const xml = feed(item("App-1.1.0.dmg"), item("App-1.0.0.dmg"));
  assert.equal(pickLatestDmg(["App-1.0.0.dmg", "App-1.10.0.dmg", "App-1.1.0.dmg"], xml), "App-1.10.0.dmg");
});

test("a beta-channel version is skipped, paid and trial alike", () => {
  const xml = feed(item("App-1.2.0.dmg", "beta"), item("App-1.1.0.dmg"));
  assert.equal(pickLatestDmg(["App-1.1.0.dmg", "App-1.2.0.dmg"], xml), "App-1.1.0.dmg");
  assert.equal(pickLatestDmg(["App-Trial-1.1.0.dmg", "App-Trial-1.2.0.dmg"], xml), "App-Trial-1.1.0.dmg");
  assert.deepEqual(channelVersions(xml), { betas: [[1, 2, 0]], items: 2 });
});

test("a regular release newer than the beta is picked again", () => {
  const xml = feed(item("App-1.3.0.dmg"), item("App-1.2.0.dmg", "beta"), item("App-1.1.0.dmg"));
  assert.equal(pickLatestDmg(["App-1.1.0.dmg", "App-1.2.0.dmg", "App-1.3.0.dmg"], xml), "App-1.3.0.dmg");
});

test("when only a beta exists there is no release to hand out", () => {
  assert.equal(pickLatestDmg(["App-0.9.0.dmg"], feed(item("App-0.9.0.dmg", "beta"))), null);
});

test("a missing, empty or garbled feed excludes nothing", () => {
  const names = ["App-1.0.0.dmg", "App-1.2.0.dmg"];
  for (const xml of [null, "", "<rss>not xml", feed()]) assert.equal(pickLatestDmg(names, xml), "App-1.2.0.dmg");
});

test("URL-encoded and path-style enclosures are both understood", () => {
  const xml = feed(
    `<item><enclosure url="https://example.invalid/dl/App-2.0.0.dmg"/><sparkle:channel>beta</sparkle:channel></item>`,
    `<item><enclosure url="https://example.invalid/x?update=App%2D1.9.0.dmg"/></item>`,
  );
  assert.equal(pickLatestDmg(["App-1.9.0.dmg", "App-2.0.0.dmg"], xml), "App-1.9.0.dmg");
});
