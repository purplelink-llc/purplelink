// Ed25519 signing keys from a 32-byte seed (base64 or base64url), the form every license secret is kept in.
// The key is built as PKCS#8 DER from the seed alone. A JWK with both "d" and "x" is refused by Node 24.22
// and later when "x" is not the seed's public key (ERR_CRYPTO_INVALID_JWK), and test seeds never match the
// real public keys; the seed determines the key completely, so the signatures are byte-identical either way.
import { createPrivateKey } from "node:crypto";

const PKCS8_ED25519_PREFIX = Buffer.from("302e020100300506032b657004220420", "hex");

export function ed25519PrivateKeyFromSeed(seedB64) {
  const seed = Buffer.from(String(seedB64).trim().replace(/-/g, "+").replace(/_/g, "/"), "base64");
  if (seed.length !== 32) throw new Error("ed25519 seed must be 32 bytes");
  return createPrivateKey({ key: Buffer.concat([PKCS8_ED25519_PREFIX, seed]), format: "der", type: "pkcs8" });
}
