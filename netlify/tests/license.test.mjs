import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";
import { issueLicense, verifyLicense, licensedSlugsFor, crockfordEncode, crockfordDecode, LICENSED_PRODUCTS } from "../lib/license.mjs";

function testPair() {
  const { privateKey } = generateKeyPairSync("ed25519");
  const j = privateKey.export({ format: "jwk" });
  const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");
  return { seedB64: b64(j.d), publicB64: b64(j.x) };
}
const pair = testPair();

test("a key has the product prefix, 5-character groups and verifies for its own product only", () => {
  for (const slug of Object.keys(LICENSED_PRODUCTS)) {
    const key = issueLicense(slug, { sessionId: "cs_test_1", ...pair });
    assert.match(key, new RegExp(`^${LICENSED_PRODUCTS[slug].prefix}-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$`));
    assert.equal(verifyLicense(slug, key, { publicB64: pair.publicB64 }), true);
    for (const other of Object.keys(LICENSED_PRODUCTS).filter((s) => s !== slug)) {
      assert.equal(verifyLicense(other, key, { publicB64: pair.publicB64 }), false, `${slug} key must not unlock ${other}`);
    }
  }
});

test("the same session always yields the same key; different sessions differ", () => {
  const a = issueLicense("legroom", { sessionId: "cs_a", ...pair });
  assert.equal(a, issueLicense("legroom", { sessionId: "cs_a", ...pair }));
  assert.notEqual(a, issueLicense("legroom", { sessionId: "cs_b", ...pair }));
});

test("without a session id keys are random but still valid", () => {
  const a = issueLicense("legroom", { ...pair });
  const b = issueLicense("legroom", { ...pair });
  assert.notEqual(a, b);
  assert.equal(verifyLicense("legroom", a, { publicB64: pair.publicB64 }), true);
});

test("tampering, a wrong public key, spelling variants and junk", () => {
  const key = issueLicense("outbound-veil", { sessionId: "cs_x", ...pair });
  const flipped = key.slice(0, 10) + (key[10] === "A" ? "B" : "A") + key.slice(11);
  assert.equal(verifyLicense("outbound-veil", flipped, { publicB64: pair.publicB64 }), false);
  assert.equal(verifyLicense("outbound-veil", key, { publicB64: testPair().publicB64 }), false);
  assert.equal(verifyLicense("outbound-veil", key.toLowerCase(), { publicB64: pair.publicB64 }), true);
  assert.equal(verifyLicense("outbound-veil", ` ${key.replace(/-/g, "")} `, { publicB64: pair.publicB64 }), true);
  assert.equal(verifyLicense("outbound-veil", "", { publicB64: pair.publicB64 }), false);
  assert.equal(verifyLicense("outbound-veil", "OV1-12345", { publicB64: pair.publicB64 }), false);
  assert.equal(verifyLicense("nope", key), false);
});

test("a missing seed or an unknown product (ModernTex and Keyfeel have their own schemes) returns null and never throws", () => {
  assert.equal(issueLicense("legroom", { sessionId: "cs_x" }), null);
  assert.equal(issueLicense("moderntex", { sessionId: "cs_x", ...pair }), null);
  assert.equal(issueLicense("keyfeel", { sessionId: "cs_x", ...pair }), null);
});

test("crockford round trip", () => {
  const bytes = Buffer.from(Array.from({ length: 68 }, (_, i) => (i * 37 + 11) & 0xff));
  assert.deepEqual(crockfordDecode(crockfordEncode(bytes)).subarray(0, 68), bytes);
});

test("the suite entitles all three licensed apps; a single app only itself", () => {
  assert.deepEqual(licensedSlugsFor("app-suite").sort(), ["legroom", "outbound-veil"]);
  assert.deepEqual(licensedSlugsFor("legroom"), ["legroom"]);
  assert.deepEqual(licensedSlugsFor("moderntex"), []);
});
