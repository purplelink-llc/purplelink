// Lenses uses the shared PurplelinkLicenseV1 scheme (prefix LN1, slug "lenses"), like Née, Legroom and Outbound Veil.
// Run with: node --test netlify/tests/lenses-license.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";
import { issueLicense, verifyLicense, licensedSlugsFor, suiteIncludes, LICENSED_PRODUCTS, LICENSE_SCHEME } from "../lib/license.mjs";

function testPair() {
  const { privateKey } = generateKeyPairSync("ed25519");
  const j = privateKey.export({ format: "jwk" });
  const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");
  return { seedB64: b64(j.d), publicB64: b64(j.x) };
}
const pair = testPair();

test("Lenses is on the shared scheme with prefix LN1 and its own page", () => {
  assert.equal(LICENSE_SCHEME, "PurplelinkLicenseV1");
  assert.deepEqual(LICENSED_PRODUCTS.lenses, { prefix: "LN1", label: "Lenses", appPath: "/lenses/" });
});

test("a Lenses key has the LN1 shape, verifies for Lenses only, and no other product's key unlocks it", () => {
  const key = issueLicense("lenses", { sessionId: "cs_test_ln", ...pair });
  assert.match(key, /^LN1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/);
  assert.equal(verifyLicense("lenses", key, { publicB64: pair.publicB64 }), true);
  assert.equal(verifyLicense("lenses", `  ${key.toLowerCase()} `, { publicB64: pair.publicB64 }), true);
  for (const other of ["nee", "legroom", "outbound-veil"]) {
    assert.equal(verifyLicense(other, key, { publicB64: pair.publicB64 }), false, `a Lenses key must not unlock ${other}`);
    const theirs = issueLicense(other, { sessionId: "cs_test_ln", ...pair });
    assert.equal(verifyLicense("lenses", theirs, { publicB64: pair.publicB64 }), false, `a ${other} key must not unlock Lenses`);
  }
});

test("the same session always yields the same Lenses key, and it differs per session", () => {
  const a = issueLicense("lenses", { sessionId: "cs_a", ...pair });
  assert.equal(a, issueLicense("lenses", { sessionId: "cs_a", ...pair }));
  assert.notEqual(a, issueLicense("lenses", { sessionId: "cs_b", ...pair }));
});

test("with no signing seed there is no key (never a fake one)", () => {
  assert.equal(issueLicense("lenses", { sessionId: "cs_x" }), null);
});

test("a single Lenses purchase and the Mac Suite are both entitled to a Lenses key", () => {
  assert.deepEqual(licensedSlugsFor("lenses"), ["lenses"]);
  assert.equal(suiteIncludes("lenses"), true);
  assert.ok(licensedSlugsFor("app-suite").includes("lenses"));
});
