# Weekly crossword clues: routine prompt

The Daily Crossword needs a clue file for every day. A weekly routine writes them, Saturdays 12:00 UTC
(`0 12 * * 6`) in a claude.ai cloud session. The routine is owned by a claude.ai account other than the one the
desktop sessions use, so it cannot be seen or edited from here. On 2026-10-31 and 2026-11-07 it produced nothing
(no cloud-session commit landed after 2026-10-28), the clue runway ran down to 2026-11-14, and its prompt existed
only in an old session transcript. This file keeps the prompt in the repo.

The prompt below replaces the 2026-10-06 version. It opens a pull request and merges only when checks pass, as the
10-17 and 10-24 runs already did, instead of the original direct push to `main`. The Daily Stars routine that ran
beside it is retired with the games freeze (2026-11-12) and must stay off.

## Prompt

```text
You write clues for the Daily Crossword at purplelink.llc/games/crossword/. Work in the repo root of
purplelink-llc/purplelink. Read docs/games.md first: its 'Crossword clue rules' section is binding.

GOAL: every day from today through today plus 21 days has a grid AND a clue file.

1. Start from a fresh branch off origin/main: `git fetch origin main && git switch -c games/crossword-clues-$(date -u +%F) origin/main`.
   List the files in scripts/games-data/crossword/. Each date has DATE.grid.json (the answers, already generated
   and fixed) and, once clued, DATE.clues.json. If there are fewer than 22 grid files dated today or later, create
   the missing ones with `python3 scripts/gen_crossword.py --ahead 24` (it only creates grids that do not exist; a
   Sunday 15x15 can take several minutes, wait for it). Never delete or regenerate an existing grid file.
2. For every date from today through today+21 that has a grid but no clues file: open its grid file (the
   `entries` list has number, direction and `answer` for every entry; `weekday` sets the difficulty). Write one
   original clue per distinct answer following docs/games.md. Look at two recent clue files for style first.
3. Put the clues for one date in lines `ANSWER: clue` and pipe them through
   `python3 scripts/games-data/clues_write.py DATE` (heredoc on stdin). It prints MISSING answers and any PROBLEM
   the validator found, and writes DATE.clues.json only when everything is clean. Fix every message and rerun
   until it says 'written'.
4. Accuracy: only state facts you are certain of; if unsure, use a safer definition of the word. Do not reuse a
   clue sentence from any published crossword. No politics, sexual or graphic content, brands or promotion. Match
   part of speech, tense and number. Mark abbreviations and foreign words. Plain ASCII, no dashes. If a grid
   contains an answer that is offensive, a slur, a drug or sexual term, or an obscure proper name you cannot clue
   safely, do not clue that date: say so in the PR body and leave it for a human.
5. Run `python3 scripts/gen_games.py`, then `python3 scripts/check_games.py --strict`,
   `python3 scripts/check_crossword.py` and `python3 scripts/check_content.py --strict`. Fix anything that fails.
6. `git add scripts/games-data/crossword site/games/data/crossword.json`, commit as
   'games: crossword clues through DATE' (DATE = the last date you clued), push the branch, and open a PR with
   `gh pr create`. Wait for every check to finish; when all are green, squash-merge it. Never push to main.
   Never use [deploy now]; the next scheduled site build publishes it.

If every date through today+21 already has clues, change nothing.
```
