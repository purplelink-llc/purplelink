// Tapefolio license keys (TFL1): the issuer in netlify/lib/tapefolio-license.mjs against an independent
// verifier written here from the scheme description, and against the stored test vectors. Everything signs with
// a throwaway key pair made in the test; the production private key is never read.
//
// Run with: node --test netlify/tests/tapefolio-license.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash, createPublicKey, generateKeyPairSync, verify as edVerify } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { issueTapefolioLicense, TAPEFOLIO_LICENSE_PUBLIC_KEY_B64, crockfordBase32Encode } from "../lib/tapefolio-license.mjs";
import { issueKeyfeelLicense } from "../lib/keyfeel-license.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const vectors = JSON.parse(readFileSync(join(HERE, "fixtures", "tapefolio-license-vectors.json"), "utf8"));

const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");

function throwawayPair() {
  const { privateKey } = generateKeyPairSync("ed25519");
  const j = privateKey.export({ format: "jwk" });
  return { seedB64: b64(j.d), publicB64: b64(j.x) };
}

/** What the app does: trim, upper-case, drop dashes and spaces, drop TFL1, decode Crockford (O->0, I and L->1), 68 bytes, verify. */
function verifyKey(text, publicB64, domain = "TapefolioLicenseV1") {
  let s = String(text).trim().toUpperCase().replace(/[-\s]/g, "");
  if (s.startsWith("TFL1")) s = s.slice(4);
  let bits = 0n, count = 0;
  const bytes = [];
  for (const ch of s.replace(/O/g, "0").replace(/[IL]/g, "1")) {
    const v = ALPHABET.indexOf(ch);
    if (v < 0) return false;
    bits = (bits << 5n) | BigInt(v);
    count += 5;
    if (count >= 8) { count -= 8; bytes.push(Number((bits >> BigInt(count)) & 0xffn)); }
  }
  if (bytes.length !== 68) return false;
  const buf = Buffer.from(bytes);
  const publicKey = createPublicKey({ key: { kty: "OKP", crv: "Ed25519", x: Buffer.from(publicB64, "base64").toString("base64url") }, format: "jwk" });
  return edVerify(null, Buffer.concat([Buffer.from(domain), buf.subarray(0, 4)]), publicKey, buf.subarray(4));
}

const pair = throwawayPair();
const envFor = (seed) => (name) => (name === "TAPEFOLIO_LICENSE_PRIVATE_KEY" ? seed : undefined);
const issue = (email, p = pair) => issueTapefolioLicense(email, envFor(p.seedB64), p.publicB64);

test("the production public key is the one compiled into the app: 32 raw bytes", () => {
  assert.equal(TAPEFOLIO_LICENSE_PUBLIC_KEY_B64, "5qmJMOr4uux0LZrWGs/V6nc6VKXsogioMgiJ3pBlSvI=");
  assert.equal(Buffer.from(TAPEFOLIO_LICENSE_PUBLIC_KEY_B64, "base64").length, 32);
});

test("a key is TFL1 plus 109 characters in groups of five, and the independent verifier accepts it", () => {
  const key = issue("buyer@example.org");
  assert.match(key, /^TFL1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/);
  assert.equal(verifyKey(key, pair.publicB64), true);
});

test("the same address always gets the same key, whatever its case or padding; other addresses differ", () => {
  const a = issue("Buyer@Example.org");
  assert.equal(a, issue(" buyer@example.org "));
  assert.notEqual(a, issue("someone.else@example.org"));
});

test("the nonce is the first four bytes of sha256 of the seed string and the address", () => {
  const key = issue("buyer@example.org");
  let bits = 0n, count = 0;
  const bytes = [];
  for (const ch of key.slice(5).replace(/-/g, "")) {
    bits = (bits << 5n) | BigInt(ALPHABET.indexOf(ch));
    count += 5;
    if (count >= 8) { count -= 8; bytes.push(Number((bits >> BigInt(count)) & 0xffn)); }
  }
  assert.equal(bytes.length, 68);
  const expected = createHash("sha256").update("tapefolio-license:buyer@example.org").digest().subarray(0, 4);
  assert.deepEqual(Buffer.from(bytes.slice(0, 4)), expected);
  assert.equal(crockfordBase32Encode(Buffer.from(bytes)), key.slice(5).replace(/-/g, ""));
});

