// Tapefolio license keys: `TFL1-` + Crockford-Base32(4-byte nonce ‖ 64-byte Ed25519 signature
// over "TapefolioLicenseV1" + nonce). The app checks the signature offline against the public key
// below (the Tapefolio app's own license code): this file and that one MUST stay byte-for-byte
// compatible. The private key lives only in TAPEFOLIO_LICENSE_PRIVATE_KEY (Netlify production env)
// and ~/.config/purplelink/tapefolio-license-private-key; it is never logged, returned or committed.
//
// This is the same scheme as netlify/lib/keyfeel-license.mjs with its own prefix, domain string,
// seed string and key pair, so a Keyfeel key never unlocks Tapefolio or the other way round.
//
// The nonce comes from the buyer's email address, so one buyer gets the same key from the
// receipt email, the success page and "Find a purchase". Like ModernTex, a key is not tied to a
// machine and cannot be revoked remotely; a refund is handled by asking the buyer to stop using it.
import { createHash, createPrivateKey, sign as edSign } from "node:crypto";

export const TAPEFOLIO_LICENSE_PUBLIC_KEY_B64 = "5qmJMOr4uux0LZrWGs/V6nc6VKXsogioMgiJ3pBlSvI=";
const DOMAIN = Buffer.from("TapefolioLicenseV1", "utf8");
const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

export function crockfordBase32Encode(buf) {
  let bits = 0n, bitCount = 0, out = "";
  for (const byte of buf) {
    bits = (bits << 8n) | BigInt(byte);
    bitCount += 8;
    while (bitCount >= 5) {
      bitCount -= 5;
      out += ALPHABET[Number((bits >> BigInt(bitCount)) & 0x1fn)];
    }
  }
  if (bitCount > 0) out += ALPHABET[Number((bits << BigInt(5 - bitCount)) & 0x1fn)];
  return out;
}

const b64url = (s) => s.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

/**
 * The key for one buyer, or null when the private key is not configured or there is no address. Never throws.
 * `publicKeyB64` defaults to the production public key; only tests pass another, because they sign with a
 * throwaway key pair and never see the production private key.
 */
export function issueTapefolioLicense(
  email,
  env = (name) => globalThis.Netlify?.env?.get(name),
  publicKeyB64 = TAPEFOLIO_LICENSE_PUBLIC_KEY_B64,
) {
  const priv = env("TAPEFOLIO_LICENSE_PRIVATE_KEY");
  const who = String(email || "").trim().toLowerCase();
  if (!priv || !who) return null;
  try {
    const privateKey = createPrivateKey({
      key: { kty: "OKP", crv: "Ed25519", d: b64url(priv.trim()), x: b64url(publicKeyB64) },
      format: "jwk",
    });
    const nonce = createHash("sha256").update("tapefolio-license:" + who).digest().subarray(0, 4);
    const signature = edSign(null, Buffer.concat([DOMAIN, nonce]), privateKey);
    const groups = crockfordBase32Encode(Buffer.concat([nonce, signature])).match(/.{1,5}/g) ?? [];
    return "TFL1-" + groups.join("-");
  } catch {
    return null;
  }
}
