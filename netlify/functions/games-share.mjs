/**
 * Netlify Function: a game result as a link preview (purplelink games).
 *
 * GET /games/r/<game>/<code>       small page with Open Graph tags, then sends the visitor to the game
 * GET /games/r/<game>/<code>.png   the 1200x630 result card those tags point at
 *
 * <code> is the result text the game already builds for sharing (headline, rows of ■ ▣ □, detail
 * lines), URL-safe base64 of its UTF-8, without the trailing link. Nothing is stored: the card is
 * drawn from the code on request and cached by the CDN, so the same link always shows the same card.
 * The text is clipped, reduced to printable characters and XML-escaped before it is drawn.
 */

import { Resvg } from "@resvg/resvg-js";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
// where the bundled fonts end up depends on how Netlify packages the function, so look in the likely places
const FONT_DIR = [join(HERE, "fonts"), join(process.cwd(), "netlify/functions/fonts"), "/var/task/netlify/functions/fonts"].find((d) => existsSync(join(d, "Fraunces-SemiBold.ttf"))) || join(HERE, "fonts");
const FONTS = ["Fraunces-SemiBold.ttf", "PlusJakartaSans-Regular.ttf", "PlusJakartaSans-Bold.ttf"].map((f) => join(FONT_DIR, f));
const ORIGIN = "https://purplelink.llc";
const MAX_TEXT = 420;

const C = { bg: "#1b1524", bg2: "#2a1f3d", text: "#f4eff9", dim: "#b9acc9", accent: "#c9a6f0", ok: "#a974ee", part: "#e7b95a", none: "#3b3050" };

function decode(code) {
  try {
    const raw = Buffer.from(code, "base64url").toString("utf8");
    return clean(raw);
  } catch {
    return "";
  }
}

function clean(s) {
  let out = "";
  for (const ch of String(s).replace(/https?:\/\/\S+/g, "").replace(/\r/g, "")) {
    const c = ch.codePointAt(0);
    const bad = c < 32 && ch !== "\n" || c === 127 || c >= 0x200b && c <= 0x200f || c === 0x2028 || c === 0x2029 || c === 0xfeff;
    if (!bad) out += ch;
  }
  return out.slice(0, MAX_TEXT).trim();
}

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function wrap(text, max) {
  const out = [];
  let line = "";
  for (const w of text.split(/\s+/)) {
    if (line && (line + " " + w).length > max) { out.push(line); line = w; } else line = line ? line + " " + w : w;
  }
  if (line) out.push(line);
  return out;
}

/** Split the shared text into a headline, grid rows (null = gap between boards) and detail lines. */
export function parse(text) {
  const lines = text.split("\n").map((l) => l.trim());
  let head = "";
  const rows = [], details = [];
  for (const l of lines) {
    if (!head) { if (l) head = l; continue; }
    const m = l.match(/^([■▣□]+)\s*(.*)$/);
    if (m) { rows.push(m[1].split("")); if (m[2]) details.push(m[2]); continue; }
    if (!l) { if (rows.length && rows[rows.length - 1]) rows.push(null); continue; }
    details.push(l);
  }
  while (rows.length && rows[rows.length - 1] === null) rows.pop();
  return { head: head || "Purplelink Games", rows, details: details.slice(0, 4) };
}

