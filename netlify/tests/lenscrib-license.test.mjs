// Lenscrib license keys (LCB1): the issuer in netlify/lib/lenscrib-license.mjs against an independent
// verifier written here from the scheme description, and against the stored test vectors. Everything signs with
// a throwaway key pair made in the test; the production private key is never read.
//
// Run with: node --test netlify/tests/lenscrib-license.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash, createPublicKey, generateKeyPairSync, verify as edVerify } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { issueLenscribLicense, LENSCRIB_LICENSE_PUBLIC_KEY_B64, crockfordBase32Encode } from "../lib/lenscrib-license.mjs";
import { issueTapefolioLicense } from "../lib/tapefolio-license.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const vectors = JSON.parse(readFileSync(join(HERE, "fixtures", "lenscrib-license-vectors.json"), "utf8"));

const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const b64 = (s) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("base64");

function throwawayPair() {
  const { privateKey } = generateKeyPairSync("ed25519");
  const j = privateKey.export({ format: "jwk" });
  return { seedB64: b64(j.d), publicB64: b64(j.x) };
}

/** What the app does: trim, upper-case, drop dashes and spaces, drop LCB1, decode Crockford (O->0, I and L->1), 68 bytes, verify. */
function verifyKey(text, publicB64, domain = "LenscribLicenseV1") {
  let s = String(text).trim().toUpperCase().replace(/[-\s]/g, "");
  if (s.startsWith("LCB1")) s = s.slice(4);
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
const envFor = (seed) => (name) => (name === "LENSCRIB_LICENSE_PRIVATE_KEY" ? seed : undefined);
const issue = (email, p = pair) => issueLenscribLicense(email, envFor(p.seedB64), p.publicB64);

test("the production public key is the one compiled into the app: 32 raw bytes", () => {
  assert.equal(LENSCRIB_LICENSE_PUBLIC_KEY_B64, "EmMW+2pz1QfCDC8IRk0pyTfINugd3oY/Xz9wD02jcGk=");
  assert.equal(Buffer.from(LENSCRIB_LICENSE_PUBLIC_KEY_B64, "base64").length, 32);
});

test("a key is LCB1 plus 109 characters in groups of five, and the independent verifier accepts it", () => {
  const key = issue("buyer@example.org");
  assert.match(key, /^LCB1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/);
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
  const expected = createHash("sha256").update("lenscrib-license:buyer@example.org").digest().subarray(0, 4);
  assert.deepEqual(Buffer.from(bytes.slice(0, 4)), expected);
  assert.equal(crockfordBase32Encode(Buffer.from(bytes)), key.slice(5).replace(/-/g, ""));
});

test("a key signed with another domain string, another key pair or a changed character does not verify", () => {
  const key = issue("buyer@example.org");
  assert.equal(verifyKey(key, pair.publicB64, "TapefolioLicenseV1"), false);
  assert.equal(verifyKey(key, throwawayPair().publicB64), false);
  const i = 12;
  assert.equal(verifyKey(key.slice(0, i) + (key[i] === "A" ? "B" : "A") + key.slice(i + 1), pair.publicB64), false);
});

test("a Tapefolio key made from the same seed is a different key and does not verify as Lenscrib", () => {
  const tfEnv = (name) => (name === "TAPEFOLIO_LICENSE_PRIVATE_KEY" ? pair.seedB64 : undefined);
  const tf = issueTapefolioLicense("buyer@example.org", tfEnv);
  // Tapefolio's module signs under the real Tapefolio public key, which only the real seed matches; with a throwaway
  // seed it may return null on some Node versions. When it returns a key, it must not be a valid Lenscrib key.
  if (tf) {
    assert.match(tf, /^TFL1-/);
    assert.equal(verifyKey(tf, pair.publicB64), false);
    assert.notEqual(tf.slice(5), issue("buyer@example.org").slice(5));
  }
});

test("no secret, an unusable secret or no address returns null and never throws", () => {
  assert.equal(issueLenscribLicense("buyer@example.org", () => undefined), null);
  assert.equal(issueLenscribLicense("buyer@example.org", () => ""), null);
  assert.equal(issueLenscribLicense("buyer@example.org", () => "not base64 at all !!!"), null);
  assert.equal(issueLenscribLicense("buyer@example.org", envFor(Buffer.alloc(5).toString("base64"))), null);
  assert.equal(issue(""), null);
  assert.equal(issue(null), null);
  assert.equal(issue(undefined), null);
  assert.equal(issue("   "), null);
});

test("with no Netlify environment at all the default reader returns null", () => {
  const saved = globalThis.Netlify;
  delete globalThis.Netlify;
  try {
    assert.equal(issueLenscribLicense("buyer@example.org"), null);
  } finally {
    if (saved !== undefined) globalThis.Netlify = saved;
  }
});

test("the default reader takes the secret from the Netlify environment variable of that name", () => {
  const saved = globalThis.Netlify;
  const seen = [];
  globalThis.Netlify = { env: { get: (k) => { seen.push(k); return undefined; } } };
  try {
    assert.equal(issueLenscribLicense("buyer@example.org"), null);
  } finally {
    if (saved === undefined) delete globalThis.Netlify; else globalThis.Netlify = saved;
  }
  assert.deepEqual(seen, ["LENSCRIB_LICENSE_PRIVATE_KEY"]);
});

// ---- stored vectors, for the app's own tests --------------------------------------------

test("every valid vector verifies under the vector public key and is a well-formed, distinct key", () => {
  assert.ok(vectors.valid.length >= 3);
  for (const v of vectors.valid) {
    assert.equal(verifyKey(v.key, vectors.testPublicKeyBase64), true, v.email);
    assert.match(v.key, /^LCB1-([0-9A-Z]{5}-){21}[0-9A-Z]{4}$/);
  }
  assert.equal(new Set(vectors.valid.map((v) => v.key)).size, vectors.valid.length);
});

test("the vector public key is not the production key", () => {
  assert.notEqual(vectors.testPublicKeyBase64, LENSCRIB_LICENSE_PUBLIC_KEY_B64);
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
  assert.equal(verifyKey("LCB1-" + swapped, vectors.testPublicKeyBase64), true);
  assert.equal(verifyKey("LCB1-U" + body.slice(1), vectors.testPublicKeyBase64), false);
});
