// Chains for the chain videos, from the data Lockerlink publishes (purplelink.llc/games/data), so a video and the game never
// disagree. Modes: of-the-day (a featured star and a far-away star), daily (yesterday's puzzle), player (any player to any other).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.PURPLELINK_BASE || "https://purplelink.llc";
const CACHE = path.join(ROOT, ".cache", "chain-data");
export const EPOCH = Date.UTC(2026, 9, 4);
export const SPORTS = ["nba", "nfl", "mlb", "nhl"];
const TWO = ["Trail Blazers", "Red Sox", "White Sox", "Blue Jays", "Maple Leafs", "Golden Knights", "Blue Jackets", "Red Wings"];

async function getJson(p, maxAgeH = 6) {
  fs.mkdirSync(CACHE, { recursive: true });
  const f = path.join(CACHE, p.replace(/[^A-Za-z0-9._-]/g, "_"));
  if (fs.existsSync(f) && Date.now() - fs.statSync(f).mtimeMs < maxAgeH * 3600e3) return JSON.parse(fs.readFileSync(f, "utf8"));
  const r = await fetch(BASE + p);
  if (!r.ok) throw new Error(`${p}: ${r.status}`);
  const text = await r.text();
  fs.writeFileSync(f, text);
  return JSON.parse(text);
}

export const dayIdx = (d) => Math.round((Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) - EPOCH) / 864e5);
const two = (n) => String(n % 100).padStart(2, "0");
const seasons = (d, a, b) => (d.cfg.split ? `${a}-${two(b + 1)}` : a === b ? String(a) : `${a}-${two(b)}`);
const short = (d, f) => d.fs?.[f] || (TWO.find((t) => (d.fr[f] || f).endsWith(t)) ?? (d.fr[f] || f).split(" ").at(-1));

const cache = {};
export async function load(sport) {
  if (cache[sport]) return cache[sport];
  const main = await getJson(`/games/data/sports-${sport}.json`);
  let extra = [];
  try { extra = (await getJson(`/games/data/sports-${sport}-all.json`, 24)).p; } catch { /* the famous pool alone still works */ }
  const players = [];
  const add = (n, pos, tier, ovr, st) => players.push({ i: players.length, n, pos, tier, ovr, st, first: Math.min(...st.map((s) => s[1])), last: Math.max(...st.map((s) => s[2])) - 1 });
  main.p.forEach((r) => add(r[0], r[1], r[2], r[3], r[4]));
  extra.forEach((r) => add(r[0], r[1] || "", 0, 0, r[3]));
  const byName = new Map(players.map((p) => [p.n, p]));
  const buckets = new Map();
  players.forEach((p) => p.st.forEach(([f, a, b]) => { for (let y = a; y < b; y++) { const k = `${f}|${y}`; (buckets.get(k) || buckets.set(k, []).get(k)).push(p); } }));
  return (cache[sport] = { sport, main, players, byName, buckets, name: main.name });
}

function neighbors(D, p) {
  const seen = new Set(), out = [];
  for (const [f, a, b] of p.st) for (let y = a; y < b; y++) for (const q of D.buckets.get(`${f}|${y}`) || []) if (q !== p && !seen.has(q.i)) { seen.add(q.i); out.push(q); }
  return out;
}
export function distances(D, src) {
  const dist = new Map([[src.i, 0]]), q = [src];
  for (let k = 0; k < q.length; k++) for (const v of neighbors(D, q[k])) if (!dist.has(v.i)) { dist.set(v.i, dist.get(q[k].i) + 1); q.push(v); }
  return dist;
}
function overlap(a, b) {
  let best = null;
  for (const [fa, sa, ea] of a.st) for (const [fb, sb, eb] of b.st) if (fa === fb && sa < eb && sb < ea) {
    const lo = Math.max(sa, sb), hi = Math.min(ea, eb);
    if (!best || hi - lo > best[2] - best[1] + 1) best = [fa, lo, hi - 1];
  }
  return best;
}
// A shortest chain from a to b; where several exist, the best-known players are preferred as the in-between links.
export function shortest(D, a, b) {
  const dist = distances(D, b);
  if (!dist.has(a.i)) return null;
  const path_ = [a];
  while (path_.at(-1) !== b) {
    const u = path_.at(-1), d = dist.get(u.i);
    const next = neighbors(D, u).filter((v) => dist.get(v.i) === d - 1).sort((x, y) => (y.tier * 100 + y.ovr) - (x.tier * 100 + x.ovr) || (x.n < y.n ? -1 : 1))[0];
    path_.push(next);
  }
  return path_;
}

export function toChain(D, pathPlayers, kind, day) {
  const career = (p) => seasons(D.main, p.first, p.last);
  return {
    sport: D.sport, league: D.name, kind, day,
    players: pathPlayers.map((p) => ({ name: p.n, pos: p.pos, span: career(p) })),
    hops: pathPlayers.slice(1).map((p, i) => { const o = overlap(pathPlayers[i], p); return { team: short(D.main, o[0]), seasons: seasons(D.main, o[1], o[2]), year: o[1] }; }),
  };
}

const rngOf = (seed) => { let a = 0; for (const c of seed) a = (Math.imul(a ^ c.charCodeAt(0), 16777619) + 0x6D2B79F5) | 0; return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };

