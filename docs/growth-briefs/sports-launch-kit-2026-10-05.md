# Sports games: launch kit (2026-10-05)

Nothing here has been posted or submitted. Every post and form below is yours to send; I have not touched any account.

## Position, in one line

Free daily sports puzzles with players from every era, in four leagues, where the chains are measured over everyone who ever played (about 61,000 players) and there are no third-party ads on the daily games.

Do not claim "first" or "only". Roster Relay, Teammate Chain, Immaculate Grid, Sportsdle, Go Unbeaten and a dozen 82-0 clones exist (see sports-games-market-2026-10-04.md). What is true and specific:

- Teamlink: add players at either end of the chain; par covers everyone back to 1920 (NFL) and 1871 (MLB); a Rival mode that works from a link with no account.
- Gridlink: award clues and a "played with [star]" clue.
- Unbeaten: a budget and an open pick from any era instead of a random spin; ratings from career honors; a weekly recap of the best roster per rule.
- Facts that make good posts, all from our own data: among the 45 biggest NBA stars any two are 2.7 teammate-links apart on average; Bill Russell reaches Jaylen Brown in 5 (Russell, Don Chaney, James Edwards, Randy Brown, Joe Johnson, Brown); LeBron James reaches Cooper Flagg in 2 (through Anthony Davis); Otto Graham to Patrick Mahomes takes 6 in the NFL; Shohei Ohtani to Ted Williams takes 5 (through Albert Pujols, Mark McGwire, Reggie Jackson and Jim Pagliaroni).

## Timing (why now)

October: NBA and NHL seasons open, the NFL is mid-season, MLB is in the postseason and the World Series starts late in the month. The weekly shortest-chain recaps give a fresh item every Monday.

## What is already built to spread

- Share text on every result with a tracked link (from=share-native, share-x, share-reddit, and so on).
- Rival mode: finish a puzzle, press Challenge a friend, the link opens the same pair for them (from=share-rival).
- Five static pages that answer questions people search: /games/sports/ and the four /games/sports/<league>-teammate-chains/ pages.
- Read the results in the first-party stats page by event type (game_share, games_signup) and by the ?from= label.

## Channels, in the order I would use them

1. **Reddit, as a person, not an ad.** Read each subreddit's rules first; most sports subs ban self-promotion outright. Safe places: r/WebGames and r/incremental_games-style game subs for the games themselves; sport subs only for the fact posts below, only if the rules allow links to your own site, and ideally as a reply when someone asks for "Immaculate Grid alternatives" or a teammate game. Post once per sub, say you made it, and answer comments.
2. **Show HN** (news.ycombinator.com): the angle is the data work, not the games.
3. **Directories and lists** of daily games (submit by hand): Listdle (listdle.com), Sportsdle's dle-games list (sportsdle.com/dle-games, if it takes submissions), "Wordle alternatives for sports fans" posts (shurzy.com and similar: ask the author to add you), AlternativeTo (alternativeto.net), Product Hunt, BetaList.
4. **X and Threads**: one fact post a week from the degrees pages, with the chain as text (no emojis; the site rule applies to our own posts too).
5. **Newsletters and podcasts** for sports-data fans: pitch the degrees pages, not the games.

## Drafts (paste-ready)

### r/WebGames or a general games subreddit

Title:
```
I made three free daily sports puzzles (NBA, NFL, MLB, NHL): link two players through teammates, fill a grid, build a perfect-season roster
```
Body:
```
I build small tools for researchers and made these on the side. The sport changes each day (NBA, NFL, MLB, NHL).

Teamlink: you get two players, often from different eras, and chain real teammates between them. You can add players at either end. The shortest chain is "par", measured over every player who ever played in the league (about 61,000 across the four), so you can use anyone, not just stars.

Gridlink: a 3x3 grid. Clues are teams, decades, positions, awards, or "played with LeBron James". Nine guesses.

Unbeaten: a budget, a rule that changes each weekday, and any player from any era. Ratings come from career honors. Then it plays the season and shows your exact chance of going undefeated.

Free, no account, no third-party ads on the daily games. https://purplelink.llc/games/sports/

The data is from Lahman (MLB), nflverse (NFL) and Wikipedia (NBA, NHL), and it has gaps; the pages say where. Happy to take feedback on anything that looks wrong.
```

### A fact post for a sport subreddit (only if the rules allow it)

Title:
```
How many teammate links separate Bill Russell from Jaylen Brown? Five.
```
Body:
```
Russell, Don Chaney (Celtics 1968-69), James Edwards (Lakers 1977-78), Randy Brown (Bulls 1995-96), Joe Johnson (Celtics 2001-02), Jaylen Brown (Celtics 2021-22).

Across the 45 biggest NBA stars, any two are on average 2.7 teammate-links apart. I put the longest chains between legends from different eras here: https://purplelink.llc/games/sports/nba-teammate-chains/

Some of the links go through role players, so I would love corrections or a shorter chain if you can find one.
```

### Show HN

Title:
```
Show HN: Daily sports puzzles built on a teammate graph of 61,000 players
```
Body:
```
I joined player histories for the NBA, NFL, MLB and NHL (Lahman, nflverse, Wikipedia) into one graph where two players are linked if they shared a franchise and a season. Teamlink asks for the shortest chain between two players; Gridlink is a 3x3 clue grid; Unbeaten is a budgeted roster builder with a season simulator. Ratings in Unbeaten come from career honors. The interesting parts were matching same-name players across sources and removing coaching stints that looked like playing time. Free, no account. https://purplelink.llc/games/sports/
```

### X or Threads (weekly)

```
Teamlink fact: Otto Graham to Patrick Mahomes is 6 teammate links in the NFL. Shohei Ohtani to Ted Williams is 5 in MLB. Connor McDavid to Gordie Howe is 4 in the NHL. Try today's chain: https://purplelink.llc/games/teamlink/
```

### Listdle or AlternativeTo entry

```
Name: Purplelink Sports Games (Teamlink, Gridlink, Unbeaten)
Short: Free daily NBA, NFL, MLB and NHL puzzles: link two players through teammates, fill a clue grid, or build a roster and play a perfect season. Players from every era, no account.
Category: sports, daily puzzle
URL: https://purplelink.llc/games/sports/
Alternatives to list: Immaculate Grid, Roster Relay, Teammate Chain, Sportsdle
```

## Four-week plan

- Week 1: submit to the directories (one sitting), post the games draft on one games subreddit, check the stats page for from= labels.
- Week 2: the Russell to Brown fact post in a sport subreddit that allows it; one X post.
- Week 3: Show HN; the next weekly recap becomes the X post.
- Week 4: look at what worked (which source label brought players who finished a puzzle and came back), then double down on that one channel.

## Measure

Players who finish a second puzzle on another day matter more than visits. The first-party stats page counts game_share and games_signup events; compare by from= label.
