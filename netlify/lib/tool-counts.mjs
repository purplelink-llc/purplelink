/**
 * Per-tool, count-only statistics for the free tool pages: runs, how each run ended, and the offer card's views and
 * clicks. One small JSON record per day and tool in the "tool-counts" store:
 *
 *   key   d/<YYYY-MM-DD>/<tool slug>          e.g. d/2026-10-14/latex-diff
 *   value { runs, ok, error, limit, offerViews, offerClicks }   whole numbers
 *
 * Nothing else is stored: no IP, user agent, timestamp finer than the day, visitor id, file name or content. The tool
 * slug is taken from the page path of the beacon and must be one of TOOL_SLUGS; the outcome and offer app must be one
 * of the short allowlists below. Anything else is dropped, so free text can never become a key or a value.
 *
 * TOOL_SLUGS is the list of directories under site/tools/ that hold a page. A site test
 * (site-tests/test_tool_offers.py) fails when the two differ, so adding a tool means adding it here too.
 */

export const TOOL_SLUGS = [
  "abstract-checker", "academic-email-signature", "anonymity-check", "bib-builder", "bib-validator", "camera-ready-checker", "citation-gap",
  "citation-generator", "cover-letter", "equation-renderer", "file-to-markdown", "latex-diff", "latex-table-generator",
  "latex-to-pdf", "latex-to-word", "markdown-to-pdf", "metadata-cleaner", "paper-review", "pdf-structure", "pdf-tools", "pii-checker",
  "reference-converter", "reproducibility-checker", "response-letter-template", "response-review", "resume-review",
  "retraction-check", "stock-keyword-cleaner", "submission-checklist", "thesis-format-checker", "transcript-cleaner", "word-counter", "word-to-latex",
];
export const OUTCOMES = ["ok", "error", "limit"];
export const OFFER_APPS = ["moderntex", "tapefolio", "outbound-veil", "vitae"];
export const COUNT_FIELDS = ["runs", "ok", "error", "limit", "offerViews", "offerClicks"];
/** The beacon event types this module counts. tool_use is also stored as an event record by track.mjs, as before. */
export const COUNTED_TYPES = ["tool_use", "tool_outcome", "offer_view", "offer_click"];

const SLUG_SET = new Set(TOOL_SLUGS);

/** /tools/<slug>/ (trailing slash optional) -> the slug if it is an allowlisted tool, else "". */
export function toolSlugFromPath(path) {
  const m = /^\/tools\/([a-z0-9-]{1,40})\/?$/.exec(String(path || ""));
  return m && SLUG_SET.has(m[1]) ? m[1] : "";
}

/** Which counter an event bumps, or "" when its meta is not on the allowlist for that type. */
export function countField(type, meta) {
  if (type === "tool_use") return "runs";
  if (type === "tool_outcome") return OUTCOMES.includes(meta) ? meta : "";
  if (type === "offer_view") return OFFER_APPS.includes(meta) ? "offerViews" : "";
  if (type === "offer_click") return OFFER_APPS.includes(meta) ? "offerClicks" : "";
  return "";
}

export const emptyCounts = () => Object.fromEntries(COUNT_FIELDS.map((f) => [f, 0]));
export const countKey = (day, slug) => `d/${day}/${slug}`;

/**
 * Add one to a counter. Read, add, write, like the other counters in this repo (Blobs here has no atomic increment):
 * two events in the same millisecond can count once, which is negligible at tens of events a day.
 */
export async function bumpToolCount(store, day, slug, field) {
  if (!SLUG_SET.has(slug) || !COUNT_FIELDS.includes(field)) return false;
  const key = countKey(day, slug);
  const cur = (await store.get(key, { type: "json" })) || {};
  const next = emptyCounts();
  for (const f of COUNT_FIELDS) next[f] = Number.isInteger(cur[f]) && cur[f] >= 0 ? cur[f] : 0;
  next[field] += 1;
  await store.setJSON(key, next);
  return true;
}

/** Counts for a list of YYYY-MM-DD days: { "<day>": { "<slug>": counts } }, skipping unknown slugs and empty days. */
export async function readToolCounts(store, days) {
  const out = {};
  for (const day of days) {
    let listing;
    try { listing = await store.list({ prefix: `d/${day}/` }); } catch (_) { continue; }
    for (const b of (listing && listing.blobs) || []) {
      const slug = b.key.split("/")[2];
      if (!SLUG_SET.has(slug)) continue;
      let cur = null;
      try { cur = await store.get(b.key, { type: "json" }); } catch (_) { /* skip */ }
      if (!cur) continue;
      const row = emptyCounts();
      for (const f of COUNT_FIELDS) row[f] = Number.isInteger(cur[f]) && cur[f] >= 0 ? cur[f] : 0;
      (out[day] = out[day] || {})[slug] = row;
    }
  }
  return out;
}
