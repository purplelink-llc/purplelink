/**
 * Purplelink license keys for Outbound Veil, Legroom and Keyfeel (scheme "PurplelinkLicenseV1").
 *
 * A key is  <PREFIX>-  +  Crockford-Base32( nonce[4] ‖ Ed25519 signature[64] ),  split into groups of 5.
 * The signature covers  UTF8("PurplelinkLicenseV1|<slug>|") ‖ nonce,  so a key for one product never
 * verifies for another. The app holds only the PUBLIC key and verifies offline; the private seed lives
 * in the PURPLELINK_LICENSE_PRIVATE_KEY secret (Netlify) and in ~/.config/purplelink/license-keys/.
 *
 * Keys are DERIVED from the Stripe session id: the nonce is HMAC-SHA256(seed, "nonce|<slug>|<sessionId>")
 * truncated to 4 bytes, and Ed25519 signing is deterministic, so the same purchase always yields the same
 * key. That is what lets the success page, the email and the recovery page all show one key without storing
 * anything. ModernTex keeps its own older scheme (MTX1, in stripe-webhook.mjs).
 *
 * This file is pure (no Netlify globals) so tests and the Swift side can pin it byte for byte.
 */
import { createHmac, createPrivateKey, createPublicKey, sign as edSign, verify as edVerify, randomBytes } from "node:crypto";

export const LICENSE_SCHEME = "PurplelinkLicenseV1";
/** Raw 32-byte Ed25519 public key, base64. Baked into the apps. */
export const PURPLELINK_LICENSE_PUBLIC_KEY_B64 = "d8gyRHTJVAivaL2wx4m1dQTLxrfE2htFhxzNDF8dFs4=";

export const LICENSED_PRODUCTS = {
  "outbound-veil": { prefix: "OV1", label: "Outbound Veil", appPath: "/outbound-veil/" },
  legroom: { prefix: "LG1", label: "Legroom", appPath: "/legroom/" },
  keyfeel: { prefix: "KF1", label: "Keyfeel", appPath: "/keyfeel/" },
};

const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

export function crockfordEncode(buf) {
  let bits = 0n, count = 0, out = "";
  for (const byte of buf) {
    bits = (bits << 8n) | BigInt(byte);
    count += 8;
    while (count >= 5) {
      count -= 5;
      out += ALPHABET[Number((bits >> BigInt(count)) & 0x1fn)];
    }
  }
  if (count > 0) out += ALPHABET[Number((bits << BigInt(5 - count)) & 0x1fn)];
  return out;
}

export function crockfordDecode(text) {
  const clean = text.toUpperCase().replace(/O/g, "0").replace(/[IL]/g, "1");
  let bits = 0n, count = 0;
  const bytes = [];
  for (const ch of clean) {
    const v = ALPHABET.indexOf(ch);
    if (v < 0) return null;
    bits = (bits << 5n) | BigInt(v);
    count += 5;
    if (count >= 8) {
      count -= 8;
      bytes.push(Number((bits >> BigInt(count)) & 0xffn));
    }
  }
  return Buffer.from(bytes);
}

const b64url = (b64) => b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

function domainFor(slug) {
  return Buffer.from(`${LICENSE_SCHEME}|${slug}|`, "utf8");
}

function privateKeyFromSeed(seedB64, publicB64 = PURPLELINK_LICENSE_PUBLIC_KEY_B64) {
  return createPrivateKey({ key: { kty: "OKP", crv: "Ed25519", d: b64url(seedB64), x: b64url(publicB64) }, format: "jwk" });
}

/**
 * One license key for `slug`, or null if the seed is missing or anything fails (never throws: a signing
 * problem must not break delivery of the download itself). With a sessionId the key is deterministic.
 */
export function issueLicense(slug, { sessionId, seedB64, publicB64 } = {}) {
  const product = LICENSED_PRODUCTS[slug];
  if (!product || !seedB64) return null;
  try {
    const privateKey = privateKeyFromSeed(seedB64, publicB64);
    const nonce = sessionId
      ? createHmac("sha256", Buffer.from(seedB64, "base64")).update(`nonce|${slug}|${sessionId}`).digest().subarray(0, 4)
      : randomBytes(4);
    const signature = edSign(null, Buffer.concat([domainFor(slug), nonce]), privateKey);
    const body = crockfordEncode(Buffer.concat([nonce, signature]));
    return `${product.prefix}-${(body.match(/.{1,5}/g) ?? []).join("-")}`;
  } catch {
    return null;
  }
}

/** Offline check, mirroring what the Swift apps do. */
export function verifyLicense(slug, key, { publicB64 = PURPLELINK_LICENSE_PUBLIC_KEY_B64 } = {}) {
  const product = LICENSED_PRODUCTS[slug];
  if (!product || typeof key !== "string") return false;
  let text = key.trim().toUpperCase().replace(/-/g, "");
  const prefix = product.prefix.replace(/-/g, "");
  if (text.startsWith(prefix)) text = text.slice(prefix.length);
  const raw = crockfordDecode(text);
  if (!raw || raw.length !== 68) return false;
  try {
    const publicKey = createPublicKey({ key: { kty: "OKP", crv: "Ed25519", x: b64url(publicB64) }, format: "jwk" });
    return edVerify(null, Buffer.concat([domainFor(slug), raw.subarray(0, 4)]), publicKey, raw.subarray(4));
  } catch {
    return false;
  }
}

/** The products whose key a paid session is entitled to. The Suite entitles all three (ModernTex's key is separate). */
export function licensedSlugsFor(productKey) {
  if (productKey === "app-suite") return Object.keys(LICENSED_PRODUCTS);
  return LICENSED_PRODUCTS[productKey] ? [productKey] : [];
}
