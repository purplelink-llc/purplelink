// AKA uses the shared PurplelinkLicenseV1 scheme (prefix AKA1, slug "aka"), like Outbound Veil and Legroom.
// This file pins what is specific to it: the key shape, that it is isolated from the other products, and the launch
// Mac Suite: AKA is in it since launch (Ben, 2026-11-02), and the `inSuite: false` switch still works for a hidden product.
//
// Run with: node --test netlify/tests/aka-license.test.mjs

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

test("AKA is on the shared scheme with prefix AKA1 and its own page", () => {
  assert.equal(LICENSE_SCHEME, "PurplelinkLicenseV1");
  assert.deepEqual(LICENSED_PRODUCTS.aka, { prefix: "AKA1", label: "AKA", appPath: "/aka/" });
});

test("a AKA key has the AKA1 shape, verifies for AKA only, and a key for another product does not unlock it", () => {
  const key = issueLicense("aka", { sessionId: "cs_test_fr", ...pair });
  assert.match(key, /^AKA1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/);
  assert.equal(verifyLicense("aka", key, { publicB64: pair.publicB64 }), true);
  assert.equal(verifyLicense("aka", `  ${key.toLowerCase()} `, { publicB64: pair.publicB64 }), true, "case and surrounding spaces do not matter");
  for (const other of ["legroom", "outbound-veil"]) {
    assert.equal(verifyLicense(other, key, { publicB64: pair.publicB64 }), false, `a AKA key must not unlock ${other}`);
    const theirs = issueLicense(other, { sessionId: "cs_test_fr", ...pair });
    assert.equal(verifyLicense("aka", theirs, { publicB64: pair.publicB64 }), false, `a ${other} key must not unlock AKA`);
  }
});

test("the same session always yields the same AKA key, and it differs from that session's other keys", () => {
  const a = issueLicense("aka", { sessionId: "cs_a", ...pair });
  assert.equal(a, issueLicense("aka", { sessionId: "cs_a", ...pair }));
  assert.notEqual(a, issueLicense("aka", { sessionId: "cs_b", ...pair }));
  assert.notEqual(a.slice(4), issueLicense("legroom", { sessionId: "cs_a", ...pair }).slice(4));
});

test("with no signing seed there is no key (never a fake one)", () => {
  assert.equal(issueLicense("aka", { sessionId: "cs_x" }), null);
});

// ---- the Suite -------------------------------------------------------------------------

test("SUITE: a Mac Suite purchase is entitled to AKA, with the other two keyed apps", () => {
  assert.equal(suiteIncludes("aka"), true);
  assert.deepEqual(licensedSlugsFor("app-suite").sort(), ["aka", "legroom", "outbound-veil"]);
});

test("a single AKA purchase is entitled to its own key", () => {
  assert.deepEqual(licensedSlugsFor("aka"), ["aka"]);
});

test("`inSuite: false` still keeps a hidden product out of the Suite (the switch is kept for the next launch)", () => {
  const entry = LICENSED_PRODUCTS.aka;
  try {
    entry.inSuite = false;
    assert.equal(suiteIncludes("aka"), false);
    assert.deepEqual(licensedSlugsFor("app-suite").sort(), ["legroom", "outbound-veil"]);
  } finally {
    delete entry.inSuite;
  }
  assert.deepEqual(licensedSlugsFor("app-suite").sort(), ["aka", "legroom", "outbound-veil"]);
});

test("Outbound Veil and Legroom behave exactly as before: still in the Suite, keys byte-identical to the pre-AKA code", () => {
  assert.equal(suiteIncludes("outbound-veil"), true);
  assert.equal(suiteIncludes("legroom"), true);
  assert.equal(suiteIncludes("moderntex"), false, "not on this scheme at all");
  const seedB64 = Buffer.alloc(32, 7).toString("base64");
  // Produced by netlify/lib/license.mjs as it was on origin/main before AKA was added.
  assert.equal(
    issueLicense("outbound-veil", { sessionId: "cs_live_pin_0001", seedB64 }),
    "OV1-5AJCR-FVTTJ-0Z03M-8RNK3-J7EN5-0PZ4Y-WR5M4-DMMX3-C7CBM-77D23-GGFC8-6647X-CNCGF-TDASY-S46MN-HYB1D-Z7MZE-7HFX1-5DT4Q-7N64S-6MQT3-AZ0J");
  assert.equal(
    issueLicense("legroom", { sessionId: "cs_live_pin_0001", seedB64 }),
    "LG1-53Q77-8XY03-DS44A-KBX8N-C6826-06ZEB-56NBF-8BQKS-PYNHT-FQYW1-9JKH5-V5K55-14D8T-86F4Q-G5YF1-4XRAP-A7YGM-QHBY9-2DABW-3SSTK-FGB0K-H102");
});
