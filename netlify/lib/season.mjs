// Server copy of the Unbeaten season model (site/games/season.js), so a daily result can be replayed from the roster instead
// of trusted. netlify/tests/ratings.test.mjs keeps the two in step. The pool comes from netlify/lib/sports-pool.json, written by
// scripts/gen_sports.py: per sport its settings and every famous player as [name, slot group, tier, rating, stints].

const COST = { 1: 1, 2: 2, 3: 3, 4: 5, 5: 7 };
const REPLACEMENT = 60;

export function hash(str) { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
export function rng(seed) {
  let a = typeof seed === "number" ? seed >>> 0 : hash(String(seed));
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

export function prepare(entry) {
  const players = entry.p.map(([n, g, tier, ovr, st]) => ({ n, g, tier, ovr, st, first: Math.min(...st.map((s) => s[1])) }));
  const byName = new Map(players.map((p) => [p.n, p]));
  return { cfg: entry.cfg, players, byName };
}

const cost = (p) => COST[p.tier];

/** The weekday rule (0 = Sunday), as in constraint() in season.js. */
export function constraint(cfg, dow) {
  const era = cfg.era || 1990;
  return [
    { cap: 4, ok: () => true }, { cap: 0, ok: () => true }, { cap: 0, ok: (p) => p.first < era }, { cap: 0, ok: (p) => p.first >= era + 10 },
    { cap: 0, ok: (p) => p.tier < 5 }, { cap: -4, ok: () => true }, { cap: 0, ok: (p) => p.tier >= 3 },
  ][((dow % 7) + 7) % 7];
}

function teammates(a, b) { return a !== b && a.st.some(([fa, sa, ea]) => b.st.some(([fb, sb, eb]) => fa === fb && sa < eb && sb < ea)); }

function strength(d, starters, bench) {
  const nB = d.cfg.bench, w = d.cfg.slots.length > 8 ? 0.82 : 0.72;
  const mean = (a) => (a.length ? a.reduce((x, p) => x + p.ovr, 0) / a.length : 0);
  const benchMean = nB ? (bench.reduce((a, p) => a + p.ovr, 0) + Math.max(0, nB - bench.length) * REPLACEMENT) / nB : 0;
  const base = nB ? w * mean(starters) + (1 - w) * benchMean : mean(starters);
  const all = starters.concat(bench); let pairs = 0;
  for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) if (teammates(all[i], all[j])) pairs++;
  return { rating: base + Math.min(4, pairs * 0.4), pairs };
}

const winProb = (rating, opp, scale) => 1 / (1 + Math.exp(-(rating - opp) / scale));

function league(d, seed) {
  const r = rng("league-" + seed), n = d.cfg.teams - 1, out = [];
  for (let i = 0; i < n; i++) { let z = 0; for (let k = 0; k < 6; k++) z += r(); z = (z - 3) / 0.7071; out.push(d.cfg.base - 4 + 4.5 * z); }
  return out.sort((a, b) => b - a);
}

function seriesWin(r, p, games) {
  const need = Math.ceil((games + 0.5) / 2); let a = 0, b = 0;
  while (a < need && b < need) { if (r() < p) a++; else b++; }
  return { won: a === need, a, b };
}

export function simulate(d, starters, bench, seed) {
  const cfg = d.cfg, r = rng("season-" + seed), str = strength(d, starters, bench), L = league(d, seed);
  const order = L.slice(); for (let i = order.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); const t = order[i]; order[i] = order[j]; order[j] = t; }
  let wins = 0, losses = 0, pAll = 1;
  for (let g = 0; g < cfg.games; g++) { const p = winProb(str.rating, order[g % order.length], cfg.scale); pAll *= p; if (r() < p) wins++; else losses++; }
  const res = { rating: str.rating, wins, losses, perfect: pAll, champion: false, made: wins / cfg.games >= 0.5 };
  if (!res.made) return res;
  const field = L.slice(0, Math.min(L.length, 8));
  for (let k = 0; k < cfg.rounds.length; k++) {
    const oppR = field[Math.min(field.length - 1, field.length - 1 - Math.floor((k / cfg.rounds.length) * (field.length - 1)))];
    if (!seriesWin(r, winProb(str.rating, oppR, cfg.scale), cfg.rounds[k]).won) return res;
  }
  res.champion = true;
  return res;
}

/** Check a submitted roster against the day's rule and budget and play its season. `names` is starters then bench, "" for an empty spot. */
export function replay(d, sport, idx, names) {
  const slots = d.cfg.slots, total = slots.length + d.cfg.bench;
  if (!Array.isArray(names) || names.length !== total || names.some((n) => typeof n !== "string")) return { ok: false, error: "bad_roster" };
  const picks = names.map((n) => (n ? d.byName.get(n) : null));
  if (names.some((n, i) => n && !picks[i])) return { ok: false, error: "bad_roster" };
  if (picks.slice(0, slots.length).some((p, i) => !p || p.g !== slots[i])) return { ok: false, error: "bad_roster" };
  const used = picks.filter(Boolean);
  if (new Set(used.map((p) => p.n)).size !== used.length) return { ok: false, error: "bad_roster" };
  const rule = constraint(d.cfg, idx % 7);
  if (used.some((p) => !rule.ok(p))) return { ok: false, error: "bad_roster" };
  if (used.reduce((a, p) => a + cost(p), 0) > d.cfg.cap + rule.cap) return { ok: false, error: "over_budget" };
  const starters = picks.slice(0, slots.length), bench = picks.slice(slots.length).filter(Boolean);
  const res = simulate(d, starters, bench, "d" + idx + sport + "|" + names.join("|"));
  return { ok: true, res };
}
