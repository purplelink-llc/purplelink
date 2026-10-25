/**
 * Shared per-request visitor helpers for the first-party counters.
 *
 * visitorId: the daily visitor hash track.mjs has always written on beacon events. A function that stores the same
 * value lets a server-side event (a download) be joined to that day's page views. It changes every UTC day, so it
 * cannot link one person across days. It is unsalted, so it is not a secret: anyone who knows an IP and a day can
 * recompute it.
 *
 * clientClass: a coarse user-agent bucket ("browser", "crawler", "other"); the user agent itself is never stored.
 *
 * isOwnIp: whether the request comes from one of our own addresses, listed in the PURPLELINK_OWN_IPS env var
 * (comma-separated; an exact IPv4 or IPv6 address, or an IPv6 /64 written "2001:db8:1:2::/64", because home IPv6
 * addresses rotate inside their /64). The list lives in the env, never in this public repo.
 */
import { createHash } from "node:crypto";

export const BOT_UA = /bot|crawl|spider|slurp|preview|facebookexternalhit|curl|wget|python-requests|httpclient|headless/i;
const BROWSER_UA = /^Mozilla\/5\.0 .*(Safari|Chrome|Firefox|Edg)\//;

export function visitorId(day, ip) {
  return createHash("sha256").update(`${day}|pl|${ip}`).digest("hex").slice(0, 16);
}

export function clientClass(ua) {
  if (!ua || BOT_UA.test(ua)) return "crawler";
  return BROWSER_UA.test(ua) ? "browser" : "other";
}

/** The first four hextets of an IPv6 address, expanded and lower-case, or null for anything that is not IPv6. */
function v6Prefix64(addr) {
  if (!addr.includes(":")) return null;
  const lower = addr.toLowerCase();
  let groups;
  if (lower.includes("::")) {
    const [head, tail] = lower.split("::");
    const h = head ? head.split(":") : [];
    const t = tail ? tail.split(":") : [];
    groups = [...h, ...Array(Math.max(0, 8 - h.length - t.length)).fill("0"), ...t];
  } else {
    groups = lower.split(":");
  }
  if (groups.length < 4) return null;
  return groups.slice(0, 4).map((g) => g.replace(/^0+(?=.)/, "")).join(":");
}

export function isOwnIp(ip, list) {
  if (!ip || ip === "unknown" || !list) return false;
  for (const raw of String(list).split(",")) {
    const entry = raw.trim();
    if (!entry) continue;
    if (entry.endsWith("/64")) {
      const want = v6Prefix64(entry.slice(0, -3));
      if (want && v6Prefix64(ip) === want) return true;
    } else if (entry.toLowerCase() === ip.toLowerCase()) {
      return true;
    }
  }
  return false;
}
