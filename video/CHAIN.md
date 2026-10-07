# Chain of the day videos

Short animated videos of the shortest teammate chain between two players, in the same style as the product videos (brand
backdrop, Fraunces names, expo-out motion, narration with word-synced captions, the Purplelink bumpers and sting) plus a
Lockerlink call to action. Everything is drawn in `src/Chain.jsx`; there are no photographs. The chains come from the data
Lockerlink publishes (purplelink.llc/games/data), so the video and the game never disagree. Nothing is uploaded or posted.

```
node build-chain.mjs --of-the-day [--sport nba] [--date 2026-10-05]   a featured star and a far-era star (the sport rotates by day)
node build-chain.mjs --daily [--date 2026-10-06]                      yesterday's puzzle and its shortest chain (never today's)
node build-chain.mjs --player "LeBron James" [--to "Cooper Flagg"] [--sport nba]
node build-chain.mjs --batch nba --tier 5 [--limit 10]                one video per star in a league
   --format 9x16 (default, Shorts/Reels/TikTok) | 16x9 (YouTube) | both      --stills 3,9,20   frames only, for a quick look
```

Output goes to `out/chain/<id>/`: `<id>-9x16.mp4`, `<id>-16x9.mp4`, a poster, frames, `caption.json` and `caption.txt`
(title, description and hashtags for the upload) and `run-log.txt`. A 9:16 render takes about 50 seconds. Narration is
`en-GB-SoniaNeural` through edge-tts (needs the network). A video is 28 to 40 seconds with the bumpers.

Notes
- Daily mode shows yesterday's chain so the live puzzle is not spoiled; of-the-day and player mode never use the live pair
  on purpose, but a featured pair can coincide with a puzzle day by chance.
- Chains use every player who ever played in the league, so some in-between players are not household names; the best-known
  players are preferred where several shortest chains exist.
- Posting: YouTube uploads use `scripts/yt-upload.py` (see the youtube-channel notes); TikTok and Instagram need accounts
  that do not exist yet. Ben approves each upload.
- Source files: `chain-data.mjs` (chains and narration), `src/chain/plan.js` (timing), `src/Chain.jsx` (the composition),
  `make-clink.py` (the link sound), `assets/lockerlink.png` (rasterised from the published logo).