function hash(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

export function cardSvg(text) {
  const parsed = parse(text);
  const { rows, details } = parsed;
  // a score such as 4/6 or X/6 at the end of the headline gets its own large line
  const sm = parsed.head.match(/\s(\d+|X)\/(\d+)\s*$/);
  const score = sm ? sm[1] + "/" + sm[2] : "";
  const head = sm ? parsed.head.slice(0, sm.index) : parsed.head;
  const size = head.length <= 22 ? 76 : head.length <= 40 ? 60 : 46;
  const hasGrid = rows.some(Boolean);
  const textW = hasGrid ? 540 : 700;
  const headLines = wrap(head, Math.floor(textW / (size * 0.53))).slice(0, 3);
  let y = (score ? 220 : 250) - (headLines.length - 1) * size * 0.5;
  const parts = [];
  parts.push(`<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${C.bg}"/><stop offset="1" stop-color="${C.bg2}"/></linearGradient></defs>`);
  parts.push(`<rect width="1200" height="630" fill="url(#g)"/>`);
  parts.push(`<rect x="80" y="76" width="30" height="30" rx="8" fill="${C.ok}"/><rect x="92" y="88" width="30" height="30" rx="8" fill="${C.accent}" opacity="0.85"/>`);
  parts.push(`<text x="140" y="108" font-family="Plus Jakarta Sans" font-weight="700" font-size="28" fill="${C.accent}">Purplelink Games</text>`);
  for (const l of headLines) {
    parts.push(`<text x="80" y="${Math.round(y)}" font-family="Fraunces" font-weight="600" font-size="${size}" fill="${C.text}">${esc(l)}</text>`);
    y += size * 1.08;
  }
  if (score) {
    parts.push(`<text x="80" y="${Math.round(y + 100)}" font-family="Fraunces" font-weight="600" font-size="150" fill="${C.accent}">${esc(score)}</text>`);
    y += 130;
  }
  y += 14;
  for (const d of details.flatMap((d) => wrap(d, hasGrid ? 34 : 60)).slice(0, 5)) {
    parts.push(`<text x="80" y="${Math.round(y + 24)}" font-family="Plus Jakarta Sans" font-weight="500" font-size="30" fill="${C.dim}">${esc(d)}</text>`);
    y += 42;
  }
  parts.push(`<text x="80" y="570" font-family="Plus Jakarta Sans" font-weight="700" font-size="26" fill="${C.accent}">purplelink.llc/games</text>`);

  if (hasGrid) {
    const cols = Math.max(...rows.filter(Boolean).map((r) => r.length));
    const area = { x: 660, y: 90, w: 460, h: 450 };
    const gapRows = rows.filter((r) => r === null).length;
    const cell = Math.min(96, Math.floor(area.w / (cols * 1.14)), Math.floor(area.h / ((rows.length - gapRows) * 1.14 + gapRows * 0.5)));
    const step = Math.round(cell * 1.14);
    const gridW = cols * step - (step - cell);
    const gridH = (rows.length - gapRows) * step + gapRows * Math.round(cell * 0.5) - (step - cell);
    const x0 = area.x + Math.round((area.w - gridW) / 2), y0 = area.y + Math.round((area.h - gridH) / 2);
    let ry = y0;
    for (const r of rows) {
      if (r === null) { ry += Math.round(cell * 0.5); continue; }
      const rowW = r.length * step - (step - cell);
      const rx0 = x0 + Math.round((gridW - rowW) / 2);
      r.forEach((ch, i) => {
        const x = rx0 + i * step, rad = Math.round(cell * 0.2);
        if (ch === "■") parts.push(`<rect x="${x}" y="${ry}" width="${cell}" height="${cell}" rx="${rad}" fill="${C.ok}"/>`);
        else if (ch === "▣") parts.push(`<rect x="${x}" y="${ry}" width="${cell}" height="${cell}" rx="${rad}" fill="${C.part}"/><circle cx="${x + cell / 2}" cy="${ry + cell / 2}" r="${Math.round(cell * 0.14)}" fill="${C.bg}"/>`);
        else parts.push(`<rect x="${x + 1.5}" y="${ry + 1.5}" width="${cell - 3}" height="${cell - 3}" rx="${rad}" fill="${C.none}" stroke="#52446a" stroke-width="3"/>`);
      });
      ry += step;
    }
  } else {
    // no grid in this result: a small mosaic, different for each result, so the card is not just type
    let h = hash(text);
    const tones = [C.ok, C.accent, "#7d4fc4", C.none, "#52446a"];
    for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) {
      h = Math.imul(h ^ (h >>> 15), 2246822507) >>> 0;
      parts.push(`<rect x="${870 + c * 74}" y="${330 + r * 52}" width="62" height="40" rx="10" fill="${tones[h % tones.length]}" opacity="${0.55 + (h % 4) * 0.12}"/>`);
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">${parts.join("")}</svg>`;
}

function png(text) {
  const r = new Resvg(cardSvg(text), { font: { fontFiles: FONTS, loadSystemFonts: false, defaultFontFamily: "Plus Jakarta Sans" } });
  return r.render().asPng();
}

function page(slug, code, text, from) {
  const { head, rows, details } = parse(text);
  const desc = [details[0], rows.some(Boolean) ? "Play today's puzzle and compare." : "Play it yourself at Purplelink Games."].filter(Boolean).join(" ");
  const self = `${ORIGIN}/games/r/${slug}/${code}`;
  const img = `${self}.png`;
  const dest = `/games/${slug}/?from=share-${from}`;
  const t = esc(head);
  const d = esc(desc);
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${t}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="description" content="${d}">
<link rel="canonical" href="${ORIGIN}/games/${slug}/">
<meta property="og:type" content="website"><meta property="og:site_name" content="Purplelink Games">
<meta property="og:title" content="${t}"><meta property="og:description" content="${d}">
<meta property="og:url" content="${self}"><meta property="og:image" content="${img}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="${t}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="${t}"><meta name="twitter:description" content="${d}"><meta name="twitter:image" content="${img}">
<meta http-equiv="refresh" content="0; url=${dest}"></head>
<body><p><a href="${dest}">Play ${t.split(/\s+\d/)[0]} at Purplelink Games</a></p></body></html>`;
}

export default async function handler(request) {
  const url = new URL(request.url);
  const m = url.pathname.match(/^\/games\/r\/([a-z0-9-]{1,40})\/([A-Za-z0-9_-]{1,1800})(\.png)?$/);
  if (!m || request.method !== "GET" && request.method !== "HEAD") return Response.redirect(`${ORIGIN}/games/`, 302);
  const [, slug, code, isPng] = m;
  const text = decode(code);
  if (!text) return Response.redirect(`${ORIGIN}/games/${slug}/`, 302);
  if (isPng) {
    try {
      return new Response(png(text), { headers: { "Content-Type": "image/png", "Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff" } });
    } catch {
      return Response.redirect(`${ORIGIN}/assets/og/games-${slug}.png`, 302);
    }
  }
  const from = (url.searchParams.get("f") || "link").replace(/[^a-z]/g, "").slice(0, 12) || "link";
  return new Response(page(slug, code, text, from), { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=3600" } });
}

export const config = { path: "/games/r/*" };
