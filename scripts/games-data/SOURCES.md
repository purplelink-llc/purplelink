# Games data sources

- `valid5.txt`: the five-letter words of the ENABLE word list (public domain). Every word is an accepted guess.
- `answers5.txt`: ENABLE words with a Zipf frequency of at least 3.3 in the `wordfreq` package (Robyn Speer et al.; data under CC BY-SA 4.0, https://github.com/rspeer/wordfreq), with regular plurals removed. Only the selection of words was taken, no text. `blocked.txt` then removes names, places, offensive and sensitive words.
- `otdb.json` (added with Daily Five): Open Trivia DB (https://opentdb.com), CC BY-SA 4.0. The page credits it.
- `academic.json`: written for this site.
- `stars-source.txt`: written for this site, entertainment only.

Rule: after launch the answer pool and blocked list are append-only in effect. Changing them reshuffles every future puzzle, so do not edit existing words; add new words only when the pool runs short, and expect puzzle order after that point to change.

## Crossword word list (cw-words.txt)
Built once from ENABLE (public domain) filtered to words that WordNet (Princeton, permissive licence) knows as a lemma or a regular inflection, which drops most names and abbreviations, then limited to wordfreq Zipf >= 2.5 (3-letter words >= 3.0), minus `blocked.txt` and a list of offensive terms. `cw-blocked.txt` removes the remaining crosswordese at fill time. The WordNet step needs `pip install nltk` and the wordnet corpus; it is not run during builds. Clues are written fresh for each puzzle (never copied from any published crossword).
