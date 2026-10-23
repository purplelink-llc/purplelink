/**
 * Netlify Function — the Instagram link-in-bio page (https://purplelink.llc/instagram/).
 * Instagram captions cannot carry a clickable link, so every Purplelink Instagram post says "Link in bio." and the
 * profile's one link points here. The list is written by backend/socialpost/instagram (social.py instagram run) to
 * the dedicated `instagram-links` Blobs store, key latest.json: [{title, kind, url, date}], newest first. Each url
 * already carries utm_source=instagram&utm_medium=social&utm_campaign=<campaign>.
 *
 *   GET|HEAD /instagram/  -> an HTML page listing those links (short cache)
 *
 * Read-only: one fixed key, no listing, no other method. A url is shown only if it is on purplelink.llc or
 * www.youtube.com, and every string is escaped. When the store is empty or unreachable the page lists the main
 * sections instead, so the bio link always works.
 */
import { getStore } from "@netlify/blobs";

const STORE = "instagram-links";
const KEY = "latest.json";
const ALLOWED = [/^https:\/\/purplelink\.llc\//, /^https:\/\/www\.youtube\.com\/watch\?v=[\w-]{11}(&|$)/];
const FALLBACK = [
  { title: "Mac apps", url: "https://purplelink.llc/products/?utm_source=instagram&utm_medium=social&utm_campaign=bio" },
  { title: "Free guides", url: "https://purplelink.llc/guides/?utm_source=instagram&utm_medium=social&utm_campaign=bio" },
  { title: "Free tools", url: "https://purplelink.llc/tools/?utm_source=instagram&utm_medium=social&utm_campaign=bio" },
];

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

export function clean(rows) {
  if (!Array.isArray(rows)) return [];
  return rows
    .filter((r) => r && typeof r.url === "string" && typeof r.title === "string" && ALLOWED.some((re) => re.test(r.url)))
    .slice(0, 12)
    .map((r) => ({ title: r.title.slice(0, 140), url: r.url, date: /^\d{4}-\d{2}-\d{2}$/.test(r.date || "") ? r.date : "" }));
}

export function page(rows) {
  const list = rows.length ? rows : FALLBACK;
  const items = list
    .map((r) => `        <li><a href="${esc(r.url)}">${esc(r.title)}</a>${r.date ? ` <span class="ig-date">${esc(r.date)}</span>` : ""}</li>`)
    .join("\n");
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex">
    <title>From our Instagram | Purplelink LLC</title>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#19141d">
    <script src="/theme.js"></script>
    <link rel="stylesheet" href="/styles.css">
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-mark.svg" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
    </header>
    <main id="main-content" class="not-found">
      <h1>From our Instagram</h1>
      <p>${rows.length ? "The pages from our latest posts, newest first." : "Where to start."}</p>
      <ul>
${items}
      </ul>
      <p><a href="https://purplelink.llc/?utm_source=instagram&amp;utm_medium=social&amp;utm_campaign=bio">purplelink.llc</a></p>
    </main>
  </body>
</html>
`;
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  let rows = [];
  try {
    rows = clean(await getStore(STORE).get(KEY, { type: "json" }));
  } catch {
    rows = [];
  }
  const headers = {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "public, max-age=300",
    "X-Content-Type-Options": "nosniff",
  };
  if (request.method === "HEAD") return new Response(null, { status: 200, headers });
  return new Response(page(rows), { status: 200, headers });
}
