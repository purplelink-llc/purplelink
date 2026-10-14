/**
 * Count-only "signals": answers a person chooses to send (the ModernTex why-not page and the trial-download poll).
 *
 * Only aggregate counters are stored, one per ISO week, kind, value (and, for whynot, a trial-day bucket). Nothing
 * about the sender is kept: no IP, no user agent, no timestamp finer than the week. signal.mjs writes the counters;
 * stats.mjs?section=signals reads them back for the owner.
 *
 * Counter key: <ISO week>/<kind>/<value>[/<td bucket>]   e.g. 2026-W42/whynot/price/4-7
 */

export const ALLOWLIST = {
  whynot: ["price", "feature", "other-tool", "deciding", "other"],
  trialpoll: ["paper", "thesis", "coauthors", "replace-overleaf", "course-notes", "looking", "other"],
};
export const TD_BUCKETS = ["0-3", "4-7", "8+", "unknown"];

/** Trial day as sent by the app's links: whole days 0 to 30, or "unknown". Returns the normalised string or null. */
export function parseTd(v) {
  if (v === undefined || v === null || v === "") return null;
  if (typeof v === "number") v = Number.isInteger(v) ? String(v) : "";
  if (typeof v !== "string") return "bad";
  return /^(?:[0-9]|[12][0-9]|30|unknown)$/.test(v) ? v : "bad";
}

export function tdBucket(td) {
  if (td === null || td === undefined || td === "unknown") return "unknown";
  const n = Number(td);
  if (n <= 3) return "0-3";
  if (n <= 7) return "4-7";
  return "8+";
}

/** ISO 8601 week label for a date, e.g. "2026-W42". */
export function isoWeek(d = new Date()) {
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dow = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - dow);
  const yearStart = Date.UTC(t.getUTCFullYear(), 0, 1);
  const week = Math.ceil(((t - yearStart) / 86400000 + 1) / 7);
  return `${t.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

export function counterKey(week, kind, value, bucket) {
  return bucket ? `${week}/${kind}/${value}/${bucket}` : `${week}/${kind}/${value}`;
}

/** The last `n` ISO week labels, newest first. */
export function recentWeeks(n, now = new Date()) {
  const out = [];
  for (let i = 0; i < n; i++) out.push(isoWeek(new Date(now.getTime() - i * 7 * 86400000)));
  return out;
}

/**
 * Weekly counts for the owner: { "2026-W42": { whynot: { price: {total, "0-3": n, ...} }, trialpoll: { paper: n } } }.
 * Reads every counter under the given weeks; unknown keys are ignored.
 */
export async function readSignals(store, weeks) {
  const out = {};
  for (const week of weeks) {
    const listing = await store.list({ prefix: `${week}/` });
    const w = {};
    for (const b of (listing && listing.blobs) || []) {
      const [, kind, value, bucket] = b.key.split("/");
      if (!ALLOWLIST[kind] || !ALLOWLIST[kind].includes(value)) continue;
      if (bucket !== undefined && !TD_BUCKETS.includes(bucket)) continue;
      const n = parseInt((await store.get(b.key)) || "0", 10) || 0;
      w[kind] = w[kind] || {};
      if (kind === "whynot") {
        const row = (w[kind][value] = w[kind][value] || { total: 0 });
        if (bucket) row[bucket] = (row[bucket] || 0) + n;
        row.total += n;
      } else {
        w[kind][value] = (w[kind][value] || 0) + n;
      }
    }
    if (Object.keys(w).length) out[week] = w;
  }
  return out;
}
