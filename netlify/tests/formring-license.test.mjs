// Formring uses the shared PurplelinkLicenseV1 scheme (prefix FR1, slug "formring"), like Outbound Veil and Legroom.
// This file pins what is specific to it: the key shape, that it is isolated from the other products, and the launch
// gate that keeps it out of every Mac Suite purchase while the app is hidden.
//
// Run with: node --test netlify/tests/formring-license.test.mjs

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

test("Formring is on the shared scheme with prefix FR1 and its own page", () => {
  assert.equal(LICENSE_SCHEME, "PurplelinkLicenseV1");
  assert.deepEqual(LICENSED_PRODUCTS.formring, { prefix: "FR1", label: "Formring", appPath: "/formring/", inSuite: false });
});

test("a Formring key has the FR1 shape, verifies for Formring only, and a key for another product does not unlock it", () => {
  const key = issueLicense("formring", { sessionId: "cs_test_fr", ...pair });
  assert.match(key, /^FR1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/);
  assert.equal(verifyLicense("formring", key, { publicB64: pair.publicB64 }), true);
  assert.equal(verifyLicense("formring", `  ${key.toLowerCase()} `, { publicB64: pair.publicB64 }), true, "case and surrounding spaces do not matter");
  for (const other of ["legroom", "outbound-veil"]) {
    assert.equal(verifyLicense(other, key, { publicB64: pair.publicB64 }), false, `a Formring key must not unlock ${other}`);
    const theirs = issueLicense(other, { sessionId: "cs_test_fr", ...pair });
    assert.equal(verifyLicense("formring", theirs, { publicB64: pair.publicB64 }), false, `a ${other} key must not unlock Formring`);
  }
});

test("the same session always yields the same Formring key, and it differs from that session's other keys", () => {
  const a = issueLicense("formring", { sessionId: "cs_a", ...pair });
  assert.equal(a, issueLicense("formring", { sessionId: "cs_a", ...pair }));
  assert.notEqual(a, issueLicense("formring", { sessionId: "cs_b", ...pair }));
  assert.notEqual(a.slice(4), issueLicense("legroom", { sessionId: "cs_a", ...pair }).slice(4));
});

test("with no signing seed there is no key (never a fake one)", () => {
  assert.equal(issueLicense("formring", { sessionId: "cs_x" }), null);
});

// ---- the launch gate -------------------------------------------------------------------

test("LAUNCH GATE: a Mac Suite purchase is not entitled to Formring while it is hidden", () => {
  assert.equal(suiteIncludes("formring"), false);
  assert.deepEqual(licensedSlugsFor("app-suite").sort(), ["legroom", "outbound-veil"]);
  assert.ok(!licensedSlugsFor("app-suite").includes("formring"));
});

test("a single Formring purchase is entitled to its own key even while the Suite gate is closed", () => {
  assert.deepEqual(licensedSlugsFor("formring"), ["formring"]);
});

test("flipping the gate (inSuite true, or the field removed) adds Formring to the Suite and nothing else changes", () => {
  const entry = LICENSED_PRODUCTS.formring;
  try {
    entry.inSuite = true;
    assert.deepEqual(licensedSlugsFor("app-suite").sort(), ["formring", "legroom", "outbound-veil"]);
    delete entry.inSuite;
    assert.deepEqual(licensedSlugsFor("app-suite").sort(), ["formring", "legroom", "outbound-veil"]);
  } finally {
    entry.inSuite = false;
  }
  assert.deepEqual(licensedSlugsFor("app-suite").sort(), ["legroom", "outbound-veil"]);
});

test("Outbound Veil and Legroom behave exactly as before: still in the Suite, keys byte-identical to the pre-Formring code", () => {
  assert.equal(suiteIncludes("outbound-veil"), true);
  assert.equal(suiteIncludes("legroom"), true);
  assert.equal(suiteIncludes("moderntex"), false, "not on this scheme at all");
  const seedB64 = Buffer.alloc(32, 7).toString("base64");
  // Produced by netlify/lib/license.mjs as it was on origin/main before Formring was added.
  assert.equal(
    issueLicense("outbound-veil", { sessionId: "cs_live_pin_0001", seedB64 }),
    "OV1-5AJCR-FVTTJ-0Z03M-8RNK3-J7EN5-0PZ4Y-WR5M4-DMMX3-C7CBM-77D23-GGFC8-6647X-CNCGF-TDASY-S46MN-HYB1D-Z7MZE-7HFX1-5DT4Q-7N64S-6MQT3-AZ0J");
  assert.equal(
    issueLicense("legroom", { sessionId: "cs_live_pin_0001", seedB64 }),
    "LG1-53Q77-8XY03-DS44A-KBX8N-C6826-06ZEB-56NBF-8BQKS-PYNHT-FQYW1-9JKH5-V5K55-14D8T-86F4Q-G5YF1-4XRAP-A7YGM-QHBY9-2DABW-3SSTK-FGB0K-H102");
});
