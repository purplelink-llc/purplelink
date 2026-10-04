# Games section design (2026-10-04)

Status: draft for Ben's review. Decisions already made by Ben (2026-10-04): launch set is all four (word game, four-board word game, trivia, horoscope); no ads on /games/ until AdSense approves the rest of the site; trivia comes from Open Trivia DB plus our own academic set.

## Goal
A free /games/ section with daily puzzles that refresh themselves, so it earns return visits and search traffic without a daily chore. No accounts, no server, no cookies.

## Working names (rename freely; avoid the trademarked Wordle and Quordle)
- Linkle: 5-letter daily word game, 6 guesses.
- Quadlink: four boards at once, 9 guesses, same dictionary.
- Daily Five: five multiple-choice trivia questions.
- Daily Stars: a short daily horoscope for each of the 12 signs, labeled as entertainment.

## Architecture
- Static pages under `site/games/` (hub, one page per game), plain HTML with a rules and FAQ section so no page is thin. Game logic in external JS files, styles in `site/games/games.css`, both fingerprinted by the existing build. No inline styles or scripts; self-hosted only.
- A puzzle is a pure function of the date. `scripts/gen_games.py` runs in the existing Netlify build and writes `site/games/data/*.json` covering the next 365 days (shuffled with a fixed seed so order is not guessable from the list). The client picks today's entry by the visitor's local date, so "today" matches their calendar.
- Valid-guess list: ENABLE word list (public domain). Answers: its common five-letter words, filtered by a frequency list; licence of the frequency source is checked in the plan before use. Quadlink draws four answers per day from the same answer set with no repeats inside a day.
- Trivia: an Open Trivia DB snapshot committed as JSON (CC BY-SA 4.0, credit on the page) plus an authored academic/science/Mac set. Daily five picked by date seed with mixed categories and difficulty.
- Horoscope: a weekly content routine writes the next 14 days of 12 sign readings into `site/games/data/stars.json` (same pattern as the weekly blog routine). If a date is missing the page falls back to a plain "check back" message rather than showing stale text.
- Health check: `scripts/check_games.py` joins the build checks and fails the build if any game has fewer than 14 days of content ahead, so a stalled pipeline shows up as a red build, not a silent gap.
- Progress and streaks: localStorage only, every access in try/catch, page works without it. Events go through the existing first-party `analytics.js` (play started, finished, won), no third party.

## Design rules (from DESIGN.md and CLAUDE.md)
- Dark default, OKLCH tokens already in `site/styles.css`; `:where(:root:not([data-theme="light"]))` for dark overrides; no `prefers-color-scheme` rules.
- No emojis anywhere, including share text. Share text uses plain characters: filled square for correct, square with dot for present, empty square for absent, plus the puzzle number and score.
- Colour is never the only signal (letters, patterns, aria labels). Full keyboard play, `aria-live` results, `prefers-reduced-motion` honoured, WCAG 2.1 AA contrast.
- Copy is calm and plain: say what the game is and how it scores. No marketing buzzwords.
- Horoscope pages state that the text is for entertainment and is not advice. No health, money or relationship claims.

## Navigation and discovery
- Footer link and a small card on /products/ and the home page; not in the primary nav at launch (the nav audience is researchers and Mac users).
- Add to sitemap, llms.txt and the site search index. JSON-LD per game page.

## Build order
1. Shared shell (hub, games.css, shared JS for date, storage, share, keyboard) and Linkle, with tests for scoring (duplicate letters), date indexing and generator determinism.
2. Quadlink on the same engine.
3. Daily Five (snapshot import script, authored set, attribution).
4. Daily Stars and its weekly routine, plus check_games.py.
Each step ships separately; the next does not start until the previous one is verified in the browser at phone and desktop widths.

## Out of scope for launch
Accounts, leaderboards, ads, answer-archive SEO pages (past answers), multiplayer, sound.

## Risks
- Searchers for "-dle" games expect their exact game; we cannot use those names.
- Horoscope text risks reading as filler; the routine prompt carries the same voice rules as the blog routine and each reading must be specific to the date (moon phase, weekday, season), not generic.
- Open Trivia DB questions vary in quality; the snapshot import drops flagged duplicates and sorts by difficulty, and I review a sample before it goes live.
