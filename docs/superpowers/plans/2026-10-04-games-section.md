# Games section implementation plan

> Spec: docs/superpowers/specs/2026-10-04-games-section-design.md. Executed inline in one worktree (branch `games`), one task at a time, each verified in the browser before the next.

**Goal:** /games/ with Linkle, Quadlink, Daily Five and Daily Stars, all refreshing from the date with no daily chore.
**Architecture:** static pages + external JS/CSS; puzzle is a pure function of the local date; `scripts/gen_games.py` writes prefix-stable 730-day data files from committed source lists; `scripts/check_games.py` guards the buffers.
**Stack:** plain JS (no deps), Python 3.12 generators, node:test for the engine.

## Task 1: Word data and generator
- Create `scripts/games-data/` with `valid5.txt` (ENABLE five-letter words, public domain), `answers5.txt` (ENABLE words with wordfreq Zipf >= 3.3, minus plurals, offensive words and words I strike by hand), `SOURCES.md` (licences and attribution).
- Create `scripts/gen_games.py`: seeded shuffles, 730 days; writes `site/games/data/linkle.json`, `quadlink.json`, `valid5.txt`.
- Check: 730 unique-in-a-cycle answers, quadlink days never repeat a word within the day, rerun gives byte-identical output.

## Task 2: Engine
- `site/games/core.js` (UMD): `dayIndex(date, epoch)`, `decode`, `score(guess, answer)` (duplicate-letter correct), `shareGrid`, storage wrapper with try/catch, streak update, `track`.
- `scripts/games-core.test.mjs`: scoring cases (duplicates both ways), day index across DST and month ends, streak update, decode round trip. Run `node --test`.

## Task 3: Shell, hub and Linkle
- `site/games/games.css` (tokens from styles.css, board/keyboard/modal, reduced motion, patterns for colour-blind), `site/games/index.html` (hub), `site/games/linkle/index.html` + `linkle.js`.
- Add "Daily games" to the footer in `scripts/apply_layout.py` and run it; cards on /products/ free section and home.
- Check in the browser pane at 390 px and 1280 px: play a full game, win and lose, restore after reload, keyboard only, share text copy.

## Task 4: Quadlink
- `site/games/quadlink/index.html` + `quadlink.js` on the same engine (four boards, 9 guesses, shared keyboard colouring by best state across boards).

## Task 5: Daily Five
- `scripts/fetch_trivia.py` (Open Trivia DB with session token, 5 s spacing, writes `scripts/games-data/otdb.json`; committed snapshot), `scripts/games-data/academic.json` (authored), filters in `gen_games.py` -> `site/games/data/trivia.json` (2 academic + 3 OTDB per day, answers shuffled with a stored order).
- `site/games/daily-five/index.html` + `daily-five.js`; attribution line for CC BY-SA 4.0.

## Task 6: Daily Stars
- `scripts/games-data/stars-source.txt` (date|sign|text, 14 days x 12 signs written now), `gen_games.py` -> `site/games/data/stars.json`, moon phase computed per date.
- `site/games/daily-stars/index.html` + `daily-stars.js`; label as entertainment; fallback message when a date is missing.
- Weekly refresh routine (prompt carries voice rules) writes the next 14 days and pushes.

## Task 7: Guards and discovery
- `scripts/check_games.py` (>= 60 days of puzzle data ahead for word games and trivia, >= 5 days of horoscopes ahead warns, >= 0 fails build) wired into the netlify.toml build command; sitemap/search/llms entries; JSON-LD; `python3 scripts/check_content.py --strict`.

## Task 8: Ship
- Full test run, preview at both widths, rebase on origin/main, push (push = prod deploy), verify on purplelink.llc.

## Task 9 (added 2026-10-04 at Ben's request): Daily crossword, easiest Monday, hardest Sunday
- `scripts/gen_crossword.py`: symmetric grid templates by weekday (Mon/Tue 9x9, Wed/Thu 11x11, Fri/Sat 13x13, Sun 15x15), backtracking fill from a frequency-scored word list (ENABLE + wordfreq Zipf bands per weekday: Monday only very common words, Sunday allows rarer ones), no themes.
- Clues: WordNet glosses (permissive licence) as a fallback only; the weekly content routine has Claude write original clues for the next 14 puzzles into `scripts/games-data/clues/<date>.json`. `check_games.py` rejects a clue that contains its answer or is missing.
- Not used: scraped crossword clue datasets (NYT and similar) because they are copyrighted.
- `site/games/crossword/` page: keyboard grid, phone entry, check and reveal, timer, share text; same storage and analytics conventions.
- Keep 14 days of clued puzzles ahead; build fails below 3.
