// Puzzle ratings for Chess Puzzles and Sudoku Unlimited: an Elo update, plus the checks the rating service applies
// to every report. The browser keeps a copy of the same formulas (site/games/ratings.js) for players who are not
// signed in; netlify/tests/ratings.test.mjs keeps the two in step.

export const START_RATING = 1000;
export const MIN_RATING = 400;
export const MAX_RATING = 3200;
export const LEVEL_RATING = [0, 900, 1250, 1600, 1950, 2300];       // Sudoku level 1 (Beginner) to 5 (Expert)
export const PAR_SECONDS = [0, 300, 480, 720, 1080, 1500];            // a typical clean solve per level
export const MIN_SECONDS = [0, 40, 55, 70, 90, 110];                  // faster than this is not a solve
export const MIN_MS_PER_MOVE = 600;                                   // chess: per move the player has to make
export const DAILY_REPORT_CAP = 1500;

export function expected(player, puzzle) { return 1 / (1 + Math.pow(10, (puzzle - player) / 400)); }
export function kFactor(n, r) { return n < 20 ? 48 : n < 60 ? 32 : r >= 2400 ? 16 : 24; }

/** score is 0 to 1. Returns the new rating (rounded, clamped) and the change. */
export function nextRating(rec, puzzleRating, score) {
  const r = rec.r, k = kFactor(rec.n, r);
  const raw = r + k * (score - expected(r, puzzleRating));
  const nr = Math.min(MAX_RATING, Math.max(MIN_RATING, Math.round(raw)));
  return { r: nr, delta: nr - r };
}

/** Sudoku score from how the puzzle ended: "clean" (no check or reveal), "help", or "skip" (gave up). */
export function sudokuScore(result, seconds, level) {
  if (result === "skip") return 0;
  if (result === "help") return 0.35;
  const p = PAR_SECONDS[level];
  return seconds <= p / 2 ? 0.95 : seconds <= p ? 0.8 : seconds <= 2 * p ? 0.6 : 0.5;
}

export function emptyRecord() {
  return { r: START_RATING, n: 0, w: 0, peak: START_RATING, streak: 0, best: 0, wk: -1, wr0: START_RATING, wn: 0, day: "", dn: 0 };
}

/** Monday-to-Sunday week number of a puzzle-day index (day 0, 2026-10-04, is a Sunday). */
export function weekOf(dayIdx) { return Math.floor((dayIdx + 6) / 7); }

/** Apply one finished puzzle to a record. `solved` drives the streak; returns { rec, delta }. */
export function applyResult(rec, { puzzleRating, score, solved, dayIdx, dayKey }) {
  const next = { ...emptyRecord(), ...rec };
  const wk = weekOf(dayIdx);
  if (next.wk !== wk) { next.wk = wk; next.wr0 = next.r; next.wn = 0; }
  if (next.day !== dayKey) { next.day = dayKey; next.dn = 0; }
  const { r, delta } = nextRating(next, puzzleRating, score);
  next.r = r; next.n += 1; next.wn += 1; next.dn += 1;
  if (solved) { next.w += 1; next.streak += 1; next.best = Math.max(next.best, next.streak); } else next.streak = 0;
  next.peak = Math.max(next.peak, r);
  return { rec: next, delta };
}

/** Validate a report. Returns { ok: true, puzzleRating, score, solved } or { ok: false, error }. */
export function checkReport(game, b, chessIndex) {
  const ms = Number(b.ms);
  if (!Number.isFinite(ms) || ms < 0 || ms > 6 * 3600 * 1000) return { ok: false, error: "bad_time" };
  if (game === "chess") {
    const id = String(b.id || "");
    const meta = chessIndex[id];
    if (!meta) return { ok: false, error: "unknown_puzzle" };
    const solved = b.result === "solved";
    if (!solved && b.result !== "failed") return { ok: false, error: "bad_result" };
    const yourMoves = Math.floor(meta[1] / 2);
    if (solved && ms < yourMoves * MIN_MS_PER_MOVE) return { ok: false, error: "too_fast" };
    return { ok: true, puzzleRating: meta[0], score: solved ? 1 : 0, solved };
  }
  if (game === "sudoku") {
    const m = /^([1-5])-(\d{1,4})$/.exec(String(b.id || ""));
    if (!m) return { ok: false, error: "unknown_puzzle" };
    const level = Number(m[1]), result = String(b.result || "");
    if (!["clean", "help", "skip"].includes(result)) return { ok: false, error: "bad_result" };
    const seconds = ms / 1000;
    if (result !== "skip" && seconds < MIN_SECONDS[level]) return { ok: false, error: "too_fast" };
    return { ok: true, puzzleRating: LEVEL_RATING[level], score: sudokuScore(result, seconds, level), solved: result !== "skip" };
  }
  return { ok: false, error: "unknown_game" };
}

const BLOCKED = /\b(fuck|shit|cunt|nigg|fagg|rape|nazi|hitler|bitch|whore|slut|dick|cock|pussy|retard)/i;
/** Public names go on a leaderboard, so they are checked a little more than a private display name. */
export function publicNameOk(name) { return !!name && name.length >= 2 && !BLOCKED.test(name.replace(/[^a-z]/gi, "")) && !BLOCKED.test(name); }

export function boardRow(game, rec, name, acct, board) {
  return { a: acct, name, r: rec.r, n: rec.n, g: board === "week" ? rec.r - rec.wr0 : 0, wn: rec.wn };
}

/** Insert or replace one account's row and keep the board sorted and capped. */
export function upsertRow(rows, row, board, cap = 100) {
  const next = rows.filter((x) => x.a !== row.a);
  if (board === "all" || row.wn >= 3) next.push(row);
  next.sort(board === "week" ? (x, y) => y.g - x.g || y.r - x.r : (x, y) => y.r - x.r || y.n - x.n);
  return next.slice(0, cap);
}