test("a key signed with another domain string, another key pair or a changed character does not verify", () => {
  const key = issue("buyer@example.org");
  assert.equal(verifyKey(key, pair.publicB64, "KeyfeelLicenseV1"), false);
  assert.equal(verifyKey(key, throwawayPair().publicB64), false);
  const i = 12;
  assert.equal(verifyKey(key.slice(0, i) + (key[i] === "A" ? "B" : "A") + key.slice(i + 1), pair.publicB64), false);
});

test("a Keyfeel key made from the same seed is a different key and does not verify as Tapefolio", () => {
  const kfEnv = (name) => (name === "KEYFEEL_LICENSE_PRIVATE_KEY" ? pair.seedB64 : undefined);
  const kf = issueKeyfeelLicense("buyer@example.org", kfEnv);
  // Keyfeel's module signs under the real Keyfeel public key, which only the real seed matches; with a throwaway
  // seed it may return null on some Node versions. When it returns a key, it must not be a valid Tapefolio key.
  if (kf) {
    assert.match(kf, /^KFL1-/);
    assert.equal(verifyKey(kf, pair.publicB64), false);
    assert.notEqual(kf.slice(5), issue("buyer@example.org").slice(5));
  }
});

test("no secret, an unusable secret or no address returns null and never throws", () => {
  assert.equal(issueTapefolioLicense("buyer@example.org", () => undefined), null);
  assert.equal(issueTapefolioLicense("buyer@example.org", () => ""), null);
  assert.equal(issueTapefolioLicense("buyer@example.org", () => "not base64 at all !!!"), null);
  assert.equal(issueTapefolioLicense("buyer@example.org", envFor(Buffer.alloc(5).toString("base64"))), null);
  assert.equal(issue(""), null);
  assert.equal(issue(null), null);
  assert.equal(issue(undefined), null);
  assert.equal(issue("   "), null);
});

test("with no Netlify environment at all the default reader returns null", () => {
  const saved = globalThis.Netlify;
  delete globalThis.Netlify;
  try {
    assert.equal(issueTapefolioLicense("buyer@example.org"), null);
  } finally {
    if (saved !== undefined) globalThis.Netlify = saved;
  }
});

test("the default reader takes the secret from the Netlify environment variable of that name", () => {
  const saved = globalThis.Netlify;
  const seen = [];
  globalThis.Netlify = { env: { get: (k) => { seen.push(k); return undefined; } } };
  try {
    assert.equal(issueTapefolioLicense("buyer@example.org"), null);
  } finally {
    if (saved === undefined) delete globalThis.Netlify; else globalThis.Netlify = saved;
  }
  assert.deepEqual(seen, ["TAPEFOLIO_LICENSE_PRIVATE_KEY"]);
});

// ---- stored vectors, for the app's own tests --------------------------------------------

test("every valid vector verifies under the vector public key and is a well-formed, distinct key", () => {
  assert.ok(vectors.valid.length >= 3);
  for (const v of vectors.valid) {
    assert.equal(verifyKey(v.key, vectors.testPublicKeyBase64), true, v.email);
    assert.match(v.key, /^TFL1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/);
  }
  assert.equal(new Set(vectors.valid.map((v) => v.key)).size, vectors.valid.length);
});

test("the vector public key is not the production key", () => {
  assert.notEqual(vectors.testPublicKeyBase64, TAPEFOLIO_LICENSE_PUBLIC_KEY_B64);
});

test("every invalid vector is rejected", () => {
  assert.ok(vectors.invalid.length >= 5);
  for (const v of vectors.invalid) assert.equal(verifyKey(v.key, vectors.testPublicKeyBase64), false, v.why);
});

test("spelling variants of a valid key (case, dashes, spaces, padding) verify", () => {
  for (const s of vectors.spelling) assert.equal(verifyKey(s, vectors.testPublicKeyBase64), true, s);
});

test("Crockford look-alikes read as the digits they resemble, and U is rejected", () => {
  const key = vectors.valid[0].key;
  const body = key.slice(5).replace(/-/g, "");
  const swapped = body.replace(/0/g, "O").replace(/1/g, "I");
  assert.equal(verifyKey("TFL1-" + swapped, vectors.testPublicKeyBase64), true);
  assert.equal(verifyKey("TFL1-U" + body.slice(1), vectors.testPublicKeyBase64), false);
});
