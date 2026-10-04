// Pure helpers for the games account API: merging two copies of a player's saved progress,
// cleaning what a browser sends, and turning a score histogram into a percentile.
// No I/O here so it can be tested without Netlify.

export const GAMES = ["linkle", "quadlink", "daily-five", "daily-photo", "daily-chess", "sudoku", "crossword", "daily-stars", "landlink", "atomlink", "prizelink", "citylink", "peaklink", "codelink", "thinkerlink", "riverlink", "wildlink"];
const COMPLETION_GAMES = ["linkle", "quadlink", "daily-five", "daily-photo", "daily-chess", "sudoku", "crossword", "landlink", "atomlink", "prizelink", "citylink", "peaklink", "codelink", "thinkerlink", "riverlink", "wildlink"];
export const EPOCH = "2026-10-04";
export const MAX_DATA_BYTES = 60000;
const MAX_WINS = 800;

const isObj = (v) => v && typeof v === "object" && !Array.isArray(v);
const int = (v, lo = 0, hi = 1e7) => (Number.isFinite(v) ? Math.min(hi, Math.max(lo, Math.trunc(v))) : lo);

export function dayIndexUTC(date = new Date()) {
  const [y, m, d] = EPOCH.split("-").map(Number);
  return Math.round((Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()) - Date.UTC(y, m - 1, d)) / 86400000);
}

function cleanStats(s) {
  if (!isObj(s)) return null;
  const dist = {};
  if (isObj(s.dist)) for (const [k, v] of Object.entries(s.dist)) if (/^\d{1,3}$/.test(k)) dist[k] = int(v, 0, 1e6);
  const wins = Array.isArray(s.wins) ? [...new Set(s.wins.map((x) => int(x, 0, 100000)))].sort((a, b) => a - b).slice(-MAX_WINS) : [];
  const freezes = Array.isArray(s.freezes) ? [...new Set(s.freezes.map((x) => int(x, 0, 100000)))].sort((a, b) => a - b).slice(-60) : [];
  return {
    played: int(s.played), won: int(s.won), streak: int(s.streak, 0, 100000), max: int(s.max, 0, 100000),
    last: Number.isFinite(s.last) ? Math.trunc(s.last) : -1, dist, wins, freezes,
  };
}