/** A featured star and a star from a very different era, so the chain has something to cross. */
export async function ofTheDay(date, sport) {
  const idx = dayIdx(date);
  const rot = (await getJson("/games/data/sports-index.json")).rotation;
  const sp = sport || rot[((idx % rot.length) + rot.length) % rot.length];
  const D = await load(sp);
  const stars = D.players.filter((p) => p.tier >= 4).sort((x, y) => (x.n < y.n ? -1 : 1));
  const r = rngOf(`day-${idx}-${sp}`);
  const a = stars[Math.floor(r() * stars.length)];
  const dist = distances(D, a);
  const far = stars.filter((s) => s !== a && dist.has(s.i)).map((s) => ({ s, gap: Math.abs(s.first - a.first), d: dist.get(s.i) }))
    .filter((x) => x.d >= 3).sort((x, y) => y.gap - x.gap).slice(0, 6);
  const pool = far.length ? far : stars.filter((s) => s !== a && dist.has(s.i)).map((s) => ({ s, gap: 0, d: dist.get(s.i) })).sort((x, y) => y.d - x.d).slice(0, 6);
  const b = pool[Math.floor(r() * pool.length)].s;
  return toChain(D, shortest(D, a, b), "of-the-day", date);
}

/** Yesterday's puzzle: the pair everyone was given, and its shortest chain. */
export async function daily(date) {
  const idx = dayIdx(date);
  const rot = (await getJson("/games/data/sports-index.json")).rotation;
  const sp = rot[((idx % rot.length) + rot.length) % rot.length];
  const D = await load(sp);
  const [a, b] = D.main.tl[Math.floor(idx / rot.length) % D.main.tl.length];
  return toChain(D, shortest(D, D.byName.get(a), D.byName.get(b)), "daily", date);
}

/** Any player to any other (or to a far-era star when no target is given). */
export async function player(name, to, sport) {
  const sports = sport ? [sport] : SPORTS;
  for (const sp of sports) {
    const D = await load(sp);
    const a = D.byName.get(name);
    if (!a) continue;
    let b = to ? D.byName.get(to) : null;
    if (to && !b) throw new Error(`${to} is not in the ${D.name} data`);
    if (!b) {
      const dist = distances(D, a);
      const stars = D.players.filter((p) => p.tier >= 4 && p !== a && dist.has(p.i) && dist.get(p.i) >= 2 && dist.get(p.i) <= 5);
      stars.sort((x, y) => Math.abs(y.first - a.first) - Math.abs(x.first - a.first) || dist.get(y.i) - dist.get(x.i));
      b = stars[0];
    }
    return toChain(D, shortest(D, a, b), "player", new Date());
  }
  throw new Error(`${name} was not found${sport ? ` in ${sport}` : ""}`);
}

// ---- words for the narrator ----
const NUM = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
const lastName = (n) => { const w = n.replace(/[.,]/g, "").split(" ").filter((x) => !/^(jr|sr|ii|iii|iv)$/i.test(x)); return w.length > 1 ? w.at(-1) : w[0]; };

export function narration(chain) {
  const P = chain.players, n = chain.hops.length, A = P[0].name, B = P.at(-1).name;
  const hook = chain.kind === "daily"
    ? `Yesterday's Lockerlink: link ${A} to ${B}. The shortest chain is ${NUM[n]} links.`
    : `How is ${A} connected to ${B}? Through teammates, in ${NUM[n]} links.`;
  const hops = chain.hops.map((h, k) => {
    const a = lastName(P[k].name), b = lastName(P[k + 1].name), team = `the ${h.team}`;
    if (k === 0) return `${a} shared ${team} with ${b} in ${h.year}.`;
    const v = [`Then ${a} and ${b}: ${team}, ${h.year}.`, `${b} was on ${team} with ${a} in ${h.year}.`, `${a} and ${b} were ${h.team} teammates in ${h.year}.`];
    const line = v[(k - 1) % v.length];
    return k === n - 1 ? line.replace(/^Then /, "And finally ") : line;
  });
  const end = `${NUM[n][0].toUpperCase() + NUM[n].slice(1)} links. Can you beat it? Make your own chain in Lockerlink, free every day.`;
  return [hook, ...hops, end];
}

export function captionFor(chain) {
  const A = chain.players[0].name, B = chain.players.at(-1).name, n = chain.hops.length;
  const tags = { nba: ["nba", "basketball"], nfl: ["nfl", "football"], mlb: ["mlb", "baseball"], nhl: ["nhl", "hockey"] }[chain.sport].concat(["sportstrivia", "lockerlink"]);
  const title = chain.kind === "daily" ? `${A} to ${B} in ${n} links: yesterday's Lockerlink` : `How ${A} connects to ${B} in ${n} teammate links`;
  const body = `${A} to ${B}: ${chain.players.map((p) => p.name).join(", ")}. ${n} links, each a pair of real teammates. Make your own chain, free every day: purplelink.llc/games/lockerlink`;
  return { title: title.slice(0, 100), description: body, hashtags: tags, text: `${body}\n\n${tags.map((t) => "#" + t).join(" ")}` };
}
