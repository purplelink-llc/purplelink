import test from "node:test";
import assert from "node:assert/strict";
import { createPublicKey, generateKeyPairSync, sign, verify } from "node:crypto";
import { ed25519PrivateKeyFromSeed } from "../lib/ed25519-seed.mjs";

test("a key built from the seed signs exactly like the key it came from, in base64 and base64url", () => {
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  const d = privateKey.export({ format: "jwk" }).d;
  const seed = Buffer.from(d, "base64url").toString("base64");
  const msg = Buffer.from("PurplelinkLicenseV1|legroom|" + "abcd");
  for (const form of [seed, d, ` ${seed}\n`]) {
    const key = ed25519PrivateKeyFromSeed(form);
    assert.deepEqual(sign(null, msg, key), sign(null, msg, privateKey));
    assert.equal(createPublicKey(key).export({ format: "jwk" }).x, publicKey.export({ format: "jwk" }).x);
    assert.ok(verify(null, msg, publicKey, sign(null, msg, key)));
  }
});

test("a seed that is not 32 bytes is refused", () => {
  assert.throws(() => ed25519PrivateKeyFromSeed(Buffer.alloc(31, 1).toString("base64")));
  assert.throws(() => ed25519PrivateKeyFromSeed(""));
});
