# haea how-to video and Short: script

Written 2026-10-25, following the Watchlight precedent (`video/src/products/watchlight*.js`). Two cuts, rendered by
`video/build-stills.mjs` (phone frame, still-driven):

- Long: "How haea works" (16:9, about 2:40), storyboard `video/storyboards/haea-howto.json`, plan
  `video/src/products/haeahowto.js`.
- Short (9:16, under 60 s), storyboard `video/storyboards/haea-short.json`, plan `video/src/products/haeashort.js`.

Voice: Kokoro bf_emma (storyboards name en-GB-SoniaNeural at +4%, as Watchlight). Music: the shared trend-style synth
bed, never a recording. Both cuts open and close with the Purplelink LLC bumper.

## Footage rules

- Captured from the app source in a dedicated simulator (iPhone 17 Pro Max, iOS 26.3), status bar 9:41, light
  appearance. Demo data only (the app's own demo seeder); no real health data. The narration says so once.
- The capture build is a scratch copy with a launch-argument hook that loads the demo data and picks the first tab;
  nothing in the app repo changed. Route screen: a made-up loop in a public park, routed by Apple Maps.
- Not shown: the paywall (the simulator has no StoreKit products), prices on screen, anything from real Health data.
- The name is always lowercase: haea.

## Claims rules applied

Features named are the ones on the App Store listing: daily readiness briefing, strength log, running with route
planning, Insights with small tests, on-device coach (Apple Intelligence on supported iPhones). No food logging (haea
only reads nutrition other apps write to Apple Health). Not medical advice, said once, over the app's own terms screen.
Prices are written in the description only, never on screen or in the voice-over. The video does not say the app
is or is not on the App Store, so it stays true when published.

## Long cut

| # | Screen | Narration |
|---|--------|-----------|
| 0 | today | This is haea, an iPhone app from Purplelink that reads Apple Health and gives you a daily readiness briefing. All of the analysis runs on the iPhone. Everything on screen in this video is demo data. |
| 1 | today (score) | The Today tab opens with the briefing: a readiness score, a short headline, and one suggestion for the day. Here the score is sixty-four, and the suggestion is a twenty-minute walk. |
| 2 | today (warning, tiles) | Below that, a warning shows up only when something stands out, like sleep debt over the last five nights. Today's health shows sleep, movement, recovery and fuel, each with a seven-day trend. |
| 3 | today (tiles) | haea gets this from Apple Health: sleep, heart rate, heart rate variability, workouts and weight. You choose what to allow. It reads nutrition that other apps write there, and it doesn't log food itself. |
| 4 | strength | The Strength tab is your workout log. Tap Start workout, then choose one of your own routines or a program. |
| 5 | strength (level, volume) | It shows weekly volume by muscle, personal records with estimated one-rep maxes, and your strength level against population standards. A deload check watches your fatigue. |
| 6 | running | The Running tab tracks runs on iPhone or Apple Watch. It suggests runs for the week, and shows training load, weekly distance and personal records. |
| 7 | route | To plan a route, tap points on the map. haea can follow paths between them, using Apple Maps, and shows the distance as you go. Then you can follow the route on a run. |
| 8 | insights | Insights asks one question: what moves your sleep, running pace, weight or mood? Pick an outcome, and haea ranks your habits by how strongly each one is linked, using your own data. |
| 9 | insights (small test) | A link isn't proof that one thing causes another. To check one, tap Try a small test, and change a single habit. |
| 10 | coach | The Coach tab answers questions about your training. It uses Apple Intelligence on the device, on iPhones that support it. |
| 11 | today | haea has no account, no cloud sync, no ads and no tracking. Your records stay in a database on the iPhone. |
| 12 | terms | haea is for general wellness. It is not medical advice, and it doesn't diagnose or treat anything. For medical questions, talk to a doctor. |
| 13 | today | haea is free to download. The briefing, strength log and running work without paying. An optional Premium subscription adds deeper analysis. The options are in the description. |
| 14 | today (end card) | haea. Your Apple Health data, analyzed on your iPhone. |

## Short

| # | Narration |
|---|-----------|
| 0 | haea reads Apple Health and gives you a daily readiness briefing, all analyzed on your iPhone. |
| 1 | One score, one suggestion for the day, and a warning only when something stands out. |
| 2 | Log strength workouts, and see weekly volume, personal records and a deload check. |
| 3 | Plan a running route on the map, then follow it on your run. |
| 4 | Insights shows which habits move your sleep, pace, weight or mood. |
| 5 | No account, no cloud sync, no ads. General wellness, not medical advice. |
| 6 | haea, free on iPhone. The full tour is on our channel. |
