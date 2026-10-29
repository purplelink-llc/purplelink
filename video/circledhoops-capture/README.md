# Circled Hoops ad captures

The Reddit ads (`../build-circledhoops.mjs`) use only real screens of the Circled Hoops web app's sample league
(lockin `apps/web`, MSW mock data, no backend), recorded headless at iPhone size (390x844 @3x, 1170x2532).

1. Clone `purplelink-llc/lockin` somewhere scratch, `npm ci --ignore-scripts`, `npm run brand:assets -w @lockin/web`.
2. `python3 fictionalize.py <lockin> name-map.json` swaps the sample data's real NBA player names for invented ones in
   that scratch copy only (never commit it to lockin). Team abbreviations stay.
3. `cd <lockin>/apps/web && npx next dev -p 3217` (no `NEXT_PUBLIC_API_URL`, so the mocks answer).
4. Copy `caplib.mjs`, `rec-circle.mjs`, `rec-all.mjs` into the lockin checkout (they import its Playwright) and run
   `node rec-circle.mjs <captures>` and `node rec-all.mjs <captures> matchup autoset chat thisweek stills`.
   `caplib.mjs` signs in with the demo account the sample mode offers, hides the draft banner, records with the CDP
   screencast (JPEG frames with timestamps, rebuilt to constant 30 fps), and draws the circle with a real pointer
   gesture, which the pick sheet accepts. Extra stills used: `still-sheet.png` (clip-circle at 2.3 s),
   `still-recap.png` (clip-chat at 0.4 s), `still-draftroom.png` (`/leagues/lg-work/draft`).
   Round 4: `node rec-r4.mjs <captures>/r4`, then copy `clip-ring.mp4`, `r4-sheet-mon.png`, `r4-teams-0.png`,
   `r4-teams-1.png` and `r4-teams-final.png` into the captures folder. It saves Monday as Tariq Monroe's pick, reopens
   the sheet, taps Wednesday and steps the app's own ring animation one frame per 1/30 s (the screencast drops frames
   during a 420 ms animation, which made the mouse-drawn loop look janky); then it creates a new league and adds three
   bots for ad C.
5. Narration: `narration-lines.json` through `TikTokPipeline/shared_media/kokoro_local.py`, one `<id>.mp3` +
   `<id>.words.json` per line (ids a1..a7, b1..b7, c1..c6; round 4 adds a5r4 and c7).
