// pl_attr: the one cookie purplelink.llc sets. A first-party, HttpOnly cookie written by the server when an ad or
// campaign visitor downloads the ModernTex trial, so a purchase made after the 7-day trial can still be credited to the
// campaign even if the browser has dropped its script-written storage (Safari does after 7 days). It holds four
// things and nothing personal: the first-touch channel label, the Reddit ad click id, the tag of the link that brought
// the visitor (utm_content, which names one ad or post, so a sale can be credited to that ad), and the day first seen.
// Never set under Do Not Track. Read by checkout.mjs only when the page did not send the same data.

export const COOKIE_NAME = "pl_attr";
export const COOKIE_MAX_AGE = 90 * 24 * 60 * 60;

const CHANNEL_RE = /^[\w.\-:]{1,40}$/;
const RDT_RE = /^[\w.\-:=]{1,128}$/;
const TAG_RE = /^[\w.\-]{1,60}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
// The value is  v2~<channel>~<rdt click id, percent-encoded>~<tag>~<YYYY-MM-DD> . Cookies set before the tag was
// added (2026-10-29) read  v1~<channel>~<rdt>~<date>  and decode with an empty tag. Every part is validated against a
// strict allow-list before it is written and again when it is read, so nothing from a request can reach a header.
const VALUE_RE = /^v1~([\w.\-:]{0,40})~([\w.\-:%]{0,200})~(\d{4}-\d{2}-\d{2})$/;
const VALUE_V2_RE = /^v2~([\w.\-:]{0,40})~([\w.\-:%]{0,200})~([\w.\-]{0,60})~(\d{4}-\d{2}-\d{2})$/;

function validDate(d) {
  if (typeof d !== "string" || !DATE_RE.test(d)) return false;
  const t = Date.parse(d + "T00:00:00Z");
  return Number.isFinite(t) && new Date(t).toISOString().slice(0, 10) === d;
}

/** Visitors never send DNT=1 from analytics.js, but the header is honoured here too. */
export function dntRequested(request) {
  const v = request.headers.get("dnt");
  return v === "1";
}

/** Pull and validate the attribution params the trial link carries. Returns null when there is nothing to remember. */
export function fromTrialParams(searchParams, now = new Date()) {
  const rawChannel = searchParams.get("ach") || "";
  const rawRdt = searchParams.get("arc") || "";
  const channel = CHANNEL_RE.test(rawChannel) ? rawChannel : "";
  const rdt = RDT_RE.test(rawRdt) ? rawRdt : "";
  const rawTag = searchParams.get("atg") || "";
  const tag = TAG_RE.test(rawTag) ? rawTag : "";
  if (!rdt && (!channel || channel === "direct")) return null;
  const today = now.toISOString().slice(0, 10);
  const rawDate = searchParams.get("ad") || "";
  // The first-seen day is the browser's claim: accept it only if it is a real date, not in the future, within 90 days.
  const floor = new Date(now.getTime() - COOKIE_MAX_AGE * 1000).toISOString().slice(0, 10);
  const date = validDate(rawDate) && rawDate <= today && rawDate >= floor ? rawDate : today;
  return { channel: channel || "direct", rdt, tag, date };
}

export function encodeValue({ channel, rdt, tag = "", date }) {
  if (!CHANNEL_RE.test(channel) || (rdt && !RDT_RE.test(rdt)) || (tag && !TAG_RE.test(tag)) || !validDate(date)) return "";
  return `v2~${channel}~${rdt ? encodeURIComponent(rdt) : ""}~${tag}~${date}`;
}

export function decodeValue(value) {
  const s = typeof value === "string" ? value : "";
  const v2 = VALUE_V2_RE.exec(s);
  const v1 = v2 ? null : VALUE_RE.exec(s);
  if (!v2 && !v1) return null;
  const [rawChannel, rawRdt, tag, date] = v2 ? [v2[1], v2[2], v2[3], v2[4]] : [v1[1], v1[2], "", v1[3]];
  let rdt = "";
  if (rawRdt) {
    try { rdt = decodeURIComponent(rawRdt); } catch { return null; }
    if (!RDT_RE.test(rdt)) return null;
  }
  if (rawChannel && !CHANNEL_RE.test(rawChannel)) return null;
  if (tag && !TAG_RE.test(tag)) return null;
  if (!validDate(date)) return null;
  if (!rawChannel && !rdt) return null;
  return { channel: rawChannel || "direct", rdt, tag, date };
}

/** The pl_attr cookie from a request's Cookie header, validated, or null. */
export function readAttrCookie(request) {
  try {
    const header = request.headers.get("cookie") || "";
    for (const part of header.split(";")) {
      const i = part.indexOf("=");
      if (i < 0) continue;
      if (part.slice(0, i).trim() === COOKIE_NAME) return decodeValue(part.slice(i + 1).trim());
    }
  } catch { /* an unreadable cookie is the same as none */ }
  return null;
}

/** The Set-Cookie header line for a validated record, or "" when the record is not valid. */
export function setCookieHeader(record) {
  const v = encodeValue(record);
  return v ? `${COOKIE_NAME}=${v}; Path=/; Max-Age=${COOKIE_MAX_AGE}; HttpOnly; Secure; SameSite=Lax` : "";
}

/**
 * What to add to a trial download response: the Set-Cookie line, or "" when no cookie should be set (Do Not Track,
 * nothing worth remembering, or a cookie already there: the first touch wins). Never throws.
 */
export function trialCookieFor(request, url) {
  try {
    if (dntRequested(request)) return "";
    if (readAttrCookie(request)) return "";
    const rec = fromTrialParams(url.searchParams);
    return rec ? setCookieHeader(rec) : "";
  } catch { return ""; }
}

/** A first-touch record in the shape analytics.js sends (s, m, d, c, t), rebuilt from the cookie's channel and tag. */
export function touchFromCookie(rec) {
  const ch = rec.channel;
  const t = { d: rec.date, c: "attr-cookie" };
  if (rec.tag) t.t = rec.tag;
  if (ch.startsWith("paid:")) { t.s = ch.slice(5); t.m = "cpc"; }
  else if (ch.startsWith("tool:")) t.s = "tool-" + ch.slice(5);
  else if (ch !== "direct") t.s = ch;
  return t;
}
