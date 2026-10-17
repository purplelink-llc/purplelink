/**
 * Signed, expiring links for double opt-in (digest signup, researcher checklist).
 *
 * Nothing is stored when someone asks to join: the request is carried inside the token, which is emailed
 * to the address. Token: base64url(JSON payload) "." expiry (unix seconds) "." hex HMAC-SHA256(
 * SUBSCRIBE_SECRET, "<kind>:<base64url payload>:<expiry>"). The kind namespaces the signature, so a
 * confirmation token can never be used as the permanent unsubscribe token (an HMAC of the bare address),
 * a billing-portal link, or the other list's confirmation. Links last 3 days.
 */
import { createHmac, timingSafeEqual } from "node:crypto";

export const CONFIRM_LINK_SECONDS = 3 * 24 * 60 * 60;

const mac = (secret, kind, enc, exp) => createHmac("sha256", secret).update(`${kind}:${enc}:${exp}`).digest("hex");

export function signConfirmToken(kind, payload, secret, now = Math.floor(Date.now() / 1000)) {
  const enc = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  const exp = now + CONFIRM_LINK_SECONDS;
  return `${enc}.${exp}.${mac(secret, kind, enc, exp)}`;
}

/** The payload of a valid, unexpired token of this kind, or null. */
export function verifyConfirmToken(kind, token, secret, now = Math.floor(Date.now() / 1000)) {
  if (!secret || typeof token !== "string" || token.length > 900) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [enc, expStr, sig] = parts;
  if (!/^\d{1,12}$/.test(expStr) || !/^[0-9a-f]{64}$/.test(sig)) return null;
  const exp = Number(expStr);
  if (exp < now) return null;
  if (!timingSafeEqual(Buffer.from(mac(secret, kind, enc, exp)), Buffer.from(sig))) return null;
  try {
    const payload = JSON.parse(Buffer.from(enc, "base64url").toString("utf8"));
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}