function cleanToday(t) {
  if (!isObj(t)) return null;
  const out = { idx: Number.isFinite(t.idx) ? Math.trunc(t.idx) : -1, done: !!t.done };
  if (Array.isArray(t.guesses)) out.guesses = t.guesses.filter((g) => typeof g === "string" && /^[a-z]{5}$/.test(g)).slice(0, 12);
  if (typeof t.won === "boolean") out.won = t.won;
  if (Array.isArray(t.picks)) out.picks = t.picks.map((x) => int(x, 0, 9)).slice(0, 5);
  if (Array.isArray(t.cells)) out.cells = t.cells.filter((r) => typeof r === "string" && /^[A-Z.#]{0,21}$/.test(r)).slice(0, 21);
  else if (typeof t.cells === "string" && /^[0-9.]{81}$/.test(t.cells)) out.cells = t.cells;      // sudoku
  if (Array.isArray(t.notes)) out.notes = t.notes.map((x) => int(x, 0, 511)).slice(0, 81);
  if (Number.isFinite(t.ply)) out.ply = int(t.ply, 0, 30);
  if (typeof t.key === "string" && /^\d{4}-\d{2}-\d{2}$/.test(t.key)) out.key = t.key;
  for (const k of ["elapsed", "checks", "reveals", "mistakes", "hints"]) if (k in t) out[k] = int(t[k], 0, 1e6);
  return out;
}

function cleanPct(p) {
  if (!isObj(p)) return null;
  return { sum: int(p.sum, 0, 1e9), count: int(p.count, 0, 1e6), best: int(p.best, 0, 100), last: int(p.last, 0, 100) };
}

/** Whitelist and bound everything a client sends. Unknown keys are dropped. */
export function cleanData(data) {
  const out = {};
  if (!isObj(data)) return out;
  for (const g of GAMES) {
    const src = data[g];
    if (!isObj(src)) continue;
    const rec = {};
    const stats = cleanStats(src.stats);
    if (stats) rec.stats = stats;
    const today = cleanToday(src.today);
    if (today) rec.today = today;
    const pct = cleanPct(src.pct);
    if (pct) rec.pct = pct;
    if (isObj(src.best)) {
      rec.best = {};
      for (const [k, v] of Object.entries(src.best)) if (/^[A-Za-z]{3,9}$/.test(k)) rec.best[k] = int(v, 1, 1e6);
    }
    if (isObj(src.scored)) {
      rec.scored = {};
      for (const k of Object.keys(src.scored).slice(-60)) if (/^\d{1,5}$/.test(k)) rec.scored[k] = true;
    }
    if ((g === "crossword" || g === "sudoku") && Number.isFinite(src.clean)) rec.clean = int(src.clean, 0, 100000);
    if (g === "daily-stars") {
      if (typeof src.sign === "string" && /^[A-Za-z]{3,12}$/.test(src.sign)) rec.sign = src.sign;
      if (Array.isArray(src.viewed)) rec.viewed = [...new Set(src.viewed.map((x) => int(x, 0, 100000)))].slice(-120);
    }
    out[g] = rec;
  }
  if (isObj(data.ach)) {
    out.ach = {};
    for (const [k, v] of Object.entries(data.ach).slice(0, 80)) if (/^[a-z0-9-]{2,40}$/.test(k)) out.ach[k] = int(v, 0, 100000);
  }
  if (isObj(data.goals)) {
    const g = data.goals, o = { d: {}, w: {}, banked: int(g.banked, 0, 1e6) };
    if (isObj(g.d)) for (const [k, v] of Object.entries(g.d).slice(0, 90)) if (/^\d{1,5}$/.test(k) && isObj(v)) o.d[k] = { t: int(v.t, 0, 3), q: int(v.q, 0, 15) };
    if (isObj(g.w)) for (const k of Object.keys(g.w).slice(0, 60)) if (/^\d{1,4}$/.test(k)) o.w[k] = 1;
    out.goals = o;
  }
  return out;
}

// A "streak saver" day bridges one missed day, so it counts toward a streak but is not itself a win.
function streakFrom(wins, last, freezes = []) {
  if (!wins.length || last < 0 || !wins.includes(last)) return 0;
  const set = new Set([...wins, ...freezes]);
  let n = 0;
  for (let d = last; set.has(d); d--) n++;
  return n;
}
function longestRun(wins, freezes = []) {
  const all = [...new Set([...wins, ...freezes])].sort((a, b) => a - b);
  let best = 0, run = 0, prev = null;
  for (const w of all) { run = prev !== null && w === prev + 1 ? run + 1 : 1; best = Math.max(best, run); prev = w; }
  return best;
}

function mergeStats(a, b) {
  if (!a) return b;
  if (!b) return a;
  const wins = [...new Set([...(a.wins || []), ...(b.wins || [])])].sort((x, y) => x - y).slice(-MAX_WINS);
  const dist = { ...a.dist };
  for (const [k, v] of Object.entries(b.dist || {})) dist[k] = Math.max(dist[k] || 0, v);
  const freezes = [...new Set([...(a.freezes || []), ...(b.freezes || [])])].sort((x, y) => x - y).slice(-60);
  const last = Math.max(a.last, b.last);
  return {
    played: Math.max(a.played, b.played, wins.length),
    won: Math.max(a.won, b.won, wins.length),
    streak: streakFrom(wins, last, freezes),
    max: Math.max(a.max, b.max, longestRun(wins, freezes)),
    last, dist, wins, freezes,
  };
}

function mergeToday(a, b) {
  if (!a) return b;
  if (!b) return a;
  if (a.idx !== b.idx) return a.idx > b.idx ? a : b;
  if (a.done !== b.done) return a.done ? a : b;
  const size = (t) => (t.guesses ? t.guesses.length : 0) + (t.picks ? t.picks.length : 0) + (t.cells ? t.cells.join("").replace(/\./g, "").length : 0);
  return size(a) >= size(b) ? a : b;
}

/** Combine two saved-progress objects (already passed through cleanData). Never loses progress. */
export function mergeData(a, b) {
  a = cleanData(a); b = cleanData(b);
  const out = {};
  for (const g of GAMES) {
    if (!a[g] && !b[g]) continue;
    const x = a[g] || {}, y = b[g] || {};
    const rec = {};
    const stats = COMPLETION_GAMES.includes(g) ? mergeStats(x.stats, y.stats) : undefined;
    if (stats) rec.stats = stats;
    const today = mergeToday(x.today, y.today);
    if (today) rec.today = today;
    if (x.pct || y.pct) rec.pct = (x.pct?.count || 0) >= (y.pct?.count || 0) ? { ...x.pct, best: Math.max(x.pct?.best || 0, y.pct?.best || 0) } : { ...y.pct, best: Math.max(x.pct?.best || 0, y.pct?.best || 0) };
    if (x.best || y.best) {
      rec.best = { ...(x.best || {}) };
      for (const [k, v] of Object.entries(y.best || {})) rec.best[k] = rec.best[k] ? Math.min(rec.best[k], v) : v;
    }
    if (x.clean || y.clean) rec.clean = Math.max(x.clean || 0, y.clean || 0);
    if (x.scored || y.scored) rec.scored = { ...(x.scored || {}), ...(y.scored || {}) };
    if (g === "daily-stars") {
      rec.sign = y.sign || x.sign;
      if (!rec.sign) delete rec.sign;
      const v = [...new Set([...(x.viewed || []), ...(y.viewed || [])])].sort((p, q) => p - q).slice(-120);
      if (v.length) rec.viewed = v;
    }
    out[g] = rec;
  }
  if (a.ach || b.ach) {
    out.ach = { ...(a.ach || {}) };
    for (const [k, v] of Object.entries(b.ach || {})) out.ach[k] = out.ach[k] !== undefined ? Math.min(out.ach[k], v) : v;
  }
  if (a.goals || b.goals) {
    const x = a.goals || { d: {}, w: {}, banked: 0 }, y = b.goals || { d: {}, w: {}, banked: 0 };
    const d = { ...x.d };
    for (const [k, v] of Object.entries(y.d)) d[k] = d[k] ? { t: Math.max(d[k].t, v.t), q: d[k].q | v.q } : v;
    out.goals = { d, w: { ...x.w, ...y.w }, banked: Math.max(x.banked, y.banked) };
  }
  return out;
}

// ---- anonymous score histograms (percentiles) ----

/** Allowed score range per game. Every score is "lower is better": guesses, misses, or
 *  20-second blocks for the crossword. 99 means the player lost. */
export const SCORE_LIMITS = { linkle: 99, quadlink: 99, "daily-five": 5, "daily-photo": 5, "daily-chess": 99, sudoku: 400, crossword: 400, landlink: 99, atomlink: 99, prizelink: 99, citylink: 99, peaklink: 99, codelink: 99, thinkerlink: 99, riverlink: 99, wildlink: 99 };

export function percentile(buckets, score) {
  let total = 0, worse = 0, same = 0;
  for (const [k, v] of Object.entries(buckets || {})) {
    const s = Number(k);
    total += v;
    if (s > score) worse += v; else if (s === score) same += v;
  }
  const pct = total ? Math.round((100 * (worse + same / 2)) / total) : 0;
  return { total, worse, same, percentile: pct };
}

export function cleanName(name) {
  const n = String(name || "").replace(/\s+/g, " ").trim();
  if (n.length < 2 || n.length > 24) return null;
  if (!/^[A-Za-z0-9 _.\-]+$/.test(n)) return null;
  return n;
}

export const SAVER_GAP_DAYS = 8;   // one streak saver per rolling week

/** Accounts that opted in to a "your streak ends tonight" email, and have a streak worth protecting. */
export function streakAtRisk(data, idx) {
  const risks = [];
  for (const g of ["linkle", "quadlink", "daily-five", "daily-photo", "daily-chess", "sudoku", "crossword", "landlink", "atomlink", "prizelink", "citylink", "peaklink", "codelink", "thinkerlink", "riverlink", "wildlink"]) {
    const s = data?.[g]?.stats, t = data?.[g]?.today;
    if (!s || s.streak < 2 || s.last !== idx - 1) continue;      // played yesterday, so the streak is alive
    if (t && t.idx === idx && t.done) continue;                  // already played today
    risks.push({ game: g, streak: s.streak });
  }
  return risks.sort((a, b) => b.streak - a.streak);
}
