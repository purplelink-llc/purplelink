/**
 * Shared-secret checks for owner-only endpoints.
 *
 * safeEqual hashes both sides to the same length first, so the comparison is
 * constant-time even when the lengths differ. ownerToken reads the token from
 * an "Authorization: Bearer" header or an "x-stats-token" header, and falls back
 * to the ?token= query parameter that the owner's existing dashboard scripts
 * still send. Prefer the header: URLs end up in logs and browser history.
 */
import { createHash, timingSafeEqual } from "node:crypto";

export function safeEqual(given, expected) {
  if (typeof expected !== "string" || expected.length === 0) return false;
  const a = createHash("sha256").update(String(given ?? "")).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}

export function ownerToken(request, url = new URL(request.url)) {
  const auth = request.headers.get("authorization") || "";
  const m = /^Bearer\s+(.+)$/i.exec(auth);
  if (m) return m[1].trim();
  const h = request.headers.get("x-stats-token");
  if (h) return h;
  return url.searchParams.get("token") || "";
}

export function bearerMatches(request, secret) {
  const auth = request.headers.get("authorization") || "";
  return safeEqual(auth, `Bearer ${secret}`);
}
