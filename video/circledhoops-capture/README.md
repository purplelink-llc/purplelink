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
5. Narration: `narration-lines.json` through `TikTokPipeline/shared_media/kokoro_local.py`, one `<id>.mp3` +
   `<id>.words.json` per line (ids a1..a7, b1..b7, c1..c6).
